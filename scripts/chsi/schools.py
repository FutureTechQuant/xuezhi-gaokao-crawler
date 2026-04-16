"""
CHSI Schools Crawler - Specification-driven implementation
Stages: 1. List extraction → 2. Detail extraction → 3. Normalization → 4. Automation
"""

import json
import os
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

# ============================================================================
# Configuration
# ============================================================================

BASE_URL_PATTERN = "https://gaokao.chsi.com.cn/sch/search--ss-on,option-qg,searchType-1,start-{start}.dhtml"
OUTPUT_DIR = Path("output")

SAVE_DEBUG = os.getenv("SAVE_DEBUG", "0") == "1"
SCRAPE_DETAILS = os.getenv("SCRAPE_DETAILS", "1") == "1"

# ============================================================================
# Utilities
# ============================================================================

def ensure_output() -> None:
    """Create output directory if it doesn't exist."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def iso_now() -> str:
    """Return current time in ISO format with timezone."""
    return datetime.now(timezone.utc).astimezone().isoformat()


def clean_text(text: Any) -> str:
    """Clean and normalize text."""
    if text is None:
        return ""
    return " ".join(str(text).split()).strip()


def normalize_lines(text: str) -> List[str]:
    """Split text into lines and clean each."""
    return [clean_text(x) for x in (text or "").splitlines() if clean_text(x)]


def unique_keep_order(items: List[Any]) -> List[Any]:
    """Remove duplicates while preserving order."""
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
    """Save data as JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def save_debug(page: Any, name: str) -> None:
    """Save debug screenshot and HTML if SAVE_DEBUG is enabled."""
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


def write_partial(flat_schools: List[Dict]) -> None:
    """Write partial results to enable recovery on failure."""
    save_json(
        OUTPUT_DIR / "schools-flat.partial.json",
        {
            "抓取时间": iso_now(),
            "来源": BASE_URL_PATTERN,
            "数量": len(flat_schools),
            "学校列表": flat_schools,
        },
    )


# ============================================================================
# Stage 1: List Extraction
# ============================================================================

def wait_list_ready(page: Any) -> None:
    """Wait for school list page to load with all required elements."""
    page.wait_for_selector("#app", timeout=30000)
    page.wait_for_function(
        """() => {
            const t = document.body ? document.body.innerText : '';
            return t.includes('院校库') || t.includes('学校列表');
        }""",
        timeout=60000,
    )
    page.wait_for_selector(".sch-card, .school-item, .card", timeout=30000)
    page.wait_for_timeout(1200)


def extract_sch_id(detail_href: str) -> str:
    """Extract schId from detail page URL."""
    if not detail_href:
        return ""
    # Patterns from ai/10_target_sites.md:
    # schschoolInfo--schId-{schId}.dhtml
    # schschoolInfoMain--schId-{schId}.dhtml
    m = re.search(r"schId-(\d+)", detail_href)
    if m:
        return m.group(1)
    return ""


