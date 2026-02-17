import re
from config.api_manager import client, MODEL_NAME
from Data import dataset_features

def NL_processor(user_input):
    """
    Analyzes the user input to determine the intended operation.
    """
    try:
        system_prompt = """
        You are an AI assistant that classifies user intent into specific data operations.
        Analyze the input and return ONLY one of the following exact keywords:

        **Data Operations:**
        - 'visualize' : Create charts, graphs, or plots.
        - 'display' : Show data rows, columns, or info.
        - 'modify' : Change values, add columns, clean data.
        - 'undo' : Revert the last change.

        **Analysis & Reporting:**
        - 'analyze_data' : Statistical analysis, insights, correlations.
        - 'generate_report' : Create a PDF report.
        - 'create_dashboard' : Launch an interactive dashboard.

        **General:**
        - 'meaningful_response' : General questions or chat.

        **Rules:**
        - Return ONLY the keyword. No explanations.
        - If unsure, default to 'meaningful_response'.
        """

        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"User Input: \"{user_input}\""}
            ],
            temperature=0.1, # Low temperature for consistent classification
            max_tokens=50,
            top_p=0.95,
            stream=False
        )

        response = completion.choices[0].message.content.strip().lower()

        valid_intents = [
            "visualize", "display", "modify", "undo", "meaningful_response",
            "analyze_data", "generate_report", "create_dashboard"
        ]

        for intent in valid_intents:
            if intent in response:
                return intent
        
        return "meaningful_response"

    except Exception as e:
        print(f"An error occurred in NL_processor: {e}")
        return None


def split_multi_commands(user_input):
    """
    Splits complex user input into individual executable commands.
    """
    try:
        system_prompt = """
        You are an expert command parser. Split the user's input into logical, independent steps.
        
        **Rules:**
        - Return commands separated by '||'.
        - Keep commands concise and executable.
        - Example: "Load data and show first 5 rows" -> "Load data||Show first 5 rows"
        - Return ONLY the string of commands.
        """

        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Input: \"{user_input}\""}
            ],
            temperature=0.1,
            max_tokens=1024,
            top_p=0.95,
            stream=False
        )

        response = completion.choices[0].message.content.strip()
        commands = [cmd.strip() for cmd in response.split("||") if cmd.strip()]
        return commands
    except Exception as e:
        print(f"Error in split_multi_commands: {e}")
        return [user_input]


def result_response(user_input ,result):
    """
    Generates a brief, meaningful response after an operation execution.
    """
    try:
        system_prompt = "You are a helpful data assistant. Provide a concise, 1-2 sentence confirmation of the action taken."

        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"User Request: {user_input}\nResult/Action: {result}"}
            ],
            temperature=0.7,
            max_tokens=100,
            top_p=0.95,
            stream=False
        )

        print(completion.choices[0].message.content.strip())
    except Exception as e:
        print(f"Error generating response: {e}")


def genral_response_chatbot(user_input):
    """
    Generates a general response to user queries, leveraging dataset features if relevant.
    """
    try:
        features = dataset_features()
        system_prompt = f"""
        You are a smart data assistant. Answer the user's question directly.
        
        **Context:**
        - Current Dataset Features: {features}
        
        **Rules:**
        - Keep answers brief and relevant to data science if possible.
        - If the question is unrelated to data, answer politely but briefly.
        """

        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ],
            temperature=0.7,
            max_tokens=256,
            top_p=0.95,
            stream=False
        )

        print(completion.choices[0].message.content.strip())
    except Exception as e:
        print(f"Error in chatbot response: {e}")


if __name__ == "__main__":
    user_input = "Undo last modification"
    print(NL_processor(user_input))
