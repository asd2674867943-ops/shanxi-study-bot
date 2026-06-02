"""
多AI提供商智能分析模块
支持：Anthropic Claude、OpenAI (ChatGPT)、DeepSeek、其他兼容API

自动选择可用提供商，当API Key未配置时降级为纯规则模式
"""

import json
from typing import Optional

from study_bot.config import (
    # Anthropic
    ANTHROPIC_API_KEY, CLAUDE_MODEL,
    # OpenAI
    OPENAI_API_KEY, OPENAI_MODEL, OPENAI_BASE_URL,
    # DeepSeek
    DEEPSEEK_API_KEY, DEEPSEEK_MODEL, DEEPSEEK_BASE_URL,
    # Gemini
    GEMINI_API_KEY, GEMINI_MODEL,
    # Custom
    CUSTOM_API_KEY, CUSTOM_API_BASE_URL, CUSTOM_MODEL,
    # Helpers
    AI_ENABLED, get_active_provider,
)
from study_bot.data.prompts import (
    DAILY_SUMMARY_PROMPT,
    ASSESSMENT_FEEDBACK_PROMPT,
    WEEKLY_ANALYSIS_PROMPT,
    PHOTO_SOLVER_PROMPT,
    TEST_GENERATION_PROMPT,
    DIAGNOSTIC_TEST_PROMPT,
    GRADUATE_TEST_PROMPT,
    KNOWLEDGE_POINT_QUESTION_PROMPT,
    DEEPENED_EXAM_PROMPT,
)


def _get_ai_client():
    """
    根据配置返回合适的 AI 客户端
    返回 (client_type, client, model_name)
    client_type: "gemini" / "anthropic" / "openai_compatible"
    """
    provider = get_active_provider()

    if provider == "gemini":
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        return ("gemini", genai, GEMINI_MODEL)

    if provider == "anthropic":
        import anthropic
        return ("anthropic", anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY), CLAUDE_MODEL)

    elif provider == "openai":
        from openai import AsyncOpenAI
        return ("openai_compatible", AsyncOpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL), OPENAI_MODEL)

    elif provider == "deepseek":
        from openai import AsyncOpenAI
        return ("openai_compatible", AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL), DEEPSEEK_MODEL)

    elif provider == "custom":
        from openai import AsyncOpenAI
        return ("openai_compatible", AsyncOpenAI(api_key=CUSTOM_API_KEY, base_url=CUSTOM_API_BASE_URL), CUSTOM_MODEL)

    return (None, None, None)


async def _call_ai(system_prompt: str, user_prompt: str, max_tokens: int = 800, temperature: float = 0.7) -> Optional[str]:
    """
    统一的 AI 调用接口，自动选择提供商
    """
    client_type, client, model = _get_ai_client()

    if client_type == "gemini":
        # Gemini: system prompt + user prompt 合并发送
        full_prompt = f"{system_prompt}\n\n---\n\n{user_prompt}"
        gemini_model = client.GenerativeModel(model)
        response = await gemini_model.generate_content_async(
            full_prompt,
            generation_config={
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            },
        )
        return response.text if response.text else None

    elif client_type == "anthropic":
        message = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return message.content[0].text

    elif client_type == "openai_compatible":
        response = await client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content

    return None


# ============================================================
# 每日学习总结
# ============================================================

async def analyze_daily_summary(
    logs_data: list,
    plan_data: Optional[dict],
    mastery_changes: list,
) -> str:
    """分析每日学习情况，生成个性化总结"""
    if not AI_ENABLED:
        return _rule_based_daily_feedback(logs_data, mastery_changes)

    try:
        log_summary = "\n".join(
            f"- {log['subject_name']} | {log['chapter_name']} | "
            f"学习{log['time_spent_min']}分钟 | 自评{log['self_rating']}/5"
            for log in logs_data
        ) if logs_data else "（今日暂无学习记录）"

        mastery_summary = "\n".join(
            f"- {m['chapter_name']}: {m['old_mastery']}% → {m['new_mastery']}%"
            for m in mastery_changes
        ) if mastery_changes else "（今日无掌握度变化）"

        plan_completion = "未使用计划"
        if plan_data:
            completed = sum(1 for s in plan_data.get("plan", {}).get("sessions", [])
                          if any(log.get("chapter_id") == s.get("chapter_id") for log in logs_data))
            total = len(plan_data.get("plan", {}).get("sessions", []))
            plan_completion = f"{completed}/{total} 任务完成"

        prompt = DAILY_SUMMARY_PROMPT.format(
            log_summary=log_summary,
            mastery_summary=mastery_summary,
            plan_completion=plan_completion,
        )

        result = await _call_ai(
            system_prompt="你是一位经验丰富的专升本备考导师，擅长电气工程专业的学习指导。你的建议具体、实用、有针对性。",
            user_prompt=prompt,
            max_tokens=800,
        )
        return result if result else _rule_based_daily_feedback(logs_data, mastery_changes)

    except Exception as e:
        print(f"[AI分析失败] {e}，降级为规则模式")
        return _rule_based_daily_feedback(logs_data, mastery_changes)


