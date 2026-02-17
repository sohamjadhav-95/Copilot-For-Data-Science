import csv
from openai import OpenAI
import pandas as pd
import os
from config.api_manager import get_api_key
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key="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",
)

CSV_FILE = r"E:\Projects\Copilot-For-Data-Science\Copilote for data science\Phase 3 Human in the Loop (Interactive AI)\v3.8 Updated Models\Retrival_Agumented_Generation\commands_database.csv"

# Initialize CSV file if it doesn't exist
def init_csv():
    """Initialize CSV file with header if it doesn't exist."""
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['Command'])  # Add header

def clean_and_repair_csv():
    """Clean and repair corrupted CSV file by removing invalid entries."""
    try:
        if not os.path.exists(CSV_FILE):
            init_csv()
            return
        
        # Try to read and validate the CSV
        try:
            df = pd.read_csv(CSV_FILE, encoding='utf-8')
        except Exception:
            # CSV is corrupted, recreate it
            os.remove(CSV_FILE)
            init_csv()
            return
        
        # Check if empty
        if df.empty:
            return
        
        # Filter out invalid entries
        df = df.dropna(subset=['Command'])  # Remove NaN
        df['Command'] = df['Command'].astype(str)  # Convert to string
        df = df[~df['Command'].isin(["'No Command'", "", "Command", "nan"])]  # Remove unwanted
        
        # Write back the cleaned data
        df.to_csv(CSV_FILE, index=False, encoding='utf-8')
    except Exception as e:
        print(f"Error cleaning CSV: {str(e)}")
        # If cleaning fails, recreate the CSV
        try:
            os.remove(CSV_FILE)
            init_csv()
        except:
            pass

def store_command(command):
    """Append the command to the CSV file."""
    try:
        init_csv()  # Ensure CSV exists
        with open(CSV_FILE, mode='a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow([str(command)])  # Ensure command is string
    except Exception as e:
        print(f"Error storing command: {str(e)}")

def get_last_commands(n=5, _retry=False):
    """Get the last n commands from the CSV file."""
    try:
        if not os.path.exists(CSV_FILE):
            return []
        
        if os.path.getsize(CSV_FILE) == 0:
            return []
        
        # Read CSV
        df = pd.read_csv(CSV_FILE, encoding='utf-8')
        
        # Filter out empty, NaN, and unwanted entries
        df = df.dropna(subset=['Command'])  # Remove NaN values
        df['Command'] = df['Command'].astype(str)  # Convert to string
        df = df[~df['Command'].isin(["'No Command'", "", "Command", "nan"])]  # Filter unwanted
        
        # Get last n commands
        last_commands = df.tail(n)['Command'].tolist()
        
        return last_commands
    except Exception as e:
        print(f"Error reading commands: {str(e)}")
        
        # Try to clean and repair the CSV (only once)
        if not _retry:
            try:
                clean_and_repair_csv()
                return get_last_commands(n, _retry=True)  # Retry once after cleaning
            except:
                pass
        
        return []

def modify_command_api(user_input):
    """Use the API to modify the command based on recent commands."""
    last_commands = get_last_commands(5)
    context = "\n".join(last_commands) if last_commands else "No previous commands"

    prompt = f"""
    You are an AI assistant that refines user commands based on previous instructions Like Windows Memory Buffer.
    Here are the last few commands given by the user:
    {context}

    The user has now given a new command: "{user_input}"

    Rules for command modification:
    Importent : If there is no need to modify command return as it is.
    1. If the command is a "restore" command and follows a "delete" command, include the specific details from the delete command
    2. Maintain context between related commands (delete/restore, copy/paste, etc.)
    3. If no previous commands are referenced, return the original command as is

    Return only the modified command, nothing else.
    """

    try:
        completion = client.chat.completions.create(
            model="qwen/qwen3-coder-flash",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=100,
            top_p=0.95,
            stream=False,
            stop=None,
        )

        response = completion.choices[0].message.content.strip()
        return response

    except Exception as e:
        return f"Error: {str(e)}"

def basic_rag(user_input):
    """Process user input, modify it using API, and store the result."""
    try:
        modified_command = modify_command_api(user_input)
        
        # If there's an error or empty response, return original input
        if not modified_command or modified_command.startswith("Error:"):
            print(f"Using original command: {user_input}")
            return user_input
        
        # Store the modified command
        store_command(modified_command)
        print(f"Modified command: {modified_command}")
        
        return modified_command
    except Exception as e:
        error_msg = f"Error in basic_rag: {str(e)}"
        print(error_msg)
        # Return original input instead of error message to allow execution to continue
        return user_input

if __name__ == "__main__":
    user_input = "Visualize the dataset"
    modified_command = basic_rag(user_input)