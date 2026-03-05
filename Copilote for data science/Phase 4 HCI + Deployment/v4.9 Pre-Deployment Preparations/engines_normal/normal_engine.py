# engines.py -- Full AI-powered Data Science Copilot Engine
# v4.4: All operations handled by AI. No hardcoded templates or keyword matching.
# The AI studies the dataset and generates appropriate code for ANY user request.
import re, json, base64, io, traceback, time
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from api_config import get_client, get_model, get_active_provider, auto_fallback_on_error
from logger import log_api_call, log_interaction, log_error, app_logger
from models_api.model_router import ModelRouter

# ModelRouter instance (only used when high_tier toggle is ON)
_router = ModelRouter()

# =====================================================================
# HIGH-TIER TOGGLE — Ultra users can switch to Pro models in Quick Run
# =====================================================================

_high_tier_enabled = False

def set_high_tier(enabled):
    """Enable/disable high-tier model usage in Quick Run (Ultra users only)."""
    global _high_tier_enabled
    _high_tier_enabled = bool(enabled)

def get_high_tier():
    """Check if high-tier models are enabled."""
    return _high_tier_enabled


# =====================================================================
# CODE SAFETY — validate AI-generated code before exec()
# =====================================================================

_DANGEROUS_PATTERNS = [
    r"\bos\.\w+",            # os.system, os.remove, etc.
    r"\bsys\.\w+",           # sys.exit, etc.
    r"\bsubprocess\b",       # subprocess.run, etc.
    r"\b__import__\b",       # __import__('os')
    r"\beval\s*\(",          # eval(...)
    r"\bexec\s*\(",          # nested exec(...)
    r"\bopen\s*\(",          # file open (except pd.read_csv)
    r"\bshutil\b",           # shutil.rmtree, etc.
    r"\bglobals\s*\(",       # globals()
    r"\bcompile\s*\(",       # compile(...)
    r"\bimport\s+os\b",      # import os
    r"\bimport\s+sys\b",     # import sys
    r"\bimport\s+subprocess\b",
    r"\bimport\s+shutil\b",
    r"\bfrom\s+os\b",        # from os import ...
    r"\bfrom\s+sys\b",
]


def _validate_code(code):
    """Check if AI-generated code is safe to execute.
    Returns (is_safe, reason) tuple.
    """
    if not code or not code.strip():
        return False, "Empty code"
    for pattern in _DANGEROUS_PATTERNS:
        match = re.search(pattern, code)
        if match:
            return False, f"Dangerous pattern detected: {match.group()}"
    return True, "OK"


def _safe_exec(code, description="code execution"):
    """Execute code with restricted globals. Returns (namespace, error_or_None)."""
    is_safe, reason = _validate_code(code)
    if not is_safe:
        app_logger.warning(f"[SAFETY] Blocked unsafe code: {reason}")
        log_error(ValueError(reason), context=f"Code validation failed during {description}")
        return {}, f"Code blocked: {reason}"

    restricted_globals = {
        "__builtins__": {
            # Core types
            "range": range, "len": len, "int": int, "float": float, "str": str,
            "bool": bool, "list": list, "dict": dict, "tuple": tuple, "set": set,
            "frozenset": frozenset, "bytes": bytes, "bytearray": bytearray,
            "complex": complex, "slice": slice, "object": object, "type": type,
            # Aggregation / iteration
            "min": min, "max": max, "sum": sum, "abs": abs, "round": round,
            "sorted": sorted, "enumerate": enumerate, "zip": zip, "map": map,
            "filter": filter, "reversed": reversed,
            # Boolean / checking
            "all": all, "any": any, "isinstance": isinstance, "issubclass": issubclass,
            "hasattr": hasattr, "getattr": getattr, "setattr": setattr, "callable": callable,
            # String / repr
            "repr": repr, "chr": chr, "ord": ord, "format": format, "hash": hash, "id": id,
            # Math helpers
            "pow": pow, "divmod": divmod,
            # Suppressed
            "print": lambda *a, **k: None,
            # Exceptions
            "ValueError": ValueError, "TypeError": TypeError,
            "KeyError": KeyError, "IndexError": IndexError,
            "AttributeError": AttributeError, "RuntimeError": RuntimeError,
            "StopIteration": StopIteration, "Exception": Exception,
            # Constants
            "True": True, "False": False, "None": None,
            # Controlled import
            "__import__": _restricted_import,
            # OOP helpers (AI code sometimes uses these)
            "property": property, "staticmethod": staticmethod,
            "classmethod": classmethod, "super": super,
        },
    }
    ns = dict(restricted_globals)
    try:
        exec(code, ns)
        return ns, None
    except Exception as e:
        log_error(e, context=f"Exec failed during {description}")
        return ns, str(e)


