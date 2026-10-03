"""Fuse body position + head direction into "who is looking at which product".

    fusion = AttentionFusion("zones.json")
    people = fusion.process(frame_bgr, timestamp_ms)
    # [{"person_id": 1, "product": "face_cream", "touch": False, "facing": -0.8, "source": "face+pose", ...}]

Two kinds of zones (see draw_zones.py):
  floor zone - where a shopper stands to look at the product (needs feet in view, fixed camera).
               Attended when the feet are inside it AND the head faces its shelf side.
  shelf zone - the product area on the shelf itself.
               Attended when the gaze direction (left/right + up/down) points at it,
               and flagged as a TOUCH when a wrist is inside it.
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
GAZE_CONE_DEG = 40      # a shelf zone must be within this angle of the gaze direction
TILT_GAIN = 1.5         # how strongly head tilt bends the gaze ray up/down
HOLD_REACH = 1.6        # hand within this many torso lengths of the nose = examining it
HOLD_ABOVE = 0.3        # a hand higher than this above the nose is reaching, not examining
HOLD_MEMORY_S = 1.0     # keep "holding" through brief wrist-detection dropouts


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
            mode = "looking"
            hand = self.examining_hand(body, facing, pid)
            if hand is not None:
                self.last_hold[pid] = (timestamp_ms / 1000, hand)
            elif pid in self.last_hold and timestamp_ms / 1000 - self.last_hold[pid][0] <= HOLD_MEMORY_S \
                    and not self.wrist_in_shelf(body):
                hand = self.last_hold[pid][1]  # wrist briefly lost, still examining
            if hand is not None:
                product, touch, target, mode = self.held[pid], False, hand, "holding"
                gaze = unit(np.array(hand, float) - np.array(body["nose"], float))
            else:
                product, touch, target = self.pick_product(body, facing, gaze)
                if touch:
                    self.held[pid], mode = product, "touch"
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
                "wrists": body["wrists"],
                "yaw": face["yaw"] if face else None,
            })
        return people

    def wrist_in_shelf(self, body):
        return any(polygon_distance(wr, z["shelf"]) >= 0 and wr[1] < body["nose"][1]
                   for wr in body["wrists"] for z in self.zones if "shelf" in z)

    def examining_hand(self, body, facing, pid):
        """Wrist position if the person is looking at a product they picked up, else None."""
        if pid not in self.held:
            return None
        nose = np.array(body["nose"], float)
        reach = HOLD_REACH * body["torso_h"]
        best = None
        for wr in body["wrists"]:
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

    def pick_product(self, body, facing, gaze):
        """Returns (product, touched, target_point)."""
        # 1. Touch: a wrist inside a shelf zone is the strongest signal
        for zone in self.zones:
            if "shelf" in zone:
                for wr in body["wrists"]:
                    if polygon_distance(wr, zone["shelf"]) >= 0:
                        return zone["product"], True, tuple(int(v) for v in polygon_center(zone["shelf"]))

        if abs(facing) < FACING_THRESHOLD:
            return None, False, None  # looking along the aisle, not at a shelf
        side = "right" if facing > 0 else "left"

        # 2. Floor zone: standing in front of it and facing its side
        for zone in self.zones:
            if "floor" in zone and zone.get("side") == side and polygon_distance(body["feet"], zone["floor"]) >= 0:
                return zone["product"], False, None

        # 3. Shelf zone: the product area best aligned with the gaze ray
        nose = np.array(body["nose"], float)
        best, best_angle, best_pt = None, GAZE_CONE_DEG, None
        for zone in self.zones:
            if "shelf" not in zone:
                continue
            if -polygon_distance(nose, zone["shelf"]) > SHELF_REACH * body["torso_h"]:
                continue
            center = polygon_center(zone["shelf"])
            to_zone = center - nose
            norm = np.linalg.norm(to_zone)
            if norm < 1:
                continue
            angle = math.degrees(math.acos(float(np.clip(np.dot(to_zone / norm, gaze), -1, 1))))
            if angle < best_angle:
                best, best_angle, best_pt = zone["product"], angle, tuple(int(v) for v in center)
        return best, False, best_pt

    def close(self):
        self.body.close()
        if self.face:
            self.face.close()


def unit(v):
    n = np.linalg.norm(v)
    return v / n if n > 1e-6 else np.array([0.0, 0.0])


def gaze_vector(facing, tilt):
    """Unit gaze direction in image coords (x right, y down)."""
    return unit(np.array([facing, -TILT_GAIN * tilt], float))


def match_face(body, faces):
    """Face whose nose is closest to the body's nose (within half a face width)."""
    best, best_d = None, None
    for f in faces:
        d = math.dist(f["nose"], body["nose"])
        if d <= max(f["bbox"][2], 20) * 0.5 and (best_d is None or d < best_d):
            best, best_d = f, d
    return best
