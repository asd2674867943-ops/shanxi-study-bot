"""
周测试卷生成与PDF输出
支持：数学、电路、英语 三科
生成试卷 → PDF → 答案分开发送
"""

import os
import json
import re
from datetime import date, datetime
from typing import Optional

from study_bot.config import PDF_OUTPUT_DIR
from study_bot.services.analyzer import generate_weekly_test, grade_photo_answer
from study_bot.database.ops import (
    get_user_mastery,
    get_chapters_by_subject,
    get_all_subjects,
    get_user,
    save_assessment,
)


# 确保输出目录存在
os.makedirs(PDF_OUTPUT_DIR, exist_ok=True)


async def create_weekly_test(
    user_id: int,
    subject_name: str,
    difficulty: str = "medium",
    question_count: int = 10,
) -> dict:
    """
    生成一份周测试卷
    返回 {"subject": str, "test_text": str, "answer_text": str, "file_path": str}
    """
    # 获取该科目的章节和掌握度
    subjects = await get_all_subjects()
    subject_id = None
    for s in subjects:
        if s["name"] == subject_name:
            subject_id = s["id"]
            break

    if subject_id is None:
        return {"error": f"未找到科目：{subject_name}"}

    # 获取章节掌握度
    mastery_list = await get_user_mastery(user_id, subject_id)
    chapters_info = []
    for m in mastery_list:
        chapters_info.append({
            "name": m["chapter_name"],
            "mastery": m.get("mastery_level", 0.0),
            "importance": m.get("importance", 3),
        })

    # 按掌握度排序，优先考察薄弱章节
    chapters_info.sort(key=lambda c: (c["mastery"], -c["importance"]))

    # AI 或规则生成测试
    test_raw = await generate_weekly_test(
        subject_name=subject_name,
        chapters=chapters_info,
        difficulty_level=difficulty,
        question_count=question_count,
    )

    # 解析试题和答案（AI输出中已包含答案部分）
    test_text, answer_text = _split_test_and_answer(test_raw)

    # 保存为TXT（后续可转PDF）
    today = date.today().isoformat()
    safe_subject = subject_name.replace(" ", "_")
    filename = f"weekly_test_{safe_subject}_{today}.txt"
    file_path = os.path.join(PDF_OUTPUT_DIR, filename)

    full_content = f"{'='*60}\n"
    full_content += f"  山西专升本 · {subject_name} 周测试卷\n"
    full_content += f"  日期：{today}\n"
    full_content += f"  难度：{difficulty} | 题量：{question_count}题\n"
    full_content += f"{'='*60}\n\n"
    full_content += test_text
    full_content += f"\n\n{'='*60}\n"
    full_content += f"  参考答案与解析\n"
    full_content += f"{'='*60}\n\n"
    full_content += answer_text

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(full_content)

    return {
        "subject": subject_name,
        "date": today,
        "difficulty": difficulty,
        "test_text": test_text,
        "answer_text": answer_text,
        "file_path": file_path,
        "question_count": question_count,
    }


async def generate_full_weekly_exam(
    user_id: int,
    include_subjects: list = None,
) -> dict:
    """
    生成完整的周六周测试卷（所有科目）
    返回各科试卷的聚合结果
    """
    if include_subjects is None:
        include_subjects = ["电路分析", "高等数学", "英语"]

    results = {}
    for subject in include_subjects:
        # 根据科目调整题量和难度
        config = {
            "电路分析": {"count": 8, "difficulty": "medium"},
            "高等数学": {"count": 8, "difficulty": "medium"},
            "英语": {"count": 10, "difficulty": "medium"},
        }
        cfg = config.get(subject, {"count": 8, "difficulty": "medium"})

        result = await create_weekly_test(
            user_id=user_id,
            subject_name=subject,
            difficulty=cfg["difficulty"],
            question_count=cfg["count"],
        )
        results[subject] = result

    return results


