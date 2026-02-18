# engines.py -- AI-powered engines with local templates + minimal API calls
import re, json, base64, io, traceback, time
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from api_config import client, MODEL_NAME, MODEL_LITE, MODEL_CODER


# =====================================================================
# RESILIENT AI CALL (with retry + model fallback)
# =====================================================================

def _ai_call(system_prompt, user_content, model=None, temperature=0.2, max_tokens=300, retries=2):
    """AI call with retry + automatic model fallback."""
    models_to_try = []
    if model and model != MODEL_NAME:
        models_to_try.append(model)
    models_to_try.append(MODEL_NAME)

    for m in models_to_try:
        for attempt in range(retries):
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
                print(f"  [AI] {m}: empty response (attempt {attempt+1})")
            except Exception as e:
                err_str = str(e).lower()
                print(f"  [AI] {m} attempt {attempt+1} failed: {e}")
                # If rate limited, wait before retry
                if "rate" in err_str or "429" in err_str or "limit" in err_str:
                    wait = 3 * (attempt + 1)
                    print(f"  [AI] Rate limited, waiting {wait}s...")
                    time.sleep(wait)
                elif attempt < retries - 1:
                    time.sleep(1)
    return None


def _ai_call_messages(messages, model=None, temperature=0.2, max_tokens=300, retries=2):
    """AI call with message list, retry + model fallback."""
    models_to_try = []
    if model and model != MODEL_NAME:
        models_to_try.append(model)
    models_to_try.append(MODEL_NAME)

    for m in models_to_try:
        for attempt in range(retries):
            try:
                completion = client.chat.completions.create(
                    model=m, messages=messages,
                    temperature=temperature, max_tokens=max_tokens,
                )
                result = completion.choices[0].message.content
                if result and result.strip():
                    return _clean_think_tags(result.strip())
            except Exception as e:
                err_str = str(e).lower()
                if "rate" in err_str or "429" in err_str or "limit" in err_str:
                    time.sleep(3 * (attempt + 1))
                elif attempt < retries - 1:
                    time.sleep(1)
    return None


def _clean_think_tags(text):
    """Remove <think>...</think> tags from qwen3-coder."""
    if not text:
        return text
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return cleaned if cleaned else text


# =====================================================================
# CONVERSATION HISTORY
# =====================================================================

def format_history(messages, max_messages=10):
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
    if not messages:
        return []
    recent = messages[-max_messages:]
    return [{"role": m.get("role", "user"),
             "content": m.get("content", "")[:300]} for m in recent]


# =====================================================================
# INTENT CLASSIFICATION (keyword-first, AI only if ambiguous)
# =====================================================================

def classify_intent(user_input, conversation_history=None):
    """Keyword-first intent classification. AI only if ambiguous."""
    # Try keywords first (FREE, instant, reliable)
    intent = _keyword_classify(user_input, conversation_history)
    if intent != "chat":
        return intent

    # For short ambiguous inputs with history, try AI
    if conversation_history and len(user_input.split()) <= 4:
        history_str = format_history(conversation_history)
        raw = _ai_call(
            "Classify intent: display, visualize, modify, undo, or chat. Reply with ONLY one word.",
            f"Context:\n{history_str}\n\nNew: {user_input}",
            model=MODEL_LITE, temperature=0.0, max_tokens=10, retries=1
        )
        if raw:
            for intent in ["display", "visualize", "modify", "undo"]:
                if intent in raw.lower():
                    print(f"  [INTENT] '{user_input}' -> {intent} (AI)")
                    return intent

    return "chat"


