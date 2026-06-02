"""
自适应学习计划生成引擎 v2
支持：上课日/空闲日区分、周六测试、周日休息、动态调整
"""

import math
import random
from datetime import date, datetime, timedelta
from typing import List, Optional

from study_bot.database.ops import (
    get_user_mastery,
    get_all_subjects,
    get_chapters_by_subject,
    get_user,
    get_daily_logs,
    get_weekly_logs,
)
from study_bot.config import (
    CLASS_DAY_HOURS,
    FREE_DAY_HOURS,
    TEST_DAY_HOURS,
    REST_DAY_HOURS,
    MIN_SESSION_MINUTES,
    MAX_SESSION_MINUTES,
    FORGET_DECAY_RATE,
    FORGET_THRESHOLD_DAYS,
)
from study_bot.data.preset import (
    CLASS_DAY_ALLOCATION,
    FREE_DAY_ALLOCATION,
    SATURDAY_ALLOCATION,
    ENGLISH_LEARNING_PATH,
    MATH_LEARNING_PATH,
    CIRCUIT_LEARNING_PATH,
)


# ============================================================
# 日期类型判断
# ============================================================

def get_day_type(check_date: date = None) -> str:
    """
    判断某一天的日期类型
    返回："class_day" / "free_day" / "saturday_test" / "sunday_rest"
    """
    if check_date is None:
        check_date = date.today()

    weekday = check_date.weekday()  # 0=Mon, 6=Sun

    if weekday == 6:  # 周日
        return "sunday_rest"
    elif weekday == 5:  # 周六
        return "saturday_test"
    else:
        # 周一到周五：需要用户告知是否为上课日
        # 默认按空闲日处理（用户可通过 /set_schedule 设置）
        return "class_day"  # 默认上课日，用户未告知则按最少3h


def get_daily_hours_for_day(day_type: str, user_hours_override: int = None) -> int:
    """根据日期类型获取每日学习小时数"""
    if user_hours_override is not None:
        return user_hours_override

    return {
        "class_day": CLASS_DAY_HOURS,
        "free_day": FREE_DAY_HOURS,
        "saturday_test": TEST_DAY_HOURS,
        "sunday_rest": REST_DAY_HOURS,
    }.get(day_type, FREE_DAY_HOURS)


def get_time_allocation_for_day(day_type: str) -> dict:
    """根据日期类型获取各科时间分配（分钟）"""
    if day_type == "saturday_test":
        return SATURDAY_ALLOCATION
    elif day_type == "class_day":
        return CLASS_DAY_ALLOCATION
    elif day_type == "sunday_rest":
        return {}
    else:
        return FREE_DAY_ALLOCATION


# ============================================================
# 学习路径阶段判断
# ============================================================

def _get_chapters_for_phase(subject_name: str, phase_key: str) -> list:
    """根据学习路径的阶段key，返回该阶段应学习的章节名称列表"""
    path_map = {
        "英语": ENGLISH_LEARNING_PATH,
        "电路分析": CIRCUIT_LEARNING_PATH,
    }
    learning_path = path_map.get(subject_name)
    if not learning_path or phase_key not in learning_path:
        return None
    phase = learning_path[phase_key]
    chapters_field = phase.get("chapters", phase.get("chapters_order", []))
    return chapters_field


def _determine_english_phase(subj_chapters: list) -> str:
    """
    按四级路径 Phase1→2→3 判断当前阶段。
    当前阶段章节平均掌握度 < 0.6 则停留，否则进阶。
    """
    phase_order = ["phase1_foundation", "phase2_building", "phase3_practice"]
    for phase_key in phase_order:
        phase_names = _get_chapters_for_phase("英语", phase_key) or []
        phase_masteries = [
            ch_dict["mastery_level"] for (_, ch_dict) in subj_chapters
            if ch_dict.get("chapter_name") in phase_names and ch_dict.get("mastery_level", 0) > 0
        ]
        if not phase_masteries:
            return phase_key
        avg = sum(phase_masteries) / len(phase_masteries)
        if avg < 0.6:
            return phase_key
    return phase_order[-1]


