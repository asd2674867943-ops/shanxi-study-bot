"""
数据模型定义（dataclass）
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class User:
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    target_univ: str = "太原工业学院"
    daily_hours: int = 6
    reminder_time: str = "07:00"
    summary_time: str = "21:30"
    exam_date: str = "2027-03-20"
    timezone_offset: int = 8
    is_active: bool = True
    onboarding_done: bool = False
    created_at: Optional[str] = None


@dataclass
class Subject:
    id: int
    name: str
    category: str
    max_score: int


@dataclass
class Chapter:
    id: int
    subject_id: int
    name: str
    importance: int = 3
    difficulty: int = 3


@dataclass
class UserChapterMastery:
    id: int
    user_id: int
    chapter_id: int
    mastery_level: float = 0.0
    last_reviewed: Optional[str] = None
    review_count: int = 0
    consecutive_ok: int = 0


@dataclass
class StudyPlan:
    id: int
    user_id: int
    date: str
    plan_json: str
    is_completed: bool = False
    created_at: Optional[str] = None


@dataclass
class StudyLog:
    id: int
    user_id: int
    date: str
    subject_id: int
    chapter_id: int
    time_spent_min: int = 0
    self_rating: int = 0
    notes: Optional[str] = None
    created_at: Optional[str] = None


@dataclass
class Assessment:
    id: int
    user_id: int
    date: str
    subject_id: int
    result_json: str
    ai_feedback: Optional[str] = None
    created_at: Optional[str] = None


@dataclass
class StudyStreak:
    user_id: int
    current_streak: int = 0
    longest_streak: int = 0
    last_study_date: Optional[str] = None


@dataclass
class ErrorLog:
    """错题记录"""
    id: int
    user_id: int
    date: str
    subject_id: int
    chapter_id: int
    question: Optional[str] = None
    wrong_answer: Optional[str] = None
    correct_answer: Optional[str] = None
    solution: Optional[str] = None
    knowledge_point: Optional[str] = None
    review_count: int = 0
    last_reviewed: Optional[str] = None
    mastered: bool = False
    created_at: Optional[str] = None


@dataclass
class TestRecord:
    """周测记录"""
    id: int
    user_id: int
    date: str
    subject_id: int
    score: float = 0.0
    max_score: float = 100.0
    test_content: Optional[str] = None
    grading_result: Optional[str] = None
    weak_points: Optional[str] = None
    created_at: Optional[str] = None


@dataclass
class UserSchedule:
    """用户日程设置"""
    user_id: int
    mon_type: str = "class"
    tue_type: str = "class"
    wed_type: str = "class"
    thu_type: str = "class"
    fri_type: str = "class"
    sat_type: str = "test"
    sun_type: str = "rest"
    is_holiday: bool = False
    school_start_date: Optional[str] = None
    holiday_end_date: Optional[str] = None
    updated_at: Optional[str] = None
