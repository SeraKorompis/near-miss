# Near-Miss
EAT_HACK - shows brands the sales they *almost* won: products shoppers looked at or picked up, but didn't buy.

## Quick start (demo) - no labelling needed
Python 3.10-3.12.
```bash
git switch vision-pipeline
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
./run_demo.sh            # plays all 3 demo videos with gaze tracking (space = pause, q = next)
./run_demo.sh IMG_9472   # just one video
```
The product zones for the demo videos are already in `zones_tripod.json`, so **don't run
`calibrate.py` or `draw_zones.py`** for the demo - those are only for a new camera setup.

Results go to `output/<video>/`:
- `annotated.mp4` - video with gaze cone, highlighted product and dwell-time panel
- `attention_events.csv` - person_id, product_id, start_s, end_s, dwell_s, touched
- `attention_frames.csv` - per-frame detail

## Near-misses, AI recommendations and dashboard
```bash
./run_demo.sh --no-show            # 1. attention events for the 3 videos
python analysis/nearmiss.py         # 2. + till log -> output/results.json
python analysis/recommend.py        # 3. Ollama (gemma3:12b) -> output/recommendations.json (~45 s)
streamlit run dashboard/app.py      # 4. dashboard at http://localhost:8501
```
- `analysis/till_log.csv` is the simulated till log (what each shopper bought).
- Near-miss = picked up and put back, or looked >= 2.5 s without touching, and not bought.
- `recommend.py` falls back to rules if Ollama isn't running (`--rules` forces that);
  other model: `NEARMISS_MODEL=llama3.2:3b python analysis/recommend.py`.

## Demo videos
`videos/IMG_9470.MOV`, `IMG_9472.MOV`, `IMG_9473.MOV` (tripod, same camera position).

| Video | What happens |
|---|---|
| IMG_9470 | Takes crisps_packs and leaves with it (purchase) |
| IMG_9472 | Picks up well_truly_crunchies, puts them back, takes crisps_packs (near-miss on crunchies) |
| IMG_9473 | Looks at the shelf (mostly crisps_packs / top_shelf), touches nothing (near-miss) |

## How it works
- **People + body pose**: YOLOv8-pose + ByteTrack (works from behind, in profile, legs out of frame)
- **Head direction**: face yaw (MediaPipe) when the face is visible, otherwise nose-vs-ears from the body pose
- **Looking**: the gaze cone has to hit a product zone (first zone along the ray wins)
- **Touching**: a hand reaching out into a product zone
- **Holding**: after touching, a hand held up near the face = examining that product

Code is in `pipeline/`: `body_pose.py`, `head_pose.py`, `fusion.py` (the logic), `viz.py` (drawing),
`run_attention.py` (runner). Tune thresholds at the top of `pipeline/fusion.py`.

## New camera setup (not needed for the demo)
Film with a **fixed camera** (tripod) - zones are drawn once, so a moving camera makes them drift.

1. Draw product zones on a frame of the new video (click the corners of each product's area on the shelf, ENTER):
```bash
python pipeline/draw_zones.py --source my_video.mov --products product_a,product_b --out zones.json
```
2. Run:
```bash
python pipeline/run_attention.py --source my_video.mov --zones zones.json
```
`--source 0` uses the webcam. `--no-show` skips the live window.

`pipeline/calibrate.py` is an older face-only prototype (camera at the shelf facing the shopper); it isn't used by the demo.