def _restricted_import(name, *args, **kwargs):
    """Only allow safe imports."""
    allowed = {"pandas", "numpy", "matplotlib", "matplotlib.pyplot", "matplotlib.dates",
               "seaborn", "math", "statistics", "collections", "datetime", "re",
               "time", "functools", "itertools", "operator", "string", "decimal",
               "copy", "json", "csv", "io", "textwrap", "warnings"}
    if name in allowed:
        return __import__(name, *args, **kwargs)
    raise ImportError(f"Import of '{name}' is not allowed for security reasons")


# =====================================================================
# RESILIENT AI CALL (with retry + model fallback + provider fallback)
# =====================================================================

def _ai_call(system_prompt, user_content, model=None, temperature=0.2, max_tokens=2048, retries=2):
    """AI call for Quick Run — always uses Groq (api_config).
    When high_tier toggle is ON (Ultra users), routes through ModelRouter → NVIDIA.
    """
    # ── High-tier toggle (Ultra): use NVIDIA coding model ──
    if _high_tier_enabled:
        app_logger.info("[AI] High-tier ON → routing via ModelRouter (coding)")
        result = _router.call_with_system(
            task="coding",
            system_prompt=system_prompt,
            user_content=user_content,
            temperature=temperature,
            max_tokens=max_tokens,
            retries=retries,
        )
        if result:
            return _clean_think_tags(result)
        app_logger.warning("[AI] High-tier routing failed, falling back to Groq")

    # ── Default: always use Groq via api_config ──
    role = "primary"
    if model:
        for r in ("lite", "coder", "primary"):
            if model == get_model(r):
                role = r
                break

    models_to_try = []
    requested = model or get_model("primary")
    if requested != get_model("primary"):
        models_to_try.append(requested)
    models_to_try.append(get_model("primary"))

    provider_attempts = 0
    max_provider_switches = 1

    while provider_attempts <= max_provider_switches:
        current_provider = get_active_provider()

        for m in models_to_try:
            for attempt in range(retries):
                t0 = time.time()
                try:
                    completion = get_client().chat.completions.create(
                        model=m,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_content},
                        ],
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    elapsed = (time.time() - t0) * 1000
                    result = completion.choices[0].message.content
                    if result and result.strip():
                        cleaned = _clean_think_tags(result.strip())
                        log_api_call(
                            current_provider, m,
                            user_content[:200], cleaned[:300],
                            elapsed, status="success",
                        )
                        return cleaned
                    log_api_call(current_provider, m, user_content[:200], "",
                                 elapsed, status="empty_response")
                    app_logger.warning(f"[AI] {m}: empty response (attempt {attempt+1})")
                except Exception as e:
                    elapsed = (time.time() - t0) * 1000
                    err_str = str(e).lower()
                    log_api_call(current_provider, m, user_content[:200], "",
                                 elapsed, status="error", error=str(e))
                    app_logger.warning(f"[AI] {current_provider}/{m} attempt {attempt+1} failed: {e}")

                    if "rate" in err_str or "429" in err_str or "limit" in err_str:
                        wait = 3 * (attempt + 1)
                        app_logger.info(f"[AI] Rate limited, waiting {wait}s...")
                        time.sleep(wait)
                    elif attempt < retries - 1:
                        time.sleep(1)

        # All models failed → try switching provider
        new_provider = auto_fallback_on_error()
        if new_provider and provider_attempts < max_provider_switches:
            app_logger.info(f"[AI] Switching provider: {current_provider} -> {new_provider}")
            models_to_try = []
            requested_new = get_model(role)
            if requested_new != get_model("primary"):
                models_to_try.append(requested_new)
            models_to_try.append(get_model("primary"))
            provider_attempts += 1
        else:
            break

    log_error(RuntimeError("All AI call attempts exhausted"),
              context=f"prompt={user_content[:100]}")
    return None


