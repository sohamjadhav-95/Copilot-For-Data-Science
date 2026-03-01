# routes/auth_routes.py — Authentication endpoints (JSON only)
import os
import bcrypt
from datetime import datetime, timezone, timedelta
from functools import wraps

import jwt
from flask import Blueprint, request, jsonify

from config import SECRET_KEY, UPLOAD_FOLDER, JWT_EXPIRY_HOURS
from database import db
from database.models import User, Activity
from logger import log_app_event

auth_bp = Blueprint("auth", __name__)


# ═══════════════════════════════════════════════════════════════════════
# AUTH HELPERS
# ═══════════════════════════════════════════════════════════════════════

def _make_token(user):
    return jwt.encode(
        {"user_id": user.id, "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS)},
        SECRET_KEY, algorithm="HS256",
    )


def _log_activity(user_id, action, details=None):
    db.session.add(Activity(user_id=user_id, action=action, details=details))
    db.session.commit()


def login_required(f):
    """Support both Authorization: Bearer <token> header and cookie-based auth."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        # 1. Check Authorization header (React frontend)
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]

        # 2. Fallback to cookie
        if not token:
            token = request.cookies.get("token")

        if not token:
            return jsonify({"error": "Not authenticated"}), 401

        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            user = db.session.get(User, data["user_id"])
            if not user:
                raise ValueError("User not found")
            request.current_user = user
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except Exception:
            return jsonify({"error": "Invalid token"}), 401

        return f(*args, **kwargs)
    return decorated


# ═══════════════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════════════

@auth_bp.route("/api/register", methods=["POST"])
def api_register():
    data = request.get_json()
    username = data.get("username", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not username or not email or not password:
        return jsonify({"error": "All fields are required"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400
    if User.query.filter((User.username == username) | (User.email == email)).first():
        return jsonify({"error": "Username or email already exists"}), 409

    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    user = User(username=username, email=email, password_hash=pw_hash)
    db.session.add(user)
    db.session.commit()

    os.makedirs(os.path.join(UPLOAD_FOLDER, str(user.id)), exist_ok=True)

    _log_activity(user.id, "register", f"Registered as {username}")
    log_app_event("register", f"New user: {username}")
    token = _make_token(user)
    return jsonify({"message": "Registration successful", "user": user.to_dict(), "token": token}), 201


@auth_bp.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json()
    login_id = data.get("login_id", "").strip()
    password = data.get("password", "")

    user = User.query.filter((User.username == login_id) | (User.email == login_id.lower())).first()
    if not user or not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
        return jsonify({"error": "Invalid credentials"}), 401

    _log_activity(user.id, "login")
    log_app_event("login", f"User: {user.username}")
    token = _make_token(user)
    return jsonify({"message": "Login successful", "user": user.to_dict(), "token": token})


@auth_bp.route("/api/logout", methods=["POST"])
def api_logout():
    return jsonify({"message": "Logged out"})


@auth_bp.route("/api/me")
@login_required
def api_me():
    return jsonify({"user": request.current_user.to_dict()})
