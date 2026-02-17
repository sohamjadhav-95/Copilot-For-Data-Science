# app.py — Split-Panel Streamlit Chat Interface for Data Science Copilot
import streamlit as st
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import io, os

from data_manager import (
    save_uploaded_file, load_dataframe, get_df_info,
    create_backup, undo_last_change, MODIFIED_DIR,
)
from engines import (
    classify_intent, generate_display_code, generate_chart_spec,
    build_chart, generate_visualize_code,
    generate_modify_code, generate_chat_response, generate_result_summary,
    fix_code, extract_code,
)

# ──────────────────────────── Page Config ─────────────────────────────
st.set_page_config(
    page_title="Data Science Copilot",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────── CSS ─────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
}
[data-testid="stSidebar"] { border-right: 1px solid #30363d !important; }
[data-testid="stChatMessage"] {
    border: 1px solid #30363d !important;
    border-radius: 12px !important;
    margin-bottom: 8px !important;
    padding: 12px 16px !important;
}
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
    border-left: 3px solid #58a6ff !important;
    background: #0d1117 !important;
}
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {
    border-left: 3px solid #a371f7 !important;
    background: #161b22 !important;
}
[data-testid="stChatInput"] textarea {
    border: 1px solid #30363d !important;
    border-radius: 12px !important;
}
[data-testid="stChatInput"] textarea:focus {
    border-color: #58a6ff !important;
    box-shadow: 0 0 0 3px rgba(88,166,255,0.15) !important;
}
[data-testid="stDataFrame"] {
    border-radius: 10px !important;
    border: 1px solid #30363d !important;
}
.stButton > button {
    background: linear-gradient(135deg, #58a6ff, #a371f7) !important;
    color: #fff !important; border: none !important;
    border-radius: 10px !important; font-weight: 600 !important;
}
[data-testid="stFileUploader"] {
    border: 2px dashed #30363d !important;
    border-radius: 12px !important; padding: 12px !important;
}
[data-testid="stFileUploader"]:hover { border-color: #58a6ff !important; }
.copilot-title {
    text-align:center;
    background: linear-gradient(135deg, #58a6ff, #a371f7, #f778ba);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
    font-size:2rem; font-weight:800; margin-bottom:4px;
}
.copilot-subtitle {
    text-align:center; color:#8b949e !important;
    font-size:0.9rem; margin-top:0;
}
.metric-card {
    background:#161b22; border:1px solid #30363d;
    border-radius:12px; padding:16px; text-align:center;
}
.metric-card:hover { border-color:#58a6ff; }
.metric-card h4 {
    margin:0; color:#8b949e !important; font-size:0.7rem;
    text-transform:uppercase; letter-spacing:1.2px; font-weight:600;
}
.metric-card p {
    margin:6px 0 0 0; color:#f0f6fc !important;
    font-size:1.5rem; font-weight:700;
}
.panel-header {
    color: #8b949e !important; font-size: 0.75rem;
    text-transform: uppercase; letter-spacing: 1.5px;
    font-weight: 700; padding: 8px 0 6px 0;
    border-bottom: 1px solid #30363d; margin-bottom: 12px;
}
::-webkit-scrollbar { width:8px; }
::-webkit-scrollbar-track { background:#0d1117; }
::-webkit-scrollbar-thumb { background:#30363d; border-radius:4px; }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────── Session State ───────────────────────────
for key, default in [
    ("messages", []),
    ("file_path", None),
    ("df", None),
    ("results_history", []),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ──────────────────────────── Sidebar ─────────────────────────────────
with st.sidebar:
    st.markdown('<p class="copilot-title">🧪 Data Copilot</p>', unsafe_allow_html=True)
    st.markdown('<p class="copilot-subtitle">AI-powered data assistant</p>', unsafe_allow_html=True)
    st.markdown("---")

    uploaded_file = st.file_uploader("📂 Upload your CSV dataset", type=["csv"])

    if uploaded_file is not None:
        if st.session_state.file_path is None or not st.session_state.file_path.endswith(uploaded_file.name):
            path = save_uploaded_file(uploaded_file)
            st.session_state.file_path = path
            st.session_state.df = load_dataframe(path)
            st.session_state.messages = []
            st.session_state.results_history = []
            st.rerun()

    if st.session_state.df is not None:
        df = st.session_state.df
        st.markdown("---")
        st.markdown("### 📊 Dataset Overview")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f'<div class="metric-card"><h4>Rows</h4><p>{df.shape[0]:,}</p></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="metric-card"><h4>Columns</h4><p>{df.shape[1]}</p></div>', unsafe_allow_html=True)
        st.markdown("")
        c3, c4 = st.columns(2)
        with c3:
            nulls = int(df.isnull().sum().sum())
            st.markdown(f'<div class="metric-card"><h4>Missing</h4><p>{nulls:,}</p></div>', unsafe_allow_html=True)
        with c4:
            numerics = len(df.select_dtypes(include="number").columns)
            st.markdown(f'<div class="metric-card"><h4>Numeric</h4><p>{numerics}</p></div>', unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("##### 📋 Columns")
        for col in df.columns:
            badge = "🔢" if pd.api.types.is_numeric_dtype(df[col]) else "🔤"
            st.markdown(f"`{badge} {col}`")

        st.markdown("---")
        st.markdown("##### 💡 Try these")
        for ex in ["Show first 10 rows", "Display summary statistics",
                    "Plot a histogram of CLOSE", "Create a scatter plot",
                    "Add a column 'ID' with row numbers", "Undo the last change"]:
            st.markdown(f"- *{ex}*")

    if os.path.exists(MODIFIED_DIR):
        files = [f for f in os.listdir(MODIFIED_DIR) if f.endswith(".csv")]
        if files:
            st.markdown("---")
            st.markdown("##### 💾 Modified Files")
            for f in files:
                st.markdown(f"📄 `{f}`")


# ──────────────────────────── Welcome Screen ──────────────────────────
if st.session_state.df is None:
    st.markdown("")
    st.markdown("")
    st.markdown('<p class="copilot-title" style="font-size:3rem;">🧪 Data Science Copilot</p>', unsafe_allow_html=True)
    st.markdown('<p class="copilot-subtitle" style="font-size:1.1rem;">Upload a CSV file in the sidebar to start chatting with your data</p>', unsafe_allow_html=True)
    st.markdown("")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown('<div class="metric-card"><h4 style="font-size:1.3rem;color:#58a6ff !important;">📊 Display</h4><p style="font-size:0.85rem;font-weight:400;color:#8b949e !important;">View rows, stats &amp; info with natural language</p></div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="metric-card"><h4 style="font-size:1.3rem;color:#a371f7 !important;">📈 Visualize</h4><p style="font-size:0.85rem;font-weight:400;color:#8b949e !important;">Generate charts &amp; plots by describing them</p></div>', unsafe_allow_html=True)
    with c3:
        st.markdown('<div class="metric-card"><h4 style="font-size:1.3rem;color:#f778ba !important;">✏️ Modify</h4><p style="font-size:0.85rem;font-weight:400;color:#8b949e !important;">Transform your data &amp; auto-save to disk</p></div>', unsafe_allow_html=True)
    st.stop()


# ══════════════════════════════════════════════════════════════════════
# SPLIT-PANEL LAYOUT
# ══════════════════════════════════════════════════════════════════════
chat_col, results_col = st.columns([1, 1.2])

# ──────────────────────── LEFT: Chat Panel ────────────────────────────
with chat_col:
    st.markdown('<div class="panel-header">💬 Chat</div>', unsafe_allow_html=True)
    chat_box = st.container(height=480)
    with chat_box:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

# ──────────────────────── RIGHT: Results Panel ────────────────────────
with results_col:
    st.markdown('<div class="panel-header">📊 Results</div>', unsafe_allow_html=True)
    results_box = st.container(height=480)
    with results_box:
        if st.session_state.results_history:
            for i, result in enumerate(reversed(st.session_state.results_history)):
                if i > 0:
                    st.markdown("---")
                st.markdown(f"**{result['title']}**")
                if result["type"] == "dataframe":
                    try:
                        st.dataframe(pd.read_json(io.StringIO(result["data"])), use_container_width=True)
                    except Exception:
                        st.markdown("_Could not render table._")
                elif result["type"] == "chart":
                    st.image(result["data"], use_container_width=True)
                elif result["type"] == "text":
                    st.markdown(result["data"])
        else:
            st.markdown("")
            st.markdown("")
            st.markdown(
                '<p style="text-align:center; color:#484f58; font-size:1.1rem; margin-top:60px;">'
                '📋 Results will appear here</p>',
                unsafe_allow_html=True,
            )
            st.markdown(
                '<p style="text-align:center; color:#30363d; font-size:0.85rem;">'
                'Ask a question in the chat panel</p>',
                unsafe_allow_html=True,
            )


# ═══════════════════════════════════════════════════════════════════════
# CHAT INPUT HANDLER
# ═══════════════════════════════════════════════════════════════════════
user_input = st.chat_input("Ask me anything about your data...")

if user_input:
    # Add user message
    st.session_state.messages.append({"role": "user", "content": user_input})

    file_path = st.session_state.file_path
    df = st.session_state.df
    df_info = get_df_info(df, file_path)

    intent = classify_intent(user_input)

    # ── UNDO ──────────────────────────────────────────────────────────
    if intent == "undo":
        success, message = undo_last_change(file_path)
        if success:
            st.session_state.df = load_dataframe(file_path)
        st.session_state.messages.append({"role": "assistant", "content": message})
        st.session_state.results_history.append(
            {"type": "text", "title": "↩️ Undo", "data": message}
        )

    # ── DISPLAY ───────────────────────────────────────────────────────
    elif intent == "display":
        raw_code = generate_display_code(user_input, df_info)
        code = extract_code(raw_code)

        if code is None:
            st.session_state.messages.append({
                "role": "assistant",
                "content": "⚠️ Could not generate valid code. Please rephrase."
            })
        else:
            namespace = {}
            ok = False
            try:
                exec(code, namespace)
                ok = True
            except Exception as e:
                fixed = fix_code(code, str(e), df_info)
                code = extract_code(fixed)
                if code:
                    try:
                        namespace = {}
                        exec(code, namespace)
                        ok = True
                    except Exception:
                        pass

            if ok and "_result_df" in namespace:
                result_df = namespace["_result_df"]
                if isinstance(result_df, pd.Series):
                    result_df = result_df.to_frame()
                if isinstance(result_df, pd.DataFrame):
                    summary = generate_result_summary(user_input, "display")
                    st.session_state.messages.append({"role": "assistant", "content": summary})
                    st.session_state.results_history.append({
                        "type": "dataframe",
                        "title": f"📊 {user_input}",
                        "data": result_df.to_json(),
                    })
                else:
                    st.session_state.messages.append({
                        "role": "assistant", "content": f"✅ Result: {result_df}"
                    })
                    st.session_state.results_history.append({
                        "type": "text",
                        "title": f"📊 {user_input}",
                        "data": str(result_df),
                    })
            else:
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": "⚠️ Could not display the result. Try rephrasing."
                })

    # ── VISUALIZE ─────────────────────────────────────────────────────
    elif intent == "visualize":
        # PRIMARY: JSON spec → build_chart (reliable)
        spec = generate_chart_spec(user_input, df_info)
        fig = None
        err_msg = None

        if spec:
            fig, err_msg = build_chart(df, spec)

        # FALLBACK: AI code generation if spec approach failed
        if fig is None:
            raw_code = generate_visualize_code(user_input, df_info)
            code = extract_code(raw_code)
            if code:
                namespace = {}
                try:
                    plt.close("all")
                    exec(code, namespace)
                    fig = namespace.get("_result_fig", plt.gcf())
                    if fig and not fig.get_axes():
                        fig = None
                except Exception:
                    fig = None

        # AUTO-FALLBACK: if everything failed, just plot first numeric column
        if fig is None:
            try:
                num_cols = df.select_dtypes(include="number").columns.tolist()
                if num_cols:
                    plt.style.use("dark_background")
                    fig, ax = plt.subplots(figsize=(10, 6))
                    fig.patch.set_facecolor("#0d1117")
                    ax.set_facecolor("#161b22")
                    ax.hist(df[num_cols[0]].dropna(), bins=40,
                            color="steelblue", edgecolor="#30363d", alpha=0.85)
                    ax.set_title(f"Distribution of {num_cols[0]}",
                                 color="#f0f6fc", fontsize=14, fontweight="bold")
                    ax.set_xlabel(num_cols[0], color="#e6edf3")
                    ax.set_ylabel("Frequency", color="#e6edf3")
                    ax.tick_params(colors="#8b949e")
                    for spine in ax.spines.values():
                        spine.set_color("#30363d")
                    plt.tight_layout()
            except Exception:
                fig = None

        if fig is not None:
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                        facecolor="#0d1117", edgecolor="none")
            buf.seek(0)
            img_bytes = buf.getvalue()
            plt.close("all")

            summary = generate_result_summary(user_input, "visualize")
            st.session_state.messages.append({"role": "assistant", "content": summary})
            st.session_state.results_history.append({
                "type": "chart",
                "title": f"📈 {user_input}",
                "data": img_bytes,
            })
        else:
            st.session_state.messages.append({
                "role": "assistant",
                "content": "⚠️ Could not generate a visualization. Try something like 'plot histogram of CLOSE' or 'create a scatter plot'."
            })

    # ── MODIFY ────────────────────────────────────────────────────────
    elif intent == "modify":
        create_backup(file_path)
        raw_code = generate_modify_code(user_input, df_info)
        code = extract_code(raw_code)

        if code is None:
            st.session_state.messages.append({
                "role": "assistant",
                "content": "⚠️ Could not generate modification code."
            })
        else:
            namespace = {}
            ok = False
            try:
                exec(code, namespace)
                ok = True
            except Exception as e:
                fixed = fix_code(code, str(e), df_info)
                code = extract_code(fixed)
                if code:
                    try:
                        namespace = {}
                        exec(code, namespace)
                        ok = True
                    except Exception:
                        pass

            if ok:
                st.session_state.df = load_dataframe(file_path)
                result_df = namespace.get("_result_df", st.session_state.df)
                if isinstance(result_df, pd.Series):
                    result_df = result_df.to_frame()
                preview = result_df.head(10) if isinstance(result_df, pd.DataFrame) else st.session_state.df.head(10)

                summary = generate_result_summary(user_input, "modify")
                st.session_state.messages.append({"role": "assistant", "content": summary})
                st.session_state.results_history.append({
                    "type": "dataframe",
                    "title": f"✏️ Modified: {user_input}",
                    "data": preview.to_json(),
                })
            else:
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": "⚠️ Modification failed. Try rephrasing."
                })

    # ── CHAT ──────────────────────────────────────────────────────────
    else:
        response = generate_chat_response(user_input, df_info)
        st.session_state.messages.append({"role": "assistant", "content": response})

    st.rerun()