# ============================================================
# 知识点评估分析
# ============================================================

async def analyze_assessment(subject_name: str, chapter_results: list) -> str:
    """分析知识点评估结果"""
    if not AI_ENABLED:
        return _rule_based_assessment_feedback(subject_name, chapter_results)

    try:
        results_text = "\n".join(
            f"- {c['chapter_name']}（重要度{c['importance']}/5）: {c['score']}/100"
            for c in chapter_results
        )
        prompt = ASSESSMENT_FEEDBACK_PROMPT.format(
            subject_name=subject_name,
            results_text=results_text,
        )

        result = await _call_ai(
            system_prompt="你是一位专升本电路分析/高等数学/英语的专业辅导老师。你的分析准确、建议可操作。",
            user_prompt=prompt,
            max_tokens=1000,
        )
        return result if result else _rule_based_assessment_feedback(subject_name, chapter_results)

    except Exception as e:
        print(f"[AI分析失败] {e}")
        return _rule_based_assessment_feedback(subject_name, chapter_results)


# ============================================================
# 每周综合分析
# ============================================================

async def analyze_weekly(user_id: int, weekly_data: dict) -> str:
    """每周综合分析与建议"""
    if not AI_ENABLED:
        return _rule_based_weekly_feedback(weekly_data)

    try:
        prompt = WEEKLY_ANALYSIS_PROMPT.format(
            weekly_hours=weekly_data.get("weekly_hours", 0),
            daily_avg=weekly_data.get("daily_avg_hours", 0),
            study_days=weekly_data.get("weekly_days", 0),
            subject_progress=weekly_data.get("subject_summary", "暂无数据"),
            weak_points=weekly_data.get("weak_points", "暂无数据"),
        )

        result = await _call_ai(
            system_prompt="你是一位资深专升本备考顾问，擅长数据分析和学习策略规划。",
            user_prompt=prompt,
            max_tokens=1200,
        )
        return result if result else _rule_based_weekly_feedback(weekly_data)

    except Exception as e:
        print(f"[AI分析失败] {e}")
        return _rule_based_weekly_feedback(weekly_data)


# ============================================================
# 拍照搜题 / 图片解题
# ============================================================

async def solve_photo_question(
    image_description: str,
    subject_name: str = "unknown",
    user_text: str = "",
) -> str:
    """
    拍照搜题：根据图片中提取的文字/描述，给出详细解析与知识点
    image_description: 从图片中提取的文字内容
    subject_name: 科目名称（可选）
    user_text: 用户额外说明
    """
    if not AI_ENABLED:
        return (
            f"📷 拍照搜题\n\n"
            f"检测到题目内容：\n{image_description[:300]}\n\n"
            f"⚠️ 当前未配置 AI API Key，无法进行智能解题。\n"
            f"请在 .env 中配置 DeepSeek / OpenAI / Claude 的 API Key 后重试。"
        )

    try:
        prompt = PHOTO_SOLVER_PROMPT.format(
            image_text=image_description[:2000],
            subject_name=subject_name,
            user_note=user_text if user_text else "无额外说明",
        )

        result = await _call_ai(
            system_prompt="你是一位资深的专升本辅导老师，擅长电路分析、高等数学、英语的解题教学。你的解析详细透彻，知识点总结清晰，适合基础薄弱的学生理解。请用中文输出。",
            user_prompt=prompt,
            max_tokens=2000,
            temperature=0.3,  # 解题需要准确，降低随机性
        )
        return result if result else "AI 解题服务暂时不可用，请稍后重试。"

    except Exception as e:
        print(f"[拍照搜题失败] {e}")
        return f"❌ 解题服务出错：{str(e)[:200]}\n请确认 AI API Key 配置正确。"


# ============================================================
# 生成周测题目
# ============================================================