def _ai_call_messages(messages, model=None, temperature=0.2, max_tokens=2048, retries=2):
    """AI call with message list — always uses Groq.
    When high_tier toggle is ON, routes through ModelRouter → NVIDIA.
    """
    # ── High-tier toggle (Ultra): use NVIDIA coding model ──
    if _high_tier_enabled:
        app_logger.info("[AI] High-tier ON → routing messages via ModelRouter (coding)")
        result = _router.call(
            task="coding",
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            retries=retries,
        )
        if result:
            return _clean_think_tags(result)
        app_logger.warning("[AI] High-tier messages routing failed, falling back")

    # ── Default: always use Groq via api_config ──
    role = "primary"
    if model:
        for r in ("lite", "coder", "primary"):
            if model == get_model(r):
                role = r
                break

    models_to_try = []
    requested = model or get_model("primary")
    if requested != get_model("primary"):
        models_to_try.append(requested)
    models_to_try.append(get_model("primary"))

    provider_attempts = 0
    max_provider_switches = 1

    while provider_attempts <= max_provider_switches:
        current_provider = get_active_provider()

        for m in models_to_try:
            for attempt in range(retries):
                t0 = time.time()
                try:
                    completion = get_client().chat.completions.create(
                        model=m, messages=messages,
                        temperature=temperature, max_tokens=max_tokens,
                    )
                    elapsed = (time.time() - t0) * 1000
                    result = completion.choices[0].message.content
                    if result and result.strip():
                        cleaned = _clean_think_tags(result.strip())
                        prompt_preview = str(messages[-1].get("content", ""))[:200] if messages else ""
                        log_api_call(current_provider, m, prompt_preview,
                                     cleaned[:300], elapsed, status="success")
                        return cleaned
                    log_api_call(current_provider, m, "", "", (time.time() - t0) * 1000,
                                 status="empty_response")
                except Exception as e:
                    elapsed = (time.time() - t0) * 1000
                    err_str = str(e).lower()
                    log_api_call(current_provider, m, "", "", elapsed,
                                 status="error", error=str(e))
                    app_logger.warning(f"[AI] {current_provider}/{m} attempt {attempt+1} failed: {e}")
                    if "rate" in err_str or "429" in err_str or "limit" in err_str:
                        time.sleep(3 * (attempt + 1))
                    elif attempt < retries - 1:
                        time.sleep(1)

        new_provider = auto_fallback_on_error()
        if new_provider and provider_attempts < max_provider_switches:
            app_logger.info(f"[AI] Switching provider: {current_provider} -> {new_provider}")
            models_to_try = []
            requested_new = get_model(role)
            if requested_new != get_model("primary"):
                models_to_try.append(requested_new)
            models_to_try.append(get_model("primary"))
            provider_attempts += 1
        else:
            break

    log_error(RuntimeError("All AI call_messages attempts exhausted"),
              context="messages call")
    return None


def _clean_think_tags(text):
    """Remove <think>...</think> tags from thinking models."""
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
        if role == "assistant" and len(content) > 300:
            content = content[:300] + "..."
        lines.append(f"{role.upper()}: {content}")
    return "\n".join(lines)


def format_history_as_messages(messages, max_messages=10):
    if not messages:
        return []
    recent = messages[-max_messages:]
    return [{"role": m.get("role", "user"),
             "content": m.get("content", "")[:500]} for m in recent]


# =====================================================================
# INTENT CLASSIFICATION — Fully AI-driven
# =====================================================================

def classify_intent(user_input, conversation_history=None):
    """Keyword-first + AI intent classification. Keyword handles most cases instantly.
    Returns: 'display' | 'visualize' | 'modify' | 'undo' | 'chat'
    """
    # Step 1: Try keyword classification (instant, free, reliable)
    kw_intent = _keyword_classify(user_input, conversation_history)
    if kw_intent != "chat":
        app_logger.info(f"[INTENT] '{user_input}' -> {kw_intent} (keyword)")
        log_interaction(user_input, kw_intent, user_input, "keyword_classification", True)
        return kw_intent

    # Step 2: For ambiguous inputs, use AI
    history_str = format_history(conversation_history) if conversation_history else ""

    sys_prompt = """You are an intent classifier for a Data Science Copilot application.

Given a user's message about a dataset, classify it into EXACTLY ONE of these categories:

- **display**: User wants to SEE data, statistics, values, rows, columns, aggregations, comparisons, insights, analysis results, or any computation that returns data/numbers.
- **visualize**: User wants to CREATE a chart, plot, graph, or any visual representation.
- **modify**: User wants to CHANGE the dataset (add/remove columns, clean, transform, etc.).
- **undo**: User wants to REVERT the last change.
- **chat**: User is greeting, asking general questions, or making conversation.

Reply with ONLY the single word: display, visualize, modify, undo, or chat. Nothing else."""

    user_msg = f"{f'Conversation context:{chr(10)}{history_str}{chr(10)}{chr(10)}' if history_str else ''}User message: {user_input}"

    raw = _ai_call(sys_prompt, user_msg,
                   model=get_model("lite"), temperature=0.0, max_tokens=20, retries=2)

    if raw:
        raw_lower = raw.lower().strip().strip(".")
        for intent in ["display", "visualize", "modify", "undo", "chat"]:
            if intent in raw_lower:
                app_logger.info(f"[INTENT] '{user_input}' -> {intent} (AI)")
                log_interaction(user_input, intent, user_input, "ai_classification", True)
                return intent

    # Fallback: default to chat
    app_logger.warning(f"[INTENT] '{user_input}' -> chat (default)")
    log_interaction(user_input, "chat", user_input, "fallback", True, "AI classification failed")
    return "chat"


