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

from study_bot.config import PDF_OUTPUT_DIR, DIFFICULTY_LEVELS
from study_bot.services.analyzer import generate_weekly_test, grade_photo_answer, generate_knowledge_point_questions
from study_bot.database.ops import (
    get_user_mastery,
    get_chapters_by_subject,
    get_all_subjects,
    get_user,
    save_assessment,
)


# 确保输出目录存在
os.makedirs(PDF_OUTPUT_DIR, exist_ok=True)


# 难度映射表
DIFFICULTY_MAP = {
    "basic": {"label": "专升本基础", "prompt_difficulty": "基础", "mode": "zhuanshengben"},
    "advanced": {"label": "专升本进阶", "prompt_difficulty": "进阶", "mode": "zhuanshengben"},
    "medium": {"label": "专升本进阶", "prompt_difficulty": "进阶", "mode": "zhuanshengben"},
    "easy": {"label": "专升本基础", "prompt_difficulty": "基础", "mode": "zhuanshengben"},
    "hard": {"label": "研究生入门", "prompt_difficulty": "研究生入门", "mode": "graduate"},
    "grad_intro": {"label": "研究生入门", "prompt_difficulty": "研究生入门", "mode": "graduate"},
    "grad_advanced": {"label": "研究生进阶", "prompt_difficulty": "研究生进阶", "mode": "graduate"},
    "deepened": {"label": "深化专升本", "prompt_difficulty": "深化专升本", "mode": "zhuanshengben"},
}


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

    # 解析难度配置
    diff_config = DIFFICULTY_MAP.get(difficulty, DIFFICULTY_MAP["medium"])
    study_mode = diff_config["mode"]
    prompt_diff = diff_config["prompt_difficulty"]

    # AI 或规则生成测试
    test_raw = await generate_weekly_test(
        subject_name=subject_name,
        chapters=chapters_info,
        difficulty_level=prompt_diff,
        question_count=question_count,
        mode=study_mode if study_mode == "graduate" else "zhuanshengben",
    )

    # 解析试题和答案（AI输出中已包含答案部分）
    test_text, answer_text = _split_test_and_answer(test_raw)

    # 后处理：确保来源标注存在
    answer_text = _ensure_source_attribution(answer_text)

    # 保存为TXT（后续可转PDF）
    today = date.today().isoformat()
    safe_subject = subject_name.replace(" ", "_")
    filename = f"weekly_test_{safe_subject}_{today}.txt"
    file_path = os.path.join(PDF_OUTPUT_DIR, filename)

    full_content = f"{'='*60}\n"
    full_content += f"  山西专升本 · {subject_name} 周测试卷\n"
    full_content += f"  日期：{today}\n"
    full_content += f"  难度：{diff_config['label']} | 题量：{question_count}题\n"
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
        "difficulty_label": diff_config["label"],
        "test_text": test_text,
        "answer_text": answer_text,
        "file_path": file_path,
        "question_count": question_count,
    }


async def create_knowledge_point_test(
    user_id: int,
    subject_name: str,
    knowledge_point: str,
    difficulty: str = "basic",
    question_count: int = 5,
) -> dict:
    """
    生成针对特定知识点的专项练习题

    返回同 create_weekly_test 格式
    """
    diff_config = DIFFICULTY_MAP.get(difficulty, DIFFICULTY_MAP["basic"])
    prompt_diff = diff_config["prompt_difficulty"]

    # 调用AI生成知识点专项题
    test_raw = await generate_knowledge_point_questions(
        subject_name=subject_name,
        knowledge_point=knowledge_point,
        difficulty=prompt_diff,
        question_count=question_count,
    )

    if not test_raw:
        return {"error": f"AI生成失败，请检查API Key配置"}

    test_text, answer_text = _split_test_and_answer(test_raw)
    answer_text = _ensure_source_attribution(answer_text)

    today = date.today().isoformat()
    safe_kp = knowledge_point.replace(" ", "_")[:20]
    filename = f"kp_test_{safe_kp}_{today}.txt"
    file_path = os.path.join(PDF_OUTPUT_DIR, filename)

    full_content = f"{'='*60}\n"
    full_content += f"  知识点专项练习\n"
    full_content += f"  科目：{subject_name} | 知识点：{knowledge_point}\n"
    full_content += f"  日期：{today} | 难度：{diff_config['label']}\n"
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
        "difficulty_label": diff_config["label"],
        "knowledge_point": knowledge_point,
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


def _ensure_source_attribution(answer_text: str) -> str:
    """
    确保答案部分包含来源标注
    如果AI输出的答案缺少来源标注，自动追加
    """
    if "📎 题目来源" in answer_text or "题目来源" in answer_text:
        return answer_text

    # 追加通用来源标注
    attribution = "\n\n---\n📎 题目来源：🤖 AI原创出题（由山西专升本学习助手生成，仅供学习参考）"
    return answer_text + attribution


def format_test_for_telegram(test_data: dict) -> str:
    """
    将试卷格式化为 Telegram 消息（分多条发送）
    """
    subject = test_data["subject"]
    date_str = test_data["date"]
    difficulty = test_data.get("difficulty", "medium")
    difficulty_label = test_data.get("difficulty_label", test_data.get("difficulty", "medium"))

    difficulty_emoji = {
        "easy": "🟢", "basic": "🟢",
        "medium": "🟡", "advanced": "🟡",
        "hard": "🔴", "grad_intro": "🟠", "grad_advanced": "🔴",
    }.get(difficulty, "🟡")

    header = (
        f"📝 周测试卷 — {subject}\n"
        f"📅 {date_str} | {difficulty_emoji} 难度：{difficulty_label}\n"
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


def format_knowledge_point_test(test_data: dict) -> str:
    """格式化知识点专项练习为 Telegram 消息"""
    subject = test_data.get("subject", "")
    kp = test_data.get("knowledge_point", "")
    difficulty_label = test_data.get("difficulty_label", "")

    header = (
        f"📝 知识点专项练习 — {subject}\n"
        f"🎯 知识点：{kp}\n"
        f"📊 难度：{difficulty_label}\n"
        f"─" * 30
    )
    return header + "\n\n" + test_data.get("test_text", "")
