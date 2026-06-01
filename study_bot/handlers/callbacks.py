"""
Inline Button 回调处理器
处理入门引导、学习日志、知识评估的交互流程
"""

import json
from datetime import date

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler

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
from study_bot.services.plan_generator import generate_daily_plan, format_plan_message
from study_bot.utils.helpers import today_str, get_morning_greeting, days_until

from study_bot.handlers.conversations import (
    ONBOARD_TARGET, ONBOARD_HOURS, ONBOARD_TIME, ONBOARD_PROGRESS,
    ONBOARD_DATA,
    LOG_SELECT_SUBJECT, LOG_SELECT_CHAPTER, LOG_INPUT_TIME, LOG_INPUT_RATING, LOG_INPUT_NOTES,
    LOG_DATA,
    ASSESS_SUBJECT, ASSESS_CHAPTER, ASSESS_SCORE,
    ASSESS_DATA,
)


# ============================================================
# 入门引导回调
# ============================================================

async def onboarding_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """入门引导的回调处理"""
    query = update.callback_query
    await query.answer()
    data = query.data

    user = update.effective_user
    onboard = context.user_data.get(ONBOARD_DATA, {})

    # Step 1: 目标大学
    if data.startswith("onboard_target_"):
        target = data.replace("onboard_target_", "")
        if target == "other":
            await query.edit_message_text(
                "请输入你的目标大学名称：\n（直接输入文字发送即可）"
            )
            return ONBOARD_TARGET
        onboard["target_univ"] = target
        context.user_data[ONBOARD_DATA] = onboard

        await query.edit_message_text(
            f"目标大学：{target} ✅\n\n"
            "第二步：你每天能投入多少小时学习？",
            reply_markup=_hours_keyboard(),
        )
        return ONBOARD_HOURS

    # Step 2: 每日学习时长
    if data.startswith("onboard_hours_"):
        hours = int(data.replace("onboard_hours_", ""))
        onboard["daily_hours"] = hours
        context.user_data[ONBOARD_DATA] = onboard

        await query.edit_message_text(
            f"每日学习：{hours}小时 ✅\n\n"
            "第三步：每天几点推送学习计划？\n（早上推送，建议7:00-8:00）",
            reply_markup=_time_keyboard(),
        )
        return ONBOARD_TIME

    # Step 3: 推送时间
    if data.startswith("onboard_time_"):
        time_str = data.replace("onboard_time_", "")
        onboard["reminder_time"] = time_str
        context.user_data[ONBOARD_DATA] = onboard

        await query.edit_message_text(
            f"计划推送：{time_str} ✅\n\n"
            "最后一步：你目前的复习进度如何？\n"
            "请对每门科目选择当前状态：",
            reply_markup=_progress_keyboard_first(),
        )
        onboard["progress"] = {}
        context.user_data[ONBOARD_DATA] = onboard
        return ONBOARD_PROGRESS

    # Step 4: 当前进度（多科目，分步骤）
    if data.startswith("onboard_progress_"):
        parts = data.replace("onboard_progress_", "").split("_", 1)
        subject_name = parts[0]
        level = parts[1] if len(parts) > 1 else ""

        level_map = {
            "not_started": "还没开始",
            "beginner": "刚开始学",
            "half": "学了一半",
            "mostly": "基本学完",
            "review": "在复习阶段",
        }
        onboard["progress"][subject_name] = level_map.get(level, level)

        # 三个科目依次询问
        subjects_order = ["电路分析", "高等数学", "英语"]
        done = len(onboard["progress"])

        if done < len(subjects_order):
            next_subj = subjects_order[done]
            context.user_data[ONBOARD_DATA] = onboard
            await query.edit_message_text(
                f"已记录 {done}/{len(subjects_order)} 科 ✅\n\n"
                f"📚 {next_subj} 的情况：",
                reply_markup=_progress_keyboard_for_subject(next_subj),
            )
            return ONBOARD_PROGRESS

        # 全部完成 → 保存用户数据
        await _finish_onboarding(query, user, onboard, context)
        return ConversationHandler.END


async def _finish_onboarding(query, user, onboard, context):
    """完成入门引导"""
    # 确保用户已在数据库中存在（新用户必须先创建记录）
    await get_or_create_user(user.id, user.username, user.first_name)

    # 更新用户数据
    await update_user(
        user.id,
        target_univ=onboard.get("target_univ", "太原理工大学"),
        daily_hours=onboard.get("daily_hours", 6),
        reminder_time=onboard.get("reminder_time", "07:00"),
        onboarding_done=1,
    )

    # 初始化所有章节掌握度
    await init_user_mastery(user.id)

    # 根据用户回答的进度设置初始掌握度
    level_to_mastery = {
        "还没开始": 0.05,
        "刚开始学": 0.20,
        "学了一半": 0.45,
        "基本学完": 0.70,
        "在复习阶段": 0.80,
    }
    for subj_name, level_str in onboard.get("progress", {}).items():
        initial_mastery = level_to_mastery.get(level_str, 0.1)
        subjects = await get_all_subjects()
        for subj in subjects:
            if subj["name"] == subj_name:
                chapters = await get_chapters_by_subject(subj["id"])
                for ch in chapters:
                    await update_mastery(user.id, ch["id"], initial_mastery)

    # 生成第一份计划
    plan = await generate_daily_plan(user.id, onboard.get("daily_hours", 6))
    from study_bot.database.ops import save_study_plan
    await save_study_plan(user.id, today_str(), plan)

    greeting = get_morning_greeting()
    plan_msg = format_plan_message(plan, greeting)

    db_user = await get_user(user.id)
    days = days_until(db_user["exam_date"])

    await query.edit_message_text(
        f"🎉 设置完成！{user.first_name or '同学'}，欢迎加入！\n\n"
        f"🏫 目标：{onboard.get('target_univ', '太原理工大学')}\n"
        f"⏰ 每日学习：{onboard.get('daily_hours', 6)}小时\n"
        f"🕖 计划推送：{onboard.get('reminder_time', '07:00')}\n"
        f"📅 距考试：约{days}天\n\n"
        f"📌 这是你的第一份学习计划：\n\n{plan_msg}\n\n"
        f"💪 每天按时学习，用 /log 记录，用 /summary 总结！\n"
        f"祝你成功上岸！🚀"
    )


