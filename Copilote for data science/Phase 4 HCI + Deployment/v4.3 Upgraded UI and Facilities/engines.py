# engines.py -- AI-powered engines with conversation memory (resilient multi-model)
import re, json, base64, io, traceback
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from api_config import client, MODEL_NAME, MODEL_LITE, MODEL_CODER


# =====================================================================
# RESILIENT AI CALL HELPERS
# =====================================================================

def _ai_call(system_prompt, user_content, model=None, temperature=0.2, max_tokens=300):
    """Make an AI call with automatic model fallback.
    Tries: specified model -> MODEL_NAME -> returns None on total failure."""
    models_to_try = []
    if model and model != MODEL_NAME:
        models_to_try.append(model)
    models_to_try.append(MODEL_NAME)

    for m in models_to_try:
        try:
            completion = client.chat.completions.create(
                model=m,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            result = completion.choices[0].message.content
            if result and result.strip():
                return _clean_think_tags(result.strip())
            print(f"  [AI] {m}: empty response, trying next...")
        except Exception as e:
            print(f"  [AI] {m} failed: {e}")
    return None


def _ai_call_messages(messages, model=None, temperature=0.2, max_tokens=300):
    """Make an AI call with message list and automatic model fallback."""
    models_to_try = []
    if model and model != MODEL_NAME:
        models_to_try.append(model)
    models_to_try.append(MODEL_NAME)

    for m in models_to_try:
        try:
            completion = client.chat.completions.create(
                model=m, messages=messages,
                temperature=temperature, max_tokens=max_tokens,
            )
            result = completion.choices[0].message.content
            if result and result.strip():
                return _clean_think_tags(result.strip())
            print(f"  [AI] {m}: empty response, trying next...")
        except Exception as e:
            print(f"  [AI] {m} failed: {e}")
    return None


def _clean_think_tags(text):
    """Remove <think>...</think> tags that qwen3-coder adds."""
    if not text:
        return text
    # Remove think blocks (can be multi-line)
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return cleaned if cleaned else text


# =====================================================================
# CONVERSATION HISTORY HELPERS
# =====================================================================

def format_history(messages, max_messages=10):
    """Format recent messages into a conversation string for AI context."""
    if not messages:
        return ""
    recent = messages[-max_messages:]
    lines = []
    for m in recent:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role == "assistant" and len(content) > 200:
            content = content[:200] + "..."
        lines.append(f"{role.upper()}: {content}")
    return "\n".join(lines)


def format_history_as_messages(messages, max_messages=10):
    """Format recent messages as OpenAI-style message list."""
    if not messages:
        return []
    recent = messages[-max_messages:]
    result = []
    for m in recent:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role == "assistant" and len(content) > 300:
            content = content[:300] + "..."
        result.append({"role": role, "content": content})
    return result


# =====================================================================
# AI INTENT CLASSIFICATION (with strong keyword fallback)
# =====================================================================

def classify_intent(user_input, conversation_history=None):
    """AI-first intent classification. Falls back to robust keywords if AI fails."""
    # First try AI classification
    history_str = format_history(conversation_history) if conversation_history else ""

    sys_prompt = """You are an intent classifier for a data science app. The user works with a CSV dataset.
Classify into exactly ONE category. Reply with ONLY that single word, nothing else.

Categories:
- display: see/show/query data, statistics, find values, compare, describe, count, head, tail
- visualize: chart, plot, graph, histogram, scatter, pie, heatmap, trend, draw
- modify: change/delete/add/drop/rename/sort/fill/clean/transform data
- undo: undo or revert changes
- chat: greeting, general question, or anything not about data operations

Consider conversation history for follow-ups (e.g. "only 5" after "show rows" = display).
Reply with ONLY one word."""

    user_msg = user_input
    if history_str:
        user_msg = f"Conversation:\n{history_str}\n\nNew message: {user_input}"

    raw = _ai_call(sys_prompt, user_msg, model=MODEL_LITE, temperature=0.0, max_tokens=15)
    if raw:
        raw_lower = raw.lower().strip().strip(".")
        for intent in ["display", "visualize", "modify", "undo", "chat"]:
            if intent in raw_lower:
                print(f"  [INTENT] '{user_input}' -> {intent} (AI)")
                return intent
        print(f"  [INTENT] AI returned unexpected: '{raw}', using keyword fallback")

    # Keyword fallback (robust)
    return _keyword_classify(user_input, conversation_history)


def _keyword_classify(user_input, conversation_history=None):
    """Robust keyword-based intent classification."""
    text = user_input.lower().strip()

    # Undo
    if any(kw in text for kw in ["undo", "revert", "rollback", "go back", "restore"]):
        print(f"  [INTENT] '{user_input}' -> undo (keyword)")
        return "undo"

    # Visualize (check before display/modify since "show chart" should be visualize)
    viz_kw = ["plot", "chart", "graph", "histogram", "scatter", "visualize",
              "pie", "heatmap", "boxplot", "box plot", "distribution", "trend",
              "draw", "diagram", "bar graph", "line graph", "area chart",
              "candlestick", "correlation"]
    if any(kw in text for kw in viz_kw):
        print(f"  [INTENT] '{user_input}' -> visualize (keyword)")
        return "visualize"

    # Modify
    modify_phrases = ["add column", "remove column", "delete column", "drop column",
                      "rename column", "fill missing", "fill null", "create column",
                      "drop rows", "remove rows", "delete rows", "drop na", "dropna", "fillna"]
    if any(kw in text for kw in modify_phrases):
        print(f"  [INTENT] '{user_input}' -> modify (phrase)")
        return "modify"

    modify_context = ["delete", "remove", "drop", "add", "change", "update", "filter"]
    context_words = ["column", "col", "row", "field", "missing", "null", "na", "data"]
    for kw in modify_context:
        if kw in text and any(cw in text for cw in context_words):
            print(f"  [INTENT] '{user_input}' -> modify (contextual)")
            return "modify"

    modify_single = ["modify", "rename", "replace", "clean", "merge", "transform",
                     "convert", "sort", "normalize", "encode"]
    if any(kw in text for kw in modify_single):
        print(f"  [INTENT] '{user_input}' -> modify (keyword)")
        return "modify"

    # Display
    display_kw = ["show", "display", "head", "tail", "first", "last", "describe",
                  "info", "statistics", "stats", "rows", "columns", "shape",
                  "preview", "sample", "summary", "dtypes", "types", "count",
                  "unique", "null", "missing", "print", "view", "look",
                  "how many", "how much",
                  "maximum", "minimum", "average", "mean", "total", "sum",
                  "max", "min", "top", "bottom", "largest", "smallest",
                  "highest", "lowest", "find", "get", "list",
                  "compare", "difference"]
    if any(kw in text for kw in display_kw):
        print(f"  [INTENT] '{user_input}' -> display (keyword)")
        return "display"

    # Question words with data context -> display
    question_words = ["what", "which", "where", "when"]
    data_context = ["column", "row", "value", "data", "dataset", "table", "field",
                    "close", "open", "high", "low", "price", "date", "time"]
    if any(qw in text for qw in question_words) and any(dw in text for dw in data_context):
        print(f"  [INTENT] '{user_input}' -> display (question+data)")
        return "display"

    # Short follow-ups with conversation context (e.g. "only 5", "10", "just 3")
    if conversation_history and len(text.split()) <= 3:
        # Check if previous messages had data operations
        recent = [m.get("content", "").lower() for m in (conversation_history or []) if m.get("role") == "user"]
        if recent:
            last_user = recent[-1] if recent else ""
            if any(kw in last_user for kw in ["show", "display", "head", "first", "last", "rows"]):
                print(f"  [INTENT] '{user_input}' -> display (follow-up)")
                return "display"
            if any(kw in last_user for kw in ["plot", "chart", "visualize"]):
                print(f"  [INTENT] '{user_input}' -> visualize (follow-up)")
                return "visualize"

    # Number-only inputs after display context
    if text.strip().isdigit() and conversation_history:
        print(f"  [INTENT] '{user_input}' -> display (number follow-up)")
        return "display"

    print(f"  [INTENT] '{user_input}' -> chat (default)")
    return "chat"


# =====================================================================
# QUERY RESOLUTION
# =====================================================================

def resolve_query(user_input, conversation_history, ctx):
    """Resolve vague/follow-up queries into clear standalone instructions."""
    if not conversation_history:
        return user_input
    # If input is already clear enough, skip resolution
    if len(user_input.split()) >= 5:
        return user_input

    history_str = format_history(conversation_history)

    resolved = _ai_call(
        """You resolve follow-up queries into clear standalone instructions.
Given conversation history and a new message, rewrite it as a clear, complete instruction.
If the message is already clear, return it unchanged.
Return ONLY the resolved instruction, nothing else. No quotes, no explanation.""",
        f"History:\n{history_str}\n\nNew message: {user_input}",
        model=MODEL_LITE, temperature=0.1, max_tokens=100
    )

    if resolved and len(resolved) >= 2:
        resolved = resolved.strip('"').strip("'")
        if resolved.lower() != user_input.lower():
            print(f"  [RESOLVE] '{user_input}' -> '{resolved}'")
        return resolved
    return user_input


# =====================================================================
# DATA CONTEXT
# =====================================================================

def build_data_context(df, file_path):
    """Build dataset context dict and string."""
    info = {
        "file_path": file_path,
        "shape": str(df.shape),
        "dtypes": str(df.dtypes.to_dict()),
        "head": df.head(5).to_string(),
    }
    ctx = (f"File: '{file_path}'\nShape: {info['shape']}\n"
           f"Columns & Types: {info['dtypes']}\nSample rows:\n{info['head']}")
    return info, ctx


# =====================================================================
# DISPLAY CODE GENERATION
# =====================================================================

def generate_display_code(user_input, file_path, ctx, conversation_history=None):
    history_str = format_history(conversation_history) if conversation_history else ""

    sys_prompt = f"""You are a Python code generator for pandas DataFrames. Generate ONLY executable Python code.

Dataset:
{ctx}

{f"Recent conversation:{chr(10)}{history_str}" if history_str else ""}

RULES:
1. import pandas as pd
2. df = pd.read_csv(r'{file_path}')
3. Perform the requested operation
4. Store result in: _result_df (must be DataFrame or Series)
5. For scalar results: _result_df = pd.DataFrame({{"Result": [value]}})
6. Do NOT use print(). ONLY output code in ```python ... ```
7. Use actual column names (CASE-SENSITIVE)."""

    return _ai_call(sys_prompt, f"Request: {user_input}",
                    model=MODEL_CODER, temperature=0.2, max_tokens=4096)


# =====================================================================
# VISUALIZATION
# =====================================================================

def generate_chart_spec(user_input, dtypes_str, conversation_history=None):
    """Ask AI for a JSON chart specification."""
    history_str = format_history(conversation_history) if conversation_history else ""

    sys_prompt = f"""Return ONLY a valid JSON object for a chart specification.

Format: {{"chart_type":"histogram|bar|line|scatter|pie|box|heatmap|area",
 "x":"column_name_or_null", "y":"column_name_or_null",
 "title":"Chart Title", "color":"#58a6ff",
 "multiple_columns":["col1","col2"] or null}}

Dataset columns: {dtypes_str}
{f"Context:{chr(10)}{history_str}" if history_str else ""}

Match chart type to user request. Use actual column names. Return ONLY JSON."""

    raw = _ai_call(sys_prompt, user_input, model=MODEL_LITE, temperature=0.1, max_tokens=300)
    if raw:
        try:
            print(f"  [CHART-SPEC] Raw: {raw[:200]}")
            cleaned = re.sub(r"```json\s*", "", raw)
            cleaned = re.sub(r"```\s*", "", cleaned).strip()
            start, end = cleaned.find("{"), cleaned.rfind("}")
            if start != -1 and end != -1:
                spec = json.loads(cleaned[start:end + 1])
                print(f"  [CHART-SPEC] Parsed: {spec}")
                return spec
        except Exception as e:
            print(f"  [CHART-SPEC] Parse error: {e}")
    return None


def _smart_chart_spec_fallback(user_input, df):
    """When AI fails, use keywords to determine chart type."""
    text = user_input.lower()
    num_cols = df.select_dtypes(include="number").columns.tolist()
    cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()

    if "pie" in text:
        col = cat_cols[0] if cat_cols else (num_cols[0] if num_cols else df.columns[0])
        return {"chart_type": "pie", "x": col, "title": f"Distribution of {col}", "color": "#58a6ff"}
    if "scatter" in text:
        x = num_cols[0] if num_cols else df.columns[0]
        y = num_cols[1] if len(num_cols) >= 2 else x
        return {"chart_type": "scatter", "x": x, "y": y, "title": f"{x} vs {y}", "color": "#58a6ff"}
    if "bar" in text:
        col = cat_cols[0] if cat_cols else (num_cols[0] if num_cols else df.columns[0])
        return {"chart_type": "bar", "x": col, "title": f"Bar Chart of {col}", "color": "#58a6ff"}
    if "line" in text:
        col = num_cols[0] if num_cols else df.columns[0]
        return {"chart_type": "line", "y": col, "title": f"Line Chart of {col}", "color": "#58a6ff"}
    if "box" in text:
        col = num_cols[0] if num_cols else df.columns[0]
        return {"chart_type": "box", "x": col, "title": f"Box Plot of {col}", "color": "#58a6ff"}
    if "heatmap" in text or "correlation" in text:
        return {"chart_type": "heatmap", "title": "Correlation Heatmap", "color": "#58a6ff"}
    if "area" in text:
        col = num_cols[0] if num_cols else df.columns[0]
        return {"chart_type": "area", "x": col, "title": f"Area Chart of {col}", "color": "#58a6ff"}
    # Default: best chart for data
    if len(num_cols) >= 2:
        return {"chart_type": "scatter", "x": num_cols[0], "y": num_cols[1],
                "title": f"{num_cols[0]} vs {num_cols[1]}", "color": "#58a6ff"}
    elif num_cols:
        return {"chart_type": "histogram", "x": num_cols[0],
                "title": f"Distribution of {num_cols[0]}", "color": "#58a6ff"}
    return {"chart_type": "bar", "x": df.columns[0], "title": f"Bar of {df.columns[0]}", "color": "#58a6ff"}


def build_chart(df, spec):
    """Build matplotlib chart from spec. Returns (base64_png, error_msg)."""
    try:
        ct = spec.get("chart_type", "histogram")
        x, y = spec.get("x"), spec.get("y")
        title = spec.get("title", "Chart")
        color = spec.get("color", "#58a6ff")
        multi = spec.get("multiple_columns")

        def _col(name):
            if not name: return None
            if name in df.columns: return name
            for c in df.columns:
                if c.lower() == name.lower(): return c
            return name
        x, y = _col(x), _col(y)

        plt.style.use("dark_background")
        fig, ax = plt.subplots(figsize=(10, 6))
        fig.patch.set_facecolor("#0d1117")
        ax.set_facecolor("#161b22")

        if ct == "histogram":
            col = x or y or df.select_dtypes(include="number").columns[0]
            ax.hist(df[col].dropna(), bins=40, color=color, edgecolor="#30363d", alpha=0.85)
            ax.set_xlabel(col, color="#e6edf3"); ax.set_ylabel("Frequency", color="#e6edf3")
        elif ct == "bar":
            if x and y:
                data = df.groupby(x)[y].mean().head(20)
                data.plot(kind="bar", ax=ax, color=color, edgecolor="#30363d")
            elif x:
                df[x].value_counts().head(20).plot(kind="bar", ax=ax, color=color)
            else:
                df.select_dtypes(include="number").iloc[:, :5].mean().plot(kind="bar", ax=ax, color=color)
            ax.set_ylabel("Value", color="#e6edf3")
        elif ct == "line":
            if multi:
                for c in [_col(c) for c in multi if _col(c) in df.columns][:5]:
                    ax.plot(df[c].values[:500], label=c, linewidth=1.5)
                ax.legend(facecolor="#161b22", edgecolor="#30363d", labelcolor="#e6edf3")
            elif y:
                ax.plot(df[y].values[:500], color=color, linewidth=1.5)
                ax.set_ylabel(y, color="#e6edf3")
            elif x:
                ax.plot(df[x].values[:500], color=color, linewidth=1.5)
            else:
                col = df.select_dtypes(include="number").columns[0]
                ax.plot(df[col].values[:500], color=color, linewidth=1.5)
        elif ct == "scatter":
            xc = x or df.select_dtypes(include="number").columns[0]
            yc = y or df.select_dtypes(include="number").columns[min(1, len(df.select_dtypes(include="number").columns)-1)]
            ax.scatter(df[xc].values[:2000], df[yc].values[:2000], c=color, alpha=0.5, s=12, edgecolors="none")
            ax.set_xlabel(xc, color="#e6edf3"); ax.set_ylabel(yc, color="#e6edf3")
        elif ct == "pie":
            col = x or y or df.columns[0]
            if df[col].dtype in ['int64', 'float64', 'int32', 'float32']:
                n_bins = min(8, max(4, df[col].nunique()))
                if n_bins > 15: n_bins = 8
                counts = pd.cut(df[col].dropna(), bins=n_bins).value_counts().sort_index()
                labels = [str(iv) for iv in counts.index]
            else:
                counts = df[col].value_counts().head(8)
                labels = [str(l)[:20] for l in counts.index]
            colors_list = sns.color_palette("Set2", len(counts))
            wedges, texts, autotexts = ax.pie(
                counts, labels=labels, autopct="%1.1f%%", colors=colors_list,
                textprops={"color": "#e6edf3", "fontsize": 9}, pctdistance=0.8)
            for t in autotexts: t.set_color("#e6edf3"); t.set_fontsize(8)
        elif ct == "box":
            col = x or y or df.select_dtypes(include="number").columns[0]
            ax.boxplot(df[col].dropna(), patch_artist=True,
                       boxprops=dict(facecolor=color, color="#30363d", alpha=0.7),
                       medianprops=dict(color="#f778ba", linewidth=2),
                       whiskerprops=dict(color="#8b949e"), capprops=dict(color="#8b949e"))
            ax.set_xticklabels([col])
        elif ct == "heatmap":
            corr = df.select_dtypes(include="number").corr()
            sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm", ax=ax,
                       linewidths=0.5, annot_kws={"size": 8, "color": "#e6edf3"})
        elif ct == "area":
            col = x or y or df.select_dtypes(include="number").columns[0]
            data_slice = df[col].values[:500]
            ax.fill_between(range(len(data_slice)), data_slice, alpha=0.4, color=color)
            ax.plot(data_slice, color=color, linewidth=1.5)
        else:
            col = df.select_dtypes(include="number").columns[0]
            ax.hist(df[col].dropna(), bins=40, color=color, edgecolor="#30363d")

        ax.set_title(title, color="#f0f6fc", fontsize=14, fontweight="bold", pad=15)
        ax.tick_params(colors="#8b949e")
        for sp in ax.spines.values(): sp.set_color("#30363d")
        plt.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="#0d1117")
        buf.seek(0)
        b64 = base64.b64encode(buf.getvalue()).decode()
        plt.close(fig)
        print(f"  [CHART] Built {ct}: '{title}'")
        return b64, None
    except Exception as e:
        plt.close("all")
        print(f"  [CHART] Error: {e}")
        return None, str(e)


