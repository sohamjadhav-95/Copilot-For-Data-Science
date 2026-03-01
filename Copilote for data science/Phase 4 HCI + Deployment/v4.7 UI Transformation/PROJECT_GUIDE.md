# Data Science Copilot — Project Guide v4.7

> **Enterprise-grade AI analytics platform: Flask REST API + React Material Design UI + Pro DAG execution engine**

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Project Structure](#project-structure)
4. [Installation & Setup](#installation--setup)
5. [Frontend Architecture](#frontend-architecture)
6. [User Guide](#user-guide)
7. [Developer Guide](#developer-guide)
8. [API Reference](#api-reference)
9. [Configuration Reference](#configuration-reference)
10. [Troubleshooting](#troubleshooting)

---

## Overview

Data Science Copilot is a full-stack analytics platform that lets users interact with CSV datasets using natural language. v4.7 brings a complete UI transformation: the old vanilla HTML/JS frontend is replaced by a professional **React + TypeScript + Material Design** application. The Flask backend is refactored into a clean **REST API** with Blueprint modules.

| | Normal Mode | Pro Mode |
|---|---|---|
| **Route** | `/normal` | `/pro` |
| **Use case** | Single-step queries | Multi-step pipelines |
| **Planning** | None | DAG plan generated, user reviews |
| **Execution** | Immediate | Step-by-step with live results |
| **Model tier** | Mid / Light | Heavy → Mid → Light |
| **Results** | AG Grid table or Plotly chart | Per-step inline expand/collapse |
| **Replan** | N/A | Auto-replan up to 2× on failure |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  React Frontend (Vite · TypeScript · TailwindCSS v4)        │
│  localhost:5173                                              │
│                                                             │
│  ┌───────────────────┐  ┌──────────────────────────────┐   │
│  │  Normal Mode      │  │  Pro Workflow Studio          │   │
│  │  AppBar (64px)    │  │  Top Control Bar              │   │
│  │  Sidebar (260px)  │  │  Left Panel (280px)           │   │
│  │  Chat (40%)       │  │  Workspace (fluid)            │   │
│  │  Results (60%)    │  │  Meta Panel (300px)           │   │
│  └───────────────────┘  └──────────────────────────────┘   │
│                                                             │
│  State: Zustand (authStore · sessionStore · proStore)       │
│  API:   Axios with Bearer token interceptor → /api/*        │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP/JSON + Bearer token
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Flask REST API  ·  localhost:5000                           │
│  app.py — slim factory (~50 lines) + CORS                   │
│                                                             │
│  routes/auth_routes.py      /api/register, /login, /logout  │
│  routes/dataset_routes.py   /api/upload, /sessions, ...     │
│  routes/normal_routes.py    /api/chat                        │
│  routes/pro_routes.py       /api/pro/classify, /plan, ...   │
│  routes/profile_routes.py   /api/activities, /provider, ... │
└─────────────┬──────────────────────┬────────────────────────┘
              ▼                      ▼
┌─────────────────────┐  ┌──────────────────────────────────┐
│  engines_normal/    │  │  engines_pro/                    │
│  normal_engine.py   │  │  dag_schema.py   dag_planner.py  │
│  (original logic)   │  │  dag_executor.py validator.py    │
│                     │  │  pro_engine.py (orchestrator)    │
└─────────────────────┘  └──────────────────────────────────┘
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
          │  model_router.py         │  ← tier routing + fallback
          │  groq_models.py          │
          │  openrouter_models.py    │
          └──────────────────────────┘
```

### Model Tiers

| Tier | Role | Primary | Fallback |
|------|------|---------|---------|
| **Heavy** | DAG planning, re-planning, final summaries | Groq DeepSeek R1 | OpenRouter Gemini 2.0 Flash |
| **Mid** | Code generation per node, retries | Groq Llama 3.3 70B | OpenRouter Llama 3.1 70B |
| **Light** | Intent classification, complexity detection | Groq Llama 3.1 8B | OpenRouter Llama 3.1 8B |

### Pro Mode Execution Flow

```
User prompt
    │
    ▼
POST /api/pro/classify  ─── light model → {is_complex: bool}
    │ is_complex = true
    ▼
POST /api/pro/plan  ─── DatasetProfiler + heavy model → DAGPlan JSON
    │
    ▼ (user reviews plan in UI — DAGViewer + PlanApproval)
User clicks "⚡ Approve & Execute"
    │
    ▼
POST /api/pro/approve
    │
    ▼
DAGExecutor.execute()
    ├── topological_sort() → ordered node IDs
    └── for each node:
        ├── generate_node_code()   ─── mid model
        ├── _safe_exec_with_timeout()  ─── sandboxed, hard timeout
        ├── validate_node_output()   ─── CRITICAL vs WARN two-tier
        ├── store in ExecutionContext
        └── ReplanTrigger.check_*()
    │
    ├── if replan_needed → DAGPlanner.replan() (max 2×)
    └── generate_final_summary()  ─── heavy model
         │
         ▼
GET /api/pro/status/<plan_id>  ─── frontend polls every 2s
    │  per-node: {status, output_type, output_payload, duration_ms, model_used}
    ▼
StepCard expands with inline AG Grid / Plotly / JSON on completion
```

---

## Project Structure

```
v4.7 UI Transformation/
│
├── 🚀 Entry Points
│   ├── run.py                        # Flask entry point → localhost:5000
│   ├── app.py                        # App factory (50 lines) — creates Flask + registers blueprints
│   ├── engines.py                    # Re-export shim → engines_normal
│   ├── config.py                     # Flask config (DB, uploads, JWT)
│   └── api_config.py                 # Legacy API config (Normal Mode)
│
├── 🌐 REST API Routes (Blueprints)
│   └── routes/
│       ├── __init__.py               # Blueprint registry
│       ├── auth_routes.py            # register, login, logout, /me  (Bearer token)
│       ├── dataset_routes.py         # upload, sessions, messages, download
│       ├── normal_routes.py          # /api/chat — Normal Mode AI processing
│       ├── pro_routes.py             # /api/pro/classify, /plan, /approve, /status, /profile
│       └── profile_routes.py         # activities, code snippets, model provider switch
│
├── 🧠 Core Infrastructure
│   └── core/
│       ├── config.py                 # Pro Mode config (model tiers, limits)
│       ├── dataset_profiler.py       # DatasetProfiler — full column stats + correlations
│       └── execution_context.py     # ExecutionContext — DAG execution memory
│
├── 🤖 Model API Abstraction
│   └── models_api/
│       ├── model_router.py           # ModelRouter — tier routing + automatic fallback
│       ├── groq_models.py            # Groq API wrapper
│       └── openrouter_models.py      # OpenRouter API wrapper
│
├── ⚙️ Normal Engine (original behavior, unchanged)
│   └── engines_normal/
│       └── normal_engine.py          # Intent classify + all original operation handlers
│
├── 🔬 Pro Engine (DAG system)
│   └── engines_pro/
│       ├── dag_schema.py             # DAGPlan, DAGNode, NodeOutput, ExecutionMetadata
│       ├── validator.py              # Operand resolution, condition eval, output validation
│       ├── dag_planner.py            # Plan generation + re-planning (heavy model)
│       ├── dag_executor.py           # Topological execution, timeout, retry, replan triggers
│       └── pro_engine.py             # Top-level orchestrator, in-memory plan store
│
├── 💾 Database
│   └── database/
│       ├── __init__.py               # SQLAlchemy instance
│       └── models.py                 # User, ChatSession, Message, Activity, CodeSnippet
│
├── 🎨 Frontend (React + Vite)
│   └── frontend/
│       ├── index.html                # SPA root
│       ├── vite.config.ts            # Vite + TailwindCSS plugin + /api proxy
│       ├── tsconfig.json             # TypeScript config (react-jsx)
│       └── src/
│           ├── index.css             # Material Design tokens, elevation, animations
│           ├── App.tsx               # React Router (protected routes)
│           ├── main.tsx              # React 18 root
│           ├── types.d.ts            # Ambient type declarations (CSS, react-plotly.js)
│           │
│           ├── theme/
│           │   └── tokens.ts         # Color palette, elevation presets, spacing
│           │
│           ├── services/
│           │   └── api.ts            # Axios instance with Bearer token interceptor
│           │
│           ├── store/
│           │   ├── authStore.ts      # Auth: login / register / logout + localStorage
│           │   ├── sessionStore.ts   # Sessions, messages, dataset info, file upload
│           │   └── proStore.ts       # Pro workflow: classify → plan → execute → poll
│           │
│           ├── components/
│           │   ├── common/
│           │   │   ├── Button.tsx    # Material button (elevation, ripple, loading)
│           │   │   ├── Card.tsx      # Elevation 0-3, Normal 12px / Pro 6px radius
│           │   │   ├── Badge.tsx     # Chip-style with dot indicator
│           │   │   ├── Skeleton.tsx  # Shimmer loaders
│           │   │   ├── Modal.tsx     # Dialog with scrim + elevation-4
│           │   │   └── ErrorBoundary.tsx
│           │   ├── layout/
│           │   │   ├── AppBar.tsx    # 64px sticky bar, elevation-2, mode-aware accent
│           │   │   └── Sidebar.tsx   # Collapsible sections + SessionList component
│           │   ├── data/
│           │   │   ├── DataTable.tsx      # AG Grid dark theme, toolbar, CSV export
│           │   │   └── InteractiveChart.tsx # Plotly, mode-aware colorway, dark theme
│           │   ├── normal/
│           │   │   ├── ChatPanel.tsx      # Chat bubbles, typing indicator, auto-scroll
│           │   │   └── ResultPanel.tsx    # Dataset stats + table/chart renderer
│           │   └── pro/
│           │       ├── StepCard.tsx       # ★ Expand/collapse step results with inline data
│           │       ├── DAGViewer.tsx      # React Flow visualization with status colors
│           │       ├── ExecutionTracker.tsx # Progress bar + compact step list
│           │       ├── PlanApproval.tsx   # Numbered plan review with Approve button
│           │       └── MetadataPanel.tsx  # Execution stats, model usage, dataset info
│           │
│           ├── layouts/
│           │   ├── NormalLayout.tsx  # AppBar(64px) + Sidebar(260) + Chat(40%) | Results(60%)
│           │   └── ProLayout.tsx     # TopBar + Left(280) + Workspace(fluid) + Meta(300)
│           │
│           └── pages/
│               ├── Login.tsx         # 420px Material card, elevation-3, gradient bg
│               ├── Register.tsx      # Same card style, 4 fields
│               ├── NormalMode.tsx    # Composition page
│               ├── ProWorkspace.tsx  # Full workflow studio
│               └── Settings.tsx      # Account + AI provider switching
│
├── 📊 Data & Logs
│   ├── uploads/                      # User CSV files
│   ├── modified_files/backups/        # Undo backup files
│   └── logs_and_debug/               # Runtime logs (auto-generated)
│
├── 🧪 Tests
│   └── All Tests/
│       ├── test_features.py           # Integration tests
│       ├── test_fixes.py              # Regression tests
│       └── test_classify.py           # Intent classification tests
│
└── 📄 Docs
    ├── PROJECT_GUIDE.md               # This file
    ├── README.md                      # Quick-start card
    └── requirements.txt               # Python dependencies
```

---

## Installation & Setup

### Prerequisites

- Python 3.9+
- Node.js 18+
- npm 9+

### Backend Setup

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Set API keys
set GROQ_API_KEY=gsk_...
set OPENROUTER_API_KEY=sk-or-...
set SECRET_KEY=your-secret-key

# 3. Start Flask
python run.py
# → API server at http://localhost:5000
```

**Core Python dependencies:**

| Package | Purpose |
|---------|---------|
| `flask`, `flask-sqlalchemy`, `flask-cors` | Web framework + ORM + CORS |
| `pyjwt`, `bcrypt` | JWT Bearer token auth |
| `openai` | Groq + OpenRouter API client |
| `pandas`, `numpy` | Data processing |
| `matplotlib`, `seaborn` | Chart generation |
| `scipy`, `scikit-learn` | Advanced analysis (Pro nodes) |

### Frontend Setup

```bash
cd frontend

# Install Node dependencies
npm install

# Start Vite dev server
npm run dev
# → React app at http://localhost:5173
```

The dev server proxies `/api/*` to `http://127.0.0.1:5000` (configured in `vite.config.ts`).

**Build for production:**
```bash
npm run build
# Output in frontend/dist/  — serve via Flask static or CDN
```

---

## Frontend Architecture

### Design System (Material Design)

All styles are driven by CSS custom properties in `src/index.css`:

```
Background:  #0B1220  (base-bg — Deep Slate)
Surface 1:   #111827  (cards, panels)
Surface 2:   #1F2937  (hover, secondary elements)
Divider:     #1E293B  (borders)

Normal accent:  #2563EB  (blue)
Pro accent:     #D4AF37  (gold)

Success: #10B981 · Error: #EF4444 · Warning: #F59E0B · Info: #3B82F6
```

**Elevation system** (4-level Material shadows):
```css
.elevation-1  /* cards */
.elevation-2  /* app bar */
.elevation-3  /* modals, focused inputs */
.elevation-4  /* dialogs */
```

**Typography** — Inter (UI) + JetBrains Mono (data/code).

**Animations** — all 150ms `ease-in-out`, fade-in, slide-down, shimmer skeletons.

### State Management (Zustand)

| Store | Manages |
|-------|---------|
| `authStore` | User auth, JWT token, localStorage persistence |
| `sessionStore` | Chat sessions, messages, dataset info, file upload |
| `proStore` | classify → plan → execute → 2s polling → node status |

### API Service

`src/services/api.ts` — Axios instance with:
- `Authorization: Bearer <token>` injected on every request
- 401 → auto-logout redirect to `/login`
- All typed response interfaces

---

## User Guide

### Normal Mode

Access at `/normal`. Chat interface on the left, results panel on the right.

| Intent | Example phrases |
|--------|----------------|
| **Display** | "show first 10 rows", "summary statistics" |
| **Visualize** | "plot histogram of price", "scatter x vs y" |
| **Modify** | "add column id with row numbers", "fill missing with 0" |
| **Undo** | "undo", "revert last change" |
| **Chat** | "what insights can you give me?" |

Results render immediately in the right panel — tables open in AG Grid with full sort/filter/export, charts render in Plotly with zoom/pan.

### Pro Mode

Access at `/pro`. Paste your goal in the top bar and click **⚡ Analyze**.

**Example requests:**
```
"Clean missing data, compute correlations across all numeric columns, 
 visualize as heatmap, and summarize key findings"

"Build a feature importance analysis, train a regression model, 
 and generate a prediction accuracy report"
```

**Execution flow:**
1. **Classify** — light model determines if complex (Pro) or simple (redirects to Normal)
2. **Plan** — DAG plan generated (3–10 nodes), rendered as a flow graph
3. **Review** — inspect each step (type, operation, dependencies) in the PlanApproval panel
4. **Approve** — click ⚡ Approve & Execute
5. **Live results** — each `StepCard` updates as the node completes; click to expand inline table/chart
6. **Summary** — AI-generated final summary appears when all nodes finish

---

## Developer Guide

### Adding a New Normal Mode Operation

1. Add keyword list to `engines_normal/normal_engine.py`
2. Update `classify_intent()` to detect new keywords
3. Create a `generate_XXX_code()` function
4. Add handler in `routes/normal_routes.py`

### Adding a New Pro Node Type

1. Add to `NodeType` enum in `engines_pro/dag_schema.py`
2. Add corresponding `StepCard` display label if needed in `components/pro/StepCard.tsx`
3. The executor handles execution through `_execute_operation()` — no code change needed

### Adding a New Model Provider

1. Create `models_api/XXX_models.py` with this interface:
   ```python
   def call(messages, model, temperature, max_tokens) -> Optional[str]: ...
   def get_available_models() -> List[str]: ...
   ```
2. Register in `models_api/model_router.py` `_PROVIDER_CHAIN`
3. Add to `profile_routes.py` switch handler

### Key Design Contracts

#### NodeOutput Contract (`dag_schema.py`)
Every DAG node execution must produce a `NodeOutput`:
```python
@dataclass
class NodeOutput:
    output_type: OutputType   # scalar | dataframe | artifact | dict | none
    value: Any                # the actual value
    summary: str              # human-readable description (used for model context)
```

The `output_type` is sent to the frontend as `output_payload` in the status response.
The `StepCard` component renders based on `output_type`:
- `dataframe` → AG Grid table
- `artifact` → Plotly chart (base64 image)
- `scalar`/`text` → formatted text block
- `dict` → JSON code block

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

All endpoints require `Authorization: Bearer <token>` except `/api/register` and `/api/login`.

### Auth Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/register` | Create user account |
| `POST` | `/api/login` | Authenticate → returns `token` |
| `POST` | `/api/logout` | Blacklist token |
| `GET` | `/api/me` | Current user info |

### Dataset Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/upload` | Upload CSV, creates session |
| `GET` | `/api/sessions` | List user sessions |
| `GET` | `/api/sessions/<id>/messages` | Load session history |
| `GET` | `/api/download-modified` | Download transformed CSV |

### Normal Mode Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/chat` | Process Normal Mode message |

### Pro Mode Endpoints

#### `POST /api/pro/classify`
Determine if a prompt should route to Normal or Pro.

**Request:**
```json
{ "message": "...", "session_id": 42 }
```
**Response:**
```json
{ "is_complex": true, "confidence": "high", "reason": "..." }
```

---

#### `POST /api/pro/plan`
Generate a DAG plan.

**Request:**
```json
{ "message": "Clean data, compute correlations, plot heatmap", "session_id": 42 }
```

**Response:**
```json
{
    "plan_id": "uuid-...",
    "plan": {
        "nodes": [
            {
                "node_id": "node_clean",
                "label": "Clean Data",
                "operation": "drop_missing_values",
                "node_type": "transformation",
                "description": "Drop rows with >50% missing values",
                "depends_on": [],
                "output_var": "df_clean",
                "expected_output_type": "dataframe"
            }
        ],
        "user_goal": "...",
        "estimated_cost": "~3 AI calls",
        "version": 1
    },
    "dataset_profile": { ... },
    "node_count": 3
}
```

---

#### `POST /api/pro/approve`
Execute an approved plan (runs asynchronously, poll `/status`).

**Request:** `{ "plan_id": "uuid-..." }`

**Response:**
```json
{
    "status": "completed",
    "completed_nodes": ["node_clean", "node_corr", "node_heatmap"],
    "failed_nodes": [],
    "summary": "**Analysis complete.** ...",
    "metadata": {
        "node_clean": {
            "status": "success",
            "output_type": "dataframe",
            "output_payload": { "columns": [...], "data": [[...]] },
            "model_used": "llama-3.3-70b-versatile",
            "duration_ms": 2341.5,
            "retry_count": 0
        }
    }
}
```

`status` values: `completed` | `partial` | `failed` | `replan_needed`

---

#### `GET /api/pro/status/<plan_id>`
Poll execution state — identical response shape as `/approve`.

---

#### `POST /api/pro/profile`
Get dataset profile for a session.

**Request:** `{ "session_id": 42 }`

---

### Profile Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/activities` | Activity log |
| `GET` | `/api/code-snippets` | Generated code history |
| `GET` | `/api/provider` | Current AI provider |
| `POST` | `/api/provider/switch` | Switch AI provider |

---

## Configuration Reference

### `core/config.py` — Pro Mode Settings

```python
PRO_MAX_ROWS = 100_000              # rows before size warning
PRO_MAX_DAG_NODES = 20             # max nodes per plan
PRO_NODE_RETRY_LIMIT = 1           # retry once on node failure
PRO_EXECUTION_TIMEOUT = 300        # seconds per node (hard timeout)
PRO_MAX_REPLAN_COUNT = 2           # max automatic replans before hard failure
PRO_MAX_ARTIFACT_SIZE_BYTES = 5 * 1024 * 1024   # 5 MB per artifact
PRO_MAX_ARTIFACTS = 20
PRO_MAX_HISTORY_ENTRIES = 100

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
MAX_CONTENT_LENGTH = 50 * 1024 * 1024   # 50 MB
JWT_EXPIRY_HOURS = 24
```

### `frontend/vite.config.ts` — Frontend Settings

```ts
server: {
    proxy: { '/api': 'http://127.0.0.1:5000' }
}
```

---

## Troubleshooting

### Backend

**`ModuleNotFoundError: No module named 'flask'`**
→ Run `pip install -r requirements.txt`

**`ImportError: cannot import name 'X' from 'engines'`**
→ `engines.py` is a re-export shim pointing to `engines_normal`. Verify `engines_normal/normal_engine.py` exports the required function.

**Pro Mode plan returns error:**
```json
{"error": "Failed to generate plan."}
```
→ Check `logs_and_debug/api_calls.log`. Usually API rate limit or ambiguous request. Try a more specific prompt.

**Node execution fails immediately:**
```
CRITICAL: Node 'X' declared output_var='Y' but produced no output
```
→ Triggers retry automatically. If retry also fails → replan. Check `logs_and_debug/errors.log`.

**`OperationalError: no such table: users`**
→ Delete `database/copilot.db` and restart. It will be recreated.

**File upload fails (413)**
→ File exceeds `MAX_CONTENT_LENGTH`. Increase in `config.py` or reduce file size.

### Frontend

**`npm run dev` fails**
→ Run `npm install` first in the `frontend/` directory.

**Blank page at `/`**
→ Check browser console. Ensure Flask backend is running at port 5000 (required for the API proxy).

**AG Grid not rendering**
→ Verify `ag-grid-community` and `ag-grid-react` are installed.

### Logs

| File | Contents |
|------|---------|
| `logs_and_debug/app.log` | General application events |
| `logs_and_debug/api_calls.log` | Every model API call with timing |
| `logs_and_debug/errors.log` | Errors and tracebacks |
| `logs_and_debug/user_interactions.log` | User chat events |

---

## Deployment Checklist

### Backend
- [ ] Set `SECRET_KEY` environment variable (not the default)
- [ ] Set `GROQ_API_KEY` and/or `OPENROUTER_API_KEY` as env vars
- [ ] Set `debug=False` in `run.py`
- [ ] Use production WSGI: `gunicorn -w 4 "app:create_app()"`
- [ ] Set up HTTPS reverse proxy (nginx / Caddy)
- [ ] Configure log rotation for `logs_and_debug/`
- [ ] Set permissions on `uploads/` and `modified_files/backups/`

### Frontend
- [ ] Build: `npm run build` in `frontend/`
- [ ] Serve `frontend/dist/` via Flask static or CDN (Vercel / S3)
- [ ] Update Vite proxy to production API URL before building
- [ ] Set correct `VITE_API_BASE` if using env-based base URLs

---

*Data Science Copilot v4.7 · March 2026 · Flask + React + Material Design*
