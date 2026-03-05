# DataCopilot — Data Science Copilot

> **AI-powered conversational data science platform — Quick Run mode + Pro Workflow Studio DAG engine**

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/flask-3.0-green.svg)](https://flask.palletsprojects.com/)
[![Version](https://img.shields.io/badge/version-4.8-indigo.svg)]()

---

## What It Does

Upload a CSV, ask questions in plain English, get instant results. DataCopilot routes your request to the right engine automatically.

| Mode | What It Handles |
|------|----------------|
| **Quick Run** | Single-step queries — display data, plot charts, modify columns, undo |
| **Workflow Studio (Pro)** | Multi-step pipelines — generates a DAG plan, you approve, it executes step-by-step with live tracking |

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set API keys
set GROQ_API_KEY=gsk_...
set OPENROUTER_API_KEY=sk-or-...
set SECRET_KEY=your-secret-key

# 3. Run
python run.py
```

Open **http://localhost:5000** → register → upload a CSV → start chatting.

---

## Pages & Routes

| Route | Page | Description |
|-------|------|-------------|
| `/dashboard` | Dashboard | Overview, stats, recent activity |
| `/quick-run` | Quick Run | Chat-based single-step analysis |
| `/workflow` | Workflow Studio | Pro DAG planner + executor |
| `/datasets` | Datasets | Upload and manage CSV files |
| `/sessions` | Sessions | Chat history browser |
| `/models` | Plans | Subscription plan tiers |
| `/monitoring` | Monitoring | System health metrics |
| `/settings` | Settings | User preferences |

---

## Quick Run Examples

```
"Show first 10 rows"
"Plot a histogram of price"
"Create a scatter plot of X vs Y"
"Add a column 'id' with row numbers"
"Fill missing values with 0"
"Undo"
"What do you notice about this dataset?"
```

---

## Workflow Studio (Pro Mode)

Navigate to **Workflow Studio** in the sidebar.

**Example request:**
```
"Check for missing data, compute correlations between all numeric columns,
visualize the top correlations as a heatmap, and summarize the findings"
```

**What happens:**
1. A DAG plan appears in the left panel (3–10 steps)
2. Review each step — type, description, dependencies
3. Click **Approve & Execute**
4. Watch the step tracker update in real time per node
5. Read the AI-generated summary in the output panel

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Flask 3.0, SQLAlchemy, SQLite |
| Auth | JWT + bcrypt |
| AI | Groq API, OpenRouter API (OpenAI-compatible) |
| Models | Llama 3.3 70B (mid), DeepSeek R1 (heavy), Llama 3.1 8B (light) |
| Data | Pandas, NumPy, Matplotlib, Seaborn |
| Frontend | Vanilla HTML/CSS/JS · 7-file split CSS design system · Material Symbols |

---

## Project Layout

```
run.py                  App entry point
app.py                  App factory + all routes
engines.py              Re-export shim → engines_normal
config.py               Flask config (DB, uploads, JWT)
api_config.py           Legacy API config

core/                   Dataset profiler, execution context, Pro config
models_api/             Model router — Groq + OpenRouter + fallback
engines_normal/         Quick Run engine (single-step AI operations)
engines_pro/            DAG schema, planner, executor, validator
database/               SQLAlchemy models (User, Session, Message, Activity)

templates/              Jinja2 templates — 11 pages
  base.html             App shell: sidebar nav, topbar, theme toggle
  dashboard.html        Overview page
  quick_run.html        Quick Run chat interface
  workflow.html         Pro Workflow Studio (3-panel DAG layout)
  datasets.html         Dataset management
  sessions.html         Session history
  models.html           Plans & Capabilities page
  monitoring.html       System monitoring
  settings.html         User settings
  login.html / register.html  Auth pages

static/css/             7-file split CSS design system
  base.css              Design tokens, reset, app shell, sidebar, topbar
  components.css        Cards, buttons, badges, forms, tables, modals, auth
  dashboard.css         Dashboard page styles
  quick-run.css         Quick Run / Normal mode styles
  workflow.css          Pro Workflow Studio (scroll-fixed, theme-aware)
  pages.css             Datasets, sessions, plans, monitoring, settings
  responsive.css        All breakpoints

static/js/              Frontend logic
uploads/                User CSV files (per-user dirs)
All Tests/              Integration + regression tests
PROJECT_GUIDE.md        Full developer reference
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | Yes (or OpenRouter) | Groq API key |
| `OPENROUTER_API_KEY` | Yes (or Groq) | OpenRouter API key |
| `SECRET_KEY` | Recommended | JWT signing key (use a random string in production) |

At least one of `GROQ_API_KEY` / `OPENROUTER_API_KEY` must be set. Both enables automatic fallback.

---

## Plans

| Plan | Key Features | Dataset Limit |
|------|-------------|---------------|
| **Free** | Quick Run only, basic profiling, light-tier AI | 25 MB / 100k rows |
| **Pro** | Workflow Studio, DAG execution, heavy-tier reasoning | 500 MB / 5M rows |
| **Ultra** | Multi-agent orchestration, autonomous replanning, local agent | Unlimited |

See the **Plans** page in the app for full feature breakdown.

---

## Execution Limits (Pro Mode)

| Resource | Default |
|----------|---------| 
| Max dataset rows | 100,000 (soft warn + override) |
| Max nodes per plan | 20 |
| Execution timeout per node | 300 s |
| Retry on node failure | 1× |
| Max auto-replans | 2× |
| Max artifact size | 5 MB |

All limits are configurable in `core/config.py`.

---

## Full Documentation

See **[PROJECT_GUIDE.md](PROJECT_GUIDE.md)** for:
- Full architecture diagram and execution flow
- Developer guide (adding operations, node types, model providers)
- Complete API reference with request/response examples
- Configuration reference
- Deployment checklist

---

*v4.8 · March 2026 · Material SaaS UI + Workflow Studio*
