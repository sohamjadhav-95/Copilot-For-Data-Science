import os
import shutil
import re
from Data import Data_rows, filepath
from NL_processor import result_response
from config.api_manager import client, MODEL_NAME

first_100_rows, last_100_rows = Data_rows()
data = filepath()
backup_path = data + ".backup"

def create_backup():
    """Creates a backup of the dataset before modification."""
    if os.path.exists(data):
        shutil.copy(data, backup_path)
    print("Backup Is Created Before Modification, Use Undo to restore changes")

def undo_last_change():
    """Restores the dataset from the last backup."""
    if os.path.exists(backup_path):
        shutil.copy(backup_path, data)
        print("Undo successful: Data restored from the last backup.")
    else:
        print("No backup found! Cannot undo.")

def Groq_Input(user_input):
    original_code_generation_approach(user_input)

def original_code_generation_approach(user_input):
    try:
        first_100_rows, last_100_rows = Data_rows()
        data = filepath()
        if first_100_rows is None or last_100_rows is None:
            print("Error: Unable to load data.")
            return

        create_backup() # Ensure backup before modify

        system_prompt = f"""
        You are an expert Pandas Data Engineer. Your task is to **MODIFY** the dataset based on user requests.

        **Dataset Context:**
        - File Path: '{data}'
        - First 100 rows preview: {first_100_rows}

        **Rules:**
        1. **Load Data**: Use `pd.read_csv(r'{data}')`.
        2. **Modify**: Apply the requested changes to the DataFrame.
        3. **Save**: Save the modified DataFrame back to '{data}' using `df.to_csv(r'{data}', index=False)`.
        4. **Safety**: Ensure you do not accidentally lose data rows unless explicitly asked to filter/drop.
        5. **Format**: Return **ONLY** valid Python code inside a markdown block: ```python ... ```.
        6. **No Explanations**: Do NOT include any text outside the code block.
        """

        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"User Request: {user_input}"}
            ],
            temperature=0.2,
            max_tokens=4096,
            top_p=0.95,
            stream=False
        )

        generated_code = completion.choices[0].message.content
        execute_generated_code(generated_code, user_input)

    except Exception as e:
        print(f"Error in Groq_Input (Modify): {e}")

def execute_generated_code(generated_code, user_input):
    """Parses and executes the generated Python code."""
    code_match = re.search(r"```python\n(.*?)\n```", generated_code, re.DOTALL)
    
    if code_match:
        valid_code = code_match.group(1).strip()
    else:
        valid_code = generated_code.strip() if "import" in generated_code else None

    if not valid_code:
        print("No valid Modification Logic detected!")
        return

    try:
        print("\nExecuting Modification Operation...\n")
        exec(valid_code)
        print("\nData modified and saved successfully!")
        result_response(user_input, "Transformation applied successfully.")
    except Exception as e:
        print(f"\nExecution Error: {e}")
        generate_code_error_handling(user_input, valid_code, e)

def generate_code_error_handling(user_input, failed_code, error):
    try:
        first_100_rows, last_100_rows = Data_rows()
        data = filepath()

        system_prompt = f"""
        You are an expert Pandas Debugger. The modification code failed. Fix it.

        **Context:**
        - File Path: '{data}'
        - Error: {error}
        - Failed Code:
        ```python
        {failed_code}
        ```

        **Rules:**
        1. Fix the error.
        2. Ensure the code loads, modifies, and saves the data correctly.
        3. Return **ONLY** the fixed Python code inside a markdown block.
        """

        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Fix the modification code."}
            ],
            temperature=0.2,
            max_tokens=4096,
            top_p=0.95,
            stream=False
        )

        generated_code = completion.choices[0].message.content
        
        code_match = re.search(r"```python\n(.*?)\n```", generated_code, re.DOTALL)
        if code_match:
            fixed_code = code_match.group(1).strip()
            print("\nRetrying with fixed code...\n")
            exec(fixed_code)
            print("\nTask completed successfully!")
            result_response(user_input, "Fixed and executed modification.")
        else:
            print("Failed to generate fixed code.")

    except Exception as e:
        print(f"Critical Error in Error Handler: {e}")
