"""
GigSure views.py — full extended version
Includes:
  - All original auth views (unchanged)
  - Insurer dashboard views
  - Claim management (approve/reject/filter)
  - Policy CRUD
  - ML risk score API
  - AI assistant endpoint
  - Analytics endpoint
  - Auto-claim trigger (manual test)
"""

import json
import random
import string
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import authenticate
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.models import User
from django.db.models import Count, Q, Sum, Avg
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings


# ══════════════════════════════════════════════════════════════
# PAGE VIEWS
# ══════════════════════════════════════════════════════════════

def home(request):
    return render(request, "login.html")


def dashboard(request):
    return render(request, "index.html")


def claim_page(request):
    return render(request, "claim.html")


def weather_page(request):
    return render(request, "weather.html")


def insurer_dashboard(request):
    """Insurer-only dashboard page."""
    return render(request, "insurer_dashboard.html")


# ══════════════════════════════════════════════════════════════
# HELPER
# ══════════════════════════════════════════════════════════════

def _user_dict(user, role=None):
    return {
        "id":         user.id,
        "email":      user.email,
        "first_name": user.first_name,
        "last_name":  user.last_name,
        "role":       role or "beneficiary",
        "created_at": user.date_joined.isoformat() if user.date_joined else None,
        "last_login": user.last_login.isoformat() if user.last_login else None,
    }