def _keyword_classify(user_input, conversation_history=None):
    """Robust keyword-based intent classification — instant, zero API calls."""
    text = user_input.lower().strip()

    # Undo
    if any(kw in text for kw in ["undo", "revert", "rollback", "go back", "restore"]):
        return "undo"

    # Visualize (check before display since "show chart" = visualize)
    viz_kw = ["plot", "chart", "graph", "histogram", "scatter", "visualize",
              "pie", "heatmap", "boxplot", "box plot", "distribution", "trend",
              "draw", "diagram", "bar graph", "line graph", "area chart",
              "candlestick", "correlation", "lineplot"]
    if any(kw in text for kw in viz_kw):
        return "visualize"

    # Modify phrases
    modify_phrases = ["add column", "remove column", "delete column", "drop column",
                      "rename column", "fill missing", "fill null", "create column",
                      "drop rows", "remove rows", "delete rows", "drop na",
                      "dropna", "fillna", "sort by", "sort the"]
    if any(kw in text for kw in modify_phrases):
        return "modify"

    # Modify context (verb + data noun)
    modify_verbs = ["delete", "remove", "drop", "add", "change", "update", "filter"]
    context_nouns = ["column", "col", "row", "field", "missing", "null", "na"]
    for kw in modify_verbs:
        if kw in text and any(cw in text for cw in context_nouns):
            return "modify"

    modify_single = ["modify", "rename", "replace", "clean", "merge", "transform",
                     "convert", "normalize", "encode"]
    if any(kw in text for kw in modify_single):
        return "modify"

    # ─── CHAT PRIORITY: catch conversational/descriptive queries BEFORE display ───
    # These phrases indicate the user wants a TEXT explanation, not a table/code output
    chat_phrases = [
        "in words", "in plain", "in simple", "in english", "in text",
        "tell me about", "tell me summary", "tell me what",
        "explain", "what is this data",
        "what does this data", "what kind of data", "what type of data",
        "what is the data", "describe this data", "describe the data",
        "can you explain", "what can you tell",
        "help me understand", "summarize in", "summary in",
        "overview of", "brief about", "brief of",
        "give me summary", "give me overview", "provide summary", "provide overview",
        "in detail", "in brief", "in short",
        "about this dataset", "about the dataset", "about this data",
        "about my data", "what do you see", "what do you think",
        "your thoughts", "your analysis", "analyze this",
        "insights about", "insight about", "observations",
    ]
    if any(phrase in text for phrase in chat_phrases):
        return "chat"

    # Pure conversational — greetings, thanks, questions without data-action intent
    chat_starters = ["hi", "hello", "hey", "thanks", "thank you", "ok", "okay",
                     "great", "nice", "good", "cool", "awesome", "sure", "yes", "no",
                     "who are you", "what can you do", "how are you",
                     "what are you", "help"]
    if text in chat_starters or any(text.startswith(s + " ") for s in ["hi", "hello", "hey"]):
        return "chat"

    # Display (broad — catches most data queries that need CODE execution)
    display_kw = ["show", "display", "head", "tail", "first", "last", "describe",
                  "info", "statistics", "stats", "rows", "columns", "shape",
                  "preview", "sample", "summary", "dtypes", "types", "count",
                  "unique", "null", "missing", "print", "view", "look",
                  "how many", "how much",
                  "maximum", "minimum", "average", "mean", "total", "sum",
                  "max", "min", "top", "bottom", "largest", "smallest",
                  "highest", "lowest", "find", "get", "list",
                  "compare", "difference", "on which", "mid", "range"]
    if any(kw in text for kw in display_kw):
        return "display"

    # Question words + data-related context → display (needs code to compute)
    q_words = ["what", "which", "where", "when", "how"]
    data_words = ["column", "row", "value", "table", "field",
                  "close", "open", "high", "low", "price", "date", "time",
                  "day", "movement", "record", "entry",
                  "pct", "change", "index", "timestamp"]
    if any(qw in text for qw in q_words) and any(dw in text for dw in data_words):
        return "display"

    # Follow-up context
    if conversation_history and len(text.split()) <= 3:
        recent = [m.get("content", "").lower() for m in (conversation_history or [])
                  if m.get("role") == "user"]
        if recent:
            last = recent[-1]
            if any(kw in last for kw in ["show", "display", "head", "first", "last", "rows"]):
                return "display"
            if any(kw in last for kw in ["plot", "chart", "visualize"]):
                return "visualize"

    # Number-only follow-up
    if text.strip().replace(" ", "").isdigit() and conversation_history:
        return "display"

    return "chat"


