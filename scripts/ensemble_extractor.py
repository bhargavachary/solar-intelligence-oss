#!/usr/bin/env python3
"""
Ensemble Data Extractor — 5-Strategy Voting Engine
====================================================
Robust solar data extraction using 5 independent strategies:

  1. CSS Selectors (header-aware)  — DOM traversal with dynamic column finding
  2. Regex on body text           — Pattern matching on visible text
  3. JavaScript DOM query          — Execute JS in page context
  4. Screenshot OCR               — Tesseract OCR on page screenshot
  5. Network/CDP interception      — Capture XHR/API responses

Each strategy extracts the same fields independently. The ensemble
engine then applies a voting/consensus algorithm:
  - For each field, collect non-zero values from all strategies
  - If ≥3 strategies agree (within 10%), use their average
  - If 2 agree, use their average (medium confidence)
  - If only 1 value, use it (low confidence)
  - Report per-field confidence and extraction source

This module is designed to be imported by waaree_deep_crawler.py and
replaces the old sequential CSS→regex→JS fallback chain.

Usage:
    from scripts.ensemble_extractor import EnsembleExtractor
    result = EnsembleExtractor.extract(driver, wait)
"""

import re
import os
import time
import datetime
import statistics
import traceback
from pathlib import Path

# Optional imports — graceful degradation
try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False

try:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.common.exceptions import (
        TimeoutException, StaleElementReferenceException,
        NoSuchElementException, WebDriverException
    )
    HAS_SELENIUM = True
except ImportError:
    HAS_SELENIUM = False


# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════
SNAPSHOT_DIR = Path("system_snapshots")
SNAPSHOT_DIR.mkdir(exist_ok=True)

# Agreement threshold: values within this % are considered "agreeing"
AGREEMENT_THRESHOLD_PCT = 15.0

# Minimum number of strategies that must agree for high confidence
HIGH_CONFIDENCE_MIN = 3
MEDIUM_CONFIDENCE_MIN = 2

# Core fields we extract
CORE_FIELDS = [
    "current_power",   # kW — instantaneous power generation
    "daily_yield",     # kWh — energy generated today
    "monthly_yield",   # kWh — energy generated this month
    "total_yield",     # kWh — lifetime energy generated
    "income",          # INR — accumulated income
]

# Supplementary fields (from device tab or secondary sources)
SUPPLEMENTARY_FIELDS = [
    "voltage",         # V
    "current",         # A
    "frequency",       # Hz
    "temperature",     # °C
]


def _log(level, msg):
    """Lightweight logging compatible with crawler's log()."""
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    icons = {
        "INFO": "ℹ️", "WARN": "⚠️", "ERROR": "❌", "OK": "✅",
        "DATA": "📊", "DIAG": "🔬", "VOTE": "🗳️",
    }
    print(f"[{ts}] {icons.get(level, '•')} [{level}] {msg}")


def _to_float(val, default=0.0):
    """Robust numeric parser."""
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    text = str(val).replace(",", "").replace(" ", "")
    m = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(m.group(0)) if m else default