def _require_insurer(request):
    """Return None if OK, JsonResponse if not insurer."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Not authenticated."}, status=401)
    role = request.session.get("role", "beneficiary")
    if role != "insurer":
        return JsonResponse({"error": "Insurer access only."}, status=403)
    return None


def _gen_claim_id():
    return "GS-" + str(date.today().year) + "-" + "".join(random.choices(string.digits, k=6))


# ══════════════════════════════════════════════════════════════
# AUTH API  (unchanged from original)
# ══════════════════════════════════════════════════════════════

@csrf_exempt
@require_http_methods(["POST"])
def signup(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "errors": {"general": "Invalid JSON."}}, status=400)

    email      = (data.get("email") or "").strip()
    password   = data.get("password", "")
    first_name = (data.get("first_name") or "").strip()
    last_name  = (data.get("last_name") or "").strip()
    role       = data.get("role", "beneficiary")
    company    = (data.get("company") or "").strip()

    errors = {}
    if not first_name: errors["first_name"] = "First name is required."
    if not last_name:  errors["last_name"]  = "Last name is required."
    if not email:      errors["email"]      = "Email is required."
    if not password or len(password) < 6:
        errors["password"] = "Password must be at least 6 characters."
    if role not in ("insurer", "beneficiary"):
        errors["role"] = "Invalid role."
    if errors:
        return JsonResponse({"success": False, "errors": errors}, status=400)

    if User.objects.filter(username=email).exists():
        return JsonResponse(
            {"success": False, "errors": {"email": "Account with this email already exists."}},
            status=400,
        )

    user = User.objects.create_user(
        username=email, email=email, password=password,
        first_name=first_name, last_name=last_name,
    )
    auth_login(request, user)
    request.session["role"] = role
    request.session["company"] = company
    return JsonResponse({"success": True, "user": _user_dict(user, role=role)})


@csrf_exempt
@require_http_methods(["POST"])
def login(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "errors": {"general": "Invalid JSON."}}, status=400)

    email    = (data.get("email") or "").strip()
    password = data.get("password", "")
    role     = data.get("role", "beneficiary")

    if not email or not password:
        return JsonResponse({"success": False, "errors": {"general": "Fill in all fields."}}, status=400)

    user = authenticate(request, username=email, password=password)
    if user is None:
        return JsonResponse({"success": False, "errors": {"general": "Incorrect email or password."}}, status=401)

    auth_login(request, user)
    request.session["role"] = role
    return JsonResponse({"success": True, "user": _user_dict(user, role=role)})


def me(request):
    if request.user.is_authenticated:
        role = request.session.get("role", "beneficiary")
        return JsonResponse({"user": _user_dict(request.user, role=role)})
    return JsonResponse({"user": None})


@csrf_exempt
def logout(request):
    auth_logout(request)
    return JsonResponse({"success": True})


# ══════════════════════════════════════════════════════════════
# WEATHER API  (from original + extended)
# ══════════════════════════════════════════════════════════════

from .utils.weather import get_weather as _get_weather_data


def weather_api(request):
    city = request.GET.get("city", "Vadodara")
    data = _get_weather_data(city)
    return JsonResponse({"success": True, "data": data})


# ══════════════════════════════════════════════════════════════
# CLAIMS API
# ══════════════════════════════════════════════════════════════

@csrf_exempt
@require_http_methods(["POST"])
def submit_claim(request):
    """Beneficiary submits a claim (manual or auto-fill)."""
    if not request.user.is_authenticated:
        return JsonResponse({"success": False, "error": "Login required."}, status=401)
 
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON."}, status=400)
 
    from .models import Claim, Policy, Notification
 
    claim_id = _gen_claim_id()
    expected = Decimal(str(data.get("expected_earnings", 0)))
    actual   = Decimal(str(data.get("actual_earnings", 0)))
    loss     = max(Decimal("0"), expected - actual)
    payout   = round(loss * Decimal("0.80"), 2)
 
    # Parse optional incident_time
    incident_time = None
    raw_time = data.get("incident_time")
    if raw_time:
        try:
            from datetime import time as dt_time
            parts = raw_time.split(":")
            incident_time = dt_time(int(parts[0]), int(parts[1]))
        except Exception:
            pass
 
    claim = Claim.objects.create(
        claimant=request.user,
        claim_id=claim_id,
        source=Claim.SOURCE_MANUAL,
        status=Claim.STATUS_PENDING,
        disruption_type=data.get("disruption_type", "heavy_rain"),
        city=data.get("city", "Vadodara"),
        platform=data.get("platform", ""),
        incident_date=date.today(),
        incident_time=incident_time,
        expected_earnings=expected,
        actual_earnings=actual,
        estimated_loss=loss,
        payout_amount=payout,
        description=data.get("description", ""),
        ai_confidence=data.get("ai_confidence"),
        ai_reasoning=data.get("ai_reasoning", ""),
        ai_approved=data.get("ai_approved"),
    )
 
    # Notify the claimant that their claim was received
    Notification.objects.create(
        recipient=request.user,
        notif_type=Notification.TYPE_GENERAL,
        title=f"Claim {claim.claim_id} submitted",
        body=f"Your income protection claim for ₹{claim.payout_amount} has been received and is pending review.",
        claim=claim,
    )
 
    return JsonResponse({
        "success":  True,
        "claim_id": claim.claim_id,
        "payout":   float(claim.payout_amount),
        "status":   claim.status,
    })


@require_http_methods(["GET"])
def my_claims(request):
    """Beneficiary: list their own claims."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Login required."}, status=401)

    from .models import Claim
    claims = Claim.objects.filter(claimant=request.user).select_related("weather_log")
    return JsonResponse({"claims": [_claim_dict(c) for c in claims]})


