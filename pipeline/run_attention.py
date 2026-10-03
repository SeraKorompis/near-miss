"""Run body+head fusion on a video -> attention_events.csv + annotated video.

    python pipeline/run_attention.py --source demo.mp4 --zones zones.json
    python pipeline/run_attention.py --source 0 --zones zones.json          # live webcam

Opens a live window (real-time speed) with gaze cones and an attention panel.
Keys: q quit, space pause. Use --no-show to just write the outputs.

Outputs (in --out-dir, default output/):
    attention_frames.csv   one row per person per frame
    attention_events.csv   person_id, product_id, start_s, end_s, dwell_s, touched
    annotated.mp4          the same video as the live window
"""
import argparse
import csv
import sys
import time
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dashboard_feed import DashboardFeed  # noqa: E402
from fusion import AttentionFusion  # noqa: E402
from viz import LiveStats, color_for, draw_panel, draw_person, draw_zones  # noqa: E402

GAP_TOLERANCE_S = 0.5  # merge looks at the same product interrupted by short gaps
MIN_EVENT_S = 0.5      # drop flickers shorter than this


def frames_to_events(rows):
    """rows: (t, person_id, product, touch) -> list of events."""
    events, open_ = [], {}  # (pid, product) -> [start, last, touched]
    for t, pid, product, touch in sorted(rows, key=lambda r: r[0]):
        key = (pid, product)
        if product is None:
            continue
        if key in open_ and t - open_[key][1] <= GAP_TOLERANCE_S:
            open_[key][1] = t
            open_[key][2] |= touch
        else:
            if key in open_:
                events.append((pid, product, *open_[key]))
            open_[key] = [t, t, touch]
    events += [(pid, product, *v) for (pid, product), v in open_.items()]
    return sorted(
        [(pid, prod, round(s, 2), round(e, 2), round(e - s, 2), int(tc))
         for pid, prod, s, e, tc in events if e - s >= MIN_EVENT_S],
        key=lambda ev: (ev[2], ev[0]),
    )


def clip_suggestions(events, args):
    """Ask analysis/recommend.py for a suggestion per product in this clip."""
    analysis = Path(__file__).resolve().parent.parent / "analysis"
    sys.path.insert(0, str(analysis))
    from recommend import suggest_clip

    video = Path(args.out_dir).name
    if video in ("output", ".", ""):
        video = Path(args.source).stem
    return suggest_clip(events, video)


def publish_frame(feed, frame):
    if feed is None:
        return
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 72])
    if ok:
        feed.frame(buf.tobytes())


