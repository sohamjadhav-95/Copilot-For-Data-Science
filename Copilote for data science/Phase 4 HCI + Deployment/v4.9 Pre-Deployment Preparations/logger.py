# logger.py — Centralized structured logging for DataCopilot
# ─────────────────────────────────────────────────────────────────────────────
# Architecture:
#   • 8 named loggers, each with its own .log file (JSON-per-line)
#   • EVERY write is simultaneously mirrored to a .csv with typed columns
#   • CSV mirroring is universal — no code changes needed for new log files
#   • A frontend log endpoint writes to frontend.log / frontend.csv
#   • Log files rotate at 5 MB (3 backups kept)
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import csv
import json
import logging
import os
import traceback
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional

# ═══════════════════════════════════════════════════════════════════════
# DIRECTORY SETUP
# ═══════════════════════════════════════════════════════════════════════

LOG_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / "logs_and_debug"
LOG_DIR.mkdir(exist_ok=True)

# Sub-directory for CSV mirrors
CSV_DIR = LOG_DIR / "csv"
CSV_DIR.mkdir(exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════
# UNIVERSAL CSV COLUMNS — superset of all log fields
# Every CSV shares the same header; absent fields are written as empty.
# Adding a new log file NEVER requires changing this list —
# unknown keys are appended to the "extra_json" column instead.
# ═══════════════════════════════════════════════════════════════════════

_CSV_COLUMNS = [
    "timestamp", "level", "logger",
    # Common identity
    "session_id", "user_id", "plan_id",
    # API / model calls
    "provider", "model", "latency_ms", "tokens", "status",
    # User interactions
    "intent", "query", "result_type",
    # Execution / DAG
    "node_id", "node_type", "operation", "execution_time_ms",
    "completed_nodes", "failed_nodes", "replan_count",
    # Performance
    "endpoint", "method", "http_status", "response_ms", "memory_mb",
    # Errors
    "error_type", "error_detail", "context", "stack_trace",
    # Auth / security
    "action", "ip_address", "user_agent",
    # Frontend
    "page", "component", "event_type", "browser", "viewport",
    # General
    "message",
    # Overflow for any extra keys not in columns above
    "extra_json",
]

# Build a fast lookup set
_CSV_COL_SET = set(_CSV_COLUMNS)


# ═══════════════════════════════════════════════════════════════════════
# CSV MIRROR HANDLER — attaches to every logger automatically
# ═══════════════════════════════════════════════════════════════════════

class CSVMirrorHandler(logging.Handler):
    """
    Writes every JSON log record into a matching CSV file.
    Thread-safe via Python's GIL + csv module's line-by-line writes.
    No configuration needed — works for any logger / field set.
    """

    def __init__(self, csv_path: Path):
        super().__init__()
        self.csv_path = csv_path
        self._ensure_header()

    def _ensure_header(self):
        """Write header row if the file is new or empty."""
        if not self.csv_path.exists() or self.csv_path.stat().st_size == 0:
            with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
                csv.DictWriter(f, fieldnames=_CSV_COLUMNS).writeheader()

    def emit(self, record: logging.LogRecord):
        try:
            # Parse JSON from the record (set by JSONFormatter)
            raw = record.getMessage() if not hasattr(record, "_json_str") else record._json_str
            # Try to get the structured dict from the formatter output
            try:
                entry: Dict[str, Any] = json.loads(self.format(record))
            except Exception:
                entry = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                }

            # Separate known columns from overflow
            row = {col: "" for col in _CSV_COLUMNS}
            extra_fields = {}
            for key, val in entry.items():
                if key in _CSV_COL_SET:
                    # Flatten complex values
                    if isinstance(val, (dict, list)):
                        row[key] = json.dumps(val, ensure_ascii=False, default=str)
                    elif val is None:
                        row[key] = ""
                    else:
                        row[key] = str(val)
                else:
                    extra_fields[key] = val

            if extra_fields:
                row["extra_json"] = json.dumps(extra_fields, ensure_ascii=False, default=str)

            # Ensure message is filled
            if not row.get("message"):
                row["message"] = record.getMessage()

            with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=_CSV_COLUMNS, extrasaction="ignore")
                writer.writerow(row)

        except Exception:
            self.handleError(record)