def _keyword_classify(user_input, conversation_history=None):
    """Robust keyword classification."""
    text = user_input.lower().strip()

    # Undo
    if any(kw in text for kw in ["undo", "revert", "rollback", "go back", "restore"]):
        print(f"  [INTENT] '{user_input}' -> undo (kw)")
        return "undo"

    # Visualize
    viz_kw = ["plot", "chart", "graph", "histogram", "scatter", "visualize",
              "pie", "heatmap", "boxplot", "box plot", "distribution", "trend",
              "draw", "diagram", "bar graph", "line graph", "area chart",
              "candlestick", "correlation", "lineplot"]
    if any(kw in text for kw in viz_kw):
        print(f"  [INTENT] '{user_input}' -> visualize (kw)")
        return "visualize"

    # Modify phrases
    modify_phrases = ["add column", "remove column", "delete column", "drop column",
                      "rename column", "fill missing", "fill null", "create column",
                      "drop rows", "remove rows", "delete rows", "drop na",
                      "dropna", "fillna", "sort by", "sort the"]
    if any(kw in text for kw in modify_phrases):
        print(f"  [INTENT] '{user_input}' -> modify (phrase)")
        return "modify"

    # Modify context
    modify_verbs = ["delete", "remove", "drop", "add", "change", "update", "filter"]
    context_nouns = ["column", "col", "row", "field", "missing", "null", "na"]
    for kw in modify_verbs:
        if kw in text and any(cw in text for cw in context_nouns):
            print(f"  [INTENT] '{user_input}' -> modify (context)")
            return "modify"

    modify_single = ["modify", "rename", "replace", "clean", "merge", "transform",
                     "convert", "normalize", "encode"]
    if any(kw in text for kw in modify_single):
        print(f"  [INTENT] '{user_input}' -> modify (kw)")
        return "modify"

    # Display (broad)
    display_kw = ["show", "display", "head", "tail", "first", "last", "describe",
                  "info", "statistics", "stats", "rows", "columns", "shape",
                  "preview", "sample", "summary", "dtypes", "types", "count",
                  "unique", "null", "missing", "print", "view", "look",
                  "how many", "how much", "insight",
                  "maximum", "minimum", "average", "mean", "total", "sum",
                  "max", "min", "top", "bottom", "largest", "smallest",
                  "highest", "lowest", "find", "get", "list",
                  "compare", "difference", "on which", "mid"]
    if any(kw in text for kw in display_kw):
        print(f"  [INTENT] '{user_input}' -> display (kw)")
        return "display"

    # Question words + data context
    q_words = ["what", "which", "where", "when", "how"]
    data_words = ["column", "row", "value", "data", "dataset", "table", "field",
                  "close", "open", "high", "low", "price", "date", "time",
                  "day", "movement", "difference", "record", "entry"]
    if any(qw in text for qw in q_words) and any(dw in text for dw in data_words):
        print(f"  [INTENT] '{user_input}' -> display (question+data)")
        return "display"

    # Follow-ups with context
    if conversation_history and len(text.split()) <= 3:
        recent = [m.get("content", "").lower() for m in (conversation_history or [])
                  if m.get("role") == "user"]
        if recent:
            last = recent[-1]
            if any(kw in last for kw in ["show", "display", "head", "first", "last", "rows"]):
                print(f"  [INTENT] '{user_input}' -> display (follow-up)")
                return "display"
            if any(kw in last for kw in ["plot", "chart", "visualize"]):
                print(f"  [INTENT] '{user_input}' -> visualize (follow-up)")
                return "visualize"

    if text.strip().replace(" ", "").isdigit() and conversation_history:
        print(f"  [INTENT] '{user_input}' -> display (number)")
        return "display"

    print(f"  [INTENT] '{user_input}' -> chat (default)")
    return "chat"


# =====================================================================
# LOCAL CODE TEMPLATES (zero API calls!)
# =====================================================================