# ═══════════════════════════════════════════════════════════════
# STRATEGY 1: CSS SELECTORS (Header-Aware)
# ═══════════════════════════════════════════════════════════════
class CSSStrategy:
    """Extract data using CSS selectors with dynamic column discovery.

    Instead of hard-coding column indices (e.g., .el-table_1_column_10),
    we find columns by their header text. This survives portal UI updates
    that reorder columns.
    """

    @staticmethod
    def extract(driver):
        result = {}
        try:
            # ── Money spans: Today Yield, Monthly Yield, Total Yield, Income ──
            money_spans = driver.find_elements(By.CSS_SELECTOR, ".plant-money span")
            values = []
            for span in money_spans:
                try:
                    txt = span.text.strip()
                    if txt and re.match(r"^[\d.,]+$", txt):
                        values.append(txt)
                except StaleElementReferenceException:
                    continue

            # Portal .plant-money span order (verified from DOM):
            #   [0] Today Yield (kW·h)
            #   [1] Monthly Yield (kW·h)
            #   [2] Total Yield (kW·h)
            #   [3] Accumulated Income (INR)
            if len(values) >= 4:
                result["daily_yield"] = values[0]
                result["monthly_yield"] = values[1]
                result["total_yield"] = values[2]
                result["income"] = values[3]
            elif len(values) >= 3:
                result["daily_yield"] = values[0]
                result["monthly_yield"] = values[1]
                result["total_yield"] = values[2]
            elif len(values) >= 1:
                result["daily_yield"] = values[0]

            _log("DIAG", f"[CSS] Money spans: {values}")

            # ── Current Power: Find by header text, not column index ──
            power_found = False

            # Method A: Header-based column finding (robust)
            try:
                headers = driver.find_elements(
                    By.CSS_SELECTOR, ".el-table__header-wrapper th .cell"
                )
                power_col_idx = None
                for idx, hdr in enumerate(headers):
                    txt = hdr.text.strip().lower()
                    if any(kw in txt for kw in ["power", "generating", "kw"]):
                        power_col_idx = idx
                        _log("DIAG", f"[CSS] Power column found at index {idx}: '{hdr.text}'")
                        break

                if power_col_idx is not None:
                    # Get all body rows and extract the cell at that column
                    rows = driver.find_elements(
                        By.CSS_SELECTOR, ".el-table__body-wrapper .el-table__row"
                    )
                    for row in rows:
                        cells = row.find_elements(By.CSS_SELECTOR, "td .cell")
                        if power_col_idx < len(cells):
                            txt = cells[power_col_idx].text.strip()
                            if txt and re.match(r"^[\d.,]+$", txt):
                                result["current_power"] = txt
                                power_found = True
                                _log("DIAG", f"[CSS] Power via header: {txt} kW")
                                break
            except Exception as e:
                _log("DIAG", f"[CSS] Header-based power search error: {e}")

            # Method B: Legacy column selector (fallback)
            if not power_found:
                for selector in [
                    ".el-table_1_column_10 .cell",
                    ".el-table_1_column_9 .cell",
                    ".el-table_1_column_11 .cell",
                ]:
                    try:
                        cells = driver.find_elements(By.CSS_SELECTOR, selector)
                        for cell in cells:
                            txt = cell.text.strip()
                            if txt and re.match(r"^[\d.,]+$", txt):
                                val = float(txt.replace(",", ""))
                                # Power should be < plant capacity (2.32 kW * 1.5)
                                if 0 < val < 10:
                                    result["current_power"] = txt
                                    power_found = True
                                    _log("DIAG", f"[CSS] Power via legacy selector: {txt}")
                                    break
                        if power_found:
                            break
                    except Exception:
                        continue

            # Method C: Scan all table cells for power-like values
            if not power_found:
                try:
                    all_cells = driver.find_elements(
                        By.CSS_SELECTOR, ".el-table__body td .cell"
                    )
                    for cell in all_cells:
                        txt = cell.text.strip()
                        if txt and re.match(r"^[\d.,]+$", txt):
                            val = float(txt.replace(",", ""))
                            # Power generating is typically < 5 kW for a 2.32 kW system
                            # and distinct from yield values which are larger
                            if 0.01 < val < 5.0:
                                result["current_power"] = txt
                                _log("DIAG", f"[CSS] Power via cell scan: {txt}")
                                break
                except Exception:
                    pass

        except Exception as e:
            _log("WARN", f"[CSS] Extraction error: {e}")

        return result if result else None


# ═══════════════════════════════════════════════════════════════
# STRATEGY 2: REGEX ON BODY TEXT
# ═══════════════════════════════════════════════════════════════
class RegexStrategy:
    """Extract data by regex-matching the visible body text."""

    PATTERNS = {
        "current_power": [
            r"Power\s*Generating\s*\(?kW\)?\s*([\d.,]+)",
            r"([\d.,]+)\s*kW\s*(?:Power|Generating)",
            r"Power\s*[:：]\s*([\d.,]+)",
            r"Generating\s*[:：]?\s*([\d.,]+)\s*kW",
        ],
        "daily_yield": [
            r"Today\s*(?:Yield|Generation)\s*\(?kW[·.]?h\)?\s*([\d.,]+)",
            r"([\d.,]+)\s*kW[·.]?h\s*Today",
            r"Today\s*(?:Yield|Generation)\s*[:：]\s*([\d.,]+)",
        ],
        "monthly_yield": [
            r"Monthly?\s*(?:Yield|Generation)\s*\(?kW[·.]?h\)?\s*([\d.,]+)",
            r"([\d.,]+)\s*kW[·.]?h\s*Month",
        ],
        "total_yield": [
            r"Total\s*(?:Yield|Generation)\s*\(?kW[·.]?h\)?\s*([\d.,]+)",
            r"([\d.,]+)\s*kW[·.]?h\s*Total",
            r"Total\s*(?:Yield|Generation)\s*[:：]\s*([\d.,]+)",
        ],
        "income": [
            r"(?:Accumulated\s*)?Income\s*\(INR\(₹\)\)\s*([\d.,]+)",
            r"₹\s*([\d.,]+)",
            r"Income\s*[:：]\s*([\d.,]+)",
            r"(?:Accumulated\s*)?Income\s*\(?(?:INR|₹)\)?\s*([\d.,]+)",
        ],
    }

    @staticmethod
    def extract(body_text):
        result = {}
        if not body_text:
            return None

        for field, patterns in RegexStrategy.PATTERNS.items():
            for pat in patterns:
                m = re.search(pat, body_text, re.IGNORECASE)
                if m:
                    result[field] = m.group(1).replace(",", "")
                    break

        if result:
            _log("DIAG", f"[Regex] Found: {list(result.keys())}")
        return result if result else None