def _determine_circuit_phase(subj_chapters: list) -> str:
    """
    电路：已完成一轮复习，从 Phase2 动态电路强化开始。
    当前阶段章节平均掌握度 >= 0.7 则进阶。
    """
    phase_order = ["phase2_dynamic", "phase3_sinusoidal", "phase4_advanced"]
    for phase_key in phase_order:
        phase_names = _get_chapters_for_phase("电路分析", phase_key) or []
        phase_masteries = [
            ch_dict["mastery_level"] for (_, ch_dict) in subj_chapters
            if ch_dict.get("chapter_name") in phase_names
        ]
        if not phase_masteries:
            continue
        avg = sum(phase_masteries) / len(phase_masteries)
        if avg < 0.7:
            return phase_key
    return phase_order[-1]


def _determine_math_chapter_order(subj_chapters: list) -> list:
    """
    高等数学：将 'learning' 状态章节排最前，按 MATH_LEARNING_PATH 排序。
    'review' 状态章节作为后备。
    """
    ordered_names = []
    for phase_key in ["phase1_determinant", "phase2_eigenvalue", "phase3_probability"]:
        phase = MATH_LEARNING_PATH.get(phase_key, {})
        ordered_names.extend(phase.get("chapters_order", []))
    name_order = {name: i for i, name in enumerate(ordered_names)}

    learning = [(p, ch) for (p, ch) in subj_chapters if ch.get("status") == "learning"]
    review = [(p, ch) for (p, ch) in subj_chapters if ch.get("status") != "learning"]

    learning.sort(key=lambda x: (name_order.get(x[1].get("chapter_name"), 999), -x[0]))

    return learning + review


# ============================================================
# 核心计划生成
# ============================================================

def _days_since_reviewed(mastery_row: dict) -> int:
    """计算距上次复习的天数"""
    last = mastery_row.get("last_reviewed")
    if not last:
        return 999
    last_date = datetime.fromisoformat(last).date()
    return (date.today() - last_date).days


def _calc_forget_decay(days: int) -> float:
    """计算遗忘衰减因子"""
    if days <= FORGET_THRESHOLD_DAYS:
        return 0.0
    return 1.0 - math.exp(-FORGET_DECAY_RATE * (days - FORGET_THRESHOLD_DAYS))


def _calc_chapter_priority(mastery_row: dict, days_since: int, error_count: int = 0) -> float:
    """
    计算单个章节的学习优先级 (0.0~1.0)
    考虑：掌握度 + 重要度 + 难度 + 遗忘 + 错题数量
    """
    mastery = mastery_row.get("mastery_level", 0.0)
    importance = mastery_row.get("importance", 3)
    difficulty = mastery_row.get("difficulty", 3)
    decay = _calc_forget_decay(days_since)

    priority = (
        (1.0 - mastery) * 0.35 +      # 掌握度越低优先级越高
        (importance / 5.0) * 0.25 +   # 重要度加权
        (difficulty / 5.0) * 0.15 +   # 难度加权
        decay * 0.10 +                # 遗忘因子
        min(0.15, error_count * 0.03) # 错题加成（该章节错题越多越优先）
    )
    return min(1.0, priority)


def _suggest_session_time(mastery: float, importance: int, difficulty: int) -> int:
    """根据章节情况建议学习时长（分钟）"""
    base = 45
    if difficulty >= 4:
        base += 15
    if importance >= 4:
        base += 10
    if mastery < 0.3:
        base += 15
    return min(MAX_SESSION_MINUTES, max(MIN_SESSION_MINUTES, base))


