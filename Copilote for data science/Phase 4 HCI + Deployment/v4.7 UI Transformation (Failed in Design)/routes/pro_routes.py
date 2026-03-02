# routes/pro_routes.py — Pro Mode DAG workflow (JSON only)
import os
import pandas as pd

from flask import Blueprint, request, jsonify

from database import db
from database.models import ChatSession
from routes.auth_routes import login_required, _log_activity
from engines_pro.pro_engine import pro_engine
from logger import log_error, app_logger

pro_bp = Blueprint("pro", __name__)


@pro_bp.route("/api/pro/classify", methods=["POST"])
@login_required
def api_pro_classify():
    """Classify prompt complexity: SIMPLE → Normal engine, COMPLEX → Pro DAG."""
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
    if not sess.file_path or not os.path.exists(sess.file_path):
        return jsonify({"error": "No dataset file found"}), 400

    try:
        df = pd.read_csv(sess.file_path)
    except Exception as e:
        return jsonify({"error": f"Could not read dataset: {e}"}), 400

    profile = pro_engine.get_profile(df)
    result = pro_engine.detect_complexity(user_input, profile)

    return jsonify({
        "complexity": "complex" if result.get("needs_pro") else "simple",
        "needs_pro": result.get("needs_pro", False),
        "reason": result.get("reason", ""),
        "estimated_steps": result.get("estimated_steps", 0),
    })


@pro_bp.route("/api/pro/plan", methods=["POST"])
@login_required
def api_pro_plan():
    """Generate a DAG plan for user approval."""
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

    size_check = pro_engine.check_dataset_size(df)
    if not size_check["within_limits"] and not size_override:
        return jsonify({
            "warning": size_check["warning"],
            "requires_confirmation": True,
            "rows": size_check["rows"],
            "max_rows": size_check["max_rows"],
        }), 200

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


@pro_bp.route("/api/pro/approve", methods=["POST"])
@login_required
def api_pro_approve():
    """Approve and execute a DAG plan."""
    data = request.get_json()
    plan_id = data.get("plan_id")

    if not plan_id:
        return jsonify({"error": "plan_id required"}), 400

    result = pro_engine.execute(plan_id)
    if result is None:
        return jsonify({"error": "Plan not found or expired"}), 404

    if "error" in result:
        return jsonify(result), 400

    _log_activity(request.current_user.id, "pro_execute", f"Plan {plan_id}")
    return jsonify(result)


@pro_bp.route("/api/pro/status/<plan_id>")
@login_required
def api_pro_status(plan_id):
    """Poll execution status for a plan with per-node detail."""
    status = pro_engine.get_status(plan_id)
    if status is None:
        return jsonify({"error": "Plan not found"}), 404
    return jsonify(status)


@pro_bp.route("/api/pro/profile", methods=["POST"])
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
