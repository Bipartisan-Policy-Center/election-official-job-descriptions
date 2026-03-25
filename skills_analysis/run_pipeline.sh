#!/usr/bin/env bash
# run_pipeline.sh — runs the full skills analysis pipeline end-to-end.
#
# Usage (from repo root):
#   python3 skills_analysis/01_extract_all.py        # step 1: extract (resumable)
#   python3 skills_analysis/02_merge_outputs.py      # step 2: merge
#   python3 skills_analysis/03_build_validation_sample.py  # step 3: validation sample
#
# Or run all steps at once:
#   bash skills_analysis/run_pipeline.sh
#
# To start completely fresh (clear all cached API responses):
#   bash skills_analysis/run_pipeline.sh --fresh

set -e
cd "$(dirname "$0")/.."

SKILLS_DIR="skills_analysis"

if [[ "$1" == "--fresh" ]]; then
  echo "=== --fresh: clearing cached extraction results ==="
  rm -rf "$SKILLS_DIR/api_cache_combined"
  rm -f  "$SKILLS_DIR/skills_extracted.csv"
  rm -f  "$SKILLS_DIR/dataset_final.csv"
  rm -f  "$SKILLS_DIR/extraction_errors.csv"
  echo "  Done."
  echo ""
fi

echo "=== Step 1/3: extraction (text selection + skill/salary/classification) ==="
python3 "$SKILLS_DIR/01_extract_all.py"
echo ""

echo "=== Step 2/3: merge into dataset_final.csv ==="
python3 "$SKILLS_DIR/02_merge_outputs.py"
echo ""

echo "=== Step 3/3: build validation sample ==="
python3 "$SKILLS_DIR/03_build_validation_sample.py"
echo ""

echo "=== Pipeline complete ==="
echo "  Output: $SKILLS_DIR/dataset_final.csv"
echo "  Validation tool: $SKILLS_DIR/validation_review.html"
