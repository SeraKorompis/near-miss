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

## Dashboard

The live floor counts glances, products looked at, and a dwell timer that climbs while the same product name keeps arriving. History stays on dummy volumes for this shelf and ranks the next move. Today and this month scale the week’s volume. They do not change the decision.

```bash
cd frontend
npm install
npm run dev
```

Open the URL Vite prints (usually http://localhost:5173).

The dashboard does not read pixels. It needs the product name the vision model returns. In the browser console, while a clip plays:

```js
NearMiss.gaze('Dash Pink Lady Apple Sparkling Water')  // or null
NearMiss.purchase('Lowrise Lager')
NearMiss.reset()
```

Or launch with a socket and send the same JSON:

```bash
# open http://localhost:5173/?feed=ws://localhost:8765
```

```json
{ "type": "gaze", "name": "Dash Pink Lady Apple Sparkling Water" }
{ "type": "purchase", "name": "Lowrise Lager" }
{ "type": "reset" }
```

The first message takes over from the mock shoppers. Names are matched to the shelf list, case-insensitively. An unknown name still runs the timer, and dummy history is left unchanged.

Store zones and dwell, not faces or identity. Head direction is a proxy for gaze, not gaze itself. The purchase side is a simulated till log until a real one is connected.
