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