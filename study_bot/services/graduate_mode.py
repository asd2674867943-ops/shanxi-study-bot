"""
研究生难度学习模式服务
处理研究生模式开启/关闭、进度追踪、深化测试触发
"""

import logging
from datetime import date, datetime, timedelta
from typing import Optional

from study_bot.config import GRADUATE_MODE, EXAM_DATE_DEFAULT
from study_bot.database.ops import (
    get_user_mastery,
    get_graduate_mode,
    set_graduate_mode,
    toggle_graduate_mode,
    update_graduate_progress,
    get_user_mode,
)
from study_bot.utils.helpers import progress_bar, format_percentage, days_until

logger = logging.getLogger(__name__)


async def can_start_graduate_mode(user_id: int) -> dict:
    """
    检查用户是否可以开启研究生模式
    条件：所有专升本章节平均掌握度 >= mastery_threshold (默认75%)

    返回：
    {
        "can_start": bool,
        "overall_mastery": float,
        "threshold": float,
        "subject_details": {...},
        "blocked_subjects": [...],
        "estimated_start_date": str,
        "estimated_completion_date": str,
        "days_to_ready": int,
    }
    """
    threshold = GRADUATE_MODE["mastery_threshold"]
    mastery_data = await get_user_mastery(user_id)

    # 按科目汇总掌握度
    subject_mastery = {}
    for row in mastery_data:
        subj = row.get("subject_name", "未知")
        if subj not in subject_mastery:
            subject_mastery[subj] = {"total": 0, "chapters": []}
        subject_mastery[subj]["chapters"].append(row.get("mastery_level", 0))

    for subj, data in subject_mastery.items():
        chapters = data["chapters"]
        data["avg"] = sum(chapters) / len(chapters) if chapters else 0
        data["total"] = len(chapters)

    overall_mastery = (
        sum(d["avg"] for d in subject_mastery.values()) / len(subject_mastery)
        if subject_mastery else 0
    )

    blocked = [
        {"subject": s, "avg": d["avg"], "need": threshold - d["avg"]}
        for s, d in subject_mastery.items()
        if d["avg"] < threshold
    ]

    can_start = len(blocked) == 0 and overall_mastery >= threshold

    # 预估时间
    today = date.today()
    if can_start:
        estimated_start = today.isoformat()
        weeks = GRADUATE_MODE["estimated_completion_weeks"]
        estimated_completion = (today + timedelta(weeks=weeks)).isoformat()
        days_to_ready = 0
    else:
        # 估算：假设每周掌握度提升5%
        max_gap = max((b["need"] for b in blocked), default=0)
        weeks_needed = max_gap / 0.05 if max_gap > 0 else 4
        days_to_ready = int(weeks_needed * 7)
        estimated_start = (today + timedelta(days=days_to_ready)).isoformat()
        weeks = GRADUATE_MODE["estimated_completion_weeks"]
        estimated_completion = (today + timedelta(days=days_to_ready + weeks * 7)).isoformat()

    return {
        "can_start": can_start,
        "overall_mastery": round(overall_mastery, 2),
        "threshold": threshold,
        "subject_details": subject_mastery,
        "blocked_subjects": blocked,
        "estimated_start_date": estimated_start,
        "estimated_completion_date": estimated_completion,
        "days_to_ready": days_to_ready,
    }


async def generate_graduate_study_plan(user_id: int, daily_hours: int = None) -> dict:
    """
    生成研究生模式的学习计划
    复用 plan_generator 框架，但使用研究生模块结构
    """
    from study_bot.services.plan_generator import generate_daily_plan

    if daily_hours is None:
        daily_hours = GRADUATE_MODE["daily_hours_target"]

    plan = await generate_daily_plan(
        user_id,
        daily_hours=daily_hours,
        day_type="free_day",
        study_mode="graduate",
    )
    plan["study_mode"] = "graduate"
    plan["modules"] = GRADUATE_MODE["modules"]
    return plan


async def get_graduate_progress(user_id: int) -> dict:
    """
    获取研究生模式学习进度
    """
    grad_data = await get_graduate_mode(user_id)
    if not grad_data:
        return {
            "is_active": False,
            "total": GRADUATE_MODE["modules"],
            "completed": 0,
            "percentage": 0.0,
            "modules": GRADUATE_MODE["modules"],
            "started_at": None,
            "target_completion_date": None,
            "exam_days_left": days_until(EXAM_DATE_DEFAULT),
        }

    total = grad_data.get("total_modules") or 5
    completed = grad_data.get("completed_modules") or 0
    percentage = round(completed / total * 100, 1) if total > 0 else 0.0

    return {
        "is_active": bool(grad_data.get("is_active")),
        "total": total,
        "completed": completed,
        "percentage": percentage,
        "modules": GRADUATE_MODE["modules"],
        "started_at": grad_data.get("started_at"),
        "target_completion_date": grad_data.get("target_completion_date"),
        "exam_days_left": days_until(EXAM_DATE_DEFAULT),
    }