def _try_local_display(user_input, df, file_path):
    """Try to generate display code locally for common patterns. Returns (code, title) or (None, None)."""
    text = user_input.lower().strip()
    cols = {c.lower(): c for c in df.columns}
    num_cols = df.select_dtypes(include="number").columns.tolist()

    # Find column reference in query
    def _find_col(t):
        for cl, real in cols.items():
            if cl in t:
                return real
        return None

    # show N rows / head N / first N rows
    m = re.search(r"(?:show|display|first|head|top)\s*(\d+)\s*(?:rows?)?", text)
    if m:
        n = int(m.group(1))
        return f"import pandas as pd\ndf = pd.read_csv(r'{file_path}')\n_result_df = df.head({n})", f"First {n} rows"

    # tail N / last N rows
    m = re.search(r"(?:last|tail|bottom)\s*(\d+)\s*(?:rows?)?", text)
    if m:
        n = int(m.group(1))
        return f"import pandas as pd\ndf = pd.read_csv(r'{file_path}')\n_result_df = df.tail({n})", f"Last {n} rows"

    # mid/middle N rows
    m = re.search(r"(?:mid|middle)\s*(\d+)\s*(?:rows?)?", text)
    if m:
        n = int(m.group(1))
        return (f"import pandas as pd\ndf = pd.read_csv(r'{file_path}')\n"
                f"mid = len(df) // 2\n_result_df = df.iloc[mid - {n//2}:mid + {max(n//2, 1)}]",
                f"Middle {n} rows")

    # N rows (just a number + rows)
    m = re.search(r"(\d+)\s*rows?", text)
    if m and "last" not in text and "tail" not in text:
        n = int(m.group(1))
        return f"import pandas as pd\ndf = pd.read_csv(r'{file_path}')\n_result_df = df.head({n})", f"First {n} rows"

    # describe / statistics / summary stats
    if any(kw in text for kw in ["describe", "statistics", "summary stat", "descriptive"]):
        return f"import pandas as pd\ndf = pd.read_csv(r'{file_path}')\n_result_df = df.describe()", "Summary Statistics"

    # columns / dtypes
    if text in ["columns", "show columns", "list columns", "column names", "dtypes", "types"]:
        return (f"import pandas as pd\ndf = pd.read_csv(r'{file_path}')\n"
                f"_result_df = pd.DataFrame({{'Column': df.columns, 'Type': df.dtypes.values.astype(str)}})",
                "Columns & Types")

    # shape
    if text in ["shape", "size", "how many rows", "how big"]:
        return (f"import pandas as pd\ndf = pd.read_csv(r'{file_path}')\n"
                f"_result_df = pd.DataFrame({{'Metric': ['Rows', 'Columns'], 'Value': [df.shape[0], df.shape[1]]}})",
                "Dataset Shape")

    # max of COLUMN
    col = _find_col(text)
    if col and col in num_cols:
        if any(kw in text for kw in ["max", "maximum", "highest", "largest", "biggest"]):
            return (f"import pandas as pd\ndf = pd.read_csv(r'{file_path}')\n"
                    f"val = df['{col}'].max()\n"
                    f"idx = df['{col}'].idxmax()\n"
                    f"_result_df = pd.DataFrame({{'Metric': ['Maximum {col}', 'At Row Index'], 'Value': [val, idx]}})",
                    f"Maximum of {col}")

        if any(kw in text for kw in ["min", "minimum", "lowest", "smallest"]):
            return (f"import pandas as pd\ndf = pd.read_csv(r'{file_path}')\n"
                    f"val = df['{col}'].min()\n"
                    f"idx = df['{col}'].idxmin()\n"
                    f"_result_df = pd.DataFrame({{'Metric': ['Minimum {col}', 'At Row Index'], 'Value': [val, idx]}})",
                    f"Minimum of {col}")

        if any(kw in text for kw in ["mean", "average", "avg"]):
            return (f"import pandas as pd\ndf = pd.read_csv(r'{file_path}')\n"
                    f"_result_df = pd.DataFrame({{'Metric': ['Mean {col}'], 'Value': [df['{col}'].mean()]}})",
                    f"Average of {col}")

    # missing / null count
    if any(kw in text for kw in ["missing", "null", "na count"]):
        return (f"import pandas as pd\ndf = pd.read_csv(r'{file_path}')\n"
                f"missing = df.isnull().sum()\n"
                f"_result_df = pd.DataFrame({{'Column': missing.index, 'Missing Count': missing.values}})",
                "Missing Values")

    # unique values
    if "unique" in text and col:
        return (f"import pandas as pd\ndf = pd.read_csv(r'{file_path}')\n"
                f"_result_df = pd.DataFrame({{'Unique Values': df['{col}'].unique()[:50]}})",
                f"Unique values in {col}")

    return None, None


# =====================================================================
# QUERY RESOLUTION
# =====================================================================

