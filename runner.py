"""
Runs the student's prompt on the level's sample input using OpenRouter.
"""

import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "openai/gpt-4o-mini"


def run_student_prompt(student_prompt: str, sample_input: str) -> str:
    """
    Execute the student's prompt on the given sample input.
    Returns the raw text output from the model.
    """
    if not student_prompt or not student_prompt.strip():
        return "⚠️ No prompt provided. Write your prompt in the editor."

    if not OPENROUTER_API_KEY:
        return "⚠️ OpenRouter API key not configured. Set OPENROUTER_API_KEY in .env"

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8501",
        "X-Title": "Prompt Doctor"
    }

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": student_prompt},
            {"role": "user", "content": sample_input}
        ],
        "temperature": 0.3,
        "max_tokens": 2048
    }

    try:
        response = requests.post(
            OPENROUTER_URL,
            headers=headers,
            json=payload,
            timeout=60
        )
        response.raise_for_status()
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        return content

    except requests.exceptions.Timeout:
        return "⚠️ Request timed out. Try simplifying your prompt."
    except requests.exceptions.RequestException as e:
        return f"⚠️ API error: {str(e)}"
    except (KeyError, IndexError) as e:
        return f"⚠️ Unexpected response format: {str(e)}"