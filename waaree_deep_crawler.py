#!/usr/bin/env python3
"""
Waaree Solar Telemetry Engine v4.0 — Bulletproof Edition
=========================================================
Root-cause analysis from diagnostic HTML snapshots:
  ✓ Login page: title="SIGN IN", form uses Element UI (el-input__inner)
  ✓ Login SUCCEEDS — post-click title changes to "Home", username visible
  ✗ PROBLEM: After login, lands on Home index (just a bg image), NOT plant page
  ✗ Vue router navigation to plant/overview needs explicit wait + retry
  ✗ dashboard_wait_timeout occurs because plant data elements aren't loaded yet

This rewrite addresses every failure point with:
  • Phase-gated login: load → verify form → fill → click → verify Home title
  • Explicit SPA navigation with Vue router hash awareness
  • Plant page arrival confirmation via plant-specific CSS selectors
  • Screenshot + HTML + text dump at EVERY phase transition
  • OCR text parsing to diagnose hangs
  • Structured diagnostic logging with phase/state tracking
"""

import time
import csv
import json
import pickle
import os
import sys
import datetime
import re
import subprocess
import shutil
import hashlib
import traceback
import statistics
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, StaleElementReferenceException,
    NoSuchElementException, WebDriverException,
    ElementClickInterceptedException, ElementNotInteractableException
)
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

# Anti-detection: undetected-chromedriver patches Chrome binary to bypass WAF/bot detection
try:
    import undetected_chromedriver as uc
    HAS_UC = True
except ImportError:
    HAS_UC = False

# Import analytics engine
try:
    from solar_analytics import run_analytics
    HAS_ANALYTICS = True
except ImportError:
    HAS_ANALYTICS = False


# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════
CREDENTIALS_FILE = "credentials.json"

try:
    with open(CREDENTIALS_FILE, "r") as f:
        creds = json.load(f)
        USERNAME = creds["username"]
        PASSWORD = creds["password"]
        PLANT_ID = creds["plant_id"]
        PLANT_CAPACITY_KW = float(creds.get("plant_capacity_kw", 2.32))
        DAILY_REALISTIC_MAX_KWH = float(creds.get("daily_realistic_max_kwh", 12.0))
        LOCATION = creds.get("location", "Berhampur, Odisha")
except Exception as e:
    print(f"[FATAL] credentials.json load failed: {e}")
    sys.exit(1)

HEADLESS = True
COOKIE_FILE = "waaree_session.pkl"
CSV_FILE = "waaree_telemetry_log.csv"
JSON_DASHBOARD_FILE = "dashboard_data.json"
SNAPSHOT_DIR = "system_snapshots"
DIAGNOSTICS_DIR = "diagnostics"

BASE_URL = "https://digital.waaree.com"
LOGIN_URL = f"{BASE_URL}/#/bus/login"  # Vue SPA hash routing (redirects to /login#/bus/login)
LOGIN_URL_ALT = BASE_URL  # Root also shows login form
HOME_URL = f"{BASE_URL}/bus/index"  # Post-login uses real server paths (NOT hash)
PLANT_URL = f"{BASE_URL}/bus/plant/overview?id={PLANT_ID}"  # Real server path
PLANT_URL_HASH = f"{BASE_URL}/#/bus/plant/overview?id={PLANT_ID}"  # Hash fallback
PLANT_URL_CANDIDATES = [
    f"{BASE_URL}/bus/plant/overview?id={PLANT_ID}",
    f"{BASE_URL}/bus/plant/detail?id={PLANT_ID}",
    f"{BASE_URL}/bus/plant/view?id={PLANT_ID}",
    f"{BASE_URL}/#/bus/plant/overview?id={PLANT_ID}",
    f"{BASE_URL}/#/bus/plant/detail?id={PLANT_ID}",
    f"{BASE_URL}/#/bus/plant/view?id={PLANT_ID}",
]

# ── Timing ──
MAX_LOGIN_RETRIES = 4
LOGIN_BACKOFF_BASE = 4
PAGE_LOAD_TIMEOUT = 30
VUE_RENDER_WAIT = 8
SCRAPE_INTERVAL = 60
MAX_HISTORY_POINTS = 288
SESSION_MAX_AGE_HOURS = 4
ELEMENT_WAIT = 15

# ── Portal validation ──
PORTAL_KEYWORDS = [
    "Power Generating", "Today Yield", "Total Yield",
    "Inverter", "Sites", "Plant", "kW", "kWh"
]

# ── Exact selectors discovered from DOM analysis ──
# Login page (Element UI form)
SEL_USERNAME_INPUT = "input.el-input__inner[placeholder='Username']"
SEL_PASSWORD_INPUT = "input.el-input__inner[placeholder='Password']"
SEL_LOGIN_BTN = "button.login-click.el-button--primary"
SEL_LOGIN_BTN_FALLBACK = "button.el-button--primary"

# Post-login Home page indicators
SEL_HOME_BREADCRUMB = ".el-breadcrumb__inner"
SEL_USER_TAG = ".el-tag.el-tag--small"
SEL_SIDEBAR_MENU = ".el-menu"
SEL_SIDEBAR_SITES = ".sub-title"  # contains text "Sites", "Overview", etc.

# Plant detail page data selectors
SEL_PLANT_MONEY = ".plant-money span"
SEL_DETAIL_BOX = ".detail-box"
SEL_TABLE_ROW = ".el-table__row"
SEL_TABLE_CELL = ".cell"
SEL_TABS_ITEM = ".el-tabs__item"
SEL_CONTENT_ITEM = ".content-item"
SEL_WEATHER_DATE = ".date"

for d in [SNAPSHOT_DIR, DIAGNOSTICS_DIR]:
    Path(d).mkdir(exist_ok=True)


# ═══════════════════════════════════════════════════════════════
# LOGGING & DIAGNOSTICS
# ═══════════════════════════════════════════════════════════════
def log(level, msg):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    icons = {
        "INFO": "ℹ️", "WARN": "⚠️", "ERROR": "❌", "OK": "✅",
        "NAV": "🧭", "DATA": "📊", "AUTH": "🔐", "SYS": "⚙️",
        "DIAG": "🔬", "PHASE": "🔷"
    }
    print(f"[{ts}] {icons.get(level, '•')} [{level}] {msg}")


def to_float(val, default=0.0):
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    text = str(val).replace(",", "").replace(" ", "")
    m = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(m.group(0)) if m else default


def is_hard_error_page(title, body_text, url):
    t = (title or "").strip().lower()
    b = (body_text or "").lower()
    u = (url or "").lower()

    # Strict checks only: avoid false positives from menu labels like "Error List"
    if t in {"403", "404", "500", "502", "503"}:
        return True
    if "/error/" in u:
        return True
    if re.search(r"\b(403|404|500|502|503)\b", b):
        return True
    if "forbidden" in b or "page not found" in b:
        return True
    if "power station does not exist" in b:
        return True
    return False


def is_valid_data_point(packet):
    """Return True only if the data point has real non-zero telemetry worth saving.

    We reject:
      - Error pages (403, 404, station-not-found)
      - Extraction that yielded all-zero core metrics
      - Portal not loaded with no extraction method
    """
    # Must have at least one non-zero core metric
    power = to_float(packet.get("current_power_kw", packet.get("current_power", 0)))
    daily = to_float(packet.get("daily_yield_kwh", packet.get("daily_yield", 0)))
    total = to_float(packet.get("total_yield_kwh", packet.get("total_yield", 0)))
    voltage = to_float(packet.get("voltage_v", packet.get("voltage_sample", 0)))

    has_any_value = (power > 0 or daily > 0 or total > 0 or voltage > 0)

    # Reject if OCR excerpt indicates an error page
    ocr = (packet.get("portal_ocr_excerpt") or "").lower()
    is_error = any(k in ocr for k in [
        "403 forbidden", "404", "page not found",
        "power station does not exist",
    ])

    if is_error:
        return False

    # Reject if portal didn't load and no valid extraction
    method = packet.get("extraction_method", "none")
    portal_loaded = packet.get("portal_loaded", False)
    if not portal_loaded and method == "none" and not has_any_value:
        return False

    # Reject all-zero extractions even if portal "loaded" (CSS returned 0.00s)
    if not has_any_value:
        return False

    return True


