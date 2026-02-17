# engines.py — AI-powered Display, Visualize, Modify, and Chat engines
import re
from api_config import client, MODEL_NAME


def classify_intent(user_input):
    """Classify user intent into: display, visualize, modify, undo, or chat."""
    try:
        system_prompt = """
        You are an AI assistant that classifies user intent for data operations.
        Analyze the input and return ONLY one of these exact keywords:

        - 'visualize' : Create charts, graphs, plots, histograms, scatter plots, etc.
        - 'display'   : Show data rows, columns, info, describe, head, tail, shape, dtypes, etc.
        - 'modify'    : Change/add/delete values, columns, rows, rename, clean, fill missing, etc.
        - 'undo'      : Revert/undo the last change.
        - 'chat'      : General questions, greetings, or anything else.

        Rules:
        - Return ONLY the keyword. No quotes, no explanation, no punctuation.
        - If unsure, default to 'chat'.
        """

        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f'User Input: "{user_input}"'},
            ],
            temperature=0.1,
            max_tokens=20,
            top_p=0.95,
        )

        response = completion.choices[0].message.content.strip().lower()
        valid = ["visualize", "display", "modify", "undo", "chat"]
        for intent in valid:
            if intent in response:
                return intent
        return "chat"
    except Exception as e:
        return "chat"


def _build_data_context(df_info):
    """Build a compact dataset context string for prompts."""
    return (
        f"File Path: '{df_info['file_path']}'\n"
        f"Shape: {df_info['shape']}\n"
        f"Columns & Types: {df_info['dtypes']}\n"
        f"First rows preview:\n{df_info['head']}"
    )


def generate_display_code(user_input, df_info):
    """Generate Python code to display/query the dataset."""
    ctx = _build_data_context(df_info)
    system_prompt = f"""
    You are an expert Python Data Scientist. Generate Python code to DISPLAY data based on the user request.

    Dataset Context:
    {ctx}

    Rules:
    1. Load data with: df = pd.read_csv(r'{df_info["file_path"]}')
    2. Only display/print data — do NOT modify or visualize.
    3. Store the final result in a variable called `_result_df`. It MUST be a pandas DataFrame or Series.
       - If the result is a scalar or string, wrap it: `_result_df = pd.DataFrame({{"Result": [value]}})`
       - If the result is a dict, wrap it: `_result_df = pd.DataFrame(result_dict, index=[0])` or similar.
    4. Do NOT use print(). Just assign to `_result_df`.
    5. You must import pandas as pd at the top.
    6. Return ONLY valid Python code inside ```python ... ``` — no explanations.
    """

    return _call_code_generation(system_prompt, user_input)


def generate_visualize_code(user_input, df_info):
    """Generate Python code to create a visualization."""
    ctx = _build_data_context(df_info)
    system_prompt = f"""
    You are an expert Python Data Scientist. Generate Python code to VISUALIZE data.

    Dataset Context:
    {ctx}

    Rules:
    1. Load data with: df = pd.read_csv(r'{df_info["file_path"]}')
    2. Use matplotlib (preferred) or seaborn for plotting.
    3. IMPORTANT: Use `plt.figure()` at the start and store the figure: `_result_fig = plt.gcf()`
    4. Do NOT call plt.show(). Just assign to `_result_fig`.
    5. Make the chart visually appealing with title, labels, and appropriate colors.
    6. You must import pandas, matplotlib.pyplot, and optionally seaborn.
    7. Return ONLY valid Python code inside ```python ... ``` — no explanations.
    """

    return _call_code_generation(system_prompt, user_input)


def generate_modify_code(user_input, df_info):
    """Generate Python code to modify and save the dataset."""
    ctx = _build_data_context(df_info)
    fp = df_info["file_path"]
    system_prompt = f"""
    You are an expert Pandas Data Engineer. Generate Python code to MODIFY the dataset.

    Dataset Context:
    {ctx}

    Rules:
    1. Load data with: df = pd.read_csv(r'{fp}')
    2. Apply the requested modifications to df.
    3. Save the result: df.to_csv(r'{fp}', index=False)
    4. Store the modified dataframe in `_result_df = df` so we can preview it.
    5. Do NOT delete data unless the user explicitly asks.
    6. You must import pandas as pd at the top.
    7. Return ONLY valid Python code inside ```python ... ``` — no explanations.
    """

    return _call_code_generation(system_prompt, user_input)


def generate_chat_response(user_input, df_info=None):
    """Generate a general conversational response, optionally aware of the data."""
    ctx = _build_data_context(df_info) if df_info else "No dataset loaded."
    system_prompt = f"""
    You are a friendly and smart Data Science assistant. Answer the user's question.

    Current Dataset Info:
    {ctx}

    Rules:
    - Keep answers concise and helpful.
    - If the question relates to the data, reference columns/stats.
    - If unrelated, answer politely and briefly.
    """

    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ],
            temperature=0.7,
            max_tokens=512,
            top_p=0.95,
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠️ Error generating response: {e}"


def fix_code(failed_code, error, df_info):
    """Attempt to fix code that failed execution."""
    ctx = _build_data_context(df_info)
    system_prompt = f"""
    You are an expert Python Debugger. The previous code failed. Fix it.

    Dataset Context:
    {ctx}

    Error: {error}

    Failed Code:
    ```python
    {failed_code}
    ```

    Rules:
    1. Fix the error while preserving the original intent.
    2. Keep the same variable naming conventions (_result_df or _result_fig).
    3. Return ONLY the fixed Python code inside ```python ... ```.
    """

    return _call_code_generation(system_prompt, "Fix the code.")


# ─── Internal helpers ────────────────────────────────────────────────

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
            top_p=0.95,
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        return None


def extract_code(raw_response):
    """Extract Python code from a markdown-fenced response."""
    if raw_response is None:
        return None
    match = re.search(r"```python\n(.*?)```", raw_response, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Fallback: if it looks like code, use it directly
    if "import" in raw_response or "pd." in raw_response or "plt." in raw_response:
        return raw_response.strip()
    return None
