"""
定时任务调度 v2
每天早间推送学习计划 + 晚间提醒学习总结 + 周六测试日提醒
"""

import logging
import asyncio
from datetime import time, datetime, date

from telegram.ext import Application, ContextTypes
from telegram import Bot

from study_bot.database.ops import (
    get_active_users,
    get_user,
    get_daily_logs,
    get_user_mastery,
    update_streak,
    seed_subjects_and_chapters,
    is_plan_paused,
    save_test_record,
    get_all_subjects,
)
from study_bot.services.plan_generator import generate_daily_plan, format_plan_message
from study_bot.services.analyzer import analyze_daily_summary
from study_bot.services.assessment import calc_mastery_with_decay
from study_bot.services.error_tracker import init_error_db, get_errors_due_for_review, format_error_for_review
from study_bot.utils.helpers import today_str, get_morning_greeting, days_until

logger = logging.getLogger(__name__)


async def daily_plan_job(context: ContextTypes.DEFAULT_TYPE):
    """早间任务：为所有活跃用户推送今日学习计划"""
    logger.info("⏰ 开始执行早间计划推送...")

    await seed_subjects_and_chapters()

    users = await get_active_users()
    bot: Bot = context.bot
    today = date.today()

    for user in users:
        user_id = user["user_id"]
        try:
            # 检查是否暂停
            if await is_plan_paused(user_id):
                logger.info(f"   用户 {user_id} 已暂停，跳过推送")
                continue

            # 检测当天类型
            day_type = "free_day"
            if today.weekday() == 6:
                day_type = "sunday_rest"
            elif today.weekday() == 5:
                day_type = "saturday_test"

            # 检测学习模式
            study_mode = "zhuanshengben"
            try:
                from study_bot.database.ops import get_user_mode
                study_mode = await get_user_mode(user_id)
            except Exception:
                pass

            plan = await generate_daily_plan(
                user_id, daily_hours=user.get("daily_hours", 6), day_type=day_type,
                study_mode=study_mode,
            )
            greeting = get_morning_greeting()
            message = format_plan_message(plan, greeting)

            days_left = days_until(user.get("exam_date", "2027-03-20"))

            # 考试倒计时里程碑提醒
            from study_bot.config import EXAM_COUNTDOWN_MILESTONES
            if days_left in EXAM_COUNTDOWN_MILESTONES:
                if days_left == 1:
                    message += f"\n\n🚨 明天就是考试日！调整好心态，早睡早起，相信自己！"
                elif days_left <= 7:
                    message += f"\n\n⚠️ 仅剩 {days_left} 天！最后冲刺，查漏补缺！"
                elif days_left <= 30:
                    message += f"\n\n⏰ 距考试仅 {days_left} 天，进入冲刺阶段！"
                else:
                    message += f"\n\n📅 距考试 {days_left} 天，时间还很充裕，按计划稳步前进！"
            else:
                message += f"\n\n🎯 距考试还有 {days_left} 天，加油！"

            # 研究生模式进度附加
            if study_mode == "graduate":
                try:
                    from study_bot.services.graduate_mode import get_graduate_progress
                    grad_prog = await get_graduate_progress(user_id)
                    pct = grad_prog.get("percentage", 0)
                    from study_bot.utils.helpers import progress_bar
                    bar = progress_bar(pct, length=12)
                    message += f"\n\n🎓 研究生模式进度：{bar} {pct}%"
                except Exception:
                    pass

            await bot.send_message(chat_id=user_id, text=message)
            logger.info(f"   已推送计划给用户 {user_id} ({day_type})")

        except Exception as e:
            if "Forbidden" in str(e) or "blocked" in str(e):
                logger.warning(f"   用户 {user_id} 已阻止Bot，跳过")
            else:
                logger.error(f"   推送用户 {user_id} 失败: {e}")


async def daily_summary_reminder(context: ContextTypes.DEFAULT_TYPE):
    """晚间任务：提醒用户提交学习总结"""
    logger.info("🌙 开始执行晚间总结提醒...")

    users = await get_active_users()
    bot: Bot = context.bot

    for user in users:
        user_id = user["user_id"]
        try:
            today = today_str()
            logs = await get_daily_logs(user_id, today)

            if logs:
                total_minutes = sum(log["time_spent_min"] or 0 for log in logs)
                subjects = set(log["subject_name"] for log in logs)

                summary_lines = [
                    "🌙 今日学习总结",
                    "",
                    f"⏰ 今日学习：{total_minutes // 60}小时{total_minutes % 60}分钟",
                    f"📚 覆盖科目：{'、'.join(subjects)}",
                    f"📝 记录条数：{len(logs)}条",
                    "",
                    "📋 详细记录：",
                ]
                for log in logs:
                    rating_stars = "⭐" * (log["self_rating"] or 0)
                    summary_lines.append(
                        f"   {log['subject_name']} - {log['chapter_name']} "
                        f"({log['time_spent_min']}分钟) {rating_stars}"
                    )
                summary_lines.append("")
                summary_lines.append("💡 做得好！睡前花几分钟回忆今天学的内容")
                summary_lines.append("   需要详细分析请使用 /summary")
                summary_lines.append("   有错题请及时拍照保存 → /solve")

                await bot.send_message(chat_id=user_id, text="\n".join(summary_lines))
                await update_streak(user_id)
            else:
                await bot.send_message(
                    chat_id=user_id,
                    text=(
                        "🌙 晚安～\n\n"
                        "今天还没有学习记录哦 😢\n"
                        "即使只有半小时，也要保持每天的学习节奏！\n\n"
                        "💪 现在做点什么吧：\n"
                        "   /log — 记录今天的学习\n"
                        "   /plan — 查看明天计划"
                    ),
                )

            logger.info(f"   已推送总结给用户 {user_id}")

        except Exception as e:
            if "Forbidden" in str(e) or "blocked" in str(e):
                logger.warning(f"   用户 {user_id} 已阻止Bot，跳过")
            else:
                logger.error(f"   推送用户 {user_id} 失败: {e}")