# ═══════════════════════════════════════════════════════════════════════
# FORMATTERS
# ═══════════════════════════════════════════════════════════════════════

class JSONFormatter(logging.Formatter):
    """Structured JSON log format — one JSON object per line."""

    # Fields collected from LogRecord.extra
    _EXTRA_FIELDS = [
        "provider", "model", "latency_ms", "tokens", "status",
        "intent", "query", "result_type", "error_type", "error_detail",
        "stack_trace", "context", "session_id", "user_id", "plan_id",
        "node_id", "node_type", "operation", "execution_time_ms",
        "completed_nodes", "failed_nodes", "replan_count",
        "endpoint", "method", "http_status", "response_ms", "memory_mb",
        "action", "ip_address", "user_agent",
        "page", "component", "event_type", "browser", "viewport",
    ]

    def format(self, record: logging.LogRecord) -> str:
        entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in self._EXTRA_FIELDS:
            val = getattr(record, field, None)
            if val is not None:
                entry[field] = val
        return json.dumps(entry, ensure_ascii=False, default=str)


class ReadableFormatter(logging.Formatter):
    """Human-readable console output."""
    _LEVEL_COLORS = {
        "DEBUG": "\033[90m", "INFO": "\033[36m",
        "WARNING": "\033[33m", "ERROR": "\033[31m", "CRITICAL": "\033[35m",
    }
    _RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.now().strftime("%H:%M:%S")
        color = self._LEVEL_COLORS.get(record.levelname, "")
        return f"[{ts}] {color}{record.levelname:<7}{self._RESET} {record.name}: {record.getMessage()}"


# ═══════════════════════════════════════════════════════════════════════
# LOGGER FACTORY — universal, auto-creates CSV mirror
# ═══════════════════════════════════════════════════════════════════════