async def generate_pdf_test(
    user_id: int,
    subject_name: str,
    test_data: dict,
) -> str:
    """
    将测试内容转为 PDF 文件
    返回 PDF 文件路径
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_LEFT, TA_CENTER
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except ImportError:
        # ReportLab 未安装，返回 TXT 路径
        return test_data.get("file_path", "")

    today = date.today().isoformat()
    safe_subject = subject_name.replace(" ", "_")
    filename = f"weekly_test_{safe_subject}_{today}.pdf"
    pdf_path = os.path.join(PDF_OUTPUT_DIR, filename)

    doc = SimpleDocTemplate(pdf_path, pagesize=A4)

    # 尝试注册中文字体
    try:
        # 尝试常见 Windows 中文字体路径
        font_candidates = [
            ("C:/Windows/Fonts/simsun.ttc", "SimSun"),
            ("C:/Windows/Fonts/msyh.ttc", "MSYH"),
            ("C:/Windows/Fonts/simhei.ttf", "SimHei"),
        ]
        font_name = "Helvetica"
        for font_path, name in font_candidates:
            if os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont(name, font_path))
                font_name = name
                break
    except Exception:
        font_name = "Helvetica"

    styles = getSampleStyleSheet()
    chinese_style = ParagraphStyle(
        "ChineseStyle",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=11,
        leading=18,
        spaceAfter=6,
    )
    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Heading1"],
        fontName=font_name,
        fontSize=16,
        leading=24,
        alignment=TA_CENTER,
        spaceAfter=12,
    )

    story = []
    story.append(Paragraph(f"山西专升本 · {subject_name} 周测试卷", title_style))
    story.append(Paragraph(f"日期：{today}", chinese_style))
    story.append(Spacer(1, 20))

    # 解析试题内容，逐行添加
    test_text = test_data.get("test_text", "")
    for line in test_text.split("\n"):
        if line.strip():
            # 转义HTML特殊字符
            safe_line = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            story.append(Paragraph(safe_line, chinese_style))
        else:
            story.append(Spacer(1, 8))

    # 答案部分（新页）
    story.append(PageBreak())
    story.append(Paragraph("参考答案与解析", title_style))
    story.append(Spacer(1, 20))

    answer_text = test_data.get("answer_text", "")
    for line in answer_text.split("\n"):
        if line.strip():
            safe_line = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            story.append(Paragraph(safe_line, chinese_style))
        else:
            story.append(Spacer(1, 8))

    try:
        doc.build(story)
        return pdf_path
    except Exception as e:
        print(f"[PDF生成失败] {e}")
        return test_data.get("file_path", "")  # 降级为 TXT


def _split_test_and_answer(raw_text: str) -> tuple:
    """
    从AI生成的文本中分离试题和答案
    预期格式：试题和答案之间用 "参考答案" 或类似标记分隔
    """
    # 常见的分隔标记
    separators = [
        "📋 参考答案与解析",
        "参考答案与解析",
        "📋 参考答案",
        "参考答案",
        "答案与解析",
        "---\n（试卷结束）",
        "（试卷结束）",
    ]

    for sep in separators:
        if sep in raw_text:
            parts = raw_text.split(sep, 1)
            test_part = parts[0].strip()
            answer_part = parts[1].strip() if len(parts) > 1 else ""
            return test_part, answer_part

    # 没有找到分隔标记，返回原始内容
    return raw_text, "（答案暂未生成，请完成试题后联系老师批改）"


def format_test_for_telegram(test_data: dict) -> str:
    """
    将试卷格式化为 Telegram 消息（分多条发送）
    """
    subject = test_data["subject"]
    date_str = test_data["date"]
    difficulty = test_data.get("difficulty", "medium")

    difficulty_emoji = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}.get(difficulty, "🟡")

    header = (
        f"📝 周测试卷 — {subject}\n"
        f"📅 {date_str} | {difficulty_emoji} 难度：{difficulty}\n"
        f"⏰ 建议用时：90分钟\n"
        f"─" * 30
    )

    return header + "\n\n" + test_data["test_text"]


def format_answer_for_telegram(test_data: dict) -> str:
    """格式化答案为 Telegram 消息"""
    return (
        f"📋 参考答案 — {test_data['subject']}\n"
        f"─" * 30 + "\n\n"
        f"{test_data['answer_text']}\n\n"
        f"💡 做完后请对比答案，把错题拍照发给我，我会帮你分析薄弱点！"
    )
