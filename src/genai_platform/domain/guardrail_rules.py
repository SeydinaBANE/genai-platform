import re


def check_prompt_injection(text: str) -> str | None:
    injection_patterns = [
        r"ignore\s+(all\s+)?(previous|above|below)\s+(instructions|prompts|commands)",
        r"system\s+prompt",
        r"you\s+are\s+(not\s+)?(an?\s+)?(ai|assistant|chatbot)",
        r"forget\s+(everything|all)",
        r"override\s+(your\s+)?(instructions|prompt|commands)",
        r"new\s+instructions?",
        r"disregard",
        r"act\s+as\s+if",
        r"do\s+(not\s+)?(follow|obey|listen)",
    ]

    text_lower = text.lower()
    for pattern in injection_patterns:
        if re.search(pattern, text_lower):
            return f"prompt_injection: {pattern}"

    return None


def check_toxicity(text: str) -> str | None:
    toxic_keywords = [
        "hack",
        "crack",
        "exploit",
        "bypass",
        "jailbreak",
        "sudo",
        "terminal",
        "cmd",
        "shell",
    ]
    text_lower = text.lower()
    for keyword in toxic_keywords:
        if keyword in text_lower:
            return f"toxic_content: {keyword}"

    return None
