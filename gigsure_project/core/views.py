from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
import json


# ── Page views ──────────────────────────────────────────────────────────────

def home(request):
    return render(request, "login.html")


def dashboard(request):
    return render(request, "index.html")


def claim_page(request):
    return render(request, "claim.html")


def weather_page(request):
    return render(request, "weather.html")


# ── Helper: build user dict for JSON responses ───────────────────────────────

def _user_dict(user, role=None):
    """
    Build a serialisable user dict.
    Role is stored in the session (request.session['role']) so it survives
    across page loads without needing a separate Profile model.
    """
    return {
        "id":         user.id,
        "email":      user.email,
        "first_name": user.first_name,
        "last_name":  user.last_name,
        "role":       role or "beneficiary",
        "created_at": user.date_joined.isoformat() if user.date_joined else None,
        "last_login": user.last_login.isoformat() if user.last_login else None,
    }


# ── API: Signup ──────────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def signup(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "errors": {"general": "Invalid JSON body."}}, status=400)

    email      = (data.get("email") or "").strip()
    password   = data.get("password", "")
    first_name = (data.get("first_name") or "").strip()
    last_name  = (data.get("last_name") or "").strip()
    role       = data.get("role", "beneficiary")
    company    = (data.get("company") or "").strip()

    errors = {}
    if not first_name:
        errors["first_name"] = "First name is required."
    if not last_name:
        errors["last_name"] = "Last name is required."
    if not email:
        errors["email"] = "Email is required."
    if not password or len(password) < 6:
        errors["password"] = "Password must be at least 6 characters."
    if role not in ("insurer", "beneficiary"):
        errors["role"] = "Invalid role selected."
    if errors:
        return JsonResponse({"success": False, "errors": errors}, status=400)

    if User.objects.filter(username=email).exists():
        return JsonResponse(
            {"success": False, "errors": {"email": "An account with this email already exists."}},
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


# ── API: Login ───────────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def login(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "errors": {"general": "Invalid JSON body."}}, status=400)

    email    = (data.get("email") or "").strip()
    password = data.get("password", "")
    role     = data.get("role", "beneficiary")

    if not email or not password:
        return JsonResponse(
            {"success": False, "errors": {"general": "Please fill in all fields."}}, status=400,
        )

    user = authenticate(request, username=email, password=password)
    if user is None:
        return JsonResponse(
            {"success": False, "errors": {"general": "Incorrect email or password."}}, status=401,
        )

    auth_login(request, user)
    request.session["role"] = role

    return JsonResponse({"success": True, "user": _user_dict(user, role=role)})


# ── API: Me (session check) ──────────────────────────────────────────────────

def me(request):
    if request.user.is_authenticated:
        role = request.session.get("role", "beneficiary")
        return JsonResponse({"user": _user_dict(request.user, role=role)})
    return JsonResponse({"user": None})


# ── API: Logout ──────────────────────────────────────────────────────────────

@csrf_exempt
def logout(request):
    auth_logout(request)
    return JsonResponse({"success": True})

from django.http import JsonResponse
from .utils.weather import get_weather

def weather_api(request):
    city = "Vadodara"   # you can make this dynamic later
    data = get_weather(city)

    return JsonResponse({
        "success": True,
        "data": data
    })