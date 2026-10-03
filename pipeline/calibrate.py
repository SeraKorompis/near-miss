"""Calibration: learn which head angles correspond to which product.

Interactive (webcam or video file):
    python pipeline/calibrate.py --source 0 --products chocolate,coffee,chips,juice
    python pipeline/calibrate.py --source demo.mp4 --products chocolate,coffee,chips,juice

    Look at a product, press its number key (1-9): records ~1.5 s of head angles.
    Do this for every product (repeat a key to add more samples).
      t      toggle test mode (shows which product you're looking at live)
      c      clear all samples
      s      save calibration.json
      space  pause/resume (video files)
      q      quit

From a pre-recorded clip with known segments (no key presses needed):
    python pipeline/calibrate.py --source demo.mp4 --segments segments.json
    segments.json: {"chocolate": [2.0, 4.0], "coffee": [5.0, 7.0], ...}   (seconds)
"""
import argparse
import json
import sys
import time
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent))
from head_pose import HeadPoseEstimator, draw_pose  # noqa: E402
from zones import ZoneClassifier  # noqa: E402

RECORD_SECONDS = 1.5


def open_source(source):
    cap = cv2.VideoCapture(int(source) if source.isdigit() else source)
    if not cap.isOpened():
        sys.exit(f"Could not open video source: {source}")
    is_file = not source.isdigit()
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    return cap, is_file, fps


def largest(poses):
    return max(poses, key=lambda p: p["bbox"][2] * p["bbox"][3]) if poses else None


def calibrate_from_segments(args):
    segments = json.loads(Path(args.segments).read_text())
    cap, _, fps = open_source(args.source)
    est = HeadPoseEstimator()
    samples = {p: [] for p in segments}
    frame_idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        t = frame_idx / fps
        frame_idx += 1
        active = [p for p, (start, end) in segments.items() if start <= t <= end]
        if not active:
            continue
        pose = largest(est.get_head_poses(frame, t * 1000))
        if pose:
            samples[active[0]].append((pose["yaw"], pose["pitch"]))
    est.close()
    return samples


def calibrate_interactive(args, products):
    cap, is_file, fps = open_source(args.source)
    est = HeadPoseEstimator()
    samples = {p: [] for p in products}
    recording, record_until = None, 0.0
    test_mode, paused, clf = False, False, None
    frame, frame_idx, start = None, 0, time.monotonic()

    while True:
        if not paused or frame is None:
            ok, frame = cap.read()
            if not ok:
                if is_file:  # loop the clip
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                break
            frame_idx += 1
        now = frame_idx / fps if is_file else time.monotonic() - start
        ts = now * 1000

        view = frame.copy()
        pose = largest(est.get_head_poses(frame, ts))

        label = None
        if pose:
            if recording and now <= record_until:
                samples[recording].append((pose["yaw"], pose["pitch"]))
            if test_mode and clf:
                label = clf.classify(pose["yaw"], pose["pitch"]) or "nothing"
            draw_pose(view, pose, label)

        if recording and now > record_until:
            print(f"  recorded {recording}: {len(samples[recording])} samples total")
            recording = None

        # HUD
        y = 25
        for i, p in enumerate(products):
            n = len(samples[p])
            color = (0, 200, 0) if n >= 15 else (0, 165, 255) if n else (180, 180, 180)
            if p == recording:
                color = (0, 0, 255)
            cv2.putText(view, f"[{i + 1}] {p}: {n}", (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            y += 24
        status = "RECORDING " + recording if recording else ("TEST MODE" if test_mode else "")
        if not pose:
            status = "NO FACE DETECTED"
        cv2.putText(view, status, (10, view.shape[0] - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        cv2.imshow("calibration (q to quit)", view)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        if ord("1") <= key <= ord("9") and key - ord("1") < len(products):
            recording = products[key - ord("1")]
            record_until = now + RECORD_SECONDS
            if is_file and paused:
                paused = False
        elif key == ord("t"):
            clf = ZoneClassifier.from_samples(samples, args.max_distance)
            test_mode = not test_mode and bool(clf.centroids)
        elif key == ord("c"):
            samples = {p: [] for p in products}
            test_mode = False
        elif key == ord(" ") and is_file:
            paused = not paused
        elif key == ord("s"):
            save(samples, args)

    cap.release()
    cv2.destroyAllWindows()
    est.close()
    return samples


def save(samples, args):
    clf = ZoneClassifier.from_samples(samples, args.max_distance)
    if not clf.centroids:
        print("Nothing to save yet.")
        return
    clf.save(args.out, source=args.source)
    print(f"\nSaved {args.out}  (max_distance = {clf.max_distance} deg)")
    for p, c in clf.centroids.items():
        print(f"  {p:<15} yaw {c['yaw']:+6.1f}  pitch {c['pitch']:+6.1f}  "
              f"(std {c['yaw_std']:.1f}/{c['pitch_std']:.1f}, n={c['n_samples']})")
    for w in clf.warnings():
        print("  WARNING:", w)
    missing = [p for p, s in samples.items() if not s]
    if missing:
        print("  Not calibrated:", ", ".join(missing))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", default="0", help="webcam index (0) or path to a video file")
    ap.add_argument("--products", help="comma-separated product ids, in key order 1-9")
    ap.add_argument("--segments", help="JSON of {product: [start_s, end_s]} for non-interactive mode")
    ap.add_argument("--out", default="calibration.json")
    ap.add_argument("--max-distance", type=float, default=None,
                    help="max degrees from a product centroid (default: auto from product spacing)")
    args = ap.parse_args()

    if args.segments:
        samples = calibrate_from_segments(args)
    else:
        if not args.products:
            ap.error("--products is required in interactive mode")
        products = [p.strip() for p in args.products.split(",") if p.strip()][:9]
        samples = calibrate_interactive(args, products)
    save(samples, args)


if __name__ == "__main__":
    main()