# ═══════════════════════════════════════════════════════════════
# STRATEGY 3: JAVASCRIPT DOM QUERY
# ═══════════════════════════════════════════════════════════════
class JavaScriptStrategy:
    """Extract data via JavaScript execution in the browser context.

    FIXED: Field mapping now matches CSS strategy:
    .plant-money spans → [daily_yield, monthly_yield, total_yield, income]
    Current power comes from the sites table, NOT from .plant-money.
    """

    @staticmethod
    def extract(driver):
        result = {}
        try:
            # ── Extract money values via JS ──
            js_money = """
            var moneyEls = document.querySelectorAll('.plant-money span');
            var vals = [];
            moneyEls.forEach(function(el) {
                var t = el.textContent.trim();
                if (/^[\\d.,]+$/.test(t)) vals.push(t);
            });
            return vals;
            """
            values = driver.execute_script(js_money)
            if values and len(values) >= 3:
                # FIXED: Correct mapping (was previously wrong)
                # .plant-money spans: [Today Yield, Monthly Yield, Total Yield, Income]
                result["daily_yield"] = values[0]
                result["monthly_yield"] = values[1]
                result["total_yield"] = values[2]
                if len(values) >= 4:
                    result["income"] = values[3]
                _log("DIAG", f"[JS] Money values: {values}")

            # ── Extract power via JS: find by header text ──
            js_power = """
            var headers = document.querySelectorAll('.el-table__header-wrapper th .cell');
            var powerIdx = -1;
            for (var i = 0; i < headers.length; i++) {
                var t = headers[i].textContent.toLowerCase();
                if (t.indexOf('power') !== -1 || t.indexOf('generating') !== -1) {
                    powerIdx = i;
                    break;
                }
            }
            if (powerIdx === -1) return null;
            var rows = document.querySelectorAll('.el-table__body-wrapper .el-table__row');
            for (var r = 0; r < rows.length; r++) {
                var cells = rows[r].querySelectorAll('td .cell');
                if (powerIdx < cells.length) {
                    var txt = cells[powerIdx].textContent.trim();
                    if (/^[\\d.,]+$/.test(txt)) return txt;
                }
            }
            return null;
            """
            power_val = driver.execute_script(js_power)
            if power_val:
                result["current_power"] = power_val
                _log("DIAG", f"[JS] Power: {power_val}")

            # ── Fallback: extract all visible numbers and look for patterns ──
            if "current_power" not in result:
                js_all_numbers = """
                var body = document.body.innerText;
                var matches = body.match(/Power\\s*Generating\\s*\\(kW\\)\\s*([\\d.,]+)/i);
                if (matches) return matches[1];
                matches = body.match(/([\\d.,]+)\\s*kW/);
                if (matches) return matches[1];
                return null;
                """
                power_text = driver.execute_script(js_all_numbers)
                if power_text:
                    result["current_power"] = power_text
                    _log("DIAG", f"[JS] Power from text: {power_text}")

        except Exception as e:
            _log("WARN", f"[JS] Extraction error: {e}")

        return result if result else None