# ============================================================
# 学习日志回调
# ============================================================

async def log_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """学习日志的回调处理"""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "log_cancel":
        await query.edit_message_text("✅ 已取消记录。")
        return ConversationHandler.END

    log_ctx = context.user_data.get(LOG_DATA, {})

    # Step 1: 选择科目
    if data.startswith("log_subject_"):
        parts = data.replace("log_subject_", "").split("_", 1)
        subj_id = int(parts[0])
        subj_name = parts[1]
        log_ctx["subject_id"] = subj_id
        log_ctx["subject_name"] = subj_name
        context.user_data[LOG_DATA] = log_ctx

        chapters = await get_chapters_by_subject(subj_id)
        keyboard = _chapters_keyboard(chapters, "log_chapter")
        keyboard.append([InlineKeyboardButton("⬅️ 返回选科目", callback_data="log_back_subject")])
        keyboard.append([InlineKeyboardButton("❌ 取消", callback_data="log_cancel")])

        await query.edit_message_text(
            f"📝 记录学习 — 第2步\n\n科目：{subj_name}\n请选择学习的章节：",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return LOG_SELECT_CHAPTER

    # 返回选科目
    if data == "log_back_subject":
        subjects = await get_all_subjects()
        emoji_map = {"电路分析": "🔌", "英语": "📝", "高等数学": "📘"}
        keyboard = []
        for subj in subjects:
            emoji = emoji_map.get(subj["name"], "📚")
            keyboard.append([
                InlineKeyboardButton(
                    f"{emoji} {subj['name']}",
                    callback_data=f"log_subject_{subj['id']}_{subj['name']}",
                )
            ])
        keyboard.append([InlineKeyboardButton("❌ 取消", callback_data="log_cancel")])
        await query.edit_message_text(
            "📝 记录学习 — 第1步\n\n请选择你学习的科目：",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return LOG_SELECT_SUBJECT

    # Step 2: 选择章节
    if data.startswith("log_chapter_"):
        parts = data.replace("log_chapter_", "").split("_", 1)
        ch_id = int(parts[0])
        ch_name = parts[1] if len(parts) > 1 else ""
        log_ctx["chapter_id"] = ch_id
        log_ctx["chapter_name"] = ch_name
        context.user_data[LOG_DATA] = log_ctx

        await query.edit_message_text(
            f"📝 记录学习 — 第3步\n\n科目：{log_ctx['subject_name']}\n章节：{ch_name}\n\n"
            f"请输入学习时长（分钟）：\n例如：90\n（直接输入数字即可）"
        )
        return LOG_INPUT_TIME


async def log_time_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """接收学习时长文本输入"""
    log_ctx = context.user_data.get(LOG_DATA, {})
    text = update.message.text.strip()

    try:
        minutes = int(text)
        if minutes < 5:
            await update.message.reply_text("⏰ 学习时长至少5分钟，请重新输入：")
            return LOG_INPUT_TIME
        if minutes > 600:
            await update.message.reply_text("⏰ 单次学习最长600分钟(10小时)，请重新输入：")
            return LOG_INPUT_TIME

        log_ctx["time_spent_min"] = minutes
        context.user_data[LOG_DATA] = log_ctx

        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = [
            [
                InlineKeyboardButton("⭐1", callback_data="log_rating_1"),
                InlineKeyboardButton("⭐2", callback_data="log_rating_2"),
                InlineKeyboardButton("⭐3", callback_data="log_rating_3"),
                InlineKeyboardButton("⭐4", callback_data="log_rating_4"),
                InlineKeyboardButton("⭐5", callback_data="log_rating_5"),
            ],
            [InlineKeyboardButton("❌ 取消", callback_data="log_cancel")],
        ]

        await update.message.reply_text(
            f"📝 记录学习 — 第4步\n\n学习时长：{minutes}分钟\n\n"
            f"请自评掌握程度（1-5星）：",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return LOG_INPUT_RATING

    except ValueError:
        await update.message.reply_text("⚠️ 请输入数字（分钟），例如：90")
        return LOG_INPUT_TIME


async def log_rating_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """自评打分回调"""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "log_cancel":
        await query.edit_message_text("✅ 已取消记录。")
        return ConversationHandler.END

    if data.startswith("log_rating_"):
        rating = int(data.replace("log_rating_", ""))
        log_ctx = context.user_data.get(LOG_DATA, {})

        # 保存学习日志
        await add_study_log(
            user_id=update.effective_user.id,
            subject_id=log_ctx["subject_id"],
            chapter_id=log_ctx["chapter_id"],
            time_spent_min=log_ctx["time_spent_min"],
            self_rating=rating,
            date_str=today_str(),
        )

        # 更新掌握度
        rating_to_mastery_change = {
            1: -0.05,  # 完全不懂 → 降5%
            2: 0.0,    # 不太懂 → 不变
            3: 0.03,   # 一般 → +3%
            4: 0.06,   # 较好 → +6%
            5: 0.10,   # 很好 → +10%
        }

        from study_bot.database.ops import get_user_mastery
        mastery_list = await get_user_mastery(update.effective_user.id, log_ctx["subject_id"])
        current_mastery = 0.0
        for m in mastery_list:
            if m["chapter_id"] == log_ctx["chapter_id"]:
                current_mastery = m["mastery_level"]
                break

        new_mastery = min(1.0, max(0.0, current_mastery + rating_to_mastery_change.get(rating, 0.02)))
        await update_mastery(update.effective_user.id, log_ctx["chapter_id"], new_mastery)

        # 更新连续学习
        from study_bot.database.ops import update_streak
        await update_streak(update.effective_user.id)

        rating_stars = "⭐" * rating
        await query.edit_message_text(
            f"✅ 学习记录已保存！\n\n"
            f"📚 {log_ctx['subject_name']} - {log_ctx['chapter_name']}\n"
            f"⏰ {log_ctx['time_spent_min']}分钟\n"
            f"⭐ {rating_stars}\n"
            f"📈 掌握度：{current_mastery*100:.0f}% → {new_mastery*100:.0f}%\n\n"
            f"继续加油！💪"
        )

        # 清理临时数据
        context.user_data.pop(LOG_DATA, None)
        return ConversationHandler.END


# ============================================================
# 知识点评估回调
# ============================================================

async def assess_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """知识评估的回调处理"""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "assess_cancel":
        await query.edit_message_text("✅ 已取消评估。")
        return ConversationHandler.END

    assess_ctx = context.user_data.get(ASSESS_DATA, {})

    # Step 1: 选择科目
    if data.startswith("assess_subject_"):
        parts = data.replace("assess_subject_", "").split("_", 1)
        subj_id = int(parts[0])
        subj_name = parts[1]
        assess_ctx["subject_id"] = subj_id
        assess_ctx["subject_name"] = subj_name

        chapters = await get_chapters_by_subject(subj_id)
        assess_ctx["chapters_to_assess"] = [{"id": ch["id"], "name": ch["name"], "importance": ch["importance"]} for ch in chapters]
        assess_ctx["current_index"] = 0
        assess_ctx["scores"] = {}
        context.user_data[ASSESS_DATA] = assess_ctx

        return await _ask_next_chapter(query, assess_ctx, update)

    # 处理"停止评估"
    if data == "assess_finish":
        return await _finish_assessment(query, assess_ctx, update)

    # Step 2 & 3: 逐章打分
    if data.startswith("assess_score_"):
        score = int(data.replace("assess_score_", ""))
        idx = assess_ctx["current_index"]
        chapters = assess_ctx["chapters_to_assess"]

        if idx < len(chapters):
            ch = chapters[idx]
            assess_ctx["scores"][ch["name"]] = {
                "chapter_id": ch["id"],
                "score": score,
                "importance": ch["importance"],
            }
            assess_ctx["current_index"] = idx + 1
            context.user_data[ASSESS_DATA] = assess_ctx

            return await _ask_next_chapter(query, assess_ctx, update)

    # 完成评估 — 生成报告
    return await _finish_assessment(query, assess_ctx, update)


async def _ask_next_chapter(query, assess_ctx, update):
    """询问下一章的评分"""
    idx = assess_ctx["current_index"]
    chapters = assess_ctx["chapters_to_assess"]

    if idx >= len(chapters):
        return await _finish_assessment(query, assess_ctx, update)

    ch = chapters[idx]
    remaining = len(chapters) - idx - 1

    keyboard = [
        [
            InlineKeyboardButton("0-20", callback_data="assess_score_10"),
            InlineKeyboardButton("20-40", callback_data="assess_score_30"),
            InlineKeyboardButton("40-60", callback_data="assess_score_50"),
        ],
        [
            InlineKeyboardButton("60-75", callback_data="assess_score_68"),
            InlineKeyboardButton("75-90", callback_data="assess_score_83"),
            InlineKeyboardButton("90-100", callback_data="assess_score_95"),
        ],
        [InlineKeyboardButton("❌ 停止评估", callback_data="assess_finish")],
    ]

    await query.edit_message_text(
        f"📋 {assess_ctx['subject_name']} 知识自评\n\n"
        f"当前章节 ({idx+1}/{len(chapters)})：\n"
        f"📖 {ch['name']}\n"
        f"重要度：{'⭐' * ch['importance']}\n\n"
        f"你对这个章节的掌握程度是多少？\n"
        f"（0=完全不会, 100=完全掌握）",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return ASSESS_SCORE


async def _finish_assessment(query, assess_ctx, update):
    """完成评估，生成报告"""
    db_user = await get_or_create_user(
        update.effective_user.id,
        update.effective_user.username,
        update.effective_user.first_name,
    )

    scores = assess_ctx.get("scores", {})
    if not scores:
        await query.edit_message_text("⚠️ 没有评估数据，本次评估取消。")
        return ConversationHandler.END

    # 更新掌握度（评分数值 / 100）
    for ch_name, info in scores.items():
        mastery = info["score"] / 100.0
        await update_mastery(update.effective_user.id, info["chapter_id"], mastery)

    # 保存评估记录
    results_list = [
        {"chapter_name": name, "score": info["score"], "importance": info["importance"]}
        for name, info in scores.items()
    ]
    await save_assessment(
        update.effective_user.id,
        assess_ctx["subject_id"],
        today_str(),
        results_list,
    )

    # AI 分析反馈
    feedback = await analyze_assessment(assess_ctx["subject_name"], results_list)

    # 组装消息
    avg_score = sum(info["score"] for info in scores.values()) / len(scores)
    weak = [name for name, info in scores.items() if info["score"] < 50]
    strong = [name for name, info in scores.items() if info["score"] >= 75]

    report_lines = [
        f"📋 {assess_ctx['subject_name']} 评估报告",
        f"",
        f"📊 评估章节：{len(scores)}个",
        f"📈 平均自评：{avg_score:.0f}/100",
    ]
    if strong:
        report_lines.append(f"✅ 掌握较好：{'、'.join(strong[:3])}")
    if weak:
        report_lines.append(f"⚠️ 薄弱环节：{'、'.join(weak[:3])}")

    report_lines.append("")
    report_lines.append(feedback)

    await query.edit_message_text("\n".join(report_lines))

    # 清理
    context.user_data.pop(ASSESS_DATA, None)
    return ConversationHandler.END


# ============================================================
# 键盘构建辅助函数
# ============================================================

def _hours_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("4小时", callback_data="onboard_hours_4"),
            InlineKeyboardButton("6小时", callback_data="onboard_hours_6"),
            InlineKeyboardButton("8小时", callback_data="onboard_hours_8"),
        ],
        [InlineKeyboardButton("10小时+", callback_data="onboard_hours_10")],
    ])


def _time_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("06:30", callback_data="onboard_time_06:30"),
            InlineKeyboardButton("07:00", callback_data="onboard_time_07:00"),
            InlineKeyboardButton("07:30", callback_data="onboard_time_07:30"),
        ],
        [
            InlineKeyboardButton("08:00", callback_data="onboard_time_08:00"),
            InlineKeyboardButton("08:30", callback_data="onboard_time_08:30"),
        ],
    ])