# =====================================================================
# QUERY RESOLUTION — AI-powered follow-up handling
# =====================================================================

def resolve_query(user_input, conversation_history, ctx):
    """Resolve vague/follow-up queries into clear, actionable instructions using AI."""
    if not conversation_history:
        return user_input

    # Only resolve short/ambiguous inputs (likely follow-ups)
    if len(user_input.split()) >= 8:
        return user_input

    history_str = format_history(conversation_history)

    sys_prompt = """You are a query resolver for a Data Science Copilot.

The user may send follow-up messages that reference previous conversation context (e.g., "do that again", "but for column X", "only 5", "show more", "now plot it").

Your job: resolve the follow-up into a CLEAR, SELF-CONTAINED instruction that can be understood WITHOUT the conversation history.

Rules:
- If the message is already clear and self-contained, return it EXACTLY as-is.
- If it's a follow-up, rewrite it to include the full context.
- Return ONLY the resolved instruction, nothing else.
- Do NOT add explanations or commentary."""

    resolved = _ai_call(
        sys_prompt,
        f"Conversation:\n{history_str}\n\nNew message: {user_input}",
        model=get_model("primary"), temperature=0.1, max_tokens=150, retries=1
    )

    if resolved and len(resolved) >= 2:
        resolved = resolved.strip('"').strip("'").strip()
        if resolved.lower() != user_input.lower():
            app_logger.info(f"[RESOLVE] '{user_input}' -> '{resolved}'")
        return resolved

    return user_input


# =====================================================================
# DATA CONTEXT — Rich context for AI to understand the dataset
# =====================================================================

def build_data_context(df, file_path):
    """Build rich data context so AI truly understands the dataset."""
    num_cols = df.select_dtypes(include="number").columns.tolist()
    cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
    date_cols = []
    for c in df.columns:
        if df[c].dtype == "object":
            try:
                pd.to_datetime(df[c].head(5), errors="raise")
                date_cols.append(c)
            except Exception:
                pass

    info = {
        "file_path": file_path,
        "shape": str(df.shape),
        "dtypes": str(df.dtypes.to_dict()),
        "head": df.head(5).to_string(),
    }

    ctx_parts = [
        f"CSV File: '{file_path}'",
        f"Shape: {df.shape[0]} rows × {df.shape[1]} columns",
        f"",
        f"Column Names & Types:",
    ]

    for c in df.columns:
        dtype = str(df[c].dtype)
        null_count = int(df[c].isnull().sum())
        null_pct = f" ({null_count / len(df) * 100:.1f}% missing)" if null_count > 0 else ""
        if c in num_cols:
            try:
                ctx_parts.append(
                    f"  - '{c}' ({dtype}): range [{df[c].min():.6g} .. {df[c].max():.6g}], "
                    f"mean={df[c].mean():.6g}{null_pct}"
                )
            except Exception:
                ctx_parts.append(f"  - '{c}' ({dtype}){null_pct}")
        elif c in date_cols:
            ctx_parts.append(f"  - '{c}' (date-like string){null_pct}")
        else:
            n_unique = df[c].nunique()
            samples = df[c].dropna().unique()[:5]
            ctx_parts.append(
                f"  - '{c}' ({dtype}): {n_unique} unique values, "
                f"samples={[str(v)[:30] for v in samples]}{null_pct}"
            )

    if date_cols:
        ctx_parts.append(f"\nPossible date columns: {date_cols}")

    ctx_parts.append(f"\nSample data (first 5 rows):\n{info['head']}")

    ctx = "\n".join(ctx_parts)
    return info, ctx


