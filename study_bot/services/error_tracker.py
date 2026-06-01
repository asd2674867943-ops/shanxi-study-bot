"""
错题收集与复习提醒系统
追踪错误题目 → 定期提醒复习 → 融入学习计划
"""

import json
from datetime import date, datetime, timedelta
from typing import List, Optional

from study_bot.database.schema import get_conn
from study_bot.database.ops import (
    get_all_subjects,
    get_chapters_by_subject,
    add_study_log,
    update_mastery,
    get_user_mastery,
)


async def init_error_db():
    """初始化错题表"""
    conn = await get_conn()
    try:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS error_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER REFERENCES users(user_id),
                date        TEXT NOT NULL,
                subject_id  INTEGER REFERENCES subjects(id),
                chapter_id  INTEGER REFERENCES chapters(id),
                question    TEXT,
                wrong_answer TEXT,
                correct_answer TEXT,
                solution    TEXT,
                knowledge_point TEXT,
                review_count INTEGER DEFAULT 0,
                last_reviewed TEXT,
                mastered    INTEGER DEFAULT 0,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.commit()
    finally:
        await conn.close()


async def add_error(
    user_id: int,
    subject_id: int,
    chapter_id: int,
    question: str,
    wrong_answer: str = "",
    correct_answer: str = "",
    solution: str = "",
    knowledge_point: str = "",
) -> int:
    """添加一条错题记录"""
    conn = await get_conn()
    try:
        cursor = await conn.execute(
            """INSERT INTO error_log
               (user_id, date, subject_id, chapter_id, question, wrong_answer,
                correct_answer, solution, knowledge_point)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id, date.today().isoformat(), subject_id, chapter_id,
                question, wrong_answer, correct_answer, solution, knowledge_point,
            ),
        )
        await conn.commit()
        return cursor.lastrowid
    finally:
        await conn.close()


async def get_errors(
    user_id: int,
    subject_id: int = None,
    chapter_id: int = None,
    mastered: bool = None,
    limit: int = 50,
) -> List[dict]:
    """获取错题列表，可按科目/章节/掌握状态过滤"""
    conn = await get_conn()
    try:
        query = """
            SELECT el.*, s.name as subject_name, c.name as chapter_name
            FROM error_log el
            JOIN subjects s ON el.subject_id = s.id
            JOIN chapters c ON el.chapter_id = c.id
            WHERE el.user_id = ?
        """
        params = [user_id]

        if subject_id is not None:
            query += " AND el.subject_id = ?"
            params.append(subject_id)
        if chapter_id is not None:
            query += " AND el.chapter_id = ?"
            params.append(chapter_id)
        if mastered is not None:
            query += " AND el.mastered = ?"
            params.append(1 if mastered else 0)

        query += " ORDER BY el.created_at DESC LIMIT ?"
        params.append(limit)

        cursor = await conn.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def get_errors_due_for_review(
    user_id: int,
    limit: int = 10,
) -> List[dict]:
    """获取需要复习的错题（按复习间隔）"""
    conn = await get_conn()
    try:
        today = date.today()

        cursor = await conn.execute(
            """SELECT el.*, s.name as subject_name, c.name as chapter_name
               FROM error_log el
               JOIN subjects s ON el.subject_id = s.id
               JOIN chapters c ON el.chapter_id = c.id
               WHERE el.user_id = ? AND el.mastered = 0
               ORDER BY
                   CASE
                       WHEN el.last_reviewed IS NULL THEN 0
                       WHEN el.review_count = 0 THEN 1
                       WHEN el.review_count = 1 THEN 2
                       WHEN el.review_count >= 2 THEN 3
                   END,
                   el.last_reviewed ASC
               LIMIT ?""",
            (user_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def mark_error_reviewed(error_id: int, mastered: bool = False):
    """标记错题已复习"""
    conn = await get_conn()
    try:
        today = date.today().isoformat()
        if mastered:
            await conn.execute(
                "UPDATE error_log SET mastered = 1, last_reviewed = ? WHERE id = ?",
                (today, error_id),
            )
        else:
            await conn.execute(
                """UPDATE error_log
                   SET review_count = review_count + 1,
                       last_reviewed = ?
                   WHERE id = ?""",
                (today, error_id),
            )
        await conn.commit()
    finally:
        await conn.close()


async def get_error_stats(user_id: int) -> dict:
    """获取错题统计"""
    conn = await get_conn()
    try:
        # 总错题数
        cursor = await conn.execute(
            "SELECT COUNT(*) as total FROM error_log WHERE user_id = ?",
            (user_id,),
        )
        total = (await cursor.fetchone())["total"]

        # 已掌握
        cursor = await conn.execute(
            "SELECT COUNT(*) as mastered FROM error_log WHERE user_id = ? AND mastered = 1",
            (user_id,),
        )
        mastered_count = (await cursor.fetchone())["mastered"]

        # 本周新增
        today = date.today()
        week_ago = (today - timedelta(days=7)).isoformat()
        cursor = await conn.execute(
            "SELECT COUNT(*) as week_new FROM error_log WHERE user_id = ? AND date >= ?",
            (user_id, week_ago),
        )
        week_new = (await cursor.fetchone())["week_new"]

        # 按科目统计
        cursor = await conn.execute(
            """SELECT s.name as subject_name, COUNT(*) as count
               FROM error_log el
               JOIN subjects s ON el.subject_id = s.id
               WHERE el.user_id = ? AND el.mastered = 0
               GROUP BY el.subject_id
               ORDER BY count DESC""",
            (user_id,),
        )
        by_subject = [dict(r) for r in await cursor.fetchall()]

        # 高频错误知识点
        cursor = await conn.execute(
            """SELECT chapter_id, c.name as chapter_name, COUNT(*) as count
               FROM error_log el
               JOIN chapters c ON el.chapter_id = c.id
               WHERE el.user_id = ? AND el.mastered = 0
               GROUP BY el.chapter_id
               ORDER BY count DESC
               LIMIT 5""",
            (user_id,),
        )
        top_chapters = [dict(r) for r in await cursor.fetchall()]

        return {
            "total": total,
            "mastered": mastered_count,
            "unmastered": total - mastered_count,
            "week_new": week_new,
            "by_subject": by_subject,
            "top_error_chapters": top_chapters,
            "mastery_rate": round(mastered_count / max(1, total) * 100, 1),
        }
    finally:
        await conn.close()


def format_error_stats(stats: dict) -> str:
    """格式化错题统计"""
    total = stats["total"]
    mastered = stats["mastered"]
    rate = stats["mastery_rate"]

    lines = [
        "📊 错题统计",
        "",
        f"📝 总错题数：{total}",
        f"✅ 已掌握：{mastered} ({rate}%)",
        f"🆕 本周新增：{stats['week_new']}",
        f"⚠️ 待攻克：{stats['unmastered']}",
        "",
    ]

    if stats["top_error_chapters"]:
        lines.append("🔴 高频错误章节：")
        for item in stats["top_error_chapters"][:5]:
            lines.append(f"   {item['count']}题 → {item['chapter_name']}")

    lines.append("")
    if stats["unmastered"] > 0:
        lines.append(f"💡 还有{stats['unmastered']}道错题等待复习，今天要看看吗？")
        lines.append("   使用 /review_errors 开始复习错题")
    elif total > 0:
        lines.append("🎉 所有错题都已掌握！继续保持！")
    else:
        lines.append("📌 还没有错题记录，开始学习吧！")

    return "\n".join(lines)


def format_error_for_review(error: dict, index: int, show_answer: bool = False) -> str:
    """格式化单道错题供复习"""
    lines = [
        f"📝 错题 {index}",
        f"📚 {error['subject_name']} → {error['chapter_name']}",
        f"📅 记录日期：{error.get('date', '未知')}",
        f"",
        f"❓ 题目：",
        f"{error.get('question', '无题目内容')[:300]}",
    ]

    if error.get("wrong_answer"):
        lines.append(f"")
        lines.append(f"❌ 你的答案：")
        lines.append(f"{error['wrong_answer'][:200]}")

    if show_answer:
        lines.append(f"")
        lines.append(f"✅ 正确答案：")
        lines.append(f"{error.get('correct_answer', '暂无')[:300]}")
        if error.get("solution"):
            lines.append(f"")
            lines.append(f"📖 解析：")
            lines.append(f"{error['solution'][:300]}")

    lines.append(f"")
    lines.append(f"📌 知识点：{error.get('knowledge_point', '未标注')}")
    lines.append(f"🔄 已复习：{error.get('review_count', 0)}次")

    return "\n".join(lines)
