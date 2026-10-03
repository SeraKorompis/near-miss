#!/usr/bin/env bash
# Run the attention pipeline on the 3 demo videos (zones are already set up).
#   ./run_demo.sh              all three videos, live window
#   ./run_demo.sh IMG_9472     just one
#   ./run_demo.sh --no-show    all three, no window (just write output/)
set -e
cd "$(dirname "$0")"
[ -d .venv ] && source .venv/bin/activate

videos=()
extra=()
for arg in "$@"; do
  case "$arg" in
    --*) extra+=("$arg") ;;
    *) videos+=("$arg") ;;
  esac
done
[ ${#videos[@]} -eq 0 ] && videos=(IMG_9470 IMG_9472 IMG_9473)

for v in "${videos[@]}"; do
  echo "=== $v"
  python pipeline/run_attention.py --source "videos/$v.MOV" --zones zones_tripod.json --out-dir "output/$v" "${extra[@]}"
done
