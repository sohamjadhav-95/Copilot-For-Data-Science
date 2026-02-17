# engines.py — AI-powered Display, Visualize, Modify, and Chat engines
import re, json
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from api_config import client, MODEL_NAME


# ═══════════════════════════════════════════════════════════════════════
# INTENT CLASSIFICATION — keyword-first, AI-fallback
# ═══════════════════════════════════════════════════════════════════════

_VISUALIZE_KW = [
    "plot", "chart", "graph", "histogram", "scatter", "visualize",
    "bar chart", "line chart", "pie chart", "heatmap", "boxplot",
    "box plot", "distribution", "trend", "draw", "diagram",
    "bar graph", "line graph", "area chart", "candlestick",
]
_DISPLAY_KW = [
    "show", "display", "head", "tail", "first", "last", "describe",
    "info", "statistics", "stats", "rows", "columns", "shape",
    "preview", "sample", "summary", "dtypes", "types", "count",
    "unique", "null", "missing", "print", "view", "look",
    "which", "what", "where", "when", "how many", "how much",
    "maximum", "minimum", "average", "mean", "total", "sum",
    "max", "min", "top", "bottom", "largest", "smallest",
    "difference", "compare", "find", "get", "list", "on which",
]
_MODIFY_KW = [
    "add column", "add a column", "remove column", "delete column",
    "drop column", "rename", "fill", "replace", "clean", "merge",
    "modify", "change", "update", "convert", "transform", "create column",
    "drop rows", "remove rows", "delete rows", "add row", "sort",
    "filter", "fill missing", "fillna", "drop na", "dropna",
]
_UNDO_KW = ["undo", "revert", "rollback", "go back", "restore"]


def classify_intent(user_input):
    """Classify user intent using keyword matching first, AI fallback."""
    text = user_input.lower().strip()

    # Check undo first (most specific)
    for kw in _UNDO_KW:
        if kw in text:
            return "undo"

    # Check visualize (before display, since "show chart" should be visualize)
    for kw in _VISUALIZE_KW:
        if kw in text:
            return "visualize"

    # Check modify
    for kw in _MODIFY_KW:
        if kw in text:
            return "modify"

    # Check display
    for kw in _DISPLAY_KW:
        if kw in text:
            return "display"

    # AI fallback for ambiguous inputs
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": (
                    "Classify intent. Return ONLY one word: "
                    "visualize, display, modify, undo, or chat. "
                    "No quotes, no punctuation, no explanation."
                )},
                {"role": "user", "content": text},
            ],
            temperature=0.0,
            max_tokens=10,
        )
        r = completion.choices[0].message.content.strip().lower()
        for intent in ["visualize", "display", "modify", "undo", "chat"]:
            if intent in r:
                return intent
    except Exception:
        pass
    return "chat"


# ═══════════════════════════════════════════════════════════════════════
# DATA CONTEXT BUILDER
# ═══════════════════════════════════════════════════════════════════════

def _build_data_context(df_info):
    """Build a compact dataset context string for prompts."""
    return (
        f"File Path: '{df_info['file_path']}'\n"
        f"Shape: {df_info['shape']}\n"
        f"Columns & Types: {df_info['dtypes']}\n"
        f"First rows preview:\n{df_info['head']}"
    )


# ═══════════════════════════════════════════════════════════════════════
# DISPLAY CODE GENERATION
# ═══════════════════════════════════════════════════════════════════════

def generate_display_code(user_input, df_info):
    """Generate Python code to display/query the dataset."""
    ctx = _build_data_context(df_info)
    system_prompt = f"""You are a Python code generator. Generate ONLY executable Python code.

Dataset Context:
{ctx}

STRICT RULES:
1. Start with: import pandas as pd
2. Load: df = pd.read_csv(r'{df_info["file_path"]}')
3. Store result in: _result_df (must be DataFrame or Series)
4. Wrap scalars: _result_df = pd.DataFrame({{"Result": [value]}})
5. Do NOT use print()
6. Do NOT add any explanation text
7. Return ONLY code inside ```python ... ```"""

    return _call_code_generation(system_prompt, user_input)


# ═══════════════════════════════════════════════════════════════════════
# VISUALIZATION — JSON SPEC APPROACH
# ═══════════════════════════════════════════════════════════════════════