def publish_gaze(feed, stats, people, t):
    """Send the longest current look. An empty frame clears the dashboard timer."""
    if feed is None:
        return
    looking = [p for p in people if p.get("product")]
    if not looking:
        feed.gaze(None, 0, False)
        return

    def dwell(person):
        st = stats.people.get(person["person_id"])
        if not st or st["current"] != person["product"]:
            return 0
        return max(0.0, t - st["since"])

    person = max(looking, key=dwell)
    feed.gaze(person["product"], dwell(person) * 1000, person.get("touch"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True)
    ap.add_argument("--zones", default="zones.json")
    ap.add_argument("--out-dir", default="output")
    ap.add_argument("--no-face", action="store_true", help="pose only (faster)")
    ap.add_argument("--no-show", action="store_true", help="don't open the live window")
    ap.add_argument("--fast", action="store_true", help="don't slow the live window down to real time")
    ap.add_argument("--width", type=int, default=1280, help="process at this width (4K is slow)")
    ap.add_argument("--every", type=int, default=0, help="process every Nth frame (default: ~15 fps)")
    ap.add_argument("--no-dashboard", action="store_true", help="don't broadcast looks to the live dashboard")
    ap.add_argument("--dashboard-port", type=int, default=8765)
    args = ap.parse_args()

    is_cam = args.source.isdigit()
    cap = cv2.VideoCapture(int(args.source) if is_cam else args.source)
    if not cap.isOpened():
        sys.exit(f"Could not open {args.source}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if w > args.width:
        w, h = args.width, int(h * args.width / w)
    every = args.every or max(1, round(fps / 15))

    out_dir = Path(args.out_dir)
    out_dir.mkdir(exist_ok=True)
    # H.264 plays smoothly in QuickTime/browsers (mp4v glitches). Write to a temp file
    # and rename at the end so a player never opens a half-written video.
    video_tmp = out_dir / "annotated.partial.mp4"
    writer = cv2.VideoWriter(str(video_tmp), cv2.VideoWriter_fourcc(*"avc1"), fps / every, (w, h))
    if not writer.isOpened():
        writer = cv2.VideoWriter(str(video_tmp), cv2.VideoWriter_fourcc(*"mp4v"), fps / every, (w, h))
    fusion = AttentionFusion(args.zones, use_face=not args.no_face)
    feed = None if args.no_dashboard else DashboardFeed(port=args.dashboard_port)
    if feed:
        feed.start()

    stats = LiveStats()
    rows, frame_idx, start = [], 0, time.monotonic()
    frame_interval = every / fps
    win = "Near-Miss attention  (q quit, space pause)"
    with open(out_dir / "attention_frames.csv", "w", newline="") as f:
        fw = csv.writer(f)
        fw.writerow(["t", "person_id", "product_id", "touch", "facing", "source", "feet_x", "feet_y", "yaw"])
        while True:
            if not is_cam and frame_idx % every:
                frame_idx += 1
                if not cap.grab():  # skip without decoding
                    break
                continue
            ok, frame = cap.read()
            if not ok:
                break
            tick = time.monotonic()
            t = tick - start if is_cam else frame_idx / fps
            frame_idx += 1
            if frame.shape[1] != w:
                frame = cv2.resize(frame, (w, h))

            people = fusion.process(frame, t * 1000)
            for p in people:
                rows.append((t, p["person_id"], p["product"], p["touch"]))
                fw.writerow([round(t, 3), p["person_id"], p["product"] or "", int(p["touch"]), p["facing"], p["source"],
                             *p["feet"], p["yaw"] if p["yaw"] is not None else ""])

            stats.update(t, people)
            publish_gaze(feed, stats, people, t)
            draw_zones(frame, fusion.zones, {p["product"]: color_for(p["person_id"]) for p in people if p["product"]})
            for p in people:
                if stats.people[p["person_id"]]["frames"] >= 3:  # hide 1-2 frame tracker blips
                    draw_person(frame, p)
            draw_panel(frame, stats, t)
            publish_frame(feed, frame)
            writer.write(frame)
            if not args.no_show:
                cv2.imshow(win, frame)
                wait = 1 if (args.fast or is_cam) else max(1, int((frame_interval - (time.monotonic() - tick)) * 1000))
                key = cv2.waitKey(wait) & 0xFF
                if key == ord(" "):
                    key = cv2.waitKey(0) & 0xFF
                if key == ord("q"):
                    break
            if frame_idx % 100 == 0:
                print(f"  {frame_idx} frames, t={t:.1f}s")

    cap.release()
    writer.release()
    if feed:
        feed.gaze(None, 0, False)
    video_tmp.replace(out_dir / "annotated.mp4")
    cv2.destroyAllWindows()
    fusion.close()

    events = frames_to_events(rows)
    with open(out_dir / "attention_events.csv", "w", newline="") as f:
        ew = csv.writer(f)
        ew.writerow(["person_id", "product_id", "start_s", "end_s", "dwell_s", "touched"])
        ew.writerows(events)
    print(f"\n{len(events)} attention events -> {out_dir / 'attention_events.csv'}")
    for ev in events:
        print(f"  ID {ev[0]:02d}  {ev[1]:<15} {ev[2]:6.1f}s - {ev[3]:6.1f}s  ({ev[4]:.1f}s){'  touched' if ev[5] else ''}")

    suggestions = clip_suggestions(events, args)
    print(f"\n{len(suggestions)} suggestions")
    for item in suggestions:
        print(f"  [{item['priority']:>6}] {item['product']:<22} {item['action']}")
    if feed:
        video = Path(args.out_dir).name
        if video in ("output", ".", ""):
            video = Path(args.source).stem
        feed.suggestions(video, suggestions)
        time.sleep(0.5)


if __name__ == "__main__":
    main()