def _progress_keyboard_first():
    """第一科进度选择（电路分析）"""
    return _progress_keyboard_for_subject("电路分析")


def _progress_keyboard_for_subject(subject_name: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("还没开始", callback_data=f"onboard_progress_{subject_name}_not_started")],
        [InlineKeyboardButton("刚开始学", callback_data=f"onboard_progress_{subject_name}_beginner")],
        [InlineKeyboardButton("学了一半", callback_data=f"onboard_progress_{subject_name}_half")],
        [InlineKeyboardButton("基本学完", callback_data=f"onboard_progress_{subject_name}_mostly")],
        [InlineKeyboardButton("在复习阶段", callback_data=f"onboard_progress_{subject_name}_review")],
    ])


def _chapters_keyboard(chapters: list, prefix: str):
    """章节列表键盘"""
    keyboard = []
    for ch in chapters:
        keyboard.append([
            InlineKeyboardButton(
                f"{ch['name']} {'⭐'*ch['importance']}",
                callback_data=f"{prefix}_{ch['id']}_{ch['name']}",
            )
        ])
    return keyboard


# ============================================================
# 考试反馈回调（多轮测试→反馈→计划调整）
# ============================================================

async def testfb_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理考试反馈的多步交互"""
    query = update.callback_query
    await query.answer()
    data = query.data

    fb = context.user_data.get("testfb_data", {})

    from study_bot.handlers.conversations import (
        TESTFB_SUBJECT, TESTFB_SCORE, TESTFB_WRONG, TESTFB_CONFIRM,
        TESTFB_DATA,
    )

    if data == "testfb_cancel":
        await query.edit_message_text("✅ 已取消考试反馈。")
        context.user_data.pop(TESTFB_DATA, None)
        return ConversationHandler.END

    # Step 1: 选择科目
    if data.startswith("testfb_"):
        parts = data.replace("testfb_", "").split("_", 1)
        if parts[0] == "done":
            return await _testfb_finish_all(query, fb, update, context)

        subj_id = int(parts[0])
        subj_name = parts[1] if len(parts) > 1 else ""
        fb["current_subject_id"] = subj_id
        fb["current_subject_name"] = subj_name
        context.user_data[TESTFB_DATA] = fb

        await query.edit_message_text(
            f"📝 考试反馈 — {subj_name}\n\n"
            "第2步：请输入你的得分\n"
            "例如：75\n"
            "（输入0-100的分数，直接输入数字即可）"
        )
        return TESTFB_SCORE


async def testfb_score_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """接收考试分数"""
    fb = context.user_data.get("testfb_data", {})
    text = update.message.text.strip()

    try:
        score = float(text)
        if score < 0 or score > 100:
            await update.message.reply_text("⚠️ 分数应在0-100之间，请重新输入：")
            return TESTFB_SCORE

        fb["current_score"] = score
        context.user_data[TESTFB_DATA] = fb

        await update.message.reply_text(
            f"📝 考试反馈 — {fb['current_subject_name']}\n"
            f"得分：{score}/100 ✅\n\n"
            "第3步：请告诉我你错了哪些题\n"
            "例如：错了 1,3,5\n"
            "（如果没有错题，回复「全对」）"
        )
        return TESTFB_WRONG

    except ValueError:
        await update.message.reply_text("⚠️ 请输入数字，例如：75")
        return TESTFB_SCORE


async def testfb_wrong_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """接收错题题号并处理"""
    import re
    fb = context.user_data.get("testfb_data", {})
    text = update.message.text.strip()

    from study_bot.handlers.conversations import (
        TESTFB_SUBJECT, TESTFB_CONFIRM, TESTFB_DATA,
    )
    from study_bot.database.ops import (
        get_chapters_by_subject, get_user_mastery, update_mastery,
        add_error, get_test_history, save_study_plan,
    )
    from study_bot.services.plan_generator import generate_daily_plan, format_plan_message
    from study_bot.utils.helpers import today_str, get_morning_greeting

    user = update.effective_user

    if "全对" in text or "没错" in text:
        fb["wrong_questions"] = []
        fb["wrong_chapters"] = []
    else:
        nums = re.findall(r'\d+', text)
        fb["wrong_questions"] = [int(n) for n in nums]

        # 尝试从最近的测试记录中匹配章节
        tests = await get_test_history(user.id, limit=3)
        test_content = ""
        if tests:
            # 找对应科目的最新测试
            for t in tests:
                if t.get("subject_id") == fb["current_subject_id"]:
                    test_content = t.get("test_content", "")
                    break
            if not test_content:
                test_content = tests[0].get("test_content", "")

        # 匹配章节并更新掌握度
        wrong_chapters = set()
        recorded = 0
        for q_num in fb["wrong_questions"][:10]:
            ch_name = _find_chapter_in_test(test_content, q_num)
            chapter_id = None
            if ch_name:
                chapters = await get_chapters_by_subject(fb["current_subject_id"])
                for ch in chapters:
                    if ch_name in ch["name"] or ch["name"] in ch_name:
                        chapter_id = ch["id"]
                        break

            if chapter_id:
                await add_error(
                    user.id, fb["current_subject_id"], chapter_id,
                    question=f"{fb['current_subject_name']}测试第{q_num}题",
                    wrong_answer="考试反馈",
                    knowledge_point=ch_name or "",
                )
                mastery_list = await get_user_mastery(user.id, fb["current_subject_id"])
                current = 0.0
                for m in mastery_list:
                    if m["chapter_id"] == chapter_id:
                        current = m["mastery_level"]
                        break
                new_mastery = max(0.0, current - 0.08)
                await update_mastery(user.id, chapter_id, new_mastery)
                wrong_chapters.add(ch_name or f"第{q_num}题")
                recorded += 1

        fb["wrong_chapters"] = list(wrong_chapters)
        fb["recorded_count"] = recorded

    # 记录本轮结果
    if "results" not in fb:
        fb["results"] = []
    fb["results"].append({
        "subject_name": fb["current_subject_name"],
        "subject_id": fb["current_subject_id"],
        "score": fb["current_score"],
        "wrong_count": len(fb.get("wrong_questions", [])),
        "wrong_chapters": fb.get("wrong_chapters", []),
    })

    # 更新已完成列表
    if "completed_subjects" not in fb:
        fb["completed_subjects"] = []
    fb["completed_subjects"].append(fb["current_subject_name"])

    context.user_data[TESTFB_DATA] = fb

    # 显示本轮摘要并询问是否继续
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    wrong_str = "、".join(fb.get("wrong_chapters", [])) if fb.get("wrong_chapters") else "无"
    subj_names = "、".join(fb["completed_subjects"])

    await update.message.reply_text(
        f"✅ {fb['current_subject_name']} 反馈已记录\n\n"
        f"📊 得分：{fb['current_score']}/100\n"
        f"❌ 错题数：{len(fb.get('wrong_questions', []))}\n"
        f"🔍 薄弱章节：{wrong_str}\n\n"
        f"已反馈科目：{subj_names}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔌 电路分析", callback_data=f"testfb_subj_电路分析")],
            [InlineKeyboardButton("📘 高等数学", callback_data=f"testfb_subj_高等数学")],
            [InlineKeyboardButton("📝 英语", callback_data=f"testfb_subj_英语")],
            [InlineKeyboardButton("✅ 全部考完，生成计划", callback_data="testfb_done_all")],
            [InlineKeyboardButton("❌ 取消", callback_data="testfb_cancel")],
        ]),
    )
    return TESTFB_CONFIRM


async def testfb_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理确认阶段的选择（继续下一科 or 全部完成）"""
    query = update.callback_query
    await query.answer()
    data = query.data

    fb = context.user_data.get("testfb_data", {})
    from study_bot.handlers.conversations import (
        TESTFB_SUBJECT, TESTFB_SCORE, TESTFB_CONFIRM, TESTFB_DATA,
    )

    if data == "testfb_cancel":
        await query.edit_message_text("✅ 已取消考试反馈。")
        context.user_data.pop(TESTFB_DATA, None)
        return ConversationHandler.END

    if data == "testfb_done_all":
        return await _testfb_finish_all(query, fb, update, context)

    # 继续下一科
    parts = data.split("_", 2)
    if len(parts) >= 3:
        subj_name = parts[2]
        # 查找科目ID
        from study_bot.database.ops import get_all_subjects
        subjects = await get_all_subjects()
        for s in subjects:
            if s["name"] == subj_name:
                fb["current_subject_id"] = s["id"]
                fb["current_subject_name"] = s["name"]
                context.user_data[TESTFB_DATA] = fb
                break

    await query.edit_message_text(
        f"📝 考试反馈 — {fb['current_subject_name']}\n\n"
        "第2步：请输入你的得分\n"
        "例如：75"
    )
    return TESTFB_SCORE


