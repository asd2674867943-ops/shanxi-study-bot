"""
配置管理模块 - 支持多AI提供商切换
所有敏感信息通过环境变量或在此文件配置
"""

import os
from dotenv import load_dotenv

_env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(_env_path)

# ============================================================
# AI 提供商配置（支持多种AI，可随时切换）
# ============================================================
# 优先级：DeepSeek > OpenAI > Anthropic Claude > 本地模型
# 设置对应的 API_KEY 即可启用该提供商
# 如果同时设置了多个，按优先级使用第一个可用的

AI_PROVIDER = os.getenv("AI_PROVIDER", "auto").lower()  # auto / anthropic / openai / deepseek

# Anthropic Claude
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

# OpenAI (ChatGPT / GPT-4o 等)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

# DeepSeek（国产高性价比，推荐国内用户使用）
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

# Google Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# 其他 OpenAI 兼容的 API（如 豆包、通义千问、Moonshot 等）
CUSTOM_API_KEY = os.getenv("CUSTOM_API_KEY", "")
CUSTOM_API_BASE_URL = os.getenv("CUSTOM_API_BASE_URL", "")
CUSTOM_MODEL = os.getenv("CUSTOM_MODEL", "")

# 是否启用 AI 分析（任一 API Key 配置了就算启用）
def _has_ai_key():
    return bool(
        (GEMINI_API_KEY and GEMINI_API_KEY not in ("YOUR_API_KEY_HERE", ""))
        or (ANTHROPIC_API_KEY and ANTHROPIC_API_KEY not in ("YOUR_API_KEY_HERE", ""))
        or (OPENAI_API_KEY and OPENAI_API_KEY not in ("YOUR_API_KEY_HERE", ""))
        or (DEEPSEEK_API_KEY and DEEPSEEK_API_KEY not in ("YOUR_API_KEY_HERE", ""))
        or (CUSTOM_API_KEY and CUSTOM_API_KEY not in ("YOUR_API_KEY_HERE", ""))
    )

AI_ENABLED = _has_ai_key()

# 当前使用的 AI 提供商（自动检测）
def get_active_provider() -> str:
    """返回当前活跃的 AI 提供商名称"""
    if AI_PROVIDER == "gemini" and GEMINI_API_KEY:
        return "gemini"
    if AI_PROVIDER == "anthropic" and ANTHROPIC_API_KEY:
        return "anthropic"
    if AI_PROVIDER == "openai" and OPENAI_API_KEY:
        return "openai"
    if AI_PROVIDER == "deepseek" and DEEPSEEK_API_KEY:
        return "deepseek"
    if AI_PROVIDER == "custom" and CUSTOM_API_KEY:
        return "custom"
    # auto 模式：按优先级自动选择
    if GEMINI_API_KEY and GEMINI_API_KEY not in ("YOUR_API_KEY_HERE", ""):
        return "gemini"
    if DEEPSEEK_API_KEY and DEEPSEEK_API_KEY not in ("YOUR_API_KEY_HERE", ""):
        return "deepseek"
    if OPENAI_API_KEY and OPENAI_API_KEY not in ("YOUR_API_KEY_HERE", ""):
        return "openai"
    if ANTHROPIC_API_KEY and ANTHROPIC_API_KEY not in ("YOUR_API_KEY_HERE", ""):
        return "anthropic"
    if CUSTOM_API_KEY and CUSTOM_API_KEY not in ("YOUR_API_KEY_HERE", ""):
        return "custom"
    return "none"


# ============================================================
# Telegram Bot 配置
# ============================================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# ============================================================
# 考试配置（山西专升本 电气工程及其自动化）
# ============================================================
EXAM_DATE_DEFAULT = "2027-03-20"  # 默认考试日期（预估每年3月中下旬）
EXAM_SUBJECTS = {
    "电路分析": {"category": "professional", "max_score": 150},
    "英语":     {"category": "public",      "max_score": 50},
    "高等数学": {"category": "public",      "max_score": 100},
}
EXAM_TOTAL_SCORE = 300

# ============================================================
# 太原工业学院 历年分数线（电气工程及其自动化）
# ============================================================
SCORE_LINE_HISTORY = {
    2021: 169.127042,
    2022: 217.135082,
    2023: 256.148108,
    2024: 239.132107,
    2025: 253.121132,
}

# 目标院校（默认太原工业学院）
DEFAULT_TARGET_UNIV = "太原工业学院"
DEFAULT_TARGET_SCORE = 260  # 建议比预测线高出10-20分以确保录取

