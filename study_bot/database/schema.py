"""
数据库表定义与初始化
"""

import sqlite3
import aiosqlite
from study_bot.config import DATABASE_PATH, DEFAULT_REMINDER_TIME, DEFAULT_SUMMARY_TIME, DEFAULT_DAILY_HOURS

SCHEMA_SQL = """
-- 用户表
CREATE TABLE IF NOT EXISTS users (
    user_id         INTEGER PRIMARY KEY,
    username        TEXT,
    first_name      TEXT,
    target_univ     TEXT DEFAULT '太原理工大学',
    daily_hours     INTEGER DEFAULT 6,
    reminder_time   TEXT DEFAULT '07:00',
    summary_time    TEXT DEFAULT '21:30',
    exam_date       TEXT DEFAULT '2027-03-20',
    timezone_offset INTEGER DEFAULT 8,
    is_active       INTEGER DEFAULT 1,
    onboarding_done INTEGER DEFAULT 0,
    plan_paused     INTEGER DEFAULT 0,
    study_mode      TEXT DEFAULT 'zhuanshengben',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 科目表
CREATE TABLE IF NOT EXISTS subjects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    category    TEXT NOT NULL,
    max_score   INTEGER NOT NULL
);

-- 章节表
CREATE TABLE IF NOT EXISTS chapters (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id  INTEGER REFERENCES subjects(id),
    name        TEXT NOT NULL,
    importance  INTEGER DEFAULT 3,
    difficulty  INTEGER DEFAULT 3,
    status      TEXT DEFAULT ''
);

-- 用户章节掌握度
CREATE TABLE IF NOT EXISTS user_chapter_mastery (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id          INTEGER REFERENCES users(user_id),
    chapter_id       INTEGER REFERENCES chapters(id),
    mastery_level    REAL DEFAULT 0.0,
    last_reviewed    TIMESTAMP,
    review_count     INTEGER DEFAULT 0,
    consecutive_ok   INTEGER DEFAULT 0,
    UNIQUE(user_id, chapter_id)
);

-- 每日学习计划
CREATE TABLE IF NOT EXISTS study_plans (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER REFERENCES users(user_id),
    date         TEXT NOT NULL,
    plan_json    TEXT NOT NULL,
    is_completed INTEGER DEFAULT 0,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 每日学习日志
CREATE TABLE IF NOT EXISTS study_logs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER REFERENCES users(user_id),
    date           TEXT NOT NULL,
    subject_id     INTEGER REFERENCES subjects(id),
    chapter_id     INTEGER REFERENCES chapters(id),
    time_spent_min INTEGER,
    self_rating    INTEGER,
    notes          TEXT,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 知识点评估记录
CREATE TABLE IF NOT EXISTS assessments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER REFERENCES users(user_id),
    date        TEXT NOT NULL,
    subject_id  INTEGER REFERENCES subjects(id),
    result_json TEXT NOT NULL,
    ai_feedback TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 连续学习记录
CREATE TABLE IF NOT EXISTS study_streaks (
    user_id         INTEGER PRIMARY KEY REFERENCES users(user_id),
    current_streak  INTEGER DEFAULT 0,
    longest_streak  INTEGER DEFAULT 0,
    last_study_date TEXT
);

-- 错题本
CREATE TABLE IF NOT EXISTS error_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER REFERENCES users(user_id),
    date            TEXT NOT NULL,
    subject_id      INTEGER REFERENCES subjects(id),
    chapter_id      INTEGER REFERENCES chapters(id),
    question        TEXT,
    wrong_answer    TEXT,
    correct_answer  TEXT,
    solution        TEXT,
    knowledge_point TEXT,
    review_count    INTEGER DEFAULT 0,
    last_reviewed   TEXT,
    mastered        INTEGER DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 周测记录
CREATE TABLE IF NOT EXISTS test_records (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER REFERENCES users(user_id),
    date            TEXT NOT NULL,
    subject_id      INTEGER REFERENCES subjects(id),
    score           REAL,
    max_score       REAL,
    test_content    TEXT,
    grading_result  TEXT,
    weak_points     TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 用户日程设置
CREATE TABLE IF NOT EXISTS user_schedule (
    user_id         INTEGER PRIMARY KEY REFERENCES users(user_id),
    -- 每周各天类型: mon,tue,wed,thu,fri,sat,sun → class/free/holiday
    mon_type        TEXT DEFAULT 'class',
    tue_type        TEXT DEFAULT 'class',
    wed_type        TEXT DEFAULT 'class',
    thu_type        TEXT DEFAULT 'class',
    fri_type        TEXT DEFAULT 'class',
    sat_type        TEXT DEFAULT 'test',
    sun_type        TEXT DEFAULT 'rest',
    -- 是否处于假期模式
    is_holiday      INTEGER DEFAULT 0,
    -- 开学日期（假期结束后自动恢复上课日安排）
    school_start_date TEXT,
    -- 假期结束日期
    holiday_end_date TEXT,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 研究生模式状态表
CREATE TABLE IF NOT EXISTS graduate_mode (
    user_id                INTEGER PRIMARY KEY REFERENCES users(user_id),
    is_active              INTEGER DEFAULT 0,
    started_at             TEXT,
    target_completion_date TEXT,
    total_modules          INTEGER DEFAULT 5,
    completed_modules      INTEGER DEFAULT 0,
    mastery_threshold      REAL DEFAULT 0.75,
    created_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def get_sync_conn() -> sqlite3.Connection:
    """获取同步数据库连接（用于初始化）"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


async def get_conn() -> aiosqlite.Connection:
    """获取异步数据库连接"""
    conn = await aiosqlite.connect(DATABASE_PATH)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA foreign_keys=ON")
    return conn


async def init_db():
    """初始化数据库：建表 + 预置数据"""
    conn = await get_conn()
    try:
        await conn.executescript(SCHEMA_SQL)
        await conn.commit()
    finally:
        await conn.close()
    await migrate_add_chapter_status()
    await migrate_add_study_mode()


async def migrate_add_chapter_status():
    """迁移：为旧数据库的 chapters 表添加 status 列（如果缺失）"""
    conn = await get_conn()
    try:
        cursor = await conn.execute("PRAGMA table_info(chapters)")
        columns = [row[1] for row in await cursor.fetchall()]
        if "status" not in columns:
            await conn.execute("ALTER TABLE chapters ADD COLUMN status TEXT DEFAULT ''")
            await conn.commit()
    finally:
        await conn.close()


async def migrate_add_study_mode():
    """迁移：为旧数据库的 users 表添加 study_mode 列（如果缺失）"""
    conn = await get_conn()
    try:
        cursor = await conn.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in await cursor.fetchall()]
        if "study_mode" not in columns:
            await conn.execute("ALTER TABLE users ADD COLUMN study_mode TEXT DEFAULT 'zhuanshengben'")
            await conn.commit()
    finally:
        await conn.close()
