"""
山西专升本学习助手 v2 — Telegram Bot 入口
电气工程及其自动化 | 电路分析 + 英语 + 高等数学
新增：多AI提供商、分数线预测、周测系统、拍照搜题、错题管理、政策监控
"""

import asyncio
import logging
import sys
import os as _os # 重命名 os 避免与 os.environ 冲突

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from study_bot.config import TELEGRAM_BOT_TOKEN, AI_ENABLED, get_active_provider
from study_bot.database.schema import init_db
from study_bot.database.ops import seed_subjects_and_chapters
from study_bot.services.error_tracker import init_error_db

from study_bot.bot_handlers import register_command_handlers

# 对话处理器
from study_bot.handlers.conversations import (
    ONBOARD_TARGET, ONBOARD_HOURS, ONBOARD_TIME, ONBOARD_PROGRESS,
    onboard_entry,
    LOG_SELECT_SUBJECT, LOG_SELECT_CHAPTER, LOG_INPUT_TIME, LOG_INPUT_RATING, LOG_INPUT_NOTES,
    log_entry,
    ASSESS_SUBJECT, ASSESS_CHAPTER, ASSESS_SCORE,
    assess_entry,
    TESTFB_SUBJECT, TESTFB_SCORE, TESTFB_WRONG, TESTFB_CONFIRM,
    testfb_entry,
    DIAG_CONFIRM, DIAG_FEEDBACK, DIAG_WRONG, DIAG_NEXT,
    diag_entry,
    stop_diag_command,
    start_plan_command,
    diag_rounds_command,
)
from study_bot.handlers.callbacks import (
    onboarding_callback,
    log_callback,
    log_time_input,
    log_rating_callback,
    assess_callback,
    testfb_callback,
    testfb_score_input,
    testfb_wrong_input,
    testfb_confirm_callback,
    diag_callback,
    diag_score_input,
    diag_wrong_input,
    # v3 新增
    graduate_callback,
    difficulty_callback,
    knowledge_point_callback,
)
from study_bot.services.scheduler import setup_scheduler # 保留导入，但在 FC 中注释掉调用

# 修复 Windows GBK 编码问题
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# 日志文件路径 (在 FC 中可能不需要本地文件日志，通常直接输出到控制台)
_LOG_DIR = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), "logs")
_os.makedirs(_LOG_DIR, exist_ok=True)
_LOG_FILE = _os.path.join(_LOG_DIR, "bot.log")

# 日志配置（同时输出到控制台和文件，FC 环境下建议只输出到控制台）
# For FC, consider removing FileHandler if it's not needed for persistent logging.
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
        # logging.FileHandler(_LOG_FILE, encoding="utf-8"), # Comment out for FC
    ],
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