async def _testfb_finish_all(query, fb, update, context):
    """完成所有考试反馈，生成综合计划"""
    from study_bot.handlers.conversations import TESTFB_DATA
    from study_bot.database.ops import get_user, save_study_plan
    from study_bot.services.plan_generator import generate_daily_plan, format_plan_message
    from study_bot.utils.helpers import today_str, get_morning_greeting, days_until

    user = update.effective_user
    db_user = await get_user(user.id)

    # 生成调整后的计划
    plan = await generate_daily_plan(user.id, db_user.get("daily_hours", 4))
    await save_study_plan(user.id, today_str(), plan)

    greeting = get_morning_greeting()
    plan_msg = format_plan_message(plan, greeting)

    # 汇总
    results = fb.get("results", [])
    summary_lines = ["📊 考试反馈汇总", ""]
    total_avg = 0
    for r in results:
        summary_lines.append(
            f"{'📘' if '数学' in r['subject_name'] else '🔌' if '电路' in r['subject_name'] else '📝'} "
            f"{r['subject_name']}：{r['score']}/100 | 错{r['wrong_count']}题"
        )
        total_avg += r['score']
    if results:
        total_avg = total_avg / len(results)
    summary_lines.append(f"\n📈 平均分：{total_avg:.0f}/100")
    summary_lines.append(f"📋 已根据考试结果更新掌握度和学习计划")

    await query.edit_message_text("\n".join(summary_lines))

    # 发送新计划
    days = days_until(db_user["exam_date"])
    await query.message.reply_text(
        f"📋 基于考试反馈的调整后计划：\n\n{plan_msg}\n\n"
        f"🎯 距考试还有 {days} 天，加油！"
    )

    context.user_data.pop(TESTFB_DATA, None)
    return ConversationHandler.END