def _make_logger(
    name: str,
    log_filename: str,
    level: int = logging.DEBUG,
    console_level: int = logging.INFO,
) -> logging.Logger:
    """
    Create or retrieve a named logger with:
      1. Rotating JSON file handler  → logs_and_debug/<log_filename>
      2. CSV mirror handler          → logs_and_debug/csv/<stem>.csv
      3. Colored console handler     → stdout (INFO+ by default)
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # Already configured in this process

    logger.setLevel(level)
    logger.propagate = False

    json_fmt  = JSONFormatter()
    csv_fmt   = JSONFormatter()   # CSV handler needs JSON to parse
    readable_fmt = ReadableFormatter()

    # 1. Rotating JSON file handler
    log_path = LOG_DIR / log_filename
    fh = RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(json_fmt)
    logger.addHandler(fh)

    # 2. CSV mirror — same stem as .log file
    csv_path = CSV_DIR / (Path(log_filename).stem + ".csv")
    csv_handler = CSVMirrorHandler(csv_path)
    csv_handler.setLevel(logging.DEBUG)
    csv_handler.setFormatter(csv_fmt)   # JSON→ CSVMirrorHandler parses JSON
    logger.addHandler(csv_handler)

    # 3. Console (readable, INFO+)
    ch = logging.StreamHandler()
    ch.setLevel(console_level)
    ch.setFormatter(readable_fmt)
    logger.addHandler(ch)

    return logger


# ═══════════════════════════════════════════════════════════════════════
# NAMED LOGGERS
# ═══════════════════════════════════════════════════════════════════════

# General application events (startup, config, lifecycle)
app_logger          = _make_logger("copilot.app",          "app.log")

# External LLM / model API calls
api_logger          = _make_logger("copilot.api",          "api_calls.log")

# User query → intent → result interactions
interaction_logger  = _make_logger("copilot.interaction",  "user_interactions.log")

# All errors and exceptions with tracebacks
error_logger        = _make_logger("copilot.errors",       "errors.log")

# Pro Mode DAG planning + execution telemetry
workflow_logger     = _make_logger("copilot.workflow",     "workflow_execution.log")

# Auth events: login, logout, failed attempts, session expiry
security_logger     = _make_logger("copilot.security",     "security_auth.log")

# HTTP endpoint latency, memory usage, slow query warnings
performance_logger  = _make_logger("copilot.performance",  "performance.log")

# Frontend JS errors, UI events, navigation, component failures
frontend_logger     = _make_logger("copilot.frontend",     "frontend.log",
                                   console_level=logging.WARNING)


# ═══════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════

def log_api_call(
    provider: str,
    model: str,
    prompt_preview: str,
    response_preview: str,
    latency_ms: float,
    tokens: Optional[int] = None,
    status: str = "success",
    error=None,
    session_id: Optional[str] = None,
) -> None:
    """Log an LLM API call with full telemetry."""
    extra = {
        "provider": provider, "model": model,
        "latency_ms": round(latency_ms, 1),
        "tokens": tokens, "status": status,
    }
    if session_id:
        extra["session_id"] = session_id
    prompt_short  = prompt_preview[:120]  + ("…" if len(prompt_preview)  > 120 else "")
    resp_short    = response_preview[:200] + ("…" if len(response_preview) > 200 else "")
    msg = f"[{provider}/{model}] {status} ({latency_ms:.0f}ms)"
    if status == "success":
        api_logger.info(f"{msg} | prompt={prompt_short!r} | response={resp_short!r}", extra=extra)
    else:
        extra["error_detail"] = str(error) if error else "unknown"
        api_logger.warning(f"{msg} | error={error}", extra=extra)


def log_interaction(
    query: str,
    intent: str,
    resolved_query: str,
    result_type: str,
    success: bool,
    details: Optional[str] = None,
    session_id: Optional[str] = None,
    user_id: Optional[int] = None,
) -> None:
    """Log a full user query → result interaction."""
    extra = {
        "query": query[:300], "intent": intent, "result_type": result_type,
        "status": "success" if success else "failure",
    }
    if session_id: extra["session_id"] = session_id
    if user_id:    extra["user_id"]    = str(user_id)
    msg = (
        f"[{intent}] query={query!r}"
        + (f" → resolved={resolved_query!r}" if resolved_query != query else "")
        + f" | result={result_type} | {'OK' if success else 'FAIL'}"
    )
    if details:
        msg += f" | {details[:200]}"
    if success:
        interaction_logger.info(msg, extra=extra)
    else:
        interaction_logger.warning(msg, extra=extra)


def log_error(
    error: Exception,
    context: str = "",
    include_traceback: bool = True,
    session_id: Optional[str] = None,
) -> None:
    """Log an exception with type, message, context, and optional traceback."""
    extra = {
        "error_type": type(error).__name__,
        "error_detail": str(error)[:500],
        "context": context,
    }
    if include_traceback:
        extra["stack_trace"] = traceback.format_exc()
    if session_id:
        extra["session_id"] = session_id
    error_logger.error(f"[{type(error).__name__}] {error} | context={context}", extra=extra)


def log_app_event(event: str, details: Optional[str] = None) -> None:
    """Log a general application lifecycle event."""
    msg = f"[{event}]"
    if details:
        msg += f" {details}"
    app_logger.info(msg)


def log_workflow_execution(
    plan_id: str,
    status: str,
    completed_nodes: list,
    failed_nodes: list,
    replan_count: int = 0,
    execution_time_ms: float = 0,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    replan_reason: Optional[str] = None,
) -> None:
    """Log a full Pro Mode DAG execution result."""
    extra = {
        "plan_id": plan_id,
        "status": status,
        "completed_nodes": json.dumps(completed_nodes),
        "failed_nodes": json.dumps(failed_nodes),
        "replan_count": replan_count,
        "execution_time_ms": round(execution_time_ms, 1),
    }
    if user_id:       extra["user_id"]    = str(user_id)
    if session_id:    extra["session_id"] = str(session_id)
    if replan_reason: extra["context"]    = replan_reason
    msg = (
        f"[DAG] plan={plan_id} status={status} "
        f"completed={len(completed_nodes)} failed={len(failed_nodes)} "
        f"replans={replan_count} time={execution_time_ms:.0f}ms"
    )
    level = logging.WARNING if failed_nodes else logging.INFO
    workflow_logger.log(level, msg, extra=extra)


def log_workflow_node(
    plan_id: str,
    node_id: str,
    node_type: str,
    operation: str,
    status: str,
    execution_time_ms: float = 0,
    error: Optional[str] = None,
) -> None:
    """Log a single DAG node execution."""
    extra = {
        "plan_id": plan_id,
        "node_id": node_id,
        "node_type": node_type,
        "operation": operation[:200],
        "status": status,
        "execution_time_ms": round(execution_time_ms, 1),
    }
    if error:
        extra["error_detail"] = error[:300]
    msg = f"[NODE] plan={plan_id} node={node_id} ({node_type}) op={operation!r} → {status} ({execution_time_ms:.0f}ms)"
    if status in ("success",):
        workflow_logger.info(msg, extra=extra)
    else:
        workflow_logger.warning(msg, extra=extra)


def log_security_event(
    action: str,
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    success: bool = True,
    details: Optional[str] = None,
) -> None:
    """Log an authentication or security event."""
    extra = {
        "action": action,
        "status": "success" if success else "failure",
    }
    if user_id:    extra["user_id"]    = str(user_id)
    if ip_address: extra["ip_address"] = ip_address
    if user_agent: extra["user_agent"] = user_agent[:200]
    msg = f"[SECURITY] {action} | user={user_id} | ip={ip_address} | {'OK' if success else 'FAIL'}"
    if details:
        msg += f" | {details}"
    level = logging.INFO if success else logging.WARNING
    security_logger.log(level, msg, extra=extra)


def log_performance(
    endpoint: str,
    method: str,
    http_status: int,
    response_ms: float,
    memory_mb: Optional[float] = None,
    session_id: Optional[str] = None,
) -> None:
    """Log HTTP endpoint performance metrics."""
    extra = {
        "endpoint": endpoint,
        "method": method,
        "http_status": http_status,
        "response_ms": round(response_ms, 1),
    }
    if memory_mb:   extra["memory_mb"] = round(memory_mb, 2)
    if session_id:  extra["session_id"] = session_id
    msg = f"[PERF] {method} {endpoint} → {http_status} ({response_ms:.0f}ms)"
    if response_ms > 3000:
        performance_logger.warning(f"SLOW: {msg}", extra=extra)
    else:
        performance_logger.info(msg, extra=extra)


def log_frontend_event(
    event_type: str,
    page: str,
    component: Optional[str] = None,
    message: Optional[str] = None,
    level: str = "info",
    browser: Optional[str] = None,
    viewport: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    stack_trace: Optional[str] = None,
) -> None:
    """Log a frontend JS event (error, navigation, UI action)."""
    extra = {
        "event_type": event_type,
        "page": page,
    }
    if component:   extra["component"]   = component
    if browser:     extra["browser"]     = browser[:100]
    if viewport:    extra["viewport"]    = viewport
    if user_id:     extra["user_id"]     = str(user_id)
    if session_id:  extra["session_id"]  = session_id
    if stack_trace: extra["stack_trace"] = stack_trace[:1000]
    msg = message or f"[FE] {event_type} | page={page} component={component}"
    _level = {
        "debug":    logging.DEBUG,
        "info":     logging.INFO,
        "warning":  logging.WARNING,
        "error":    logging.ERROR,
        "critical": logging.CRITICAL,
    }.get(level.lower(), logging.INFO)
    frontend_logger.log(_level, msg, extra=extra)
