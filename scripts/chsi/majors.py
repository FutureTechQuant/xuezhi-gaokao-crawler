"""
CHSI Majors Crawler - Minimal structured output
Stages: 1. List extraction → 2. Detail extraction → 3. Normalization
"""

import json
import os
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import parse_qs, urljoin, urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

# ============================================================================
# Configuration
# ============================================================================

BASE_URL = "https://gaokao.chsi.com.cn/zyk/zybk/"
OUTPUT_DIR = Path("data/chsi-major")
LEVEL_NAMES = ["本科（普通教育）", "本科（职业教育）", "高职（专科）"]

SAVE_DEBUG = os.getenv("SAVE_DEBUG", "0") == "1"
SCRAPE_DETAILS = os.getenv("SCRAPE_DETAILS", "1") == "1"

NAV_BLACKLIST = {
    "首页", "高考资讯", "阳光志愿", "高招咨询", "招生动态", "试题评析", "院校库", "专业库",
    "院校满意度", "专业满意度", "专业推荐", "更多", "招生政策", "选科参考", "云咨询周",
    "成绩查询", "招生章程", "名单公示", "志愿参考", "咨询室", "录取结果", "高职招生",
    "工作动态", "心理测评", "直播安排", "批次线", "专业解读", "各地网站", "职业前景",
    "特殊类型招生", "志愿填报时间", "招办访谈", "登录", "注册", "搜索", "查看", "取消",
    "基本信息", "开设院校", "开设课程", "图解专业", "选科要求", "更多>"
}

SECTION_ORDER = [
    "专业介绍", "统计信息", "相近专业", "本专业推荐人数较多的高校",
    "该专业学生考研方向", "已毕业人员从业方向", "薪酬指数",
]


# ============================================================================
# Utilities
# ============================================================================

def ensure_output() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def clean_text(text: Any) -> str:
    if text is None:
        return ""
    return " ".join(str(text).split()).strip()


def normalize_lines(text: str) -> List[str]:
    return [clean_text(x) for x in (text or "").splitlines() if clean_text(x)]


def unique_keep_order(items: List[Any]) -> List[Any]:
    seen = set()
    out = []
    for item in items:
        key = json.dumps(item, ensure_ascii=False, sort_keys=True) \
            if isinstance(item, (dict, list)) else item
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def save_debug(page: Any, name: str) -> None:
    if not SAVE_DEBUG:
        return
    try:
        page.screenshot(path=str(OUTPUT_DIR / f"{name}.png"), full_page=True)
    except Exception:
        pass
    try:
        (OUTPUT_DIR / f"{name}.html").write_text(page.content(), encoding="utf-8")
    except Exception:
        pass


def write_partial(flat_majors: List[Dict]) -> None:
    save_json(
        OUTPUT_DIR / "majors-flat.partial.json",
        {
            "抓取时间": iso_now(),
            "来源": BASE_URL,
            "数量": len(flat_majors),
            "专业列表": flat_majors,
        },
    )


# ============================================================================
# Stage 1: List Extraction
# ============================================================================

def wait_ready(page: Any) -> None:
    page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_selector("#app", timeout=30000)
    page.wait_for_function(
        """() => {
            const t = document.body ? document.body.innerText : '';
            return t.includes('专业知识库')
                && t.includes('本科（普通教育）专业目录')
                && t.includes('本科（职业教育）专业目录')
                && t.includes('高职（专科）专业目录');
        }""",
        timeout=60000,
    )
    page.wait_for_selector(".index-cc-list", timeout=30000)
    page.wait_for_timeout(1200)


def wait_table(page: Any) -> None:
    page.wait_for_selector(".zyk-table-con .ivu-table-body tbody tr", timeout=30000)
    page.wait_for_function(
        """() => {
            const rows = document.querySelectorAll('.zyk-table-con .ivu-table-body tbody tr');
            if (!rows.length) return false;
            const loading = document.querySelector('.ivu-spin-spinning')
                         || document.querySelector('.ivu-spin-show-text');
            return !loading;
        }""",
        timeout=30000,
    )
    page.wait_for_timeout(600)


def get_level_texts(page: Any) -> List[str]:
    items = page.locator(".index-cc-list li")
    out = []
    for i in range(items.count()):
        txt = clean_text(items.nth(i).inner_text())
        if txt:
            out.append(txt)
    return out


def click_level_by_text(page: Any, level_name: str) -> None:
    items = page.locator(".index-cc-list li")
    for i in range(items.count()):
        item = items.nth(i)
        txt = clean_text(item.inner_text())
        if txt == level_name:
            item.click()
            page.wait_for_timeout(1000)
            return
    raise RuntimeError(f"未找到培养层次：{level_name}")


def get_group(page: Any, idx: int) -> Any:
    return page.locator(".spec-list .zyk-lb-ul-con").nth(idx)


def get_group_items_texts(group: Any) -> List[str]:
    items = group.locator("ul.zyk-lb-ul > li")
    out = []
    for i in range(items.count()):
        txt = clean_text(items.nth(i).inner_text())
        if txt:
            out.append(txt)
    return out


def click_group_item_by_text(group: Any, text: str) -> None:
    items = group.locator("ul.zyk-lb-ul > li")
    for i in range(items.count()):
        item = items.nth(i)
        txt = clean_text(item.inner_text())
        if txt == text:
            item.click()
            return
    raise RuntimeError(f"未找到分组项：{text}")


def extract_spec_id(detail_href: str, school_href: str) -> str:
    for url in [detail_href, school_href]:
        if not url:
            continue
        m = re.search(r"specId=(\d+)", url)
        if m:
            return m.group(1)
        m = re.search(r"/detail/(\d+)", url)
        if m:
            return m.group(1)
    return ""


def extract_table_rows(
    page: Any, level_name: str, discipline: str, major_class: str
) -> List[Dict]:
    row_data = page
