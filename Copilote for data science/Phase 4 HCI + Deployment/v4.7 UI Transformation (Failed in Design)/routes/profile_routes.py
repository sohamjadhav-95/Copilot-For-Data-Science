# routes/profile_routes.py — User profile, activities, code snippets, provider
from flask import Blueprint, request, jsonify

from database import db
from database.models import Activity, CodeSnippet
from routes.auth_routes import login_required
from api_config import get_active_provider, switch_provider, PROVIDERS
from logger import log_app_event

profile_bp = Blueprint("profile", __name__)


@profile_bp.route("/api/activities")
@login_required
def api_activities():
    acts = Activity.query.filter_by(user_id=request.current_user.id)\
        .order_by(Activity.created_at.desc()).limit(50).all()
    return jsonify({"activities": [a.to_dict() for a in acts]})


@profile_bp.route("/api/code-snippets")
@login_required
def api_code_snippets():
    snippets = CodeSnippet.query.filter_by(user_id=request.current_user.id)\
        .order_by(CodeSnippet.created_at.desc()).limit(100).all()
    return jsonify({"snippets": [s.to_dict() for s in snippets]})


@profile_bp.route("/api/code-snippets/<int:snippet_id>")
@login_required
def api_code_snippet_detail(snippet_id):
    snippet = CodeSnippet.query.get_or_404(snippet_id)
    if snippet.user_id != request.current_user.id:
        return jsonify({"error": "Forbidden"}), 403
    return jsonify({"snippet": snippet.to_dict()})


@profile_bp.route("/api/provider", methods=["GET"])
@login_required
def api_get_provider():
    return jsonify({
        "active_provider": get_active_provider(),
        "available_providers": list(PROVIDERS.keys()),
    })


@profile_bp.route("/api/provider", methods=["POST"])
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