# =====================================================================
# DISPLAY CODE GENERATION — AI generates pandas code
# =====================================================================

def generate_display_code(user_input, file_path, ctx, conversation_history=None):
    """Generate Python/pandas code to display or analyze data."""
    history_str = format_history(conversation_history) if conversation_history else ""

    sys_prompt = f"""You are an expert Python/pandas code generator for a Data Science Copilot.
The user wants to view, analyze, or extract information from a dataset.

DATASET INFORMATION:
{ctx}

{f"CONVERSATION CONTEXT:{chr(10)}{history_str}" if history_str else ""}

YOUR TASK: Generate executable Python code that answers the user's request.

STRICT RULES:
1. Start with: import pandas as pd
2. Load data: df = pd.read_csv(r'{file_path}')
3. Perform the requested analysis/operation
4. Store the final result in: _result_df
5. _result_df MUST be a pandas DataFrame (or Series, which will be auto-converted)
6. For scalar results: _result_df = pd.DataFrame({{"Result": [value]}})
7. For multiple metrics: _result_df = pd.DataFrame({{"Metric": [...], "Value": [...]}})
8. Column names are CASE-SENSITIVE — use EXACT names from the dataset info above.
9. Handle potential errors: check if columns exist, handle NaN values.
10. For date operations, convert strings to datetime with pd.to_datetime().
11. NO print() statements.
12. NO plt.show() or visualization code.
13. Return code inside ```python ... ``` block ONLY.
14. Think step by step about what the user wants, then generate precise code."""

    return _ai_call(sys_prompt, f"User request: {user_input}",
                    model=get_model("coder"), temperature=0.2, max_tokens=3000)


# =====================================================================
# VISUALIZATION CODE GENERATION — AI generates matplotlib code
# =====================================================================

def generate_chart_code(user_input, file_path, ctx, conversation_history=None):
    """Generate Python/matplotlib code to create ANY visualization — simple or complex."""
    history_str = format_history(conversation_history) if conversation_history else ""

    sys_prompt = f"""You are an EXPERT Python data visualization engineer. You create professional, publication-quality charts.
The user wants a visualization from their dataset. You MUST handle simple AND complex requests.

DATASET INFORMATION:
{ctx}

{f"CONVERSATION CONTEXT:{chr(10)}{history_str}" if history_str else ""}

YOUR TASK: Generate complete, executable Python code for the requested visualization.

═══════════════════════════════════════════════════════
MANDATORY CODE STRUCTURE:
═══════════════════════════════════════════════════════
```python
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import numpy as np

df = pd.read_csv(r'{file_path}')

# Apply dark theme
plt.style.use('dark_background')
fig, ax = plt.subplots(figsize=(12, 6))
fig.patch.set_facecolor('#0d1117')
ax.set_facecolor('#161b22')

# ... your visualization code ...

# Style spines, ticks, labels
for spine in ax.spines.values():
    spine.set_color('#30363d')
ax.tick_params(colors='#8b949e')
ax.set_title('Title', color='#f0f6fc', fontsize=14, fontweight='bold', pad=12)
ax.set_xlabel('X Label', color='#e6edf3')
ax.set_ylabel('Y Label', color='#e6edf3')

plt.tight_layout()
_result_fig = plt.gcf()
```

═══════════════════════════════════════════════════════
VISUALIZATION CAPABILITIES (you MUST support ALL):
═══════════════════════════════════════════════════════

MULTI-LINE / COMPARISON PLOTS:
- Plot multiple columns as separate lines on the SAME axes
- Example: "Compare HIGH and LOW over time" →
    ax.plot(df.index, df['HIGH'], label='HIGH', color='#58a6ff', linewidth=1.5)
    ax.plot(df.index, df['LOW'], label='LOW', color='#f778ba', linewidth=1.5)
    ax.legend()
- ALWAYS add a legend with ax.legend() when plotting multiple series

SUBPLOTS:
- For comparing distributions or separate views:
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.patch.set_facecolor('#0d1117')
    # style each ax separately

DUAL-AXIS PLOTS:
- When scales differ wildly (e.g., price vs volume):
    ax2 = ax.twinx()
    ax2.bar(df.index, df['VOLUME'], alpha=0.3, color='#7ee787')

STATISTICAL VISUALIZATIONS:
- Correlation heatmap: sns.heatmap(df.select_dtypes(include='number').corr(), annot=True, cmap='coolwarm', ax=ax)
- Box plots: df[cols].plot.box(ax=ax)
- Violin plots: sns.violinplot(data=df, ax=ax)
- Pair plots: use multiple subplots

TIME SERIES:
- Convert date columns: df['Date'] = pd.to_datetime(df['DATETIME'])
- Format x-axis: ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
- Auto-rotate labels: fig.autofmt_xdate()
- Add rolling average: df['COL'].rolling(window=20).mean()
- Fill between: ax.fill_between(x, y1, y2, alpha=0.2)

ADVANCED:
- Candlestick-style: use fill_between for OHLC data
- Grouped bar charts: use x offset with np.arange
- Stacked area: ax.stackplot(...)
- Scatter with size/color: ax.scatter(x, y, s=sizes, c=colors, cmap='viridis')

═══════════════════════════════════════════════════════
STRICT RULES:
═══════════════════════════════════════════════════════
1. Column names are CASE-SENSITIVE — use EXACT names from dataset info.
2. For large datasets (>2000 rows), sample or use df.iloc[:2000] for line/scatter plots.
3. For time series, try to detect and use the datetime column as x-axis.
4. ALWAYS add: title, axis labels, legend (if multi-series), grid (alpha=0.15).
5. Color palette: '#58a6ff', '#f778ba', '#7ee787', '#ffa657', '#d2a8ff', '#ff7b72', '#79c0ff'
6. NO plt.show() — store as: _result_fig = plt.gcf()
7. NO print() statements.
8. Return code inside ```python ... ``` block ONLY.
9. Handle missing values: dropna() before plotting.
10. If user asks to compare columns, plot them ALL on the same chart with different colors.
11. Think about what chart type best answers the user's specific question."""

    return _ai_call(sys_prompt, f"User request: {user_input}",
                    model=get_model("coder"), temperature=0.35, max_tokens=4000)


