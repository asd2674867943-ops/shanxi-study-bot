"""
命令处理器 v2
支持：学习计划、周测、拍照搜题、错题管理、政策监控、分数线追踪
"""

import json
from datetime import date, datetime

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatAction

from study_bot.database.ops import (
    get_or_create_user,
    get_user,
    get_all_subjects,
    get_chapters_by_subject,
    get_user_mastery,
    get_daily_logs,
    get_study_plan,
    get_streak,
    get_total_study_hours,
    get_weekly_logs,
    update_streak,
    update_user,
    seed_subjects_and_chapters,
    save_study_plan,
    save_test_record,
    get_test_history,
    pause_plan,
    resume_plan,
    is_plan_paused,
    update_mastery,
)
from study_bot.database.schema import get_conn
from study_bot.services.plan_generator import (
    generate_daily_plan,
    format_plan_message,
    generate_weekly_schedule_preview,
    get_day_type,
    get_daily_hours_for_day,
)
from study_bot.services.assessment import get_progress_summary, format_progress_message
from study_bot.services.analyzer import analyze_daily_summary
from study_bot.services.score_predictor import (
    predict_score_line,
    calc_target_progress,
    format_score_prediction,
    format_progress_tracker,
    decompose_target_score,
)
from study_bot.services.test_generator import (
    create_weekly_test,
    format_test_for_telegram,
    format_answer_for_telegram,
    generate_pdf_test,
)
from study_bot.services.policy_monitor import check_policy_updates, format_policy_check, format_exam_timeline
from study_bot.services.error_tracker import (
    init_error_db,
    add_error,
    get_errors,
    get_errors_due_for_review,
    get_error_stats,
    mark_error_reviewed,
    format_error_stats,
    format_error_for_review,
)
from study_bot.services.photo_solver import process_photo_question, process_answer_photo, format_solution_for_telegram
from study_bot.utils.helpers import today_str, get_morning_greeting, days_until


# ============================================================
# /start — 欢迎与入门引导
# ============================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """启动命令"""
    user = update.effective_user
    await seed_subjects_and_chapters()
    await init_error_db()
    db_user = await get_user(user.id)

    if db_user and db_user.get("onboarding_done"):
        greeting = get_morning_greeting()
        days = days_until(db_user.get("exam_date", "2027-03-20"))
        await update.message.reply_text(
            f"{greeting}，{user.first_name or '同学'}！👋\n\n"
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
    else:
        await update.message.reply_text(
            "🎓 欢迎来到山西专升本学习助手 v2！\n"
            "我是你的专属AI学习教练，将陪你备考直到考试！\n\n"
            "📋 考试科目：电路分析(150分) + 英语(50分) + 高等数学(100分)\n"
            "📅 考试时间：每年3月中下旬\n"
            "🏫 支持院校：太原工业学院等\n\n"
            "让我们先做个简单设置～\n"
            "首先：你的目标大学是哪所？",
            reply_markup=_onboard_target_keyboard(),
        )


def _onboard_target_keyboard():
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("太原工业学院 🎯", callback_data="onboard_target_太原工业学院")],
        [InlineKeyboardButton("太原理工大学 🏆", callback_data="onboard_target_太原理工大学")],
        [InlineKeyboardButton("山西大学", callback_data="onboard_target_山西大学")],
        [InlineKeyboardButton("中北大学", callback_data="onboard_target_中北大学")],
        [InlineKeyboardButton("其他（手动输入）", callback_data="onboard_target_other")],
    ])


# ============================================================
# /plan — 查看/生成今日学习计划
# ============================================================