def _find_chapter_in_test(test_content: str, q_num: int) -> str:
    """在试卷内容中查找题号对应的章节（辅助函数）"""
    import re
    if not test_content:
        return ""
    lines = test_content.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(f"{q_num}.") or stripped.startswith(f"{q_num}、"):
            for j in range(i, min(i + 20, len(lines))):
                if "考察知识点" in lines[j] or "📚" in lines[j]:
                    match = re.search(r"考察知识点[：:]\s*(.+?)(?:\s*[-—]\s*(.+))?$", lines[j])
                    if match:
                        return match.group(1).strip()
            break
    return ""


# ============================================================
# 诊断性多轮测试回调（5轮出题→做题→反馈→计划）
# ============================================================

async def diag_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """诊断测试主回调：生成试卷、处理轮次、设置轮数"""
    query = update.callback_query
    await query.answer()
    data = query.data

    from study_bot.handlers.conversations import (
        DIAG_CONFIRM, DIAG_FEEDBACK, DIAG_WRONG, DIAG_NEXT,
        DIAG_DATA,
    )
    from study_bot.database.ops import get_test_history

    diag = context.user_data.get(DIAG_DATA, {})
    user = update.effective_user

    if data == "diag_cancel":
        await query.edit_message_text("✅ 已取消诊断测试。随时可以用 /diagnostic 重新开始。")
        context.user_data.pop(DIAG_DATA, None)
        return ConversationHandler.END

    # 处理设置轮数
    if data.startswith("diag_setrounds_"):
        rounds = int(data.replace("diag_setrounds_", ""))
        context.user_data["diag_rounds"] = rounds
        from study_bot.handlers.conversations import _build_round_plan
        new_plan = _build_round_plan(rounds)
        diag["total_rounds"] = rounds
        diag["round_plan"] = new_plan
        context.user_data[DIAG_DATA] = diag
        await query.edit_message_text(
            f"✅ 已设置为 {rounds} 轮诊断测试\n\n"
            f"点击下方按钮开始："
        )
        # Re-show start button
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        await query.message.reply_text(
            f"🔬 {rounds}轮诊断测试已就绪",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(f"🚀 开始第1轮测试", callback_data="diag_start"),
                InlineKeyboardButton("❌ 取消", callback_data="diag_cancel"),
            ]]),
        )
        return DIAG_CONFIRM

    if data == "diag_start" or data == "diag_next":
        # 进入下一轮
        current_round = diag.get("round", 0) + 1
        diag["round"] = current_round
        total = diag.get("total_rounds", 5)
        round_plan = diag.get("round_plan", [])

        if current_round > total:
            return await _diag_finish_all(query, diag, update, context)

        round_info = round_plan[current_round - 1] if current_round <= len(round_plan) else {
            "subject": "高等数学", "desc": "综合诊断"
        }
        diag["current_subject"] = round_info["subject"]
        context.user_data[DIAG_DATA] = diag

        # 查找科目ID
        from study_bot.database.ops import get_all_subjects
        subjects = await get_all_subjects()
        subj_id = None
        for s in subjects:
            if s["name"] == round_info["subject"]:
                subj_id = s["id"]
                break

        # 生成试卷
        await query.edit_message_text(
            f"⏳ 正在生成第{current_round}轮试卷...\n"
            f"📚 {round_info['subject']} — {round_info['desc']}"
        )

        # 使用诊断模式生成试卷（针对薄弱点）
        weak_info = ""
        if diag.get("weak_chapters_all"):
            weak_info = "薄弱章节：" + "、".join(
                list(diag["weak_chapters_all"].keys())[:5]
            )

        from study_bot.services.test_generator import (
            create_weekly_test, generate_pdf_test, format_test_for_telegram,
        )
        import os

        result = await create_weekly_test(user.id, round_info["subject"],
                                          difficulty="adaptive", question_count=6)
        if "error" in result:
            await query.edit_message_text(
                f"❌ 第{current_round}轮试卷生成失败：{result['error']}\n"
                "请点击重试："
            )
            return DIAG_CONFIRM

        # 生成 PDF 并发送
        pdf_path = await generate_pdf_test(user.id, round_info["subject"], result)
        if pdf_path and os.path.exists(pdf_path) and pdf_path.endswith('.pdf'):
            with open(pdf_path, 'rb') as f:
                await query.message.reply_document(
                    document=f,
                    filename=os.path.basename(pdf_path),
                    caption=(
                        f"📝 诊断测试 第{current_round}/{total}轮\n"
                        f"📚 {round_info['subject']} — {round_info['desc']}\n"
                        f"📅 {result['date']} | 题量：6题"
                    ),
                )
        else:
            test_msg = format_test_for_telegram(result)
            await query.message.reply_text(test_msg[:4000])

        # 保存试卷内容用于后续解析
        diag["current_test_content"] = result.get("test_text", "")
        context.user_data[DIAG_DATA] = diag

        await query.edit_message_text(
            f"📝 第{current_round}/{total}轮 — {round_info['subject']}\n\n"
            "试卷已发送（PDF文件）✅\n\n"
            "完成后请回复你的得分：\n"
            "例如：75"
        )
        return DIAG_FEEDBACK