def extract_school_cards(page: Any, page_url: str, page_no: int) -> List[Dict]:
    """Extract school information from card-based list page."""
    # Try different card selectors based on common patterns
    card_selectors = [".sch-card", ".school-item", ".card", ".school-card"]
    cards = None

    for selector in card_selectors:
        try:
            cards = page.locator(selector)
            if cards.count() > 0:
                break
        except Exception:
            continue

    if not cards or cards.count() == 0:
        return []

    schools = []
    for i in range(cards.count()):
        try:
            card = cards.nth(i)

            # Extract school name and detail link
            name_elem = card.locator("h3, .school-name, .name").first
            name = clean_text(name_elem.inner_text()) if name_elem.count() > 0 else ""

            detail_link_elem = card.locator("a[href*='schschoolInfo']").first
            detail_href = ""
            if detail_link_elem.count() > 0:
                detail_href = detail_link_elem.get_attribute("href") or ""
                detail_href = urljoin(page_url, detail_href)

            # Extract schId from detail URL
            sch_id = extract_sch_id(detail_href)

            # Extract image
            img_elem = card.locator("img").first
            img_src = ""
            if img_elem.count() > 0:
                img_src = img_elem.get_attribute("src") or ""
                img_src = urljoin(page_url, img_src)

            # Extract other fields from card text
            card_text = clean_text(card.inner_text())

            # Parse fields from card text (may need adjustment based on actual HTML)
            department = ""  # 主管部门
            location = ""    # 院校所在地
            level = ""       # 办学层次
            school_type = "" # 学校类型
            satisfaction = "" # 院校满意度

            # Try to extract from structured elements or text patterns
            dept_elem = card.locator(".department, .supervisor").first
            if dept_elem.count() > 0:
                department = clean_text(dept_elem.inner_text())

            loc_elem = card.locator(".location, .address").first
            if loc_elem.count() > 0:
                location = clean_text(loc_elem.inner_text())

            level_elem = card.locator(".level, .hierarchy").first
            if level_elem.count() > 0:
                level = clean_text(level_elem.inner_text())

            type_elem = card.locator(".type, .category").first
            if type_elem.count() > 0:
                school_type = clean_text(type_elem.inner_text())

            sat_elem = card.locator(".satisfaction, .rating").first
            if sat_elem.count() > 0:
                satisfaction = clean_text(sat_elem.inner_text())

            # If structured elements not found, try regex patterns
            if not department:
                m = re.search(r"(?:主管|隶属)[：:]\s*([^\n]+)", card_text)
                department = clean_text(m.group(1)) if m else ""

            if not location:
                m = re.search(r"(?:所在地|地址)[：:]\s*([^\n]+)", card_text)
                location = clean_text(m.group(1)) if m else ""

            if not level:
                m = re.search(r"(?:办学层次|层次)[：:]\s*([^\n]+)", card_text)
                level = clean_text(m.group(1)) if m else ""

            if not school_type:
                m = re.search(r"(?:学校类型|类型)[：:]\s*([^\n]+)", card_text)
                school_type = clean_text(m.group(1)) if m else ""

            if not satisfaction:
                m = re.search(r"(?:满意度)[：:]\s*([^\d]*[\d.]+[^\d]*[\d]+人?)", card_text)
                satisfaction = clean_text(m.group(1)) if m else ""

            if name and (detail_href or sch_id):
                schools.append({
                    "学校名称": name,
                    "schId": sch_id,
                    "详情页": detail_href,
                    "学校图片": img_src,
                    "主管部门": department,
                    "院校所在地": location,
                    "办学层次": level,
                    "学校类型": school_type,
                    "院校满意度": satisfaction,
                    "列表来源页": page_url,
                    "页码": page_no,
                })

        except Exception as e:
            print(f"[WARN] Failed to parse school card {i}: {repr(e)}")
            continue

    return schools


def get_total_pages(page: Any) -> int:
    """Extract total number of pages from pagination."""
    try:
        # Try different pagination selectors
        pag_selectors = [".pagination", ".ivu-page", ".page"]
        for selector in pag_selectors:
            pag_elem = page.locator(selector).first
            if pag_elem.count() > 0:
                pag_text = clean_text(pag_elem.inner_text())
                # Look for patterns like "共 146 页" or "1 / 146"
                m = re.search(r"共\s*(\d+)\s*页", pag_text)
                if m:
                    return int(m.group(1))
                m = re.search(r"/\s*(\d+)", pag_text)
                if m:
                    return int(m.group(1))
    except Exception:
        pass
    return 0  # Fallback if pagination detection fails


# ============================================================================
# Stage 2: Detail Extraction
# ============================================================================

