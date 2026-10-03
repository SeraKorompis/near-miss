"""Head pose estimation with MediaPipe Face Landmarker (Tasks API).

Shared interface between the head-pose work and the tracking/zones work:

    estimator = HeadPoseEstimator()
    poses = estimator.get_head_poses(frame_bgr, timestamp_ms)
    # [{"bbox": (x, y, w, h), "center": (cx, cy), "yaw": -18.2, "pitch": 5.1}, ...]

yaw   = left/right rotation in degrees
pitch = up/down rotation in degrees
The sign conventions don't matter for us: calibration learns what angles
each product corresponds to.
"""
import math
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions, vision

MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "face_landmarker.task"


def rotation_to_yaw_pitch(matrix):
    """Extract (yaw, pitch) in degrees from a 4x4 facial transformation matrix."""
    r = np.asarray(matrix)[:3, :3]
    yaw = math.degrees(math.atan2(r[0, 2], r[2, 2]))
    pitch = math.degrees(math.asin(max(-1.0, min(1.0, -r[1, 2]))))
    return yaw, pitch


class HeadPoseEstimator:
    def __init__(self, model_path=MODEL_PATH, max_faces=3, min_confidence=0.5):
        if not Path(model_path).exists():
            raise FileNotFoundError(
                f"{model_path} not found. Download it with:\n"
                "curl -L -o models/face_landmarker.task https://storage.googleapis.com/"
                "mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
            )
        options = vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(model_path), delegate=BaseOptions.Delegate.CPU),
            running_mode=vision.RunningMode.VIDEO,
            num_faces=max_faces,
            min_face_detection_confidence=min_confidence,
            min_face_presence_confidence=min_confidence,
            min_tracking_confidence=min_confidence,
            output_facial_transformation_matrixes=True,
        )
        self.landmarker = vision.FaceLandmarker.create_from_options(options)
        self._last_ts = -1

    def get_head_poses(self, frame_bgr, timestamp_ms):
        """Return one dict per detected face. timestamp_ms must increase every call."""
        timestamp_ms = int(max(timestamp_ms, self._last_ts + 1))
        self._last_ts = timestamp_ms

        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self.landmarker.detect_for_video(image, timestamp_ms)

        h, w = frame_bgr.shape[:2]
        poses = []
        for landmarks, matrix in zip(result.face_landmarks, result.facial_transformation_matrixes):
            xs = [p.x * w for p in landmarks]
            ys = [p.y * h for p in landmarks]
            x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
            yaw, pitch = rotation_to_yaw_pitch(matrix)
            poses.append({
                "bbox": (int(x0), int(y0), int(x1 - x0), int(y1 - y0)),
                "center": (int((x0 + x1) / 2), int((y0 + y1) / 2)),
                "nose": (int(landmarks[1].x * w), int(landmarks[1].y * h)),
                "yaw": round(yaw, 2),
                "pitch": round(pitch, 2),
            })
        return poses

    def close(self):
        self.landmarker.close()


def draw_pose(frame, pose, label=None, color=(0, 255, 0)):
    """Draw bbox, a gaze arrow from the nose and an optional label."""
    x, y, w, h = pose["bbox"]
    cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
    nx, ny = pose["nose"]
    length = max(w, 60)
    dx = int(length * math.sin(math.radians(pose["yaw"])))
    dy = int(-length * math.sin(math.radians(pose["pitch"])))
    cv2.arrowedLine(frame, (nx, ny), (nx + dx, ny + dy), (0, 0, 255), 2, tipLength=0.2)
    text = f"yaw {pose['yaw']:+.0f} pitch {pose['pitch']:+.0f}"
    if label:
        text = f"{label} | {text}"
    cv2.putText(frame, text, (x, max(20, y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
