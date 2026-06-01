"""
多步骤对话处理器
入门引导 (onboarding)、学习日志 (log)、知识点评估 (assess)
"""

import json
from datetime import date

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ChatAction

from study_bot.database.ops import (
    get_or_create_user,
    get_user,
    update_user,
    get_all_subjects,
    get_chapters_by_subject,
    get_chapter,
    add_study_log,
    save_assessment,
    update_mastery,
    init_user_mastery,
    seed_subjects_and_chapters,
)
from study_bot.services.analyzer import analyze_assessment
from study_bot.utils.helpers import today_str

# ============================================================
# 入门引导状态
# ============================================================
ONBOARD_TARGET, ONBOARD_HOURS, ONBOARD_TIME, ONBOARD_PROGRESS = range(4)

# 用户临时数据 key（存储在 context.user_data 中）
ONBOARD_DATA = "onboard_data"


async def onboard_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """入门引导入口 — ConversationHandler entry point for /start"""
    user = update.effective_user
    await seed_subjects_and_chapters()

    # 初始化错题数据库
    try:
        from study_bot.services.error_tracker import init_error_db
        await init_error_db()
    except Exception:
        pass

    db_user = await get_user(user.id)

    if db_user and db_user.get("onboarding_done"):
        # 老用户：发送欢迎菜单
        from study_bot.utils.helpers import get_morning_greeting, days_until
        greeting = get_morning_greeting()
        days = days_until(db_user.get("exam_date", "2027-03-20"))
        await update.message.reply_text(
            f"{greeting}，{user.first_name or '同学'}！\n\n"
            f"🎓 山西专升本学习助手 v2 已就绪\n"
            f"📅 距考试约 {days} 天\n\n"
            f"📌 常用命令：\n"
            f"   /plan — 今日学习计划\n"
            f"   /log — 记录学习内容\n"
            f"   /summary — 每日总结\n"
            f"   /progress — 进度总览\n"
            f"   /score_line — 分数线预测\n"
            f"   /weekly_test — 获取周测试卷\n"
            f"   /solve — 拍照搜题\n"
            f"   /errors — 错题统计\n"
            f"   /review_errors — 复习错题\n"
            f"   /policy — 政策检查\n"
            f"   /schedule — 未来一周安排\n"
            f"   /set_schedule — 调整日程\n"
            f"   /timeline — 考试时间线\n"
            f"   /help — 完整帮助\n"
        )
        return ConversationHandler.END

    # 新用户：初始化临时数据，发送入门引导
    context.user_data[ONBOARD_DATA] = {}

    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("太原工业学院", callback_data="onboard_target_太原工业学院")],
        [InlineKeyboardButton("太原理工大学", callback_data="onboard_target_太原理工大学")],
        [InlineKeyboardButton("山西大学", callback_data="onboard_target_山西大学")],
        [InlineKeyboardButton("中北大学", callback_data="onboard_target_中北大学")],
        [InlineKeyboardButton("其他（手动输入）", callback_data="onboard_target_other")],
    ])
    await update.message.reply_text(
        "🎓 欢迎来到山西专升本学习助手 v2！\n"
        "我是你的专属AI学习教练，将陪你备考直到考试！\n\n"
        "📋 考试科目：电路分析(150分) + 英语(50分) + 高等数学(100分)\n"
        "📅 考试时间：每年3月中下旬\n"
        "🏫 支持院校：太原工业学院等\n\n"
        "首先：你的目标大学是哪所？",
        reply_markup=keyboard,
    )
    return ONBOARD_TARGET


# ============================================================
# 学习日志状态
# ============================================================
LOG_SELECT_SUBJECT, LOG_SELECT_CHAPTER, LOG_INPUT_TIME, LOG_INPUT_RATING, LOG_INPUT_NOTES = range(10, 15)

LOG_DATA = "log_data"


