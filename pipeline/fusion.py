"""Fuse body position + head direction into "who is looking at which product".

    fusion = AttentionFusion("zones.json")
    people = fusion.process(frame_bgr, timestamp_ms)
    # [{"person_id": 1, "product": "face_cream", "touch": False, "facing": -0.8, "source": "face+pose", ...}]

Two kinds of zones (see draw_zones.py):
  floor zone - where a shopper stands to look at the product (needs feet in view, fixed camera).
               Attended when the feet are inside it AND the head faces its shelf side.
  shelf zone - the product area on the shelf itself.
               Attended when the gaze direction (left/right + up/down) points at it,
               and flagged as a TOUCH when a hand reaches into it.
  holding    - after touching a product, a hand close to the face on the side
               the person faces means they are examining that product in hand.
Head direction = Face Landmarker yaw when the face is visible (precise),
otherwise YOLO pose nose-vs-ears (works in profile and from behind).
"""
import json
import math
from pathlib import Path

import cv2
import numpy as np

from body_pose import BodyPoseEstimator
from head_pose import HeadPoseEstimator

FACING_THRESHOLD = 0.3  # |facing| needed to count as looking at a side shelf
FACE_WEIGHT = 0.7       # how much to trust face yaw over pose when both exist
SMOOTHING = 0.3         # EMA factor for facing (lower = smoother)
SHELF_REACH = 3.0       # max head-to-shelf-zone distance, in torso lengths
GAZE_CONE_DEG = 12      # a shelf zone must be hit by a cone this wide (half-angle) around the gaze
TILT_GAIN = 1.5         # how strongly head tilt bends the gaze ray up/down
TILT_OFFSET = 0.15      # in profile the nose sits a bit below the ear even when the head is level
HOLD_REACH = 1.6        # hand within this many torso lengths of the nose = examining it
HOLD_ABOVE = 0.3        # a hand higher than this above the nose is reaching, not examining
HOLD_MEMORY_S = 1.0     # keep "holding" through brief wrist-detection dropouts
REACH_EXTEND = 0.8      # ...or the arm stretched this far sideways (torso lengths)
HIP_MARGIN = 0.1        # a touch needs the hand above hip level (minus this margin)...
BODY_CLEARANCE = 0.35   # ...and this far (torso lengths) sideways from the body's centre line
TOUCH_FRAMES = 2        # consecutive frames a hand must stay in a zone (ignores hands passing through)


def load_zones(path):
    data = json.loads(Path(path).read_text())
    return data.get("frame_size"), data["zones"]


def scale_zones(zones, src_size, dst_size):
    if not src_size or tuple(src_size) == tuple(dst_size):
        return zones
    sx, sy = dst_size[0] / src_size[0], dst_size[1] / src_size[1]
    out = []
    for z in zones:
        z = dict(z)
        for key in ("floor", "shelf"):
            if key in z:
                z[key] = [[x * sx, y * sy] for x, y in z[key]]
        out.append(z)
    return out


def polygon_distance(pt, polygon):
    """Signed distance: positive inside, negative outside (pixels)."""
    return cv2.pointPolygonTest(np.array(polygon, np.float32), (float(pt[0]), float(pt[1])), True)


def polygon_center(polygon):
    return np.array(polygon, float).mean(axis=0)