def _claim_dict(c):
    return {
        "id":              c.id,
        "claim_id":        c.claim_id,
        "source":          c.source,
        "status":          c.status,
        "disruption_type": c.disruption_type,
        "city":            c.city,
        "platform":        c.platform,
        "incident_date":   str(c.incident_date),
        "incident_time":   str(c.incident_time) if c.incident_time else None,
        "expected":        float(c.expected_earnings),
        "actual":          float(c.actual_earnings),
        "loss":            float(c.estimated_loss),
        "payout":          float(c.payout_amount),
        "payout_amount":   float(c.payout_amount),   # alias for frontend compat
        "claimant_email":  c.claimant.email,         # ← NEW: needed by insurer table
        "ai_confidence":   c.ai_confidence,
        "ai_reasoning":    c.ai_reasoning,
        "ai_approved":     c.ai_approved,
        "review_note":     c.review_note,
        "reviewed_at":     c.reviewed_at.isoformat() if c.reviewed_at else None,
        "created_at":      c.created_at.isoformat(),
        "weather": {
            "temp":      c.weather_log.temperature_c,
            "rain_mm":   c.weather_log.rainfall_mm,
            "wind_kph":  c.weather_log.wind_speed_kph,
            "condition": c.weather_log.condition_text,
            "ml_score":  c.weather_log.ml_risk_score,
        } if c.weather_log else None,
    }


# ══════════════════════════════════════════════════════════════
# INSURER DASHBOARD APIs
# ══════════════════════════════════════════════════════════════

@require_http_methods(["GET"])
def insurer_claims(request):
    """Insurer: list all claims with optional filters."""
    err = _require_insurer(request)
    if err:
        return err
 
    from .models import Claim
    qs = Claim.objects.all().select_related("claimant", "weather_log", "policy")
 
    status = request.GET.get("status")
    source = request.GET.get("source")
    city   = request.GET.get("city")
 
    if status: qs = qs.filter(status=status)
    if source: qs = qs.filter(source=source)
    if city:   qs = qs.filter(city__icontains=city)
 
    claims = [_claim_dict(c) for c in qs[:200]]
    return JsonResponse({"claims": claims, "total": qs.count()})


@csrf_exempt
@require_http_methods(["POST"])
def review_claim(request, claim_id):
    """Insurer: approve or reject a claim."""
    err = _require_insurer(request)
    if err:
        return err

    from .models import Claim, Notification
    try:
        data   = json.loads(request.body)
        claim  = Claim.objects.get(id=claim_id)
        action = data.get("action")  # 'approve' or 'reject'
        note   = data.get("note", "")

        if action not in ("approve", "reject"):
            return JsonResponse({"error": "Invalid action."}, status=400)

        claim.status      = Claim.STATUS_APPROVED if action == "approve" else Claim.STATUS_REJECTED
        claim.review_note = note
        claim.reviewed_by = request.user
        claim.reviewed_at = timezone.now()
        claim.save()

        # In-app notification for beneficiary
        notif_type = (Notification.TYPE_CLAIM_APPROVED if action == "approve"
                      else Notification.TYPE_CLAIM_REJECTED)
        Notification.objects.create(
            recipient=claim.claimant,
            notif_type=notif_type,
            title=f"Claim {claim.claim_id} {claim.status}",
            body=(
                f"Your claim has been {claim.status}. "
                + (f"Payout of ₹{claim.payout_amount} will be transferred shortly." if action == "approve"
                   else f"Reason: {note or 'No note provided.'}") 
            ),
            claim=claim,
        )

        return JsonResponse({"success": True, "status": claim.status})
    except Claim.DoesNotExist:
        return JsonResponse({"error": "Claim not found."}, status=404)


@require_http_methods(["GET"])
def insurer_analytics(request):
    """Insurer: summary analytics for the dashboard."""
    err = _require_insurer(request)
    if err:
        return err

    from .models import Claim, WeatherLog

    total       = Claim.objects.count()
    pending     = Claim.objects.filter(status="pending").count()
    approved    = Claim.objects.filter(status="approved").count()
    rejected    = Claim.objects.filter(status="rejected").count()
    auto_claims = Claim.objects.filter(source="auto").count()
    manual      = total - auto_claims

    total_payout = Claim.objects.filter(status="approved").aggregate(
        s=Sum("payout_amount")
    )["s"] or 0

    # Last 7 days
    week_ago = date.today() - timedelta(days=7)
    recent   = Claim.objects.filter(created_at__date__gte=week_ago).count()

    # City breakdown
    city_breakdown = list(
        Claim.objects.values("city")
        .annotate(count=Count("id"))
        .order_by("-count")[:10]
    )

    # Weather disruption logs last 24h
    yesterday = timezone.now() - timedelta(hours=24)
    disruptions = WeatherLog.objects.filter(
        is_disruption=True, recorded_at__gte=yesterday
    ).count()

    return JsonResponse({
        "total":         total,
        "pending":       pending,
        "approved":      approved,
        "rejected":      rejected,
        "auto_claims":   auto_claims,
        "manual_claims": manual,
        "total_payout":  float(total_payout),
        "recent_7d":     recent,
        "disruptions_24h": disruptions,
        "city_breakdown": city_breakdown,
    })


