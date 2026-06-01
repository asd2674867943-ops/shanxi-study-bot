"""
分数线预测与目标进度追踪
基于历史数据线性回归预测当年分数线，追踪学习进度与目标的差距
"""

import math
from datetime import date
from typing import List, Tuple, Optional

from study_bot.config import SCORE_LINE_HISTORY, DEFAULT_TARGET_SCORE, EXAM_TOTAL_SCORE


# ============================================================
# 分数线预测（线性回归 + 加权平均）
# ============================================================

def predict_score_line(target_year: int = 2026) -> dict:
    """
    预测目标年份的分数线
    使用加权线性回归（越近年份权重越大） + 趋势分析

    返回：
    {
        "predicted": 预测分数,
        "confidence_range": (最低, 最高),
        "trend": "上升/下降/平稳",
        "formula": "回归方程描述",
        "history": [...]
    }
    """
    years = sorted(SCORE_LINE_HISTORY.keys())
    scores = [SCORE_LINE_HISTORY[y] for y in years]

    if len(years) < 2:
        return {
            "predicted": DEFAULT_TARGET_SCORE,
            "confidence_range": (DEFAULT_TARGET_SCORE - 10, DEFAULT_TARGET_SCORE + 10),
            "trend": "数据不足",
            "formula": "至少需要2年数据",
            "history": [],
        }

    # 加权线性回归：越近的年份权重越大
    n = len(years)
    base_weight = 1.0
    weights = []
    for i in range(n):
        # 最近一年权重最高，逐年递减
        w = base_weight + (i / max(1, n - 1)) * 1.5
        weights.append(w)

    # 加权最小二乘法
    sum_w = sum(weights)
    sum_wx = sum(w * y for w, y in zip(weights, years))
    sum_wy = sum(w * s for w, s in zip(weights, scores))
    sum_wx2 = sum(w * y * y for w, y in zip(weights, years))
    sum_wxy = sum(w * y * s for w, y, s in zip(weights, years, scores))

    denominator = sum_w * sum_wx2 - sum_wx * sum_wx
    if abs(denominator) < 1e-10:
        # 无法回归，取均值
        avg = sum(scores) / n
        return {
            "predicted": round(avg, 1),
            "confidence_range": (round(avg - 10, 1), round(avg + 10, 1)),
            "trend": "平稳",
            "formula": "数据不足，取历年均值",
            "history": [{"year": y, "score": s} for y, s in zip(years, scores)],
        }

    slope = (sum_w * sum_wxy - sum_wx * sum_wy) / denominator
    intercept = (sum_wy - slope * sum_wx) / sum_w

    predicted = slope * target_year + intercept

    # 计算置信区间（基于残差标准差）
    residuals = [s - (slope * y + intercept) for y, s in zip(years, scores)]
    residual_std = math.sqrt(sum(r * r for r in residuals) / max(1, n - 2))
    margin = 2.0 * residual_std  # ~95% 置信区间

    # 趋势判断
    if slope > 1.5:
        trend = "上升"
    elif slope < -1.5:
        trend = "下降"
    else:
        trend = "平稳"

    return {
        "predicted": round(predicted, 1),
        "confidence_range": (
            round(max(0, predicted - margin), 1),
            round(predicted + margin, 1),
        ),
        "trend": trend,
        "slope": round(slope, 3),
        "formula": f"y = {slope:.3f} × 年份 + {intercept:.1f}",
        "r_squared": _calc_r_squared(years, scores, slope, intercept),
        "history": [{"year": y, "score": s} for y, s in zip(years, scores)],
    }


def _calc_r_squared(years, scores, slope, intercept):
    """计算R²（拟合优度）"""
    mean_score = sum(scores) / len(scores)
    ss_total = sum((s - mean_score) ** 2 for s in scores)
    ss_residual = sum((s - (slope * y + intercept)) ** 2 for y, s in zip(years, scores))
    if ss_total == 0:
        return 1.0
    return round(1 - ss_residual / ss_total, 4)


# ============================================================
# 目标进度追踪
# ============================================================