def build_auto_chart(df):
    """Fallback: histogram of first numeric column."""
    try:
        col = df.select_dtypes(include="number").columns[0]
        return build_chart(df, {"chart_type": "histogram", "x": col,
                                "title": f"Distribution of {col}", "color": "#58a6ff"})
    except Exception:
        return None, "No numeric columns"


def generate_visualize_code(user_input, file_path, ctx, conversation_history=None):
    history_str = format_history(conversation_history) if conversation_history else ""
    sys_prompt = f"""Generate ONLY executable matplotlib Python code for a chart.

Dataset:
{ctx}
{f"Conversation:{chr(10)}{history_str}" if history_str else ""}

RULES:
1. import pandas, matplotlib, seaborn
2. df = pd.read_csv(r'{file_path}')
3. Create the chart
4. _result_fig = plt.gcf()
5. Do NOT call plt.show()
6. Use dark theme: plt.style.use('dark_background'), fig.patch.set_facecolor('#0d1117')
7. Wrap code in ```python ... ```"""

    return _ai_call(sys_prompt, f"Request: {user_input}",
                    model=MODEL_CODER, temperature=0.2, max_tokens=4096)


# =====================================================================
# MODIFY CODE
# =====================================================================

def generate_modify_code(user_input, file_path, ctx, conversation_history=None):
    history_str = format_history(conversation_history) if conversation_history else ""
    sys_prompt = f"""Generate ONLY executable Python code to modify a DataFrame.

Dataset:
{ctx}
{f"Conversation:{chr(10)}{history_str}" if history_str else ""}

RULES:
1. import pandas as pd
2. df = pd.read_csv(r'{file_path}')
3. Apply the modification
4. df.to_csv(r'{file_path}', index=False)
5. _result_df = df
6. No print(). Only code in ```python ... ```
7. Use actual column names (CASE-SENSITIVE)."""

    return _ai_call(sys_prompt, f"Request: {user_input}",
                    model=MODEL_CODER, temperature=0.2, max_tokens=4096)


