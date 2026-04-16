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

SAVE_DEBUG = os.getenv("SAVE_DEBUG", "1") == "1"  # Enable debug by default for testing
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

    # Also save basic page info for debugging
    try:
        title = page.title()
        url = page.url
        body_text = page.locator("body").inner_text()[:1000]  # First 1000 chars
        (OUTPUT_DIR / f"{name}.txt").write_text(
            f"Title: {title}\nURL: {url}\n\nBody preview:\n{body_text}",
            encoding="utf-8"
        )
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
    # More flexible waiting - try multiple selectors and conditions
    try:
        # First, wait for basic page load
        page.wait_for_load_state("domcontentloaded", timeout=30000)

        # Try different main container selectors
        main_selectors = ["#app", "body", ".container", ".main"]
        main_found = False
        for selector in main_selectors:
            try:
                page.wait_for_selector(selector, timeout=5000)
                main_found = True
                break
            except:
                continue

        if not main_found:
            print("[WARN] No main container found, proceeding anyway")

        # Wait for school-related content
        content_checks = [
            lambda: page.locator("text=/院校|学校|大学|学院/").count() > 0,
            lambda: len(page.locator("a[href*='schschoolInfo']").all()) > 0,
            lambda: page.locator(".sch-card, .school-item, .card, .school-card").count() > 0,
        ]

        content_found = False
        for check in content_checks:
            try:
                page.wait_for_function(f"() => {check.__name__}()", timeout=10000)
                content_found = True
                break
            except:
                continue

        if not content_found:
            print("[WARN] No school content indicators found, proceeding anyway")

        # Final wait for stability
        page.wait_for_timeout(2000)

    except Exception as e:
        print(f"[WARN] Page wait failed: {repr(e)}, proceeding anyway")
        page.wait_for_timeout(3000)


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
    # Try multiple card selectors
    card_selectors = [
        ".sch-card", ".school-item", ".card", ".school-card",
        "[class*='school']", "[class*='card']", ".item"
    ]

    cards = None
    for selector in card_selectors:
        try:
            elements = page.locator(selector)
            if elements.count() > 0:
                # Additional check: make sure they contain school-like content
                for i in range(min(elements.count(), 5)):  # Check first 5
                    text = clean_text(elements.nth(i).inner_text())
                    if any(keyword in text for keyword in ['大学', '学院', '学校', '师范大学']):
                        cards = elements
                        break
                if cards:
                    break
        except Exception:
            continue

    if not cards or cards.count() == 0:
        print(f"[WARN] No school cards found on page {page_no}, trying fallback extraction")
        # Fallback: try to extract from any links containing school info
        fallback_schools = []
        try:
            all_links = page.locator("a[href*='schschoolInfo']")
            for i in range(min(all_links.count(), 50)):  # Limit to avoid too many
                link_elem = all_links.nth(i)
                href = link_elem.get_attribute("href") or ""
                text = clean_text(link_elem.inner_text())

                if text and any(keyword in text for keyword in ['大学', '学院', '学校']):
                    sch_id = extract_sch_id(urljoin(page_url, href))
                    fallback_schools.append({
                        "学校名称": text,
                        "schId": sch_id,
                        "详情页": urljoin(page_url, href),
                        "学校图片": "",
                        "主管部门": "",
                        "院校所在地": "",
                        "办学层次": "",
                        "学校类型": "",
                        "院校满意度": "",
                        "列表来源页": page_url,
                        "页码": page_no,
                    })
        except Exception as e:
            print(f"[WARN] Fallback extraction failed: {repr(e)}")

        return fallback_schools

    schools = []
    for i in range(cards.count()):
        try:
            card = cards.nth(i)
            card_text = clean_text(card.inner_text())

            # Skip if doesn't look like a school
            if not any(keyword in card_text for keyword in ['大学', '学院', '学校']):
                continue

            # Extract school name - try multiple approaches
            name = ""
            name_selectors = ["h3", ".school-name", ".name", ".title"]
            for sel in name_selectors:
                try:
                    name_elem = card.locator(sel).first
                    if name_elem.count() > 0:
                        name = clean_text(name_elem.inner_text())
                        if name:
                            break
                except:
                    continue

            # If still no name, try to extract from text
            if not name:
                lines = card_text.split('\n')
                for line in lines:
                    line = clean_text(line)
                    if any(keyword in line for keyword in ['大学', '学院', '学校']):
                        name = line
                        break

            if not name:
                continue

            # Extract detail link
            detail_href = ""
            try:
                link_elem = card.locator("a[href*='schschoolInfo']").first
                if link_elem.count() > 0:
                    detail_href = link_elem.get_attribute("href") or ""
                    detail_href = urljoin(page_url, detail_href)
            except:
                pass

            # Extract schId from URL
            sch_id = extract_sch_id(detail_href)

            # Extract image
            img_src = ""
            try:
                img_elem = card.locator("img").first
                if img_elem.count() > 0:
                    img_src = img_elem.get_attribute("src") or ""
                    img_src = urljoin(page_url, img_src)
            except:
                pass

            # Parse other fields from card text using regex patterns
            department = ""
            location = ""
            level = ""
            school_type = ""
            satisfaction = ""

            # Try to extract structured info
            patterns = {
                'department': r'(?:主管|隶属|主办)[：:]\s*([^\n]+)',
                'location': r'(?:所在地|地址)[：:]\s*([^\n]+)',
                'level': r'(?:办学层次|层次)[：:]\s*([^\n]+)',
                'school_type': r'(?:学校类型|类型)[：:]\s*([^\n]+)',
                'satisfaction': r'(\d+(?:\.\d+)?)\s*分?\s*([0-9]+人)?',
            }

            for field, pattern in patterns.items():
                m = re.search(pattern, card_text, re.IGNORECASE)
                if m:
                    if field == 'satisfaction':
                        score = m.group(1)
                        count = m.group(2) if len(m.groups()) > 1 else ""
                        satisfaction = f"{score}分{count}".strip()
                    else:
                        locals()[field] = clean_text(m.group(1))

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
        # Try different pagination selectors and patterns
        pag_selectors = [".pagination", ".ivu-page", ".page", "[class*='page']"]
        for selector in pag_selectors:
            try:
                pag_elem = page.locator(selector).first
                if pag_elem.count() > 0:
                    pag_text = clean_text(pag_elem.inner_text())
                    # Look for various patterns
                    patterns = [
                        r"共\s*(\d+)\s*页",
                        r"/\s*(\d+)",
                        r"(\d+)\s*页",
                        r"共(\d+)页",
                    ]
                    for pattern in patterns:
                        m = re.search(pattern, pag_text)
                        if m:
                            pages = int(m.group(1))
                            if 1 <= pages <= 200:  # Reasonable bounds
                                return pages
            except:
                continue

        # Try to find pagination links
        page_links = page.locator("a[href*='start-'], .ivu-page-item, [class*='page'] a")
        max_page = 0
        for i in range(page_links.count()):
            try:
                link_elem = page_links.nth(i)
                href = link_elem.get_attribute("href") or ""
                text = clean_text(link_elem.inner_text())

                # Extract page number from URL
                m = re.search(r"start-(\d+)", href)
                if m:
                    page_num = int(m.group(1)) // 20 + 1
                    max_page = max(max_page, page_num)

                # Or from text
                if text.isdigit():
                    max_page = max(max_page, int(text))
            except:
                continue

        if max_page > 0:
            return max_page

    except Exception as e:
        print(f"[WARN] Failed to detect total pages: {repr(e)}")

    # Fallback: assume at least 10 pages based on ai/10_target_sites.md
    return 10


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
            max_pages = 5  # Limit for testing, can be increased

            while page_no <= max_pages:
                page_url = BASE_URL_PATTERN.format(start=start_page)
                print(f"[INFO] Loading page {page_no}: {page_url}")

                page.goto(page_url, wait_until="domcontentloaded", timeout=60000)
                wait_list_ready(page)
                save_debug(page, f"01_page_{page_no}")

                schools = extract_school_cards(page, page_url, page_no)
                print(f"[INFO] Extracted {len(schools)} schools from page {page_no}")

                if schools:
                    for school in schools[:3]:  # Log first 3 schools for debugging
                        print(f"[DEBUG] Sample school: {school['学校名称']} (schId: {school['schId']})")

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
                print(f"[INFO] Detected total pages: {total_pages}")

                if page_no >= total_pages or page_no >= max_pages:
                    break

                # Try next page
                start_page += 20
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