def extract_detail_header(page: Any, school_url: str) -> Dict:
    """Extract school header information from detail page."""
    try:
        # Try to find header section
        header_selectors = [".school-header", ".header", ".school-info", ".basic-info"]
        header_data = {}

        for selector in header_selectors:
            header_elem = page.locator(selector).first
            if header_elem.count() > 0:
                header_text = clean_text(header_elem.inner_text())

                # Extract title
                title_elem = header_elem.locator("h1, .title").first
                title = clean_text(title_elem.inner_text()) if title_elem.count() > 0 else ""

                # Extract follow count if present
                follow_count = ""
                follow_elem = header_elem.locator(".follow-count, .followers").first
                if follow_elem.count() > 0:
                    follow_text = clean_text(follow_elem.inner_text())
                    m = re.search(r"(\d+)", follow_text)
                    follow_count = m.group(1) if m else ""

                # Extract department/supervisor
                department = ""
                dept_elem = header_elem.locator(".department, .supervisor").first
                if dept_elem.count() > 0:
                    department = clean_text(dept_elem.inner_text())

                # Extract school type
                school_type = ""
                type_elem = header_elem.locator(".school-type, .type").first
                if type_elem.count() > 0:
                    school_type = clean_text(type_elem.inner_text())

                # Extract location
                location = ""
                loc_elem = header_elem.locator(".location, .address").first
                if loc_elem.count() > 0:
                    location = clean_text(loc_elem.inner_text())

                # Extract detailed address
                address = ""
                addr_elem = header_elem.locator(".detailed-address, .full-address").first
                if addr_elem.count() > 0:
                    address = clean_text(addr_elem.inner_text())

                # Extract website
                website = ""
                web_elem = header_elem.locator("a[href*='http'][href*='www'], a[href*='http'][href*='.edu']").first
                if web_elem.count() > 0:
                    website = web_elem.get_attribute("href") or ""

                # Extract enrollment website
                enroll_site = ""
                enroll_elem = header_elem.locator("a[href*='zs'], a[href*='admission']").first
                if enroll_elem.count() > 0:
                    enroll_site = enroll_elem.get_attribute("href") or ""

                # Extract phone
                phone = ""
                phone_elem = header_elem.locator(".phone, .tel").first
                if phone_elem.count() > 0:
                    phone = clean_text(phone_elem.inner_text())

                # Extract school image
                img_src = ""
                img_elem = header_elem.locator("img").first
                if img_elem.count() > 0:
                    img_src = img_elem.get_attribute("src") or ""
                    img_src = urljoin(school_url, img_src)

                header_data = {
                    "标题": title,
                    "学校主链接": school_url,
                    "followCount": follow_count,
                    "主管部门主办单位": department,
                    "院校类型文本": school_type,
                    "所在地": location,
                    "详细地址": address,
                    "官方网站": website,
                    "招生网址": enroll_site,
                    "官方电话": phone,
                    "学校图片": img_src,
                }
                break

        return header_data

    except Exception as e:
        return {"error": repr(e)}


def extract_detail_intro(page: Any) -> Dict:
    """Extract school introduction from detail page."""
    try:
        # Try to find introduction section
        intro_selectors = [".school-intro", ".introduction", ".intro", ".content"]
        intro_data = {"学校简介正文": "", "周边环境": "", "raw_text": ""}

        for selector in intro_selectors:
            intro_elem = page.locator(selector).first
            if intro_elem.count() > 0:
                raw_text = clean_text(intro_elem.inner_text())
                intro_data["raw_text"] = raw_text

                # Try to split into main intro and surroundings
                lines = normalize_lines(raw_text)
                if len(lines) > 1:
                    intro_data["学校简介正文"] = lines[0]
                    if len(lines) > 1:
                        intro_data["周边环境"] = " ".join(lines[1:])
                else:
                    intro_data["学校简介正文"] = raw_text

                break

        return intro_data

    except Exception as e:
        return {"error": repr(e), "学校简介正文": "", "周边环境": "", "raw_text": ""}


