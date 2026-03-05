# app.py — Flask backend: Authentication, API routes, Chat processing
# v4.5: Pro Mode extension — Normal + Pro dual-mode with DAG execution engine
import os, io, shutil, base64, json
from datetime import datetime, timezone, timedelta
from functools import wraps

import jwt
import bcrypt
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from flask import (
    Flask, request, jsonify, render_template,
    redirect, url_for, session, make_response, send_from_directory,
)
from config import (
    SECRET_KEY, SQLALCHEMY_DATABASE_URI, SQLALCHEMY_TRACK_MODIFICATIONS,
    UPLOAD_FOLDER, MODIFIED_FOLDER, MAX_CONTENT_LENGTH, JWT_EXPIRY_HOURS,
)
from database import db
from database.models import User, ChatSession, Message, Activity, CodeSnippet
from engines import (
    classify_intent, build_data_context, resolve_query,
    generate_display_code, generate_chart_code, generate_modify_code,
    generate_chat_response, generate_result_summary,
    fix_code, extract_code, _safe_exec,
    set_high_tier,
)
from api_config import get_active_provider, switch_provider, PROVIDERS
from logger import (
    log_error, log_interaction, log_app_event, app_logger,
    log_security_event, log_performance, log_frontend_event,
    log_workflow_execution, security_logger,
)
from engines_pro.pro_engine import pro_engine
from core.plan_access import has_access, get_upload_limit, get_plan_limits


# ═══════════════════════════════════════════════════════════════════════
# APP FACTORY
# ═══════════════════════════════════════════════════════════════════════

def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = SECRET_KEY
    app.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = SQLALCHEMY_TRACK_MODIFICATIONS
    app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
    app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

    db.init_app(app)

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(MODIFIED_FOLDER, exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(__file__), "database"), exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(__file__), "logs_and_debug"), exist_ok=True)

    with app.app_context():
        db.create_all()

    log_app_event("startup", f"App created, provider={get_active_provider()}")
    register_routes(app)

    # ── Performance timing middleware (universal — covers all routes) ────────
    import time as _time

    @app.before_request
    def _before():
        request._start_time = _time.perf_counter()

    @app.after_request
    def _after(response):
        try:
            elapsed_ms = (_time.perf_counter() - getattr(request, "_start_time", 0)) * 1000
            # Skip static assets to keep logs clean
            if not request.path.startswith("/static"):
                log_performance(
                    endpoint=request.path,
                    method=request.method,
                    http_status=response.status_code,
                    response_ms=elapsed_ms,
                    session_id=str(session.get("session_id", "")),
                )
        except Exception:
            pass
        return response

    return app


# ═══════════════════════════════════════════════════════════════════════
# AUTH DECORATOR
# ═══════════════════════════════════════════════════════════════════════

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get("token")
        if not token:
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"error": "Not authenticated"}), 401
            return redirect(url_for("login_page"))
        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            user = db.session.get(User, data["user_id"])
            if not user:
                raise ValueError("User not found")
            request.current_user = user
        except Exception:
            resp = redirect(url_for("login_page"))
            resp.delete_cookie("token")
            return resp
        return f(*args, **kwargs)
    return decorated


