"""
GigSure Weather Monitor
=======================
Background task that:
1. Fetches current weather for all cities where beneficiaries are registered
2. Runs ML risk model on the data
3. Auto-creates claims for users whose policy thresholds are exceeded
4. Sends email + in-app notifications

Run as a management command (see management/commands/run_weather_monitor.py)
or schedule with cron / Celery beat.

Standalone test:
    python manage.py run_weather_monitor --once
"""

import os
import time
import logging
import requests
from datetime import date, datetime
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.utils import timezone

logger = logging.getLogger('gigsure.monitor')

# ── Config ───────────────────────────────────────────────────────────────────

# WeatherAPI.com free key — replace with yours
WEATHER_API_KEY = getattr(settings, 'WEATHER_API_KEY', 'd76f6b52979d4579b5543501260204')
WEATHER_API_URL = "https://api.weatherapi.com/v1/current.json"

# Default cities to monitor (add more as users register different cities)
DEFAULT_CITIES = ['Vadodara', 'Bengaluru', 'Mumbai', 'Delhi', 'Chennai', 'Hyderabad', 'Pune']

# Poll interval in seconds (used when running in loop mode)
POLL_INTERVAL_SECONDS = 300  # 5 minutes

# Prevent duplicate auto-claims for same user on same day
MAX_AUTO_CLAIMS_PER_USER_PER_DAY = 1


# ── Main runner ───────────────────────────────────────────────────────────────

def run_monitor_once():
    """
    Single monitoring pass — fetch weather for all cities, evaluate thresholds,
    create claims if needed.  Call this from a management command or scheduler.
    """
    # Lazy imports to avoid circular issues when called from Django management
    from core.models import Policy, WeatherLog, Claim, Notification
    from core.ml_model import predict_claim_probability

    logger.info("🌦️  Weather monitor pass starting...")

    # Collect all cities that have active beneficiaries
    cities = _get_monitored_cities()
    if not cities:
        logger.info("No active beneficiaries found. Skipping.")
        return

    for city in cities:
        try:
            weather_data = _fetch_weather(city)
            if not weather_data:
                continue

            # Save weather log
            weather_log = _save_weather_log(weather_data, city)

            # Run ML model
            ml_score = predict_claim_probability({
                'rainfall_mm':    weather_data['precip_mm'],
                'wind_speed_kph': weather_data['wind_kph'],
                'temperature_c':  weather_data['temp_c'],
                'humidity_pct':   weather_data['humidity'],
                'condition_code': weather_data['condition_code'],
            })
            weather_log.ml_risk_score = ml_score
            weather_log.is_disruption = ml_score >= 0.5
            weather_log.save()

            logger.info(
                f"  {city}: temp={weather_data['temp_c']}°C rain={weather_data['precip_mm']}mm "
                f"wind={weather_data['wind_kph']}kph ML={ml_score:.0%}"
            )

            # For each policy covering this city's beneficiaries
            policies = Policy.objects.filter(is_active=True)
            for policy in policies:
                for user in policy.beneficiaries.all():
                    _maybe_create_auto_claim(user, policy, weather_data, weather_log, ml_score, city)

        except Exception as e:
            logger.error(f"  ❌ Error processing {city}: {e}")

    logger.info("✅ Weather monitor pass complete.")


def run_monitor_loop():
    """Run monitor in a continuous loop (for development / simple deployments)."""
    logger.info(f"⏱  Starting monitor loop (interval: {POLL_INTERVAL_SECONDS}s)")
    while True:
        try:
            run_monitor_once()
        except Exception as e:
            logger.error(f"Monitor loop error: {e}")
        time.sleep(POLL_INTERVAL_SECONDS)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_monitored_cities():
    """Return list of cities for active beneficiary users."""
    # In production, store city in the user's profile.
    # For now, return the defaults + any city on active claims.
    from core.models import Claim
    claim_cities = list(
        Claim.objects.values_list('city', flat=True).distinct()
    )
    all_cities = list(set(DEFAULT_CITIES + claim_cities))
    return all_cities


def _fetch_weather(city: str) -> dict | None:
    """Fetch current weather for a city from WeatherAPI.com."""
    try:
        resp = requests.get(
            WEATHER_API_URL,
            params={'key': WEATHER_API_KEY, 'q': city, 'aqi': 'no'},
            timeout=10,
        )
        if resp.status_code != 200:
            logger.warning(f"WeatherAPI returned {resp.status_code} for {city}")
            return None
        data = resp.json()
        cur = data['current']
        return {
            'city':           city,
            'temp_c':         cur['temp_c'],
            'feels_like_c':   cur['feelslike_c'],
            'humidity':       cur['humidity'],
            'precip_mm':      cur['precip_mm'],
            'wind_kph':       cur['wind_kph'],
            'condition_text': cur['condition']['text'],
            'condition_code': cur['condition']['code'],
            'lat':            data['location']['lat'],
            'lon':            data['location']['lon'],
        }
    except Exception as e:
        logger.error(f"Weather fetch failed for {city}: {e}")
        return None


def _save_weather_log(weather_data: dict, city: str):
    """Save a WeatherLog record and return it."""
    from core.models import WeatherLog
    return WeatherLog.objects.create(
        city=city,
        latitude=weather_data.get('lat'),
        longitude=weather_data.get('lon'),
        temperature_c=weather_data['temp_c'],
        feels_like_c=weather_data['feels_like_c'],
        humidity_pct=weather_data['humidity'],
        rainfall_mm=weather_data['precip_mm'],
        wind_speed_kph=weather_data['wind_kph'],
        condition_text=weather_data['condition_text'],
        condition_code=weather_data['condition_code'],
    )


