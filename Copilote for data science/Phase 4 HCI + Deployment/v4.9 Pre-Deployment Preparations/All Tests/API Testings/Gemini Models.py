
from google import genai
from google.genai import types

client = genai.Client(api_key="AIzaSyBxm9imbaUG9fDUziA5xU66NfXlx2FVtgg")

# The prompt asks for a complex task involving math and plotting
prompt = "what is meaning of life?"

response = client.models.generate_content(
    model="gemini-3-flash-preview", # Swap with gemini-3.1-pro-preview for Pro tests
    contents=prompt,
    config=types.GenerateContentConfig(
        tools=[types.Tool(code_execution=types.ToolCodeExecution())],
        temperature=0.1
    )
)

# Gemini will actually run the code and give you the text + results
for part in response.candidates[0].content.parts:
    if part.text:
        print(f"MODEL RESPONSE:\n{part.text}")
    if part.executable_code:
        print(f"\nEXECUTED CODE:\n{part.executable_code.code}")
    if part.code_execution_result:
        print(f"\nEXECUTION OUTCOME:\n{part.code_execution_result.output}")