# =====================================================================
# MODIFY CODE GENERATION — AI generates data modification code
# =====================================================================

def generate_modify_code(user_input, file_path, ctx, conversation_history=None):
    """Generate Python code to modify the dataset."""
    history_str = format_history(conversation_history) if conversation_history else ""

    sys_prompt = f"""You are an expert Python/pandas code generator.
The user wants to MODIFY their dataset (add/remove columns, clean data, transform, etc.).

DATASET INFORMATION:
{ctx}

{f"CONVERSATION CONTEXT:{chr(10)}{history_str}" if history_str else ""}

YOUR TASK: Generate executable Python code that modifies the dataset as requested.

STRICT RULES:
1. Import: import pandas as pd
2. Load data: df = pd.read_csv(r'{file_path}')
3. Perform the requested modification
4. Save the modified data: df.to_csv(r'{file_path}', index=False)
5. Store result: _result_df = df
6. Column names are CASE-SENSITIVE — use EXACT names from dataset info.
7. NO print() statements.
8. Handle edge cases (missing values, wrong types, etc.).
9. Return code inside ```python ... ``` block ONLY.
10. Be careful with destructive operations — only do what the user explicitly asked."""

    return _ai_call(sys_prompt, f"User request: {user_input}",
                    model=get_model("coder"), temperature=0.2, max_tokens=3000)


# =====================================================================
# CHAT — Conversational AI about the dataset
# =====================================================================

def generate_chat_response(user_input, ctx="No dataset loaded.", conversation_history=None):
    """Generate a conversational response about the dataset or general data science."""
    messages = [
        {"role": "system", "content":
            f"""You are 'Data Science Copilot', a friendly and knowledgeable AI assistant specializing in data science.

You help users understand their data, suggest analyses, explain concepts, and guide them through data exploration.

DATASET INFORMATION:
{ctx}

YOUR BEHAVIOR:
- Be conversational, helpful, and thorough.
- When the user asks for a summary, overview, or description of the data, give a **detailed** answer:
  - Mention the number of rows and columns.
  - List key column names and their types (numeric vs categorical).
  - Point out notable patterns: missing values, date ranges, value distributions.
  - Suggest 2-3 specific analyses they could try next.
- For general data science questions, explain clearly with examples.
- Use **bold** for key terms and column names.
- Use bullet points or numbered lists for structured answers.
- Do NOT generate code or tables — just explain in natural language.
- Keep responses informative but concise (5-8 sentences for summaries, 3-5 for quick questions).
- If the dataset has interesting patterns you notice from the context, mention them proactively."""}
    ]
    if conversation_history:
        messages.extend(format_history_as_messages(conversation_history))
    messages.append({"role": "user", "content": user_input})

    result = _ai_call_messages(messages, model=get_model("primary"), temperature=0.7, max_tokens=800)
    return result if result else "I'm here to help! Tell me what you'd like to know about your data, or try asking me to show some rows, create a chart, or analyze patterns."


