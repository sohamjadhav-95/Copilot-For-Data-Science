# routes/normal_routes.py — Normal mode chat processing (JSON only)
import os
import io
import shutil
import base64
import json
from datetime import datetime

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from flask import Blueprint, request, jsonify

from config import MODIFIED_FOLDER
from database import db
from database.models import ChatSession, Message, CodeSnippet
from routes.auth_routes import login_required, _log_activity
from engines import (
    classify_intent, build_data_context, resolve_query,
    generate_display_code, generate_chart_code, generate_modify_code,
    generate_chat_response, generate_result_summary,
    fix_code, extract_code, _safe_exec,
)
from logger import log_error, log_interaction, app_logger

normal_bp = Blueprint("normal", __name__)


# ═══════════════════════════════════════════════════════════════════════
# CODE SNIPPET SAVING
# ═══════════════════════════════════════════════════════════════════════

def _save_code_snippet(user_id, session_id, user_input, operation, code):
    """Save generated code snippet to CodeSnippet table."""
    if not user_id or not code:
        return
    try:
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
# INTENT PROCESSING
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
    return {"content": "↩️ Reverted to previous version.", "result_type": "text",
            "result_data": "Successfully undone the last change.", "result_title": "↩️ Undo"}


def _handle_display(user_input, df, file_path, ctx, history=None, user_id=None, session_id=None):
    """AI generates code, executes it safely, returns result."""
    app_logger.info(f"[DISPLAY] AI code generation for: {user_input}")
    raw = generate_display_code(user_input, file_path, ctx, history)
    code = extract_code(raw)
    if not code:
        log_interaction(user_input, "display", user_input, None, False, "code extraction failed")
        return {"content": "I couldn't generate code for that request. Could you rephrase it?"}

    ns, err = _safe_exec(code, description=f"display: {user_input}")

    if err:
        fixed = fix_code(code, err, file_path, ctx)
        code = extract_code(fixed)
        if code:
            ns, err = _safe_exec(code, description=f"display (fixed): {user_input}")

    if err is None and "_result_df" in ns:
        rdf = ns["_result_df"]
        if isinstance(rdf, pd.Series):
            rdf = rdf.to_frame()
        if isinstance(rdf, pd.DataFrame):
            summary = generate_result_summary(user_input, "display")
            log_interaction(user_input, "display", user_input, "dataframe", True)
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
    """Execute chart code and capture as base64 PNG."""
    try:
        plt.close("all")
        ns, err = _safe_exec(code, description=f"visualize: {user_input}")

        if err:
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
                return b64
        plt.close("all")
    except Exception as e:
        log_error(e, context=f"Chart code exec: {user_input}")
        plt.close("all")
    return None


def _handle_modify(user_input, df, file_path, ctx, history=None, user_id=None, session_id=None):
    """AI generates modification code, executes safely, returns preview."""
    backup_dir = os.path.join(MODIFIED_FOLDER, "backups")
    os.makedirs(backup_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy2(file_path, os.path.join(backup_dir, f"backup_{ts}.csv"))

    raw = generate_modify_code(user_input, file_path, ctx, history)
    code = extract_code(raw)
    if not code:
        log_interaction(user_input, "modify", user_input, None, False, "code extraction failed")
        return {"content": "I couldn't generate the modification code. Could you rephrase?"}

    ns, err = _safe_exec(code, description=f"modify: {user_input}")
    if err:
        fixed = fix_code(code, err, file_path, ctx)
        code = extract_code(fixed)
        if code:
            ns, err = _safe_exec(code, description=f"modify (fixed): {user_input}")

    if err is None:
        try:
            preview_df = pd.read_csv(file_path).head(10)
        except Exception:
            rdf = ns.get("_result_df")
            preview_df = rdf.head(10) if isinstance(rdf, pd.DataFrame) else None

        preview = preview_df.to_json(orient="split") if preview_df is not None else "{}"

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


# ═══════════════════════════════════════════════════════════════════════
# CHAT ROUTE
# ═══════════════════════════════════════════════════════════════════════

@normal_bp.route("/api/chat", methods=["POST"])
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
                         content="⚠️ Could not read the dataset file. Please re-upload.")
        db.session.add(ai_msg)
        db.session.commit()
        return jsonify({"user_msg": user_msg.to_dict(), "assistant_msg": ai_msg.to_dict()})

    info, ctx = build_data_context(df, file_path)

    intent = classify_intent(user_input, conversation_history)
    app_logger.info(f"[CHAT] User: '{user_input}' -> Intent: {intent}")

    resolved_input = resolve_query(user_input, conversation_history, ctx)
    if resolved_input != user_input:
        app_logger.info(f"[RESOLVED] '{user_input}' -> '{resolved_input}'")

    _log_activity(request.current_user.id, intent, user_input)

    try:
        result = _process_intent(intent, resolved_input, df, file_path, ctx, sess,
                                 conversation_history, user_id=request.current_user.id)
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
