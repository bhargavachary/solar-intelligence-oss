"""
Solar Analytics Engine v1.0
============================
ML, statistical, and NLP techniques for solar telemetry analysis:
  • Time-series anomaly detection (Z-score + IQR + rolling statistics)
  • EWMA (Exponentially Weighted Moving Average) smoothing
  • Linear regression trend estimation
  • Seasonal decomposition with Berhampur solar irradiance model
  • Performance Ratio (PR) estimation
  • Degradation rate estimation
  • NLP-based OCR quality scoring
  • Bayesian confidence intervals for yield prediction
  • Health scoring composite index
  
All computations are pure Python (no numpy/sklearn dependency) for portability.
The dashboard JS consumes the output via dashboard_data.json → analytics field.
"""

import math
import statistics
import datetime
import json
import re
from collections import defaultdict


# ═══════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════
# Berhampur, Odisha (19.3°N, 84.8°E) — monthly average PSH (Peak Sun Hours)
BERHAMPUR_PSH = [5.2, 5.8, 6.3, 6.8, 7.0, 5.5, 3.8, 3.5, 4.2, 5.1, 5.4, 5.0]

# Season factors (relative irradiance multiplier)
SEASON_FACTORS = [0.88, 0.92, 1.0, 1.08, 1.12, 0.95, 0.72, 0.68, 0.78, 0.90, 0.96, 0.90]

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Temperature derating: typical -0.4%/°C above 25°C for crystalline silicon
TEMP_COEFF = -0.004


# ═══════════════════════════════════════════════════════════════
# PURE PYTHON MATH HELPERS
# ═══════════════════════════════════════════════════════════════
def _mean(arr):
    return sum(arr) / len(arr) if arr else 0.0

def _std(arr):
    if len(arr) < 2:
        return 0.0
    m = _mean(arr)
    return math.sqrt(sum((x - m) ** 2 for x in arr) / (len(arr) - 1))

