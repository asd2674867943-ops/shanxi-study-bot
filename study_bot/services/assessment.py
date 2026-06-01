"""
知识点掌握度评估算法
包括：掌握度计算、薄弱点分析、得分预估
"""

import math
from datetime import date, datetime
from typing import List, Optional

from study_bot.database.ops import (
    get_user_mastery,
    get_all_subjects,
    get_chapters_by_subject,
    get_streak,
    get_total_study_hours,
    get_weekly_logs,
)
from study_bot.config import FORGET_DECAY_RATE, FORGET_THRESHOLD_DAYS


def calc_mastery_with_decay(mastery_row: dict) -> float:
    """
    计算考虑遗忘衰减后的真实掌握度
    公式：
      mastery = raw_mastery * decay_factor
      其中 decay_factor = exp(-decay_rate * max(0, days_since_review - threshold))
    """
    raw = mastery_row.get("mastery_level", 0.0)
    last = mastery_row.get("last_reviewed")
    if not last:
        return raw  # 从未复习，保持原值

    last_date = datetime.fromisoformat(last).date()
    days_since = (date.today() - last_date).days
    if days_since <= FORGET_THRESHOLD_DAYS:
        return raw

    decay = math.exp(-FORGET_DECAY_RATE * (days_since - FORGET_THRESHOLD_DAYS))
    return raw * decay


async def get_weaknesses(user_id: int, top_n: int = 5) -> list:
    """获取最薄弱的知识点列表"""
    all_mastery = await get_user_mastery(user_id)
    if not all_mastery:
        return []

    # 计算每个章节的综合评分（越低越弱）
    scored = []
    for m in all_mastery:
        effective = calc_mastery_with_decay(m)
        importance = m.get("importance", 3)
        # 重要度高但掌握度低的章节得分最低（最需要关注）
        score = effective * 0.6 + (1.0 / importance) * 0.4
        scored.append({
            "chapter_id": m["chapter_id"],
            "chapter_name": m["chapter_name"],
            "subject_name": m["subject_name"],
            "mastery": effective,
            "raw_mastery": m["mastery_level"],
            "importance": importance,
            "score": score,
        })

    scored.sort(key=lambda x: x["score"])
    return scored[:top_n]


async def get_subject_progress(user_id: int) -> List[dict]:
    """获取各科目整体进度"""
    subjects = await get_all_subjects()
    result = []

    for subj in subjects:
        mastery_list = await get_user_mastery(user_id, subj["id"])
        if not mastery_list:
            result.append({
                "subject_name": subj["name"],
                "max_score": subj["max_score"],
                "avg_mastery": 0.0,
                "mastered_chapters": 0,
                "total_chapters": 0,
                "estimated_score": 0,
                "weaknesses": [],
            })
            continue

        total = len(mastery_list)
        # 掌握度>=0.6视为已掌握
        mastered = sum(1 for m in mastery_list if m["mastery_level"] >= 0.6)
        avg_mastery = sum(m["mastery_level"] for m in mastery_list) / total

        # 考虑遗忘的有效掌握度
        effective_masteries = [calc_mastery_with_decay(m) for m in mastery_list]
        effective_avg = sum(effective_masteries) / len(effective_masteries)

        # 预估得分
        estimated = int(subj["max_score"] * effective_avg)

        # 薄弱章节
        weak = sorted(
            [m for m in mastery_list if m["mastery_level"] < 0.5],
            key=lambda m: (m["mastery_level"], -m["importance"]),
        )[:3]

        result.append({
            "subject_name": subj["name"],
            "max_score": subj["max_score"],
            "avg_mastery": avg_mastery,
            "effective_mastery": effective_avg,
            "mastered_chapters": mastered,
            "total_chapters": total,
            "estimated_score": estimated,
            "weaknesses": [
                {"name": w["chapter_name"], "mastery": w["mastery_level"]}
                for w in weak
            ],
        })

    return result


async def get_progress_summary(user_id: int) -> dict:
    """生成进度总览数据"""
    subjects_progress = await get_subject_progress(user_id)
    streak = await get_streak(user_id)
    total_minutes = await get_total_study_hours(user_id)

    # 本周学习统计
    weekly_logs = await get_weekly_logs(user_id)
    weekly_minutes = sum(log["time_spent_min"] for log in weekly_logs if log["time_spent_min"])
    weekly_days = len(set(log["date"] for log in weekly_logs))

    total_estimated = sum(s["estimated_score"] for s in subjects_progress)
    max_total = sum(s["max_score"] for s in subjects_progress)

    return {
        "subjects": subjects_progress,
        "streak": streak,
        "total_hours": round(total_minutes / 60, 1),
        "weekly_hours": round(weekly_minutes / 60, 1),
        "weekly_days": weekly_days,
        "daily_avg_hours": round(weekly_minutes / 60 / max(weekly_days, 1), 1),
        "total_estimated": total_estimated,
        "max_total": max_total,
    }


def format_progress_message(summary: dict, exam_date: str) -> str:
    """格式化进度总览消息"""
    from study_bot.utils.helpers import days_until, progress_bar, format_percentage, rank_emoji

    days_left = days_until(exam_date)
    lines = ["📊 学习进度总览", ""]

    for subj in summary["subjects"]:
        name = subj["subject_name"]
        score = subj["max_score"]
        mastery = subj["effective_mastery"]
        est = subj["estimated_score"]
        bar = progress_bar(mastery)
        pct = format_percentage(mastery)
        emoji = rank_emoji(mastery)

        lines.append(f"{emoji} {name} ({score}分)")
        lines.append(f"   {bar} {pct}  预估：{est}分")
        if subj["weaknesses"]:
            weak_names = [w["name"] for w in subj["weaknesses"]]
            lines.append(f"   弱项：{'、'.join(weak_names[:2])}")
        lines.append("")

    # 统计行
    lines.append("─" * 25)
    lines.append(f"")
    lines.append(f"🔥 连续学习：{summary['streak']['current_streak']}天 "
                 f"| ⏰ 总学习：{summary['total_hours']}小时")
    lines.append(f"📈 本周日均：{summary['daily_avg_hours']}小时 "
                 f"| 📅 距考试：{days_left}天")
    lines.append(f"🎯 预估总分：{summary['total_estimated']}/{summary['max_total']}分")
    lines.append(f"")

    # 效率评级
    daily_avg = summary["daily_avg_hours"]
    if daily_avg >= 8:
        grade = "S  🏆 非常努力！保持住！"
    elif daily_avg >= 6:
        grade = "A  💪 节奏不错，稳步前进"
    elif daily_avg >= 4:
        grade = "B  👍 中规中矩，还可以加量"
    elif daily_avg >= 2:
        grade = "C  📖 时间投入偏少，需要加强"
    else:
        grade = "D  ⚠️ 备考时间紧迫，请尽快进入状态"
    lines.append(f"效率评级：{grade}")

    return "\n".join(lines)