# ═══════════════════════════════════════════════════════════════
# STRATEGY 4: SCREENSHOT OCR
# ═══════════════════════════════════════════════════════════════
class OCRStrategy:
    """Extract data from a screenshot using Tesseract OCR.

    Takes a full-page screenshot, then applies OCR and uses regex
    patterns to find numeric values associated with known labels.
    """

    @staticmethod
    def extract(driver):
        if not HAS_PIL or not HAS_TESSERACT:
            _log("DIAG", "[OCR] Skipped — Pillow or pytesseract not available")
            return None

        result = {}
        try:
            # Save screenshot
            screenshot_path = str(SNAPSHOT_DIR / "ensemble_ocr_capture.png")
            driver.save_screenshot(screenshot_path)

            if not os.path.exists(screenshot_path):
                return None

            # Run OCR
            img = Image.open(screenshot_path)

            # Full page OCR with optimized config for numeric extraction
            ocr_config = "--oem 3 --psm 6"
            ocr_text = pytesseract.image_to_string(img, config=ocr_config)

            if not ocr_text or len(ocr_text) < 20:
                _log("DIAG", "[OCR] No text extracted from screenshot")
                return None

            _log("DIAG", f"[OCR] Extracted {len(ocr_text)} chars from screenshot")

            # Apply the same regex patterns as RegexStrategy
            for field, patterns in RegexStrategy.PATTERNS.items():
                for pat in patterns:
                    m = re.search(pat, ocr_text, re.IGNORECASE)
                    if m:
                        result[field] = m.group(1).replace(",", "")
                        break

            # OCR-specific patterns (handles OCR quirks: O→0, l→1, etc.)
            ocr_patterns = {
                "daily_yield": [
                    r"Today\s*Yie[l1]d.*?([\d]+[.,]?\d*)",
                    r"([\d]+[.,]?\d*)\s*kW[hH·.]?\s*Today",
                ],
                "current_power": [
                    r"Power.*?Generat.*?([\d]+[.,]?\d*)",
                    r"([\d]+[.,]?\d*)\s*kW\b",
                ],
                "total_yield": [
                    r"Tota[l1]\s*Yie[l1]d.*?([\d]+[.,]?\d*)",
                ],
            }
            for field, patterns in ocr_patterns.items():
                if field not in result:
                    for pat in patterns:
                        m = re.search(pat, ocr_text, re.IGNORECASE)
                        if m:
                            result[field] = m.group(1).replace(",", "")
                            break

            if result:
                _log("DIAG", f"[OCR] Found: {list(result.keys())}")

        except Exception as e:
            _log("WARN", f"[OCR] Extraction error: {e}")
            traceback.print_exc()

        return result if result else None