class AttentionFusion:
    def __init__(self, zones_path="zones.json", use_face=True):
        self.zones_size, self.raw_zones = load_zones(zones_path)
        self.zones = None  # scaled on the first frame
        self.body = BodyPoseEstimator()
        self.face = HeadPoseEstimator() if use_face else None
        self.facing_state = {}  # person_id -> smoothed (facing, tilt)
        self.held = {}          # person_id -> last product touched (assumed in hand)
        self.last_hold = {}     # person_id -> (t, hand position) of the last "holding" frame
        self.touch_streak = {}  # person_id -> (product, consecutive frames)
        self._fallback_id = 1000

    def process(self, frame_bgr, timestamp_ms):
        h, w = frame_bgr.shape[:2]
        if self.zones is None:
            self.zones = scale_zones(self.raw_zones, self.zones_size, (w, h))
        bodies = self.body.get_body_poses(frame_bgr, timestamp_ms)
        faces = self.face.get_head_poses(frame_bgr, timestamp_ms) if self.face else []

        people = []
        for body in bodies:
            pid = body["track_id"]
            if pid is None:  # tracker not confirmed yet
                self._fallback_id += 1
                pid = self._fallback_id
            face = match_face(body, faces)
            if face:
                # Positive yaw = facing image-right (same convention as pose facing)
                face_facing = math.sin(math.radians(face["yaw"])) * 2.0
                raw = FACE_WEIGHT * face_facing + (1 - FACE_WEIGHT) * body["facing"]
                source = "face+pose"
            else:
                raw = body["facing"]
                source = "pose"
            raw = float(np.clip(raw, -1, 1))

            prev = self.facing_state.get(pid)
            if prev is None:
                facing, tilt = raw, body["tilt"]
            else:
                facing = prev[0] + SMOOTHING * (raw - prev[0])
                tilt = prev[1] + SMOOTHING * (body["tilt"] - prev[1])
            self.facing_state[pid] = (facing, tilt)

            gaze = gaze_vector(facing, tilt)
            t = timestamp_ms / 1000

            # 1. Touch (hand reaching into a shelf zone for a few frames) wins and
            #    becomes the product they are holding.
            # While examining a held product, only a clearly stretched arm is a new touch
            examining = self.examining_hand(body, facing, pid) is not None
            touched = self.touching(body, stretched_only=examining)
            name = touched[0] if touched else None
            prev_name, count = self.touch_streak.get(pid, (None, 0))
            count = count + 1 if name and name == prev_name else (1 if name else 0)
            self.touch_streak[pid] = (name, count)

            hand = None
            if touched and count >= TOUCH_FRAMES:
                product, touch, target, mode = touched[0], True, touched[1], "touch"
                self.held[pid] = product
                self.last_hold.pop(pid, None)
            else:
                # 2. Holding: examining a picked-up product in hand
                hand = self.examining_hand(body, facing, pid)
                if hand is not None:
                    self.last_hold[pid] = (t, hand)
                elif pid in self.last_hold and t - self.last_hold[pid][0] <= HOLD_MEMORY_S and not touched:
                    hand = self.last_hold[pid][1]  # hand briefly lost, still examining
                if hand is not None:
                    product, touch, target, mode = self.held[pid], False, hand, "holding"
                    gaze = unit(np.array(hand, float) - np.array(body["nose"], float))
                else:
                    # 3. Looking at a shelf zone
                    product, target = self.looking_at(body, facing, gaze)
                    touch, mode = False, "looking"
            people.append({
                "person_id": pid,
                "product": product,
                "touch": touch,
                "mode": mode if product else None,
                "target": target,
                "gaze": gaze,
                "torso_h": body["torso_h"],
                "facing": round(facing, 3),
                "tilt": round(tilt, 3),
                "source": source,
                "feet": body["feet"],
                "feet_estimated": body["feet_estimated"],
                "bbox": body["bbox"],
                "nose": body["nose"],
                "hands": body["hands"],
                "yaw": face["yaw"] if face else None,
            })
        return people

    def examining_hand(self, body, facing, pid):
        """Wrist position if the person is looking at a product they picked up, else None."""
        if pid not in self.held:
            return None
        nose = np.array(body["nose"], float)
        reach = HOLD_REACH * body["torso_h"]
        best = None
        for wr in body["hands"]:
            d = np.array(wr, float) - nose
            if np.linalg.norm(d) > reach or d[1] < -HOLD_ABOVE * body["torso_h"]:
                continue  # too far away, or raised up to the shelf
            if wr[1] > body["hip_mid"][1] - 0.25 * body["torso_h"]:
                continue  # relaxed hand hanging at the hip, not held up to look at
            if any(polygon_distance(wr, z["shelf"]) >= 0 for z in self.zones if "shelf" in z) and d[1] < 0:
                continue  # hand up inside a shelf zone = touching the shelf, not examining
            if abs(facing) >= FACING_THRESHOLD and d[0] * facing < -0.2 * body["torso_h"]:
                continue  # hand is behind the direction they face
            if best is None or np.linalg.norm(d) < np.linalg.norm(np.array(best) - nose):
                best = wr
        return best

    def touching(self, body, stretched_only=False):
        """(product, target) for a hand reaching into a shelf zone, else None.
        Deepest zone wins when zones overlap."""
        best, best_depth = None, -1.0
        for hand in body["hands"]:
            if not is_reaching(body, hand, stretched_only):
                continue
            for zone in self.zones:
                if "shelf" in zone:
                    depth = polygon_distance(hand, zone["shelf"])
                    if depth >= 0 and depth > best_depth:
                        best, best_depth = zone, depth
        if not best:
            return None
        return best["product"], tuple(int(v) for v in polygon_center(best["shelf"]))

    def looking_at(self, body, facing, gaze):
        """(product, target_point) the head is turned toward, or (None, None)."""
        if abs(facing) < FACING_THRESHOLD:
            return None, None  # looking along the aisle, not at a shelf
        side = "right" if facing > 0 else "left"

        # 2. Floor zone: standing in front of it and facing its side
        for zone in self.zones:
            if "floor" in zone and zone.get("side") == side and polygon_distance(body["feet"], zone["floor"]) >= 0:
                return zone["product"], None

        # 3. Shelf zone: the product area best aligned with the gaze ray
        nose = np.array(body["nose"], float)
        best, best_score, best_pt = None, (GAZE_CONE_DEG, 0.0), None
        for zone in self.zones:
            if "shelf" not in zone:
                continue
            if -polygon_distance(nose, zone["shelf"]) > SHELF_REACH * body["torso_h"]:
                continue
            angle, dist, pt = angle_to_zone(nose, gaze, zone["shelf"])
            # Zones the ray passes through (angle 0) beat near-misses; among those, the first one hit wins
            if (angle, dist) < best_score:
                best, best_score, best_pt = zone["product"], (angle, dist), pt
        return best, best_pt

    def close(self):
        self.body.close()
        if self.face:
            self.face.close()


