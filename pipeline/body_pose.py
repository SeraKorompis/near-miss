"""Body pose + person tracking with YOLOv8-pose (ultralytics) and ByteTrack.

Works from the side and from behind, and when legs are cut off, where
MediaPipe's pose model (which needs to find the face first) fails.

    est = BodyPoseEstimator()
    bodies = est.get_body_poses(frame_bgr)
    # [{"track_id": 1, "bbox": (x,y,w,h), "nose": (x,y), "facing": -0.7,
    #   "hands": [(x,y), ...], "feet": (x,y), ...}, ...]

facing: horizontal head direction in IMAGE terms, -1 = facing image-left,
+1 = facing image-right, ~0 = looking along the aisle (toward/away from camera).
tilt:   +1 = looking up, -1 = looking down (from nose height vs ears).
"""
from pathlib import Path

import numpy as np
from ultralytics import YOLO

MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "yolov8n-pose.pt"

# COCO keypoint indices
NOSE, L_EYE, R_EYE, L_EAR, R_EAR = 0, 1, 2, 3, 4
L_SHOULDER, R_SHOULDER, L_ELBOW, R_ELBOW, L_WRIST, R_WRIST = 5, 6, 7, 8, 9, 10
L_HIP, R_HIP, L_ANKLE, R_ANKLE = 11, 12, 15, 16
VISIBLE = 0.4
HAND_EXTEND = 0.35  # hand centre is ~1/3 of a forearm beyond the wrist


class BodyPoseEstimator:
    def __init__(self, model_path=MODEL_PATH, min_confidence=0.3, imgsz=640):
        # Downloads yolov8n-pose.pt automatically if missing
        self.model = YOLO(str(model_path) if Path(model_path).exists() else "yolov8n-pose.pt")
        self.conf = min_confidence
        self.imgsz = imgsz

    def get_body_poses(self, frame_bgr, timestamp_ms=None):
        r = self.model.track(frame_bgr, persist=True, tracker="bytetrack.yaml", conf=self.conf,
                             imgsz=self.imgsz, classes=[0], verbose=False)[0]
        if r.keypoints is None or r.boxes is None or len(r.boxes) == 0:
            return []
        kps = r.keypoints.xy.cpu().numpy()
        confs = r.keypoints.conf.cpu().numpy() if r.keypoints.conf is not None else np.ones(kps.shape[:2])
        boxes = r.boxes.xyxy.cpu().numpy()
        ids = r.boxes.id.int().cpu().tolist() if r.boxes.id is not None else [None] * len(boxes)

        bodies = []
        for i, (pts, vis, box, tid) in enumerate(zip(kps, confs, boxes, ids)):
            if is_nested(i, boxes) or head_inside_bigger(i, pts, boxes):
                continue  # e.g. an arm + held product detected as a second "person"
            body = summarize(pts, vis, box)
            if body:
                body["track_id"] = tid
                bodies.append(body)
        return bodies

    def close(self):
        pass


def is_nested(i, boxes, max_inside=0.4):
    """True if box i lies mostly inside a bigger box."""
    x0, y0, x1, y1 = boxes[i]
    area = max((x1 - x0) * (y1 - y0), 1.0)
    for j, (a0, b0, a1, b1) in enumerate(boxes):
        if j == i or (a1 - a0) * (b1 - b0) <= area:
            continue
        iw = max(0.0, min(x1, a1) - max(x0, a0))
        ih = max(0.0, min(y1, b1) - max(y0, b0))
        if iw * ih / area > max_inside:
            return True
    return False


def head_inside_bigger(i, nose_pts, boxes):
    """True if this detection's nose lies inside a bigger person's box (partial duplicate)."""
    nx, ny = nose_pts[NOSE]
    x0, y0, x1, y1 = boxes[i]
    area = (x1 - x0) * (y1 - y0)
    for j, (a0, b0, a1, b1) in enumerate(boxes):
        if j != i and (a1 - a0) * (b1 - b0) > area and a0 <= nx <= a1 and b0 <= ny <= b1:
            return True
    return False


def summarize(pts, vis, box):
    """Turn 17 keypoints into the few numbers we need."""
    x0, y0, x1, y1 = box
    if vis[[L_SHOULDER, R_SHOULDER]].max() < VISIBLE or vis[NOSE] < 0.2:
        return None
    shoulders = [i for i in (L_SHOULDER, R_SHOULDER) if vis[i] >= VISIBLE]
    shoulder_mid = pts[shoulders].mean(axis=0)

    hips = [i for i in (L_HIP, R_HIP) if vis[i] >= VISIBLE]
    if hips:
        hip_mid = pts[hips].mean(axis=0)
        torso_h = max(float(np.linalg.norm(hip_mid - shoulder_mid)), 1.0)
    else:
        torso_h = max((y1 - y0) * 0.3, 1.0)
        hip_mid = shoulder_mid + np.array([0.0, torso_h])

    # Feet: ankles if visible, otherwise estimate ~2 torso-lengths below the hips
    ankles = [i for i in (L_ANKLE, R_ANKLE) if vis[i] >= VISIBLE]
    if ankles:
        feet, feet_estimated = pts[ankles].mean(axis=0), False
    else:
        feet, feet_estimated = hip_mid + np.array([0.0, 2.0 * torso_h]), True

    # Facing: nose offset from the visible ears (or shoulders), normalised by
    # torso height so it doesn't depend on distance to the camera.
    ears = [i for i in (L_EAR, R_EAR) if vis[i] >= VISIBLE]
    head_ref = pts[ears].mean(axis=0) if ears else shoulder_mid
    facing = float(np.clip((pts[NOSE][0] - head_ref[0]) / (0.25 * torso_h), -1, 1))
    # Tilt: nose above the ears = looking up (+), below = looking down (-)
    tilt = float(np.clip((head_ref[1] - pts[NOSE][1]) / (0.25 * torso_h), -1, 1)) if ears else 0.0

    # Hand point: the wrist keypoint stops short of the fingers, so extend it
    # along the forearm (elbow -> wrist) to where the hand actually grabs.
    hands = []
    for wrist, elbow in ((L_WRIST, L_ELBOW), (R_WRIST, R_ELBOW)):
        if vis[wrist] < VISIBLE:
            continue
        hand = pts[wrist] + (HAND_EXTEND * (pts[wrist] - pts[elbow]) if vis[elbow] >= VISIBLE else 0)
        hands.append(tuple(int(v) for v in hand))
    return {
        "bbox": (int(x0), int(y0), int(x1 - x0), int(y1 - y0)),
        "feet": (int(feet[0]), int(feet[1])),
        "feet_estimated": feet_estimated,
        "nose": (int(pts[NOSE][0]), int(pts[NOSE][1])),
        "hip_mid": (int(hip_mid[0]), int(hip_mid[1])),
        "shoulder_mid": (int(shoulder_mid[0]), int(shoulder_mid[1])),
        "torso_h": torso_h,
        "hands": hands,
        "facing": round(facing, 3),
        "tilt": round(tilt, 3),
    }