async def plan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查看今日学习计划"""
    user = update.effective_user
    await seed_subjects_and_chapters()
    db_user = await get_or_create_user(user.id, user.username, user.first_name)

    await update.message.chat.send_action(ChatAction.TYPING)

    # 检查已有计划（如果暂停了，不返回缓存计划，重新生成以显示暂停状态）
    existing = await get_study_plan(user.id, today_str())
    if existing and not await is_plan_paused(user.id):
        greeting = get_morning_greeting()
        message = format_plan_message(existing["plan"], greeting)
        days = days_until(db_user["exam_date"])
        message += f"\n\n🎯 距考试还有 {days} 天，加油！"
        await update.message.reply_text(message)
        return

    # 生成新计划
    plan = await generate_daily_plan(user.id, db_user["daily_hours"])
    greeting = get_morning_greeting()
    message = format_plan_message(plan, greeting)

    await save_study_plan(user.id, today_str(), plan)

    days = days_until(db_user["exam_date"])
    message += f"\n\n🎯 距考试还有 {days} 天，加油！"

    await update.message.reply_text(message)


# ============================================================
# /score_line — 分数线预测与目标进度
# ============================================================

async def score_line_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查看分数线预测和目标进度"""
    user = update.effective_user
    db_user = await get_or_create_user(user.id, user.username, user.first_name)

    await update.message.chat.send_action(ChatAction.TYPING)

    # 预测分数线
    prediction = predict_score_line(2026)
    pred_msg = format_score_prediction(prediction, db_user.get("target_univ", "太原工业学院"))

    # 进度追踪
    summary = await get_progress_summary(user.id)
    progress = calc_target_progress(
        current_estimated_score=summary["total_estimated"],
        target_score=prediction["predicted"] + 10,  # 预测线+10分安全边际
        days_until_exam=days_until(db_user["exam_date"]),
        total_study_hours=summary["total_hours"],
    )
    progress_msg = format_progress_tracker(progress, db_user.get("target_univ", "太原工业学院"))

    # 各科分解
    subject_mastery = {}
    for s in summary["subjects"]:
        subject_mastery[s["subject_name"]] = s.get("effective_mastery", s["avg_mastery"])
    decompose = decompose_target_score(progress["target_score"], subject_mastery)

    decompose_lines = ["📊 各科目标分解", ""]
    for d in decompose:
        decompose_lines.append(
            f"{d['subject']}：{d['current_score']:.0f} → {d['target_score']:.0f}/{d['max_score']}分 "
            f"（差{d['gap']:.0f}分）"
        )
    decompose_lines.append("")

    full_msg = pred_msg + "\n\n" + progress_msg + "\n\n" + "\n".join(decompose_lines)
    await update.message.reply_text(full_msg)


# ============================================================
# /weekly_test — 获取周测试卷
# ============================================================

