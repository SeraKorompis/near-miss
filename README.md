# near-miss
EAT_HACK

## Setup
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```
The face model is in `models/face_landmarker.task`.

## Calibration
Camera at the shelf, facing the shopper. Stand where shoppers will stand.
```bash
python pipeline/calibrate.py --source 0 --products chocolate,coffee,chips,juice
```
Look at each product and press its number key (1-9); press it 2-3 times per product.
Press `t` to test live, `s` to save `calibration.json`, `q` to quit.

For a pre-recorded clip where someone looks at each product at known times:
```bash
python pipeline/calibrate.py --source demo.mp4 --segments segments.json
```
`segments.json`: `{"chocolate": [2.0, 4.0], "coffee": [5.0, 7.0]}` (seconds).

Using it in code:
```python
from head_pose import HeadPoseEstimator
from zones import ZoneClassifier
est = HeadPoseEstimator(); clf = ZoneClassifier.load("calibration.json")
for pose in est.get_head_poses(frame, timestamp_ms):
    product = clf.classify(pose["yaw"], pose["pitch"])  # or None
```

## Aisle camera: body position + head direction (recommended)
Body + tracking: **YOLOv8-pose + ByteTrack** (works from behind, in profile, with legs out of frame).
Head direction: face yaw (MediaPipe) when the face is visible, otherwise nose-vs-ears from YOLO pose.

Zones (`pipeline/draw_zones.py`):
- **shelf** (default): draw each product's area on the shelf. Attended = head faces it (nearest
  zone on that side); **touch** = a wrist enters it.
- **floor** (`--kind floor`, fixed camera + feet visible): draw where a shopper stands; attended =
  feet inside it AND facing its shelf side.

```bash
python pipeline/draw_zones.py --source demo.mp4 --products canned_goods,tang_jars,goody_cans
python pipeline/run_attention.py --source demo.mp4 --zones zones.json
```
Opens a **live window** (real-time) with gaze cones, the looked-at product highlighted and a dwell-time panel (`--no-show` to skip).
Outputs in `output/`: `attention_events.csv` (person_id, product_id, start_s, end_s, dwell_s, touched),
`attention_frames.csv` (per frame) and `annotated.mp4`. 4K input is resized to 1280 px wide and sampled at ~15 fps.
`mock_zones.json` is an example for the stock test clip.

**Film with a fixed camera (tripod / phone leaning on the shelf)** - zones are drawn once, so a moving camera makes them drift.
Tune `FACING_THRESHOLD` / `FACE_WEIGHT` / `SHELF_REACH` in `pipeline/fusion.py` and `MIN_EVENT_S` in `pipeline/run_attention.py`.