def generate_chart_spec(user_input, df_info):
    """Ask AI to return a JSON chart specification (not code)."""
    cols = df_info["dtypes"]
    try:
        system_prompt = f"""You are a data visualization advisor. Given a user request about a dataset,
return a JSON object describing the chart to create.

Dataset columns and types: {cols}

Return ONLY a valid JSON object with these fields:
- "chart_type": one of "histogram", "bar", "line", "scatter", "pie", "box", "heatmap", "area"
- "x": column name for x-axis (string or null)
- "y": column name for y-axis (string or null)  
- "title": descriptive chart title (string)
- "color": a nice color like "steelblue", "coral", "seagreen", "#58a6ff" (string)
- "multiple_columns": list of column names if visualizing multiple columns, else null

Example: {{"chart_type": "histogram", "x": "CLOSE", "y": null, "title": "Distribution of Close Prices", "color": "steelblue", "multiple_columns": null}}

Rules:
- Return ONLY the JSON object, no ```json fences, no explanation, no extra text.
- Pick the most appropriate chart type for the request.
- If the user says "visualize columns" or is vague, pick histogram or line chart for numeric columns.
- Use actual column names from the dataset."""

        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ],
            temperature=0.2,
            max_tokens=300,
        )
        raw = completion.choices[0].message.content.strip()

        # Try to extract JSON from the response
        # Remove any markdown fences
        raw = re.sub(r"```json\s*", "", raw)
        raw = re.sub(r"```\s*", "", raw)
        raw = raw.strip()

        # Find first { and last }
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1:
            raw = raw[start:end+1]

        spec = json.loads(raw)
        return spec
    except Exception as e:
        return None


