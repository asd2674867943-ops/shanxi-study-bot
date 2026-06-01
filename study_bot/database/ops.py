"""
数据库 CRUD 操作
"""

import json
from datetime import date, datetime
from typing import Optional, List

from study_bot.database.schema import get_conn
from study_bot.data.preset import SUBJECTS, CHAPTERS


# ============================================================
# 初始化：预置科目和章节
# ============================================================

async def seed_subjects_and_chapters():
    """插入预置的科目和章节（幂等操作）"""
    conn = await get_conn()
    try:
        for subj in SUBJECTS:
            cursor = await conn.execute(
                "SELECT id FROM subjects WHERE name = ?", (subj["name"],)
            )
            row = await cursor.fetchone()
            if row is None:
                cursor = await conn.execute(
                    "INSERT INTO subjects (name, category, max_score) VALUES (?, ?, ?)",
                    (subj["name"], subj["category"], subj["max_score"]),
                )
                subject_id = cursor.lastrowid
            else:
                subject_id = row[0]

            # 插入该科目的章节
            for ch in CHAPTERS.get(subj["name"], []):
                cursor = await conn.execute(
                    "SELECT id FROM chapters WHERE subject_id = ? AND name = ?",
                    (subject_id, ch["name"]),
                )
                existing = await cursor.fetchone()
                if existing is None:
                    await conn.execute(
                        "INSERT INTO chapters (subject_id, name, importance, difficulty, status) VALUES (?, ?, ?, ?, ?)",
                        (subject_id, ch["name"], ch["importance"], ch["difficulty"], ch.get("status", "")),
                    )
                else:
                    # 补充 status（旧数据迁移）
                    await conn.execute(
                        "UPDATE chapters SET status = ? WHERE id = ?",
                        (ch.get("status", ""), existing[0]),
                    )
        await conn.commit()
    finally:
        await conn.close()


# ============================================================
# 用户操作
# ============================================================

async def get_or_create_user(user_id: int, username: str = None, first_name: str = None) -> dict:
    """获取或创建用户"""
    conn = await get_conn()
    try:
        cursor = await conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if row is None:
            await conn.execute(
                "INSERT INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
                (user_id, username, first_name),
            )
            await conn.commit()
            cursor = await conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
        return dict(row)
    finally:
        await conn.close()


async def update_user(user_id: int, **kwargs) -> None:
    """更新用户字段"""
    if not kwargs:
        return
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [user_id]
    conn = await get_conn()
    try:
        await conn.execute(f"UPDATE users SET {sets} WHERE user_id = ?", values)
        await conn.commit()
    finally:
        await conn.close()


async def get_user(user_id: int) -> Optional[dict]:
    """获取用户信息"""
    conn = await get_conn()
    try:
        cursor = await conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await conn.close()


async def get_active_users() -> List[dict]:
    """获取所有活跃用户"""
    conn = await get_conn()
    try:
        cursor = await conn.execute("SELECT * FROM users WHERE is_active = 1")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


# ============================================================
# 科目与章节查询
# ============================================================

