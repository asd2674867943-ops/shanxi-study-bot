"""
工具函数：日期计算、格式化等
"""

from datetime import datetime, date, timedelta
from typing import Optional


def today_str() -> str:
    """返回今天日期字符串 YYYY-MM-DD"""
    return date.today().isoformat()


def days_until(target_date: str) -> int:
    """计算距目标日期还有多少天"""
    target = datetime.strptime(target_date, "%Y-%m-%d").date()
    return max(0, (target - date.today()).days)


def days_between(date1: str, date2: Optional[str] = None) -> int:
    """计算两个日期之间的天数"""
    d1 = datetime.strptime(date1, "%Y-%m-%d").date()
    d2 = date.today() if date2 is None else datetime.strptime(date2, "%Y-%m-%d").date()
    return abs((d2 - d1).days)


def week_range() -> tuple[str, str]:
    """返回本周的起止日期"""
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday.isoformat(), sunday.isoformat()


def format_minutes(minutes: int) -> str:
    """将分钟格式化为可读字符串"""
    hours = minutes // 60
    mins = minutes % 60
    if hours > 0 and mins > 0:
        return f"{hours}小时{mins}分"
    elif hours > 0:
        return f"{hours}小时"
    else:
        return f"{mins}分钟"


def progress_bar(percentage: float, length: int = 10) -> str:
    """生成进度条"""
    pct = max(0.0, min(1.0, percentage))
    filled = int(pct * length)
    empty = length - filled
    return "█" * filled + "░" * empty


def format_percentage(value: float) -> str:
    """格式化为百分比"""
    return f"{value * 100:.0f}%"


def estimate_score(subject_score: int, mastery: float) -> int:
    """根据掌握度预估考试得分"""
    raw = subject_score * mastery
    # 考试时有发挥空间，加一些浮动
    return max(0, min(subject_score, int(raw * 1.1)))


def rank_emoji(level: float) -> str:
    """根据水平返回表情"""
    if level >= 0.8:
        return "🌟"
    elif level >= 0.6:
        return "👍"
    elif level >= 0.4:
        return "📖"
    elif level >= 0.2:
        return "🔰"
    else:
        return "⚠️"


def get_morning_greeting() -> str:
    """根据当前时间返回问候语"""
    hour = datetime.now().hour
    if hour < 6:
        return "凌晨好"
    elif hour < 9:
        return "早上好"
    elif hour < 12:
        return "上午好"
    elif hour < 14:
        return "中午好"
    elif hour < 18:
        return "下午好"
    else:
        return "晚上好"