# ═══════════════════════════════════════════════════════════════
# STRATEGY 5: NETWORK/CDP INTERCEPTION
# ═══════════════════════════════════════════════════════════════
class NetworkStrategy:
    """Capture API responses via Chrome DevTools Protocol (CDP).

    The Waaree portal (Vue.js SPA) makes XHR/fetch requests to its
    backend API for plant data. By intercepting these requests via CDP,
    we can get raw JSON data — far more reliable than DOM scraping.
    """

    @staticmethod
    def extract(driver):
        result = {}
        try:
            # Enable CDP network domain
            driver.execute_cdp_cmd("Network.enable", {})
            time.sleep(1)

            # Navigate refresh to trigger API calls
            # Use soft refresh (Vue router reload) to avoid WAF
            try:
                driver.execute_script("""
                    if (window.__vue_router__) {
                        window.__vue_router__.go(0);
                    } else if (window.$nuxt) {
                        window.$nuxt.$router.go(0);
                    } else {
                        // Subtle DOM re-render trigger
                        var app = document.querySelector('#app') || document.querySelector('.app-content');
                        if (app && app.__vue__) {
                            app.__vue__.$forceUpdate();
                        }
                    }
                """)
            except Exception:
                pass

            time.sleep(3)

            # Try to get performance log entries for XHR responses
            # This captures network responses that contain plant data
            try:
                perf_logs = driver.execute_cdp_cmd(
                    "Runtime.evaluate",
                    {"expression": """
                        (function() {
                            var entries = performance.getEntriesByType('resource');
                            var apiCalls = entries.filter(function(e) {
                                return e.name.indexOf('/api/') !== -1
                                    || e.name.indexOf('/bus/') !== -1
                                    || e.name.indexOf('plant') !== -1;
                            }).map(function(e) { return e.name; });
                            return JSON.stringify(apiCalls);
                        })();
                    """}
                )
                api_urls = perf_logs.get("result", {}).get("value", "[]")
                _log("DIAG", f"[Network] API URLs found: {api_urls[:200]}")
            except Exception:
                pass

            # Extract data from Vue component state (reactivity system)
            js_vue_data = """
            (function() {
                // Try to find Vue component with plant data
                var app = document.querySelector('#app');
                if (!app || !app.__vue__) return null;

                function searchVueTree(vm, depth) {
                    if (depth > 10) return null;
                    var data = vm.$data || vm._data || {};

                    // Look for plant data keys
                    var found = {};
                    if (data.plantInfo) {
                        found = data.plantInfo;
                    } else if (data.overview) {
                        found = data.overview;
                    } else if (data.stationData) {
                        found = data.stationData;
                    } else if (data.powerData || data.yieldData) {
                        found = {power: data.powerData, yield: data.yieldData};
                    }

                    // Check for relevant keys in the data
                    for (var key in data) {
                        if (typeof data[key] === 'object' && data[key] !== null) {
                            var obj = data[key];
                            if (obj.todayYield !== undefined || obj.today_yield !== undefined
                                || obj.totalYield !== undefined || obj.power !== undefined
                                || obj.currentPower !== undefined) {
                                return obj;
                            }
                        }
                    }

                    if (Object.keys(found).length > 0) return found;

                    // Recurse into children
                    var children = vm.$children || [];
                    for (var i = 0; i < children.length; i++) {
                        var result = searchVueTree(children[i], depth + 1);
                        if (result) return result;
                    }
                    return null;
                }

                return JSON.stringify(searchVueTree(app.__vue__, 0));
            })();
            """
            try:
                vue_data_str = driver.execute_script(js_vue_data)
                if vue_data_str and vue_data_str != "null":
                    vue_data = __import__("json").loads(vue_data_str)
                    _log("DIAG", f"[Network] Vue data: {str(vue_data)[:300]}")

                    # Map Vue data keys to our standard keys
                    key_mappings = {
                        "current_power": [
                            "currentPower", "current_power", "power",
                            "powerGenerating", "genPower", "activePower",
                        ],
                        "daily_yield": [
                            "todayYield", "today_yield", "dailyYield",
                            "daily_yield", "todayEnergy", "today_energy",
                        ],
                        "monthly_yield": [
                            "monthlyYield", "monthly_yield", "monthEnergy",
                            "month_yield",
                        ],
                        "total_yield": [
                            "totalYield", "total_yield", "totalEnergy",
                            "total_energy", "cumulativeYield",
                        ],
                        "income": [
                            "income", "accumulatedIncome", "revenue",
                            "totalIncome", "accumulated_income",
                        ],
                    }

                    for field, candidates in key_mappings.items():
                        for key in candidates:
                            val = vue_data.get(key)
                            if val is not None:
                                fval = _to_float(val)
                                if fval > 0:
                                    result[field] = str(fval)
                                    break
            except Exception as e:
                _log("DIAG", f"[Network] Vue data extraction error: {e}")

            # Disable network tracking
            try:
                driver.execute_cdp_cmd("Network.disable", {})
            except Exception:
                pass

            if result:
                _log("DIAG", f"[Network] Found: {list(result.keys())}")

        except Exception as e:
            _log("WARN", f"[Network] Extraction error: {e}")

        return result if result else None


# ═══════════════════════════════════════════════════════════════
# DEVICE TAB EXTRACTOR (Supplementary data)
# ═══════════════════════════════════════════════════════════════
class DeviceTabStrategy:
    """Extract voltage, current, frequency, temperature from device tab."""

    @staticmethod
    def extract(driver, wait):
        data = {}
        try:
            tabs = driver.find_elements(By.CSS_SELECTOR, ".el-tabs__item")
            device_tab = None
            for tab in tabs:
                try:
                    txt = tab.text.lower()
                    if any(kw in txt for kw in ["device", "inverter", "equipment"]):
                        device_tab = tab
                        break
                except StaleElementReferenceException:
                    continue

            if not device_tab:
                return None

            device_tab.click()
            time.sleep(5)
            deep_text = driver.find_element(By.TAG_NAME, "body").text

            voltage_patterns = [
                r"(?:Grid\s+)?Voltage\s*[:：]?\s*([\d.]+)\s*V?",
                r"Ua[bc]?\s*[:：]?\s*([\d.]+)",
                r"(2[0-9]{2}(?:\.\d+)?)\s*V",
            ]
            current_patterns = [
                r"(?:Output\s+)?Current\s*[:：]?\s*([\d.]+)\s*A?",
                r"Ia[bc]?\s*[:：]?\s*([\d.]+)",
                r"([\d.]+)\s*A(?:\s|$)",
            ]
            freq_patterns = [
                r"Frequency\s*[:：]?\s*([\d.]+)\s*Hz?",
                r"(4[89]|5[01])\.\d+\s*Hz",
            ]
            temp_patterns = [
                r"Temp(?:erature)?\s*[:：]?\s*([\d.]+)\s*[°C]?",
                r"([\d.]+)\s*°C",
            ]

            for name, patterns in [
                ("voltage", voltage_patterns),
                ("current", current_patterns),
                ("frequency", freq_patterns),
                ("temperature", temp_patterns),
            ]:
                for pat in patterns:
                    m = re.search(pat, deep_text, re.IGNORECASE)
                    if m:
                        data[name] = m.group(1)
                        break

        except Exception as e:
            _log("WARN", f"[DeviceTab] Error: {e}")

        return data if data else None


