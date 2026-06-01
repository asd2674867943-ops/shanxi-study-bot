"""
山西专升本政策监控服务
定期检查考试政策变化、报名时间、考纲更新等
"""

import logging
from datetime import date, datetime, timedelta
from typing import Optional

from study_bot.config import POLICY_URLS, SHANXI_EXAM_INFO

logger = logging.getLogger(__name__)


async def check_policy_updates() -> dict:
    """
    检查山西专升本政策更新
    返回 {"has_update": bool, "updates": list, "last_check": str}
    """
    updates = []

    for url in POLICY_URLS:
        try:
            page_updates = await _fetch_and_parse(url)
            if page_updates:
                updates.extend(page_updates)
        except Exception as e:
            logger.warning(f"政策检查失败 [{url}]: {e}")

    return {
        "has_update": len(updates) > 0,
        "updates": updates,
        "last_check": date.today().isoformat(),
        "source": "山西招生考试网",
    }


async def _fetch_and_parse(url: str) -> list:
    """抓取并解析政策页面"""
    try:
        import httpx
        from bs4 import BeautifulSoup

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            if response.status_code != 200:
                return []

        # 解析HTML，提取专升本相关新闻标题
        soup = BeautifulSoup(response.text, "html.parser")
        updates = []

        # 常见新闻列表结构
        for tag in soup.find_all(["a", "li"]):
            text = tag.get_text(strip=True)
            if not text:
                continue

            # 筛选专升本相关关键词
            keywords = ["专升本", "考试", "招考", "报名", "分数线", "大纲", "录取"]
            if any(kw in text for kw in keywords):
                link = tag.get("href", "") if tag.name == "a" else ""
                if link and not link.startswith("http"):
                    base = url.rstrip("/").replace("/index.html", "").replace("/index.htm", "")
                    link = base + "/" + link.lstrip("/") if link else ""

                updates.append({
                    "title": text[:100],
                    "url": link,
                    "source": "山西招生考试网",
                    "date_found": date.today().isoformat(),
                })

        return updates[:10]  # 最多返回10条

    except ImportError:
        logger.warning("httpx 或 beautifulsoup4 未安装，政策监控降级")
        return []
    except Exception as e:
        logger.error(f"页面解析错误: {e}")
        return []


# ============================================================
# 关键时间节点提醒
# ============================================================

def get_exam_timeline(exam_year: int = None) -> list:
    """获取山西专升本考试时间线"""
    if exam_year is None:
        exam_year = date.today().year + (1 if date.today().month > 4 else 0)

    timeline = [
        {
            "period": f"{exam_year-1}年10月-11月",
            "event": "各院校发布招生简章",
            "action": "关注目标院校官网，确认招生计划",
        },
        {
            "period": f"{exam_year-1}年12月",
            "event": "省招考中心发布考试大纲 / 网上报名",
            "action": "下载最新考纲，核对考试范围是否有变化",
        },
        {
            "period": f"{exam_year}年1月",
            "event": "网上报名确认 / 缴费",
            "action": "确认报名成功，保存报名信息",
        },
        {
            "period": f"{exam_year}年2月",
            "event": "考前冲刺阶段",
            "action": "做真题模拟，查漏补缺，调整作息",
        },
        {
            "period": f"{exam_year}年3月中下旬",
            "event": "全省统一考试",
            "action": "考前一周调整状态，保证睡眠，备好考试用品",
        },
        {
            "period": f"{exam_year}年4月",
            "event": "成绩公布 / 分数线发布",
            "action": "查询成绩，关注省控线和各校分数线",
        },
        {
            "period": f"{exam_year}年5月",
            "event": "志愿填报 / 录取结果公布",
            "action": "根据成绩和分数线合理填报志愿",
        },
    ]

    return timeline


def format_policy_check(result: dict) -> str:
    """格式化政策检查结果"""
    if not result.get("has_update"):
        return (
            f"📋 政策检查 ({result['last_check']})\n\n"
            f"✅ 暂未发现新的专升本相关政策公告。\n"
            f"📌 数据来源：{result['source']}\n\n"
            f"💡 每年12月前后关注新考纲发布！"
        )

    lines = [
        f"📋 政策检查 ({result['last_check']})",
        f"",
        f"🔔 发现 {len(result['updates'])} 条相关更新：",
        f"",
    ]

    for i, update in enumerate(result["updates"][:5], 1):
        title = update.get("title", "无标题")
        url = update.get("url", "")
        lines.append(f"{i}. {title}")
        if url:
            lines.append(f"   🔗 {url}")

    lines.append("")
    lines.append(f"📌 数据来源：{result['source']}")
    lines.append("💡 建议及时查看，特别是考纲变化和报名时间！")

    return "\n".join(lines)


def format_exam_timeline() -> str:
    """格式化考试时间线"""
    timeline = get_exam_timeline()

    lines = ["📅 山西专升本考试时间线", ""]

    for item in timeline:
        period = item["period"]
        event = item["event"]
        action = item["action"]
        lines.append(f"📌 {period}")
        lines.append(f"   ├─ {event}")
        lines.append(f"   └─ 💡 {action}")
        lines.append("")

    lines.append("⚠️ 以上为预估时间，具体以省招考中心公告为准。")
    lines.append("   官网：http://www.sxkszx.cn/")

    return "\n".join(lines)