async def saturday_test_reminder(context: ContextTypes.DEFAULT_TYPE):
    """周六：自动生成全科测试卷，输出PDF并推送"""
    today = date.today()
    if today.weekday() != 5:
        return

    logger.info("📝 开始执行周六测试自动生成与推送...")
    users = await get_active_users()
    bot: Bot = context.bot

    import os
    from study_bot.services.test_generator import (
        create_weekly_test,
        generate_pdf_test,
        format_test_for_telegram,
    )

    for user in users:
        user_id = user["user_id"]
        try:
            # 检查暂停
            if await is_plan_paused(user_id):
                logger.info(f"   用户 {user_id} 已暂停，跳过")
                continue

            # 发送开始消息
            await bot.send_message(
                chat_id=user_id,
                text="📝 周六测试日！正在为你生成本周测试卷...",
            )

            subjects = ["高等数学", "电路分析", "英语"]
            for subj in subjects:
                try:
                    result = await create_weekly_test(user_id, subj)
                    if "error" in result:
                        await bot.send_message(
                            chat_id=user_id,
                            text=f"⚠️ {subj} 试卷生成失败：{result['error']}",
                        )
                        continue

                    # 生成 PDF 并发送
                    pdf_path = await generate_pdf_test(user_id, subj, result)
                    if pdf_path and os.path.exists(pdf_path) and pdf_path.endswith('.pdf'):
                        with open(pdf_path, 'rb') as f:
                            await bot.send_document(
                                chat_id=user_id,
                                document=f,
                                filename=os.path.basename(pdf_path),
                                caption=(
                                    f"📝 {subj} 周测试卷\n"
                                    f"📅 {result['date']} | 难度：{result.get('difficulty', 'medium')}"
                                ),
                            )
                    else:
                        # 降级为文本
                        test_msg = format_test_for_telegram(result)
                        await bot.send_message(chat_id=user_id, text=test_msg[:4000])

                    # 保存测试记录
                    subjects_list = await get_all_subjects()
                    for s in subjects_list:
                        if s["name"] == subj:
                            await save_test_record(
                                user_id, s["id"], today.isoformat(),
                                0, 100, result.get("test_text", ""),
                            )
                            break

                    logger.info(f"   已推送{subj}试卷给用户 {user_id}")

                except Exception as subj_err:
                    logger.error(f"   生成{subj}试卷失败(用户{user_id}): {subj_err}")

            # 发送参考答案说明
            await bot.send_message(
                chat_id=user_id,
                text=(
                    "📋 参考答案在每份PDF文件末尾\n\n"
                    "📌 做完后反馈错题：\n"
                    "   回复「错了 题号」我会自动：\n"
                    "   ├─ 记录错题到错题本\n"
                    "   ├─ 调整章节掌握度\n"
                    "   └─ 重新生成学习计划\n\n"
                    "   例如：错了 1,3,5\n\n"
                    "⏰ 建议时间：\n"
                    "   上午 做题\n"
                    "   下午 对答案+错题分析\n"
                    "   晚上 薄弱点复习"
                ),
            )

        except Exception as e:
            if "Forbidden" in str(e) or "blocked" in str(e):
                logger.warning(f"   用户 {user_id} 已阻止Bot，跳过")
            else:
                logger.error(f"   推送测试给用户 {user_id} 失败: {e}")


async def error_review_reminder(context: ContextTypes.DEFAULT_TYPE):
    """错题复习提醒（每天推送一次）"""
    users = await get_active_users()
    bot: Bot = context.bot

    for user in users:
        user_id = user["user_id"]
        try:
            # 获取待复习错题
            await init_error_db()
            errors = await get_errors_due_for_review(user_id, limit=1)

            if errors:
                await bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"📝 错题复习提醒\n\n"
                        f"你还有错题等待复习！\n"
                        f"今天花10分钟复习一道错题，积少成多。\n\n"
                        f"📌 使用 /review_errors 开始复习"
                    ),
                )
        except Exception as e:
            if "Forbidden" not in str(e):
                logger.error(f"   错题提醒推送 {user_id} 失败: {e}")


def setup_scheduler(app: Application):
    """设置定时任务"""
    job_queue = app.job_queue

    # 早间计划推送（每天 07:00）
    job_queue.run_daily(
        daily_plan_job,
        time=time(7, 0),
        name="morning_plan",
    )

    # 周六测试提醒（周六 07:30）
    job_queue.run_daily(
        saturday_test_reminder,
        time=time(7, 30),
        days=(5,),  # Saturday
        name="saturday_test",
    )

    # 错题复习提醒（每天 12:00）
    job_queue.run_daily(
        error_review_reminder,
        time=time(12, 0),
        name="error_review",
    )

    # 晚间总结提醒（每天 21:30）
    job_queue.run_daily(
        daily_summary_reminder,
        time=time(21, 30),
        name="evening_summary",
    )

    logger.info("✅ 定时任务已设置：")
    logger.info("   🕖 每日07:00 — 推送学习计划")
    logger.info("   🕢 周六07:30 — 周测提醒")
    logger.info("   🕛 每日12:00 — 错题复习提醒")
    logger.info("   🕤 每日21:30 — 晚间总结提醒")