# ============================================================
# 山西专升本相关信息
# ============================================================
SHANXI_EXAM_INFO = {
    "province": "山西省",
    "exam_name": "山西省普通高校专升本选拔考试",
    "exam_time": "每年3月中下旬（具体以省招考中心公告为准）",
    "official_site": "http://www.sxkszx.cn/",  # 山西招生考试网
    "major": "电气工程及其自动化",
    "subjects_detail": {
        "电路分析": {
            "max_score": 150,
            "reference_book": "《电路》（第5版）邱关源主编，高等教育出版社",
            "exam_type": "专业课（专业基础课）",
        },
        "英语": {
            "max_score": 50,
            "reference_book": "山西省专升本英语考试大纲词汇表",
            "exam_type": "公共课",
        },
        "高等数学": {
            "max_score": 100,
            "reference_book": "《高等数学》（第7版）同济大学数学系编，高等教育出版社",
            "exam_type": "公共课",
        },
    },
}

# 山西专升本政策公告抓取URL列表
POLICY_URLS = [
    "http://www.sxkszx.cn/news/zsbks/index.html",  # 山西招生考试网-专升本
    "https://www.sxkszx.cn/index.html",             # 山西招生考试网首页
]

# ============================================================
# 数据库配置
# ============================================================
# Render 挂载磁盘路径（数据持久化），本地开发则存在项目目录
_RENDER_DISK = os.environ.get("RENDER_DISK_PATH", "")
if _RENDER_DISK:
    DATABASE_PATH = os.path.join(_RENDER_DISK, "study_bot.db")
else:
    DATABASE_PATH = os.path.join(os.path.dirname(__file__), "study_bot.db")

# ============================================================
# 定时推送默认时间
# ============================================================
DEFAULT_REMINDER_TIME = "07:00"   # 早间学习计划推送
DEFAULT_SUMMARY_TIME = "21:30"    # 晚间总结提醒
DEFAULT_WEEKLY_TEST_TIME = "08:00"  # 周六测试推送时间

# ============================================================
# 学习计划配置
# ============================================================
CLASS_DAY_HOURS = 3               # 上课日最少学习时长
FREE_DAY_HOURS = 6                # 空闲日最少学习时长
TEST_DAY_HOURS = 4                # 周六测试日（含做题+复盘）
REST_DAY_HOURS = 0                # 周日休息
MIN_SESSION_MINUTES = 30          # 最短学习时段（分钟）
MAX_SESSION_MINUTES = 150         # 最长学习时段（分钟）

# 遗忘曲线参数
FORGET_DECAY_RATE = 0.05          # 遗忘衰减率
FORGET_THRESHOLD_DAYS = 7         # 超过此天数开始衰减

# 向后兼容
DEFAULT_DAILY_HOURS = FREE_DAY_HOURS

# ============================================================
# PDF 输出配置
# ============================================================
PDF_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
PDF_FONT_NAME = "SimSun"  # 宋体（中文支持）

# ============================================================
# 时区配置
# ============================================================
DEFAULT_TIMEZONE_OFFSET = 8       # UTC+8 北京时间

# ============================================================
# 研究生学习模式配置
# ============================================================
GRADUATE_MODE = {
    "mastery_threshold": 0.75,         # 需专升本章节掌握度 >= 75% 才能开启
    "daily_hours_target": 8,           # 研究生模式每日目标学习时长
    "estimated_completion_weeks": 16,  # 预估完成周数
    "modules": [
        {"name": "线性代数进阶（考研数学一难度）", "subject": "高等数学", "weight": 25},
        {"name": "概率论与数理统计进阶", "subject": "高等数学", "weight": 20},
        {"name": "电路理论深度分析（邱关源教材全本+考研真题）", "subject": "电路分析", "weight": 30},
        {"name": "信号与系统基础（研究生衔接）", "subject": "电路分析", "weight": 15},
        {"name": "学术英语阅读与写作", "subject": "英语", "weight": 10},
    ],
}

# ============================================================
# 难度级别配置
# ============================================================
DIFFICULTY_LEVELS = {
    "basic": {
        "label": "专升本基础",
        "emoji": "🟢",
        "description": "基础概念题为主，适合初学阶段",
        "prompt_difficulty": "基础",
        "mode": "zhuanshengben",
    },
    "advanced": {
        "label": "专升本进阶",
        "emoji": "🟡",
        "description": "综合应用题为主，适合冲刺阶段",
        "prompt_difficulty": "进阶",
        "mode": "zhuanshengben",
    },
    "grad_intro": {
        "label": "研究生入门",
        "emoji": "🟠",
        "description": "考研基础难度，衔接研究生学习",
        "prompt_difficulty": "研究生入门",
        "mode": "graduate",
    },
    "grad_advanced": {
        "label": "研究生进阶",
        "emoji": "🔴",
        "description": "考研真题难度，深度学术训练",
        "prompt_difficulty": "研究生进阶",
        "mode": "graduate",
    },
}

# ============================================================
# 太原工业学院官网抓取配置
# ============================================================
TAIYUAN_INSTITUTE_URLS = [
    "https://www.tit.edu.cn/",                    # 太原工业学院首页
    "https://www.tit.edu.cn/zsw/index.htm",       # 招生信息网
]

# ============================================================
# 考试倒计时提醒配置
# ============================================================
EXAM_COUNTDOWN_MILESTONES = [90, 60, 30, 14, 7, 3, 1]  # 距考试N天时发送提醒
