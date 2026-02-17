# app.py — Streamlit Chat Interface for Data Science Copilot
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
    classify_intent, generate_display_code, generate_visualize_code,
    generate_modify_code, generate_chat_response, fix_code, extract_code,
)

# ──────────────────────────── Page Config ─────────────────────────────
st.set_page_config(
    page_title="Data Science Copilot",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────── Inject CSS ──────────────────────────────
_css = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
}
[data-testid="stSidebar"] { border-right: 1px solid #30363d !important; }
[data-testid="stChatMessage"] {
    border: 1px solid #30363d !important;
    border-radius: 14px !important;
    margin-bottom: 10px !important;
    padding: 16px 20px !important;
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
    font-size: 0.95rem !important;
}
[data-testid="stChatInput"] textarea:focus {
    border-color: #58a6ff !important;
    box-shadow: 0 0 0 3px rgba(88, 166, 255, 0.15) !important;
}
[data-testid="stDataFrame"] {
    border-radius: 12px !important;
    border: 1px solid #30363d !important;
}
.stButton > button {
    background: linear-gradient(135deg, #58a6ff, #a371f7) !important;
    color: #fff !important; border: none !important;
    border-radius: 10px !important; font-weight: 600 !important;
    transition: all 0.25s ease !important;
    box-shadow: 0 2px 8px rgba(88,166,255,0.2) !important;
}
.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 20px rgba(88,166,255,0.35) !important;
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
    transition: border-color 0.25s ease, box-shadow 0.25s ease;
}
.metric-card:hover {
    border-color:#58a6ff;
    box-shadow: 0 0 12px rgba(88,166,255,0.1);
}
.metric-card h4 {
    margin:0; color:#8b949e !important; font-size:0.7rem;
    text-transform:uppercase; letter-spacing:1.2px; font-weight:600;
}
.metric-card p {
    margin:6px 0 0 0; color:#f0f6fc !important;
    font-size:1.5rem; font-weight:700;
}
::-webkit-scrollbar { width:8px; height:8px; }
::-webkit-scrollbar-track { background:#0d1117; }
::-webkit-scrollbar-thumb { background:#30363d; border-radius:4px; }
::-webkit-scrollbar-thumb:hover { background:#484f58; }
</style>
"""
st.markdown(_css, unsafe_allow_html=True)

# ──────────────────────────── Session State ───────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "file_path" not in st.session_state:
    st.session_state.file_path = None
if "df" not in st.session_state:
    st.session_state.df = None

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
        st.markdown("##### 💡 Try these commands")
        for ex in [
            "Show the first 10 rows",
            "Display summary statistics",
            "Plot a histogram of the first numeric column",
            "Create a bar chart",
            "Add a new column called 'ID' with row numbers",
            "Remove rows with missing values",
            "Undo the last change",
        ]:
            st.markdown(f"- *{ex}*")

    if os.path.exists(MODIFIED_DIR):
        files = [f for f in os.listdir(MODIFIED_DIR) if f.endswith(".csv")]
        if files:
            st.markdown("---")
            st.markdown("##### 💾 Modified Files")
            for f in files:
                st.markdown(f"📄 `{f}`")


# ──────────────────────────── Main Area ───────────────────────────────
if st.session_state.df is None:
    st.markdown("")
    st.markdown("")
    st.markdown('<p class="copilot-title" style="font-size:3rem;">🧪 Data Science Copilot</p>', unsafe_allow_html=True)
    st.markdown('<p class="copilot-subtitle" style="font-size:1.1rem;">Upload a CSV file in the sidebar to start chatting with your data</p>', unsafe_allow_html=True)

    st.markdown("")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown('<div class="metric-card"><h4 style="font-size:1.3rem;color:#58a6ff !important;">📊 Display</h4><p style="font-size:0.85rem;font-weight:400;color:#8b949e !important;">View rows, stats, info &amp; more with natural language</p></div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="metric-card"><h4 style="font-size:1.3rem;color:#a371f7 !important;">📈 Visualize</h4><p style="font-size:0.85rem;font-weight:400;color:#8b949e !important;">Generate charts &amp; plots just by describing them</p></div>', unsafe_allow_html=True)
    with c3:
        st.markdown('<div class="metric-card"><h4 style="font-size:1.3rem;color:#f778ba !important;">✏️ Modify</h4><p style="font-size:0.85rem;font-weight:400;color:#8b949e !important;">Transform your data &amp; auto-save changes to disk</p></div>', unsafe_allow_html=True)

    st.stop()

# ──────────────────────── Render Chat History ─────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg.get("type") == "dataframe":
            st.markdown(msg.get("text", ""))
            st.dataframe(pd.read_json(io.StringIO(msg["data"])), use_container_width=True)
        elif msg.get("type") == "chart":
            st.markdown(msg.get("text", ""))
            st.image(msg["data"], use_container_width=True)
        elif msg.get("type") == "code":
            st.markdown(msg.get("text", ""))
            st.code(msg["data"], language="python")
        else:
            st.markdown(msg["content"])


# ──────────────────────── Chat Input Handler ──────────────────────────
user_input = st.chat_input("Ask me anything about your data...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        file_path = st.session_state.file_path
        df = st.session_state.df
        df_info = get_df_info(df, file_path)

        with st.spinner("🧠 Thinking..."):
            intent = classify_intent(user_input)

        # ── UNDO ──
        if intent == "undo":
            success, message = undo_last_change(file_path)
            if success:
                st.session_state.df = load_dataframe(file_path)
            st.markdown(message)
            st.session_state.messages.append({"role": "assistant", "content": message})

        # ── DISPLAY ──
        elif intent == "display":
            with st.spinner("📊 Generating display code..."):
                raw_code = generate_display_code(user_input, df_info)
                code = extract_code(raw_code)

            if code is None:
                err_msg = "⚠️ Could not generate valid code. Please rephrase your request."
                st.markdown(err_msg)
                st.session_state.messages.append({"role": "assistant", "content": err_msg})
            else:
                namespace = {}
                try:
                    exec(code, namespace)
                except Exception as e:
                    with st.spinner("🔧 Fixing code..."):
                        fixed_raw = fix_code(code, str(e), df_info)
                        code = extract_code(fixed_raw)
                    if code:
                        try:
                            namespace = {}
                            exec(code, namespace)
                        except Exception as e2:
                            err_msg = f"⚠️ Execution failed after retry:\n```\n{e2}\n```"
                            st.markdown(err_msg)
                            st.session_state.messages.append({"role": "assistant", "content": err_msg})
                            code = None

                if code and "_result_df" in namespace:
                    result_df = namespace["_result_df"]
                    if isinstance(result_df, pd.Series):
                        result_df = result_df.to_frame()
                    if isinstance(result_df, pd.DataFrame):
                        st.markdown("✅ Here's the result:")
                        st.dataframe(result_df, use_container_width=True)
                        st.session_state.messages.append({
                            "role": "assistant", "type": "dataframe",
                            "text": "✅ Here's the result:", "data": result_df.to_json(),
                        })
                    else:
                        text = f"✅ Result:\n\n{result_df}"
                        st.markdown(text)
                        st.session_state.messages.append({"role": "assistant", "content": text})
                elif code:
                    text = "✅ Code executed but no displayable result was captured. Try rephrasing."
                    st.markdown(text)
                    st.session_state.messages.append({"role": "assistant", "content": text})

        # ── VISUALIZE ──
        elif intent == "visualize":
            with st.spinner("📈 Generating visualization code..."):
                raw_code = generate_visualize_code(user_input, df_info)
                code = extract_code(raw_code)

            if code is None:
                err_msg = "⚠️ Could not generate valid visualization code."
                st.markdown(err_msg)
                st.session_state.messages.append({"role": "assistant", "content": err_msg})
            else:
                namespace = {}
                try:
                    plt.close("all")
                    exec(code, namespace)
                except Exception as e:
                    with st.spinner("🔧 Fixing code..."):
                        fixed_raw = fix_code(code, str(e), df_info)
                        code = extract_code(fixed_raw)
                    if code:
                        try:
                            plt.close("all")
                            namespace = {}
                            exec(code, namespace)
                        except Exception as e2:
                            err_msg = f"⚠️ Visualization failed after retry:\n```\n{e2}\n```"
                            st.markdown(err_msg)
                            st.session_state.messages.append({"role": "assistant", "content": err_msg})
                            code = None

                if code:
                    fig = namespace.get("_result_fig", None)
                    if fig is None:
                        fig = plt.gcf()
                        if not fig.get_axes():
                            fig = None

                    if fig is not None:
                        buf = io.BytesIO()
                        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                                    facecolor="#0d1117", edgecolor="none")
                        buf.seek(0)
                        img_bytes = buf.getvalue()
                        plt.close("all")

                        st.markdown("✅ Here's the visualization:")
                        st.image(img_bytes, use_container_width=True)
                        st.session_state.messages.append({
                            "role": "assistant", "type": "chart",
                            "text": "✅ Here's the visualization:", "data": img_bytes,
                        })
                    else:
                        text = "✅ Code executed but no chart was captured. Try being more specific."
                        st.markdown(text)
                        st.session_state.messages.append({"role": "assistant", "content": text})

        # ── MODIFY ──
        elif intent == "modify":
            with st.spinner("✏️ Generating modification code..."):
                create_backup(file_path)
                raw_code = generate_modify_code(user_input, df_info)
                code = extract_code(raw_code)

            if code is None:
                err_msg = "⚠️ Could not generate valid modification code."
                st.markdown(err_msg)
                st.session_state.messages.append({"role": "assistant", "content": err_msg})
            else:
                namespace = {}
                try:
                    exec(code, namespace)
                except Exception as e:
                    with st.spinner("🔧 Fixing code..."):
                        fixed_raw = fix_code(code, str(e), df_info)
                        code = extract_code(fixed_raw)
                    if code:
                        try:
                            namespace = {}
                            exec(code, namespace)
                        except Exception as e2:
                            err_msg = f"⚠️ Modification failed after retry:\n```\n{e2}\n```"
                            st.markdown(err_msg)
                            st.session_state.messages.append({"role": "assistant", "content": err_msg})
                            code = None

                if code:
                    st.session_state.df = load_dataframe(file_path)
                    result_df = namespace.get("_result_df", st.session_state.df)
                    if isinstance(result_df, pd.Series):
                        result_df = result_df.to_frame()

                    st.markdown(f"✅ Data modified and saved to `{os.path.basename(file_path)}`!")
                    st.markdown("**Preview of modified data (first 10 rows):**")
                    preview = result_df.head(10) if isinstance(result_df, pd.DataFrame) else st.session_state.df.head(10)
                    st.dataframe(preview, use_container_width=True)

                    st.session_state.messages.append({
                        "role": "assistant", "type": "dataframe",
                        "text": f"✅ Data modified and saved to `{os.path.basename(file_path)}`!\n\n**Preview of modified data (first 10 rows):**",
                        "data": preview.to_json(),
                    })

        # ── CHAT ──
        else:
            with st.spinner("💬 Generating response..."):
                response = generate_chat_response(user_input, df_info)
            st.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})
