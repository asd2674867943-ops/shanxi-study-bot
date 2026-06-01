"""
拍照搜题服务
接收用户拍照上传的图片 → OCR识别 → AI解题 → 知识点总结
支持：数学题、电路题、英语题
"""

import os
import base64
import json
from datetime import date
from typing import Optional

from study_bot.services.analyzer import solve_photo_question
from study_bot.database.ops import (
    add_study_log,
    get_user_mastery,
    get_all_subjects,
    get_chapters_by_subject,
)


async def process_photo_question(
    user_id: int,
    image_data: bytes,
    subject_hint: str = "",
    user_notes: str = "",
) -> dict:
    """
    处理拍照搜题请求
    1. OCR识别图片中的文字
    2. AI解题
    3. 提取知识点
    4. 更新薄弱知识点到学习计划

    返回：
    {
        "text_extracted": "从图片中提取的文字",
        "solution": "AI解题答案",
        "subject": "识别的科目",
        "chapter": "识别的章节",
        "knowledge_points": ["知识点1", "知识点2"],
        "error_warning": "易错点",
    }
    """
    # Step 1: OCR 文字提取
    extracted_text = await _ocr_from_image(image_data)

    if not extracted_text or len(extracted_text.strip()) < 3:
        return {
            "text_extracted": "",
            "solution": "⚠️ 未能从图片中识别到文字内容。请确认：\n"
                        "1. 照片清晰，文字可辨认\n"
                        "2. 光线充足，没有反光\n"
                        "3. 题目在照片中完整可见\n\n"
                        "请重新拍照后发送。",
            "subject": "",
            "chapter": "",
            "knowledge_points": [],
            "error_warning": "",
        }

    # Step 2: AI 解题
    solution = await solve_photo_question(
        image_description=extracted_text,
        subject_name=subject_hint or "自动识别",
        user_text=user_notes,
    )

    # Step 3: 尝试提取知识点信息
    knowledge_data = _extract_knowledge_info(solution, extracted_text)

    # Step 4: 记录到数据库（用于后续学习计划）
    await _record_question_to_db(user_id, knowledge_data)

    return {
        "text_extracted": extracted_text[:500],
        "solution": solution,
        "subject": knowledge_data.get("subject", subject_hint),
        "chapter": knowledge_data.get("chapter", ""),
        "knowledge_points": knowledge_data.get("knowledge_points", []),
        "error_warning": knowledge_data.get("error_warning", ""),
    }


async def process_answer_photo(
    user_id: int,
    subject_name: str,
    test_questions: str,
    image_data: bytes,
) -> dict:
    """
    处理学生拍照上传的作答（批改用）
    1. OCR识别作答内容
    2. AI批改
    3. 分析薄弱点
    """
    # OCR 提取作答内容
    answer_text = await _ocr_from_image(image_data)

    if not answer_text or len(answer_text.strip()) < 3:
        return {
            "success": False,
            "message": "⚠️ 未能从照片中识别到作答内容，请重新拍摄清晰的答卷照片。",
        }

    # AI 批改
    from services.analyzer import grade_photo_answer
    grading_result = await grade_photo_answer(
        subject_name=subject_name,
        test_questions=test_questions[:2000],
        student_answer_text=answer_text[:2000],
    )

    # 提取得分和薄弱点
    score_info = _extract_score(grading_result)

    return {
        "success": True,
        "answer_text": answer_text[:500],
        "grading_result": grading_result,
        "score": score_info.get("score", None),
        "weak_points": score_info.get("weak_points", []),
    }


async def _ocr_from_image(image_data: bytes) -> str:
    """
    从图片中提取文字
    优先使用 OCR 库，降级为 base64 传给 AI 处理
    """
    # 尝试使用 Tesseract OCR
    try:
        import pytesseract
        from PIL import Image
        import io

        image = Image.open(io.BytesIO(image_data))
        # 预处理：转灰度 + 二值化 提高识别率
        image = image.convert("L")
        text = pytesseract.image_to_string(image, lang="chi_sim+eng")
        if text and len(text.strip()) > 5:
            return text.strip()
    except ImportError:
        pass  # pytesseract 未安装
    except Exception as e:
        print(f"[OCR识别失败] {e}")

    # 降级方案：使用 AI 视觉能力（如果提供商支持）
    # 对于不支持图片的 API，返回提示
    try:
        # 尝试用 base64 传给支持视觉的 AI
        b64_image = base64.b64encode(image_data).decode("utf-8")
        return f"[图片base64编码，长度{len(b64_image)}] 请使用支持视觉识别的AI模型处理。"
    except Exception:
        pass

    return ""