def _threshold_exceeded(weather_data: dict, policy, ml_score: float) -> tuple[bool, str]:
    """
    Check if any policy threshold is exceeded.
    Returns (exceeded: bool, reason: str).
    """
    rain  = weather_data['precip_mm']
    wind  = weather_data['wind_kph']
    temp  = weather_data['temp_c']

    if rain >= policy.rainfall_threshold_mm:
        return True, f"Heavy rain ({rain} mm ≥ threshold {policy.rainfall_threshold_mm} mm)"
    if wind >= policy.wind_speed_threshold_kph:
        return True, f"High wind ({wind} km/h ≥ threshold {policy.wind_speed_threshold_kph} km/h)"
    if temp <= policy.temperature_min_threshold_c:
        return True, f"Extreme cold ({temp}°C ≤ threshold {policy.temperature_min_threshold_c}°C)"
    if temp >= policy.temperature_max_threshold_c:
        return True, f"Extreme heat ({temp}°C ≥ threshold {policy.temperature_max_threshold_c}°C)"
    if ml_score >= policy.ml_claim_probability_threshold:
        return True, f"ML risk score ({ml_score:.0%} ≥ threshold {policy.ml_claim_probability_threshold:.0%})"
    return False, ""


def _maybe_create_auto_claim(user, policy, weather_data: dict, weather_log, ml_score: float, city: str):
    """Create an auto-claim for the user if thresholds are exceeded and no claim exists today."""
    from core.models import Claim, Notification

    # Check threshold
    exceeded, reason = _threshold_exceeded(weather_data, policy, ml_score)
    if not exceeded:
        return

    # Prevent duplicate auto-claims for same user today
    today_claims = Claim.objects.filter(
        claimant=user,
        source=Claim.SOURCE_AUTO,
        incident_date=date.today(),
    ).count()
    if today_claims >= MAX_AUTO_CLAIMS_PER_USER_PER_DAY:
        logger.info(f"    Skipping {user.email}: already has auto-claim today")
        return

    # Generate claim ID
    import random
    claim_id = f"GS-{date.today().year}-AUTO-{random.randint(100000, 999999)}"

    # Estimate payout (80% of ₹900 expected daily average)
    expected = Decimal('900.00')
    actual   = Decimal('310.00')  # estimated low during disruption
    loss     = expected - actual
    payout   = round(loss * Decimal(str(policy.payout_percentage)) / 100, 2)
    payout   = min(payout, policy.max_payout_per_claim)

    # Map condition to disruption type
    disruption_type = _condition_to_disruption(weather_data['condition_code'], weather_data['precip_mm'])

    claim = Claim.objects.create(
        claimant=user,
        policy=policy,
        claim_id=claim_id,
        source=Claim.SOURCE_AUTO,
        status=Claim.STATUS_PENDING,
        disruption_type=disruption_type,
        city=city,
        incident_date=date.today(),
        incident_time=datetime.now().time(),
        expected_earnings=expected,
        actual_earnings=actual,
        estimated_loss=loss,
        payout_amount=payout,
        ai_confidence=ml_score,
        ai_reasoning=(
            f"Auto-triggered: {reason}. "
            f"ML model predicted {ml_score:.0%} claim probability. "
            f"Condition: {weather_data['condition_text']}. "
            f"Weather recorded at {timezone.now().strftime('%H:%M IST')}."
        ),
        ai_approved=True,
        weather_log=weather_log,
        description=f"[AUTO] {reason}",
    )

    logger.info(f"    ✅ Auto-claim {claim.claim_id} created for {user.email}")

    # Create in-app notification
    Notification.objects.create(
        recipient=user,
        notif_type=Notification.TYPE_CLAIM_AUTO,
        title=f"Auto-claim created: {claim.claim_id}",
        body=(
            f"Extreme weather detected in {city}. "
            f"We've automatically filed a claim on your behalf. "
            f"Reason: {reason}. "
            f"Estimated payout: ₹{payout}."
        ),
        claim=claim,
    )

    # Send email notification
    _send_claim_email(user, claim, reason)


def _condition_to_disruption(code: int, precip_mm: float) -> str:
    """Map a WeatherAPI condition code to a GigSure disruption type."""
    thunder_codes = {1087, 1273, 1276, 1279, 1282}
    rain_codes    = {1063, 1150, 1153, 1180, 1183, 1186, 1189, 1192, 1195, 1240, 1243, 1246}

    if code in thunder_codes:
        return 'storm'
    if code in rain_codes or precip_mm > 5:
        return 'heavy_rain' if precip_mm > 10 else 'heavy_rain'
    return 'other'


def _send_claim_email(user, claim, reason: str):
    """Send an email notification to the user about their auto-created claim."""
    if not user.email:
        return
    try:
        subject = f"[GigSure] Auto-claim {claim.claim_id} created for you"
        body = f"""Hi {user.first_name},

GigSure has automatically filed a claim on your behalf.

Claim ID   : {claim.claim_id}
Date       : {claim.incident_date}
Reason     : {reason}
Payout est.: ₹{claim.payout_amount}
Status     : Pending review

We detected extreme weather in {claim.city} that likely disrupted your deliveries.
No action needed from you — our team will review and process the payout soon.

For questions, visit gigsure.in or reply to this email.

— The GigSure Team
"""
        send_mail(
            subject=subject,
            message=body,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@gigsure.in'),
            recipient_list=[user.email],
            fail_silently=True,
        )
        logger.info(f"    📧 Email sent to {user.email}")
    except Exception as e:
        logger.warning(f"    Email failed for {user.email}: {e}")