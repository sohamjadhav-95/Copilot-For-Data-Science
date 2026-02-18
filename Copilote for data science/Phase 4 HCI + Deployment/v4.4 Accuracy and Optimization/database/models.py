# database/models.py — SQLAlchemy ORM models
from datetime import datetime, timezone
from database import db


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    sessions = db.relationship("ChatSession", backref="user", lazy=True, cascade="all, delete-orphan")
    activities = db.relationship("Activity", backref="user", lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {"id": self.id, "username": self.username, "email": self.email,
                "created_at": self.created_at.isoformat()}


class ChatSession(db.Model):
    __tablename__ = "chat_sessions"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    filename = db.Column(db.String(255), nullable=True)
    file_path = db.Column(db.String(512), nullable=True)
    title = db.Column(db.String(255), default="New Session")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    messages = db.relationship("Message", backref="session", lazy=True, cascade="all, delete-orphan",
                               order_by="Message.created_at")

    def to_dict(self):
        return {"id": self.id, "filename": self.filename, "title": self.title,
                "created_at": self.created_at.isoformat(), "message_count": len(self.messages)}


class Message(db.Model):
    __tablename__ = "messages"
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("chat_sessions.id"), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # "user" | "assistant"
    content = db.Column(db.Text, nullable=False)
    result_type = db.Column(db.String(20), nullable=True)  # "dataframe" | "chart" | "text" | None
    result_data = db.Column(db.Text, nullable=True)  # JSON or base64
    result_title = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {"id": self.id, "role": self.role, "content": self.content,
                "result_type": self.result_type, "result_data": self.result_data,
                "result_title": self.result_title, "created_at": self.created_at.isoformat()}


class Activity(db.Model):
    __tablename__ = "activities"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    action = db.Column(db.String(50), nullable=False)  # login, upload, display, visualize, modify, etc.
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {"id": self.id, "action": self.action, "details": self.details,
                "created_at": self.created_at.isoformat()}


class CodeSnippet(db.Model):
    __tablename__ = "code_snippets"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey("chat_sessions.id"), nullable=True)
    label = db.Column(db.String(255), nullable=False)           # auto-generated from user query
    operation = db.Column(db.String(30), nullable=False)        # display / visualize / modify
    code = db.Column(db.Text, nullable=False)                   # the generated Python code
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship("User", backref=db.backref("code_snippets", lazy=True, cascade="all, delete-orphan"))

    def to_dict(self):
        return {
            "id": self.id, "label": self.label, "operation": self.operation,
            "code": self.code, "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
        }