def _make_token(user):
    return jwt.encode(
        {"user_id": user.id, "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS)},
        SECRET_KEY, algorithm="HS256")


def _log_activity(user_id, action, details=None):
    db.session.add(Activity(user_id=user_id, action=action, details=details))
    db.session.commit()


# ═══════════════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════════════

def register_routes(app):

    # ── Page routes ───────────────────────────────────────────────────

    @app.route("/")
    def index():
        token = request.cookies.get("token")
        if token:
            try:
                jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
                return redirect(url_for("dashboard_page"))
            except Exception:
                pass
        return redirect(url_for("login_page"))

    @app.route("/login")
    def login_page():
        return render_template("login.html")

    @app.route("/register")
    def register_page():
        return render_template("register.html")

    @app.route("/dashboard")
    @login_required
    def dashboard_page():
        return render_template("dashboard.html", user=request.current_user, active_page="dashboard")

    @app.route("/quick-run")
    @login_required
    def quick_run_page():
        return render_template("quick_run.html", user=request.current_user, active_page="quick-run")

    @app.route("/workflow")
    @login_required
    def workflow_page():
        return render_template("workflow.html", user=request.current_user, active_page="workflow")

    @app.route("/datasets")
    @login_required
    def datasets_page():
        return render_template("datasets.html", user=request.current_user, active_page="datasets")

    @app.route("/sessions")
    @login_required
    def sessions_page():
        return render_template("sessions.html", user=request.current_user, active_page="sessions")

    @app.route("/models")
    @login_required
    def models_page():
        return render_template("models.html", user=request.current_user, active_page="models")

    @app.route("/monitoring")
    @login_required
    def monitoring_page():
        return render_template("monitoring.html", user=request.current_user, active_page="monitoring")

    @app.route("/settings")
    @login_required
    def settings_page():
        return render_template("settings.html", user=request.current_user, active_page="settings")

    # ── Monitoring API ────────────────────────────────────────────────

    @app.route("/api/monitoring")
    @login_required
    def api_monitoring():
        """Return real-time monitoring data for the current user."""
        from datetime import datetime, timezone, timedelta
        from sqlalchemy import func
        uid = request.current_user.id
        plan = request.current_user.plan or "free"

        # ── Usage metrics ──
        total_sessions = ChatSession.query.filter_by(user_id=uid).count()
        total_queries = Message.query.join(ChatSession).filter(
            ChatSession.user_id == uid, Message.role == "user"
        ).count()
        total_responses = Message.query.join(ChatSession).filter(
            ChatSession.user_id == uid, Message.role == "assistant"
        ).count()
        total_datasets = ChatSession.query.filter(
            ChatSession.user_id == uid, ChatSession.filename.isnot(None)
        ).with_entities(func.count(func.distinct(ChatSession.filename))).scalar()
        total_charts = Message.query.join(ChatSession).filter(
            ChatSession.user_id == uid,
            Message.result_type.in_(["chart", "image"]),
        ).count()
        total_snippets = CodeSnippet.query.filter_by(user_id=uid).count()

        # ── Workflow stats from Activity logs ──
        wf_total = Activity.query.filter_by(user_id=uid, action="workflow_execute").count()
        wf_success = Activity.query.filter(
            Activity.user_id == uid,
            Activity.action == "workflow_execute",
            Activity.details.like("%success%"),
        ).count()
        wf_failed = wf_total - wf_success

        # ── Model usage (approximate from activities) ──
        coding_calls = Activity.query.filter(
            Activity.user_id == uid,
            Activity.action.in_(["display", "visualize", "modify"]),
        ).count()
        reasoning_calls = Activity.query.filter(
            Activity.user_id == uid,
            Activity.action.in_(["workflow_execute", "workflow_plan"]),
        ).count()
        intent_calls = total_queries  # each user query triggers intent classification

        # ── Recent activities (last 20) ──
        activities = Activity.query.filter_by(user_id=uid).order_by(
            Activity.created_at.desc()
        ).limit(20).all()

        # ── Credits used (approximate: total API calls) ──
        credits_used = total_queries + total_responses + coding_calls + reasoning_calls

        # ── System health ──
        try:
            provider = get_active_provider()
            ai_status = "connected"
        except Exception:
            provider = "unknown"
            ai_status = "error"

        return jsonify({
            "plan": plan,
            "limits": get_plan_limits(plan),
            "metrics": {
                "datasets": total_datasets,
                "sessions": total_sessions,
                "queries": total_queries,
                "charts_generated": total_charts,
                "code_snippets": total_snippets,
                "credits_used": credits_used,
            },
            "model_usage": {
                "coding": coding_calls,
                "reasoning": reasoning_calls,
                "intent": intent_calls,
            },
            "workflow_stats": {
                "total": wf_total,
                "success": wf_success,
                "failed": wf_failed,
            },
            "activities": [
                {
                    "time": a.created_at.strftime("%Y-%m-%d %H:%M") if a.created_at else "",
                    "action": a.action,
                    "details": a.details or "",
                }
                for a in activities
            ],
            "health": {
                "flask": "running",
                "database": "operational",
                "ai_provider": provider,
                "ai_status": ai_status,
            },
        })

    # ── Frontend Logging API ──────────────────────────────────────────
    # Accepts log events from the browser JS logger (logger.js).
    # No auth required — errors may happen before login completes.

    @app.route("/api/log/frontend", methods=["POST"])
    def api_log_frontend():
        try:
            d = request.get_json(force=True, silent=True) or {}
            log_frontend_event(
                event_type  = str(d.get("event_type", "unknown"))[:50],
                page        = str(d.get("page", "unknown"))[:100],
                component   = str(d.get("component", ""))[:80] or None,
                message     = str(d.get("message", ""))[:500] or None,
                level       = str(d.get("level", "info"))[:10],
                browser     = str(d.get("browser", ""))[:120] or None,
                viewport    = str(d.get("viewport", ""))[:30]  or None,
                user_id     = str(d.get("user_id", ""))[:20]   or None,
                session_id  = str(d.get("session_id", ""))[:40] or None,
                stack_trace = str(d.get("stack_trace", ""))[:1000] or None,
            )
        except Exception as e:
            app_logger.warning(f"[frontend-log] failed to parse: {e}")
        return jsonify({"ok": True}), 200

    # ── Auth API ──────────────────────────────────────────────────────


    @app.route("/api/register", methods=["POST"])
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
        resp = jsonify({"message": "Registration successful", "user": user.to_dict()})
        resp.set_cookie("token", token, httponly=True, max_age=JWT_EXPIRY_HOURS * 3600, samesite="Lax")
        return resp, 201

    @app.route("/api/login", methods=["POST"])
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
        resp = jsonify({"message": "Login successful", "user": user.to_dict()})
        resp.set_cookie("token", token, httponly=True, max_age=JWT_EXPIRY_HOURS * 3600, samesite="Lax")
        return resp

    @app.route("/api/logout", methods=["POST"])
    def api_logout():
        resp = jsonify({"message": "Logged out"})
        resp.delete_cookie("token")
        return resp

    @app.route("/api/me")
    @login_required
    def api_me():
        return jsonify({"user": request.current_user.to_dict()})

    # ── Plan Activation API ────────────────────────────────────────────

    @app.route("/api/activate-plan", methods=["POST"])
    @login_required
    def api_activate_plan():
        data = request.get_json()
        token = (data.get("token") or "").strip()
        if not token:
            return jsonify({"success": False, "message": "Token is required"}), 400

        tokens_path = os.path.join(os.path.dirname(__file__), "database", "plan_tokens.txt")
        if not os.path.exists(tokens_path):
            return jsonify({"success": False, "message": "Invalid token"}), 400

        with open(tokens_path, "r") as fh:
            lines = [line.strip() for line in fh.readlines() if line.strip()]

        matched_plan = None
        remaining = []
        for line in lines:
            if ":" not in line:
                remaining.append(line)
                continue
            plan_part, token_part = line.split(":", 1)
            if token_part == token and matched_plan is None:
                matched_plan = plan_part.lower()
            else:
                remaining.append(line)

        if not matched_plan:
            return jsonify({"success": False, "message": "Invalid token"}), 400

        user = request.current_user
        user.plan = matched_plan
        user.plan_token = token
        db.session.commit()

        with open(tokens_path, "w") as fh:
            fh.write("\n".join(remaining) + "\n" if remaining else "")

        log_app_event("plan_activate", f"User {user.username} activated {matched_plan} plan")
        return jsonify({"success": True, "plan": matched_plan})

    # ── File Upload ───────────────────────────────────────────────────

    @app.route("/api/upload", methods=["POST"])
    @login_required
    def api_upload():
        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400
        f = request.files["file"]
        if not f.filename.endswith(".csv"):
            return jsonify({"error": "Only CSV files are supported"}), 400

        # Plan-based upload size limit
        f.seek(0, 2)
        file_size = f.tell()
        f.seek(0)
        max_size = get_upload_limit(request.current_user.plan or "free")
        if file_size > max_size:
            limit_mb = max_size // (1024 * 1024)
            return jsonify({"error": f"File exceeds your plan limit of {limit_mb} MB. Upgrade your plan for larger uploads."}), 413

        user_dir = os.path.join(UPLOAD_FOLDER, str(request.current_user.id))
        os.makedirs(user_dir, exist_ok=True)
        path = os.path.join(user_dir, f.filename)
        f.save(path)

        try:
            df = pd.read_csv(path)
        except Exception as e:
            log_error(e, context=f"Failed to parse uploaded CSV: {f.filename}")
            try:
                os.remove(path)
            except OSError:
                pass
            return jsonify({"error": f"Could not parse CSV file: {str(e)}. Please check the file format."}), 400

        sess = ChatSession(
            user_id=request.current_user.id,
            filename=f.filename,
            file_path=path,
            title=f"Chat: {f.filename}",
        )
        db.session.add(sess)
        db.session.commit()
        _log_activity(request.current_user.id, "upload", f"Uploaded {f.filename}")
        log_app_event("upload", f"User {request.current_user.username} uploaded {f.filename} ({df.shape[0]}x{df.shape[1]})")

        info = {
            "filename": f.filename,
            "rows": df.shape[0],
            "columns": df.shape[1],
            "column_names": df.columns.tolist(),
            "dtypes": {c: str(df[c].dtype) for c in df.columns},
            "missing": int(df.isnull().sum().sum()),
            "numeric_count": len(df.select_dtypes(include="number").columns),
            "session_id": sess.id,
        }
        return jsonify({"message": "File uploaded", "dataset": info})

    # ── Sessions ──────────────────────────────────────────────────────

    @app.route("/api/sessions")
    @login_required
    def api_sessions():
        sessions = ChatSession.query.filter_by(user_id=request.current_user.id)\
            .order_by(ChatSession.created_at.desc()).all()
        return jsonify({"sessions": [s.to_dict() for s in sessions]})

    @app.route("/api/sessions/clear", methods=["DELETE"])
    @login_required
    def api_clear_sessions():
        ChatSession.query.filter_by(user_id=request.current_user.id).delete()
        db.session.commit()
        return jsonify({"message": "All sessions cleared"})

    @app.route("/api/change-password", methods=["POST"])
    @login_required
    def api_change_password():
        data = request.get_json()
        old_pw = data.get("old_password", "")
        new_pw = data.get("new_password", "")
        user = request.current_user
        if not bcrypt.checkpw(old_pw.encode(), user.password_hash.encode()):
            return jsonify({"error": "Current password is incorrect"}), 401
        if len(new_pw) < 8:
            return jsonify({"error": "New password must be at least 8 characters"}), 400
        user.password_hash = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()
        db.session.commit()
        return jsonify({"message": "Password updated successfully"})

    @app.route("/api/sessions/<int:session_id>/messages")
    @login_required
    def api_session_messages(session_id):
        sess = ChatSession.query.get_or_404(session_id)
        if sess.user_id != request.current_user.id:
            return jsonify({"error": "Forbidden"}), 403
        msgs = [m.to_dict() for m in sess.messages]
        info = None
        if sess.file_path and os.path.exists(sess.file_path):
            try:
                df = pd.read_csv(sess.file_path)
                info = {
                    "filename": sess.filename,
                    "rows": df.shape[0],
                    "columns": df.shape[1],
                    "column_names": df.columns.tolist(),
                    "dtypes": {c: str(df[c].dtype) for c in df.columns},
                    "missing": int(df.isnull().sum().sum()),
                    "numeric_count": len(df.select_dtypes(include="number").columns),
                    "session_id": sess.id,
                }
            except Exception as e:
                log_error(e, context=f"Failed to read session CSV: {sess.file_path}")
        return jsonify({"messages": msgs, "dataset": info})

    # ── Provider Switching API ────────────────────────────────────────

    @app.route("/api/provider", methods=["GET"])
    @login_required
    def api_get_provider():
        return jsonify({
            "active_provider": get_active_provider(),
            "available_providers": list(PROVIDERS.keys()),
        })

    @app.route("/api/provider", methods=["POST"])
    @login_required
    def api_switch_provider():
        data = request.get_json()
        provider = data.get("provider", "").strip().lower()
        try:
            new_provider = switch_provider(provider)
            log_app_event("provider_switch", f"User {request.current_user.username} switched to {new_provider}")
            return jsonify({
                "message": f"Switched to {new_provider}",
                "active_provider": new_provider,
            })
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    # ── Chat / Process ────────────────────────────────────────────────

    @app.route("/api/chat", methods=["POST"])
    @login_required
    def api_chat():
        data = request.get_json()
        user_input = data.get("message", "").strip()
        session_id = data.get("session_id")

        if not user_input:
            return jsonify({"error": "Empty message"}), 400
        if not session_id:
            return jsonify({"error": "No session selected"}), 400

        sess = ChatSession.query.get_or_404(session_id)
        if sess.user_id != request.current_user.id:
            return jsonify({"error": "Forbidden"}), 403

        user_msg = Message(session_id=session_id, role="user", content=user_input)
        db.session.add(user_msg)
        db.session.commit()

        recent_msgs = Message.query.filter_by(session_id=session_id)\
            .order_by(Message.created_at.desc()).limit(11).all()
        recent_msgs.reverse()
        conversation_history = [
            {"role": m.role, "content": m.content}
            for m in recent_msgs[:-1]
        ]

        file_path = sess.file_path
        if not file_path or not os.path.exists(file_path):
            ai_msg = Message(session_id=session_id, role="assistant",
                             content="No dataset file found. Please upload a CSV first.")
            db.session.add(ai_msg)
            db.session.commit()
            return jsonify({"user_msg": user_msg.to_dict(), "assistant_msg": ai_msg.to_dict()})

        try:
            df = pd.read_csv(file_path)
        except Exception as e:
            log_error(e, context=f"Failed to read CSV during chat: {file_path}")
            ai_msg = Message(session_id=session_id, role="assistant",
                             content="⚠️ Could not read the dataset file. It may be corrupted. Please re-upload.")
            db.session.add(ai_msg)
            db.session.commit()
            return jsonify({"user_msg": user_msg.to_dict(), "assistant_msg": ai_msg.to_dict()})

        info, ctx = build_data_context(df, file_path)

        # AI-driven intent classification
        # High-tier toggle: Ultra users can opt into NVIDIA models for Quick Run
        high_tier = data.get('high_tier', False)
        user_plan = getattr(request.current_user, 'plan', 'free')
        set_high_tier(high_tier and user_plan == 'ultra')
        intent = classify_intent(user_input, conversation_history)
        app_logger.info(f"[CHAT] User: '{user_input}' -> Intent: {intent}")

        # AI-driven query resolution for follow-ups
        resolved_input = resolve_query(user_input, conversation_history, ctx)
        if resolved_input != user_input:
            app_logger.info(f"[RESOLVED] '{user_input}' -> '{resolved_input}'")

        _log_activity(request.current_user.id, intent, user_input)

        try:
            result = _process_intent(intent, resolved_input, df, file_path, ctx, sess, conversation_history, user_id=request.current_user.id)
        except Exception as e:
            log_error(e, context=f"_process_intent failed for intent={intent}, input={user_input}")
            result = {
                "content": "⚠️ Something went wrong while processing your request. "
                           "Please try rephrasing or try a simpler query.",
            }
            log_interaction(user_input, intent, resolved_input, "error", False, str(e))

        ai_msg = Message(
            session_id=session_id,
            role="assistant",
            content=result["content"],
            result_type=result.get("result_type"),
            result_data=result.get("result_data"),
            result_title=result.get("result_title"),
        )
        db.session.add(ai_msg)
        db.session.commit()

        return jsonify({"user_msg": user_msg.to_dict(), "assistant_msg": ai_msg.to_dict()})

    # ── Activity Log ──────────────────────────────────────────────────

    @app.route("/api/activities")
    @login_required
    def api_activities():
        acts = Activity.query.filter_by(user_id=request.current_user.id)\
            .order_by(Activity.created_at.desc()).limit(50).all()
        return jsonify({"activities": [a.to_dict() for a in acts]})

    # ── Code Snippets API ─────────────────────────────────────────────

    @app.route("/api/code-snippets")
    @login_required
    def api_code_snippets():
        snippets = CodeSnippet.query.filter_by(user_id=request.current_user.id)\
            .order_by(CodeSnippet.created_at.desc()).limit(100).all()
        return jsonify({"snippets": [s.to_dict() for s in snippets]})

    @app.route("/api/code-snippets/<int:snippet_id>")
    @login_required
    def api_code_snippet_detail(snippet_id):
        snippet = CodeSnippet.query.get_or_404(snippet_id)
        if snippet.user_id != request.current_user.id:
            return jsonify({"error": "Forbidden"}), 403
        return jsonify({"snippet": snippet.to_dict()})

    # ── Download Modified CSV ─────────────────────────────────────────

    @app.route("/api/download-modified")
    @login_required
    def api_download_modified():
        session_id = request.args.get("session_id", type=int)
        if not session_id:
            return jsonify({"error": "session_id required"}), 400
        sess = ChatSession.query.get_or_404(session_id)
        if sess.user_id != request.current_user.id:
            return jsonify({"error": "Forbidden"}), 403
        fp = sess.file_path
        if not fp or not os.path.exists(fp):
            return jsonify({"error": "File not found"}), 404
        from flask import send_file
        return send_file(fp, as_attachment=True,
                         download_name=f"modified_{os.path.basename(fp)}")

    # ── Pro Mode API ──────────────────────────────────────────────────

    @app.route("/api/pro/plan", methods=["POST"])
    @login_required
    def api_pro_plan():
        """Generate a DAG plan for user approval."""
        if (request.current_user.plan or "free") == "free":
            return jsonify({"error": "Pro Workflow requires a Pro or Ultra plan"}), 403

        data = request.get_json()
        user_input = data.get("message", "").strip()
        session_id = data.get("session_id")
        size_override = data.get("size_override", False)

        if not user_input:
            return jsonify({"error": "Empty message"}), 400
        if not session_id:
            return jsonify({"error": "No session selected"}), 400

        sess = ChatSession.query.get_or_404(session_id)
        if sess.user_id != request.current_user.id:
            return jsonify({"error": "Forbidden"}), 403
        if not sess.file_path or not os.path.exists(sess.file_path):
            return jsonify({"error": "No dataset file found"}), 400

        try:
            df = pd.read_csv(sess.file_path)
        except Exception as e:
            log_error(e, context="Pro plan: CSV read failed")
            return jsonify({"error": f"Could not read dataset: {e}"}), 400

        # Dataset size check
        size_check = pro_engine.check_dataset_size(df)
        if not size_check["within_limits"] and not size_override:
            return jsonify({
                "warning": size_check["warning"],
                "requires_confirmation": True,
                "rows": size_check["rows"],
                "max_rows": size_check["max_rows"],
            }), 200

        # Generate plan (Pro Mode always uses NVIDIA via ModelRouter)
        result = pro_engine.plan(
            user_input=user_input,
            df=df,
            file_path=sess.file_path,
            session_id=session_id,
            user_id=request.current_user.id,
        )

        if not result:
            return jsonify({"error": "Failed to generate plan. Try rephrasing your request."}), 500

        _log_activity(request.current_user.id, "pro_plan", user_input)
        return jsonify(result)

    @app.route("/api/pro/approve", methods=["POST"])
    @login_required
    def api_pro_approve():
        """Approve and start executing a DAG plan in a background thread.
        Returns 202 immediately — client should poll /api/pro/status/<plan_id>.
        """
        if (request.current_user.plan or "free") == "free":
            return jsonify({"error": "Pro Workflow requires a Pro or Ultra plan"}), 403

        import threading as _threading
        data = request.get_json()
        plan_id = data.get("plan_id")

        if not plan_id:
            return jsonify({"error": "plan_id required"}), 400

        # Mark as queued so get_status returns "running" immediately
        from engines_pro.pro_engine import _execution_store
        entry = _execution_store.get(plan_id)
        if entry is None:
            return jsonify({"error": "Plan not found or expired. Please regenerate the plan."}), 404

        plan = entry.get("plan")
        if plan and plan.status not in ("planned", "replanned"):
            return jsonify({"error": f"Plan already executed (status: {plan.status})"}), 400

        # Mark as running before background thread starts
        entry["running"] = True
        entry["result"] = None

        def _run_in_background():
            try:
                result = pro_engine.execute(plan_id)
                entry["running"] = False
                if result is None:
                    entry["exec_error"] = "Execution returned no result"
                elif "error" in result:
                    entry["exec_error"] = result["error"]
                else:
                    entry["exec_error"] = None
                    entry["result"] = result
            except Exception as exc:
                entry["running"] = False
                entry["exec_error"] = str(exc)
                log_error(exc, context=f"Background execution of plan {plan_id}")

        t = _threading.Thread(target=_run_in_background, daemon=True, name=f"pro-exec-{plan_id}")
        t.start()

        _log_activity(request.current_user.id, "pro_execute_start", f"Plan {plan_id}")
        # Return 202 Accepted — client must poll /api/pro/status/<plan_id>
        return jsonify({"status": "running", "plan_id": plan_id, "message": "Execution started. Poll /api/pro/status/<plan_id>"}), 202

    @app.route("/api/pro/status/<plan_id>")
    @login_required
    def api_pro_status(plan_id):
        """Poll execution status for a plan."""
        status = pro_engine.get_status(plan_id)
        if status is None:
            return jsonify({"error": "Plan not found"}), 404
        return jsonify(status)

    @app.route("/api/pro/profile", methods=["POST"])
    @login_required
    def api_pro_profile():
        """Get dataset profile for current session."""
        data = request.get_json()
        session_id = data.get("session_id")

        if not session_id:
            return jsonify({"error": "session_id required"}), 400

        sess = ChatSession.query.get_or_404(session_id)
        if sess.user_id != request.current_user.id:
            return jsonify({"error": "Forbidden"}), 403
        if not sess.file_path or not os.path.exists(sess.file_path):
            return jsonify({"error": "No dataset file"}), 400

        try:
            df = pd.read_csv(sess.file_path)
        except Exception as e:
            return jsonify({"error": f"Could not read dataset: {e}"}), 400

        profile = pro_engine.get_profile(df)
        return jsonify({"profile": profile})

# ═══════════════════════════════════════════════════════════════════════
# CODE SNIPPET SAVING
# ═══════════════════════════════════════════════════════════════════════

def _save_code_snippet(user_id, session_id, user_input, operation, code):
    """Save generated code snippet to CodeSnippet table."""
    if not user_id or not code:
        return
    try:
        # Generate a short label from the user query
        label = user_input[:80].strip()
        if len(user_input) > 80:
            label += "..."
        snippet = CodeSnippet(
            user_id=user_id,
            session_id=session_id,
            label=label,
            operation=operation,
            code=code,
        )
        db.session.add(snippet)
        db.session.commit()
        app_logger.info(f"[CODE] Saved snippet #{snippet.id}: {operation} — {label}")
    except Exception as e:
        app_logger.warning(f"[CODE] Failed to save snippet: {e}")
        db.session.rollback()


# ═══════════════════════════════════════════════════════════════════════
# INTENT PROCESSING — All operations go through AI
# ═══════════════════════════════════════════════════════════════════════

def _process_intent(intent, user_input, df, file_path, ctx, sess, conversation_history=None, user_id=None):
    """Process user intent — fully AI-driven for all operations."""
    history = conversation_history or []
    uid = user_id
    sid = sess.id if sess else None

    if intent == "undo":
        return _handle_undo(file_path, sess)
    elif intent == "display":
        return _handle_display(user_input, df, file_path, ctx, history, user_id=uid, session_id=sid)
    elif intent == "visualize":
        return _handle_visualize(user_input, df, file_path, ctx, history, user_id=uid, session_id=sid)
    elif intent == "modify":
        return _handle_modify(user_input, df, file_path, ctx, history, user_id=uid, session_id=sid)
    else:  # chat
        resp = generate_chat_response(user_input, ctx, history)
        return {"content": resp}


def _handle_undo(file_path, sess):
    backup_dir = os.path.join(MODIFIED_FOLDER, "backups")
    if not os.path.exists(backup_dir):
        return {"content": "⚠️ No changes to undo."}
    backups = sorted([f for f in os.listdir(backup_dir) if f.endswith(".csv")])
    if not backups:
        return {"content": "⚠️ No backups available."}
    latest = os.path.join(backup_dir, backups[-1])
    shutil.copy2(latest, file_path)
    os.remove(latest)
    log_app_event("undo", f"Reverted to {backups[-1]}")
    return {"content": "↩️ Reverted to previous version.", "result_type": "text",
            "result_data": "Successfully undone the last change.", "result_title": "↩️ Undo"}


def _handle_display(user_input, df, file_path, ctx, history=None, user_id=None, session_id=None):
    """AI generates code, executes it safely, returns result."""
    app_logger.info(f"[DISPLAY] AI code generation for: {user_input}")
    raw = generate_display_code(user_input, file_path, ctx, history)
    code = extract_code(raw)
    if not code:
        app_logger.warning(f"[DISPLAY] Code extraction failed")
        log_interaction(user_input, "display", user_input, None, False, "code extraction failed")
        return {"content": "I couldn't generate code for that request. Could you rephrase it?"}

    ns, err = _safe_exec(code, description=f"display: {user_input}")

    # If failed, try fixing the code once
    if err:
        app_logger.warning(f"[DISPLAY] Code exec failed: {err}")
        fixed = fix_code(code, err, file_path, ctx)
        code = extract_code(fixed)
        if code:
            ns, err = _safe_exec(code, description=f"display (fixed): {user_input}")
            if err:
                app_logger.warning(f"[DISPLAY] Fixed code also failed: {err}")

    if err is None and "_result_df" in ns:
        rdf = ns["_result_df"]
        if isinstance(rdf, pd.Series):
            rdf = rdf.to_frame()
        if isinstance(rdf, pd.DataFrame):
            summary = generate_result_summary(user_input, "display")
            log_interaction(user_input, "display", user_input, "dataframe", True)
            # Save code snippet
            _save_code_snippet(user_id, session_id, user_input, "display", code)
            return {
                "content": summary,
                "result_type": "dataframe",
                "result_data": rdf.to_json(orient="split"),
                "result_title": f"Results: {user_input}",
                "code": code,
            }
        else:
            log_interaction(user_input, "display", user_input, "text", True, "scalar result")
            _save_code_snippet(user_id, session_id, user_input, "display", code)
            return {"content": f"Result: {rdf}", "result_type": "text",
                    "result_data": str(rdf), "result_title": f"Results: {user_input}",
                    "code": code}

    log_interaction(user_input, "display", user_input, None, False, "all attempts failed")
    return {"content": "I couldn't process that request. Could you rephrase it?"}


def _handle_visualize(user_input, df, file_path, ctx, history=None, user_id=None, session_id=None):
    """AI generates chart code, executes safely, captures figure as base64."""
    app_logger.info(f"[VIZ] AI chart code generation for: {user_input}")
    raw = generate_chart_code(user_input, file_path, ctx, history)
    code = extract_code(raw)
    b64 = None

    if code:
        b64 = _exec_chart_code(code, user_input, file_path, ctx)

    if b64:
        summary = generate_result_summary(user_input, "visualize")
        log_interaction(user_input, "visualize", user_input, "chart", True)
        _save_code_snippet(user_id, session_id, user_input, "visualize", code)
        return {
            "content": summary,
            "result_type": "chart",
            "result_data": b64,
            "result_title": f"Chart: {user_input}",
            "code": code,
        }

    log_interaction(user_input, "visualize", user_input, None, False, "chart generation failed")
    return {"content": "I couldn't generate that visualization. Could you describe it differently?"}


def _exec_chart_code(code, user_input, file_path, ctx):
    """Execute chart code and capture as base64 PNG. Returns b64 string or None."""
    try:
        plt.close("all")
        ns, err = _safe_exec(code, description=f"visualize: {user_input}")

        if err:
            app_logger.warning(f"[VIZ] Code exec failed: {err}")
            fixed = fix_code(code, err, file_path, ctx)
            fixed_code = extract_code(fixed)
            if fixed_code:
                plt.close("all")
                ns, err = _safe_exec(fixed_code, description=f"visualize (fixed): {user_input}")

        if err is None:
            fig = ns.get("_result_fig", plt.gcf())
            if fig and fig.get_axes():
                buf = io.BytesIO()
                fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="#0d1117")
                buf.seek(0)
                b64 = base64.b64encode(buf.getvalue()).decode()
                plt.close("all")
                app_logger.info(f"[VIZ] Chart generated successfully")
                return b64
        plt.close("all")
    except Exception as e:
        log_error(e, context=f"Chart code exec: {user_input}")
        plt.close("all")
    return None