# ══════════════════════════════════════════════════════════════
# POLICY CRUD (Insurer)
# ══════════════════════════════════════════════════════════════

@require_http_methods(["GET"])
def list_policies(request):
    err = _require_insurer(request)
    if err:
        return err
    from .models import Policy
    policies = Policy.objects.filter(insurer=request.user)
    return JsonResponse({"policies": [_policy_dict(p) for p in policies]})


@csrf_exempt
@require_http_methods(["POST"])
def create_policy(request):
    err = _require_insurer(request)
    if err:
        return err
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    from .models import Policy
    policy = Policy.objects.create(
        name=data.get("name", "New Policy"),
        description=data.get("description", ""),
        insurer=request.user,
        max_payout_per_claim=data.get("max_payout", 1200),
        payout_percentage=data.get("payout_pct", 80),
        max_claims_per_month=data.get("max_claims_month", 5),
        monthly_premium=data.get("premium", 129),
        rainfall_threshold_mm=data.get("rainfall_threshold", 5.0),
        wind_speed_threshold_kph=data.get("wind_threshold", 50.0),
        temperature_min_threshold_c=data.get("temp_min_threshold", 5.0),
        temperature_max_threshold_c=data.get("temp_max_threshold", 45.0),
        ml_claim_probability_threshold=data.get("ml_threshold", 0.65),
    )
    return JsonResponse({"success": True, "policy": _policy_dict(policy)})


@csrf_exempt
@require_http_methods(["POST"])
def update_policy(request, policy_id):
    err = _require_insurer(request)
    if err:
        return err
    try:
        data   = json.loads(request.body)
        from .models import Policy
        policy = Policy.objects.get(id=policy_id, insurer=request.user)
        for field, model_field in {
            "name":               "name",
            "description":        "description",
            "max_payout":         "max_payout_per_claim",
            "payout_pct":         "payout_percentage",
            "max_claims_month":   "max_claims_per_month",
            "premium":            "monthly_premium",
            "rainfall_threshold": "rainfall_threshold_mm",
            "wind_threshold":     "wind_speed_threshold_kph",
            "temp_min_threshold": "temperature_min_threshold_c",
            "temp_max_threshold": "temperature_max_threshold_c",
            "ml_threshold":       "ml_claim_probability_threshold",
        }.items():
            if field in data:
                setattr(policy, model_field, data[field])
        policy.save()
        return JsonResponse({"success": True, "policy": _policy_dict(policy)})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def delete_policy(request, policy_id):
    err = _require_insurer(request)
    if err:
        return err
    from .models import Policy
    try:
        policy = Policy.objects.get(id=policy_id, insurer=request.user)
        policy.delete()
        return JsonResponse({"success": True})
    except Policy.DoesNotExist:
        return JsonResponse({"error": "Not found."}, status=404)


