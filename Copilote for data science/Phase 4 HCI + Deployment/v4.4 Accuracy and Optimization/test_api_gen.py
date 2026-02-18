'''
from openai import OpenAI

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key="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"
)

resp = client.chat.completions.create(
    model="qwen/qwen3-235b-a22b-thinking-2507",
    messages=[
        {"role": "user", "content": "How many r's are in strawberry?"}
    ]
)

print(resp.choices[0].message.content)
'''

from groq import Groq

client = Groq(api_key="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")

chat_completion = client.chat.completions.create(
    messages=[
        {
            "role": "user",
            "content": "Explain the importance of fast language models",
        }
    ],
    model="openai/gpt-oss-120b",
)

print(chat_completion.choices[0].message.content)
