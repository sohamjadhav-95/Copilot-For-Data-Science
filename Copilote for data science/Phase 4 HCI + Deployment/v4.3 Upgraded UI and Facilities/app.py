# app.py — Flask backend: Authentication, API routes, Chat processing
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
from database.models import User, ChatSession, Message, Activity
from engines import (
    classify_intent, build_data_context, resolve_query,
    generate_display_code, generate_chart_spec, build_chart, build_auto_chart,
    generate_visualize_code, generate_modify_code,
    generate_chat_response, generate_result_summary,
    fix_code, extract_code, _smart_chart_spec_fallback,
)


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

    with app.app_context():
        db.create_all()

    register_routes(app)
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
        return render_template("dashboard.html", user=request.current_user)

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

        # Create user upload directory
        os.makedirs(os.path.join(UPLOAD_FOLDER, str(user.id)), exist_ok=True)

        _log_activity(user.id, "register", f"Registered as {username}")
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

    # ── File Upload ───────────────────────────────────────────────────

    @app.route("/api/upload", methods=["POST"])
    @login_required
    def api_upload():
        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400
        f = request.files["file"]
        if not f.filename.endswith(".csv"):
            return jsonify({"error": "Only CSV files are supported"}), 400

        user_dir = os.path.join(UPLOAD_FOLDER, str(request.current_user.id))
        os.makedirs(user_dir, exist_ok=True)
        path = os.path.join(user_dir, f.filename)
        f.save(path)

        # Create a new chat session
        sess = ChatSession(
            user_id=request.current_user.id,
            filename=f.filename,
            file_path=path,
            title=f"Chat: {f.filename}",
        )
        db.session.add(sess)
        db.session.commit()
        _log_activity(request.current_user.id, "upload", f"Uploaded {f.filename}")

        # Read dataset info
        df = pd.read_csv(path)
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

    @app.route("/api/sessions/<int:session_id>/messages")
    @login_required
    def api_session_messages(session_id):
        sess = ChatSession.query.get_or_404(session_id)
        if sess.user_id != request.current_user.id:
            return jsonify({"error": "Forbidden"}), 403
        msgs = [m.to_dict() for m in sess.messages]
        # Also return dataset info
        info = None
        if sess.file_path and os.path.exists(sess.file_path):
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
        return jsonify({"messages": msgs, "dataset": info})

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

        # Save user message
        user_msg = Message(session_id=session_id, role="user", content=user_input)
        db.session.add(user_msg)
        db.session.commit()

        # Fetch conversation history (last 10 messages before current)
        recent_msgs = Message.query.filter_by(session_id=session_id)\
            .order_by(Message.created_at.desc()).limit(11).all()
        recent_msgs.reverse()  # chronological order
        # Exclude the message we just saved (last one)
        conversation_history = [
            {"role": m.role, "content": m.content}
            for m in recent_msgs[:-1]  # exclude current message
        ]

        file_path = sess.file_path
        if not file_path or not os.path.exists(file_path):
            ai_msg = Message(session_id=session_id, role="assistant",
                             content="No dataset file found. Please upload a CSV first.")
            db.session.add(ai_msg)
            db.session.commit()
            return jsonify({"user_msg": user_msg.to_dict(), "assistant_msg": ai_msg.to_dict()})

        df = pd.read_csv(file_path)
        info, ctx = build_data_context(df, file_path)

        # AI-first intent classification with conversation context
        intent = classify_intent(user_input, conversation_history)
        print(f"\n{'='*60}")
        print(f"[CHAT] User: '{user_input}' -> Intent: {intent}")
        print(f"{'='*60}")

        # Resolve vague/follow-up queries into clear instructions
        resolved_input = resolve_query(user_input, conversation_history, ctx)
        if resolved_input != user_input:
            print(f"[RESOLVED] '{user_input}' -> '{resolved_input}'")

        _log_activity(request.current_user.id, intent, user_input)

        result = _process_intent(intent, resolved_input, df, file_path, ctx, sess, conversation_history)

        # Save assistant message
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


# ═══════════════════════════════════════════════════════════════════════
# INTENT PROCESSING
# ═══════════════════════════════════════════════════════════════════════

def _process_intent(intent, user_input, df, file_path, ctx, sess, conversation_history=None):
    """Process user intent and return result dict."""
    history = conversation_history or []

    if intent == "undo":
        return _handle_undo(file_path, sess)

    elif intent == "display":
        return _handle_display(user_input, df, file_path, ctx, history)

    elif intent == "visualize":
        return _handle_visualize(user_input, df, file_path, ctx, history)

    elif intent == "modify":
        return _handle_modify(user_input, df, file_path, ctx, history)

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
    return {"content": "↩️ Reverted to previous version.", "result_type": "text",
            "result_data": "Successfully undone the last change.", "result_title": "↩️ Undo"}