def resolve_query(user_input, conversation_history, ctx):
    """Resolve follow-up queries. Only calls AI for very short ambiguous inputs."""
    if not conversation_history:
        return user_input
    if len(user_input.split()) >= 4:
        return user_input

    # Try local resolution first
    text = user_input.lower().strip()
    recent_user = [m.get("content", "") for m in conversation_history if m.get("role") == "user"]
    if not recent_user:
        return user_input

    last = recent_user[-1].lower()

    # "only N" / "just N" after show/display
    m = re.search(r"(?:only|just)\s*(\d+)", text)
    if m and any(kw in last for kw in ["show", "display", "head", "first", "rows"]):
        n = m.group(1)
        print(f"  [RESOLVE] '{user_input}' -> 'show first {n} rows' (local)")
        return f"show first {n} rows"

    # Pure number after show
    if text.isdigit() and any(kw in last for kw in ["show", "display", "head", "first", "rows"]):
        print(f"  [RESOLVE] '{user_input}' -> 'show first {text} rows' (local)")
        return f"show first {text} rows"

    # AI resolution (only if truly ambiguous, 1 retry)
    history_str = format_history(conversation_history)
    resolved = _ai_call(
        "Resolve follow-up into a clear instruction. Return ONLY the instruction, nothing else.",
        f"History:\n{history_str}\n\nNew: {user_input}",
        model=MODEL_LITE, temperature=0.1, max_tokens=80, retries=1
    )
    if resolved and len(resolved) >= 2:
        resolved = resolved.strip('"').strip("'")
        if resolved.lower() != user_input.lower():
            print(f"  [RESOLVE] '{user_input}' -> '{resolved}' (AI)")
        return resolved
    return user_input


# =====================================================================
# DATA CONTEXT
# =====================================================================

def build_data_context(df, file_path):
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
    sys_prompt = f"""You are a Python code generator for pandas. Generate ONLY executable code.

Dataset:
{ctx}

{f"Conversation:{chr(10)}{history_str}" if history_str else ""}

RULES:
1. import pandas as pd
2. df = pd.read_csv(r'{file_path}')
3. Perform the operation
4. Store in: _result_df (DataFrame or Series)
5. For scalars: _result_df = pd.DataFrame({{"Result": [value]}})
6. NO print(). Code in ```python ... ``` only.
7. Column names are CASE-SENSITIVE."""
    return _ai_call(sys_prompt, f"Request: {user_input}",
                    model=MODEL_CODER, temperature=0.2, max_tokens=2048)


# =====================================================================
# VISUALIZATION
# =====================================================================

def generate_chart_spec(user_input, dtypes_str, conversation_history=None):
    history_str = format_history(conversation_history) if conversation_history else ""
    sys_prompt = f"""Return ONLY a JSON object for a chart.
Format: {{"chart_type":"histogram|bar|line|scatter|pie|box|heatmap|area",
 "x":"col_or_null","y":"col_or_null","title":"Title","color":"#58a6ff",
 "multiple_columns":null}}
Columns: {dtypes_str}
{f"Context:{chr(10)}{history_str}" if history_str else ""}
Match user's chart type. Use real column names. ONLY JSON."""
    raw = _ai_call(sys_prompt, user_input, model=MODEL_LITE, temperature=0.1, max_tokens=200)
    if raw:
        try:
            cleaned = re.sub(r"```json\s*", "", raw)
            cleaned = re.sub(r"```\s*", "", cleaned).strip()
            s, e = cleaned.find("{"), cleaned.rfind("}")
            if s != -1 and e != -1:
                spec = json.loads(cleaned[s:e+1])
                print(f"  [CHART-SPEC] {spec}")
                return spec
        except Exception as ex:
            print(f"  [CHART-SPEC] Parse error: {ex}")
    return None


def _smart_chart_spec_fallback(user_input, df):
    """Keyword-based chart spec (zero API calls)."""
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
    if len(num_cols) >= 2:
        return {"chart_type": "scatter", "x": num_cols[0], "y": num_cols[1],
                "title": f"{num_cols[0]} vs {num_cols[1]}", "color": "#58a6ff"}
    elif num_cols:
        return {"chart_type": "histogram", "x": num_cols[0],
                "title": f"Distribution of {num_cols[0]}", "color": "#58a6ff"}
    return {"chart_type": "bar", "x": df.columns[0], "title": f"Bar of {df.columns[0]}", "color": "#58a6ff"}