def _policy_dict(p):
    return {
        "id":                p.id,
        "name":              p.name,
        "description":       p.description,
        "max_payout":        float(p.max_payout_per_claim),
        "payout_pct":        float(p.payout_percentage),
        "premium":           float(p.monthly_premium),
        "max_claims_month":  p.max_claims_per_month,
        "rainfall_threshold": p.rainfall_threshold_mm,
        "wind_threshold":    p.wind_speed_threshold_kph,
        "temp_min":          p.temperature_min_threshold_c,
        "temp_max":          p.temperature_max_threshold_c,
        "ml_threshold":      p.ml_claim_probability_threshold,
        "is_active":         p.is_active,
        "beneficiary_count": p.beneficiaries.count(),
        "created_at":        p.created_at.isoformat(),
    }


# ══════════════════════════════════════════════════════════════
# ML RISK SCORE API
# ══════════════════════════════════════════════════════════════

@csrf_exempt
@require_http_methods(["POST"])
def ml_risk_score(request):
    """
    POST body: { rainfall_mm, wind_speed_kph, temperature_c, humidity_pct, condition_code }
    Returns:   { score: float, risk_level: 'low'|'medium'|'high', explanation: str }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    from .ml_model import predict_claim_probability, get_model_metadata

    score = predict_claim_probability(data)
    risk  = "high" if score >= 0.70 else ("medium" if score >= 0.40 else "low")

    # Build explanation
    rain  = data.get("rainfall_mm", 0)
    wind  = data.get("wind_speed_kph", 0)
    temp  = data.get("temperature_c", 28)
    parts = []
    if rain > 5:   parts.append(f"heavy rain ({rain} mm)")
    if wind > 40:  parts.append(f"strong winds ({wind} km/h)")
    if temp > 43:  parts.append(f"extreme heat ({temp}°C)")
    if temp < 7:   parts.append(f"extreme cold ({temp}°C)")

    explanation = (
        f"Disruption factors detected: {', '.join(parts)}." if parts
        else "No major disruption factors detected."
    )

    return JsonResponse({
        "score":       score,
        "risk_level":  risk,
        "explanation": explanation,
        "model_meta":  get_model_metadata(),
    })


# ══════════════════════════════════════════════════════════════
# AI ASSISTANT  (calls Anthropic via server-side proxy)
# ══════════════════════════════════════════════════════════════

@csrf_exempt
@require_http_methods(["POST"])
def ai_assistant(request):
    """
    POST body: { message: str, context?: { claim_id?, city?, weather_data? } }
    Returns: { reply: str }

    Calls Anthropic Claude to:
    - Explain why a claim was triggered
    - Answer policy questions
    - Suggest risk mitigation advice
    """
    import requests as http

    try:
        data    = json.loads(request.body)
        message = data.get("message", "")
        context = data.get("context", {})
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    # Build context string
    ctx_str = ""
    if context.get("claim_id"):
        from .models import Claim
        try:
            claim = Claim.objects.get(claim_id=context["claim_id"])
            ctx_str = f"""
Claim context:
- Claim ID: {claim.claim_id}
- Status: {claim.status}
- Disruption type: {claim.disruption_type}
- City: {claim.city}
- Payout: ₹{claim.payout_amount}
- AI reasoning: {claim.ai_reasoning}
"""
        except Claim.DoesNotExist:
            pass

    if context.get("weather_data"):
        w = context["weather_data"]
        ctx_str += f"""
Weather data:
- Temperature: {w.get('temp_c')}°C
- Rainfall: {w.get('precip_mm')} mm
- Wind: {w.get('wind_kph')} km/h
- Condition: {w.get('condition_text')}
"""

    system_prompt = """You are GigSure's AI assistant — a helpful, concise insurance advisor for gig workers in India.
You help with:
1. Explaining why a claim was automatically triggered
2. Answering questions about GigSure policies and coverage
3. Providing practical risk mitigation advice (e.g., "Heavy rain expected tomorrow — consider working morning shift")
4. Explaining claim status and next steps