def _handle_modify(user_input, df, file_path, ctx, history=None, user_id=None, session_id=None):
    """AI generates modification code, executes safely, returns preview."""
    # Create backup
    backup_dir = os.path.join(MODIFIED_FOLDER, "backups")
    os.makedirs(backup_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy2(file_path, os.path.join(backup_dir, f"backup_{ts}.csv"))
    app_logger.info(f"[MODIFY] Backup created: backup_{ts}.csv")

    raw = generate_modify_code(user_input, file_path, ctx, history)
    code = extract_code(raw)
    if not code:
        app_logger.warning(f"[MODIFY] Code extraction failed")
        log_interaction(user_input, "modify", user_input, None, False, "code extraction failed")
        return {"content": "I couldn't generate the modification code. Could you rephrase?"}

    app_logger.info(f"[MODIFY] Executing AI-generated code...")
    ns, err = _safe_exec(code, description=f"modify: {user_input}")
    if err:
        app_logger.warning(f"[MODIFY] Code exec failed: {err}")
        fixed = fix_code(code, err, file_path, ctx)
        code = extract_code(fixed)
        if code:
            ns, err = _safe_exec(code, description=f"modify (fixed): {user_input}")
            if err:
                app_logger.warning(f"[MODIFY] Fixed code also failed: {err}")

    if err is None:
        # Re-read CSV to get accurate modified state
        try:
            preview_df = pd.read_csv(file_path).head(10)
        except Exception:
            rdf = ns.get("_result_df")
            preview_df = rdf.head(10) if isinstance(rdf, pd.DataFrame) else None

        if preview_df is not None:
            preview = preview_df.to_json(orient="split")
        else:
            preview = "{}"

        summary = generate_result_summary(user_input, "modify")
        log_interaction(user_input, "modify", user_input, "dataframe", True)
        _save_code_snippet(user_id, session_id, user_input, "modify", code)
        return {
            "content": summary,
            "result_type": "modify",
            "result_data": preview,
            "result_title": f"Modified: {user_input}",
            "code": code,
            "file_path": file_path,
        }

    log_interaction(user_input, "modify", user_input, None, False, "all attempts failed")
    return {"content": "The modification didn't work. Could you rephrase your request?"}