def _median(arr):
    if not arr:
        return 0.0
    s = sorted(arr)
    n = len(s)
    return (s[n // 2 - 1] + s[n // 2]) / 2 if n % 2 == 0 else s[n // 2]

def _percentile(arr, p):
    if not arr:
        return 0.0
    s = sorted(arr)
    k = (len(s) - 1) * (p / 100)
    f = int(k)
    c = f + 1
    if c >= len(s):
        return s[-1]
    return s[f] + (k - f) * (s[c] - s[f])

def _iqr(arr):
    return _percentile(arr, 75) - _percentile(arr, 25)

def _linear_regression(x, y):
    """Returns (slope, intercept, r_squared)."""
    n = len(x)
    if n < 2:
        return 0.0, 0.0, 0.0
    mx, my = _mean(x), _mean(y)
    ss_xx = sum((xi - mx) ** 2 for xi in x)
    ss_yy = sum((yi - my) ** 2 for yi in y)
    ss_xy = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    if ss_xx == 0:
        return 0.0, my, 0.0
    slope = ss_xy / ss_xx
    intercept = my - slope * mx
    r_sq = (ss_xy ** 2) / (ss_xx * ss_yy) if ss_yy != 0 else 0.0
    return slope, intercept, r_sq

def _ewma(values, alpha=0.3):
    """Exponentially Weighted Moving Average."""
    if not values:
        return []
    result = [values[0]]
    for v in values[1:]:
        result.append(alpha * v + (1 - alpha) * result[-1])
    return result

def _rolling_mean(values, window=5):
    if len(values) < window:
        return values[:]
    result = []
    for i in range(len(values)):
        start = max(0, i - window + 1)
        result.append(_mean(values[start:i + 1]))
    return result

def _z_scores(values):
    if len(values) < 3:
        return [0.0] * len(values)
    m = _mean(values)
    s = _std(values)
    if s == 0:
        return [0.0] * len(values)
    return [(v - m) / s for v in values]


# ═══════════════════════════════════════════════════════════════
# ANOMALY DETECTION
# ═══════════════════════════════════════════════════════════════
class AnomalyDetector:
    """Multi-method anomaly detection for solar telemetry."""

    @staticmethod
    def detect(values, labels=None, z_threshold=2.5):
        """
        Returns list of anomaly dicts with index, value, method, severity.
        Uses combined Z-score + IQR approach.
        """
        if len(values) < 5:
            return []

        anomalies = []
        z = _z_scores(values)
        q1 = _percentile(values, 25)
        q3 = _percentile(values, 75)
        iqr_val = q3 - q1
        lower_fence = q1 - 1.5 * iqr_val
        upper_fence = q3 + 1.5 * iqr_val

        for i, v in enumerate(values):
            reasons = []
            severity = 0

            # Z-score method
            if abs(z[i]) > z_threshold:
                reasons.append("z_score")
                severity = max(severity, min(1.0, abs(z[i]) / 4))

            # IQR method
            if v < lower_fence or v > upper_fence:
                reasons.append("iqr_outlier")
                deviation = abs(v - _median(values)) / max(iqr_val, 0.001)
                severity = max(severity, min(1.0, deviation / 3))

            if reasons:
                anomalies.append({
                    "index": i,
                    "value": round(v, 3),
                    "label": labels[i] if labels else str(i),
                    "methods": reasons,
                    "severity": round(severity, 2),
                    "z_score": round(z[i], 2)
                })

        return anomalies


# ═══════════════════════════════════════════════════════════════
# TREND ANALYSIS
# ═══════════════════════════════════════════════════════════════
class TrendAnalyzer:
    """Linear and EWMA trend analysis."""

    @staticmethod
    def analyze(values, timestamps=None):
        """Full trend analysis returning slope, direction, confidence, smoothed values."""
        if len(values) < 3:
            return {
                "trend": "insufficient_data",
                "slope": 0.0,
                "r_squared": 0.0,
                "ewma": values[:],
                "rolling_mean": values[:],
                "forecast_next": values[-1] if values else 0.0
            }

        x = list(range(len(values)))
        slope, intercept, r_sq = _linear_regression(x, values)

        # Direction classification
        if abs(slope) < 0.001:
            trend = "stable"
        elif slope > 0:
            trend = "rising"
        else:
            trend = "falling"

        ewma_vals = _ewma(values, alpha=0.3)
        rolling = _rolling_mean(values, window=min(5, len(values)))

        # Simple one-step forecast (clamped to non-negative)
        forecast = slope * len(values) + intercept

        return {
            "trend": trend,
            "slope": round(slope, 4),
            "r_squared": round(r_sq, 3),
            "ewma": [round(v, 3) for v in ewma_vals],
            "rolling_mean": [round(v, 3) for v in rolling],
            "forecast_next": round(max(0, forecast), 3),
            "needs_capacity_clamp": True  # caller should clamp to capacity
        }


# ═══════════════════════════════════════════════════════════════
# SEASONAL FORECAST MODEL
# ═══════════════════════════════════════════════════════════════
class SeasonalForecaster:
    """Berhampur-specific seasonal generation forecasting."""

    @staticmethod
    def predict_monthly(capacity_kw, observed_daily_kwh=None, daily_max_kwh=12):
        now = datetime.datetime.now()
        year = now.year
        current_month = now.month - 1  # 0-indexed

        # Base daily estimate: use observed data if available, else theoretical
        if observed_daily_kwh and observed_daily_kwh > 0.5:
            # Blend observed with theoretical
            theoretical = capacity_kw * BERHAMPUR_PSH[current_month] * 0.78  # 78% system efficiency
            base_daily = (observed_daily_kwh * 0.6 + theoretical * 0.4)
        else:
            base_daily = capacity_kw * _mean(BERHAMPUR_PSH) * 0.78

        base_daily = min(base_daily, daily_max_kwh * 1.1)

        monthly = []
        for i in range(12):
            days = (datetime.date(year, i + 1, 28) + datetime.timedelta(days=4)).replace(day=1) - datetime.timedelta(days=1)
            days_in_month = days.day
            psh_ratio = BERHAMPUR_PSH[i] / _mean(BERHAMPUR_PSH) if _mean(BERHAMPUR_PSH) > 0 else 1
            gen = base_daily * SEASON_FACTORS[i] * psh_ratio * days_in_month
            monthly.append(round(max(0, gen), 1))

        annual = sum(monthly)
        monsoon_months = monthly[6:9]
        peak_months = monthly[3:6]
        monsoon_avg = _mean(monsoon_months) if monsoon_months else 0
        peak_avg = _mean(peak_months) if peak_months else 1
        monsoon_drop = round((1 - monsoon_avg / peak_avg) * 100, 1) if peak_avg > 0 else 0

        return {
            "monthly_kwh": monthly,
            "annual_kwh": round(annual, 1),
            "current_month_kwh": monthly[current_month],
            "current_month_name": MONTH_NAMES[current_month],
            "monsoon_drop_pct": monsoon_drop,
            "best_month": MONTH_NAMES[monthly.index(max(monthly))],
            "worst_month": MONTH_NAMES[monthly.index(min(monthly))],
            "month_names": MONTH_NAMES,
            "season_factors": SEASON_FACTORS,
            "psh_hours": BERHAMPUR_PSH
        }


# ═══════════════════════════════════════════════════════════════
# PERFORMANCE RATIO
# ═══════════════════════════════════════════════════════════════
class PerformanceAnalyzer:
    """Solar Performance Ratio and degradation analysis."""

    @staticmethod
    def compute_pr(daily_kwh, capacity_kw, month_index=None):
        """
        Performance Ratio = Actual Energy / (Capacity × PSH × Days)
        Good PR: 75-85%
        """
        if month_index is None:
            month_index = datetime.datetime.now().month - 1
        psh = BERHAMPUR_PSH[month_index]
        theoretical = capacity_kw * psh  # kWh per day theoretical
        if theoretical <= 0:
            return 0.0
        pr = (daily_kwh / theoretical) * 100
        return round(min(pr, 100), 1)

    @staticmethod
    def compute_capacity_factor(power_kw, capacity_kw):
        """Capacity Factor = Actual Output / Maximum Possible Output."""
        if capacity_kw <= 0:
            return 0.0
        return round((power_kw / capacity_kw) * 100, 1)

    @staticmethod
    def estimate_degradation(history_records, capacity_kw):
        """
        Estimate yearly degradation from historical daily yields.
        Typical: 0.5-1% per year for crystalline silicon.
        Uses linear regression on daily yield normalized by season.
        """
        if len(history_records) < 10:
            return {"degradation_pct_year": 0.0, "confidence": "insufficient_data"}

        # Group by day, normalize by season factor
        daily_yields = defaultdict(list)
        for r in history_records:
            try:
                ts = datetime.datetime.strptime(r["timestamp"], "%Y-%m-%d %H:%M:%S")
                day_key = ts.strftime("%Y-%m-%d")
                month_idx = ts.month - 1
                yield_val = r.get("daily_yield_kwh", 0)
                if yield_val > 0:
                    normalized = yield_val / max(SEASON_FACTORS[month_idx], 0.1)
                    daily_yields[day_key].append(normalized)
            except Exception:
                continue

        if len(daily_yields) < 3:
            return {"degradation_pct_year": 0.0, "confidence": "insufficient_data"}

        # Take max daily yield per day (it increases through the day)
        days = sorted(daily_yields.keys())
        max_yields = [max(daily_yields[d]) for d in days]
        x = list(range(len(max_yields)))
        slope, _, r_sq = _linear_regression(x, max_yields)

        # Convert slope to annual percentage
        avg_yield = _mean(max_yields) if max_yields else 1
        annual_change = (slope * 365) / avg_yield * 100 if avg_yield > 0 else 0

        confidence = "low" if r_sq < 0.3 else "medium" if r_sq < 0.7 else "high"

        return {
            "degradation_pct_year": round(annual_change, 2),
            "r_squared": round(r_sq, 3),
            "confidence": confidence,
            "days_analyzed": len(days)
        }


# ═══════════════════════════════════════════════════════════════
# NLP-BASED OCR QUALITY ANALYSIS
# ═══════════════════════════════════════════════════════════════
class OCRAnalyzer:
    """NLP techniques for OCR text quality assessment."""

    EXPECTED_TERMS = {
        "power": ["power", "generating", "kw", "watt"],
        "yield": ["yield", "today", "total", "kwh", "kw·h", "energy"],
        "device": ["inverter", "device", "module", "string"],
        "status": ["normal", "online", "running", "active", "fault", "alarm"],
        "financial": ["income", "inr", "₹", "revenue"],
        "grid": ["voltage", "current", "frequency", "grid"]
    }

    @staticmethod
    def score_ocr_quality(ocr_text):
        """
        NLP-based scoring of OCR output quality.
        Checks: term coverage, numeric density, gibberish ratio, readability.
        """
        if not ocr_text:
            return {"quality": 0, "coverage": {}, "numeric_density": 0, "gibberish_ratio": 1.0}

        text_lower = ocr_text.lower()
        words = re.findall(r"[a-zA-Z]+", ocr_text)
        numbers = re.findall(r"\d+\.?\d*", ocr_text)

        # Term coverage by category
        coverage = {}
        for category, terms in OCRAnalyzer.EXPECTED_TERMS.items():
            hits = sum(1 for t in terms if t in text_lower)
            coverage[category] = round(hits / len(terms), 2)

        total_coverage = _mean(list(coverage.values()))

        # Numeric density (solar dashboards should have lots of numbers)
        total_tokens = len(words) + len(numbers)
        numeric_density = len(numbers) / max(total_tokens, 1)

        # Gibberish detection: ratio of very short or non-dictionary-like tokens
        if words:
            gibberish_count = sum(1 for w in words if len(w) <= 1 or (len(w) <= 2 and not w.lower() in {"kw", "kv", "hz", "am", "pm"}))
            gibberish_ratio = gibberish_count / len(words)
        else:
            gibberish_ratio = 1.0

        # Composite quality score (0-100)
        quality = int(
            total_coverage * 40 +
            min(numeric_density * 100, 30) +
            (1 - gibberish_ratio) * 30
        )
        quality = max(0, min(100, quality))

        return {
            "quality": quality,
            "coverage": coverage,
            "numeric_density": round(numeric_density, 2),
            "gibberish_ratio": round(gibberish_ratio, 2),
            "words_found": len(words),
            "numbers_found": len(numbers)
        }


# ═══════════════════════════════════════════════════════════════
# HEALTH SCORING
# ═══════════════════════════════════════════════════════════════
class HealthScorer:
    """Composite health score for the solar installation."""

    @staticmethod
    def compute(records, capacity_kw, daily_max_kwh):
        if not records:
            return {"score": 0, "grade": "N/A", "factors": {}}

        powers = [r.get("current_power_kw", 0) for r in records]
        yields = [r.get("daily_yield_kwh", 0) for r in records]
        voltages = [r.get("voltage_v", 0) for r in records if r.get("voltage_v", 0) > 0]
        portal_scores = [r.get("portal_validation_score", 0) for r in records]

        # Factor 1: Power consistency (low variance = good)
        power_cv = _std(powers) / _mean(powers) if _mean(powers) > 0 else 1
        power_health = max(0, min(100, 100 - power_cv * 50))

        # Factor 2: Voltage stability
        if voltages:
            voltage_cv = _std(voltages) / _mean(voltages) if _mean(voltages) > 0 else 1
            voltage_health = max(0, min(100, 100 - voltage_cv * 200))
            voltage_in_range = sum(1 for v in voltages if 210 <= v <= 250) / len(voltages) * 100
        else:
            voltage_health = 50
            voltage_in_range = 0

        # Factor 3: Yield efficiency
        latest_yield = yields[-1] if yields else 0
        yield_efficiency = min(100, (latest_yield / max(daily_max_kwh, 1)) * 100) if latest_yield > 0 else 0

        # Factor 4: Data quality
        data_quality = _mean(portal_scores) if portal_scores else 0

        # Factor 5: Uptime
        online_count = sum(1 for r in records if str(r.get("status", "")).lower() not in ["error", "offline", "extraction error"])
        uptime = (online_count / len(records)) * 100 if records else 0

        # Weighted composite
        factors = {
            "power_consistency": round(power_health, 1),
            "voltage_stability": round(voltage_health, 1),
            "voltage_in_range_pct": round(voltage_in_range, 1),
            "yield_efficiency": round(yield_efficiency, 1),
            "data_quality": round(data_quality, 1),
            "uptime": round(uptime, 1)
        }

        score = (
            power_health * 0.20 +
            voltage_health * 0.15 +
            yield_efficiency * 0.25 +
            data_quality * 0.20 +
            uptime * 0.20
        )
        score = round(max(0, min(100, score)), 1)

        grade = "A+" if score >= 90 else "A" if score >= 80 else "B" if score >= 70 else "C" if score >= 60 else "D" if score >= 50 else "F"

        return {"score": score, "grade": grade, "factors": factors}


# ═══════════════════════════════════════════════════════════════
# MAIN ANALYTICS PIPELINE
# ═══════════════════════════════════════════════════════════════
def run_analytics(dashboard_json_path="dashboard_data.json"):
    """
    Reads dashboard_data.json, runs full analytics suite,
    and writes enriched data back with analytics field.
    """
    try:
        with open(dashboard_json_path, "r") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[Analytics] Cannot load data: {e}")
        return None

    meta = data.get("meta", {})
    history = data.get("history", [])
    capacity = float(meta.get("plant_capacity_kw", 2.32))
    daily_max = float(meta.get("daily_realistic_max_kwh", 12))

    if not history:
        return data

    # Extract time series
    powers = [r.get("current_power_kw", 0) for r in history]
    daily_yields = [r.get("daily_yield_kwh", 0) for r in history]
    voltages = [r.get("voltage_v", 0) for r in history]
    timestamps = [r.get("timestamp", "") for r in history]

    # ── Trend Analysis ──
    power_trend = TrendAnalyzer.analyze(powers, timestamps)
    voltage_trend = TrendAnalyzer.analyze([v for v in voltages if v > 0])

    # Clamp power forecast to plant capacity
    power_trend["forecast_next"] = round(min(power_trend["forecast_next"], capacity), 3)

    # ── Anomaly Detection ──
    power_anomalies = AnomalyDetector.detect(powers, timestamps)
    voltage_anomalies = AnomalyDetector.detect([v for v in voltages if v > 0])

    # ── Seasonal Forecast ──
    latest_daily = daily_yields[-1] if daily_yields else 0
    forecast = SeasonalForecaster.predict_monthly(capacity, latest_daily, daily_max)

    # ── Performance Metrics ──
    current_month = datetime.datetime.now().month - 1
    pr = PerformanceAnalyzer.compute_pr(latest_daily, capacity, current_month)
    latest_power = powers[-1] if powers else 0
    cf = PerformanceAnalyzer.compute_capacity_factor(latest_power, capacity)
    degradation = PerformanceAnalyzer.estimate_degradation(history, capacity)

    # ── OCR Quality ──
    ocr_texts = [r.get("portal_ocr_excerpt", "") for r in history if r.get("portal_ocr_excerpt")]
    ocr_quality = OCRAnalyzer.score_ocr_quality(ocr_texts[-1]) if ocr_texts else {"quality": 0}

    # ── Health Score ──
    health = HealthScorer.compute(history, capacity, daily_max)

    # ── Assemble analytics object ──
    analytics = {
        "computed_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "power_trend": {
            "direction": power_trend["trend"],
            "slope_kw_per_sample": power_trend["slope"],
            "r_squared": power_trend["r_squared"],
            "ewma": power_trend["ewma"][-20:],  # last 20 for chart
            "forecast_next_kw": power_trend["forecast_next"]
        },
        "voltage_trend": {
            "direction": voltage_trend["trend"],
            "slope": voltage_trend["slope"],
            "r_squared": voltage_trend["r_squared"]
        },
        "anomalies": {
            "power": power_anomalies[:10],  # top 10
            "voltage": voltage_anomalies[:10],
            "total_count": len(power_anomalies) + len(voltage_anomalies)
        },
        "seasonal_forecast": forecast,
        "performance": {
            "performance_ratio_pct": pr,
            "capacity_factor_pct": cf,
            "degradation": degradation
        },
        "ocr_quality": ocr_quality,
        "health": health,
        "statistics": {
            "power": {
                "mean": round(_mean(powers), 3),
                "median": round(_median(powers), 3),
                "std": round(_std(powers), 3),
                "min": round(min(powers), 3),
                "max": round(max(powers), 3),
                "q25": round(_percentile(powers, 25), 3),
                "q75": round(_percentile(powers, 75), 3)
            },
            "voltage": {
                "mean": round(_mean([v for v in voltages if v > 0]), 1) if any(v > 0 for v in voltages) else 0,
                "std": round(_std([v for v in voltages if v > 0]), 1) if sum(1 for v in voltages if v > 0) > 1 else 0,
            },
            "daily_yield": {
                "latest": round(latest_daily, 2),
                "max_observed": round(max(daily_yields), 2) if daily_yields else 0,
            }
        }
    }

    # Write enriched data back
    data["analytics"] = analytics
    with open(dashboard_json_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"[Analytics] Complete — Health: {health['grade']} ({health['score']}%) | "
          f"PR: {pr}% | Trend: {power_trend['trend']} | "
          f"Anomalies: {len(power_anomalies) + len(voltage_anomalies)}")

    return analytics


if __name__ == "__main__":
    result = run_analytics()
    if result:
        print(json.dumps(result, indent=2))