async def weekly_test_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """获取周测试卷"""
    user = update.effective_user
    await get_or_create_user(user.id, user.username, user.first_name)

    from telegram import InlineKeyboardMarkup, InlineKeyboardButton

    # 获取当前选择的难度（默认basic）
    current_diff = context.user_data.get("test_difficulty", "basic")
    from study_bot.config import DIFFICULTY_LEVELS

    keyboard = [
        # 难度选择行
        [
            InlineKeyboardButton(
                f"{'✅ ' if current_diff == 'basic' else ''}🟢 专升本基础",
                callback_data="difficulty_basic"
            ),
            InlineKeyboardButton(
                f"{'✅ ' if current_diff == 'advanced' else ''}🟡 专升本进阶",
                callback_data="difficulty_advanced"
            ),
        ],
        [
            InlineKeyboardButton(
                f"{'✅ ' if current_diff == 'grad_intro' else ''}🟠 研究生入门",
                callback_data="difficulty_grad_intro"
            ),
            InlineKeyboardButton(
                f"{'✅ ' if current_diff == 'grad_advanced' else ''}🔴 研究生进阶",
                callback_data="difficulty_grad_advanced"
            ),
        ],
        # 分隔行 — 科目选择
        [
            InlineKeyboardButton("📘 高等数学", callback_data="weeklytest_高等数学"),
            InlineKeyboardButton("🔌 电路分析", callback_data="weeklytest_电路分析"),
        ],
        [
            InlineKeyboardButton("📝 英语", callback_data="weeklytest_英语"),
            InlineKeyboardButton("📋 全科测试", callback_data="weeklytest_all"),
        ],
    ]

    diff_label = DIFFICULTY_LEVELS.get(current_diff, {}).get("label", "专升本基础")
    await update.message.reply_text(
        f"📝 周测试卷生成\n\n当前难度：{diff_label}\n请选择难度和科目：",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def weekly_test_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """周测选择回调"""
    query = update.callback_query
    await query.answer()
    data = query.data.replace("weeklytest_", "")

    user = update.effective_user
    await query.edit_message_text("⏳ 正在生成试卷...")

    import os

    if data == "all":
        subjects = ["高等数学", "电路分析", "英语"]
        for subj in subjects:
            result = await create_weekly_test(user.id, subj)
            if "error" in result:
                await query.message.reply_text(f"⚠️ {subj} 试卷生成失败：{result['error']}")
                continue

            # 生成 PDF
            pdf_path = await generate_pdf_test(user.id, subj, result)
            if pdf_path and os.path.exists(pdf_path) and pdf_path.endswith('.pdf'):
                with open(pdf_path, 'rb') as f:
                    await query.message.reply_document(
                        document=f,
                        filename=os.path.basename(pdf_path),
                        caption=f"📝 {subj} 周测试卷\n📅 {result['date']} | 难度：{result.get('difficulty', 'medium')}",
                    )
            else:
                test_msg = format_test_for_telegram(result)
                await query.message.reply_text(test_msg[:4000])

            # 保存测试记录
            subjects_list = await get_all_subjects()
            for s in subjects_list:
                if s["name"] == subj:
                    await save_test_record(user.id, s["id"], today_str(), 0, 100,
                                           result.get("test_text", ""))
                    break

        await query.edit_message_text(
            "✅ 全科测试卷已生成！PDF 文件已发送。\n\n"
            "📌 做完后回复「错了 题号」来记录错题，我会自动调整你的学习计划\n"
            "   例如：错了 1,3,5"
        )
    else:
        result = await create_weekly_test(user.id, data)
        if "error" in result:
            await query.edit_message_text(f"❌ {result['error']}")
            return

        # 生成 PDF
        pdf_path = await generate_pdf_test(user.id, data, result)
        if pdf_path and os.path.exists(pdf_path) and pdf_path.endswith('.pdf'):
            with open(pdf_path, 'rb') as f:
                await query.message.reply_document(
                    document=f,
                    filename=os.path.basename(pdf_path),
                    caption=f"📝 {data} 周测试卷（PDF版）\n📅 {result['date']}",
                )
            await query.edit_message_text(
                f"✅ {data} 试卷已生成！PDF文件已发送。\n\n"
                "📌 做完后回复「错了 题号」来记录错题，我会自动调整你的学习计划\n"
                "   例如：错了 1,3,5"
            )
        else:
            test_msg = format_test_for_telegram(result)
            await query.edit_message_text(test_msg[:4000])
            answer_msg = format_answer_for_telegram(result)
            await query.message.reply_text(answer_msg[:4000])

        # 保存测试记录
        subjects_list = await get_all_subjects()
        for s in subjects_list:
            if s["name"] == data:
                await save_test_record(user.id, s["id"], today_str(), 0, 100,
                                       result.get("test_text", ""))
                break


# ============================================================
# /solve — 拍照搜题（处理照片消息）
# ============================================================

async def solve_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """拍照搜题入口"""
    await update.message.reply_text(
        "📷 拍照搜题\n\n"
        "使用方法：\n"
        "1. 直接发送题目照片给我\n"
        "2. 可以附文字说明「这是电路题 / 数学题 / 英语题」\n"
        "3. 我会识别题目并给出：\n"
        "   ✏️ 详细解题步骤\n"
        "   📌 知识点总结\n"
        "   🔗 相关考点链接\n"
        "   ⚠️ 易错提醒\n\n"
        "📸 现在就把不会的题拍照发过来吧！"
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理用户发送的照片（拍照搜题/提交答案）"""
    user = update.effective_user
    await update.message.chat.send_action(ChatAction.TYPING)

    # 获取最大的照片
    photo_file = await update.message.photo[-1].get_file()
    photo_bytes = await photo_file.download_as_bytearray()

    caption = update.message.caption or ""

    # 判断是搜题还是提交测试答案
    if "答案" in caption or "批改" in caption or "提交" in caption:
        await update.message.reply_text("⏳ 正在批改你的作答...")
        # 尝试获取最近的测试
        result = await process_answer_photo(
            user_id=user.id,
            subject_name="综合",
            test_questions="（请参考最近生成的周测试卷）",
            image_data=bytes(photo_bytes),
        )
        if result.get("success"):
            await update.message.reply_text(result["grading_result"][:4000])
        else:
            await update.message.reply_text(result.get("message", "批改失败，请重试"))
    else:
        await update.message.reply_text("⏳ 正在识别题目并解题...")
        result = await process_photo_question(
            user_id=user.id,
            image_data=bytes(photo_bytes),
            subject_hint=caption[:50],
            user_notes=caption,
        )
        solution_msg = format_solution_for_telegram(result)
        await update.message.reply_text(solution_msg[:4000])


# ============================================================
# /errors — 错题统计
# ============================================================

async def errors_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查看错题统计"""
    user = update.effective_user
    await init_error_db()
    stats = await get_error_stats(user.id)
    message = format_error_stats(stats)
    await update.message.reply_text(message)


# ============================================================
# /review_errors — 复习错题
# ============================================================

async def review_errors_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """复习错题"""
    user = update.effective_user
    await init_error_db()

    # 获取待复习错题
    errors = await get_errors_due_for_review(user.id, limit=3)

    if not errors:
        await update.message.reply_text(
            "🎉 暂无需要复习的错题！\n\n"
            "💡 做周测试卷或练习后，如果做错了，记得拍照发给我保存到错题本哦～"
        )
        return

    await update.message.reply_text(f"📝 以下是 {len(errors)} 道待复习错题，请逐一攻克：")

    for i, error in enumerate(errors):
        msg = format_error_for_review(error, i + 1, show_answer=False)
        await update.message.reply_text(msg[:4000])

        # 存储当前复习状态
        context.user_data[f"reviewing_error_{i}"] = error["id"]

    await update.message.reply_text(
        "📌 复习完后，请回复：\n"
        "   「会了 {题号}」— 标记该题已掌握\n"
        "   「不会 {题号}」— 下次继续复习\n\n"
        "例如：「会了 1」或「不会 2」"
    )


# ============================================================
# /policy — 政策检查
# ============================================================

async def policy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """检查山西专升本政策更新"""
    await update.message.chat.send_action(ChatAction.TYPING)
    await update.message.reply_text("⏳ 正在检查山西专升本最新政策...")

    result = await check_policy_updates()
    message = format_policy_check(result)
    await update.message.reply_text(message)


# ============================================================
# /timeline — 考试时间线
# ============================================================

async def timeline_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """显示考试时间线"""
    message = format_exam_timeline()
    await update.message.reply_text(message)


# ============================================================
# /schedule — 未来一周安排
# ============================================================

async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查看未来一周安排"""
    message = generate_weekly_schedule_preview(7)
    await update.message.reply_text(message)


# ============================================================
# /set_schedule — 调整日程（告知上课日/假期）
# ============================================================

async def set_schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """设置日程类型"""
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = [
        [
            InlineKeyboardButton("📚 今天是上课日", callback_data="setschedule_class"),
            InlineKeyboardButton("☀️ 今天是空闲日", callback_data="setschedule_free"),
        ],
        [
            InlineKeyboardButton("🏖️ 今天放假", callback_data="setschedule_holiday"),
            InlineKeyboardButton("🎓 即将开学", callback_data="setschedule_school"),
        ],
        [InlineKeyboardButton("📝 调整考试日期", callback_data="setschedule_examdate")],
    ]

    await update.message.reply_text(
        "⚙️ 调整日程设置\n\n"
        "请选择你今天的状态：",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def set_schedule_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """日程设置回调"""
    query = update.callback_query
    await query.answer()
    data = query.data.replace("setschedule_", "")

    user = update.effective_user

    if data == "class":
        await query.edit_message_text(
            "📚 已设置为上课日\n"
            "今天最低学习3小时，主要利用课余时间。\n\n"
            "💡 晚上是黄金学习时间，建议用来攻克薄弱科目。"
        )
    elif data == "free":
        await query.edit_message_text(
            "☀️ 已设置为空闲日\n"
            "今天有6+小时学习时间，加油！\n\n"
            "💡 查看最新计划请使用 /plan"
        )
    elif data == "holiday":
        await query.edit_message_text(
            "🏖️ 放假模式已记录\n"
            "假期有大把时间学习，建议每天保持6-8小时。\n"
            "我会调整计划，增加每日任务量。\n\n"
            "💡 假期是弯道超车的好时机，制定好计划严格执行！"
        )
    elif data == "school":
        await query.edit_message_text(
            "🎓 开学模式已记录\n"
            "上课日至少保证3小时学习，周末加量。\n"
            "我会相应调整每日计划。\n\n"
            "💡 每天用 /plan 查看当天计划，晚上用 /summary 回顾"
        )


# ============================================================
# /summary — 每日总结
# ============================================================

async def summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查看今日学习总结"""
    user = update.effective_user
    db_user = await get_or_create_user(user.id, user.username, user.first_name)

    await update.message.chat.send_action(ChatAction.TYPING)

    logs = await get_daily_logs(user.id, today_str())

    if not logs:
        await update.message.reply_text(
            "📋 今天还没有学习记录哦～\n\n"
            "用 /log 记录你的学习内容，\n"
            "或者现在就去学习，回来再总结！💪"
        )
        return

    # 获取掌握度变化
    mastery_changes = []
    for log in logs:
        mastery_data = await get_user_mastery(user.id, log["subject_id"])
        for m in mastery_data:
            if m["chapter_id"] == log["chapter_id"]:
                old_mastery = m["mastery_level"]
                rating = log["self_rating"] or 3
                improvement = {1: -0.02, 2: 0, 3: 0.02, 4: 0.05, 5: 0.10}.get(rating, 0.02)
                new_mastery = min(1.0, old_mastery + improvement)
                mastery_changes.append({
                    "chapter_name": log["chapter_name"],
                    "old_mastery": f"{old_mastery*100:.0f}",
                    "new_mastery": f"{new_mastery*100:.0f}",
                })
                break

    plan_data = await get_study_plan(user.id, today_str())

    logs_for_ai = [
        {
            "subject_name": log["subject_name"],
            "chapter_name": log["chapter_name"],
            "time_spent_min": log["time_spent_min"] or 0,
            "self_rating": log["self_rating"] or 0,
            "chapter_id": log["chapter_id"],
        }
        for log in logs
    ]

    feedback = await analyze_daily_summary(logs_for_ai, plan_data, mastery_changes)

    total_minutes = sum(log["time_spent_min"] or 0 for log in logs)
    subjects_set = set(log["subject_name"] for log in logs)
    avg_rating = sum(log["self_rating"] or 0 for log in logs) / len(logs) if logs else 0

    header = (
        f"📊 {today_str()} 学习总结\n\n"
        f"⏰ 今日学习：{total_minutes // 60}小时{total_minutes % 60}分钟\n"
        f"📚 覆盖科目：{'、'.join(subjects_set)}\n"
        f"⭐ 平均自评：{avg_rating:.1f}/5\n"
        f"📝 记录条数：{len(logs)}条\n\n"
    )

    message = header + feedback
    await update.message.reply_text(message)


# ============================================================
# /progress — 进度总览
# ============================================================

async def progress_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查看学习进度总览"""
    user = update.effective_user
    db_user = await get_or_create_user(user.id, user.username, user.first_name)

    await update.message.chat.send_action(ChatAction.TYPING)

    summary = await get_progress_summary(user.id)
    message = format_progress_message(summary, db_user["exam_date"])

    await update.message.reply_text(message)


# ============================================================
# /help — 完整帮助
# ============================================================

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """完整帮助命令"""
    help_text = (
        "🎓 <b>山西专升本学习助手 v3 — 完整帮助</b>\n\n"
        "<b>📌 每日学习：</b>\n"
        "  /plan — 查看/生成今日学习计划\n"
        "  /log — 记录学习内容\n"
        "  /summary — 每日总结 + AI 建议\n"
        "  /schedule — 未来一周安排\n"
        "  /set_schedule — 调整日程（上课/放假等）\n\n"
        "<b>📊 进度与目标：</b>\n"
        "  /progress — 学习进度总览\n"
        "  /score_line — 分数线预测 + 目标进度条\n"
        "  /assess — 知识点自评\n\n"
        "<b>🎓 研究生模式：</b>\n"
        "  /graduate — 研究生难度学习模式开关\n"
        "  含资格评估、进度追踪、深化专升本测试\n\n"
        "<b>📝 周测系统：</b>\n"
        "  /weekly_test — 获取周测试卷（含难度选择+PDF）\n"
        "  /submit_test — 提交错题反馈\n"
        "  做完回复「错了 1,3,5」→ 自动调整计划\n"
        "  也可直接发送「XXX知识点不会」→ 专项出题\n\n"
        "<b>📷 拍照搜题：</b>\n"
        "  /solve — 拍照搜题说明\n"
        "  直接发题目照片 → AI 详细解题\n\n"
        "<b>📋 错题管理：</b>\n"
        "  /errors — 错题统计\n"
        "  /review_errors — 复习错题\n\n"
        "<b>🔔 政策与信息：</b>\n"
        "  /policy — 检查山西专升本政策更新\n"
        "  /timeline — 考试时间线\n"
        "  /taiyuan_info — 太原工业学院专升本信息\n\n"
        "<b>⏯️ 学习控制：</b>\n"
        "  /pause — 暂停今日学习计划\n"
        "  /resume — 恢复学习计划\n\n"
        "<b>⚙️ 其他：</b>\n"
        "  /help — 本帮助\n"
        "  /cancel — 取消当前操作\n\n"
        "<b>⏰ 自动功能：</b>\n"
        "  🕖 每天07:00 → 推送学习计划\n"
        "  🕤 每天21:30 → 提醒学习总结\n"
        "  📅 周六07:30 → 自动生成PDF试卷\n"
        "  📋 每日 → 错题复习提醒\n\n"
        "<i>山西专升本 · 电气工程及其自动化</i>\n"
        "<i>电路分析 | 英语 | 高等数学</i>"
    )

    await update.message.reply_text(help_text, parse_mode="HTML")


# ============================================================
# /cancel — 取消当前操作
# ============================================================

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """取消当前操作"""
    await update.message.reply_text("✅ 已取消当前操作。有什么需要可以随时找我！")


# ============================================================
# /log — 记录学习（快捷方式，实际由 ConversationHandler 接管）
# ============================================================

async def log_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """记录学习 — 快捷说明"""
    await update.message.reply_text(
        "📝 记录今天的学习内容\n\n"
        "使用 /log 开始交互式记录：\n"
        "依次选择：科目 → 章节 → 时长 → 自评"
    )


# ============================================================
# 文本消息处理（识别"会了/不会"等错题复习回复）
# ============================================================

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理非命令文本消息"""
    text = update.message.text.strip()

    # 识别错题复习回复
    if "会了" in text or "掌握了" in text:
        try:
            # 提取题号
            import re
            nums = re.findall(r'\d+', text)
            if nums:
                error_id = context.user_data.get(f"reviewing_error_{int(nums[0]) - 1}")
                if error_id:
                    await mark_error_reviewed(error_id, mastered=True)
                    await update.message.reply_text(
                        f"✅ 第{nums[0]}题已标记为掌握！\n"
                        f"继续保持，攻克下一题！💪"
                    )
                    return
        except Exception:
            pass

    if "不会" in text or "没懂" in text:
        try:
            import re
            nums = re.findall(r'\d+', text)
            if nums:
                error_id = context.user_data.get(f"reviewing_error_{int(nums[0]) - 1}")
                if error_id:
                    await mark_error_reviewed(error_id, mastered=False)
                    await update.message.reply_text(
                        f"📝 第{nums[0]}题已标记为「需要继续复习」\n"
                        f"下次复习时会再次出现。\n"
                        f"💡 建议先看解析，再做类似题目巩固。"
                    )
                    return
        except Exception:
            pass


# ============================================================
# 错题反馈处理（"错了 1,3,5"）
# ============================================================

async def handle_test_error_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理用户反馈的错题题号，记录错题并调整学习计划"""
    import re
    text = update.message.text.strip()
    user = update.effective_user

    nums = re.findall(r'\d+', text)
    if not nums:
        await update.message.reply_text("⚠️ 请提供错题题号，例如：错了 1,3,5")
        return

    from study_bot.database.ops import get_test_history
    tests = await get_test_history(user.id, limit=3)
    if not tests:
        await update.message.reply_text("⚠️ 没有找到最近的测试记录，请先使用 /weekly_test 生成试卷")
        return

    latest_test = tests[0]
    test_content = latest_test.get("test_content", "")
    subject_id = latest_test.get("subject_id", 0)
    subject_name = latest_test.get("subject_name", "未知科目")

    error_details = []
    for num_str in nums[:10]:
        q_num = int(num_str)
        ch_name = _find_chapter_for_question(test_content, q_num)
        error_details.append((q_num, ch_name))

    if not error_details:
        await update.message.reply_text("⚠️ 未能从试卷中匹配到错题信息，请检查题号是否正确")
        return

    recorded_count = 0
    weak_chapters = set()
    for q_num, ch_name in error_details:
        chapter_id = None
        if ch_name:
            subjects_list = await get_all_subjects()
            for s in subjects_list:
                chapters = await get_chapters_by_subject(s["id"])
                for ch in chapters:
                    if ch_name in ch["name"] or ch["name"] in ch_name:
                        chapter_id = ch["id"]
                        subject_id = s["id"]
                        subject_name = s["name"]
                        break
                if chapter_id:
                    break

        if chapter_id:
            await add_error(
                user.id, subject_id, chapter_id,
                question=f"周测第{q_num}题",
                wrong_answer="用户反馈错误",
                knowledge_point=ch_name,
            )
            mastery_list = await get_user_mastery(user.id, subject_id)
            current = 0.0
            for m in mastery_list:
                if m["chapter_id"] == chapter_id:
                    current = m["mastery_level"]
                    break
            new_mastery = max(0.0, current - 0.08)
            await update_mastery(user.id, chapter_id, new_mastery)
            weak_chapters.add(ch_name)
            recorded_count += 1

    db_user = await get_user(user.id)
    plan = await generate_daily_plan(user.id, db_user.get("daily_hours", 4))
    await save_study_plan(user.id, today_str(), plan)

    weak_str = "、".join(weak_chapters) if weak_chapters else "相关章节"
    await update.message.reply_text(
        f"✅ 已记录 {recorded_count} 道错题\n\n"
        f"📉 薄弱章节掌握度已下调\n"
        f"🔍 薄弱点：{weak_str}\n"
        f"📋 学习计划已自动更新！\n\n"
        f"💡 使用 /plan 查看调整后的计划\n"
        f"📝 使用 /review_errors 复习错题"
    )


def _find_chapter_for_question(test_content: str, q_num: int) -> str:
    """在试卷内容中查找题号对应的章节名称"""
    import re
    if not test_content:
        return ""
    lines = test_content.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(f"{q_num}.") or stripped.startswith(f"{q_num}、") or stripped.startswith(f"{q_num} "):
            for j in range(i, min(i + 20, len(lines))):
                if "考察知识点" in lines[j] or "📚" in lines[j]:
                    match = re.search(r"考察知识点[：:]\s*(.+?)(?:\s*[-—]\s*(.+))?$", lines[j])
                    if match:
                        return match.group(1).strip()
                    parts = lines[j].split("：")
                    if len(parts) > 1:
                        return parts[-1].strip()
                    parts = lines[j].split(":")
                    if len(parts) > 1:
                        return parts[-1].strip()
            break
    return ""


# ============================================================
# /pause — 暂停今日学习
# ============================================================

async def pause_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """暂停今日学习计划"""
    user = update.effective_user
    await get_or_create_user(user.id, user.username, user.first_name)
    await pause_plan(user.id)
    await update.message.reply_text(
        "⏸️ 今日学习计划已暂停\n\n"
        "休息调整好状态再继续\n"
        "使用 /resume 恢复学习计划\n"
        "使用 /plan 查看当前状态"
    )


# ============================================================
# /resume — 恢复学习
# ============================================================

async def resume_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """恢复学习计划"""
    user = update.effective_user
    await get_or_create_user(user.id, user.username, user.first_name)
    await resume_plan(user.id)

    db_user = await get_user(user.id)
    plan = await generate_daily_plan(user.id, db_user.get("daily_hours", 4))
    await save_study_plan(user.id, today_str(), plan)
    greeting = get_morning_greeting()
    plan_msg = format_plan_message(plan, greeting)

    await update.message.reply_text(
        "▶️ 学习计划已恢复！\n\n"
        f"{plan_msg}"
    )


# ============================================================
# /submit_test — 提交测试错题
# ============================================================

async def submit_test_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """提交测试错题反馈"""
    await update.message.reply_text(
        "📝 错题反馈\n\n"
        "请告诉我你错了哪些题，格式如下：\n"
        "   错了 1,3,5\n\n"
        "我会自动：\n"
        "   ├─ 记录错题到错题本\n"
        "   ├─ 调整对应章节掌握度\n"
        "   └─ 重新生成学习计划\n\n"
        "💡 也可以直接发送「错了 X,X,X」来反馈"
    )


# ============================================================
# v3 新增: /graduate — 研究生难度学习模式
# ============================================================

async def graduate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """研究生难度学习模式开关"""
    user = update.effective_user
    await get_or_create_user(user.id, user.username, user.first_name)

    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    from study_bot.database.ops import get_user_mode, get_graduate_mode
    from study_bot.services.graduate_mode import (
        can_start_graduate_mode,
        get_graduate_progress,
        format_graduate_progress_bar,
        format_graduate_eligibility,
    )

    study_mode = await get_user_mode(user.id)
    grad_data = await get_graduate_mode(user.id)
    is_graduate_active = grad_data and grad_data.get("is_active")

    # 研究生模式已激活 → 显示进度和管理按钮
    if is_graduate_active:
        progress = await get_graduate_progress(user.id)
        msg = format_graduate_progress_bar(progress)

        keyboard = [
            [InlineKeyboardButton("📈 刷新进度", callback_data="grad_progress")],
            [
                InlineKeyboardButton("🔬 深化专升本测试", callback_data="grad_deepened_test"),
                InlineKeyboardButton("🏃 退出研究生模式", callback_data="grad_exit"),
            ],
        ]
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # 检查资格
    eligibility = await can_start_graduate_mode(user.id)
    msg = format_graduate_eligibility(eligibility)

    if eligibility["can_start"]:
        keyboard = [
            [InlineKeyboardButton("🎓 开启研究生模式", callback_data="grad_start")],
            [InlineKeyboardButton("📊 查看详细评估", callback_data="grad_progress")],
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("📊 查看详细评估", callback_data="grad_progress")],
        ]

    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))


# ============================================================
# v3 新增: /taiyuan_info — 太原工业学院专升本信息
# ============================================================

async def taiyuan_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查看太原工业学院专升本相关信息"""
    await update.message.chat.send_action(ChatAction.TYPING)
    await update.message.reply_text("⏳ 正在获取太原工业学院专升本信息...")

    try:
        from study_bot.services.taiyuan_scraper import scrape_taiyuan_info, format_taiyuan_info
        info = await scrape_taiyuan_info()
        msg = format_taiyuan_info(info)
        await update.message.reply_text(msg, disable_web_page_preview=True)
    except Exception as e:
        await update.message.reply_text(
            f"❌ 获取信息失败：{str(e)[:200]}\n\n"
            f"🏫 太原工业学院\n"
            f"📋 电气工程及其自动化\n"
            f"🌐 官网：https://www.tit.edu.cn/\n"
            f"📖 招生网：https://www.tit.edu.cn/zsw/index.htm"
        )


# ============================================================
# v3 新增: 知识点专项出题（文本消息处理器）
# ============================================================

async def handle_knowledge_point_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    处理用户关于知识点的提问
    匹配模式：XXX知识点不会 / XXX不会 / XXX不懂 / XXX搞不懂
    """
    import re
    text = update.message.text.strip()

    # 检测模式
    patterns = [
        (r'(.+?)知识点不会', True),
        (r'(.+?)不会', True),
        (r'(.+?)不懂', True),
        (r'(.+?)搞不懂', True),
        (r'(.+?)学不明白', True),
    ]

    knowledge_point = None
    for pattern, _ in patterns:
        match = re.search(pattern, text)
        if match:
            kp = match.group(1).strip()
            # 过滤太短的匹配和明显的日常对话
            if len(kp) >= 2 and not any(
                w in kp for w in ["我", "你", "他", "这", "那", "怎么", "什么", "为什么"]
            ):
                knowledge_point = kp
                break

    if not knowledge_point:
        return  # 不处理，让其他处理器处理

    user = update.effective_user
    await get_or_create_user(user.id, user.username, user.first_name)

    # 在章节中模糊匹配知识点
    from study_bot.database.ops import get_all_subjects, get_chapters_by_subject
    subjects = await get_all_subjects()

    matched_subject = None
    matched_chapter = None
    best_score = 0

    for subj in subjects:
        chapters = await get_chapters_by_subject(subj["id"])
        for ch in chapters:
            ch_name = ch.get("name", "")
            # 精确匹配
            if knowledge_point in ch_name:
                matched_subject = subj["name"]
                matched_chapter = ch_name
                best_score = 100
                break
            # 部分匹配
            score = sum(1 for c in knowledge_point if c in ch_name) / max(len(knowledge_point), 1)
            if score > best_score and score > 0.3:
                best_score = score
                matched_subject = subj["name"]
                matched_chapter = ch_name

    if not matched_subject:
        await update.message.reply_text(
            f"🤔 没有在知识点库中找到「{knowledge_point}」\n\n"
            "请确认知识点名称是否正确，或使用以下命令：\n"
            "  /weekly_test — 选择科目和难度生成试卷\n"
            "  /assess — 知识点自评\n"
            "  /solve — 拍照搜题"
        )
        return

    # 显示确认按钮
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton

    current_diff = context.user_data.get("test_difficulty", "basic")
    from study_bot.config import DIFFICULTY_LEVELS
    diff_label = DIFFICULTY_LEVELS.get(current_diff, {}).get("label", "专升本基础")

    await update.message.reply_text(
        f"🎯 检测到知识点：{knowledge_point}\n"
        f"📚 匹配章节：{matched_subject} — {matched_chapter}\n"
        f"📊 难度：{diff_label}\n\n"
        "请选择题量：",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("5题（快速练习）", callback_data=f"kpquestion_5"),
                InlineKeyboardButton("10题（标准练习）", callback_data=f"kpquestion_10"),
            ],
            [
                InlineKeyboardButton("15题（强化训练）", callback_data=f"kpquestion_15"),
            ],
        ]),
    )

    # 存储匹配信息到 user_data
    context.user_data["kp_subject"] = matched_subject
    context.user_data["kp_name"] = knowledge_point
    context.user_data["kp_chapter"] = matched_chapter