def _handle_display(user_input, df, file_path, ctx, history=None):
    # AI code generation with conversation context
    print(f"  [DISPLAY] Generating code with AI...")
    raw = generate_display_code(user_input, file_path, ctx, history)
    code = extract_code(raw)
    if not code:
        print(f"  [DISPLAY] Code extraction failed")
        return {"content": "I couldn't process that query. Could you rephrase it?"}

    ns = {}
    ok = False
    try:
        exec(code, ns)
        ok = True
    except Exception as e:
        print(f"  [DISPLAY] Code exec failed: {e}")
        fixed = fix_code(code, str(e), file_path, ctx)
        code = extract_code(fixed)
        if code:
            try:
                ns = {}
                exec(code, ns)
                ok = True
            except Exception as e2:
                print(f"  [DISPLAY] Fixed code also failed: {e2}")

    if ok and "_result_df" in ns:
        rdf = ns["_result_df"]
        if isinstance(rdf, pd.Series):
            rdf = rdf.to_frame()
        if isinstance(rdf, pd.DataFrame):
            summary = generate_result_summary(user_input, "display")
            return {
                "content": summary,
                "result_type": "dataframe",
                "result_data": rdf.to_json(orient="split"),
                "result_title": f"Results: {user_input}",
            }
        else:
            return {"content": f"Result: {rdf}", "result_type": "text",
                    "result_data": str(rdf), "result_title": f"Results: {user_input}"}

    return {"content": "I couldn't process that display request. Could you rephrase it?"}


def _handle_visualize(user_input, df, file_path, ctx, history=None):
    dtypes_str = str(df.dtypes.to_dict())
    b64 = None

    # Tier 1: JSON spec from AI
    print(f"  [VIZ] Tier 1: AI chart spec...")
    spec = generate_chart_spec(user_input, dtypes_str, history)
    if spec:
        b64, err = build_chart(df, spec)
        if not b64:
            print(f"  [VIZ] Tier 1 build failed: {err}")
    else:
        print(f"  [VIZ] Tier 1 returned None")

    # Tier 1.5: Smart keyword fallback
    if not b64:
        print(f"  [VIZ] Tier 1.5: keyword fallback...")
        spec = _smart_chart_spec_fallback(user_input, df)
        if spec:
            b64, err = build_chart(df, spec)
            if not b64:
                print(f"  [VIZ] Tier 1.5 build failed: {err}")

    # Tier 2: AI code generation
    if not b64:
        print(f"  [VIZ] Tier 2: AI code gen...")
        raw = generate_visualize_code(user_input, file_path, ctx, history)
        code = extract_code(raw)
        if code:
            ns = {}
            try:
                plt.close("all")
                exec(code, ns)
                fig = ns.get("_result_fig", plt.gcf())
                if fig and fig.get_axes():
                    buf = io.BytesIO()
                    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="#0d1117")
                    buf.seek(0)
                    b64 = base64.b64encode(buf.getvalue()).decode()
                    print(f"  [VIZ] Tier 2 succeeded")
                plt.close("all")
            except Exception as e:
                print(f"  [VIZ] Tier 2 exec failed: {e}")
                plt.close("all")

    # Tier 3: Auto chart
    if not b64:
        print(f"  [VIZ] Tier 3: auto chart...")
        b64, _ = build_auto_chart(df)

    if b64:
        summary = generate_result_summary(user_input, "visualize")
        return {
            "content": summary,
            "result_type": "chart",
            "result_data": b64,
            "result_title": f"Chart: {user_input}",
        }

    return {"content": "I couldn't generate that visualization. Could you describe it differently?"}


def _handle_modify(user_input, df, file_path, ctx, history=None):
    # Create backup
    backup_dir = os.path.join(MODIFIED_FOLDER, "backups")
    os.makedirs(backup_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy2(file_path, os.path.join(backup_dir, f"backup_{ts}.csv"))
    print(f"  [MODIFY] Backup created: backup_{ts}.csv")

    raw = generate_modify_code(user_input, file_path, ctx, history)
    code = extract_code(raw)
    if not code:
        print(f"  [MODIFY] Code extraction failed")
        return {"content": "I couldn't generate the modification code. Could you rephrase?"}

    print(f"  [MODIFY] Executing code...")
    ns = {}
    ok = False
    try:
        exec(code, ns)
        ok = True
        print(f"  [MODIFY] Success")
    except Exception as e:
        print(f"  [MODIFY] Code exec failed: {e}")
        fixed = fix_code(code, str(e), file_path, ctx)
        code = extract_code(fixed)
        if code:
            try:
                ns = {}
                exec(code, ns)
                ok = True
                print(f"  [MODIFY] Fixed code succeeded")
            except Exception as e2:
                print(f"  [MODIFY] Fixed code also failed: {e2}")

    if ok:
        rdf = ns.get("_result_df")
        if isinstance(rdf, pd.DataFrame):
            preview = rdf.head(10).to_json(orient="split")
        else:
            preview = pd.read_csv(file_path).head(10).to_json(orient="split")
        summary = generate_result_summary(user_input, "modify")
        return {
            "content": summary,
            "result_type": "dataframe",
            "result_data": preview,
            "result_title": f"Modified: {user_input}",
        }

    return {"content": "The modification didn't work. Could you rephrase your request?"}