def build_chart(df, spec):
    """Build matplotlib chart from spec."""
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
    try:
        col = df.select_dtypes(include="number").columns[0]
        return build_chart(df, {"chart_type": "histogram", "x": col,
                                "title": f"Distribution of {col}", "color": "#58a6ff"})
    except Exception:
        return None, "No numeric columns"


def generate_visualize_code(user_input, file_path, ctx, conversation_history=None):
    history_str = format_history(conversation_history) if conversation_history else ""
    sys_prompt = f"""Generate ONLY matplotlib Python code for a chart.
Dataset:
{ctx}
{f"Conversation:{chr(10)}{history_str}" if history_str else ""}
RULES: import pandas/matplotlib/seaborn, df = pd.read_csv(r'{file_path}'),
create chart, _result_fig = plt.gcf(), NO plt.show(),
dark theme, code in ```python ... ```"""
    return _ai_call(sys_prompt, f"Request: {user_input}",
                    model=MODEL_CODER, temperature=0.2, max_tokens=2048)


# =====================================================================
# MODIFY CODE
# =====================================================================

def generate_modify_code(user_input, file_path, ctx, conversation_history=None):
    history_str = format_history(conversation_history) if conversation_history else ""
    sys_prompt = f"""Generate ONLY Python code to modify a DataFrame.
Dataset:
{ctx}
{f"Conversation:{chr(10)}{history_str}" if history_str else ""}
RULES: import pandas, df = pd.read_csv(r'{file_path}'),
modify, df.to_csv(r'{file_path}', index=False),
_result_df = df, NO print(), code in ```python ... ```"""
    return _ai_call(sys_prompt, f"Request: {user_input}",
                    model=MODEL_CODER, temperature=0.2, max_tokens=2048)


# =====================================================================
# CHAT
# =====================================================================

def generate_chat_response(user_input, ctx="No dataset loaded.", conversation_history=None):
    messages = [
        {"role": "system", "content":
            f"You are a friendly Data Science assistant called 'Data Science Copilot'. "
            f"Be conversational and concise (2-4 sentences). "
            f"If asked about data, use the context. No code, no tables.\n\nDataset:\n{ctx}"}
    ]
    if conversation_history:
        messages.extend(format_history_as_messages(conversation_history))
    messages.append({"role": "user", "content": user_input})
    result = _ai_call_messages(messages, model=MODEL_NAME, temperature=0.7, max_tokens=300)
    return result if result else "I'm here to help! Ask me about your data or try 'show 10 rows'."


def generate_result_summary(user_input, operation):
    """Static summary -- no API calls needed."""
    summaries = {
        "display": f"Displayed results for: *{user_input}* -- see the results panel ->",
        "visualize": f"Chart generated for: *{user_input}* -- see the results panel ->",
        "modify": f"Applied: *{user_input}* -- preview in the results panel ->",
    }
    return summaries.get(operation, f"Done: *{user_input}* -- see results panel ->")


# =====================================================================
# HELPERS
# =====================================================================

def fix_code(failed_code, error, file_path, ctx):
    sys_prompt = f"""Fix this Python code. Return ONLY fixed code in ```python ... ```.
Dataset: {ctx}
Error: {error}
Code:\n```python\n{failed_code}\n```"""
    return _ai_call(sys_prompt, "Fix the code.", model=MODEL_CODER, temperature=0.2, max_tokens=2048)


def extract_code(raw):
    """Extract Python code from AI response."""
    if not raw:
        return None
    text = _clean_think_tags(raw).replace("\r\n", "\n").replace("\r", "\n")

    # Fenced blocks
    for pat in [r"```python3?\s*\n(.*?)```", r"```py\s*\n(.*?)```", r"```\s*\n(.*?)```"]:
        m = re.search(pat, text, re.DOTALL | re.IGNORECASE)
        if m:
            code = m.group(1).strip()
            if code:
                print(f"  [EXTRACT] Fenced ({len(code)} chars)")
                return code

    m = re.search(r"```python3?(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if m:
        code = m.group(1).strip()
        if code:
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
        print(f"  [EXTRACT] Raw ({len(code_lines)} lines)")
        return "\n".join(code_lines).strip()

    print(f"  [EXTRACT] Failed")
    return None
