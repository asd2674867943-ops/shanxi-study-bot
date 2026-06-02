"""
太原工业学院官网信息抓取服务
抓取专升本招生相关信息：分数线、专业、考试大纲等
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from study_bot.config import TAIYUAN_INSTITUTE_URLS, SHANXI_EXAM_INFO, SCORE_LINE_HISTORY, DEFAULT_TARGET_UNIV

logger = logging.getLogger(__name__)

# 简单内存缓存（避免频繁请求）
_cache: dict = {"data": None, "timestamp": None}
_CACHE_DURATION = timedelta(hours=24)


async def scrape_taiyuan_info() -> dict:
    """
    抓取太原工业学院专升本相关信息

    返回：
    {
        "success": bool,
        "university": str,
        "admission_requirements": str,
        "score_lines": list,
        "majors": list,
        "exam_syllabi": list,
        "updates": list,
        "source_urls": list,
        "last_updated": str,
        "from_cache": bool,
    }
    """
    # 检查缓存
    if _cache["data"] and _cache["timestamp"]:
        if datetime.now() - _cache["timestamp"] < _CACHE_DURATION:
            _cache["data"]["from_cache"] = True
            return _cache["data"]

    result = {
        "success": False,
        "university": DEFAULT_TARGET_UNIV,
        "admission_requirements": "",
        "score_lines": [],
        "majors": [],
        "exam_syllabi": [],
        "updates": [],
        "source_urls": TAIYUAN_INSTITUTE_URLS.copy(),
        "last_updated": datetime.now().isoformat(),
        "from_cache": False,
    }

    # 尝试抓取各URL
    updates = []
    try:
        import httpx
        from bs4 import BeautifulSoup

        async with httpx.AsyncClient(timeout=15.0) as client:
            for url in TAIYUAN_INSTITUTE_URLS:
                try:
                    response = await client.get(
                        url,
                        headers={
                            "User-Agent": (
                                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) "
                                "Chrome/120.0.0.0 Safari/537.36"
                            ),
                            "Accept": "text/html,application/xhtml+xml",
                            "Accept-Language": "zh-CN,zh;q=0.9",
                        },
                    )
                    if response.status_code == 200:
                        # 尝试推断编码
                        content = response.text
                        soup = BeautifulSoup(content, "html.parser")

                        # 提取标题文本
                        title = soup.title.string if soup.title else url
                        logger.info(f"[太原工业学院] 成功抓取: {title}")

                        # 搜索专升本相关链接
                        keywords = ["专升本", "招生", "电气", "录取", "考试", "大纲"]
                        for tag in soup.find_all(["a", "li"], string=True):
                            text = tag.get_text(strip=True)
                            if any(kw in text for kw in keywords) and len(text) > 4:
                                href = tag.get("href", "") if tag.name == "a" else ""
                                updates.append({
                                    "title": text[:100],
                                    "url": _resolve_url(url, href) if href else "",
                                    "source": "太原工业学院官网",
                                })
                except Exception as e:
                    logger.warning(f"[太原工业学院] 抓取失败 {url}: {e}")

        result["updates"] = updates[:20]

    except ImportError:
        logger.warning("[太原工业学院] httpx/bs4 未安装，使用静态数据")

    # 从静态配置填充数据
    result["admission_requirements"] = (
        f"🏫 {DEFAULT_TARGET_UNIV} 电气工程及其自动化专业\n\n"
        f"📋 考试科目：\n"
        f"   • 电路分析（专业课）— 满分150分\n"
        f"   • 英语（公共课）— 满分50分\n"
        f"   • 高等数学（公共课）— 满分100分\n"
        f"📊 总分：300分\n\n"
        f"📅 考试时间：每年3月中下旬\n"
        f"🌐 官网：{TAIYUAN_INSTITUTE_URLS[0]}"
    )

    result["score_lines"] = [
        {"year": y, "score": s, "university": DEFAULT_TARGET_UNIV}
        for y, s in sorted(SCORE_LINE_HISTORY.items(), reverse=True)
    ]

    result["majors"] = [
        {"name": "电气工程及其自动化", "category": "工学", "degree": "工学学士"},
    ]

    result["exam_syllabi"] = [
        {"subject": "电路分析", "reference": SHANXI_EXAM_INFO["subjects_detail"]["电路分析"]["reference_book"]},
        {"subject": "英语", "reference": SHANXI_EXAM_INFO["subjects_detail"]["英语"]["reference_book"]},
        {"subject": "高等数学", "reference": SHANXI_EXAM_INFO["subjects_detail"]["高等数学"]["reference_book"]},
    ]

    if updates:
        result["success"] = True

    # 更新缓存
    _cache["data"] = result
    _cache["timestamp"] = datetime.now()

    return result


def _resolve_url(base_url: str, href: str) -> str:
    """将相对URL解析为绝对URL"""
    if not href:
        return ""
    if href.startswith("http"):
        return href
    # 从base_url中提取基础路径
    from urllib.parse import urljoin
    return urljoin(base_url, href)


def format_taiyuan_info(info: dict) -> str:
    """格式化为Telegram消息"""
    lines = [
        f"🏫 {info.get('university', DEFAULT_TARGET_UNIV)} 专升本信息",
        "",
    ]

    # 招生要求
    if info.get("admission_requirements"):
        lines.append(info["admission_requirements"])
        lines.append("")

    # 历年分数线
    score_lines = info.get("score_lines", [])
    if score_lines:
        lines.append("📈 历年分数线（电气工程及其自动化）：")
        lines.append("```")
        for sl in score_lines:
            y = sl.get("year", "?")
            s = sl.get("score", 0)
            bar = "█" * min(int(s / 10), 30)
            lines.append(f"{y}: {s:.1f} {bar}")
        lines.append("```")
        lines.append("")

    # 考试大纲
    syllabi = info.get("exam_syllabi", [])
    if syllabi:
        lines.append("📚 参考教材：")
        for syl in syllabi:
            lines.append(f"   • {syl['subject']}：{syl['reference']}")
        lines.append("")

    # 官网更新
    updates = info.get("updates", [])
    if updates:
        lines.append("🔔 官网最新信息：")
        for u in updates[:8]:
            title = u.get("title", "")[:60]
            url = u.get("url", "")
            if url:
                lines.append(f"   • [{title}]({url})")
            else:
                lines.append(f"   • {title}")
        lines.append("")

    # 来源和缓存状态
    if info.get("from_cache"):
        lines.append("⏳ 数据来源：缓存（24小时内更新）")
    else:
        lines.append("🔄 数据来源：实时抓取")
    lines.append(f"   更新时间：{info.get('last_updated', '未知')[:16]}")

    return "\n".join(lines)
