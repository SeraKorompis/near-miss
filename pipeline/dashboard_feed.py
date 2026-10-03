"""Broadcast the current look and the annotated picture to the dashboard.

The live floor connects to ws://127.0.0.1:8765 and expects:

    {"type": "gaze", "name": "crisps_packs", "dwellMs": 1400, "touch": false}
    {"type": "gaze", "name": null}

The same frames the OpenCV window draws are served as a motion JPEG at
http://127.0.0.1:8766/video. `name` is the zone id from the vision pipeline.
When dwellMs is present, the dashboard shows that duration rather than timing
the look itself.
"""
import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from websockets.asyncio.server import serve


class DashboardFeed:
    def __init__(self, host="127.0.0.1", port=8765):
        self.host = host
        self.port = port
        self.loop = asyncio.new_event_loop()
        self.clients = set()
        self._last = None
        self._payload = None
        self._thread = None
        self._jpeg = None
        self._frame_id = 0
        self._frame_cond = threading.Condition()
        self.video_port = port + 1

    def start(self):
        ready = threading.Event()
        errors = []

        def run():
            asyncio.set_event_loop(self.loop)
            try:
                self.loop.run_until_complete(self._serve(ready))
            except Exception as exc:  # noqa: BLE001 - keep the video running if the port is taken
                errors.append(exc)
                ready.set()

        self._thread = threading.Thread(target=run, name="dashboard-feed", daemon=True)
        self._thread.start()
        ready.wait(timeout=3)
        if errors or not ready.is_set():
            self.loop = None
            reason = errors[0] if errors else "timed out"
            print(f"Dashboard feed not started ({reason}). The video will still run.")
            return False
        print(f"Dashboard feed  ws://{self.host}:{self.port}")
        self._start_video()
        return True

    def _start_video(self):
        handler = type("FrameHandler", (_FrameHandler,), {"feed": self})
        try:
            server = ThreadingHTTPServer((self.host, self.video_port), handler)
        except OSError as exc:
            print(f"Camera stream not started ({exc}). Gaze updates will still run.")
            return
        thread = threading.Thread(target=server.serve_forever, name="dashboard-video", daemon=True)
        thread.start()
        print(f"Camera stream   http://{self.host}:{self.video_port}/video")

    def frame(self, jpeg):
        with self._frame_cond:
            self._jpeg = jpeg
            self._frame_id += 1
            self._frame_cond.notify_all()

    async def _serve(self, ready):
        async with serve(self._handler, self.host, self.port):
            ready.set()
            await asyncio.Future()

    async def _handler(self, ws):
        self.clients.add(ws)
        if self._payload:
            await self._send(ws, self._payload)
        try:
            await ws.wait_closed()
        finally:
            self.clients.discard(ws)

    def gaze(self, name, dwell_ms=0, touch=False):
        if self.loop is None:
            return
        dwell = max(0, int(round(dwell_ms)))
        key = (name, dwell // 50, bool(touch))
        if key == self._last:
            return
        self._last = key
        self._payload = payload = json.dumps({
            "type": "gaze",
            "name": name,
            "dwellMs": dwell,
            "touch": bool(touch),
        })
        self.loop.call_soon_threadsafe(self._broadcast, payload)

    def suggestions(self, video, items):
        if self.loop is None:
            return
        payload = json.dumps({"type": "suggestions", "video": video, "items": items})
        self.loop.call_soon_threadsafe(self._broadcast, payload)

    def _broadcast(self, payload):
        for ws in list(self.clients):
            asyncio.create_task(self._send(ws, payload))

    async def _send(self, ws, payload):
        try:
            await ws.send(payload)
        except Exception:  # noqa: BLE001
            self.clients.discard(ws)


class _FrameHandler(BaseHTTPRequestHandler):
    feed = None

    def log_message(self, fmt, *args):
        return

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/health":
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok")
            return
        if path != "/video":
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Age", "0")
        self.send_header("Cache-Control", "no-cache, private")
        self.send_header("Pragma", "no-cache")
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.end_headers()
        last = -1
        try:
            while True:
                with self.feed._frame_cond:
                    if self.feed._frame_id == last:
                        self.feed._frame_cond.wait(timeout=1)
                    jpeg = self.feed._jpeg
                    last = self.feed._frame_id
                if not jpeg:
                    continue
                self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n")
                self.wfile.write(jpeg)
                self.wfile.write(b"\r\n")
                self.wfile.flush()
        except OSError:
            return
