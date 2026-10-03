"""Broadcast the current look to the dashboard.

The live floor connects to ws://127.0.0.1:8765 and expects:

    {"type": "gaze", "name": "crisps_packs", "dwellMs": 1400, "touch": false}
    {"type": "gaze", "name": null}

`name` is the zone id from the vision pipeline. The dashboard times nothing
itself when dwellMs is present: the number is the dwell the camera measured.
"""
import asyncio
import json
import threading

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
        return True

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

    def _broadcast(self, payload):
        for ws in list(self.clients):
            asyncio.create_task(self._send(ws, payload))

    async def _send(self, ws, payload):
        try:
            await ws.send(payload)
        except Exception:  # noqa: BLE001
            self.clients.discard(ws)
