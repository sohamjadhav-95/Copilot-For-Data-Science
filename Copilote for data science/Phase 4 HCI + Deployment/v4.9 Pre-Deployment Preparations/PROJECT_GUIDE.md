# DataCopilot — Project Guide v4.8

> **Enterprise SaaS AI data science platform — Material Design UI · Quick Run + Pro Workflow Studio DAG Engine**
> Normal Mode (Quick Run): single-step AI operations · Pro Mode (Workflow Studio): multi-step planned DAG pipelines

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Project Structure](#project-structure)
4. [Frontend Design System](#frontend-design-system)
5. [Installation & Setup](#installation--setup)
6. [User Guide](#user-guide)
7. [Developer Guide](#developer-guide)
8. [API Reference](#api-reference)
9. [Configuration Reference](#configuration-reference)
10. [Troubleshooting](#troubleshooting)
11. [Deployment Checklist](#deployment-checklist)

---

## Overview

DataCopilot is a full-stack Flask web application that lets users interact with CSV datasets using natural language. Version 4.8 brings a complete **enterprise SaaS UI overhaul** — a multi-page routed architecture with 8 distinct pages, a 7-file split CSS design system, light/dark theme support, and a redesigned Pro Workflow Studio with scroll-fixed resizable panels.

| | Quick Run | Workflow Studio (Pro) |
|---|---|---|
| **Use case** | Single-step queries | Multi-step analysis pipelines |
| **Planning** | None | DAG plan generated, user approves |
| **Execution** | Immediate | Step-by-step with live tracker |
| **Model tier** | Mid/Light | Heavy→Mid→Light |
| **Replan** | N/A | Auto-replan up to 2× on failure |
| **Plan tier** | Free | Pro / Ultra |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  Browser — Multi-Page SaaS UI (Jinja2 + Vanilla JS)                │
│                                                                     │
│  base.html (App Shell: sidebar nav, topbar, theme toggle)          │
│  ┌──────────────┐  ┌────────────────┐  ┌──────────────────────┐   │
│  │  Dashboard   │  │  Quick Run     │  │  Workflow Studio      │   │
│  │  Datasets    │  │  (chat panel + │  │  (3-panel resizable   │  │
│  │  Sessions    │  │   results)     │  │   DAG layout)         │  │
│  │  Plans       │  └────────────────┘  └──────────────────────┘   │
│  │  Monitoring  │                                                   │
│  │  Settings    │                                                   │
│  └──────────────┘                                                   │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ HTTP/JSON
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Flask (app.py) — Thin routing layer                                │
│                                                                     │
│  Page routes         Normal routes       Pro routes                │
│  /dashboard          /api/chat           /api/pro/plan             │
│  /quick-run          /api/upload         /api/pro/approve          │
│  /workflow           /api/sessions       /api/pro/status/<id>      │
│  /datasets           /api/...            /api/pro/profile          │
│  /sessions, /models                                                │
│  /monitoring, /settings                                            │
└───────────────┬───────────────────────────┬────────────────────────┘
                ▼                           ▼
┌──────────────────────┐    ┌───────────────────────────────────────┐
│  engines_normal/     │    │  engines_pro/                         │
│  normal_engine.py    │    │  ┌───────────┐  ┌──────────────────┐ │
│  (Quick Run logic)   │    │  │ dag_schema│  │  dag_planner     │ │
│                      │    │  │ validator │  │  dag_executor    │ │
│  engines.py          │    │  └───────────┘  └──────────────────┘ │
│  (re-export shim)    │    │  pro_engine.py (orchestrator)         │
└──────────────────────┘    └───────────────────────────────────────┘
               │                           │
               └──────────────┬────────────┘
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
    ▼ (user reviews plan in Workflow Studio UI)
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
v4.8 Materilistic UI + Optimization/
│
├── 🚀 Entry Points
│   ├── run.py                       # Flask application entry point
│   ├── app.py                       # App factory, all routes (Normal + Pro + Pages)
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
├── ⚙️ Normal Engine (Quick Run)
│   └── engines_normal/
│       └── normal_engine.py         # All Quick Run AI operation logic
│
├── 🔬 Pro Engine (Workflow Studio DAG)
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
├── 🎨 Frontend — Multi-Page SaaS UI
│   ├── templates/                   # 11 Jinja2 templates
│   │   ├── base.html                # App shell: nav, topbar, theme toggle, ripple
│   │   ├── dashboard.html           # Overview: stats, metrics, recent activity
│   │   ├── quick_run.html           # Quick Run: chat + resizable results panel
│   │   ├── workflow.html            # Workflow Studio: 3-panel DAG layout (resize, scroll-fix)
│   │   ├── datasets.html            # Dataset upload + management
│   │   ├── sessions.html            # Session history browser
│   │   ├── models.html              # Plans & Capabilities: Free / Pro / Ultra cards
│   │   ├── monitoring.html          # System health metrics
│   │   ├── settings.html            # User preferences
│   │   ├── login.html               # Auth — login
│   │   └── register.html            # Auth — registration
│   │
│   └── static/
│       ├── css/                     # 7-file split design system (load order matters)
│       │   ├── base.css             # CSS variables, reset, app shell, sidebar, topbar
│       │   ├── components.css       # Cards, buttons, badges, forms, tables, modals, auth
│       │   ├── dashboard.css        # Dashboard page only
│       │   ├── quick-run.css        # Quick Run / Normal mode
│       │   ├── workflow.css         # Workflow Studio (theme-aware, scroll-fixed)
│       │   ├── pages.css            # Datasets, sessions, plans, monitoring, settings
│       │   └── responsive.css       # All breakpoints (must load last)
│       └── js/
│           ├── app.js               # Normal + Pro Mode frontend logic
│           └── logger.js            # Frontend structured logger
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
    └── requirements.txt             # Python dependencies
```

---

## Frontend Design System

### CSS Architecture — Load Order

The 7 CSS files must be loaded in this exact order in `base.html`:

```html
<link rel="stylesheet" href="{{ url_for('static', filename='css/base.css') }}">
<link rel="stylesheet" href="{{ url_for('static', filename='css/components.css') }}">
<link rel="stylesheet" href="{{ url_for('static', filename='css/dashboard.css') }}">
<link rel="stylesheet" href="{{ url_for('static', filename='css/quick-run.css') }}">
<link rel="stylesheet" href="{{ url_for('static', filename='css/workflow.css') }}">
<link rel="stylesheet" href="{{ url_for('static', filename='css/pages.css') }}">
<link rel="stylesheet" href="{{ url_for('static', filename='css/responsive.css') }}">
```

`base.css` must be first (defines all CSS variables). `responsive.css` must be last (applies breakpoint overrides). The middle five can target independently per task.

### Theme System

The app ships with light and dark themes toggled via `[data-theme]` on `<html>`:

```js
document.documentElement.setAttribute('data-theme', 'dark');
```

All components use CSS variables (`var(--bg)`, `var(--text-primary)`, `var(--border)`, etc.) — **never hardcoded hex values** (especially in `workflow.css`, which historically used dark hex directly).

### Pro Mode Visual Identity

Pro mode is visually distinct through **gradient accents only** — not forced dark backgrounds:
- `--pro-gradient: linear-gradient(135deg, var(--accent-500), var(--violet-500))`
- Topbar gradient border stripe + indigo glow
- Panel headers gradient left-bar accent
- CTA buttons gradient fill with glow shadow
- Progress bar gradient + animated glow

### Navigation Structure

The sidebar in `base.html` contains 8 nav items. The active page is highlighted via `active_page` Jinja2 variable passed from route handlers.

| Route | `active_page` value | Icon |
|-------|--------|------|
| `/dashboard` | `dashboard` | `dashboard` |
| `/quick-run` | `quick-run` | `bolt` |
| `/workflow` | `workflow` | `account_tree` |
| `/datasets` | `datasets` | `table_chart` |
| `/sessions` | `sessions` | `history` |
| `/models` | `models` | `workspace_premium` |
| `/monitoring` | `monitoring` | `monitoring` |
| `/settings` | `settings` | `settings` |

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
GROQ_API_KEY       = "gsk_..."       # from console.groq.com
OPENROUTER_API_KEY = "sk-or-..."     # from openrouter.ai
```

Or set as environment variables (recommended for production):
```bash
set GROQ_API_KEY=gsk_...
set OPENROUTER_API_KEY=sk-or-...
set SECRET_KEY=your-secret-key
```

### Step 3: Run

```bash
python run.py
```

Server starts at `http://localhost:5000`. Register an account, upload a CSV, and start chatting.

---

## User Guide

### Quick Run

Navigate to **Quick Run** in the sidebar. Upload a CSV, then use the chat input:

| Intent | Example phrases |
|--------|----------------|
| **Display** | "show first 10 rows", "summary statistics" |
| **Visualize** | "plot histogram of price", "scatter x vs y" |
| **Modify** | "add column id with row numbers", "fill missing with 0" |
| **Undo** | "undo", "revert last change" |
| **Chat** | "what insights can you give me?" |

### Workflow Studio (Pro Mode)

Navigate to **Workflow** in the sidebar.

1. **Type a complex multi-step request** in the Plan panel
2. Click **Generate Plan** — the DAG plan appears in the step list
3. **Review steps** — type, description, dependencies shown per step
4. Click **Approve & Execute** — the output panel shows live step execution
5. **Read the summary** — AI-generated report after completion
6. Click **Reject** to dismiss the plan and start over

#### Layout Modes

Three layout toggle buttons in the topbar switch between:
- **Layout 1** — default 3-column (Plan | Graph | Output)
- **Layout 2** — Plan + Output top, Graph bottom
- **Layout 3** — Plan + Graph stacked left, Output full-height right

Each panel can also be expanded to full screen via the **expand** button in the panel header.

#### Workflow Studio Node Types

| Icon | Type | Description |
|------|------|-------------|
| 🔬 | `analysis` | Statistical computation, correlation, profiling |
| ⚙️ | `transformation` | Data cleaning, reshaping, feature engineering |
| 📊 | `visualization` | Chart/plot generation |
| ⑂ | `conditional` | Branch on computed value (if/else) |
| 📝 | `summary` | Aggregate findings, generate text |
| ▶ | `operation` | Generic computation |

### Plans Page

Navigate to **Plans** in the sidebar to see the Free / Pro / Ultra tier comparison.

| Plan | Key Capabilities |
|------|----------------|
| **Free** | Quick Run, basic profiling, light-tier AI, 25 MB datasets |
| **Pro** | Workflow Studio, DAG execution, heavy-tier reasoning, 500 MB |
| **Ultra** | Multi-agent orchestration, autonomous replanning, unlimited (local agent) |

---

## Developer Guide

### Adding a New Quick Run Operation

1. Add keyword list to `engines_normal/normal_engine.py`
2. Update `classify_intent()` to check new keywords
3. Create a `generate_XXX_code()` function
4. Add handler in `app.py` under the `_handle_chat` route

### Adding a New Pro Node Type

1. Add to `NodeType` enum in `engines_pro/dag_schema.py`
2. Add the CSS icon class in `static/css/workflow.css` (`.pro-node-type-XXX`)
3. Add icon to `NODE_ICONS` map in `static/js/app.js`
4. The executor handles all types through `_execute_operation()` — no code change needed

### Adding a New Page

1. Create `templates/XXX.html` extending `base.html`
2. Add a route in `app.py` that passes `active_page="XXX"` to `render_template`
3. Add the nav item in `base.html` sidebar
4. Add page-specific styles to `pages.css` (or a new CSS file if large)

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

### Auth & User Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/register` | Create user account |
| `POST` | `/api/login` | Authenticate (sets JWT cookie) |
| `POST` | `/api/logout` | Clear session |
| `GET` | `/api/me` | Current user info |

### Data Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/upload` | Upload CSV, creates session |
| `GET` | `/api/sessions` | List user sessions |
| `GET` | `/api/sessions/<id>/messages` | Load session history |
| `GET` | `/api/download-modified` | Download transformed CSV |
| `GET` | `/api/activities` | Activity log |
| `GET` | `/api/code-snippets` | Generated code history |

### Quick Run Endpoint

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/chat` | Process Quick Run message |

### Pro / Workflow Studio Endpoints

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
    "dataset_profile": { "..." : "..." },
    "node_count": 3
}
```

**Response (dataset too large):**
```json
{
    "warning": "Dataset has 150,000 rows (limit: 100,000)...",
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
        "column_names": ["..."],
        "numeric_columns": ["..."],
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

```
TypeError: run_simple() got an unexpected keyword argument 'ost'
```
→ Typo in `run.py` — ensure `app.run(host="0.0.0.0", ...)` not `ost=`.

### Pro Mode plan returns error
```json
{"error": "Failed to generate plan. Try rephrasing your request."}
```
→ Check `logs_and_debug/api_calls.log` for model response details. Usually an ambiguous request or API rate limit. Try a more specific request.

### Pro Mode execution fails immediately
```
CRITICAL: Node 'X' declared output_var='Y' but produced no output
```
→ The mid-tier model generated code that didn't set `_result`. This triggers retry automatically. If retry also fails, the plan is replanned. Check `logs_and_debug/errors.log`.

### Page missing CSS / unstyled
→ Check `base.html` — all 7 CSS files must be linked in order. The `{% block body %}` override in auth pages (login, register) bypasses the app shell but still loads the same CSS.

### Database errors
```
OperationalError: no such table: users
```
→ Delete `database/copilot.db` and restart — it will be recreated automatically.

### File upload fails (413)
→ File exceeds `MAX_CONTENT_LENGTH` in `config.py`. Increase it or reduce file size.

### Logs

| File | Contents |
|------|---------|
| `logs_and_debug/app.log` | General application events |
| `logs_and_debug/api_calls.log` | Every model API call with timing |
| `logs_and_debug/errors.log` | Errors and tracebacks |
| `logs_and_debug/user_interactions.log` | User chat events |

---

## Deployment Checklist

- [ ] Set `SECRET_KEY` environment variable (don't use the default)
- [ ] Set `GROQ_API_KEY` and/or `OPENROUTER_API_KEY` as env vars
- [ ] Set `debug=False` in `run.py`
- [ ] Use a production WSGI server: `gunicorn -w 4 "run:app"`
- [ ] Set up HTTPS reverse proxy (nginx / caddy)
- [ ] Configure log rotation for `logs_and_debug/`
- [ ] Set up `uploads/` and `modified_files/backups/` with appropriate permissions
- [ ] Verify all 7 CSS files present in `static/css/`
- [ ] Confirm `static/js/logger.js` is present (loaded in `<head>` before other scripts)

---

*DataCopilot v4.8 — Material SaaS UI · Flask · SQLAlchemy · Groq · OpenRouter*