# =====================================================================
# RESULT SUMMARY — AI generates contextual summaries
# =====================================================================

def generate_result_summary(user_input, operation):
    """Generate a varied, personality-driven summary of what was done."""
    import random
    short = user_input if len(user_input) <= 50 else user_input[:47] + "..."

    pools = {
        "display": [
            f"Done! I pulled up the data for **{short}** — check the results panel 👉",
            f"Here's what I found 🔍 — your results for **{short}** are ready on the right →",
            f"Got it! **{short}** — results are loaded in the panel →",
            f"All set! I ran that query for you — take a look at the results panel 📊",
            f"Your data is ready! **{short}** — see the results on the right →",
        ],
        "visualize": [
            f"Your chart is ready! 📊 **{short}** — take a look on the right →",
            f"I created that visualization for you 🎨 — see the results panel →",
            f"Here's your chart! **{short}** — check the results panel 📈",
            f"Visualization done! I plotted **{short}** for you — see the right panel →",
            f"Chart's up! 🖼️ **{short}** — it's in the results panel →",
        ],
        "modify": [
            f"All done! ✅ I applied **{short}** — preview is on the right →",
            f"Changes saved! ✏️ **{short}** — check the preview in results →",
            f"Done! I updated the dataset for you — **{short}** — see the results panel →",
            f"Modification complete! **{short}** — preview is ready on the right ✅",
            f"Got it done! ✅ **{short}** — your updated data is in the results panel →",
        ],
    }
    fallback = [
        f"Done! **{short}** — see the results panel →",
        f"All set! **{short}** — check the results on the right →",
    ]
    return random.choice(pools.get(operation, fallback))


# =====================================================================
# HELPERS
# =====================================================================

def fix_code(failed_code, error, file_path, ctx):
    """Ask AI to fix broken code."""
    sys_prompt = f"""Fix this Python code that failed with an error.

DATASET INFO:
{ctx}

ERROR: {error}

FAILED CODE:
```python
{failed_code}
```

Return ONLY the corrected code inside ```python ... ``` block.
Fix the specific error while keeping the original intent.
Make sure column names are correct (case-sensitive)."""

    return _ai_call(sys_prompt, "Fix the code.",
                    model=get_model("coder"), temperature=0.2, max_tokens=3000)


def extract_code(raw):
    """Extract Python code from AI response."""
    if not raw:
        return None
    text = _clean_think_tags(raw).replace("\r\n", "\n").replace("\r", "\n")

    # Fenced blocks (most common)
    for pat in [r"```python3?\s*\n(.*?)```", r"```py\s*\n(.*?)```", r"```\s*\n(.*?)```"]:
        m = re.search(pat, text, re.DOTALL | re.IGNORECASE)
        if m:
            code = m.group(1).strip()
            if code:
                app_logger.debug(f"[EXTRACT] Fenced block ({len(code)} chars)")
                return code

    # Alternative fenced format (no newline after ```)
    m = re.search(r"```python3?(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if m:
        code = m.group(1).strip()
        if code:
            return code

    # Fallback: lines that look like Python code
    lines = text.strip().split("\n")
    code_kw = ["import ", "pd.", "plt.", "df[", "df.", "= pd.", "from ", "_result", "sns.", "np."]
    code_lines = []
    started = False
    for line in lines:
        stripped = line.strip()
        if not started:
            if stripped.startswith(("import ", "from ", "df ", "df=", "df[")) or any(k in stripped for k in code_kw):
                started = True
                code_lines.append(line)
        else:
            if stripped.startswith(("Note:", "This ", "The ", "I ", "Here ", "Output", "Explanation", "---")):
                break
            code_lines.append(line)
    if len(code_lines) >= 2:
        app_logger.debug(f"[EXTRACT] Raw lines ({len(code_lines)} lines)")
        return "\n".join(code_lines).strip()

    app_logger.warning("[EXTRACT] Failed to extract code from AI response")
    return None