def build_chart(df, spec):
    """Build a matplotlib chart from a JSON spec. Returns (fig, error_msg)."""
    try:
        chart_type = spec.get("chart_type", "histogram")
        x = spec.get("x")
        y = spec.get("y")
        title = spec.get("title", "Chart")
        color = spec.get("color", "steelblue")
        multi_cols = spec.get("multiple_columns")

        # Validate columns exist
        if x and x not in df.columns:
            # Try case-insensitive match
            for c in df.columns:
                if c.lower() == x.lower():
                    x = c
                    break
        if y and y not in df.columns:
            for c in df.columns:
                if c.lower() == y.lower():
                    y = c
                    break

        # Dark theme styling
        plt.style.use("dark_background")
        fig, ax = plt.subplots(figsize=(10, 6))
        fig.patch.set_facecolor("#0d1117")
        ax.set_facecolor("#161b22")

        if chart_type == "histogram":
            col = x or y or df.select_dtypes(include="number").columns[0]
            ax.hist(df[col].dropna(), bins=40, color=color, edgecolor="#30363d", alpha=0.85)
            ax.set_xlabel(col, color="#e6edf3")
            ax.set_ylabel("Frequency", color="#e6edf3")

        elif chart_type == "bar":
            if x and y:
                data = df.groupby(x)[y].mean().head(20)
                data.plot(kind="bar", ax=ax, color=color, edgecolor="#30363d")
            elif x:
                df[x].value_counts().head(20).plot(kind="bar", ax=ax, color=color, edgecolor="#30363d")
            else:
                num_cols = df.select_dtypes(include="number").columns[:5]
                df[num_cols].mean().plot(kind="bar", ax=ax, color=color, edgecolor="#30363d")
            ax.set_ylabel("Value", color="#e6edf3")

        elif chart_type == "line":
            if multi_cols:
                valid_cols = [c for c in multi_cols if c in df.columns]
                for col in valid_cols[:5]:
                    ax.plot(df[col].values[:500], label=col, linewidth=1.5)
                ax.legend(facecolor="#161b22", edgecolor="#30363d")
            elif x and y:
                ax.plot(df[x].values[:500], df[y].values[:500], color=color, linewidth=1.5)
                ax.set_xlabel(x, color="#e6edf3")
                ax.set_ylabel(y, color="#e6edf3")
            elif y:
                ax.plot(df[y].values[:500], color=color, linewidth=1.5)
                ax.set_ylabel(y, color="#e6edf3")
            else:
                col = df.select_dtypes(include="number").columns[0]
                ax.plot(df[col].values[:500], color=color, linewidth=1.5)
                ax.set_ylabel(col, color="#e6edf3")

        elif chart_type == "scatter":
            xcol = x or df.select_dtypes(include="number").columns[0]
            ycol = y or df.select_dtypes(include="number").columns[1]
            ax.scatter(df[xcol].values[:1000], df[ycol].values[:1000],
                       c=color, alpha=0.5, s=10, edgecolors="none")
            ax.set_xlabel(xcol, color="#e6edf3")
            ax.set_ylabel(ycol, color="#e6edf3")

        elif chart_type == "pie":
            col = x or df.columns[0]
            counts = df[col].value_counts().head(8)
            ax.pie(counts, labels=counts.index, autopct="%1.1f%%",
                   colors=sns.color_palette("Set2", len(counts)))

        elif chart_type == "box":
            if multi_cols:
                valid_cols = [c for c in multi_cols if c in df.columns]
                df[valid_cols].boxplot(ax=ax, patch_artist=True,
                    boxprops=dict(facecolor=color, color="#30363d"),
                    medianprops=dict(color="#f778ba"))
            else:
                col = x or y or df.select_dtypes(include="number").columns[0]
                ax.boxplot(df[col].dropna(), patch_artist=True,
                    boxprops=dict(facecolor=color, color="#30363d"),
                    medianprops=dict(color="#f778ba"))
                ax.set_xticklabels([col])

        elif chart_type == "heatmap":
            num_df = df.select_dtypes(include="number")
            corr = num_df.corr()
            sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm",
                        ax=ax, linewidths=0.5, linecolor="#30363d",
                        cbar_kws={"shrink": 0.8})

        elif chart_type == "area":
            col = x or y or df.select_dtypes(include="number").columns[0]
            ax.fill_between(range(min(500, len(df))), df[col].values[:500],
                            alpha=0.5, color=color)
            ax.plot(df[col].values[:500], color=color, linewidth=1)
            ax.set_ylabel(col, color="#e6edf3")

        else:
            # Default: histogram of first numeric column
            col = df.select_dtypes(include="number").columns[0]
            ax.hist(df[col].dropna(), bins=40, color=color, edgecolor="#30363d")

        ax.set_title(title, color="#f0f6fc", fontsize=14, fontweight="bold", pad=15)
        ax.tick_params(colors="#8b949e")
        for spine in ax.spines.values():
            spine.set_color("#30363d")

        plt.tight_layout()
        return fig, None

    except Exception as e:
        plt.close("all")
        return None, str(e)


# ═══════════════════════════════════════════════════════════════════════
# LEGACY VISUALIZE CODE GENERATION (fallback)
# ═══════════════════════════════════════════════════════════════════════

def generate_visualize_code(user_input, df_info):
    """Generate Python code to create a visualization (fallback)."""
    ctx = _build_data_context(df_info)
    system_prompt = f"""You are a Python code generator. Generate ONLY executable matplotlib code.

Dataset Context:
{ctx}

STRICT RULES:
1. Start with imports: import pandas as pd, import matplotlib.pyplot as plt
2. Load: df = pd.read_csv(r'{df_info["file_path"]}')
3. Use plt.figure() and store: _result_fig = plt.gcf()
4. Do NOT call plt.show()
5. Do NOT add any explanation text — ONLY code
6. Return ONLY code inside ```python ... ```"""

    return _call_code_generation(system_prompt, user_input)


# ═══════════════════════════════════════════════════════════════════════
# MODIFY CODE GENERATION
# ═══════════════════════════════════════════════════════════════════════

def generate_modify_code(user_input, df_info):
    """Generate Python code to modify and save the dataset."""
    ctx = _build_data_context(df_info)
    fp = df_info["file_path"]
    system_prompt = f"""You are a Python code generator. Generate ONLY executable Python code.

Dataset Context:
{ctx}

STRICT RULES:
1. Start with: import pandas as pd
2. Load: df = pd.read_csv(r'{fp}')
3. Apply modifications to df
4. Save: df.to_csv(r'{fp}', index=False)
5. Store: _result_df = df
6. Do NOT add any explanation text — ONLY code
7. Return ONLY code inside ```python ... ```"""

    return _call_code_generation(system_prompt, user_input)