def extract_school_detail(context: Any, school_row: Dict) -> Dict:
    """Extract detail page content (Stage 2)."""
    if not school_row["详情页"]:
        return {
            "error": "missing_detail_url",
            "抓取时间": iso_now(),
        }

    detail_page = context.new_page()
    try:
        detail_page.goto(school_row["详情页"], wait_until="domcontentloaded", timeout=60000)
        detail_page.wait_for_timeout(1500)

        header_info = extract_detail_header(detail_page, school_row["详情页"])
        intro_info = extract_detail_intro(detail_page)

        detail = {
            "顶部信息": header_info,
            "intro": intro_info,
            "抓取时间": iso_now(),
        }
        return detail

    except Exception as e:
        return {
            "error": repr(e),
            "详情页": school_row["详情页"],
            "抓取时间": iso_now(),
        }
    finally:
        detail_page.close()


# ============================================================================
# Stage 3: Normalization
# ============================================================================

def build_hierarchy(flat_schools: List[Dict]) -> List[Dict]:
    """Build hierarchical structure from flat school rows."""
    # For schools, we might group by department or location
    # For now, keep it simple as a flat list since no clear hierarchy defined
    return flat_schools


# ============================================================================
# Main
# ============================================================================

def run() -> None:
    """Main execution: Stages 1-3."""
    ensure_output()

    flat_schools = []
    seen_school = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        try:
            # Stage 1: Navigate and extract list data
            start_page = 0
            page_no = 1

            while True:
                page_url = BASE_URL_PATTERN.format(start=start_page)
                print(f"[INFO] Loading page {page_no}: {page_url}")

                page.goto(page_url, wait_until="domcontentloaded", timeout=60000)
                wait_list_ready(page)
                save_debug(page, f"01_page_{page_no}")

                schools = extract_school_cards(page, page_url, page_no)
                print(f"[INFO] Extracted {len(schools)} schools from page {page_no}")

                for school in schools:
                    key = school["schId"] or (
                        school["学校名称"],
                        school["详情页"],
                    )
                    if key in seen_school:
                        continue
                    seen_school.add(key)

                    # Stage 2: Extract detail data
                    if SCRAPE_DETAILS:
                        school["详情"] = extract_school_detail(context, school)
                    else:
                        school["详情"] = {}

                    flat_schools.append(school)

                write_partial(flat_schools)

                # Check if there are more pages
                total_pages = get_total_pages(page)
                if total_pages > 0 and page_no >= total_pages:
                    break

                # Try next page
                next_start = start_page + 20
                if next_start > 2900:  # Safety limit from ai/10_target_sites.md
                    break

                start_page = next_start
                page_no += 1

            save_debug(page, "02_done")

        except PlaywrightTimeoutError as e:
            save_debug(page, "timeout")
            write_partial(flat_schools)
            raise e
        except Exception as e:
            save_debug(page, "error")
            write_partial(flat_schools)
            raise e
        finally:
            context.close()
            browser.close()

    # Stage 3: Normalize and output
    all_json = {
        "抓取时间": iso_now(),
        "来源": BASE_URL_PATTERN,
        "学校列表": build_hierarchy(flat_schools),
    }

    flat_json = {
        "抓取时间": iso_now(),
        "来源": BASE_URL_PATTERN,
        "数量": len(flat_schools),
        "学校列表": flat_schools,
    }

    meta_json = {
        "抓取时间": iso_now(),
        "来源": BASE_URL_PATTERN,
        "学校总数": len(flat_schools),
        "是否抓详情": SCRAPE_DETAILS,
    }

    save_json(OUTPUT_DIR / "all.json", all_json)
    save_json(OUTPUT_DIR / "schools-flat.json", flat_json)
    save_json(OUTPUT_DIR / "meta.json", meta_json)

    print(f"[DONE] schools={len(flat_schools)}, detail={SCRAPE_DETAILS}")


if __name__ == "__main__":
    run()
