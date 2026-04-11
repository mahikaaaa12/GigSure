"""
GigSure Fraud Detection Engine
================================
Calculates a fraud score (0–100) for each submitted claim.
Higher score = more suspicious.

Usage:
    from core.fraud_utils import calculate_fraud_score

    result = calculate_fraud_score(claim, weather_data, user_history)
    # result = {
    #   "fraud_score": 34,
    #   "decision": "approve",          # approve | review | reject
    #   "reasoning_text": "...",
    #   "flags": [...],
    # }
"""

from datetime import date, timedelta


# ── Decision thresholds ────────────────────────────────────────────────────
THRESHOLD_APPROVE = 40   # score < 40  → auto approve
THRESHOLD_REVIEW  = 70   # 40–69       → pending manual review
                          # 70+         → auto reject


def calculate_fraud_score(claim, weather_data: dict, user_history: dict) -> dict:
    """
    Parameters
    ----------
    claim        : Claim model instance (or dict with same keys)
    weather_data : dict with keys: rainfall_mm, wind_speed_kph, temperature_c,
                   humidity_pct, condition_code, condition_text
    user_history : dict with keys:
                     claims_last_7d   (int)
                     claims_last_30d  (int)
                     avg_expected_earnings (float)
                     avg_actual_earnings   (float)

    Returns
    -------
    dict with fraud_score, decision, reasoning_text, flags
    """
    flags  = []
    score  = 0

    # ── 1. Weather mismatch check ──────────────────────────────────────────
    weather_score, weather_flags = _check_weather_mismatch(claim, weather_data)
    score += weather_score
    flags.extend(weather_flags)

    # ── 2. Claim frequency check ───────────────────────────────────────────
    freq_score, freq_flags = _check_claim_frequency(user_history)
    score += freq_score
    flags.extend(freq_flags)

    # ── 3. Earnings plausibility check ────────────────────────────────────
    earn_score, earn_flags = _check_earnings_plausibility(claim, user_history)
    score += earn_score
    flags.extend(earn_flags)

    # ── 4. Time anomaly check ──────────────────────────────────────────────
    time_score, time_flags = _check_time_anomalies(claim)
    score += time_score
    flags.extend(time_flags)

    score = min(100, max(0, score))

    # ── Decision ───────────────────────────────────────────────────────────
    if score < THRESHOLD_APPROVE:
        decision = "approve"
    elif score < THRESHOLD_REVIEW:
        decision = "review"
    else:
        decision = "reject"

    reasoning_text = _build_reasoning(score, decision, flags, weather_data, claim)

    return {
        "fraud_score":    score,
        "decision":       decision,
        "reasoning_text": reasoning_text,
        "flags":          flags,
    }


# ── Sub-checks ────────────────────────────────────────────────────────────

def _check_weather_mismatch(claim, weather_data: dict):
    """
    Compare claimed disruption type against actual weather readings.
    Rain claim + no rain → high mismatch.
    """
    score = 0
    flags = []

    disruption = _get_field(claim, "disruption_type", "heavy_rain")
    rain_mm    = float(weather_data.get("rainfall_mm", weather_data.get("precip_mm", 0)))
    wind_kph   = float(weather_data.get("wind_speed_kph", weather_data.get("wind_kph", 0)))
    temp_c     = float(weather_data.get("temperature_c", weather_data.get("temp_c", 28)))
    ml_score   = float(weather_data.get("ml_risk_score", 0.0))

    rain_claims = {"heavy_rain", "flood", "storm"}
    heat_claims = {"extreme_heat"}
    cold_claims = {"extreme_cold"}

    if disruption in rain_claims:
        if rain_mm < 1.0 and wind_kph < 30:
            score += 30
            flags.append(f"Weather mismatch: claimed rain/storm but only {rain_mm}mm rain and {wind_kph}km/h wind recorded")
        elif rain_mm < 3.0:
            score += 15
            flags.append(f"Marginal weather: only {rain_mm}mm rainfall for heavy rain claim")

    if disruption in heat_claims and temp_c < 40:
        score += 25
        flags.append(f"Weather mismatch: extreme heat claimed but temp only {temp_c}°C")

    if disruption in cold_claims and temp_c > 15:
        score += 25
        flags.append(f"Weather mismatch: extreme cold claimed but temp is {temp_c}°C")

    # ML score bonus — if ML says low risk but claim says disruption
    if ml_score < 0.25 and disruption in rain_claims:
        score += 12
        flags.append(f"ML model predicts low disruption probability ({ml_score:.0%})")

    return score, flags


def _check_claim_frequency(user_history: dict):
    score = 0
    flags = []

    claims_7d  = int(user_history.get("claims_last_7d",  0))
    claims_30d = int(user_history.get("claims_last_30d", 0))

    if claims_7d >= 5:
        score += 35
        flags.append(f"Very high claim frequency: {claims_7d} claims in the last 7 days")
    elif claims_7d >= 3:
        score += 20
        flags.append(f"High claim frequency: {claims_7d} claims in the last 7 days")
    elif claims_7d >= 2:
        score += 8
        flags.append(f"Elevated claim frequency: {claims_7d} claims in last 7 days")

    if claims_30d >= 10:
        score += 15
        flags.append(f"Unusually high monthly claims: {claims_30d} in last 30 days")

    return score, flags