# ═══════════════════════════════════════════════════════════════
# ENSEMBLE VOTING ENGINE
# ═══════════════════════════════════════════════════════════════
class EnsembleVoter:
    """Consensus/voting algorithm for multi-strategy extraction."""

    @staticmethod
    def vote(strategy_results, field):
        """Compute consensus value for a single field across all strategies.

        Returns: (value, confidence, sources) where:
            - value: the consensus numeric value (float)
            - confidence: 'high' (≥3 agree), 'medium' (2 agree), 'low' (1 source)
            - sources: list of strategy names that contributed
        """
        values = []
        sources = []

        for name, result in strategy_results.items():
            if result and field in result:
                val = _to_float(result[field])
                if val > 0:
                    values.append(val)
                    sources.append(name)

        if not values:
            return 0.0, "none", []

        if len(values) == 1:
            return values[0], "low", sources

        # Group values that agree within threshold
        groups = EnsembleVoter._cluster_values(values, sources)

        # Find the largest agreeing group
        largest_group = max(groups, key=lambda g: len(g["values"]))

        n_agree = len(largest_group["values"])
        avg_value = statistics.mean(largest_group["values"])

        if n_agree >= HIGH_CONFIDENCE_MIN:
            return round(avg_value, 4), "high", largest_group["sources"]
        elif n_agree >= MEDIUM_CONFIDENCE_MIN:
            return round(avg_value, 4), "medium", largest_group["sources"]
        else:
            # No agreement; use the value from the most trusted strategy
            # Priority: CSS > Network > JS > Regex > OCR
            priority = ["css", "network", "javascript", "regex", "ocr"]
            for strat in priority:
                for name, val in zip(sources, values):
                    if strat in name.lower():
                        return round(val, 4), "low", [name]
            return round(values[0], 4), "low", [sources[0]]

    @staticmethod
    def _cluster_values(values, sources):
        """Group values that are within AGREEMENT_THRESHOLD_PCT of each other."""
        if not values:
            return []

        # Sort by value
        indexed = sorted(zip(values, sources), key=lambda x: x[0])
        groups = []
        current_group = {"values": [indexed[0][0]], "sources": [indexed[0][1]]}

        for val, src in indexed[1:]:
            # Check if this value is within threshold of the group's mean
            group_mean = statistics.mean(current_group["values"])
            pct_diff = abs(val - group_mean) / group_mean * 100 if group_mean > 0 else 100

            if pct_diff <= AGREEMENT_THRESHOLD_PCT:
                current_group["values"].append(val)
                current_group["sources"].append(src)
            else:
                groups.append(current_group)
                current_group = {"values": [val], "sources": [src]}

        groups.append(current_group)
        return groups