# ═══════════════════════════════════════════════════════════════════════
# CHAT RESPONSE
# ═══════════════════════════════════════════════════════════════════════

def generate_chat_response(user_input, df_info=None):
    """Generate a general conversational response."""
    ctx = _build_data_context(df_info) if df_info else "No dataset loaded."
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": (
                    "You are a helpful, friendly Data Science assistant. "
                    "The user has a dataset loaded. Answer their question concisely. "
                    "If they ask about the data, reference the dataset info below. "
                    "Do NOT generate Python code. Do NOT output data tables or dataframes. "
                    "Give a short, helpful TEXT response. 2-4 sentences max.\n\n"
                    f"Dataset info:\n{ctx}"
                )},
                {"role": "user", "content": user_input},
            ],
            temperature=0.7,
            max_tokens=300,
        )
        resp = completion.choices[0].message.content.strip()
        if not resp:
            return "I'm here to help! Try asking about your data, or use commands like 'show first 10 rows' or 'plot a histogram'."
        return resp
    except Exception as e:
        return f"💬 I couldn't generate a response right now. Try asking about your data or use specific commands like 'show first 10 rows'."


def generate_result_summary(user_input, operation, success=True):
    """Generate a short chat-friendly summary of the operation result."""
    # Build a good fallback that always includes what was asked
    fallbacks = {
        "display": f"📊 Displayed results for: *{user_input}* — see the results panel →",
        "visualize": f"📈 Generated chart for: *{user_input}* — see the results panel →",
        "modify": f"✏️ Applied modification: *{user_input}* — preview in the results panel →",
    }
    fallback = fallbacks.get(operation, f"✅ Completed: *{user_input}*")

    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": (
                    "Write exactly 1 sentence describing what data operation was performed. "
                    "Be specific about what was done. Do NOT include code. "
                    "Always mention 'results panel' so user knows where to look. "
                    "Example: 'Displayed the first 10 rows of the dataset in the results panel.'"
                )},
                {"role": "user", "content": (
                    f"User asked: '{user_input}'. "
                    f"Operation type: {operation}. Success: {success}."
                )},
            ],
            temperature=0.3,
            max_tokens=80,
        )
        resp = completion.choices[0].message.content.strip()
        # If AI returned empty or very short, use fallback
        if not resp or len(resp) < 5:
            return fallback
        return resp
    except Exception:
        return fallback


# ═══════════════════════════════════════════════════════════════════════
# CODE FIX + EXTRACT HELPERS
# ═══════════════════════════════════════════════════════════════════════

def fix_code(failed_code, error, df_info):
    """Attempt to fix code that failed execution."""
    ctx = _build_data_context(df_info)
    system_prompt = f"""Fix this Python code. Return ONLY the fixed code inside ```python ... ```.

Dataset: {ctx}
Error: {error}
Code:
```python
{failed_code}
```"""
    return _call_code_generation(system_prompt, "Fix the code.")


def _call_code_generation(system_prompt, user_input):
    """Call the API and return raw generated code string."""
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"User Request: {user_input}"},
            ],
            temperature=0.2,
            max_tokens=4096,
        )
        return completion.choices[0].message.content.strip()
    except Exception:
        return None


def extract_code(raw_response):
    """Extract Python code from a markdown-fenced response."""
    if raw_response is None:
        return None

    text = raw_response.replace("\r\n", "\n").replace("\r", "\n")

    # Try fence patterns
    for pat in [r"```python3?\s*\n(.*?)```", r"```py\s*\n(.*?)```", r"```\s*\n(.*?)```"]:
        match = re.search(pat, text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()

    # Fallback: find lines that look like code
    lines = text.strip().split("\n")
    code_kw = ["import ", "pd.", "plt.", "df[", "df.", "= pd.", "from "]
    code_lines = [l for l in lines if any(kw in l for kw in code_kw)]
    if len(code_lines) >= 2:
        start = 0
        for i, line in enumerate(lines):
            if line.strip().startswith(("import ", "from ")):
                start = i
                break
        return "\n".join(lines[start:]).strip()

    return None
