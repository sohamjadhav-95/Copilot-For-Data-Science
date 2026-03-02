# config.py — Application configuration
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

SECRET_KEY = os.environ.get("SECRET_KEY", "ds-copilot-secret-key-change-in-production")
SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'database', 'copilot.db')}"
SQLALCHEMY_TRACK_MODIFICATIONS = False
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
MODIFIED_FOLDER = os.path.join(BASE_DIR, "modified_files")
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB
JWT_EXPIRY_HOURS = 24