Keep responses brief (2–4 sentences max), practical, and empathetic.
Always refer to amounts in Indian Rupees (₹).
Do not make up specific policy numbers — use general guidance."""

    anthropic_api_key = getattr(settings, 'ANTHROPIC_API_KEY', '')

    if not anthropic_api_key:
        # Fallback: rule-based assistant
        return _rule_based_ai_response(message, context)

    try:
        resp = http.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key":         anthropic_api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type":      "application/json",
            },
            json={
                "model":      "claude-sonnet-4-20250514",
                "max_tokens": 300,
                "system":     system_prompt,
                "messages": [{
                    "role":    "user",
                    "content": (ctx_str + "\n\n" + message).strip(),
                }],
            },
            timeout=15,
        )
        if resp.status_code == 200:
            reply = resp.json()["content"][0]["text"]
            return JsonResponse({"reply": reply})
        else:
            return _rule_based_ai_response(message, context)
    except Exception:
        return _rule_based_ai_response(message, context)


def _rule_based_ai_response(message: str, context: dict) -> JsonResponse:
    """Fallback AI responses when Anthropic API is unavailable."""
    msg = message.lower()
    if "why" in msg and ("claim" in msg or "trigger" in msg):
        reply = ("Your claim was automatically triggered because extreme weather conditions "
                 "were detected in your area that exceeded your policy's disruption thresholds. "
                 "The system uses live weather data and our ML model to verify the event.")
    elif "rain" in msg or "weather" in msg:
        reply = ("Heavy rainfall can significantly reduce delivery demand. "
                 "If rainfall exceeds 5mm or wind speed exceeds 50km/h, your GigSure policy "
                 "may automatically file a claim on your behalf.")
    elif "payout" in msg or "money" in msg or "payment" in msg:
        reply = ("Payouts are calculated as 80% of your estimated daily income loss. "
                 "Approved claims are processed within 60 seconds via UPI transfer.")
    elif "policy" in msg or "coverage" in msg:
        reply = ("Your GigSure policy covers income disruptions from heavy rain, storms, "
                 "shutdowns, and platform outages. Coverage limits depend on your selected plan.")
    elif "tomorrow" in msg or "forecast" in msg or "precaution" in msg:
        reply = ("Check the Weather module for your zone's disruption risk. "
                 "If high risk is forecasted, consider working an early morning shift before "
                 "conditions worsen, and ensure your GigSure coverage is active.")
    else:
        reply = ("I'm here to help with your GigSure claims and coverage questions. "
                 "You can ask me why a claim was triggered, how payouts work, "
                 "or what to do before extreme weather.")
    return JsonResponse({"reply": reply})


# ══════════════════════════════════════════════════════════════
# NOTIFICATIONS API
# ══════════════════════════════════════════════════════════════

@require_http_methods(["GET"])
def my_notifications(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Login required."}, status=401)
    from .models import Notification
    notifs = Notification.objects.filter(recipient=request.user)[:20]
    return JsonResponse({
        "notifications": [{
            "id":          n.id,
            "type":        n.notif_type,
            "title":       n.title,
            "body":        n.body,
            "is_read":     n.is_read,
            "claim_id":    n.claim.claim_id if n.claim else None,
            "created_at":  n.created_at.isoformat(),
        } for n in notifs],
        "unread_count": Notification.objects.filter(recipient=request.user, is_read=False).count(),
    })


@csrf_exempt
@require_http_methods(["POST"])
def mark_notifications_read(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Login required."}, status=401)
    from .models import Notification
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return JsonResponse({"success": True})


# ══════════════════════════════════════════════════════════════
# MANUAL TRIGGER (for testing auto-claim in dev)
# ══════════════════════════════════════════════════════════════

@csrf_exempt
@require_http_methods(["POST"])
def trigger_monitor(request):
    """Dev endpoint: manually run one monitor pass. Insurer only."""
    err = _require_insurer(request)
    if err:
        return err
    try:
        from .weather_monitor import run_monitor_once
        run_monitor_once()
        return JsonResponse({"success": True, "message": "Monitor pass complete."})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})