def discover_runtime_plant_urls(driver):
    """Discover candidate plant routes from live DOM/router metadata each run."""
    discovered = []
    seen = set()

    def add_url(raw):
        if not raw:
            return
        url = str(raw).strip()
        if not url:
            return

        # Normalize relative links
        if url.startswith("/"):
            url = f"{BASE_URL}{url}"
        elif url.startswith("#"):
            url = f"{BASE_URL}/{url}"

        url_l = url.lower()
        # Keep only plant-relevant candidates
        if not any(k in url_l for k in ["/plant/", "overview", "detail", "view", "/bus/"]):
            return
        if "login" in url_l or "error" in url_l:
            return
        if PLANT_ID and ("id=" in url_l) and (f"id={PLANT_ID}" not in url_l):
            return

        if url not in seen:
            seen.add(url)
            discovered.append(url)

    # 1) Parse current URL first (already-resolved route can be useful)
    try:
        add_url(driver.current_url)
    except Exception:
        pass

    # 2) Extract href/to/index/data-path from live DOM
    try:
        attrs = driver.execute_script(
            """
            const attrs = [];
            const selectors = 'a,button,li,div,span';
            const nodes = Array.from(document.querySelectorAll(selectors));
            for (const n of nodes) {
              const vals = [
                n.getAttribute('href'),
                n.getAttribute('to'),
                n.getAttribute('index'),
                n.getAttribute('data-path'),
                n.getAttribute('data-url'),
                n.getAttribute('router-link')
              ];
              for (const v of vals) {
                if (v) attrs.push(v);
              }
            }
            return attrs;
            """
        ) or []
        for v in attrs:
            add_url(v)
    except Exception:
        pass

    # 3) Derive route from active tab id (observed: tab-bus-plant-detail)
    try:
        active_tabs = driver.find_elements(By.CSS_SELECTOR, ".el-tabs__item.is-active")
        for tab in active_tabs:
            tid = (tab.get_attribute("id") or "").strip()
            # e.g. tab-bus-plant-detail -> /bus/plant/detail?id=...
            m = re.search(r"tab-(bus-[a-zA-Z0-9-]+)", tid)
            if m:
                seg = m.group(1).replace("-", "/")
                add_url(f"{BASE_URL}/{seg}?id={PLANT_ID}")
    except Exception:
        pass

    return discovered


def click_text_sequence(driver, labels):
    """Best-effort click sequence by visible text labels."""
    for label in labels:
        clicked = False
        # Prefer exact visible sub-title labels in sidebar/menu
        xpaths = [
            f"//*[contains(@class,'sub-title') and normalize-space()='{label}']",
            f"//*[self::span or self::a or self::div or self::li][normalize-space()='{label}']",
            f"//*[contains(@class,'el-menu-item') and .//*[normalize-space()='{label}']]",
        ]
        for xp in xpaths:
            try:
                elems = driver.find_elements(By.XPATH, xp)
                for e in elems:
                    if not e.is_displayed():
                        continue
                    try:
                        driver.execute_script(
                            "arguments[0].scrollIntoView({block:'center'});", e
                        )
                    except Exception:
                        pass
                    try:
                        driver.execute_script("arguments[0].click();", e)
                    except Exception:
                        e.click()
                    clicked = True
                    time.sleep(1.2)
                    break
                if clicked:
                    break
            except Exception:
                continue
        if not clicked:
            return False
    return True


def navigate_to_plant_page(driver, timeout_per_url=14):
    """Navigate to plant view via dynamic discovery + UI clicks (static URLs are final fallback)."""

    def has_plant_signals():
        try:
            body = driver.find_element(By.TAG_NAME, "body").text.lower()
            url = (driver.current_url or "").lower()
            title = (driver.title or "").lower()

            # URL/title-based confidence (dynamic routes can load before text widgets)
            if PLANT_ID.lower() in url and any(k in url for k in ["/bus/plant/detail", "/bus/plant/overview", "/bus/plant/view"]):
                return True
            if "sites detail" in title and "/bus/plant/" in url:
                return True

            return any(k in body for k in [
                "power generating", "today yield", "total yield", "kwh", "inverter"
            ])
        except Exception:
            return False

    # Fast path: already on plant page
    if has_plant_signals():
        return True

    # Strategy A: discover runtime URLs from current live DOM and try them
    runtime_urls = discover_runtime_plant_urls(driver)
    if runtime_urls:
        log("DIAG", f"Discovered {len(runtime_urls)} runtime route candidates")

    for i, url in enumerate(runtime_urls, start=1):
        log("DIAG", f"Runtime route {i}/{len(runtime_urls)}: ...{url[-80:]}")
        try:
            driver.get(url)
        except Exception as e:
            log("WARN", f"Runtime route navigation failed: {e}")
            continue

        started = time.time()
        while time.time() - started < timeout_per_url:
            time.sleep(2)
            try:
                title = driver.title
                current = driver.current_url
                body = driver.find_element(By.TAG_NAME, "body").text

                if is_hard_error_page(title, body, current):
                    log("WARN", f"Hard error on runtime route: title='{title}' url=...{current[-55:]}")
                    break

                if has_plant_signals():
                    return True
            except Exception:
                pass

    # Strategy B: UI click path then discover routes again
    try:
        log("DIAG", "UI crawl: clicking Sites -> My Sites")
        click_text_sequence(driver, ["Sites", "My Sites"])
        time.sleep(3)

        # Re-discover URLs after menu navigation
        runtime_urls_2 = discover_runtime_plant_urls(driver)
        for i, url in enumerate(runtime_urls_2[:12], start=1):
            log("DIAG", f"Post-menu runtime route {i}/{len(runtime_urls_2)}: ...{url[-80:]}")
            try:
                driver.get(url)
                time.sleep(3)
                if has_plant_signals():
                    return True
            except Exception:
                continue

        # Finally click visible Overview entries dynamically
        overview_actions = driver.find_elements(
            By.XPATH,
            "//*[self::a or self::button or self::span or self::li][contains(normalize-space(.), 'Overview')]"
        )
        for act in overview_actions[:8]:
            try:
                if not act.is_displayed():
                    continue
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", act)
                try:
                    driver.execute_script("arguments[0].click();", act)
                except Exception:
                    act.click()
                time.sleep(4)
                if has_plant_signals():
                    return True
            except Exception:
                continue

        # If still no signals, try discovered URLs one more time from this state
        runtime_urls_3 = discover_runtime_plant_urls(driver)
        for url in runtime_urls_3[:8]:
            try:
                driver.get(url)
                time.sleep(3)
                if has_plant_signals():
                    return True
            except Exception:
                continue
    except Exception as e:
        log("WARN", f"UI fallback navigation failed: {e}")

    # Strategy C (last resort): static URL candidates
    for i, url in enumerate(PLANT_URL_CANDIDATES, start=1):
        log("DIAG", f"Static route fallback {i}/{len(PLANT_URL_CANDIDATES)}: ...{url[-70:]}")
        try:
            driver.get(url)
            time.sleep(3)
            if has_plant_signals():
                return True
        except Exception:
            continue

    return False


class Diagnostics:
    """Comprehensive diagnostics at every phase transition."""

    @staticmethod
    def capture(driver, phase_name, save_html=True, parse_text=True):
        """Full diagnostic capture: screenshot, HTML source, visible text analysis."""
        ts = datetime.datetime.now().strftime("%H%M%S")
        prefix = f"{ts}_{phase_name}"
        result = {
            "phase": phase_name,
            "timestamp": ts,
            "url": "",
            "title": "",
            "visible_text_excerpt": "",
            "page_state": "unknown",
            "screenshot_path": "",
            "html_path": "",
            "errors_detected": [],
        }

        try:
            result["url"] = driver.current_url
            result["title"] = driver.title
        except Exception:
            result["errors_detected"].append("cannot_read_url_or_title")

        # Screenshot
        png_path = f"{DIAGNOSTICS_DIR}/{prefix}.png"
        try:
            driver.save_screenshot(png_path)
            result["screenshot_path"] = png_path
        except Exception as e:
            result["errors_detected"].append(f"screenshot_failed: {e}")

        # HTML source dump
        if save_html:
            html_path = f"{DIAGNOSTICS_DIR}/{prefix}.html"
            try:
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                result["html_path"] = html_path
            except Exception as e:
                result["errors_detected"].append(f"html_dump_failed: {e}")

        # Visible text parsing
        if parse_text:
            try:
                body_text = driver.find_element(By.TAG_NAME, "body").text
                result["visible_text_excerpt"] = body_text[:500]

                # Classify page state from visible text and title
                title = result["title"].lower()
                text_lower = body_text.lower()
                url = result["url"].lower()

                if ("sign in" in title or "sign in" in text_lower
                        or ("waaree" in title and "sign in" in text_lower)
                        or ("sign up" in text_lower and "password" in text_lower)):
                    result["page_state"] = "login_page"
                elif "home" in title and ("overview" in text_lower or "sites" in text_lower):
                    result["page_state"] = "home_dashboard"
                elif "plant" in url and any(seg in url for seg in ["overview", "detail", "view"]):
                    if any(kw.lower() in text_lower for kw in ["power generating", "today yield", "total yield"]):
                        result["page_state"] = "plant_detail_loaded"
                    else:
                        result["page_state"] = "plant_detail_loading"
                elif "sites detail" in title and "plant" in url:
                    result["page_state"] = "plant_detail_loading"
                elif "login" in url:
                    result["page_state"] = "login_page"
                elif "index" in url:
                    result["page_state"] = "home_dashboard"
                else:
                    result["page_state"] = "unknown_page"

                # Check for error indicators
                if is_hard_error_page(result["title"], body_text, result["url"]):
                    result["errors_detected"].append("error_page_detected")
                if "captcha" in text_lower:
                    result["errors_detected"].append("captcha_detected")
                if "loading" in text_lower and len(body_text.strip()) < 50:
                    result["errors_detected"].append("page_still_loading")

            except Exception as e:
                result["errors_detected"].append(f"text_extraction_failed: {e}")

        log("DIAG", f"[{phase_name}] state={result['page_state']} "
                     f"title='{result['title']}' url_tail=...{result['url'][-50:]}")

        if result["errors_detected"]:
            log("WARN", f"[{phase_name}] issues: {result['errors_detected']}")

        return result

    @staticmethod
    def extract_ocr_text(image_path):
        if not image_path or not os.path.exists(image_path):
            return ""
        tess = shutil.which("tesseract")
        if not tess:
            return ""
        try:
            result = subprocess.run(
                [tess, image_path, "stdout", "--psm", "6"],
                capture_output=True, text=True, timeout=20
            )
            return (result.stdout or "").strip()
        except Exception:
            return ""