def _extract_knowledge_info(solution: str, extracted_text: str) -> dict:
    """从AI解题结果中提取知识点信息"""
    result = {
        "subject": "",
        "chapter": "",
        "knowledge_points": [],
        "error_warning": "",
    }

    lines = solution.split("\n")
    current_section = ""

    for line in lines:
        line = line.strip()
        if "科目" in line or "📷" in line:
            # 提取科目
            if "电路" in line:
                result["subject"] = "电路分析"
            elif "数学" in line or "高等数学" in line:
                result["subject"] = "高等数学"
            elif "英语" in line or "English" in line:
                result["subject"] = "英语"
        elif "所属章节" in line or "章节" in line:
            result["chapter"] = line.split("：")[-1].split(":")[-1].strip()
        elif "核心公式" in line or "核心定理" in line:
            kp = line.split("：")[-1].split(":")[-1].strip()
            if kp and len(kp) > 2:
                result["knowledge_points"].append(kp)
        elif "易错提醒" in line:
            result["error_warning"] = line.split("：")[-1].split(":")[-1].strip()

    return result


def _extract_score(grading_result: str) -> dict:
    """从批改结果中提取分数和薄弱点"""
    result = {"score": None, "weak_points": []}

    for line in grading_result.split("\n"):
        line = line.strip()
        if "总分" in line or "得分" in line:
            try:
                # 尝试提取数字
                import re
                nums = re.findall(r'(\d+)/', line)
                if nums:
                    result["score"] = int(nums[0])
            except ValueError:
                pass
        if "薄弱" in line and "：" in line:
            points = line.split("：")[-1].split(":")[-1]
            for p in points.split("、"):
                p = p.strip()
                if p and len(p) > 1:
                    result["weak_points"].append(p)

    return result


async def _record_question_to_db(user_id: int, knowledge_data: dict):
    """将搜题的知识点记录到数据库，影响后续学习计划"""
    if not knowledge_data.get("subject"):
        return

    # 找到对应的科目和章节
    subjects = await get_all_subjects()
    for subj in subjects:
        if subj["name"] == knowledge_data["subject"]:
            chapters = await get_chapters_by_subject(subj["id"])
            # 模糊匹配章节名
            target_chapter = knowledge_data.get("chapter", "")
            for ch in chapters:
                if target_chapter and target_chapter in ch["name"]:
                    # 记录这次搜题为一次"学习"（time=15min，rating=2 表示需要加强）
                    await add_study_log(
                        user_id=user_id,
                        subject_id=subj["id"],
                        chapter_id=ch["id"],
                        time_spent_min=15,
                        self_rating=2,
                        notes=f"[拍照搜题] 知识点: {', '.join(knowledge_data.get('knowledge_points', []))}",
                        date_str=date.today().isoformat(),
                    )
                    break
            break


def format_solution_for_telegram(result: dict) -> str:
    """格式化解题结果为 Telegram 消息"""
    if result.get("text_extracted"):
        preview = result["text_extracted"][:200]
        header = f"📷 识别内容：\n```\n{preview}\n```\n\n"
    else:
        header = ""

    solution = result.get("solution", "暂无解答")

    # 知识点标签
    kp = result.get("knowledge_points", [])
    if kp:
        kp_text = "\n".join(f"   • {p}" for p in kp)
        footer = f"\n\n📌 涉及知识点：\n{kp_text}"
    else:
        footer = ""

    if result.get("error_warning"):
        footer += f"\n\n⚠️ 易错提醒：{result['error_warning']}"

    footer += "\n\n💡 这类题目以后会加入你的学习计划中反复练习！"

    return header + solution + footer