def _check_earnings_plausibility(claim, user_history: dict):
    score = 0
    flags = []

    expected = float(_get_field(claim, "expected_earnings", 0))
    actual   = float(_get_field(claim, "actual_earnings",   0))
    loss     = max(0.0, expected - actual)

    avg_expected = float(user_history.get("avg_expected_earnings", 900))
    avg_actual   = float(user_history.get("avg_actual_earnings",   400))

    # Implausibly high expected earnings
    if avg_expected > 0 and expected > avg_expected * 2.5:
        score += 25
        flags.append(f"Inflated expected earnings: ₹{expected:.0f} vs avg ₹{avg_expected:.0f}")

    # Suspiciously round numbers (e.g., exactly 0 actual)
    if actual == 0 and expected > 0:
        score += 10
        flags.append("Zero actual earnings declared — possible exaggeration")

    # Loss > 90% of expected with no supporting weather evidence
    if expected > 0 and loss / expected > 0.90:
        score += 8
        flags.append(f"Near-total income loss claimed ({loss/expected:.0%}) — requires strong evidence")

    # Earnings too low to be a real gig worker
    if expected < 100 and expected > 0:
        score += 5
        flags.append(f"Unusually low expected earnings: ₹{expected:.0f}")

    return score, flags


def _check_time_anomalies(claim):
    score = 0
    flags = []

    incident_date = _get_field(claim, "incident_date", date.today())
    if isinstance(incident_date, str):
        try:
            from datetime import datetime
            incident_date = datetime.strptime(incident_date, "%Y-%m-%d").date()
        except Exception:
            incident_date = date.today()

    today = date.today()
    days_ago = (today - incident_date).days

    # Backdated claims
    if days_ago > 7:
        score += 20
        flags.append(f"Backdated claim: incident {days_ago} days ago (limit is 7 days)")
    elif days_ago > 3:
        score += 8
        flags.append(f"Late filing: incident {days_ago} days ago")

    # Future-dated claims
    if incident_date > today:
        score += 40
        flags.append("Future-dated incident — cannot file claims for future dates")

    return score, flags


# ── Reasoning builder ─────────────────────────────────────────────────────

def _build_reasoning(score: int, decision: str, flags: list, weather_data: dict, claim) -> str:
    disruption = _get_field(claim, "disruption_type", "disruption")
    rain_mm    = float(weather_data.get("rainfall_mm", weather_data.get("precip_mm", 0)))
    wind_kph   = float(weather_data.get("wind_speed_kph", weather_data.get("wind_kph", 0)))
    temp_c     = float(weather_data.get("temperature_c", weather_data.get("temp_c", 28)))
    ml_score   = float(weather_data.get("ml_risk_score", 0.5))

    weather_summary = (
        f"Live weather: {rain_mm}mm rain, {wind_kph}km/h wind, {temp_c}°C. "
        f"ML disruption probability: {ml_score:.0%}."
    )

    if decision == "approve":
        return (
            f"Fraud score {score}/100 — claim cleared. {weather_summary} "
            f"Earnings profile and claim frequency are within normal range. "
            f"Auto-approved for payout processing."
        )
    elif decision == "review":
        flag_summary = "; ".join(flags[:2]) if flags else "Minor anomalies detected"
        return (
            f"Fraud score {score}/100 — flagged for manual review. {weather_summary} "
            f"Issues: {flag_summary}. "
            f"Claim held pending insurer verification."
        )
    else:
        flag_summary = "; ".join(flags[:3]) if flags else "Multiple risk factors"
        return (
            f"Fraud score {score}/100 — claim rejected by AI engine. {weather_summary} "
            f"Critical flags: {flag_summary}. "
            f"Claim has been auto-rejected. Claimant may appeal with supporting documents."
        )


# ── Utility ────────────────────────────────────────────────────────────────

def _get_field(obj, field, default):
    """Works with both model instances and dicts."""
    if isinstance(obj, dict):
        return obj.get(field, default)
    return getattr(obj, field, default)


# ── User history helper (call from views.py) ───────────────────────────────

def get_user_claim_history(user) -> dict:
    """
    Fetch recent claim history stats for a user.
    Returns dict compatible with calculate_fraud_score().
    """
    from django.db.models import Avg
    from core.models import Claim

    today    = date.today()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    user_claims = Claim.objects.filter(claimant=user)

    claims_7d  = user_claims.filter(incident_date__gte=week_ago).count()
    claims_30d = user_claims.filter(incident_date__gte=month_ago).count()

    agg = user_claims.aggregate(
        avg_exp=Avg("expected_earnings"),
        avg_act=Avg("actual_earnings"),
    )

    return {
        "claims_last_7d":        claims_7d,
        "claims_last_30d":       claims_30d,
        "avg_expected_earnings": float(agg["avg_exp"] or 900),
        "avg_actual_earnings":   float(agg["avg_act"] or 400),
    }