def calc_target_progress(
    current_estimated_score: float,
    target_score: float = None,
    days_until_exam: int = 0,
    total_study_hours: float = 0,
) -> dict:
    """
    计算目标达成进度
    current_estimated_score: 当前预估总分
    target_score: 目标分数（默认使用预测分数线）
    """
    if target_score is None:
        prediction = predict_score_line()
        target_score = prediction["predicted"] + 10  # 建议比预测线高10分安全

    target_score = max(target_score, 1)
    progress_pct = min(1.0, current_estimated_score / target_score)
    gap = target_score - current_estimated_score

    # 分数进度条
    bar_length = 20
    filled = int(progress_pct * bar_length)
    bar = "█" * filled + "░" * (bar_length - filled)

    # 状态评估
    if progress_pct >= 1.0:
        status = "🎉 已达到目标！继续保持！"
        suggestion = "保持当前学习节奏，巩固已有成果"
    elif progress_pct >= 0.8:
        status = "💪 接近目标，冲刺阶段"
        suggestion = f"还需提升{gap:.0f}分，重点突破薄弱科目"
    elif progress_pct >= 0.6:
        status = "📖 中等进度，需要加速"
        suggestion = f"距离目标还差{gap:.0f}分，建议增加学习强度"
    elif progress_pct >= 0.4:
        status = "🔰 差距较大，急需加强"
        suggestion = f"距目标尚缺{gap:.0f}分，建议调整学习策略"
    else:
        status = "⚠️ 起步阶段，任重道远"
        suggestion = f"目标差距{gap:.0f}分，从基础开始，稳扎稳打"

    return {
        "target_score": target_score,
        "current_score": round(current_estimated_score, 1),
        "gap": round(gap, 1),
        "progress_pct": round(progress_pct * 100, 1),
        "progress_bar": bar,
        "status": status,
        "suggestion": suggestion,
        "days_until_exam": days_until_exam,
        "total_study_hours": total_study_hours,
        "score_per_day_needed": round(gap / max(1, days_until_exam), 2) if days_until_exam > 0 else gap,
    }


# ============================================================
# 各科目标分解
# ============================================================

def decompose_target_score(
    target_total: float,
    subject_mastery: dict,  # {"电路分析": 0.5, "高等数学": 0.6, "英语": 0.3}
) -> List[dict]:
    """
    将总分目标分解到各科目
    根据各科满分和当前掌握度计算各科需要达到的分数
    """
    max_scores = {
        "电路分析": 150,
        "英语": 50,
        "高等数学": 100,
    }

    total_max = sum(max_scores.values())

    results = []
    for subj_name, max_score in max_scores.items():
        current_mastery = subject_mastery.get(subj_name, 0.0)
        current_score = current_mastery * max_score

        # 按满分比例分配目标
        proportion = max_score / total_max
        target_subject = target_total * proportion

        # 计算该科需要达到的掌握度
        target_mastery = target_subject / max_score
        gap_subject = target_subject - current_score

        results.append({
            "subject": subj_name,
            "max_score": max_score,
            "current_mastery": round(current_mastery * 100, 1),
            "target_mastery": round(target_mastery * 100, 1),
            "current_score": round(current_score, 1),
            "target_score": round(target_subject, 1),
            "gap": round(gap_subject, 1),
            "gap_bar": "█" * int(abs(gap_subject) / max_score * 10) + "░" * (10 - int(abs(gap_subject) / max_score * 10)),
        })

    return results


# ============================================================
# 格式化输出
# ============================================================

def format_score_prediction(prediction: dict, target_univ: str = "太原工业学院") -> str:
    """格式化分数线预测结果"""
    pred = prediction["predicted"]
    low, high = prediction["confidence_range"]
    trend = prediction["trend"]

    lines = [
        f"📊 {target_univ} 分数线预测",
        f"",
        f"🎯 2026年预测分数线：{pred}分",
        f"📐 置信区间：{low}分 ~ {high}分",
        f"📈 趋势：{trend}",
        f"📏 拟合优度 R² = {prediction.get('r_squared', 'N/A')}",
        f"",
        f"📋 历年数据：",
    ]

    for item in prediction.get("history", []):
        bar = "█" * int(item["score"] / 300 * 15) + "░" * (15 - int(item["score"] / 300 * 15))
        lines.append(f"   {item['year']}年：{item['score']}分 {bar}")

    lines.append("")
    lines.append(f"💡 建议目标分数：{pred + 10:.0f}分（预测线 + 安全边际10分）")
    lines.append(f"   这样可以确保即便分数线小幅上涨也能录取")

    return "\n".join(lines)


def format_progress_tracker(progress: dict, target_univ: str = "太原工业学院") -> str:
    """格式化目标进度追踪"""
    bar = progress["progress_bar"]
    pct = progress["progress_pct"]

    lines = [
        f"🎯 目标进度追踪 — {target_univ}",
        f"",
        f"📊 {bar} {pct}%",
        f"",
        f"🏫 目标分数：{progress['target_score']}分",
        f"📈 当前预估：{progress['current_score']}分",
        f"📉 差距：{progress['gap']}分",
        f"",
        f"📅 距考试：{progress['days_until_exam']}天",
        f"⏰ 已学习：{progress['total_study_hours']}小时",
    ]

    if progress['days_until_exam'] > 0:
        lines.append(f"🎯 每天需提升：{progress['score_per_day_needed']}分/天")

    lines.append("")
    lines.append(f"📌 状态：{progress['status']}")
    lines.append(f"💡 {progress['suggestion']}")

    return "\n".join(lines)
