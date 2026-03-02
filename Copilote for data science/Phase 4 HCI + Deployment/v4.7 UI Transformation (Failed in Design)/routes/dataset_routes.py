# routes/dataset_routes.py — Dataset upload, sessions, file download
import os
import pandas as pd

from flask import Blueprint, request, jsonify, send_file

from config import UPLOAD_FOLDER
from database import db
from database.models import ChatSession, Message
from routes.auth_routes import login_required, _log_activity
from logger import log_error, log_app_event, app_logger

dataset_bp = Blueprint("dataset", __name__)


@dataset_bp.route("/api/upload", methods=["POST"])
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

    try:
        df = pd.read_csv(path)
    except Exception as e:
        log_error(e, context=f"Failed to parse uploaded CSV: {f.filename}")
        try:
            os.remove(path)
        except OSError:
            pass
        return jsonify({"error": f"Could not parse CSV file: {str(e)}."}), 400

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


@dataset_bp.route("/api/sessions")
@login_required
def api_sessions():
    sessions = ChatSession.query.filter_by(user_id=request.current_user.id)\
        .order_by(ChatSession.created_at.desc()).all()
    return jsonify({"sessions": [s.to_dict() for s in sessions]})


@dataset_bp.route("/api/sessions/<int:session_id>/messages")
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


@dataset_bp.route("/api/download-modified")
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
    return send_file(fp, as_attachment=True,
                     download_name=f"modified_{os.path.basename(fp)}")