async def diag_score_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """接收诊断测试得分"""
    from study_bot.handlers.conversations import DIAG_FEEDBACK, DIAG_WRONG, DIAG_DATA
    diag = context.user_data.get(DIAG_DATA, {})
    text = update.message.text.strip()

    try:
        score = float(text)
        if score < 0 or score > 100:
            await update.message.reply_text("⚠️ 分数应在0-100之间，请重新输入：")
            return DIAG_FEEDBACK

        diag["current_score"] = score
        context.user_data[DIAG_DATA] = diag

        await update.message.reply_text(
            f"📊 得分：{score}/100 ✅\n\n"
            "请告诉我你错了哪些题：\n"
            "例如：错了 1,3,5\n"
            "（如果全对，回复「全对」）"
        )
        return DIAG_WRONG

    except ValueError:
        await update.message.reply_text("⚠️ 请输入数字，例如：75")
        return DIAG_FEEDBACK


async def diag_wrong_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """接收错题并更新掌握度，然后进入下一轮或结束"""
    import re
    from study_bot.handlers.conversations import (
        DIAG_CONFIRM, DIAG_NEXT, DIAG_DATA,
    )
    from study_bot.database.ops import (
        get_user_mastery, update_mastery, get_chapters_by_subject,
        add_error, get_all_subjects, get_user, save_study_plan,
    )
    from study_bot.services.plan_generator import generate_daily_plan
    from study_bot.utils.helpers import today_str

    diag = context.user_data.get(DIAG_DATA, {})
    user = update.effective_user
    text = update.message.text.strip()

    if "全对" in text or "没错" in text:
        wrong_nums = []
        wrong_chapters = []
    else:
        nums = re.findall(r'\d+', text)
        wrong_nums = [int(n) for n in nums]

        # 匹配章节
        test_content = diag.get("current_test_content", "")
        wrong_chapters = []
        subjects_list = await get_all_subjects()
        subj_id = None
        for s in subjects_list:
            if s["name"] == diag["current_subject"]:
                subj_id = s["id"]
                break

        if subj_id:
            for q_num in wrong_nums[:10]:
                ch_name = _find_chapter_in_test(test_content, q_num)
                chapter_id = None
                if ch_name:
                    chapters = await get_chapters_by_subject(subj_id)
                    for ch in chapters:
                        if ch_name in ch["name"] or ch["name"] in ch_name:
                            chapter_id = ch["id"]
                            break

                if chapter_id:
                    await add_error(
                        user.id, subj_id, chapter_id,
                        question=f"诊断测试第{diag['round']}轮第{q_num}题",
                        wrong_answer="诊断反馈",
                        knowledge_point=ch_name or "",
                    )
                    mastery_list = await get_user_mastery(user.id, subj_id)
                    current = 0.0
                    for m in mastery_list:
                        if m["chapter_id"] == chapter_id:
                            current = m["mastery_level"]
                            break
                    new_mastery = max(0.0, current - 0.10)
                    await update_mastery(user.id, chapter_id, new_mastery)

                    # 累积薄弱章节
                    if ch_name not in diag.get("weak_chapters_all", {}):
                        diag.setdefault("weak_chapters_all", {})[ch_name] = 0
                    diag["weak_chapters_all"][ch_name] += 1
                    wrong_chapters.append(ch_name)

    # 记录本轮结果
    if "results" not in diag:
        diag["results"] = []
    diag["results"].append({
        "round": diag["round"],
        "subject": diag["current_subject"],
        "score": diag["current_score"],
        "wrong_count": len(wrong_nums),
        "wrong_chapters": wrong_chapters,
    })
    context.user_data[DIAG_DATA] = diag

    current_round = diag["round"]
    total = diag.get("total_rounds", 5)

    # 如果已达5轮，完成
    if current_round >= total:
        return await _diag_finish_all(update, diag, update, context)

    # 否则进入确认下一轮
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    next_round = current_round + 1
    round_plan = diag.get("round_plan", [])
    if next_round <= len(round_plan):
        next_info = round_plan[next_round - 1]
    else:
        next_info = {"subject": "综合", "desc": "最终诊断"}
    wrong_str = "、".join(wrong_chapters[:3]) if wrong_chapters else "无"

    await update.message.reply_text(
        f"✅ 第{current_round}轮完成！\n"
        f"📚 {diag['current_subject']} | 📊 {diag['current_score']}/100\n"
        f"❌ 错题：{len(wrong_nums)}道 | 🔍 {wrong_str}\n\n"
        f"下一轮：第{next_round}轮 — {next_info['subject']}（{next_info['desc']}）",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(
                f"▶️ 开始第{next_round}轮",
                callback_data="diag_next"
            )],
            [InlineKeyboardButton("❌ 取消", callback_data="diag_cancel")],
        ]),
    )
    return DIAG_NEXT