def cleanup_old_diagnostics(max_keep=100):
    try:
        for ext in ["*.png", "*.html"]:
            files = sorted(Path(DIAGNOSTICS_DIR).glob(ext), key=os.path.getmtime)
            if len(files) > max_keep:
                for f in files[:len(files) - max_keep]:
                    f.unlink(missing_ok=True)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════
# BROWSER ENGINE
# ═══════════════════════════════════════════════════════════════
class BrowserEngine:
    def __init__(self):
        self.driver = None
        self.wait = None
        self._session_start = None

    def start(self):
        log("SYS", "Launching Chrome...")

        if HAS_UC:
            # ── undetected-chromedriver: patches Chrome binary to bypass WAF ──
            log("SYS", "Using undetected-chromedriver (stealth mode)")
            uc_opts = uc.ChromeOptions()
            if HEADLESS:
                uc_opts.add_argument("--headless=new")
            uc_opts.add_argument("--no-sandbox")
            uc_opts.add_argument("--disable-dev-shm-usage")
            uc_opts.add_argument("--disable-gpu")
            uc_opts.add_argument("--window-size=1920,1080")
            uc_opts.add_argument("--disable-popup-blocking")
            uc_opts.add_argument("--ignore-certificate-errors")

            self.driver = uc.Chrome(options=uc_opts, use_subprocess=True)
        else:
            # ── Standard Selenium with best-effort stealth ──
            log("WARN", "undetected-chromedriver not available, using standard Selenium")
            opts = Options()
            if HEADLESS:
                opts.add_argument("--headless=new")
            opts.add_argument("--no-sandbox")
            opts.add_argument("--disable-dev-shm-usage")
            opts.add_argument("--disable-gpu")
            opts.add_argument("--window-size=1920,1080")
            opts.add_argument("--disable-extensions")
            opts.add_argument("--disable-popup-blocking")
            opts.add_argument("--ignore-certificate-errors")
            opts.add_argument("--disable-blink-features=AutomationControlled")
            opts.add_argument(
                "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            )
            opts.add_experimental_option("excludeSwitches", ["enable-automation"])
            opts.add_experimental_option("useAutomationExtension", False)
            opts.page_load_strategy = "normal"

            svc = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=svc, options=opts)

        self.driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)

        # ── Comprehensive stealth JavaScript patches ──
        stealth_js = """
            // Hide webdriver flag
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            // Fake plugins (headless has 0 plugins)
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    {name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer'},
                    {name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai'},
                    {name: 'Native Client', filename: 'internal-nacl-plugin'}
                ]
            });
            // Fake languages
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            // Fix chrome.runtime (missing in headless)
            window.chrome = window.chrome || {};
            window.chrome.runtime = window.chrome.runtime || {};
            // Fake permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) =>
                parameters.name === 'notifications'
                    ? Promise.resolve({state: Notification.permission})
                    : originalQuery(parameters);
            // Fix WebGL vendor
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) return 'Intel Inc.';
                if (parameter === 37446) return 'Intel Iris OpenGL Engine';
                return getParameter.apply(this, arguments);
            };
        """
        try:
            self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": stealth_js
            })
        except Exception:
            # undetected_chromedriver may not support CDP commands the same way
            try:
                self.driver.execute_script(stealth_js)
            except Exception:
                log("WARN", "Could not inject stealth JS (non-critical)")

        self.wait = WebDriverWait(self.driver, ELEMENT_WAIT)
        self._session_start = datetime.datetime.now()
        log("OK", "Chrome launched.")
        return self

    def stop(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
        log("SYS", "Chrome stopped.")

    def is_alive(self):
        if not self.driver:
            return False
        try:
            _ = self.driver.current_url
            return True
        except Exception:
            return False

    def session_age_hours(self):
        if not self._session_start:
            return float("inf")
        return (datetime.datetime.now() - self._session_start).total_seconds() / 3600

    def restart(self):
        log("WARN", "Restarting Chrome...")
        self.stop()
        time.sleep(2)
        return self.start()


# ═══════════════════════════════════════════════════════════════
# SESSION PERSISTENCE
# ═══════════════════════════════════════════════════════════════
class SessionManager:
    @staticmethod
    def save(driver):
        try:
            with open(COOKIE_FILE, "wb") as f:
                pickle.dump({
                    "cookies": driver.get_cookies(),
                    "saved_at": datetime.datetime.now().isoformat(),
                    "url": driver.current_url
                }, f)
            log("OK", "Session saved.")
            return True
        except Exception as e:
            log("WARN", f"Session save failed: {e}")
            return False

    @staticmethod
    def load(driver):
        if not os.path.exists(COOKIE_FILE):
            return False
        try:
            with open(COOKIE_FILE, "rb") as f:
                data = pickle.load(f)
            cookies = data.get("cookies", []) if isinstance(data, dict) else data
            saved_at = data.get("saved_at", "") if isinstance(data, dict) else ""

            if saved_at:
                age = datetime.datetime.now() - datetime.datetime.fromisoformat(saved_at)
                if age.total_seconds() > SESSION_MAX_AGE_HOURS * 3600:
                    log("WARN", f"Session expired ({age}).")
                    return False

            # Must be on the domain first to inject cookies
            driver.get(BASE_URL)
            time.sleep(3)
            driver.delete_all_cookies()
            injected = 0
            for c in cookies:
                for k in ["sameSite", "expiry"]:
                    c.pop(k, None)
                try:
                    driver.add_cookie(c)
                    injected += 1
                except Exception:
                    pass
            log("OK", f"Session restored ({injected} cookies).")
            return injected > 0
        except Exception as e:
            log("WARN", f"Session load error: {e}")
            return False

    @staticmethod
    def invalidate():
        try:
            if os.path.exists(COOKIE_FILE):
                os.remove(COOKIE_FILE)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════
# AUTHENTICATOR — Phase-gated login with full diagnostics
# ═══════════════════════════════════════════════════════════════
class Authenticator:
    """
    Phase-gated login process:
      PHASE 1: Load login page, verify title = "SIGN IN"
      PHASE 2: Locate exact form fields (el-input__inner with placeholders)
      PHASE 3: Fill credentials with human-like typing
      PHASE 4: Click login button (button.login-click)
      PHASE 5: Verify title changes from "SIGN IN" to "Home"
      PHASE 6: Verify sidebar menu + username tag visible
      PHASE 7: Navigate to plant detail page
      PHASE 8: Verify plant data elements present
    """

    @staticmethod
    def login(engine, force=False):
        driver = engine.driver
        wait = engine.wait

        for attempt in range(1, MAX_LOGIN_RETRIES + 1):
            backoff = LOGIN_BACKOFF_BASE * (2 ** (attempt - 1))
            log("AUTH", f"═══ Login Attempt {attempt}/{MAX_LOGIN_RETRIES} ═══")

            try:
                # ── PHASE 1: Load login page ──
                log("PHASE", "1/8 — Loading login page...")

                # Don't aggressively delete cookies — triggers WAF 403
                # Only clear on retry attempts
                if attempt > 1:
                    try:
                        driver.delete_all_cookies()
                    except Exception:
                        pass
                    time.sleep(2)

                # Try multiple login URLs — Vue SPA uses hash routing
                login_urls = [LOGIN_URL, LOGIN_URL_ALT]
                login_found = False
                for login_url in login_urls:
                    log("DIAG", f"Trying: {login_url}")
                    driver.get(login_url)

                    # ── Smart Vue render wait: poll for login form instead of fixed sleep ──
                    # Vue SPA loads shell HTML instantly, then mounts components async.
                    # Wait for the actual login form input to appear in DOM.
                    vue_ready = False
                    for vue_tick in range(1, 16):  # Up to 15 seconds
                        time.sleep(1)
                        try:
                            forms = driver.find_elements(By.CSS_SELECTOR,
                                "input[placeholder='Username'], input[placeholder='Password'], "
                                ".el-form input.el-input__inner")
                            if forms:
                                log("DIAG", f"Vue rendered login form in {vue_tick}s")
                                vue_ready = True
                                break
                            # Also check if we're already on dashboard (session still alive)
                            title_now = driver.title.strip().lower()
                            if title_now in ("home", "dashboard"):
                                log("OK", "Already authenticated! Skipping login.")
                                engine._session_start = datetime.datetime.now()
                                return True
                        except Exception:
                            pass

                    if not vue_ready:
                        log("DIAG", f"Vue didn't render form after 15s, checking page state...")

                    diag = Diagnostics.capture(driver, f"P1_login_load_a{attempt}")

                    # Check for 404 redirect
                    if "/error/404" in driver.current_url or "404" in (diag.get("visible_text_excerpt", "")):
                        log("WARN", f"{login_url} returned 404. Trying next...")
                        continue

                    # Check for 403 WAF block
                    if "403" in driver.title or "403" in (diag.get("visible_text_excerpt", "") or ""):
                        log("WARN", f"{login_url} returned 403 (WAF). Trying next...")
                        continue

                    if diag["page_state"] == "login_page":
                        login_found = True
                        break
                    elif diag["page_state"] in ("home_dashboard", "plant_detail_loaded"):
                        log("OK", "Already authenticated! Skipping login.")
                        engine._session_start = datetime.datetime.now()
                        return True

                    # Check body text for login form indicators
                    body = driver.find_element(By.TAG_NAME, "body").text
                    if "sign in" in body.lower() or "username" in body.lower() or "password" in body.lower():
                        login_found = True
                        break

                if not login_found:
                    log("ERROR", "Could not find login page at any URL!")
                    Diagnostics.capture(driver, f"P1_no_login_page_a{attempt}", save_html=True)
                    raise Exception("Login page not found at any known URL")

                title = driver.title.strip()
                log("DIAG", f"Login page loaded. Title: '{title}' URL: {driver.current_url}")

                # ── PHASE 2: Locate form fields ──
                log("PHASE", "2/8 — Locating form elements...")

                # Strategy 1: Exact placeholder selectors (discovered from DOM)
                user_field = None
                for selector in [
                    SEL_USERNAME_INPUT,                                    # exact placeholder match
                    "input.el-input__inner[type='text']",                 # first text input
                    ".login input[type='text']",                          # within .login container
                    "input[placeholder*='ser']",                          # partial placeholder
                    ".el-form input[type='text']",                        # within el-form
                ]:
                    try:
                        candidates = driver.find_elements(By.CSS_SELECTOR, selector)
                        for c in candidates:
                            if c.is_displayed() and c.is_enabled():
                                user_field = c
                                log("DIAG", f"Username field found via: {selector}")
                                break
                        if user_field:
                            break
                    except Exception:
                        continue

                if not user_field:
                    log("ERROR", "Username field NOT FOUND with any selector!")
                    Diagnostics.capture(driver, f"P2_no_username_a{attempt}")
                    raise Exception("Username field not found")

                pass_field = None
                for selector in [
                    SEL_PASSWORD_INPUT,                                    # exact match
                    "input.el-input__inner[type='password']",             # type=password
                    ".login input[type='password']",
                    ".password input.el-input__inner",                    # within .password class
                    "input[placeholder*='assword']",
                ]:
                    try:
                        candidates = driver.find_elements(By.CSS_SELECTOR, selector)
                        for c in candidates:
                            if c.is_displayed() and c.is_enabled():
                                pass_field = c
                                log("DIAG", f"Password field found via: {selector}")
                                break
                        if pass_field:
                            break
                    except Exception:
                        continue

                if not pass_field:
                    log("ERROR", "Password field NOT FOUND!")
                    Diagnostics.capture(driver, f"P2_no_password_a{attempt}")
                    raise Exception("Password field not found")

                log("OK", "Form fields located.")

                # ── PHASE 3: Fill credentials ──
                log("PHASE", "3/8 — Entering credentials...")

                # Click to focus, then clear, then type
                user_field.click()
                time.sleep(0.2)
                user_field.clear()
                time.sleep(0.1)
                # Select all + delete to ensure truly empty (Element UI quirk)
                select_all_key = Keys.COMMAND if sys.platform == 'darwin' else Keys.CONTROL
                user_field.send_keys(select_all_key + "a")
                user_field.send_keys(Keys.DELETE)
                time.sleep(0.1)
                for ch in USERNAME:
                    user_field.send_keys(ch)
                    time.sleep(0.04)
                time.sleep(0.3)

                pass_field.click()
                time.sleep(0.2)
                pass_field.clear()
                time.sleep(0.1)
                pass_field.send_keys(select_all_key + "a")
                pass_field.send_keys(Keys.DELETE)
                time.sleep(0.1)
                for ch in PASSWORD:
                    pass_field.send_keys(ch)
                    time.sleep(0.04)
                time.sleep(0.3)

                # Verify values were entered
                entered_user = user_field.get_attribute("value") or ""
                entered_pass = pass_field.get_attribute("value") or ""
                log("DIAG", f"Username entered: '{entered_user}' (expected: '{USERNAME}')")
                log("DIAG", f"Password entered: {'*' * len(entered_pass)} ({len(entered_pass)} chars, expected {len(PASSWORD)})")

                if entered_user != USERNAME:
                    log("WARN", "Username mismatch! Retrying with JavaScript injection...")
                    driver.execute_script(
                        "arguments[0].value = arguments[1];"
                        "arguments[0].dispatchEvent(new Event('input', {bubbles: true}));",
                        user_field, USERNAME
                    )
                    time.sleep(0.3)

                if len(entered_pass) != len(PASSWORD):
                    log("WARN", "Password length mismatch! Retrying with JavaScript...")
                    driver.execute_script(
                        "arguments[0].value = arguments[1];"
                        "arguments[0].dispatchEvent(new Event('input', {bubbles: true}));",
                        pass_field, PASSWORD
                    )
                    time.sleep(0.3)

                Diagnostics.capture(driver, f"P3_creds_filled_a{attempt}")

                # ── PHASE 4: Click login button ──
                log("PHASE", "4/8 — Clicking Sign In...")

                login_btn = None
                for selector in [
                    SEL_LOGIN_BTN,                                        # button.login-click
                    SEL_LOGIN_BTN_FALLBACK,                               # button.el-button--primary
                    "button span:first-child",                            # any button with span
                ]:
                    try:
                        btns = driver.find_elements(By.CSS_SELECTOR, selector)
                        for btn in btns:
                            if btn.is_displayed() and btn.is_enabled():
                                btn_text = btn.text.strip().lower()
                                # Prefer button with "Sign In" text
                                if "sign" in btn_text or "log" in btn_text or selector == SEL_LOGIN_BTN:
                                    login_btn = btn
                                    log("DIAG", f"Login button found via: {selector} text='{btn.text}'")
                                    break
                                elif not login_btn:
                                    login_btn = btn
                        if login_btn:
                            break
                    except Exception:
                        continue

                if not login_btn:
                    log("ERROR", "Login button NOT FOUND!")
                    Diagnostics.capture(driver, f"P4_no_button_a{attempt}")
                    raise Exception("Login button not found")

                # Try JavaScript click first (more reliable for Element UI)
                try:
                    driver.execute_script("arguments[0].click();", login_btn)
                except Exception:
                    login_btn.click()

                log("OK", "Login button clicked.")

                # ── PHASE 5: Wait for page transition ──
                log("PHASE", "5/8 — Waiting for login response...")

                # The title should change from "SIGN IN" to "Home" on success
                login_success = False
                waf_blocked = False
                for wait_round in range(1, 7):  # Up to 30 seconds total
                    time.sleep(5)
                    current_title = driver.title.strip()
                    current_url = driver.current_url

                    log("DIAG", f"Wait round {wait_round}: title='{current_title}' url=...{current_url[-40:]}")

                    # ── FAILURE: WAF 403 block ──
                    if "403" in current_title or "forbidden" in current_title.lower():
                        log("ERROR", "WAF 403 Forbidden detected! Bot detection triggered.")
                        waf_blocked = True
                        break

                    # ── FAILURE: Error pages ──
                    if current_title in ("404", "500", "502", "503"):
                        log("ERROR", f"Error page detected: {current_title}")
                        break

                    # ── SUCCESS indicators ──
                    if current_title.lower() in ("home", "dashboard"):
                        login_success = True
                        break
                    if "index" in current_url and "login" not in current_url:
                        login_success = True
                        break
                    # Title changed away from login to something that's NOT an error
                    if ("sign in" not in current_title.lower()
                            and "login" not in current_url.lower()
                            and current_title.lower() not in ("waaree", "403", "404", "500", "")):
                        login_success = True
                        break

                    # Check for error messages in the page
                    try:
                        error_msgs = driver.find_elements(By.CSS_SELECTOR,
                            ".el-message--error, .el-message-box, .el-alert--error")
                        if error_msgs:
                            for em in error_msgs:
                                if em.is_displayed():
                                    log("ERROR", f"Login error message: '{em.text}'")
                            # Don't break — might be a transient notification
                    except Exception:
                        pass

                diag = Diagnostics.capture(driver, f"P5_post_login_a{attempt}")

                if waf_blocked:
                    log("ERROR", "WAF blocked the login request. Will retry with backoff.")
                    raise Exception("WAF 403 Forbidden — bot detection triggered")

                if not login_success:
                    log("ERROR", f"Login did not succeed. Still on: '{driver.title}'")
                    # Check if credentials were wrong
                    body_text = diag.get("visible_text_excerpt", "").lower()
                    if "incorrect" in body_text or "wrong" in body_text or "invalid" in body_text:
                        log("ERROR", "⛔ INVALID CREDENTIALS detected! Check credentials.json")
                    raise Exception("Login transition did not complete")

                log("OK", "Login successful! Page transitioned to Home.")

                # ── PHASE 6: Verify dashboard elements ──
                log("PHASE", "6/8 — Verifying dashboard loaded...")
                time.sleep(3)

                dashboard_verified = False
                try:
                    body_text = driver.find_element(By.TAG_NAME, "body").text
                    # After login, the Home page should show sidebar with "Overview", "Sites", etc.
                    dashboard_keywords = ["overview", "sites", "inverter", "device", "error list"]
                    hits = sum(1 for kw in dashboard_keywords if kw in body_text.lower())
                    if hits >= 2:
                        dashboard_verified = True
                        log("OK", f"Dashboard verified ({hits} sidebar items found).")
                    else:
                        log("DIAG", f"Dashboard keywords found: {hits}/5. Body: {body_text[:200]}")
                except Exception as e:
                    log("WARN", f"Dashboard verification error: {e}")

                # Check username tag is visible (confirms we're logged in as correct user)
                try:
                    tags = driver.find_elements(By.CSS_SELECTOR, SEL_USER_TAG)
                    for tag in tags:
                        if USERNAME.lower() in tag.text.lower():
                            log("OK", f"Username tag confirmed: '{tag.text}'")
                            dashboard_verified = True
                            break
                except Exception:
                    pass

                Diagnostics.capture(driver, f"P6_dashboard_verify_a{attempt}", save_html=False)

                # ── PHASE 7: Navigate to plant detail page ──
                log("PHASE", "7/8 — Navigating to plant overview...")
                plant_loaded = navigate_to_plant_page(driver, timeout_per_url=12)

                # Capture diagnostic for plant navigation result
                diag = Diagnostics.capture(driver, f"P7_plant_final_a{attempt}",
                                           save_html=True, parse_text=True)

                if not plant_loaded:
                    log("WARN", "Plant page didn't fully load with data elements. "
                                "Proceeding — data extraction will handle missing elements.")
                    Diagnostics.capture(driver, f"P7_plant_partial_a{attempt}")

                # ── PHASE 8: Final validation ──
                log("PHASE", "8/8 — Final validation...")
                final_diag = Diagnostics.capture(driver, f"P8_final_a{attempt}")

                # Save session
                SessionManager.save(driver)
                engine._session_start = datetime.datetime.now()

                log("OK", f"═══ Login COMPLETE on attempt {attempt} ═══")
                log("DIAG", f"Final state: {final_diag['page_state']} | "
                            f"URL: ...{driver.current_url[-50:]}")
                return True

            except Exception as e:
                log("ERROR", f"Attempt {attempt} failed: {e}")
                Diagnostics.capture(driver, f"error_a{attempt}", save_html=True)

                if attempt < MAX_LOGIN_RETRIES:
                    # WAF 403 needs longer backoff + browser restart
                    if "403" in str(e) or "WAF" in str(e):
                        waf_wait = backoff * 3
                        log("WARN", f"WAF triggered — restarting browser, waiting {waf_wait}s...")
                        engine.restart()
                        # Refresh local references after restart
                        driver = engine.driver
                        wait = engine.wait
                        time.sleep(waf_wait)
                    else:
                        log("INFO", f"Backoff {backoff}s...")
                        time.sleep(backoff)

        log("ERROR", "═══ All login attempts EXHAUSTED ═══")
        return False

    @staticmethod
    def ensure_authenticated(engine):
        driver = engine.driver

        if engine.session_age_hours() > SESSION_MAX_AGE_HOURS:
            log("INFO", "Session aged out. Re-authenticating...")
            SessionManager.invalidate()
            return Authenticator.login(engine, force=True)

        # Try session reuse
        if SessionManager.load(driver):
            log("INFO", "Attempting session reuse → dynamic plant navigation...")
            navigate_to_plant_page(driver, timeout_per_url=10)
            time.sleep(2)

            diag = Diagnostics.capture(driver, "session_reuse_check")

            # Check if we landed on login page (session expired)
            if diag["page_state"] == "login_page" or "login" in driver.current_url.lower():
                log("WARN", "Session expired → fresh login needed.")
                SessionManager.invalidate()
                return Authenticator.login(engine)

            # Check if we have dashboard/plant content
            if diag["page_state"] in ("plant_detail_loaded", "home_dashboard", "plant_detail_loading"):
                log("OK", f"Session reuse successful. State: {diag['page_state']}")

                # If on home, navigate to plant
                if diag["page_state"] == "home_dashboard":
                    navigate_to_plant_page(driver, timeout_per_url=10)
                    time.sleep(2)

                engine._session_start = datetime.datetime.now()
                return True

            log("WARN", f"Session reuse unclear (state={diag['page_state']}). Trying fresh login...")
            SessionManager.invalidate()

        return Authenticator.login(engine)


# ═══════════════════════════════════════════════════════════════
# PORTAL VALIDATOR
# ═══════════════════════════════════════════════════════════════
class PortalValidator:
    @staticmethod
    def validate(body_text, screenshot_path):
        body_text = body_text or ""
        ocr_text = Diagnostics.extract_ocr_text(screenshot_path)

        body_hits = sum(1 for kw in PORTAL_KEYWORDS if kw.lower() in body_text.lower())
        ocr_hits = sum(1 for kw in PORTAL_KEYWORDS if kw.lower() in ocr_text.lower())

        score = min(100, int(body_hits * 14 + ocr_hits * 8))
        loaded = body_hits >= 2 or ocr_hits >= 2 or score >= 40

        excerpt = re.sub(r"\s+", " ", ocr_text)[:200] if ocr_text else ""

        return {
            "portal_loaded": loaded,
            "score": score,
            "body_hits": body_hits,
            "ocr_hits": ocr_hits,
            "ocr_excerpt": excerpt
        }


# ═══════════════════════════════════════════════════════════════
# DATA EXTRACTION
# ═══════════════════════════════════════════════════════════════
class DataExtractor:
    @staticmethod
    def extract(driver, wait):
        now = datetime.datetime.now()
        packet = {
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
            "plant_id": PLANT_ID,
            "current_power": "0",
            "daily_yield": "0",
            "total_yield": "0",
            "income": "0",
            "voltage_sample": "0",
            "current_sample": "0",
            "frequency_hz": "0",
            "temperature_c": "0",
            "status": "Online",
            "portal_loaded": False,
            "portal_validation_score": 0,
            "portal_ocr_excerpt": "",
            "extraction_method": "none"
        }

        try:
            # Ensure we're on plant page
            current = driver.current_url
            if PLANT_ID not in current:
                log("NAV", "Navigating to plant overview...")
                ok = navigate_to_plant_page(driver, timeout_per_url=10)
                if not ok:
                    log("WARN", "Robust plant navigation failed; continuing with current page diagnostics.")
            else:
                # Avoid hard refresh here (can trigger WAF/403). Let existing SPA state stabilize.
                time.sleep(3)

            # Wait for plant-specific elements to render
            try:
                WebDriverWait(driver, 15).until(
                    lambda d: d.find_elements(By.CSS_SELECTOR, SEL_PLANT_MONEY)
                    or "power" in d.find_element(By.TAG_NAME, "body").text.lower()
                )
            except TimeoutException:
                log("WARN", "Plant data elements didn't appear within 15s.")

            # Screenshot for validation
            snap_path = f"{SNAPSHOT_DIR}/latest_dashboard_status.png"
            driver.save_screenshot(snap_path)

            # Get body text
            body_text = ""
            try:
                body_text = driver.find_element(By.TAG_NAME, "body").text
            except Exception:
                pass

            # Validate portal
            validation = PortalValidator.validate(body_text, snap_path)
            packet["portal_loaded"] = validation["portal_loaded"]
            packet["portal_validation_score"] = validation["score"]
            packet["portal_ocr_excerpt"] = validation["ocr_excerpt"]

            if not validation["portal_loaded"]:
                # Do not fail fast: some pages render usable numeric widgets even with weak text keywords.
                log("WARN", f"Portal validation weak (score={validation['score']}); attempting extraction anyway.")
                Diagnostics.capture(driver, "extraction_portal_weak", save_html=True)

            # ── Strategy 1: CSS Selectors ──
            extracted_css = DataExtractor._extract_via_css(driver)
            if extracted_css:
                packet.update(extracted_css)
                packet["extraction_method"] = "css_selector"
                log("DATA", "CSS extraction OK.")

            # ── Strategy 2: Regex fallback ──
            if packet["current_power"] == "0" and packet["daily_yield"] == "0":
                extracted_regex = DataExtractor._extract_via_regex(body_text)
                if extracted_regex:
                    packet.update(extracted_regex)
                    packet["extraction_method"] = "regex"
                    log("DATA", "Regex fallback used.")

            # ── Strategy 3: JavaScript extraction ──
            if packet["current_power"] == "0":
                js_data = DataExtractor._extract_via_js(driver)
                if js_data:
                    packet.update(js_data)
                    packet["extraction_method"] = "javascript"
                    log("DATA", "JavaScript extraction used.")

            # ── Strategy 4: Device tab for voltage/current ──
            device_data = DataExtractor._explore_device_tab(driver, wait)
            if device_data:
                for key in ["voltage_sample", "current_sample", "frequency_hz", "temperature_c"]:
                    if device_data.get(key, "0") != "0":
                        packet[key] = device_data[key]

            # Post-extraction confidence upgrade: if we captured non-zero core metrics, treat portal as loaded.
            if (to_float(packet.get("current_power")) > 0
                    or to_float(packet.get("daily_yield")) > 0
                    or to_float(packet.get("total_yield")) > 0):
                packet["portal_loaded"] = True
                packet["status"] = "Online"
            elif not packet.get("portal_loaded"):
                packet["status"] = "Portal Not Loaded"

            log("DATA", f"Power={packet['current_power']}kW | "
                        f"Daily={packet['daily_yield']}kWh | "
                        f"Total={packet['total_yield']}kWh | "
                        f"V={packet['voltage_sample']} A={packet['current_sample']}")

        except Exception as e:
            log("ERROR", f"Extraction error: {e}")
            packet["status"] = "Extraction Error"
            traceback.print_exc()

        return packet

    @staticmethod
    def _extract_via_css(driver):
        result = {}
        try:
            money_spans = driver.find_elements(By.CSS_SELECTOR, SEL_PLANT_MONEY)
            values = []
            for span in money_spans:
                try:
                    txt = span.text.strip()
                    if txt and re.match(r"^[\d.,]+$", txt):
                        values.append(txt)
                except StaleElementReferenceException:
                    continue

            if len(values) >= 4:
                result["current_power"] = values[0]
                result["daily_yield"] = values[1]
                result["total_yield"] = values[2]
                result["income"] = values[3]
            elif len(values) >= 3:
                result["current_power"] = values[0]
                result["daily_yield"] = values[1]
                result["total_yield"] = values[2]
            elif len(values) >= 1:
                result["current_power"] = values[0]

            log("DIAG", f"CSS money values found: {values}")
        except Exception as e:
            log("WARN", f"CSS extraction error: {e}")

        return result if result else None

    @staticmethod
    def _extract_via_regex(body_text):
        result = {}
        patterns = {
            "current_power": [
                r"Power\s*Generating\s*\(kW\)\s*([\d.,]+)",
                r"([\d.,]+)\s*kW\s*(?:Power|Generating)",
                r"Power\s*[:：]\s*([\d.,]+)",
            ],
            "daily_yield": [
                r"Today\s*Yield\s*\(kW[·.]h\)\s*([\d.,]+)",
                r"([\d.,]+)\s*kW[·.]h\s*Today",
                r"Today\s*(?:Yield|Generation)\s*[:：]\s*([\d.,]+)",
            ],
            "total_yield": [
                r"Total\s*Yield\s*\(kW[·.]h\)\s*([\d.,]+)",
                r"([\d.,]+)\s*kW[·.]h\s*Total",
                r"Total\s*(?:Yield|Generation)\s*[:：]\s*([\d.,]+)",
            ],
            "income": [
                r"(?:Accumulated\s*)?Income\s*\(INR\(₹\)\)\s*([\d.,]+)",
                r"₹\s*([\d.,]+)",
                r"Income\s*[:：]\s*([\d.,]+)",
            ],
        }

        for key, pats in patterns.items():
            for pat in pats:
                m = re.search(pat, body_text, re.IGNORECASE)
                if m:
                    result[key] = m.group(1).replace(",", "")
                    break

        return result if result else None

    @staticmethod
    def _extract_via_js(driver):
        """Use JavaScript to extract text from Vue-rendered DOM elements."""
        result = {}
        try:
            js_code = """
            var moneyEls = document.querySelectorAll('.plant-money span');
            var vals = [];
            moneyEls.forEach(function(el) {
                var t = el.textContent.trim();
                if (/^[\\d.,]+$/.test(t)) vals.push(t);
            });
            return vals;
            """
            values = driver.execute_script(js_code)
            if values and len(values) >= 3:
                result["current_power"] = values[0]
                result["daily_yield"] = values[1]
                result["total_yield"] = values[2]
                if len(values) >= 4:
                    result["income"] = values[3]
                log("DIAG", f"JS extracted: {values}")
        except Exception as e:
            log("WARN", f"JS extraction error: {e}")
        return result if result else None

    @staticmethod
    def _explore_device_tab(driver, wait):
        data = {}
        try:
            tabs = driver.find_elements(By.CSS_SELECTOR, SEL_TABS_ITEM)
            device_tab = None
            for tab in tabs:
                try:
                    txt = tab.text.lower()
                    if any(kw in txt for kw in ["device", "inverter", "equipment"]):
                        device_tab = tab
                        break
                except StaleElementReferenceException:
                    continue

            if device_tab:
                device_tab.click()
                time.sleep(5)
                deep_text = driver.find_element(By.TAG_NAME, "body").text

                for pat in [r"(?:Grid\s+)?Voltage\s*[:：]?\s*([\d.]+)\s*V?",
                            r"Ua[bc]?\s*[:：]?\s*([\d.]+)",
                            r"(2[0-9]{2}(?:\.\d+)?)\s*V"]:
                    m = re.search(pat, deep_text, re.IGNORECASE)
                    if m:
                        data["voltage_sample"] = m.group(1)
                        break

                for pat in [r"(?:Output\s+)?Current\s*[:：]?\s*([\d.]+)\s*A?",
                            r"Ia[bc]?\s*[:：]?\s*([\d.]+)",
                            r"([\d.]+)\s*A(?:\s|$)"]:
                    m = re.search(pat, deep_text, re.IGNORECASE)
                    if m:
                        data["current_sample"] = m.group(1)
                        break

                for pat in [r"Frequency\s*[:：]?\s*([\d.]+)\s*Hz?",
                            r"(4[89]|5[01])\.\d+\s*Hz"]:
                    m = re.search(pat, deep_text, re.IGNORECASE)
                    if m:
                        data["frequency_hz"] = m.group(1)
                        break

                for pat in [r"Temp(?:erature)?\s*[:：]?\s*([\d.]+)\s*[°C]?",
                            r"([\d.]+)\s*°C"]:
                    m = re.search(pat, deep_text, re.IGNORECASE)
                    if m:
                        data["temperature_c"] = m.group(1)
                        break

        except Exception as e:
            log("WARN", f"Device tab error: {e}")

        return data if data else None


# ═══════════════════════════════════════════════════════════════
# DATA SANITIZER
# ═══════════════════════════════════════════════════════════════
class DataSanitizer:
    @staticmethod
    def sanitize(packet):
        notes = []

        power = to_float(packet.get("current_power"))
        daily = to_float(packet.get("daily_yield"))
        total = to_float(packet.get("total_yield"))
        income = to_float(packet.get("income"))
        voltage = to_float(packet.get("voltage_sample"))
        current = to_float(packet.get("current_sample"))
        freq = to_float(packet.get("frequency_hz"))
        temp = to_float(packet.get("temperature_c"))

        # Power normalization
        if power > PLANT_CAPACITY_KW * 2 and power > 100:
            power /= 1000.0
            notes.append("power_w_to_kw")
        max_safe_kw = PLANT_CAPACITY_KW * 1.35
        if power > max_safe_kw:
            notes.append(f"power_clamped_{power:.2f}")
            power = max_safe_kw
        if power < 0:
            power = 0.0

        # Daily yield normalization
        if daily > DAILY_REALISTIC_MAX_KWH * 3 and daily > 100:
            daily /= 1000.0
            notes.append("daily_wh_to_kwh")
        if daily > DAILY_REALISTIC_MAX_KWH * 1.5:
            notes.append(f"daily_clamped_{daily:.2f}")
            daily = DAILY_REALISTIC_MAX_KWH * 1.5
        if daily < 0:
            daily = 0.0

        # Voltage sanity
        if voltage > 0 and (voltage < 100 or voltage > 500):
            notes.append(f"voltage_outlier_{voltage:.1f}")
            voltage = 0.0

        # Current sanity
        max_current = (PLANT_CAPACITY_KW * 1000) / 230 * 1.5
        if current > max_current:
            notes.append(f"current_clamped_{current:.2f}")
            current = max_current

        # Night power check
        try:
            ts = datetime.datetime.strptime(packet.get("timestamp", ""), "%Y-%m-%d %H:%M:%S")
            if (ts.hour < 6 or ts.hour > 19) and power > 0.05:
                notes.append(f"nighttime_power_{power:.3f}")
                power = 0.0
        except Exception:
            pass

        return {
            "current_power_kw": round(max(0.0, power), 3),
            "daily_yield_kwh": round(max(0.0, daily), 3),
            "total_yield_kwh": round(max(0.0, total), 3),
            "income_inr": round(max(0.0, income), 2),
            "voltage_v": round(max(0.0, voltage), 1),
            "current_a": round(max(0.0, current), 2),
            "frequency_hz": round(freq, 2) if freq > 0 else 0.0,
            "temperature_c": round(temp, 1) if temp > 0 else 0.0,
            "anomaly_notes": notes
        }


# ═══════════════════════════════════════════════════════════════
# DATA PERSISTENCE
# ═══════════════════════════════════════════════════════════════
class DataStore:
    CSV_FIELDS = [
        "timestamp", "plant_id", "current_power_kw", "daily_yield_kwh",
        "total_yield_kwh", "income_inr", "voltage_v", "current_a",
        "frequency_hz", "temperature_c", "status", "portal_loaded",
        "portal_validation_score", "extraction_method", "anomaly_notes"
    ]

    @staticmethod
    def normalize_packet(raw):
        cleaned = DataSanitizer.sanitize(raw)
        return {
            "timestamp": raw.get("timestamp", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            "plant_id": raw.get("plant_id", PLANT_ID),
            "current_power_kw": cleaned["current_power_kw"],
            "daily_yield_kwh": cleaned["daily_yield_kwh"],
            "total_yield_kwh": cleaned["total_yield_kwh"],
            "income_inr": cleaned["income_inr"],
            "voltage_v": cleaned["voltage_v"],
            "current_a": cleaned["current_a"],
            "frequency_hz": cleaned["frequency_hz"],
            "temperature_c": cleaned["temperature_c"],
            "status": raw.get("status", "Online"),
            "portal_loaded": bool(raw.get("portal_loaded", False)),
            "portal_validation_score": int(to_float(raw.get("portal_validation_score", 0))),
            "portal_ocr_excerpt": raw.get("portal_ocr_excerpt", ""),
            "extraction_method": raw.get("extraction_method", "none"),
            "anomaly_notes": cleaned["anomaly_notes"]
        }

    @staticmethod
    def append_csv(normalized):
        exists = os.path.exists(CSV_FILE)
        with open(CSV_FILE, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=DataStore.CSV_FIELDS, extrasaction="ignore")
            if not exists:
                w.writeheader()
            row = {**normalized}
            row["anomaly_notes"] = "|".join(row.get("anomaly_notes", []))
            w.writerow(row)

    @staticmethod
    def update_dashboard_json(raw):
        normalized = DataStore.normalize_packet(raw)

        history = []
        if os.path.exists(JSON_DASHBOARD_FILE):
            try:
                with open(JSON_DASHBOARD_FILE, "r") as f:
                    existing = json.load(f)
                if isinstance(existing, dict):
                    history = existing.get("history", [])
                elif isinstance(existing, list):
                    history = existing
            except Exception:
                history = []

        # Normalize history, filtering out invalid entries
        norm_history = []
        for item in history:
            try:
                n = DataStore.normalize_packet(item)
                # Drop template/mock entries and all-zero entries
                if n.get("plant_id") == "YOUR_PLANT_ID":
                    continue
                if not is_valid_data_point(n):
                    continue
                norm_history.append(n)
            except Exception:
                continue

        norm_history.append(normalized)

        # Sort + deduplicate
        def parse_ts(ts):
            try:
                return datetime.datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
            except Exception:
                return datetime.datetime.min

        norm_history.sort(key=lambda x: parse_ts(x.get("timestamp", "")))

        # Dedupe by timestamp
        seen = set()
        deduped = []
        for p in norm_history:
            ts = p.get("timestamp", "")
            if ts not in seen:
                seen.add(ts)
                deduped.append(p)
        norm_history = deduped[-MAX_HISTORY_POINTS:]

        # Compute summary
        last = norm_history[-1]
        powers = [p["current_power_kw"] for p in norm_history]
        voltages = [p["voltage_v"] for p in norm_history if p["voltage_v"] > 0]
        online = [p for p in norm_history if p.get("status", "").lower() not in
                  ("error", "offline", "extraction error", "portal not loaded")]
        portal_ok = [p for p in norm_history if p.get("portal_loaded")]

        power_std = statistics.stdev(powers) if len(powers) > 1 else 0.0
        voltage_std = statistics.stdev(voltages) if len(voltages) > 1 else 0.0

        summary = {
            "points": len(norm_history),
            "peak_power_kw": round(max(powers), 3) if powers else 0.0,
            "avg_power_kw": round(statistics.mean(powers), 3) if powers else 0.0,
            "std_power_kw": round(power_std, 3),
            "avg_voltage_v": round(statistics.mean(voltages), 1) if voltages else 0.0,
            "std_voltage_v": round(voltage_std, 1),
            "uptime_pct": round((len(online) / len(norm_history)) * 100, 1) if norm_history else 0.0,
            "portal_validation_pct": round((len(portal_ok) / len(norm_history)) * 100, 1) if norm_history else 0.0,
            "portal_loaded_latest": bool(last.get("portal_loaded")),
            "latest_timestamp": last.get("timestamp"),
            "latest_power_kw": last.get("current_power_kw", 0.0),
            "latest_daily_yield_kwh": last.get("daily_yield_kwh", 0.0),
            "latest_total_yield_kwh": last.get("total_yield_kwh", 0.0),
            "data_quality_score": round(
                (min(100, (len(portal_ok) / max(1, len(norm_history))) * 100) * 0.5) +
                (min(100, (len(online) / max(1, len(norm_history))) * 100) * 0.3) +
                (min(100, last.get("portal_validation_score", 0)) * 0.2), 1
            )
        }

        payload = {
            "meta": {
                "schema_version": "4.0",
                "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "plant_id": PLANT_ID,
                "sampling_seconds": SCRAPE_INTERVAL,
                "plant_capacity_kw": PLANT_CAPACITY_KW,
                "daily_realistic_max_kwh": DAILY_REALISTIC_MAX_KWH,
                "location": LOCATION,
                "engine_version": "4.0"
            },
            "summary": summary,
            "history": norm_history
        }

        with open(JSON_DASHBOARD_FILE, "w") as f:
            json.dump(payload, f, indent=2)

        DataStore.append_csv(normalized)
        log("DATA", f"Dashboard updated ({len(norm_history)} pts, quality={summary['data_quality_score']}%)")

        if HAS_ANALYTICS:
            try:
                run_analytics(JSON_DASHBOARD_FILE)
            except Exception as e:
                log("WARN", f"Analytics error: {e}")

        return normalized


# ═══════════════════════════════════════════════════════════════
# ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════
class TelemetryOrchestrator:
    def __init__(self):
        self.engine = BrowserEngine()
        self.cycle_count = 0
        self.error_streak = 0
        self.max_error_streak = 5

    def run_single_cycle(self):
        self.cycle_count += 1
        log("SYS", f"━━━ Cycle #{self.cycle_count} ━━━")

        try:
            if not self.engine.is_alive():
                log("WARN", "Browser dead. Restarting...")
                self.engine.restart()
                if not Authenticator.ensure_authenticated(self.engine):
                    self.error_streak += 1
                    return None

            # Check if redirected to login
            try:
                if "login" in self.engine.driver.current_url.lower():
                    log("INFO", "On login page. Re-authenticating...")
                    if not Authenticator.login(self.engine):
                        self.error_streak += 1
                        return None
            except Exception:
                pass

            raw = DataExtractor.extract(self.engine.driver, self.engine.wait)

            # ── Data validity gate: never persist zero/error data ──
            if not is_valid_data_point(raw):
                log("WARN", f"Cycle #{self.cycle_count}: data invalid (all zeros / error page) — SKIPPED, not saved.")
                self.error_streak += 1
                return None

            normalized = DataStore.update_dashboard_json(raw)

            self.error_streak = 0
            log("OK", f"Cycle #{self.cycle_count} done. P={normalized['current_power_kw']}kW")
            return normalized

        except WebDriverException:
            self.error_streak += 1
            if self.error_streak >= self.max_error_streak:
                self.engine.restart()
                Authenticator.ensure_authenticated(self.engine)
                self.error_streak = 0
            return None
        except Exception as e:
            log("ERROR", f"Cycle error: {e}")
            self.error_streak += 1
            return None

    def run_continuous(self):
        log("SYS", "═══ Waaree Telemetry Engine v4.0 ═══")
        log("SYS", f"Plant: {PLANT_ID} | Cap: {PLANT_CAPACITY_KW}kW | {LOCATION}")
        log("SYS", f"Interval: {SCRAPE_INTERVAL}s | Headless: {HEADLESS}")

        self.engine.start()

        if not Authenticator.ensure_authenticated(self.engine):
            log("ERROR", "Initial auth failed.")
            self.engine.stop()
            sys.exit(1)

        log("OK", "Monitoring active. Ctrl+C to stop.")

        try:
            while True:
                self.run_single_cycle()
                cleanup_old_diagnostics()
                log("SYS", f"Sleep {SCRAPE_INTERVAL}s...")
                time.sleep(SCRAPE_INTERVAL)
        except KeyboardInterrupt:
            log("SYS", "Shutdown.")
        finally:
            self.engine.stop()

    def run_validation(self, fresh_cycles=3, reuse_cycles=3):
        results = {"fresh_login": [], "session_reuse": [], "summary": {}}

        log("SYS", "═══ VALIDATION MODE v4.0 ═══")

        # ── Phase 1: Fresh Login Cycles ──
        log("SYS", f"── Phase 1: {fresh_cycles} Fresh Login Cycles ──")
        for i in range(1, fresh_cycles + 1):
            log("SYS", f"━━ Fresh Cycle {i}/{fresh_cycles} ━━")
            cr = {"cycle": i, "phase": "fresh", "success": False,
                  "data": None, "error": None, "timing": {}, "diagnostics": []}

            SessionManager.invalidate()
            if self.engine.is_alive():
                self.engine.stop()
            time.sleep(2)

            t0 = time.time()
            self.engine.start()
            cr["timing"]["browser_start"] = round(time.time() - t0, 2)

            t1 = time.time()
            login_ok = Authenticator.login(self.engine)
            cr["timing"]["login"] = round(time.time() - t1, 2)

            if login_ok:
                t2 = time.time()
                raw = DataExtractor.extract(self.engine.driver, self.engine.wait)
                cr["timing"]["extraction"] = round(time.time() - t2, 2)

                if is_valid_data_point(raw):
                    normalized = DataStore.update_dashboard_json(raw)
                    cr["data"] = normalized
                    cr["success"] = normalized.get("portal_loaded", False)
                    cr["portal_score"] = normalized.get("portal_validation_score", 0)
                    cr["extraction_method"] = normalized.get("extraction_method", "none")
                else:
                    log("WARN", "Extracted data is all zeros / error page — not saved")
                    cr["data"] = None
                    cr["success"] = False
                    cr["error"] = "Data validation failed: all zeros or error page"
            else:
                cr["error"] = "Login failed"

            cr["timing"]["total"] = round(time.time() - t0, 2)
            results["fresh_login"].append(cr)

            status = "PASS ✅" if cr["success"] else "FAIL ❌"
            log("SYS", f"Fresh {i}: {status} | {cr['timing']['total']}s | "
                       f"method={cr.get('extraction_method', 'n/a')}")

            if i < fresh_cycles:
                time.sleep(5)

        # ── Phase 2: Session Reuse Cycles ──
        log("SYS", f"── Phase 2: {reuse_cycles} Session Reuse Cycles ──")
        for i in range(1, reuse_cycles + 1):
            log("SYS", f"━━ Reuse Cycle {i}/{reuse_cycles} ━━")
            cr = {"cycle": i, "phase": "reuse", "success": False,
                  "data": None, "error": None, "timing": {}}

            t0 = time.time()
            if not self.engine.is_alive():
                self.engine.start()

            t1 = time.time()
            auth_ok = Authenticator.ensure_authenticated(self.engine)
            cr["timing"]["auth"] = round(time.time() - t1, 2)

            if auth_ok:
                t2 = time.time()
                raw = DataExtractor.extract(self.engine.driver, self.engine.wait)
                cr["timing"]["extraction"] = round(time.time() - t2, 2)

                if is_valid_data_point(raw):
                    normalized = DataStore.update_dashboard_json(raw)
                    cr["data"] = normalized
                    cr["success"] = normalized.get("portal_loaded", False)
                    cr["portal_score"] = normalized.get("portal_validation_score", 0)
                else:
                    log("WARN", "Extracted data is all zeros / error page — not saved")
                    cr["data"] = None
                    cr["success"] = False
                    cr["error"] = "Data validation failed: all zeros or error page"
            else:
                cr["error"] = "Auth failed"

            cr["timing"]["total"] = round(time.time() - t0, 2)
            results["session_reuse"].append(cr)

            status = "PASS ✅" if cr["success"] else "FAIL ❌"
            log("SYS", f"Reuse {i}: {status} | {cr['timing']['total']}s")

            if i < reuse_cycles:
                time.sleep(10)

        # ── Summary ──
        fp = sum(1 for r in results["fresh_login"] if r["success"])
        rp = sum(1 for r in results["session_reuse"] if r["success"])
        total = fresh_cycles + reuse_cycles
        results["summary"] = {
            "fresh_pass": fp, "fresh_total": fresh_cycles,
            "reuse_pass": rp, "reuse_total": reuse_cycles,
            "overall_rate": round(((fp + rp) / total) * 100, 1) if total > 0 else 0
        }

        log("SYS", "═══════════════════════════════════")
        log("SYS", f"  Fresh Login:  {fp}/{fresh_cycles}")
        log("SYS", f"  Session Reuse: {rp}/{reuse_cycles}")
        log("SYS", f"  Overall:      {results['summary']['overall_rate']}%")
        log("SYS", "═══════════════════════════════════")

        rpt = f"{DIAGNOSTICS_DIR}/validation_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(rpt, "w") as f:
            json.dump(results, f, indent=2, default=str)
        log("OK", f"Report: {rpt}")

        return results


# ═══════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Waaree Telemetry Engine v4.0")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--fresh-cycles", type=int, default=3)
    parser.add_argument("--reuse-cycles", type=int, default=3)
    parser.add_argument("--no-headless", action="store_true")
    args = parser.parse_args()

    if args.no_headless:
        HEADLESS = False

    orch = TelemetryOrchestrator()

    if args.validate:
        res = orch.run_validation(args.fresh_cycles, args.reuse_cycles)
        orch.engine.stop()
        sys.exit(0 if res["summary"]["overall_rate"] >= 50 else 1)
    else:
        orch.run_continuous()
