"""Drawing for the live / annotated video: zones, gaze cones, HUD panel."""
import math

import cv2
import numpy as np

ID_COLORS = [(80, 200, 80), (255, 150, 40), (220, 80, 220), (40, 160, 255), (40, 220, 220)]
CONE_HALF_ANGLE = 12  # degrees; same as GAZE_CONE_DEG in fusion.py
FONT = cv2.FONT_HERSHEY_SIMPLEX


def color_for(pid):
    return ID_COLORS[(pid - 1) % len(ID_COLORS)]


class LiveStats:
    """Per-person running dwell times, for the HUD."""

    def __init__(self):
        self.people = {}  # pid -> {"current", "since", "last_t", "totals": {}, "touched": set()}

    def update(self, t, people):
        for p in people:
            st = self.people.setdefault(p["person_id"], {"current": None, "since": t, "last_t": t,
                                                         "totals": {}, "touched": set(), "frames": 0})
            st["frames"] += 1
            dt = t - st["last_t"]
            if st["current"] and dt < 1.0:
                st["totals"][st["current"]] = st["totals"].get(st["current"], 0.0) + dt
            if p["product"] != st["current"]:
                st["current"], st["since"] = p["product"], t
            st["mode"] = p.get("mode")
            if p["touch"] and p["product"]:
                st["touched"].add(p["product"])
            st["last_t"] = t
        active = {p["person_id"] for p in people}
        for pid, st in self.people.items():
            if pid not in active and t - st["last_t"] > 1.0:
                st["current"] = None


def overlay(frame, draw_fn, alpha):
    layer = frame.copy()
    draw_fn(layer)
    cv2.addWeighted(layer, alpha, frame, 1 - alpha, 0, frame)


def draw_zones(frame, zones, active):
    """active: {product: color}"""
    def fill(layer):
        for z in zones:
            if z["product"] in active:
                cv2.fillPoly(layer, [np.array(z.get("shelf") or z["floor"], np.int32)], active[z["product"]])
    overlay(frame, fill, 0.30)
    for z in zones:
        poly = np.array(z.get("shelf") or z["floor"], np.int32)
        on = z["product"] in active
        color = active.get(z["product"], (200, 200, 200))
        cv2.polylines(frame, [poly], True, color, 3 if on else 1, cv2.LINE_AA)
        label_box(frame, z["product"], tuple(poly[poly[:, 1].argmin()]), color if on else (90, 90, 90))


def draw_person(frame, p):
    color = color_for(p["person_id"])
    x, y, w, h = p["bbox"]
    cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2, cv2.LINE_AA)
    label_box(frame, f"ID {p['person_id']:02d}", (x, y), color)

    nose = np.array(p["nose"], float)
    gaze = np.array(p["gaze"], float)
    if np.linalg.norm(gaze) > 0 and (abs(p["facing"]) >= 0.15 or p.get("mode") == "holding"):
        length = min(1.4 * p["torso_h"], 0.3 * frame.shape[1])
        if p.get("mode") == "holding" and p.get("target"):
            length = max(40.0, float(np.linalg.norm(np.array(p["target"]) - nose)) * 1.15)
        base = math.atan2(gaze[1], gaze[0])
        pts = [nose]
        for a in np.linspace(-CONE_HALF_ANGLE, CONE_HALF_ANGLE, 9):
            r = base + math.radians(a)
            pts.append(nose + length * np.array([math.cos(r), math.sin(r)]))
        cone = np.array(pts, np.int32)
        cone_color = (0, 230, 255) if p["product"] else (0, 0, 255)
        overlay(frame, lambda layer: cv2.fillPoly(layer, [cone], cone_color), 0.35)
        cv2.polylines(frame, [cone], True, cone_color, 1, cv2.LINE_AA)
        tip = tuple((nose + length * gaze).astype(int))
        cv2.arrowedLine(frame, tuple(nose.astype(int)), tip, (0, 0, 255), 3, cv2.LINE_AA, tipLength=0.08)

    if p.get("target"):
        dashed_line(frame, tuple(nose.astype(int)), p["target"], color)
        cv2.circle(frame, p["target"], 8, color, -1, cv2.LINE_AA)
        if p.get("mode") == "holding":
            label_box(frame, f"holding {p['product']}", (p["target"][0] - 60, p["target"][1] + 40), color)

    for wr in p["hands"]:
        cv2.circle(frame, wr, 9 if p["touch"] else 6, (0, 255, 255) if p["touch"] else color, -1, cv2.LINE_AA)
    cv2.circle(frame, tuple(nose.astype(int)), 5, (0, 0, 255), -1, cv2.LINE_AA)