# =====================================================================
# CHAT RESPONSE
# =====================================================================

def generate_chat_response(user_input, ctx="No dataset loaded.", conversation_history=None):
    """Generate a natural conversational response with history."""
    messages = [
        {"role": "system", "content":
            f"You are a friendly Data Science assistant called 'Data Science Copilot'. "
            f"Be conversational and concise (2-4 sentences). "
            f"If the user greets you, greet back warmly. "
            f"If they ask about data, answer using the dataset context. "
            f"No code, no tables.\n\nDataset:\n{ctx}"}
    ]
    if conversation_history:
        messages.extend(format_history_as_messages(conversation_history))
    messages.append({"role": "user", "content": user_input})

    result = _ai_call_messages(messages, model=MODEL_NAME, temperature=0.7, max_tokens=300)
    return result if result else "I'm here to help! Ask me about your data or try 'show 10 rows'."


def generate_result_summary(user_input, operation):
    """Generate a short summary."""
    fallbacks = {
        "display": f"Here are the results for your query. Check the results panel ->",
        "visualize": f"Chart generated! See the results panel ->",
        "modify": f"Modification applied! Preview in the results panel ->",
    }
    fb = fallbacks.get(operation, f"Done! Check the results panel ->")

    result = _ai_call(
        "Write 1 short friendly sentence about what was done. Mention 'results panel'. No code.",
        f"User asked: '{user_input}'. Operation: {operation}.",
        model=MODEL_LITE, temperature=0.3, max_tokens=60
    )
    return result if result and len(result) >= 5 else fb