# ═══════════════════════════════════════════════════════════════
# ENSEMBLE EXTRACTOR — Main API
# ═══════════════════════════════════════════════════════════════
class EnsembleExtractor:
    """Run all 5 extraction strategies and return consensus data."""

    @staticmethod
    def extract(driver, wait, body_text=None):
        """Run ensemble extraction.

        Args:
            driver: Selenium WebDriver instance
            wait: WebDriverWait instance
            body_text: Pre-fetched body text (optional, will fetch if None)

        Returns:
            dict with keys:
                - data: {field: value} — consensus values
                - confidence: {field: 'high'|'medium'|'low'|'none'}
                - sources: {field: [strategy_names]}
                - strategy_results: {strategy_name: raw_result}
                - overall_confidence: float 0-100
                - extraction_method: str — primary method used
        """
        _log("DATA", "━━━ Ensemble Extraction (5 strategies) ━━━")

        # Get body text if not provided
        if body_text is None:
            try:
                body_text = driver.find_element(By.TAG_NAME, "body").text
            except Exception:
                body_text = ""

        # ── Run all strategies ──
        strategy_results = {}

        # Strategy 1: CSS
        _log("DIAG", "Running Strategy 1/5: CSS Selectors...")
        try:
            strategy_results["css"] = CSSStrategy.extract(driver)
        except Exception as e:
            _log("WARN", f"CSS strategy failed: {e}")
            strategy_results["css"] = None

        # Strategy 2: Regex
        _log("DIAG", "Running Strategy 2/5: Regex...")
        try:
            strategy_results["regex"] = RegexStrategy.extract(body_text)
        except Exception as e:
            _log("WARN", f"Regex strategy failed: {e}")
            strategy_results["regex"] = None

        # Strategy 3: JavaScript
        _log("DIAG", "Running Strategy 3/5: JavaScript...")
        try:
            strategy_results["javascript"] = JavaScriptStrategy.extract(driver)
        except Exception as e:
            _log("WARN", f"JS strategy failed: {e}")
            strategy_results["javascript"] = None

        # Strategy 4: Screenshot OCR
        _log("DIAG", "Running Strategy 4/5: Screenshot OCR...")
        try:
            strategy_results["ocr"] = OCRStrategy.extract(driver)
        except Exception as e:
            _log("WARN", f"OCR strategy failed: {e}")
            strategy_results["ocr"] = None

        # Strategy 5: Network/Vue Data
        _log("DIAG", "Running Strategy 5/5: Network/CDP...")
        try:
            strategy_results["network"] = NetworkStrategy.extract(driver)
        except Exception as e:
            _log("WARN", f"Network strategy failed: {e}")
            strategy_results["network"] = None

        # ── Log strategy results ──
        active_count = sum(1 for v in strategy_results.values() if v)
        _log("DATA", f"Strategies with data: {active_count}/5")

        for name, result in strategy_results.items():
            if result:
                vals = {k: _to_float(v) for k, v in result.items() if k in CORE_FIELDS}
                _log("DIAG", f"  {name}: {vals}")

        # ── Ensemble voting ──
        _log("VOTE", "Running ensemble voting...")
        consensus_data = {}
        confidence_map = {}
        sources_map = {}

        for field in CORE_FIELDS:
            value, confidence, sources = EnsembleVoter.vote(strategy_results, field)
            consensus_data[field] = value
            confidence_map[field] = confidence
            sources_map[field] = sources

        # ── Build result ──
        # Determine primary method (the strategy that contributed most)
        method_counts = {}
        for field, sources in sources_map.items():
            for src in sources:
                method_counts[src] = method_counts.get(src, 0) + 1
        primary_method = max(method_counts, key=method_counts.get) if method_counts else "none"

        # Overall confidence score (0-100)
        confidence_weights = {"high": 100, "medium": 70, "low": 40, "none": 0}
        field_scores = [confidence_weights[confidence_map[f]] for f in CORE_FIELDS]
        overall_confidence = statistics.mean(field_scores) if field_scores else 0

        # Log consensus
        _log("VOTE", f"Consensus (confidence={overall_confidence:.0f}%):")
        for field in CORE_FIELDS:
            _log("VOTE", f"  {field}: {consensus_data[field]} "
                         f"[{confidence_map[field]}] "
                         f"← {', '.join(sources_map[field])}")

        _log("DATA", f"━━━ Ensemble complete: method={primary_method}, "
                     f"confidence={overall_confidence:.0f}% ━━━")

        return {
            "data": consensus_data,
            "confidence": confidence_map,
            "sources": sources_map,
            "strategy_results": strategy_results,
            "overall_confidence": overall_confidence,
            "extraction_method": f"ensemble/{primary_method}",
        }

    @staticmethod
    def extract_supplementary(driver, wait):
        """Extract supplementary data (voltage, current, freq, temp) from device tab."""
        try:
            return DeviceTabStrategy.extract(driver, wait)
        except Exception as e:
            _log("WARN", f"Supplementary extraction failed: {e}")
            return None
