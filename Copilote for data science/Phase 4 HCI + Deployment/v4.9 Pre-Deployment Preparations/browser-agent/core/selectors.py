"""
Centralized DOM selectors for each supported chat interface.

Add a new class here to support a new target site.
Update TARGETS dict to register it.
"""


class ChatGPTSelectors:
    """Selectors for chat.openai.com"""

    INPUT_FIELD = [
        'div#prompt-textarea',
        'textarea[data-id="root"]',
        'div[contenteditable="true"][data-placeholder]',
        '#prompt-textarea',
    ]
    SEND_BUTTON = [
        'button[data-testid="send-button"]',
        'button[aria-label="Send prompt"]',
        'button[aria-label="Send"]',
        'form button[type="submit"]',
    ]
    STREAMING_INDICATOR = [
        'button[data-testid="stop-button"]',
        'button[aria-label="Stop generating"]',
        'div[class*="result-streaming"]',
    ]
    ASSISTANT_MESSAGE = [
        'div[data-message-author-role="assistant"]',
        'div.agent-turn',
    ]
    RESPONSE_TEXT = [
        'div.markdown',
        'div[class*="markdown"] p',
        'div.text-base',
    ]
    NEW_CHAT = [
        'a[data-testid="create-new-chat-button"]',
        'nav a:first-child',
    ]


class ClaudeSelectors:
    """Selectors for claude.ai"""

    INPUT_FIELD = [
        'div[contenteditable="true"].ProseMirror',
        'div[contenteditable="true"][aria-label="Write your prompt to Claude"]',
        'p[data-placeholder]',
        'div.ProseMirror',
    ]
    SEND_BUTTON = [
        'button[aria-label="Send Message"]',
        'button[data-testid="send-button"]',
        'button[type="submit"]',
        'button:has(svg)[aria-label*="Send"]',
    ]
    STREAMING_INDICATOR = [
        'button[aria-label="Stop Response"]',
        'button[aria-label="Stop"]',
        'div[data-is-streaming="true"]',
        'span.loading-indicator',
    ]
    ASSISTANT_MESSAGE = [
        'div[data-test-render-count]',
        'div.font-claude-message',
        'div[class*="prose"]',
    ]
    RESPONSE_TEXT = [
        'div.font-claude-message p',
        'div[class*="prose"] p',
        'div[class*="prose"]',
    ]
    NEW_CHAT = [
        'a[href="/new"]',
        'button[aria-label="New chat"]',
    ]


# ── Registry ─────────────────────────────────────────────────
TARGETS: dict[str, type] = {
    "gpt":    ChatGPTSelectors,
    "claude": ClaudeSelectors,
}

URLS: dict[str, str] = {
    "gpt":    "https://chat.openai.com",
    "claude": "https://claude.ai/new",
}

DEFAULT_TARGET = "gpt"
