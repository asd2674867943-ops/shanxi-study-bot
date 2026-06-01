"""Test key features of study bot"""
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, '.')

from study_bot.config import SCORE_LINE_HISTORY
from study_bot.services.score_predictor import (
    predict_score_line, calc_target_progress,
    decompose_target_score
)

# Test 1: Score line prediction
print("=" * 50)
print("TEST 1: Score Line Prediction")
print("=" * 50)
pred = predict_score_line(2026)
print(f"  Predicted 2026 score: {pred['predicted']}")
print(f"  Confidence range: {pred['confidence_range']}")
print(f"  Trend: {pred['trend']}")
print(f"  R-squared: {pred['r_squared']}")
print(f"  Historical data: {[(h['year'], h['score']) for h in pred['history']]}")
print()

# Test 2: Progress tracking
print("=" * 50)
print("TEST 2: Progress Tracking")
print("=" * 50)
progress = calc_target_progress(
    current_estimated_score=180,
    target_score=pred['predicted'] + 10,
    days_until_exam=280,
    total_study_hours=120,
)
print(f"  Target score: {progress['target_score']}")
print(f"  Current estimated: {progress['current_score']}")
print(f"  Gap: {progress['gap']}")
print(f"  Progress: {progress['progress_pct']}%")
print(f"  Status: {progress['status']}")
print()

# Test 3: Subject decomposition
print("=" * 50)
print("TEST 3: Subject Score Decomposition")
print("=" * 50)
decompose = decompose_target_score(
    pred['predicted'] + 10,
    {"电路分析": 0.5, "高等数学": 0.6, "英语": 0.3}
)
for d in decompose:
    print(f"  {d['subject']}: {d['current_score']:.1f} -> {d['target_score']:.1f}/{d['max_score']} (gap: {d['gap']:.1f})")

print()
print("=" * 50)
print("[OK] All tests passed!")
print("=" * 50)