def angle_to_zone(origin, direction, polygon):
    """(angle, distance, point): smallest angle (deg) between the gaze ray and the zone.
    Angle is 0 when the ray passes through the zone; distance is then how far along
    the ray it enters (so the first zone hit can win)."""
    poly = np.array(polygon, float)
    pts = [poly.mean(axis=0)]
    for a, b in zip(poly, np.roll(poly, -1, axis=0)):  # sample along the edges
        pts += [a + (b - a) * k / 8 for k in range(8)]
    best, best_pt = 180.0, None
    for q in pts:
        v = q - origin
        n = np.linalg.norm(v)
        if n < 1:
            continue
        ang = math.degrees(math.acos(float(np.clip(np.dot(v / n, direction), -1, 1))))
        if ang < best:
            best, best_pt = ang, q
    # Ray passing through the zone: aim the target at the zone centre
    for d in np.linspace(0, 3000, 300):
        q = origin + direction * d
        if polygon_distance(q, polygon) >= 0:
            return 0.0, float(d), tuple(int(v) for v in poly.mean(axis=0))
    return best, 0.0, tuple(int(v) for v in best_pt) if best_pt is not None else None


def is_reaching(body, hand, stretched_only=False):
    """Arm reaching out to the shelf: hand above hip level and away from the body,
    or stretched far sideways. Rules out hands swinging by the hips while walking,
    and hands held in front of the body that merely overlap a zone in the image."""
    t = body["torso_h"]
    above_hip = hand[1] < body["hip_mid"][1] - HIP_MARGIN * t
    away = abs(hand[0] - (body["shoulder_mid"][0] + body["hip_mid"][0]) / 2)
    if stretched_only:
        return away > REACH_EXTEND * t
    return (above_hip and away > BODY_CLEARANCE * t) or away > REACH_EXTEND * t


def unit(v):
    n = np.linalg.norm(v)
    return v / n if n > 1e-6 else np.array([0.0, 0.0])


def gaze_vector(facing, tilt):
    """Unit gaze direction in image coords (x right, y down)."""
    return unit(np.array([facing, -TILT_GAIN * (tilt + TILT_OFFSET)], float))


def match_face(body, faces):
    """Face whose nose is closest to the body's nose (within half a face width)."""
    best, best_d = None, None
    for f in faces:
        d = math.dist(f["nose"], body["nose"])
        if d <= max(f["bbox"][2], 20) * 0.5 and (best_d is None or d < best_d):
            best, best_d = f, d
    return best
