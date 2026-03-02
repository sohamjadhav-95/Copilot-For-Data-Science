# Data Science Copilot

> **AI-powered CSV analysis, visualization, and transformation — now with Pro Mode DAG execution**

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/flask-3.0-green.svg)](https://flask.palletsprojects.com/)

---

## What It Does

Upload a CSV, ask questions in plain English, get instant results.

| Mode | What It Handles |
|------|----------------|
| **Normal** | Single-step queries — display data, plot charts, modify columns, undo |
| **Pro** | Multi-step pipelines — generates a DAG plan, you approve, it executes step-by-step |

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set API keys (or edit core/config.py directly)
set GROQ_API_KEY=gsk_...
set OPENROUTER_API_KEY=sk-or-...
set SECRET_KEY=your-secret-key

# 3. Run
python run.py
```

Open **http://localhost:5000** → register → upload a CSV → start chatting.

---

## Normal Mode Examples

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

## Pro Mode

Toggle the **Normal / Pro** switch in the top navigation bar.

**Example Pro request:**
```
"Check for missing data, compute correlations between all numeric columns,
visualize the top correlations as a heatmap, and summarize the findings"
```

**What happens:**
1. A DAG plan appears in the right panel (3–10 nodes)
2. Review each step — type, description, dependencies
3. Click **Approve & Execute**
4. Watch the Step Tracker update in real time per node
5. Read the AI-generated summary at the end

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Flask 3.0, SQLAlchemy, SQLite |
| Auth | JWT + bcrypt |
| AI | Groq API, OpenRouter API (OpenAI-compatible) |
| Models | Llama 3.3 70B (mid), DeepSeek R1 (heavy), Llama 3.1 8B (light) |
| Data | Pandas, NumPy, Matplotlib, Seaborn |
| Frontend | Vanilla HTML/CSS/JS (no framework) |

---

## Project Layout

```
core/               Dataset profiler, execution context, Pro config
models_api/         Model router with Groq + OpenRouter + fallback
engines_normal/     Normal Mode logic (original, unchanged)
engines_pro/        DAG schema, planner, executor, validator
database/           SQLAlchemy models
templates/          Jinja2 templates (dashboard, login, register)
static/             CSS (dark + Pro enterprise theme) + JS
uploads/            User CSV files
All Tests/          Integration and regression tests
PROJECT_GUIDE.md    Full developer reference
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | Yes (or OpenRouter) | Groq API key |
| `OPENROUTER_API_KEY` | Yes (or Groq) | OpenRouter API key |
| `SECRET_KEY` | Recommended | JWT signing key |

At least one of `GROQ_API_KEY` / `OPENROUTER_API_KEY` must be set. Both enables automatic fallback.

---

## Limits (Pro Mode)

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
- Full architecture diagram
- Pro Mode execution flow
- API reference with request/response examples
- Developer guide (adding operations, node types, model providers)
- Configuration reference
- Deployment checklist

---

*v4.5 · March 2026*
