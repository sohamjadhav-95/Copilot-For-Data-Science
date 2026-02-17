import re
import pandas as pd
from Data import Data_rows, filepath
from NL_processor import result_response
from config.api_manager import client, MODEL_NAME

def Groq_Input(user_input):
    original_code_generation_approach(user_input)


def original_code_generation_approach(user_input):
    try:
        first_100_rows, last_100_rows = Data_rows()
        data = filepath()
        if first_100_rows is None or last_100_rows is None:
            print("Error: Unable to load data.")
            return

        system_prompt = f"""
        You are an expert Python Data Scientist. Your task is to generate Python code to **DISPLAY** data based on user requests.

        **Dataset Context:**
        - File Path: '{data}'
        - First 100 rows preview: {first_100_rows}
        - Last 100 rows preview: {last_100_rows}

        **Rules:**
        1. **Load Data**: Use `pd.read_csv(r'{data}')`.
        2. **Operation**: Generate code ONLY for displaying/printing data. Do not visualize or modify.
        3. **Output**: Print the result using `print()`.
        4. **Format**: Return **ONLY** valid Python code inside a markdown block: ```python ... ```.
        5. **No Explanations**: Do not include any text outside the code block.
        """

        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"User Request: {user_input}"}
            ],
            temperature=0.2,
            max_tokens=2048,
            top_p=0.95,
            stream=False
        )

        generated_code = completion.choices[0].message.content
        execute_generated_code(generated_code, user_input)

    except Exception as e:
        print(f"Error in Groq_Input: {e}")


def execute_generated_code(generated_code, user_input):
    """Parses and executes the generated Python code."""
    code_match = re.search(r"```python\n(.*?)\n```", generated_code, re.DOTALL)
    
    if code_match:
        valid_code = code_match.group(1).strip()
    else:
        # Fallback if no markdown found, but sometimes models just dump code
        valid_code = generated_code.strip() if "import" in generated_code else None

    if not valid_code:
        print("No valid Python code detected in response.")
        return

    try:
        print("\nExecuting Display Operation...\n")
        exec(valid_code)
        print("\nTask completed successfully!")
        result_response(user_input, "Display operation completed.")
    except Exception as e:
        print(f"\nExecution Error: {e}")
        generate_code_error_handling(user_input, valid_code, e)


def generate_code_error_handling(user_input, failed_code, error):
    try:
        first_100_rows, last_100_rows = Data_rows()
        data = filepath()

        system_prompt = f"""
        You are an expert Python Debugger. The previous code failed. Fix it.

        **Context:**
        - File Path: '{data}'
        - Error: {error}
        - Failed Code:
        ```python
        {failed_code}
        ```

        **Rules:**
        1. Fix the error.
        2. Ensure the code loads the data correctly.
        3. Return **ONLY** the fixed Python code inside a markdown block.
        """

        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Fix the code."}
            ],
            temperature=0.2,
            max_tokens=2048,
            top_p=0.95,
            stream=False
        )

        generated_code = completion.choices[0].message.content
        
        # Recursive attempt (simplified)
        code_match = re.search(r"```python\n(.*?)\n```", generated_code, re.DOTALL)
        if code_match:
            fixed_code = code_match.group(1).strip()
            print("\nRetrying with fixed code...\n")
            exec(fixed_code)
            print("\nTask completed successfully!")
            result_response(user_input, "Fixed and executed display operation.")
        else:
            print("Failed to generate fixed code.")

    except Exception as e:
        print(f"Critical Error in Error Handler: {e}")