async def _diag_finish_all(source, diag, update, context):
    """5轮完成，汇总分析 + 生成最终计划"""
    from study_bot.handlers.conversations import DIAG_DATA
    from study_bot.database.ops import get_user, save_study_plan
    from study_bot.services.plan_generator import generate_daily_plan, format_plan_message
    from study_bot.utils.helpers import today_str, get_morning_greeting, days_until

    user = update.effective_user
    db_user = await get_user(user.id)

    # 生成计划
    plan = await generate_daily_plan(user.id, db_user.get("daily_hours", 4))
    await save_study_plan(user.id, today_str(), plan)
    greeting = get_morning_greeting()
    plan_msg = format_plan_message(plan, greeting)

    # 汇总
    results = diag.get("results", [])
    summary = ["📊 诊断测试汇总（5轮完成）", ""]
    total_score = 0
    for r in results:
        subj_emoji = {"高等数学": "📘", "电路分析": "🔌", "英语": "📝"}
        summary.append(
            f"第{r['round']}轮 {subj_emoji.get(r['subject'], '📚')} {r['subject']}"
            f" — {r['score']}/100 | 错{r['wrong_count']}题"
        )
        total_score += r['score']

    avg_score = total_score / len(results) if results else 0
    summary.append(f"\n📈 平均分：{avg_score:.0f}/100")

    # 汇总薄弱章节
    weak_all = diag.get("weak_chapters_all", {})
    if weak_all:
        sorted_weak = sorted(weak_all.items(), key=lambda x: x[1], reverse=True)
        summary.append("\n🔍 高频薄弱章节：")
        for ch_name, count in sorted_weak[:5]:
            summary.append(f"   ⚠️ {ch_name}（{count}次错误）")

    summary.append(f"\n📋 已根据5轮真实水平生成学习计划")

    # 发送汇总
    if hasattr(source, 'edit_message_text'):
        await source.edit_message_text("\n".join(summary))
    else:
        await source.message.reply_text("\n".join(summary))

    # 发送计划
    days = days_until(db_user["exam_date"])
    await source.message.reply_text(
        f"📋 基于诊断结果的学习计划：\n\n{plan_msg}\n\n"
        f"🎯 距考试还有 {days} 天，加油！\n\n"
        "💡 提示：\n"
        "   /plan — 每日查看计划\n"
        "   /weekly_test — 周六周测\n"
        "   /pause — 暂停学习\n"
        "   /diagnostic — 重新诊断"
    )

    context.user_data.pop(DIAG_DATA, None)
    return ConversationHandler.END