async def get_all_subjects() -> List[dict]:
    """获取所有科目"""
    conn = await get_conn()
    try:
        cursor = await conn.execute("SELECT * FROM subjects ORDER BY id")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def get_chapters_by_subject(subject_id: int) -> List[dict]:
    """获取某科目的所有章节"""
    conn = await get_conn()
    try:
        cursor = await conn.execute(
            "SELECT id, subject_id, name, importance, difficulty, status FROM chapters WHERE subject_id = ? ORDER BY id", (subject_id,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def get_chapter(chapter_id: int) -> Optional[dict]:
    """获取单个章节"""
    conn = await get_conn()
    try:
        cursor = await conn.execute("SELECT * FROM chapters WHERE id = ?", (chapter_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await conn.close()


# ============================================================
# 章节掌握度
# ============================================================

async def get_user_mastery(user_id: int, subject_id: int = None) -> List[dict]:
    """获取用户所有章节掌握度，可按科目过滤"""
    conn = await get_conn()
    try:
        if subject_id:
            cursor = await conn.execute(
                """SELECT ucm.*, c.name as chapter_name, c.subject_id, c.importance, c.difficulty, c.status,
                          s.name as subject_name, s.max_score
                   FROM user_chapter_mastery ucm
                   JOIN chapters c ON ucm.chapter_id = c.id
                   JOIN subjects s ON c.subject_id = s.id
                   WHERE ucm.user_id = ? AND c.subject_id = ?
                   ORDER BY c.id""",
                (user_id, subject_id),
            )
        else:
            cursor = await conn.execute(
                """SELECT ucm.*, c.name as chapter_name, c.subject_id, c.importance, c.difficulty, c.status,
                          s.name as subject_name, s.max_score
                   FROM user_chapter_mastery ucm
                   JOIN chapters c ON ucm.chapter_id = c.id
                   JOIN subjects s ON c.subject_id = s.id
                   WHERE ucm.user_id = ?
                   ORDER BY c.id""",
                (user_id,),
            )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def init_user_mastery(user_id: int):
    """为新用户初始化所有章节掌握度（全部为0）"""
    conn = await get_conn()
    try:
        cursor = await conn.execute("SELECT id FROM chapters")
        chapters = await cursor.fetchall()

        for ch in chapters:
            await conn.execute(
                """INSERT OR IGNORE INTO user_chapter_mastery
                   (user_id, chapter_id, mastery_level, review_count, consecutive_ok)
                   VALUES (?, ?, 0.0, 0, 0)""",
                (user_id, ch["id"]),
            )
        await conn.commit()
    finally:
        await conn.close()


async def update_mastery(user_id: int, chapter_id: int, mastery_level: float):
    """更新章节掌握度"""
    conn = await get_conn()
    try:
        now = datetime.now().isoformat()
        # 获取当前数据
        cursor = await conn.execute(
            "SELECT * FROM user_chapter_mastery WHERE user_id = ? AND chapter_id = ?",
            (user_id, chapter_id),
        )
        row = await cursor.fetchone()
        if row:
            new_review_count = row["review_count"] + 1
            # 连续高分判断(>0.6)
            consecutive = row["consecutive_ok"] + 1 if mastery_level >= 0.6 else 0
            await conn.execute(
                """UPDATE user_chapter_mastery
                   SET mastery_level = ?, last_reviewed = ?, review_count = ?,
                       consecutive_ok = ?
                   WHERE user_id = ? AND chapter_id = ?""",
                (mastery_level, now, new_review_count, consecutive, user_id, chapter_id),
            )
        else:
            await conn.execute(
                """INSERT INTO user_chapter_mastery
                   (user_id, chapter_id, mastery_level, last_reviewed, review_count, consecutive_ok)
                   VALUES (?, ?, ?, ?, 1, ?)""",
                (user_id, chapter_id, mastery_level, now, 1 if mastery_level >= 0.6 else 0),
            )
        await conn.commit()
    finally:
        await conn.close()


# ============================================================
# 学习计划
# ============================================================

async def save_study_plan(user_id: int, date_str: str, plan: dict):
    """保存学习计划"""
    conn = await get_conn()
    try:
        # 如果当天已有计划，则更新
        cursor = await conn.execute(
            "SELECT id FROM study_plans WHERE user_id = ? AND date = ?",
            (user_id, date_str),
        )
        row = await cursor.fetchone()
        plan_json = json.dumps(plan, ensure_ascii=False)
        if row:
            await conn.execute(
                "UPDATE study_plans SET plan_json = ? WHERE id = ?",
                (plan_json, row["id"]),
            )
        else:
            await conn.execute(
                "INSERT INTO study_plans (user_id, date, plan_json) VALUES (?, ?, ?)",
                (user_id, date_str, plan_json),
            )
        await conn.commit()
    finally:
        await conn.close()


async def get_study_plan(user_id: int, date_str: str) -> Optional[dict]:
    """获取某天的学习计划"""
    conn = await get_conn()
    try:
        cursor = await conn.execute(
            "SELECT * FROM study_plans WHERE user_id = ? AND date = ?",
            (user_id, date_str),
        )
        row = await cursor.fetchone()
        if row:
            result = dict(row)
            result["plan"] = json.loads(result["plan_json"])
            return result
        return None
    finally:
        await conn.close()


async def mark_plan_completed(user_id: int, date_str: str):
    """标记计划完成"""
    conn = await get_conn()
    try:
        await conn.execute(
            "UPDATE study_plans SET is_completed = 1 WHERE user_id = ? AND date = ?",
            (user_id, date_str),
        )
        await conn.commit()
    finally:
        await conn.close()


# ============================================================
# 学习日志
# ============================================================

async def add_study_log(user_id: int, subject_id: int, chapter_id: int,
                        time_spent_min: int, self_rating: int, notes: str = None,
                        date_str: str = None) -> int:
    """添加学习日志，返回记录ID"""
    if date_str is None:
        date_str = date.today().isoformat()
    conn = await get_conn()
    try:
        cursor = await conn.execute(
            """INSERT INTO study_logs
               (user_id, date, subject_id, chapter_id, time_spent_min, self_rating, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, date_str, subject_id, chapter_id, time_spent_min, self_rating, notes),
        )
        await conn.commit()
        return cursor.lastrowid
    finally:
        await conn.close()


async def get_daily_logs(user_id: int, date_str: str = None) -> List[dict]:
    """获取某天的学习日志"""
    if date_str is None:
        date_str = date.today().isoformat()
    conn = await get_conn()
    try:
        cursor = await conn.execute(
            """SELECT sl.*, c.name as chapter_name, s.name as subject_name
               FROM study_logs sl
               JOIN chapters c ON sl.chapter_id = c.id
               JOIN subjects s ON sl.subject_id = s.id
               WHERE sl.user_id = ? AND sl.date = ?
               ORDER BY sl.id""",
            (user_id, date_str),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def get_weekly_logs(user_id: int) -> List[dict]:
    """获取本周学习日志"""
    from study_bot.utils.helpers import week_range
    start, end = week_range()
    conn = await get_conn()
    try:
        cursor = await conn.execute(
            """SELECT sl.*, c.name as chapter_name, s.name as subject_name
               FROM study_logs sl
               JOIN chapters c ON sl.chapter_id = c.id
               JOIN subjects s ON sl.subject_id = s.id
               WHERE sl.user_id = ? AND sl.date >= ? AND sl.date <= ?
               ORDER BY sl.date, sl.id""",
            (user_id, start, end),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def get_total_study_hours(user_id: int) -> int:
    """获取总学习时长（分钟）"""
    conn = await get_conn()
    try:
        cursor = await conn.execute(
            "SELECT COALESCE(SUM(time_spent_min), 0) FROM study_logs WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        return row[0]
    finally:
        await conn.close()


# ============================================================
# 评估记录
# ============================================================

async def save_assessment(user_id: int, subject_id: int, date_str: str,
                          results: list, ai_feedback: str = None):
    """保存评估记录"""
    conn = await get_conn()
    try:
        await conn.execute(
            """INSERT INTO assessments (user_id, date, subject_id, result_json, ai_feedback)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, date_str, subject_id, json.dumps(results, ensure_ascii=False), ai_feedback),
        )
        await conn.commit()
    finally:
        await conn.close()


async def get_latest_assessment(user_id: int, subject_id: int) -> Optional[dict]:
    """获取最近一次评估"""
    conn = await get_conn()
    try:
        cursor = await conn.execute(
            """SELECT * FROM assessments
               WHERE user_id = ? AND subject_id = ?
               ORDER BY date DESC LIMIT 1""",
            (user_id, subject_id),
        )
        row = await cursor.fetchone()
        if row:
            result = dict(row)
            result["results"] = json.loads(result["result_json"])
            return result
        return None
    finally:
        await conn.close()


# ============================================================
# 连续学习记录
# ============================================================

async def update_streak(user_id: int):
    """更新连续学习天数"""
    from study_bot.utils.helpers import today_str
    today = today_str()
    conn = await get_conn()
    try:
        cursor = await conn.execute(
            "SELECT * FROM study_streaks WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        if row:
            last_date = row["last_study_date"]
            if last_date == today:
                return  # 今天已记录

            # 判断是否连续
            from study_bot.utils.helpers import days_between
            if last_date and days_between(today, last_date) <= 1:
                new_streak = row["current_streak"] + 1
            else:
                new_streak = 1

            longest = max(row["longest_streak"], new_streak)
            await conn.execute(
                """UPDATE study_streaks
                   SET current_streak = ?, longest_streak = ?, last_study_date = ?
                   WHERE user_id = ?""",
                (new_streak, longest, today, user_id),
            )
        else:
            await conn.execute(
                """INSERT INTO study_streaks (user_id, current_streak, longest_streak, last_study_date)
                   VALUES (?, 1, 1, ?)""",
                (user_id, today),
            )
        await conn.commit()
    finally:
        await conn.close()


async def get_streak(user_id: int) -> dict:
    """获取连续学习数据"""
    conn = await get_conn()
    try:
        cursor = await conn.execute(
            "SELECT * FROM study_streaks WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        if row:
            return dict(row)
        return {"current_streak": 0, "longest_streak": 0, "last_study_date": None}
    finally:
        await conn.close()


# ============================================================
# 用户日程设置
# ============================================================

async def get_user_schedule(user_id: int) -> dict:
    """获取用户日程设置"""
    conn = await get_conn()
    try:
        cursor = await conn.execute(
            "SELECT * FROM user_schedule WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        if row:
            return dict(row)
        # 返回默认设置
        return {
            "mon_type": "class", "tue_type": "class", "wed_type": "class",
            "thu_type": "class", "fri_type": "class",
            "sat_type": "test", "sun_type": "rest",
            "is_holiday": 0,
        }
    finally:
        await conn.close()


async def set_user_schedule(user_id: int, **kwargs) -> None:
    """设置用户日程（Upsert）"""
    conn = await get_conn()
    try:
        cursor = await conn.execute(
            "SELECT user_id FROM user_schedule WHERE user_id = ?", (user_id,)
        )
        exists = await cursor.fetchone()

        if exists:
            sets = ", ".join(f"{k} = ?" for k in kwargs)
            values = list(kwargs.values()) + [user_id]
            await conn.execute(
                f"UPDATE user_schedule SET {sets}, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                values,
            )
        else:
            keys = ", ".join(kwargs.keys())
            placeholders = ", ".join("?" for _ in kwargs)
            await conn.execute(
                f"INSERT INTO user_schedule (user_id, {keys}) VALUES (?, {placeholders})",
                [user_id] + list(kwargs.values()),
            )
        await conn.commit()
    finally:
        await conn.close()


# ============================================================
# 周测记录
# ============================================================

async def save_test_record(
    user_id: int, subject_id: int, date_str: str,
    score: float, max_score: float,
    test_content: str = None, grading_result: str = None,
    weak_points: str = None,
) -> int:
    """保存周测记录"""
    conn = await get_conn()
    try:
        cursor = await conn.execute(
            """INSERT INTO test_records
               (user_id, date, subject_id, score, max_score, test_content, grading_result, weak_points)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, date_str, subject_id, score, max_score, test_content, grading_result, weak_points),
        )
        await conn.commit()
        return cursor.lastrowid
    finally:
        await conn.close()


async def get_test_history(user_id: int, subject_id: int = None, limit: int = 10) -> list:
    """获取测试历史"""
    conn = await get_conn()
    try:
        query = """
            SELECT tr.*, s.name as subject_name
            FROM test_records tr
            JOIN subjects s ON tr.subject_id = s.id
            WHERE tr.user_id = ?
        """
        params = [user_id]
        if subject_id:
            query += " AND tr.subject_id = ?"
            params.append(subject_id)
        query += " ORDER BY tr.date DESC LIMIT ?"
        params.append(limit)

        cursor = await conn.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


# ============================================================
# 学习暂停开关
# ============================================================

async def pause_plan(user_id: int):
    """暂停用户今日学习计划"""
    conn = await get_conn()
    try:
        await conn.execute("UPDATE users SET plan_paused = 1 WHERE user_id = ?", (user_id,))
        await conn.commit()
    finally:
        await conn.close()


async def resume_plan(user_id: int):
    """恢复用户学习计划"""
    conn = await get_conn()
    try:
        await conn.execute("UPDATE users SET plan_paused = 0 WHERE user_id = ?", (user_id,))
        await conn.commit()
    finally:
        await conn.close()


async def is_plan_paused(user_id: int) -> bool:
    """检查用户是否暂停了学习计划"""
    conn = await get_conn()
    try:
        cursor = await conn.execute("SELECT plan_paused FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return bool(row and row[0])
    finally:
        await conn.close()