def draw_panel(frame, stats, t):
    """Dark panel top-right listing each person's attention, like the pitch mock-up."""
    h, w = frame.shape[:2]
    # Only people seen recently and for more than a few frames (hides tracker blips)
    # Only people seen recently, for more than a few frames, who looked at something
    rows = sorted((pid, st) for pid, st in stats.people.items()
                  if st["frames"] >= 3 and t - st["last_t"] < 1.5 and (st["current"] or st["totals"]))
    pw = 470
    ph = 50 + 92 * max(1, len(rows))
    x0, y0 = w - pw - 15, 15
    overlay(frame, lambda layer: cv2.rectangle(layer, (x0, y0), (x0 + pw, y0 + ph), (30, 25, 20), -1), 0.85)
    cv2.putText(frame, "Attention Tracking", (x0 + 15, y0 + 32), FONT, 0.75, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(frame, f"{t:5.1f}s", (x0 + pw - 85, y0 + 32), FONT, 0.6, (180, 180, 180), 1, cv2.LINE_AA)
    y = y0 + 60
    for pid, st in rows:
        color = color_for(pid)
        cv2.rectangle(frame, (x0 + 15, y), (x0 + 75, y + 26), color, -1)
        cv2.putText(frame, f"ID {pid:02d}", (x0 + 20, y + 19), FONT, 0.55, (255, 255, 255), 2, cv2.LINE_AA)
        if st["current"]:
            now = t - st["since"]
            verb = {"holding": "Holding", "touch": "Touching"}.get(st.get("mode"), "Looking at")
            text = f"{verb} {st['current']}"
            cv2.putText(frame, text, (x0 + 90, y + 19), FONT, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(frame, f"{now:4.1f}s", (x0 + pw - 70, y + 19), FONT, 0.6, (0, 230, 255), 2, cv2.LINE_AA)
        else:
            cv2.putText(frame, "Not looking at a product", (x0 + 90, y + 19), FONT, 0.55, (170, 170, 170), 1,
                        cv2.LINE_AA)
        totals = sorted(st["totals"].items(), key=lambda kv: -kv[1])[:2]
        line = "  ".join(f"{k} {v:.1f}s{' (touched)' if k in st['touched'] else ''}" for k, v in totals)
        cv2.putText(frame, line or "-", (x0 + 90, y + 48), FONT, 0.45, (200, 200, 200), 1, cv2.LINE_AA)
        y += 92


def label_box(frame, text, org, color):
    (tw, th), _ = cv2.getTextSize(text, FONT, 0.55, 2)
    x, y = int(org[0]), max(th + 8, int(org[1]))
    cv2.rectangle(frame, (x, y - th - 8), (x + tw + 10, y), color, -1)
    cv2.putText(frame, text, (x + 5, y - 5), FONT, 0.55, (255, 255, 255), 2, cv2.LINE_AA)


def dashed_line(frame, p0, p1, color, dash=12):
    p0, p1 = np.array(p0, float), np.array(p1, float)
    n = max(1, int(np.linalg.norm(p1 - p0) / dash))
    for i in range(0, n, 2):
        a = p0 + (p1 - p0) * i / n
        b = p0 + (p1 - p0) * min(i + 1, n) / n
        cv2.line(frame, tuple(a.astype(int)), tuple(b.astype(int)), color, 2, cv2.LINE_AA)
