"""Draw product zones on a frame of the video.

Shelf zones (default; works with a moving camera / legs out of frame):
    python pipeline/draw_zones.py --source demo.mp4 --products tang,coffee,beans
  Click the corners of each product's area ON THE SHELF, press ENTER.

Floor zones (fixed camera, feet visible):
    python pipeline/draw_zones.py --source demo.mp4 --kind floor \
        --products left:face_cream,left:serum,right:perfume,right:body_lotion
  Click the floor area where a shopper stands to look at the product, press ENTER.
  The side (left/right shelf in the image) says which way they must face.
  Floor zones on opposite sides may overlap.
      ENTER  finish this zone       z  undo last point
      r      redo this zone         q  quit without saving
Saves zones.json.
"""
import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

COLORS = [(0, 200, 0), (255, 140, 0), (200, 0, 200), (0, 140, 255), (0, 220, 220), (255, 0, 0)]


def grab_frame(source, at_seconds):
    cap = cv2.VideoCapture(int(source) if source.isdigit() else source)
    if not source.isdigit():
        cap.set(cv2.CAP_PROP_POS_MSEC, at_seconds * 1000)
    else:
        for _ in range(15):  # let webcam exposure settle
            cap.read()
    ok, frame = cap.read()
    cap.release()
    if not ok:
        sys.exit(f"Could not read a frame from {source}")
    return frame


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True, help="video file or webcam index")
    ap.add_argument("--products", required=True, help="product,... (shelf) or side:product,... (floor)")
    ap.add_argument("--kind", choices=["shelf", "floor"], default="shelf")
    ap.add_argument("--at", type=float, default=0.0, help="timestamp (s) of the frame to draw on")
    ap.add_argument("--out", default="zones.json")
    ap.add_argument("--width", type=int, default=1280, help="resize frame to this width for drawing")
    args = ap.parse_args()

    products = []
    for item in args.products.split(","):
        item = item.strip()
        if args.kind == "shelf":
            products.append((None, item.split(":")[-1]))
            continue
        side, _, name = item.partition(":")
        if side not in ("left", "right") or not name:
            ap.error(f"bad product '{item}', expected left:name or right:name")
        products.append((side, name))

    frame = grab_frame(args.source, args.at)
    if frame.shape[1] > args.width:  # big videos (4K) don't fit on screen; zones get rescaled later
        frame = cv2.resize(frame, (args.width, int(frame.shape[0] * args.width / frame.shape[1])))
    h, w = frame.shape[:2]
    zones, points = [], []
    win = "draw floor zones"
    cv2.namedWindow(win)
    cv2.setMouseCallback(win, lambda e, x, y, *_: points.append((x, y)) if e == cv2.EVENT_LBUTTONDOWN else None)

    i = 0
    while i < len(products):
        side, name = products[i]
        view = frame.copy()
        for j, z in enumerate(zones):
            poly = np.array(z[args.kind], np.int32)
            cv2.polylines(view, [poly], True, COLORS[j % len(COLORS)], 2)
            cv2.putText(view, z["product"], tuple(poly[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLORS[j % len(COLORS)], 2)
        color = COLORS[i % len(COLORS)]
        for p in points:
            cv2.circle(view, p, 4, color, -1)
        if len(points) > 1:
            cv2.polylines(view, [np.array(points, np.int32)], False, color, 2)
        where = f"floor zone for {name} (shelf on {side.upper()})" if side else f"shelf area of {name}"
        cv2.putText(view, f"Click the {where}.  ENTER=done z=undo r=redo",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        cv2.imshow(win, view)

        key = cv2.waitKey(20) & 0xFF
        if key == ord("q"):
            sys.exit("Quit without saving.")
        elif key == ord("z") and points:
            points.pop()
        elif key == ord("r"):
            points.clear()
        elif key in (13, 10):
            if len(points) < 3:
                print("Need at least 3 points.")
                continue
            zone = {"product": name, args.kind: [list(p) for p in points]}
            if side:
                zone["side"] = side
            zones.append(zone)
            points.clear()
            i += 1

    cv2.destroyAllWindows()
    Path(args.out).write_text(json.dumps({"frame_size": [w, h], "zones": zones}, indent=2))
    preview = frame.copy()
    for j, z in enumerate(zones):
        poly = np.array(z[args.kind], np.int32)
        cv2.polylines(preview, [poly], True, COLORS[j % len(COLORS)], 2)
        cv2.putText(preview, z["product"], tuple(poly[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLORS[j % len(COLORS)], 2)
    cv2.imwrite(str(Path(args.out).with_suffix(".png")), preview)
    print(f"Saved {args.out} with {len(zones)} zones.")


if __name__ == "__main__":
    main()
