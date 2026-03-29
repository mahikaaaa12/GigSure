from django.http import JsonResponse
from django.shortcuts import render
from django.urls.resolvers import settings
from django.views.decorators.csrf import csrf_exempt

import sqlite3
import hashlib
import hmac
import secrets
import json
from datetime import datetime, timedelta
import os

DATABASE = os.path.join(settings.BASE_DIR, "db.sqlite3")

# ─── DB Helper ─────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT,
            last_name TEXT,
            email TEXT UNIQUE,
            password_hash TEXT,
            role TEXT,
            company TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER,
            expires_at TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

# ─── Helpers ───────────────────────────────────────

def hash_password(password):
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 260000)
    return f"{salt}${h.hex()}"

def verify_password(password, stored):
    try:
        salt, h = stored.split("$")
        new_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 260000)
        return hmac.compare_digest(new_hash.hex(), h)
    except:
        return False

def create_session(conn, user_id):
    token = secrets.token_urlsafe(32)
    expires = datetime.utcnow() + timedelta(days=7)

    conn.execute(
        "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
        (token, user_id, expires)
    )
    conn.commit()
    return token

def serialize_user(user):
    if not user:
        return {}
    d = dict(user)
    d.pop("password_hash", None)
    return d

# ─── Views ─────────────────────────────────────────

def home(request):
    return render(request, "login.html")

def dashboard(request):
    return render(request, 'index.html')

@csrf_exempt
def signup(request):
    if request.method != "POST":
        return JsonResponse({"success": False}, status=405)

    data = json.loads(request.body)

    conn = get_db()

    email = data.get("email")
    password = data.get("password")

    existing = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    if existing:
        return JsonResponse({"success": False, "error": "Email exists"}, status=400)

    pw_hash = hash_password(password)

    cursor = conn.execute(
        "INSERT INTO users (email, password_hash) VALUES (?, ?)",
        (email, pw_hash)
    )
    conn.commit()

    token = create_session(conn, cursor.lastrowid)

    return JsonResponse({"success": True, "token": token})

@csrf_exempt
def login(request):
    if request.method != "POST":
        return JsonResponse({"success": False}, status=405)

    data = json.loads(request.body)

    conn = get_db()

    email = data.get("email")
    password = data.get("password")

    user = conn.execute(
        "SELECT * FROM users WHERE email=?", (email,)
    ).fetchone()

    if not user or not verify_password(password, user["password_hash"]):
        return JsonResponse({"success": False, "error": "Invalid credentials"}, status=401)

    token = create_session(conn, user["id"])

    return JsonResponse({
        "success": True,
        "token": token,
        "user": serialize_user(user)
    })

def me(request):
    return JsonResponse({"message": "Auth check later"})

def logout(request):
    return JsonResponse({"success": True})