async def log_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """记录学习入口 — 选择科目"""
    user = update.effective_user
    await seed_subjects_and_chapters()
    await get_or_create_user(user.id, user.username, user.first_name)

    subjects = await get_all_subjects()
    context.user_data[LOG_DATA] = {}

    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = []
    emoji_map = {"电路分析": "🔌", "英语": "📝", "高等数学": "📘"}
    for subj in subjects:
        emoji = emoji_map.get(subj["name"], "📚")
        keyboard.append([
            InlineKeyboardButton(
                f"{emoji} {subj['name']}",
                callback_data=f"log_subject_{subj['id']}_{subj['name']}",
            )
        ])
    keyboard.append([InlineKeyboardButton("❌ 取消", callback_data="log_cancel")])

    await update.message.reply_text(
        "📝 记录学习 — 第1步\n\n请选择你学习的科目：",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return LOG_SELECT_SUBJECT


# ============================================================
# 知识点评估状态
# ============================================================
ASSESS_SUBJECT, ASSESS_CHAPTER, ASSESS_SCORE = range(20, 23)

ASSESS_DATA = "assess_data"


async def assess_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """评估入口 — 选择科目"""
    user = update.effective_user
    await seed_subjects_and_chapters()
    await get_or_create_user(user.id, user.username, user.first_name)

    subjects = await get_all_subjects()
    context.user_data[ASSESS_DATA] = {
        "chapters_to_assess": [],
        "current_index": 0,
        "scores": {},
    }

    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    emoji_map = {"电路分析": "🔌", "英语": "📝", "高等数学": "📘"}
    keyboard = []
    for subj in subjects:
        emoji = emoji_map.get(subj["name"], "📚")
        keyboard.append([
            InlineKeyboardButton(
                f"{emoji} {subj['name']}",
                callback_data=f"assess_subject_{subj['id']}_{subj['name']}",
            )
        ])
    keyboard.append([InlineKeyboardButton("❌ 取消", callback_data="assess_cancel")])

    await update.message.reply_text(
        "📋 知识点自评\n\n请选择要评估的科目：\n（建议每周评估一次，了解自己的薄弱点）",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return ASSESS_SUBJECT


# ============================================================
# 考试反馈状态（多轮测试→反馈→调整）
# ============================================================
TESTFB_SUBJECT, TESTFB_SCORE, TESTFB_WRONG, TESTFB_CONFIRM = range(30, 34)

TESTFB_DATA = "testfb_data"


async def testfb_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """考试反馈入口 — 选择刚考完的科目"""
    user = update.effective_user
    await seed_subjects_and_chapters()
    await get_or_create_user(user.id, user.username, user.first_name)

    context.user_data[TESTFB_DATA] = {
        "completed_subjects": [],
        "results": [],
    }

    subjects = await get_all_subjects()
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    emoji_map = {"电路分析": "🔌", "英语": "📝", "高等数学": "📘"}
    keyboard = []
    for subj in subjects:
        emoji = emoji_map.get(subj["name"], "📚")
        keyboard.append([
            InlineKeyboardButton(
                f"{emoji} {subj['name']}",
                callback_data=f"testfb_{subj['id']}_{subj['name']}",
            )
        ])
    keyboard.append([InlineKeyboardButton("✅ 全部考完，生成计划", callback_data="testfb_done")])

    await update.message.reply_text(
        "📝 考试反馈 — 第1步\n\n"
        "请选择你刚完成测试的科目：\n"
        "（可以多次反馈，我会记录每个科目的成绩）\n\n"
        "💡 建议：完成一科测试就反馈一科\n"
        "   反馈完所有科目后点击「全部考完」",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return TESTFB_SUBJECT


# ============================================================
# 诊断性多轮测试状态（至少5轮，每轮出题→做题→反馈→调整）
# ============================================================
DIAG_CONFIRM, DIAG_FEEDBACK, DIAG_WRONG, DIAG_NEXT = range(40, 44)

DIAG_DATA = "diag_data"
DEFAULT_DIAG_ROUNDS = 5

# 默认5轮科目安排（超过5轮则循环扩展）
_BASE_DIAG_PLAN = [
    {"subject": "高等数学", "desc": "数学基础诊断（山西专升本考纲）"},
    {"subject": "电路分析", "desc": "电路基础诊断（山西专升本考纲）"},
    {"subject": "英语", "desc": "英语基础诊断（山西专升本考纲）"},
    {"subject": "高等数学", "desc": "数学深入诊断（侧重薄弱考点）"},
    {"subject": "电路分析", "desc": "电路深入诊断（侧重薄弱考点）"},
    {"subject": "英语", "desc": "英语深入诊断（侧重薄弱考点）"},
    {"subject": "高等数学", "desc": "数学综合诊断"},
    {"subject": "电路分析", "desc": "电路综合诊断"},
    {"subject": "英语", "desc": "英语综合诊断"},
    {"subject": "高等数学", "desc": "数学拔高诊断"},
]


def _build_round_plan(total_rounds: int) -> list:
    """根据总轮数生成科目安排"""
    plan = []
    for i in range(total_rounds):
        tmpl = _BASE_DIAG_PLAN[i % len(_BASE_DIAG_PLAN)]
        plan.append({"round": i + 1, "subject": tmpl["subject"], "desc": tmpl["desc"]})
    return plan


async def diag_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """诊断测试入口 — 说明流程，开始第1轮"""
    user = update.effective_user
    await seed_subjects_and_chapters()
    await get_or_create_user(user.id, user.username, user.first_name)

    # 从 user_data 读取自定义轮数（如果有的话）
    custom_rounds = context.user_data.get("diag_rounds", DEFAULT_DIAG_ROUNDS)
    round_plan = _build_round_plan(custom_rounds)

    context.user_data[DIAG_DATA] = {
        "round": 0,
        "total_rounds": custom_rounds,
        "round_plan": round_plan,
        "results": [],
        "weak_chapters_all": {},
    }

    from telegram import InlineKeyboardMarkup, InlineKeyboardButton

    # 生成轮次预览
    preview = []
    for rp in round_plan[:8]:
        preview.append(f"  第{rp['round']}轮 — {rp['subject']}（{rp['desc']}）")
    if len(round_plan) > 8:
        preview.append(f"  ... 共{len(round_plan)}轮")
    preview_text = "\n".join(preview)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 开始第1轮测试", callback_data="diag_start")],
        [
            InlineKeyboardButton("5轮", callback_data="diag_setrounds_5"),
            InlineKeyboardButton("7轮", callback_data="diag_setrounds_7"),
            InlineKeyboardButton("10轮", callback_data="diag_setrounds_10"),
        ],
        [InlineKeyboardButton("❌ 取消", callback_data="diag_cancel")],
    ])

    await update.message.reply_text(
        f"🔬 诊断性多轮测试系统\n\n"
        f"我将为你进行 **{custom_rounds}轮** 诊断测试：\n\n"
        f"📋 测试安排（全部按山西专升本考纲）：\n"
        f"{preview_text}\n\n"
        f"每轮流程：我出题（PDF）→ 你做 → 反馈分数和错题 → 下一轮\n\n"
        f"⚙️ 控制指令：\n"
        f"  /diag_rounds N — 设置考试轮数\n"
        f"  /stop_diag — 停止考试，立即生成计划\n"
        f"  /start_plan — 用现有数据生成计划\n\n"
        f"🎯 {custom_rounds}轮完成后，根据真实水平生成学习计划\n"
        f"   也可随时 /stop_diag 提前结束",
        reply_markup=keyboard,
    )
    return DIAG_CONFIRM


async def stop_diag_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """停止诊断测试，立即生成计划"""
    diag = context.user_data.get(DIAG_DATA)
    if not diag or not diag.get("results"):
        await update.message.reply_text("⚠️ 没有正在进行的诊断测试，或还没有完成任何一轮。\n使用 /diagnostic 开始测试。")
        return

    from study_bot.handlers.callbacks import _diag_finish_all
    await update.message.reply_text("⏳ 正在根据已有数据生成计划...")
    return await _diag_finish_all(update.message, diag, update, context)


async def start_plan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """提前结束诊断，用现有数据生成计划"""
    return await stop_diag_command(update, context)


async def diag_rounds_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """设置诊断测试轮数并直接开始"""
    user = update.effective_user
    text = update.message.text.strip()
    import re
    nums = re.findall(r'\d+', text)
    if nums:
        rounds = max(3, min(20, int(nums[0])))
        context.user_data["diag_rounds"] = rounds
        await update.message.reply_text(
            f"✅ 诊断测试轮数已设置为 {rounds} 轮\n"
            f"正在启动诊断测试..."
        )
        return await diag_entry(update, context)
    else:
        await update.message.reply_text(
            "⚠️ 请指定轮数，例如：/diag_rounds 7\n"
            "（最少3轮，最多20轮）"
        )