async def generate_weekly_test(
    subject_name: str,
    chapters: list,
    difficulty_level: str = "medium",
    question_count: int = 10,
    mode: str = "zhuanshengben",
) -> str:
    """
    生成周测试卷（文本格式，后续转PDF）
    chapters: [{"name": "xxx", "mastery": 0.5, "importance": 4}]
    mode: "zhuanshengben" | "graduate" | "deepened"
    """
    if not AI_ENABLED:
        return _rule_based_test_generation(subject_name, chapters, question_count)

    try:
        chapters_text = "\n".join(
            f"- {c['name']}（掌握度{c.get('mastery', 0)*100:.0f}%，重要度{c.get('importance', 3)}/5）"
            for c in chapters
        )

        # 根据模式选择提示词
        if mode == "graduate":
            prompt_template = GRADUATE_TEST_PROMPT
            system_prompt = "你是一位研究生入学考试辅导老师，擅长命制考研难度的高质量试题。题目考查深度和综合性。请用中文输出。"
            max_tokens = 4000
            temperature = 0.4
        elif mode == "deepened":
            prompt_template = DEEPENED_EXAM_PROMPT
            system_prompt = "你是一位专升本资深教研专家，能从更高视角审视专升本考点。你的题目新颖有深度，帮助学生融会贯通。请用中文输出。"
            max_tokens = 4000
            temperature = 0.4
        else:
            prompt_template = TEST_GENERATION_PROMPT
            system_prompt = "你是一位专升本的出题老师，擅长命制高质量试题。你出的题目严谨、规范，覆盖考点全面，难度适中，附有详尽解析。请用中文输出。"
            max_tokens = 3000
            temperature = 0.5

        prompt = prompt_template.format(
            subject_name=subject_name,
            chapters_list=chapters_text,
            difficulty=difficulty_level,
            count=question_count,
        )

        result = await _call_ai(
            system_prompt=system_prompt,
            user_prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return result if result else _rule_based_test_generation(subject_name, chapters, question_count)

    except Exception as e:
        print(f"[生成试卷失败] {e}")
        return _rule_based_test_generation(subject_name, chapters, question_count)


async def generate_knowledge_point_questions(
    subject_name: str,
    knowledge_point: str,
    difficulty: str = "基础",
    question_count: int = 5,
) -> str:
    """
    生成针对特定知识点的专项练习题
    """
    if not AI_ENABLED:
        return (
            f"📝 {subject_name} 专项练习\n\n"
            f"🎯 知识点：{knowledge_point}\n\n"
            f"⚠️ 未配置 AI API Key，无法生成专项练习题。\n"
            f"请在 .env 中配置 API Key 后重试。"
        )

    try:
        prompt = KNOWLEDGE_POINT_QUESTION_PROMPT.format(
            subject_name=subject_name,
            knowledge_point=knowledge_point,
            difficulty=difficulty,
            count=question_count,
        )

        result = await _call_ai(
            system_prompt="你是一位资深的专升本辅导老师，擅长针对特定知识点设计精准的专项练习。你的题目层次分明，由浅入深，帮助学生彻底攻克难点。请用中文输出。",
            user_prompt=prompt,
            max_tokens=3000,
            temperature=0.4,
        )
        return result if result else ""

    except Exception as e:
        print(f"[知识点出题失败] {e}")
        return ""


# ============================================================
# 拍照批改试卷
# ============================================================

async def grade_photo_answer(
    subject_name: str,
    test_questions: str,
    student_answer_text: str,
) -> str:
    """
    批改学生拍照上传的答案
    test_questions: 原题目
    student_answer_text: 从照片中提取的学生作答内容
    """
    if not AI_ENABLED:
        return (
            "📝 批改结果\n\n"
            "⚠️ 未配置 AI API Key，无法进行智能批改。\n"
            "请在 .env 中配置 API Key 后重试。"
        )

    try:
        prompt = f"""请批改以下学生的作答。

## 考试科目：{subject_name}

## 原题：
{test_questions[:2000]}

## 学生作答：
{student_answer_text[:2000]}

## 要求：
1. 逐题批改，指出对错
2. 对错题给出正确解法和详细解析
3. 分析学生的薄弱知识点
4. 给出整体得分（百分制）
5. 给出针对性学习建议
6. 指出需要重点复习的知识点

请用以下格式输出：
📊 批改报告
- 总分：X/100
- 正确率：X%

每题批改：
（逐题分析）

🎯 薄弱知识点：
（列出需要加强的知识点）

💡 学习建议：
（针对性建议）
"""
        result = await _call_ai(
            system_prompt="你是一位认真负责的专升本阅卷老师。你批改仔细，指出错误时温和有耐心，给出的建议具体实用。请用中文输出。",
            user_prompt=prompt,
            max_tokens=2500,
            temperature=0.3,
        )
        return result if result else "批改服务暂时不可用，请稍后重试。"

    except Exception as e:
        print(f"[批改失败] {e}")
        return f"❌ 批改服务出错：{str(e)[:200]}"


# ============================================================
# 综合分析（测试后总结）
# ============================================================

async def analyze_test_result(
    subject_name: str,
    score: float,
    max_score: float,
    error_summary: str,
    previous_scores: list,
) -> dict:
    """
    综合分析测试结果，给出后续学习建议
    返回 {"feedback": str, "recommendations": list, "focus_areas": list}
    """
    if not AI_ENABLED:
        return _rule_based_test_analysis(subject_name, score, max_score, error_summary)

    try:
        prompt = f"""请分析以下周测结果并给出建议：

科目：{subject_name}
得分：{score}/{max_score}（{score/max_score*100:.1f}%）
错题情况：{error_summary}
历史成绩：{previous_scores if previous_scores else '本次为首次测试'}

## 要求：
1. 分析本次考试成绩水平
2. 与历史成绩对比分析趋势（如有）
3. 列出最需要加强的3个知识点
4. 给出下周学习调整建议
5. 设定下次测试目标分数

请用JSON格式输出：
{{
  "analysis": "成绩分析（100字内）",
  "trend": "上升/下降/持平 - 说明",
  "focus_areas": ["知识点1", "知识点2", "知识点3"],
  "suggestions": ["建议1", "建议2", "建议3"],
  "next_target": 数字（目标分）
}}
"""
        result = await _call_ai(
            system_prompt="你是一位专升本数据分析师，善于从考试成绩中发现规律。输出必须是合法的JSON格式。",
            user_prompt=prompt,
            max_tokens=800,
            temperature=0.3,
        )

        if result:
            # 尝试解析 JSON
            try:
                # 清理可能的 markdown 代码块标记
                clean = result.strip()
                if clean.startswith("```"):
                    lines = clean.split("\n")
                    clean = "\n".join(lines[1:-1]) if len(lines) > 2 else clean
                return json.loads(clean)
            except json.JSONDecodeError:
                return {"analysis": result, "focus_areas": [], "suggestions": [], "next_target": score + 5}

    except Exception as e:
        print(f"[测试分析失败] {e}")

    return _rule_based_test_analysis(subject_name, score, max_score, error_summary)


# ============================================================
# 降级规则反馈（无 AI API 时使用）
# ============================================================

def _rule_based_daily_feedback(logs_data: list, mastery_changes: list) -> str:
    """基于规则的每日反馈"""
    if not logs_data:
        return (
            "📋 今日暂无学习记录\n\n"
            "💡 建议：即使只有半小时，也要保持每天学习的节奏。\n"
            "试试用 /log 记录你今天的学习内容吧！"
        )

    total_minutes = sum(log.get("time_spent_min", 0) for log in logs_data)
    avg_rating = sum(log.get("self_rating", 0) for log in logs_data) / len(logs_data) if logs_data else 0
    subjects_studied = set(log.get("subject_name", "") for log in logs_data)

    lines = [
        "📊 今日学习总结",
        "",
        f"⏰ 总学习时长：{total_minutes // 60}小时{total_minutes % 60}分钟",
        f"📚 覆盖科目：{len(subjects_studied)}门",
        f"⭐ 平均自评：{avg_rating:.1f}/5",
        "",
    ]

    improvements = [m for m in mastery_changes if m.get("new_mastery", 0) > m.get("old_mastery", 0)]
    if improvements:
        lines.append("🎯 掌握度提升：")
        for imp in improvements[:3]:
            lines.append(f"   ✅ {imp['chapter_name']}: {imp['old_mastery']}% → {imp['new_mastery']}%")

    lines.append("")
    lines.append("💡 学习建议：")
    if total_minutes < 120:
        lines.append("   1. 今天学习时间偏少，明天争取达到4小时以上")
    else:
        lines.append("   1. 学习节奏不错，继续保持！")
    if len(subjects_studied) < 2:
        lines.append("   2. 建议每天至少覆盖2个科目，交替学习效果更好")
    if avg_rating < 3:
        lines.append("   3. 自评偏低的话，可以放慢节奏，把基础打扎实再前进")
    lines.append("   4. 睡前花5分钟回忆今天学的内容，巩固记忆")

    return "\n".join(lines)


def _rule_based_assessment_feedback(subject_name: str, chapter_results: list) -> str:
    """基于规则的评估反馈"""
    if not chapter_results:
        return "暂无评估数据"

    weak = [c for c in chapter_results if c.get("score", 0) < 50]
    medium = [c for c in chapter_results if 50 <= c.get("score", 0) < 75]
    strong = [c for c in chapter_results if c.get("score", 0) >= 75]

    lines = [f"📋 {subject_name} 评估分析", ""]

    if strong:
        lines.append(f"✅ 掌握较好（≥75分）：{len(strong)}个章节")
        lines.append("   继续保持，定期复习即可")
        lines.append("")

    if medium:
        lines.append(f"📖 中等水平（50-74分）：{len(medium)}个章节")
        medium_names = [c["chapter_name"] for c in medium]
        lines.append(f"   重点提升：{'、'.join(medium_names[:3])}")
        lines.append("   建议：精做习题 + 归纳题型")
        lines.append("")

    if weak:
        lines.append(f"⚠️ 薄弱环节（<50分）：{len(weak)}个章节")
        weak_names = [c["chapter_name"] for c in weak]
        lines.append(f"   紧急补救：{'、'.join(weak_names[:3])}")
        lines.append("   建议：看视频课 → 做基础题 → 逐步提升")
        lines.append("")

    lines.append("💡 整体建议：先攻克薄弱的基础章节，再进入强化训练")
    return "\n".join(lines)


def _rule_based_weekly_feedback(weekly_data: dict) -> str:
    """基于规则的每周反馈"""
    hours = weekly_data.get("weekly_hours", 0)
    days = weekly_data.get("weekly_days", 0)

    lines = ["📊 本周学习总结", ""]
    lines.append(f"⏰ 本周学习：{hours}小时 | 📅 学习天数：{days}/7")
    lines.append("")

    if days < 4:
        lines.append("⚠️ 学习天数偏少，建议每周至少坚持5天以上")
    elif days == 7:
        lines.append("🏆 全勤学习！非常棒！注意劳逸结合")
    else:
        lines.append("👍 学习节奏良好，继续保持")

    if hours < 20:
        lines.append("💡 学习时间不足，建议增加每日学习时长至6小时以上")
    elif hours > 40:
        lines.append("💡 学习强度很高，注意休息，避免疲劳影响效率")

    return "\n".join(lines)


def _rule_based_test_generation(subject_name: str, chapters: list, count: int) -> str:
    """基于规则生成基础测试题"""
    lines = [
        f"📝 {subject_name} 周测试卷",
        f"⏰ 时间：90分钟 | 📊 满分：100分",
        f"",
        f"一、基础题（{count//2}题，每题8分，共{count//2*8}分）",
        f"",
    ]

    for i, ch in enumerate(chapters[:count//2]):
        lines.append(f"{i+1}. （{ch['name']}相关）请在所学章节中完成对应练习。")

    lines.append("")
    lines.append(f"二、综合题（{count - count//2}题，难度递增）")
    lines.append("")
    for i in range(count - count//2):
        idx = i + count//2 + 1
        lines.append(f"{idx}. 综合应用题 - 请结合所学知识完成解答。")

    lines.append("")
    lines.append("---")
    lines.append("📌 说明：当前为规则模式生成的测试框架，配置AI API Key后可生成更精准的个性化试题。")

    return "\n".join(lines)


def _rule_based_test_analysis(subject_name: str, score: float, max_score: float, error_summary: str) -> dict:
    """基于规则的测试分析"""
    pct = score / max_score if max_score > 0 else 0
    if pct >= 0.8:
        analysis = f"成绩优秀！{subject_name}掌握得很好。"
        next_target = min(max_score, score + 5)
    elif pct >= 0.6:
        analysis = f"成绩中等，{subject_name}还需加强。"
        next_target = score + 10
    else:
        analysis = f"成绩不理想，{subject_name}需要重点突破。"
        next_target = score + 15

    return {
        "analysis": analysis,
        "trend": "首次测试" if not error_summary else "急需提升",
        "focus_areas": ["需要根据错题具体分析"],
        "suggestions": [
            "错题重做，确保理解每个错误",
            "回归教材，夯实基础概念",
            "做针对性练习，逐一攻克薄弱点",
        ],
        "next_target": next_target,
    }