# =====================================================================
# HELPERS
# =====================================================================

def fix_code(failed_code, error, file_path, ctx):
    sys_prompt = f"""Fix this Python code. Return ONLY the fixed code in ```python ... ```.
Dataset: {ctx}
Error: {error}
Code:\n```python\n{failed_code}\n```"""
    return _ai_call(sys_prompt, "Fix the code.", model=MODEL_CODER, temperature=0.2, max_tokens=4096)


def extract_code(raw):
    """Extract Python code from AI response. Handles <think> tags."""
    if not raw:
        return None
    # Clean think tags first
    text = _clean_think_tags(raw)
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Try fenced code blocks
    for pat in [r"```python3?\s*\n(.*?)```", r"```py\s*\n(.*?)```", r"```\s*\n(.*?)```"]:
        m = re.search(pat, text, re.DOTALL | re.IGNORECASE)
        if m:
            code = m.group(1).strip()
            if code:
                print(f"  [EXTRACT] Fenced code ({len(code)} chars)")
                return code

    # Try without newline
    m = re.search(r"```python3?(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if m:
        code = m.group(1).strip()
        if code:
            print(f"  [EXTRACT] Fenced variant ({len(code)} chars)")
            return code

    # Fallback: lines that look like Python
    lines = text.strip().split("\n")
    code_kw = ["import ", "pd.", "plt.", "df[", "df.", "= pd.", "from ", "_result", "sns."]
    code_lines = []
    started = False
    for line in lines:
        stripped = line.strip()
        if not started:
            if stripped.startswith(("import ", "from ", "df ", "df=", "df[")) or any(k in stripped for k in code_kw):
                started = True
                code_lines.append(line)
        else:
            if stripped.startswith(("Note:", "This ", "The ", "I ", "Here ", "Output", "Explanation")):
                break
            code_lines.append(line)

    if len(code_lines) >= 2:
        code = "\n".join(code_lines).strip()
        print(f"  [EXTRACT] Raw code ({len(code)} chars)")
        return code

    print(f"  [EXTRACT] Failed")
    return None