async def get_application() -> Application:
    """Initializes and returns the Telegram Bot Application instance.
    This function prepares the bot for Webhook mode in serverless environments.
    """

    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("=" * 50)
        logger.error("❌ 请先配置 TELEGRAM_BOT_TOKEN！")
        logger.error("   方法1: 在 config.py 中直接设置 TELEGRAM_BOT_TOKEN")
        logger.error("   方法2: 创建 .env 文件，添加 TELEGRAM_BOT_TOKEN=你的token")
        logger.error("=" * 50)
        sys.exit(1)

    # 数据库和错误追踪器初始化
    logger.info("正在初始化数据库...")
    await init_db()
    await seed_subjects_and_chapters()
    await init_error_db()
    logger.info("✅ 数据库初始化完成")

    provider = get_active_provider()
    if AI_ENABLED:
        logger.info(f"🤖 AI 分析已启用，当前提供商：{provider}")
    else:
        logger.warning("⚠️ 未配置任何 AI API Key，AI 功能将降级为纯规则模式")
        logger.warning("   请在 .env 中配置 DEEPSEEK_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY")

    # 创建 Application
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # ========================================
    # 注册命令处理器（单步命令）
    # 注意：/start 由下面的 ConversationHandler 统一处理，不在此单独注册
    register_command_handlers(app)
    # ========================================

    # ========================================
    # 注册回调处理器（Inline Button Callbacks）
    # ========================================
    # 周测试卷选择
    app.add_handler(CallbackQueryHandler(weekly_test_callback, pattern="^weeklytest_"))
    # 日程设置
    app.add_handler(CallbackQueryHandler(set_schedule_callback, pattern="^setschedule_"))
    # v3 新增
    app.add_handler(CallbackQueryHandler(graduate_callback, pattern="^grad_"))
    app.add_handler(CallbackQueryHandler(difficulty_callback, pattern="^difficulty_"))
    app.add_handler(CallbackQueryHandler(knowledge_point_callback, pattern="^kpquestion_"))

    # ========================================
    # 注册照片处理器（拍照搜题 / 提交答案）
    # ========================================
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # ========================================
    # 注册多步对话处理器
    # ========================================

    # 入门引导对话
    onboard_conv = ConversationHandler(
        entry_points=[CommandHandler("start", onboard_entry)],
        states={
            ONBOARD_TARGET:   [CallbackQueryHandler(onboarding_callback)],
            ONBOARD_HOURS:    [CallbackQueryHandler(onboarding_callback)],
            ONBOARD_TIME:     [CallbackQueryHandler(onboarding_callback)],
            ONBOARD_PROGRESS: [CallbackQueryHandler(onboarding_callback)],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
    )
    app.add_handler(onboard_conv)

    # 学习日志对话
    log_conv = ConversationHandler(
        entry_points=[CommandHandler("log", log_entry)],
        states={
            LOG_SELECT_SUBJECT: [CallbackQueryHandler(log_callback)],
            LOG_SELECT_CHAPTER: [CallbackQueryHandler(log_callback)],
            LOG_INPUT_TIME:     [MessageHandler(filters.TEXT & ~filters.COMMAND, log_time_input)],
            LOG_INPUT_RATING:   [CallbackQueryHandler(log_rating_callback)],
            LOG_INPUT_NOTES:    [MessageHandler(filters.TEXT & ~filters.COMMAND, log_time_input)],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
    )
    app.add_handler(log_conv)

    # 知识点评估对话
    assess_conv = ConversationHandler(
        entry_points=[CommandHandler("assess", assess_entry)],
        states={
            ASSESS_SUBJECT: [CallbackQueryHandler(assess_callback)],
            ASSESS_CHAPTER: [CallbackQueryHandler(assess_callback)],
            ASSESS_SCORE:   [CallbackQueryHandler(assess_callback)],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
    )
    app.add_handler(assess_conv)

    # 考试反馈对话（多轮测试→反馈→计划调整）
    testfb_conv = ConversationHandler(
        entry_points=[CommandHandler("test_feedback", testfb_entry)],
        states={
            TESTFB_SUBJECT:  [CallbackQueryHandler(testfb_callback)],
            TESTFB_SCORE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, testfb_score_input)],
            TESTFB_WRONG:    [MessageHandler(filters.TEXT & ~filters.COMMAND, testfb_wrong_input)],
            TESTFB_CONFIRM:  [CallbackQueryHandler(testfb_confirm_callback)],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
    )
    app.add_handler(testfb_conv)

    # 诊断性多轮测试对话（5轮出题→反馈→计划）
    diag_conv = ConversationHandler(
        entry_points=[CommandHandler("diagnostic", diag_entry)],
        states={
            DIAG_CONFIRM:  [CallbackQueryHandler(diag_callback)],
            DIAG_FEEDBACK: [MessageHandler(filters.TEXT & ~filters.COMMAND, diag_score_input)],
            DIAG_WRONG:    [MessageHandler(filters.TEXT & ~filters.COMMAND, diag_wrong_input)],
            DIAG_NEXT:     [CallbackQueryHandler(diag_callback)],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
    )
    app.add_handler(diag_conv)

    # ========================================
    # 注册文本消息处理器
    # ========================================
    # v3: 知识点专项出题（"XXX知识点不会" 等）——必须在通用"不会"之前
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Regex(r'(.+)知识点不会|(.+?)搞不懂|(.+?)学不明白'),
        handle_knowledge_point_request,
    ))
    # 错题复习回复
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Regex(r'(会了|掌握了|不会|没懂)'),
        handle_text_message,
    ))

    # 错题反馈处理器（"错了 1,3,5"）
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Regex(r'错了'),
        handle_test_error_feedback,
    ))

    # ========================================
    # 设置定时任务
    # ========================================
    # 注意：在无服务器（如阿里云函数计算）环境中，APScheduler 定时任务不会按预期工作。
    # 您需要使用云服务提供商的定时任务功能（如阿里云的定时触发器）来触发单独的函数。
    # setup_scheduler(app)
    logger.info("⚙️ Telegram Bot Application 设置完成。")
    return app