async def generate_daily_plan(
    user_id: int,
    daily_hours: int = None,
    day_type: str = None,
    is_class_day: bool = None,
    study_mode: str = None,
) -> dict:
    """
    生成每日学习计划（自适应版本）
    - daily_hours: 手动指定学习小时数（可选）
    - day_type: 手动指定日期类型（可选）
    - is_class_day: 手动指定是否为上课日（可选）
    - study_mode: 学习模式 "zhuanshengben" | "graduate"（可选，默认从DB读取）
    """
    today = date.today()

    # 0. 确定学习模式
    if study_mode is None:
        try:
            from study_bot.database.ops import get_user_mode
            study_mode = await get_user_mode(user_id)
        except Exception:
            study_mode = "zhuanshengben"

    # 研究生模式：如果周日休息，改为轻量学习（不休）
    if study_mode == "graduate" and today.weekday() == 6:
        day_type = "free_day"  # 研究生模式不休周日

    # 1. 确定日期类型和小时数
    if day_type is None:
        # 判断周日/周六
        if today.weekday() == 6:
            day_type = "sunday_rest"
        elif today.weekday() == 5:
            day_type = "saturday_test"
        elif is_class_day is not None:
            day_type = "class_day" if is_class_day else "free_day"
        else:
            day_type = "free_day"  # 默认空闲日

    if daily_hours is None:
        daily_hours = get_daily_hours_for_day(day_type)

    # 1.5. 检查是否暂停
    try:
        from study_bot.database.ops import is_plan_paused
        if await is_plan_paused(user_id):
            return _generate_paused_plan(today)
    except Exception:
        pass

    # 2. 周日休息 → 生成极简计划
    if day_type == "sunday_rest":
        return _generate_rest_day_plan(today)

    # 3. 周六测试日 → 生成测试计划
    if day_type == "saturday_test":
        return await _generate_test_day_plan(user_id, today)

    # 4. 获取错误统计（影响优先级）
    error_counts = await _get_chapter_error_counts(user_id)

    # 5. 获取科目列表和各科掌握度
    subjects = await get_all_subjects()

    mastery_by_subject = {}
    all_chapters_ranked = []

    for subj in subjects:
        chapters_mastery = await get_user_mastery(user_id, subj["id"])
        if chapters_mastery:
            avg = sum(m["mastery_level"] for m in chapters_mastery) / len(chapters_mastery)
        else:
            avg = 0.0
        mastery_by_subject[subj["name"]] = {
            "avg_mastery": avg,
            "total_score": subj["max_score"],
            "subject_id": subj["id"],
        }

        # 为每个章节计算优先级
        for ch in chapters_mastery:
            days_since = _days_since_reviewed(ch)
            err_count = error_counts.get(ch["chapter_id"], 0)
            priority = _calc_chapter_priority(ch, days_since, err_count)
            all_chapters_ranked.append((priority, ch, subj["name"], subj["id"]))

    # 按优先级排序
    all_chapters_ranked.sort(key=lambda x: x[0], reverse=True)

    # 6. 分配时间
    time_alloc = get_time_allocation_for_day(day_type)
    total_minutes = daily_hours * 60

    # 如果没有分配方案，按掌握度动态分配
    if not time_alloc:
        time_alloc = _dynamic_time_alloc(mastery_by_subject, total_minutes)

    # 7. 生成具体学习任务
    plan_sessions = []
    session_id = 0
    phase_info = {}

    for subj in subjects:
        subj_name = subj["name"]
        allocated_min = time_alloc.get(subj_name, total_minutes // 3)

        # 获取该科目排名靠前的章节
        subj_chapters = [(p, ch) for p, ch, sn, _ in all_chapters_ranked if sn == subj_name]

        # --- 学习路径阶段过滤 ---
        if subj_name == "英语":
            eng_phase = _determine_english_phase(subj_chapters)
            phase_names = _get_chapters_for_phase("英语", eng_phase) or []
            if phase_names:
                subj_chapters = [(p, ch) for (p, ch) in subj_chapters
                                 if ch.get("chapter_name") in phase_names]
            # 语法章节额外加权
            grammar_keywords = ["语法", "从句", "虚拟语气", "时态"]
            for i, (p, ch) in enumerate(subj_chapters):
                if any(kw in ch.get("chapter_name", "") for kw in grammar_keywords):
                    subj_chapters[i] = (p + 0.15, ch)
            subj_chapters.sort(key=lambda x: x[0], reverse=True)
            # 语法章节额外时间
            allocated_min = allocated_min + 15
            phase_info["英语"] = {
                "phase_key": eng_phase,
                "phase_name": ENGLISH_LEARNING_PATH.get(eng_phase, {}).get("name", ""),
            }

        elif subj_name == "高等数学":
            subj_chapters = _determine_math_chapter_order(subj_chapters)

        elif subj_name == "电路分析":
            circuit_phase = _determine_circuit_phase(subj_chapters)
            phase_names = _get_chapters_for_phase("电路分析", circuit_phase) or []
            if phase_names:
                subj_chapters = [(p, ch) for (p, ch) in subj_chapters
                                 if ch.get("chapter_name") in phase_names]
            phase_info["电路分析"] = {
                "phase_key": circuit_phase,
                "phase_name": CIRCUIT_LEARNING_PATH.get(circuit_phase, {}).get("name", ""),
                "phase_focus": CIRCUIT_LEARNING_PATH.get(circuit_phase, {}).get("focus", ""),
            }

        top_chapters = subj_chapters[:5]

        if not top_chapters:
            continue

        remaining = allocated_min
        selected = top_chapters[: min(3, len(top_chapters))]
        per_chapter_base = remaining // max(1, len(selected))

        for priority, ch in selected:
            session_time = min(
                per_chapter_base + 15,
                _suggest_session_time(ch["mastery_level"], ch["importance"], ch["difficulty"]),
            )
            session_time = min(session_time, remaining)
            if session_time < MIN_SESSION_MINUTES:
                continue

            remaining -= session_time
            session_id += 1

            task_desc = _generate_task_for_chapter(subj_name, ch)
            plan_sessions.append({
                "id": session_id,
                "subject_id": subj["id"],
                "subject_name": subj_name,
                "chapter_id": ch["chapter_id"],
                "chapter_name": ch["chapter_name"],
                "time_minutes": session_time,
                "importance": ch["importance"],
                "difficulty": ch["difficulty"],
                "current_mastery": ch["mastery_level"],
                "priority_score": round(priority, 2),
                "task_description": task_desc,
            })

    # 8. 排序（上午: 高数→电路, 下午: 电路/英语）
    plan_sessions.sort(key=lambda s: (
        {"高等数学": 0, "电路分析": 1, "英语": 2}.get(s["subject_name"], 3)
    ))

    # 9. 分配时间段
    time_slots = _assign_time_slots(plan_sessions, daily_hours, day_type)

    plan = {
        "date": today.isoformat(),
        "day_type": day_type,
        "daily_hours": daily_hours,
        "subject_mastery": {
            name: f"{data['avg_mastery']*100:.0f}%"
            for name, data in mastery_by_subject.items()
        },
        "sessions": [],
        "phase_info": phase_info,
    }

    for i, session in enumerate(plan_sessions):
        slot = time_slots[i] if i < len(time_slots) else "自由安排"
        plan["sessions"].append({
            **session,
            "time_slot": slot,
            "current_mastery": f"{session['current_mastery']*100:.0f}%",
        })

    return plan


def _generate_rest_day_plan(today: date) -> dict:
    """生成周日休息计划"""
    return {
        "date": today.isoformat(),
        "day_type": "sunday_rest",
        "daily_hours": 0,
        "subject_mastery": {},
        "sessions": [{
            "id": 0,
            "subject_name": "休息日",
            "chapter_name": "好好休息，恢复精力",
            "time_minutes": 0,
            "task_description": (
                "🌞 周日休息计划：\n"
                "   ├─ 😴 睡到自然醒\n"
                "   ├─ 🏃 适当运动30分钟\n"
                "   ├─ 📖 如果有精力，可轻松回顾本周错题（不超过1小时）\n"
                "   └─ 🎯 为下周做好心理准备"
            ),
            "time_slot": "全天",
        }],
    }


def _generate_paused_plan(today: date) -> dict:
    """生成暂停日计划"""
    return {
        "date": today.isoformat(),
        "day_type": "paused",
        "daily_hours": 0,
        "subject_mastery": {},
        "phase_info": {},
        "sessions": [{
            "id": 0,
            "subject_name": "暂停",
            "chapter_name": "今日学习已暂停",
            "time_minutes": 0,
            "task_description": (
                "⏸️ 今日学习计划已暂停\n\n"
                "   ├─ 😴 好好休息调整状态\n"
                "   ├─ 📖 如果想恢复学习\n"
                "   └─ 使用 /resume 恢复计划\n\n"
                "💡 休息是为了更好地出发，调整好状态再继续！"
            ),
            "time_slot": "全天",
        }],
    }


async def _generate_test_day_plan(user_id: int, today: date) -> dict:
    """生成周六测试日计划"""
    plan = {
        "date": today.isoformat(),
        "day_type": "saturday_test",
        "daily_hours": TEST_DAY_HOURS,
        "subject_mastery": {},
        "sessions": [
            {
                "id": 1,
                "subject_name": "综合测试",
                "chapter_name": "周测试卷",
                "time_minutes": 120,
                "importance": 5,
                "difficulty": 3,
                "current_mastery": "0%",
                "time_slot": "08:00-10:00",
                "task_description": (
                    "📝 周六周测计划：\n"
                    "   ├─ 08:00-10:00 限时做周测试卷（全科）\n"
                    "   ├─ 10:30-11:30 对答案批改\n"
                    "   ├─ 14:00-15:00 错题分析与整理\n"
                    "   └─ 15:30-16:30 薄弱点针对性复习\n\n"
                    "💡 使用 /weekly_test 获取本周试卷"
                ),
            },
        ],
    }
    return plan


def _dynamic_time_alloc(mastery_by_subject: dict, total_minutes: int) -> dict:
    """动态分配各科时间（基于掌握度）"""
    weights = {}
    total_weight = 0.0
    for subj_name, data in mastery_by_subject.items():
        avg_mastery = data["avg_mastery"]
        weight = (1.0 - avg_mastery) * data["total_score"] / 300.0
        if weight < 0.1:
            weight = 0.1
        weights[subj_name] = weight
        total_weight += weight

    allocations = {}
    for subj_name in mastery_by_subject:
        allocations[subj_name] = max(30, int(total_minutes * weights[subj_name] / total_weight))

    return allocations


async def _get_chapter_error_counts(user_id: int) -> dict:
    """获取各章节的未掌握错误题数"""
    try:
        from study_bot.database.schema import get_conn
        conn = await get_conn()
        try:
            cursor = await conn.execute(
                """SELECT chapter_id, COUNT(*) as cnt
                   FROM error_log
                   WHERE user_id = ? AND mastered = 0
                   GROUP BY chapter_id""",
                (user_id,),
            )
            rows = await cursor.fetchall()
            return {r["chapter_id"]: r["cnt"] for r in rows}
        finally:
            await conn.close()
    except Exception:
        return {}


def _generate_task_for_chapter(subject_name: str, chapter: dict) -> str:
    """为章节生成具体的学习任务描述"""
    mastery = chapter.get("mastery_level", 0.0)
    ch_name = chapter.get("chapter_name", "")
    status = chapter.get("status", "")

    # 有考研/四级焦点的，准备附加行
    suffix = ""
    kaoyan = chapter.get("kaoyan_focus", "")
    cet4 = chapter.get("cet4_focus", "")
    if kaoyan:
        suffix = f"\n💡 考研延伸：{kaoyan}"
    if cet4:
        suffix = f"\n🎯 四级关联：{cet4}"

    if status == "learning":
        # 新学内容（考研/专升本一轮）
        desc = (
            f"📖 新学内容 - {ch_name}\n"
            f"   ├─ 观看教学视频/阅读教材\n"
            f"   ├─ 理解核心概念与公式\n"
            f"   └─ 完成基础例题（至少5道）"
        )
    elif status == "foundation":
        # 英语基础阶段（零基础→初中水平）
        desc = (
            f"📖 基础入门 - {ch_name}\n"
            f"   ├─ 从零开始逐步学习\n"
            f"   ├─ 重点理解核心概念\n"
            f"   └─ 每天坚持完成基础练习"
        )
    elif status == "building":
        # 英语提升阶段（初中→高中水平）
        desc = (
            f"🏗️ 能力提升 - {ch_name}\n"
            f"   ├─ 系统学习核心内容\n"
            f"   ├─ 加强练习量（每日精练）\n"
            f"   └─ 每周自我检测一次"
        )
    elif status == "consolidate":
        # 电路基础巩固
        desc = (
            f"🔧 基础巩固 - {ch_name}\n"
            f"   ├─ 快速回顾核心概念与定理\n"
            f"   ├─ 完成强化练习题\n"
            f"   └─ 标记薄弱知识点便于后续重点突破"
        )
    elif status == "strengthen":
        # 电路/数学强化
        desc = (
            f"🎯 强化训练 - {ch_name}\n"
            f"   ├─ 做考研/专升本真题对应题型\n"
            f"   ├─ 限时训练提升解题速度\n"
            f"   └─ 归纳解题技巧与常见陷阱"
        )
    elif status == "practicing":
        # 英语练习阶段
        desc = (
            f"✏️ 专项练习 - {ch_name}\n"
            f"   ├─ 限时完成练习\n"
            f"   ├─ 对答案分析错误原因\n"
            f"   └─ 总结答题技巧"
        )
    elif status == "exam_prep":
        # 英语/综合 考前冲刺
        desc = (
            f"🏁 考前冲刺 - {ch_name}\n"
            f"   ├─ 限时模拟考试\n"
            f"   ├─ 错题分析与归纳\n"
            f"   └─ 针对性补强薄弱题型"
        )
    elif mastery < 0.3:
        desc = (
            f"📖 基础学习 - {ch_name}\n"
            f"   ├─ 精读教材对应章节\n"
            f"   ├─ 整理核心概念笔记\n"
            f"   └─ 完成基础例题"
        )
    elif mastery < 0.6:
        desc = (
            f"✏️ 巩固练习 - {ch_name}\n"
            f"   ├─ 完成章节练习题\n"
            f"   ├─ 归纳解题方法\n"
            f"   └─ 标记疑惑知识点"
        )
    else:
        desc = (
            f"🎯 强化提升 - {ch_name}\n"
            f"   ├─ 做真题对应题型\n"
            f"   ├─ 限时训练\n"
            f"   └─ 整理错题本"
        )

    return desc + suffix


def _assign_time_slots(sessions: list, daily_hours: int, day_type: str = "free_day") -> list:
    """为学习时段分配具体时间"""
    if day_type == "class_day":
        # 上课日：利用课余时间
        slots = ["12:30-14:00", "18:00-19:30", "20:00-21:30"]
    elif daily_hours >= 8:
        slots = ["08:00-09:30", "10:00-11:30", "13:30-15:00", "15:30-17:00", "18:00-19:30", "20:00-21:30"]
    elif daily_hours >= 6:
        slots = ["08:00-10:00", "10:30-11:30", "14:00-15:30", "16:00-17:30", "19:00-20:30"]
    else:
        # 4小时左右 → 默认晚间时段（适合白天有课/上班的用户）
        slots = ["18:30-20:00", "20:00-21:30", "21:30-22:30", "22:30-23:30"]

    while len(slots) < len(sessions):
        slots.append("自由安排")
    return slots[:len(sessions)]


# ============================================================
# 格式化输出
# ============================================================

def format_plan_message(plan: dict, greeting: str = "早上好") -> str:
    """将计划格式化为 Telegram 消息"""
    day_type = plan.get("day_type", "free_day")
    day_emoji = {
        "class_day": "📚 上课日",
        "free_day": "☀️ 空闲日",
        "saturday_test": "📝 测试日",
        "sunday_rest": "🌞 休息日",
        "paused": "⏸️ 已暂停",
    }

    lines = [f"{greeting}！{day_emoji.get(day_type, '☀️')}"]

    # 研究生模式头部
    if plan.get("study_mode") == "graduate":
        try:
            from study_bot.services.graduate_mode import format_graduate_mode_plan_header
            from study_bot.services.graduate_mode import get_graduate_progress
            from study_bot.database.ops import get_user_mode
            import asyncio as _asyncio
            # 使用简化方式避免在同步函数中调用异步
            header = f"\n🎓 研究生模式 | 📚 深度学习计划\n"
            lines[0] += header
        except Exception:
            lines[0] += "\n🎓 研究生模式"
    lines.append("")

    if day_type == "paused":
        for session in plan.get("sessions", []):
            lines.append(session["task_description"])
        return "\n".join(lines)

    if day_type == "sunday_rest":
        for session in plan.get("sessions", []):
            lines.append(session["task_description"])
        lines.append("")
        lines.append("─" * 25)
        lines.append("💡 好的休息是为了更好的学习，下周继续加油！💪")
        return "\n".join(lines)

    if day_type == "saturday_test":
        for session in plan.get("sessions", []):
            lines.append(session["task_description"])
        lines.append("")
        lines.append("─" * 25)
        lines.append("📌 测试完成后用 /log 记录，用 /submit_test 提交答案获取批改")
        return "\n".join(lines)

    lines.append(f"📅 {plan['date']} 学习计划")
    lines.append(f"⏰ 今日学习：{plan['daily_hours']}小时")

    # 显示学习阶段信息
    phase_info = plan.get("phase_info", {})
    if phase_info.get("英语"):
        ep = phase_info["英语"]
        lines.append(f"📈 英语阶段：{ep.get('phase_name', '')}")
    if phase_info.get("电路分析"):
        cp = phase_info["电路分析"]
        focus = cp.get("phase_focus", "")
        lines.append(f"🔌 电路阶段：{cp.get('phase_name', '')}" + (f"（{focus}）" if focus else ""))
    lines.append("")

    # 各科掌握度概览
    lines.append("📊 当前各科掌握度：")
    for subj, pct in plan.get("subject_mastery", {}).items():
        bar = _mini_bar(float(pct.strip("%")) / 100)
        lines.append(f"   {bar} {subj} {pct}")
    lines.append("")
    lines.append("─" * 25)
    lines.append("")

    # 学习任务
    for session in plan.get("sessions", []):
        time_slot = session.get("time_slot", "")
        subj = session["subject_name"]
        ch_name = session["chapter_name"]
        minutes = session["time_minutes"]
        mastery_pct = session.get("current_mastery", "0%")

        emoji = {"电路分析": "🔌", "高等数学": "📘", "英语": "📝"}.get(subj, "📚")

        lines.append(f"⏰ {time_slot} | {emoji} {subj}")
        lines.append(f"├─ {ch_name} ({minutes}分钟)")
        lines.append(f"├─ 当前掌握：{mastery_pct}")
        lines.append(f"{session['task_description']}")
        lines.append("")

    lines.append("─" * 25)
    lines.append("")

    if day_type == "class_day":
        lines.append("💡 上课日时间有限，高效利用课余时间，重点攻克薄弱科目")
    else:
        lines.append("💡 薄弱科目优先安排上午学习，保证精力充沛时攻克难点")

    lines.append("📌 完成后记得用 /log 记录学习内容，用 /summary 查看总结")
    lines.append("📝 遇到不会的题，拍照发给我（/solve）获取详细解析")

    return "\n".join(lines)


def _mini_bar(pct: float, length: int = 5) -> str:
    """5格迷你进度条"""
    filled = int(pct * length)
    return "█" * filled + "░" * (length - filled)


# ============================================================
# 动态调整提醒
# ============================================================

def generate_weekly_schedule_preview(days_ahead: int = 7) -> str:
    """生成未来一周的时间安排预览"""
    today = date.today()
    lines = ["📅 未来一周安排预览", ""]

    day_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

    for i in range(days_ahead):
        d = today + timedelta(days=i)
        dt = get_day_type(d)
        hours = get_daily_hours_for_day(dt)
        name = day_names[d.weekday()]

        emoji_map = {
            "class_day": "📚",
            "free_day": "☀️",
            "saturday_test": "📝",
            "sunday_rest": "🌞",
        }
        type_name = {
            "class_day": "上课日",
            "free_day": "空闲日",
            "saturday_test": "测试日",
            "sunday_rest": "休息日",
        }

        lines.append(
            f"{emoji_map.get(dt, '📚')} {name} {d.strftime('%m/%d')} | "
            f"{type_name.get(dt, dt)} | 学习{hours}h"
        )

    lines.append("")
    lines.append("💡 如需修改某天的安排，使用 /set_schedule 调整")
    return "\n".join(lines)
