# app.py — Flask REST API (JSON only, no HTML templates)
# v4.7: Modular blueprint architecture for React SPA frontend
import os

from flask import Flask
from flask_cors import CORS

from config import (
    SECRET_KEY, SQLALCHEMY_DATABASE_URI, SQLALCHEMY_TRACK_MODIFICATIONS,
    UPLOAD_FOLDER, MAX_CONTENT_LENGTH, MODIFIED_FOLDER,
)
from database import db
from api_config import get_active_provider
from logger import log_app_event
from routes import ALL_BLUEPRINTS


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

    # CORS for React dev server (localhost:5173)
    CORS(app, resources={r"/api/*": {"origins": ["http://localhost:5173", "http://127.0.0.1:5173"]}},
         supports_credentials=True)

    db.init_app(app)

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(MODIFIED_FOLDER, exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(__file__), "database"), exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(__file__), "logs_and_debug"), exist_ok=True)

    with app.app_context():
        db.create_all()

    # Register all route blueprints
    for bp in ALL_BLUEPRINTS:
        app.register_blueprint(bp)

    log_app_event("startup", f"App created, provider={get_active_provider()}")
    return app
