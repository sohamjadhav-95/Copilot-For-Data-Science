# Data Science Copilot — Project Guide v4.5

> **Dual-mode AI data science assistant with Graph-Based DAG execution engine**
> Normal Mode: single-step AI operations · Pro Mode: multi-step planned pipelines

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Project Structure](#project-structure)
4. [Installation & Setup](#installation--setup)
5. [User Guide](#user-guide)
6. [Developer Guide](#developer-guide)
7. [API Reference](#api-reference)
8. [Configuration Reference](#configuration-reference)
9. [Troubleshooting](#troubleshooting)

---

## Overview

Data Science Copilot is a full-stack Flask web application that lets users interact with CSV datasets using natural language. Version 4.5 introduces **Pro Mode** — a graph-based DAG execution engine layered cleanly on top of the existing Normal Mode. Both modes run in the same application; Normal Mode behavior is unchanged.

| | Normal Mode | Pro Mode |
|---|---|---|
| **Use case** | Single-step queries | Multi-step pipelines |
| **Planning** | None | DAG plan generated, user approves |
| **Execution** | Immediate | Step-by-step with tracker |
| **Model tier** | Mid/Light | Heavy→Mid→Light |
| **Replan** | N/A | Auto-replan up to 2× on failure |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Browser  (dashboard.html + app.js + style.css)             │
│  ┌──────────────────┐  ┌──────────────────────────────────┐ │
│  │  Normal Chat UI  │  │  Pro Mode UI                     │ │
│  │  (unchanged)     │  │  ┌─────────────┐ ┌───────────┐  │ │
│  │                  │  │  │  DAG Plan   │ │  Step     │  │ │
│  │                  │  │  │  Panel      │ │  Tracker  │  │ │
│  └──────────────────┘  └──┴─────────────┴─┴───────────┴──┘ │
└────────────────────────────┬────────────────────────────────┘
                             │ HTTP/JSON
                             ▼
┌─────────────────────────────────────────────────────────────┐
│  Flask (app.py) — Thin routing layer                        │
│                                                             │
│  Normal routes          Pro routes                          │
│  /api/chat              /api/pro/plan                       │
│  /api/upload            /api/pro/approve                    │
│  /api/sessions          /api/pro/status/<id>                │
│  /api/...               /api/pro/profile                    │
└──────────────┬──────────────────────┬───────────────────────┘
               ▼                      ▼
┌──────────────────────┐  ┌───────────────────────────────────┐
│  engines_normal/     │  │  engines_pro/                     │
│  normal_engine.py    │  │  ┌───────────┐  ┌──────────────┐ │
│  (original logic,    │  │  │ dag_schema│  │  dag_planner │ │
│   unchanged)         │  │  │ validator │  │  dag_executor│ │
│                      │  │  └───────────┘  └──────────────┘ │
│  engines.py          │  │  pro_engine.py (orchestrator)     │
│  (re-export shim)    │  └───────────────────────────────────┘
└──────────────────────┘
               │                      │
               └──────────┬───────────┘
                          ▼
           ┌──────────────────────────┐
           │  core/                   │
           │  config.py               │
           │  dataset_profiler.py     │
           │  execution_context.py    │
           └──────────────────────────┘
                          │
           ┌──────────────────────────┐
           │  models_api/             │
           │  model_router.py         │
           │  groq_models.py          │
           │  openrouter_models.py    │
           └──────────────────────────┘
```

### Model Tiers

| Tier | Role | Primary Model | Fallback |
|------|------|---------------|---------|
| **Heavy** | DAG planning, re-planning, final summaries | Groq DeepSeek R1 | OpenRouter Gemini 2.0 Flash |
| **Mid** | Code generation per node, retries | Groq Llama 3.3 70B | OpenRouter Llama 3.1 70B |
| **Light** | Intent classification, complexity detection | Groq Llama 3.1 8B | OpenRouter Llama 3.1 8B |

### Pro Mode Execution Flow

```
User message
    │
    ▼
detect_complexity()  ─── light model
    │ needs_pro=True
    ▼
DatasetProfiler.profile()  ─── full column stats, correlations, warnings
    │
    ▼
DAGPlanner.create_plan()  ─── heavy model → DAGPlan (JSON)
    │
    ▼ (user reviews plan in UI)
User clicks "Approve & Execute"
    │
    ▼
DAGExecutor.execute()
    ├── topological_sort() → ordered node IDs
    └── for each node:
        ├── ReplanTrigger.check_missing_variable()
        ├── generate_node_code()  ─── mid model
        ├── _safe_exec_with_timeout()  ─── hard timeout, sandboxed
        ├── validate_node_output()  ─── TWO-TIER: CRITICAL vs WARN
        ├── store in ExecutionContext
        └── ReplanTrigger.check_schema_change()
    │
    ▼ (if replan_needed, replan_count < 2)
DAGPlanner.replan()  ─── heavy model
    │
    ▼
generate_final_summary()  ─── heavy model
```

---

## Project Structure

```
v4.5 Architecture Transformation (Pro)/
│
├── 🚀 Entry Points
│   ├── run.py                       # Flask application entry point
│   ├── app.py                       # App factory, all routes (Normal + Pro)
│   ├── engines.py                   # Re-export shim → engines_normal
│   ├── config.py                    # Flask config (DB, uploads, JWT)
│   └── api_config.py                # Legacy API config (Normal Mode)
│
├── 🧠 Core Infrastructure
│   └── core/
│       ├── config.py                # Pro Mode config (model tiers, limits)
│       ├── dataset_profiler.py      # DatasetProfiler — used by both modes
│       └── execution_context.py    # ExecutionContext — DAG execution memory
│
├── 🤖 Model API Abstraction
│   └── models_api/
│       ├── model_router.py          # ModelRouter — tier routing + fallback
│       ├── groq_models.py           # Groq API wrapper
│       └── openrouter_models.py     # OpenRouter API wrapper
│
├── ⚙️ Normal Engine (unchanged behavior)
│   └── engines_normal/
│       └── normal_engine.py         # All original engines.py logic
│
├── 🔬 Pro Engine (DAG system)
│   └── engines_pro/
│       ├── dag_schema.py            # DAGPlan, DAGNode, Operand, NodeOutput, ExecutionMetadata
│       ├── validator.py             # Operand resolution, condition eval, output validation
│       ├── dag_planner.py           # Plan generation + re-planning via heavy model
│       ├── dag_executor.py          # Topological execution, timeout, retry, replan triggers
│       └── pro_engine.py            # Top-level orchestrator, in-memory plan store
│
├── 💾 Database
│   └── database/
│       ├── __init__.py              # SQLAlchemy instance
│       └── models.py                # User, ChatSession, Message, Activity, CodeSnippet
│
├── 🎨 Frontend
│   ├── templates/
│   │   ├── base.html                # Base layout
│   │   ├── dashboard.html           # Main UI with Normal/Pro toggle
│   │   ├── login.html               # Login page
│   │   └── register.html            # Registration page
│   └── static/
│       ├── css/style.css            # Full dark theme + Pro enterprise theme
│       └── js/app.js                # Normal + Pro Mode frontend logic
│
├── 📊 Data & Logs
│   ├── uploads/                     # User CSV files (per-user dirs)
│   ├── modified_files/backups/      # Undo backup files
│   └── logs_and_debug/              # Runtime logs (auto-generated)
│
├── 🧪 Tests
│   └── All Tests/
│       ├── test_features.py         # Integration tests
│       ├── test_fixes.py            # Regression tests
│       └── test_classify.py         # Intent classification tests
│
└── 📄 Docs
    ├── PROJECT_GUIDE.md             # This file — full developer reference
    ├── README.md                    # Quick-start card
    ├── requirements.txt             # Python dependencies
    └── logger.py                    # Centralized structured logger
```

---

## Installation & Setup

### Prerequisites
- Python 3.9+
- pip

### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

**Core dependencies:**
| Package | Purpose |
|---------|---------|
| `flask`, `flask-sqlalchemy`, `flask-cors` | Web framework + ORM |
| `pyjwt`, `bcrypt` | Authentication |
| `openai` | Groq + OpenRouter API client |
| `pandas`, `numpy` | Data processing |
| `matplotlib`, `seaborn` | Chart generation |
| `scipy`, `scikit-learn` | Optional: advanced analysis in Pro nodes |

### Step 2: Configure API Keys

Edit `core/config.py`:
```python
GROQ_API_KEY    = "gsk_..."          # from console.groq.com
OPENROUTER_API_KEY = "sk-or-..."     # from openrouter.ai
```

Or set as environment variables (recommended):
```bash
set GROQ_API_KEY=gsk_...
set OPENROUTER_API_KEY=sk-or-...
set SECRET_KEY=your-secret-key
```

### Step 3: Run

```bash
python run.py
```

Server starts at `http://localhost:5000`

---

## User Guide

### Normal Mode

Works identically to v4.4. Use the chat input to:

| Intent | Example phrases |
|--------|----------------|
| **Display** | "show first 10 rows", "summary statistics" |
| **Visualize** | "plot histogram of price", "scatter x vs y" |
| **Modify** | "add column id with row numbers", "fill missing with 0" |
| **Undo** | "undo", "revert last change" |
| **Chat** | "what insights can you give me?" |

### Pro Mode

1. **Toggle Pro** — click the **Normal/Pro** switch in the top navigation bar
2. **Send a complex request** — e.g. *"Clean missing data, compute correlations, build a regression model, and summarize findings"*
3. **Review the DAG Plan** — the right panel shows each planned step with type, description, and dependencies
4. **Approve & Execute** — click the gold **Approve & Execute** button; the Step Tracker shows live status per node
5. **Read the summary** — after completion, an AI-generated report appears in the tracker panel
6. **Reject** — click **Reject** to dismiss the plan and start over

#### Pro Mode Node Types

| Icon | Type | Description |
|------|------|-------------|
| 🔬 | `analysis` | Statistical computation, correlation, profiling |
| ⚙️ | `transformation` | Data cleaning, reshaping, feature engineering |
| 📊 | `visualization` | Chart/plot generation |
| ⑂ | `conditional` | Branch on computed value (if/else) |
| 📝 | `summary` | Aggregate findings, generate text |
| ▶ | `operation` | Generic computation |

---

## Developer Guide

### Adding a New Normal Mode Operation

1. Add keyword list to `engines_normal/normal_engine.py`
2. Update `classify_intent()` to check new keywords
3. Create a `generate_XXX_code()` function
4. Add handler in `app.py` under the `_handle_chat` route

### Adding a New Pro Node Type

1. Add to `NodeType` enum in `engines_pro/dag_schema.py`
2. Add icon and CSS class in `static/css/style.css` (`.pro-node-type-XXX`)
3. Add icon to `NODE_ICONS` map in `static/js/app.js`
4. The executor handles all types through `_execute_operation()` — no code change needed

### Adding a New Model Provider

1. Create `models_api/XXX_models.py` matching the interface in `groq_models.py`:
   ```python
   def call(messages, model, temperature, max_tokens) -> Optional[str]: ...
   def get_available_models() -> List[str]: ...
   ```
2. Register in `models_api/model_router.py` `_PROVIDER_CHAIN`

### Key Design Contracts

#### NodeOutput Contract (`dag_schema.py`)
Every DAG node execution must produce a `NodeOutput`:
```python
@dataclass
class NodeOutput:
    output_type: OutputType   # scalar | dataframe | artifact | dict | none
    value: Any                # the actual value
    summary: str              # human-readable description (for model context)
```

#### Operand Resolution (`validator.py`)
Conditions use typed operands — no `eval()`:
```python
# LITERAL:  {kind: "literal",   value: 0.7}
# VARIABLE: {kind: "variable",  value: "corr_value"}   → context.variables["corr_value"]
# STEP_REF: {kind: "step_ref",  value: "node_compute"}  → context.step_outputs["node_compute"]
```

#### validate_node_output() — Two-Tier Policy
| Condition | Tier | Action |
|-----------|------|--------|
| `output_var` declared but NONE output | CRITICAL | Abort node chain |
| `output_var` declared but `value is None` | CRITICAL | Abort node chain |
| DATAFRAME claimed but wrong runtime type | CRITICAL | Abort node chain |
| VISUALIZATION but empty artifact | CRITICAL | Abort node chain |
| Expected type ≠ actual type (value present) | WARN | Continue |
| Empty DataFrame | WARN | Continue |
| Schema column drift | WARN | Continue |

#### Memory Bounds (`execution_context.py`)
| Resource | Limit | Behavior |
|----------|-------|---------|
| Single artifact | 5 MB | Replaced with summary string |
| Artifact count | 20 | Oldest pruned on overflow |
| History entries | 100 | Oldest trimmed on overflow |
| Replan count | 2 | Hard stop, returns `"failed"` |

---

## API Reference

### Normal Mode Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/register` | Create user account |
| `POST` | `/api/login` | Authenticate (sets JWT cookie) |
| `POST` | `/api/logout` | Clear session |
| `GET` | `/api/me` | Current user info |
| `POST` | `/api/upload` | Upload CSV, creates session |
| `POST` | `/api/chat` | Process Normal Mode message |
| `GET` | `/api/sessions` | List user sessions |
| `GET` | `/api/sessions/<id>/messages` | Load session history |
| `GET` | `/api/download-modified` | Download transformed CSV |
| `GET` | `/api/activities` | Activity log |
| `GET` | `/api/code-snippets` | Generated code history |

### Pro Mode Endpoints

#### `POST /api/pro/plan`
Generate a DAG plan for user review.

**Request:**
```json
{
    "message": "Clean data, compute correlations, plot heatmap",
    "session_id": 42,
    "size_override": false
}
```

**Response (plan generated):**
```json
{
    "plan_id": "uuid-...",
    "plan": {
        "nodes": [
            {
                "id": "node_clean",
                "type": "transformation",
                "operation": "drop_missing_values",
                "description": "Drop rows with >50% missing values",
                "depends_on": [],
                "output_var": "df_clean",
                "expected_output_type": "dataframe"
            }
        ],
        "version": 1,
        "replan_count": 0
    },
    "dataset_profile": { ... },
    "node_count": 3
}
```

**Response (dataset too large):**
```json
{
    "warning": "Dataset has 150,000 rows (limit: 100,000). ...",
    "requires_confirmation": true,
    "rows": 150000,
    "max_rows": 100000
}
```
Re-send with `"size_override": true` to proceed.

---

#### `POST /api/pro/approve`
Execute an approved plan.

**Request:**
```json
{ "plan_id": "uuid-..." }
```

**Response:**
```json
{
    "status": "completed",
    "completed_nodes": ["node_clean", "node_corr", "node_heatmap"],
    "failed_nodes": [],
    "skipped_nodes": [],
    "replan_reason": null,
    "summary": "**Analysis complete.** Cleaned 42 missing rows...",
    "metadata": {
        "node_clean": {
            "status": "success",
            "model_used": "llama-3.3-70b-versatile",
            "execution_time_ms": 2341.5,
            "retry_count": 0,
            "warnings": []
        }
    }
}
```

Possible `status` values: `completed` | `partial` | `failed` | `replan_needed`

---

#### `GET /api/pro/status/<plan_id>`
Poll execution state. Returns same shape as `/api/pro/approve`.

---

#### `POST /api/pro/profile`
Get a full dataset profile for the current session.

**Request:**
```json
{ "session_id": 42 }
```

**Response:**
```json
{
    "profile": {
        "rows": 1000, "columns": 8,
        "column_names": [...],
        "numeric_columns": [...],
        "high_correlation_pairs": [
            {"column_a": "x", "column_b": "y", "correlation": 0.94}
        ],
        "warnings": ["High missing rate in column 'age' (23%)"],
        "sampled": false
    }
}
```

---

## Configuration Reference

### `core/config.py` — Pro Mode Settings

```python
# Dataset limits
PRO_MAX_ROWS = 100_000              # rows before size warning
PRO_MAX_CONTENT_LENGTH = 200 * 1024 * 1024  # 200 MB upload cap

# Execution limits
PRO_MAX_DAG_NODES = 20             # max nodes per plan
PRO_NODE_RETRY_LIMIT = 1           # retry once on failure
PRO_EXECUTION_TIMEOUT = 300        # seconds per node (hard timeout)
PRO_MAX_REPLAN_COUNT = 2           # max automatic replans before hard failure

# Memory bounds
PRO_MAX_ARTIFACT_SIZE_BYTES = 5 * 1024 * 1024   # 5 MB per artifact
PRO_MAX_ARTIFACTS = 20             # artifact store size (prunes oldest)
PRO_MAX_HISTORY_ENTRIES = 100      # execution history entries kept

# Model configuration
MODEL_TIERS = {
    "heavy": {...},   # planning, re-planning, summaries
    "mid":   {...},   # code generation, retries
    "light": {...},   # intent classification, complexity detection
}
```

### `config.py` — Flask Settings

```python
SECRET_KEY = os.environ.get("SECRET_KEY", "...")
SQLALCHEMY_DATABASE_URI = "sqlite:///database/copilot.db"
UPLOAD_FOLDER = "uploads"
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB normal mode
JWT_EXPIRY_HOURS = 24
```

---

## Troubleshooting

### Server won't start

```
ModuleNotFoundError: No module named 'flask'
```
→ Run `pip install -r requirements.txt`

### Pro Mode plan returns error

```json
{"error": "Failed to generate plan. Try rephrasing your request."}
```
→ Check `logs_and_debug/api_calls.log` for model response details. Usually caused by an ambiguous request or API rate limit. Try a more specific request.

### Pro Mode execution fails immediately

```
CRITICAL: Node 'X' declared output_var='Y' but produced no output
```
→ The mid-tier model generated code that didn't set `_result`. This triggers retry automatically. If retry also fails, the plan is replanned. Check `logs_and_debug/errors.log`.

### Database errors

```
OperationalError: no such table: users
```
→ Delete `database/copilot.db` and restart — it will be recreated.

### File upload fails (413)

→ File exceeds `MAX_CONTENT_LENGTH` in `config.py`. Increase it or reduce file size.

### Logs

| File | Contents |
|------|----------|
| `logs_and_debug/app.log` | General application events |
| `logs_and_debug/api_calls.log` | Every model API call with timing |
| `logs_and_debug/errors.log` | Errors and tracebacks |
| `logs_and_debug/user_interactions.log` | User chat events |

---

## Deployment Checklist

- [ ] Set `SECRET_KEY` environment variable (don't use default)
- [ ] Set `GROQ_API_KEY` and/or `OPENROUTER_API_KEY` as env vars
- [ ] Set `debug=False` in `run.py`
- [ ] Use a production WSGI server: `gunicorn -w 4 "run:app"`
- [ ] Set up HTTPS reverse proxy (nginx/caddy)
- [ ] Configure log rotation for `logs_and_debug/`
- [ ] Set up `uploads/` and `modified_files/backups/` with appropriate permissions

---

*Data Science Copilot v4.5 — Built with Flask, SQLAlchemy, Groq, OpenRouter*