async def trigger_deepened_exam(user_id: int) -> dict:
    """
    研究生模式完成后，触发深化专升本综合测试
    为三科各生成一份深化测试
    """
    from study_bot.services.test_generator import create_weekly_test

    subjects = ["高等数学", "电路分析", "英语"]
    results = {}

    for subj in subjects:
        result = await create_weekly_test(
            user_id=user_id,
            subject_name=subj,
            difficulty="deepened",
            question_count=8,
        )
        results[subj] = result

    return {
        "type": "deepened_exam",
        "subjects": subjects,
        "results": results,
    }


def format_graduate_progress_bar(progress_data: dict) -> str:
    """格式化研究生模式进度条消息"""
    pct = progress_data.get("percentage", 0)
    bar = progress_bar(pct, length=15)
    is_active = progress_data.get("is_active", False)
    status = "🎓 研究生模式" if is_active else "⏸️ 研究生模式（未开启）"

    lines = [status, "", f"📊 学习进度：{bar} {pct}%"]
    lines.append(f"   已完成模块：{progress_data['completed']}/{progress_data['total']}")

    modules = progress_data.get("modules", [])
    for i, m in enumerate(modules):
        status_icon = "✅" if i < progress_data["completed"] else "⬜"
        lines.append(f"   {status_icon} {m['name']} ({m['subject']}, 权重{m['weight']}%)")

    if progress_data.get("target_completion_date"):
        lines.append(f"")
        lines.append(f"🏁 预计完成日期：{progress_data['target_completion_date']}")

    lines.append(f"📅 距专升本考试：{progress_data.get('exam_days_left', '?')} 天")

    if pct >= 100:
        lines.append("")
        lines.append("🎉 研究生模式全部完成！")
        lines.append("📋 建议进行 /graduate 深化专升本综合测试")

    return "\n".join(lines)


def format_graduate_eligibility(eligibility: dict) -> str:
    """格式化研究生模式资格评估消息"""
    can_start = eligibility.get("can_start", False)
    overall = eligibility.get("overall_mastery", 0)
    threshold = eligibility.get("threshold", 0.75)

    lines = ["🎓 研究生模式 — 资格评估", ""]
    lines.append(f"📊 当前整体掌握度：{format_percentage(overall)}")
    lines.append(f"🎯 开启门槛：{format_percentage(threshold)}")
    lines.append("")

    # 各科目详情
    for subj, data in eligibility.get("subject_details", {}).items():
        bar = progress_bar(data["avg"] * 100, length=10)
        lines.append(f"   {subj}：{bar} {format_percentage(data['avg'])}")
    lines.append("")

    if can_start:
        lines.append("✅ 恭喜！你已达到研究生模式的开启条件！")
        lines.append(f"📅 预计开始：{eligibility['estimated_start_date']}")
        lines.append(f"🏁 预计完成：{eligibility['estimated_completion_date']}")
        lines.append("")
        lines.append("研究生模式将在现有专升本基础上，进一步深入学习：")
        for m in GRADUATE_MODE["modules"]:
            lines.append(f"   📚 {m['name']}")
    else:
        lines.append("❌ 暂未达到研究生模式开启条件")
        lines.append("")
        blocked = eligibility.get("blocked_subjects", [])
        if blocked:
            lines.append("⚠️ 以下科目需要加强：")
            for b in blocked:
                lines.append(f"   {b['subject']}：当前 {format_percentage(b['avg'])}，需提升至 {format_percentage(threshold)}（差 {format_percentage(b['need'])}）")
        lines.append("")
        lines.append(f"📅 预计还需 {eligibility['days_to_ready']} 天可达到开启条件")
        lines.append(f"   预计可开启日期：{eligibility['estimated_start_date']}")

    return "\n".join(lines)


def format_graduate_mode_plan_header(progress_data: dict) -> str:
    """在研究计划消息中嵌入的简短研究生模式头部"""
    if not progress_data.get("is_active"):
        return ""

    pct = progress_data.get("percentage", 0)
    bar = progress_bar(pct, length=10)
    return (
        f"\n🎓 研究生模式 | {bar} {pct}%\n"
        f"   模块：{progress_data['completed']}/{progress_data['total']} | "
        f"距考试：{progress_data.get('exam_days_left', '?')}天\n"
    )
