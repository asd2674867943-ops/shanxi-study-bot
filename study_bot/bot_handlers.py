
from telegram.ext import CommandHandler

# 命令处理器
from study_bot.handlers.commands import (
    start_command,
    plan_command,
    log_command,
    summary_command,
    progress_command,
    help_command,
    cancel_command,
    score_line_command,
    weekly_test_command,
    weekly_test_callback,
    solve_command,
    handle_photo,
    errors_command,
    review_errors_command,
    policy_command,
    timeline_command,
    schedule_command,
    set_schedule_command,
    set_schedule_callback,
    handle_text_message,
    handle_test_error_feedback,
    pause_command,
    resume_command,
    submit_test_command,
    # v3 新增
    graduate_command,
    taiyuan_info_command,
    handle_knowledge_point_request,
)

from study_bot.handlers.conversations import (
    stop_diag_command,
    start_plan_command,
    diag_rounds_command,
)


def register_command_handlers(app):
    # ========================================
    # 注册命令处理器（单步命令）
    # 注意：/start 由下面的 ConversationHandler 统一处理，不在此单独注册
    # ========================================
    app.add_handler(CommandHandler("plan", plan_command))
    app.add_handler(CommandHandler("summary", summary_command))
    app.add_handler(CommandHandler("progress", progress_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("cancel", cancel_command))

    # --- v2 新增命令 ---
    app.add_handler(CommandHandler("score_line", score_line_command))
    app.add_handler(CommandHandler("weekly_test", weekly_test_command))
    app.add_handler(CommandHandler("solve", solve_command))
    app.add_handler(CommandHandler("errors", errors_command))
    app.add_handler(CommandHandler("review_errors", review_errors_command))
    app.add_handler(CommandHandler("policy", policy_command))
    app.add_handler(CommandHandler("timeline", timeline_command))
    app.add_handler(CommandHandler("schedule", schedule_command))
    app.add_handler(CommandHandler("set_schedule", set_schedule_command))
    app.add_handler(CommandHandler("pause", pause_command))
    app.add_handler(CommandHandler("resume", resume_command))
    app.add_handler(CommandHandler("submit_test", submit_test_command))
    app.add_handler(CommandHandler("stop_diag", stop_diag_command))
    app.add_handler(CommandHandler("start_plan", start_plan_command))
    app.add_handler(CommandHandler("diag_rounds", diag_rounds_command))
    # v3 新增
    app.add_handler(CommandHandler("graduate", graduate_command))
    app.add_handler(CommandHandler("taiyuan_info", taiyuan_info_command))
