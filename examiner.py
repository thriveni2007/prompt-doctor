"""
Examiner — the prompt that grades prompts.

YOU BUILD THIS: the examiner's system prompt, the grading call,
and the parsing that turns the JSON verdict into the on-screen ✓ / ✗ panel.
"""

import os
import json
import re
import requests
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# Pin a capable judge model for consistent grading
JUDGE_MODEL = "openai/gpt-4o-mini"


def _build_examiner_system_prompt(level: int, principles: list) -> str:
    """
    Build the examiner's system prompt — the master-class prompt that grades prompts.
    Encodes every principle from the spec: role, scope, evidence, coaching, reasoning, structured output.
    """
    principles_text = "\n".join(f"- {p}" for p in principles)

    return f"""You are the Examiner: a strict but fair prompt-engineering assessor.

Your job is to evaluate a STUDENT_PROMPT that was written for a specific task at Level {level}.

## Principles to grade (Level {level})

Judge the STUDENT_PROMPT against ONLY these principles:

{principles_text}

## Grading rules (obey these exactly)

1. **Judge against the principles in your OWN words** — be specific. Do not just restate the principle; explain how the prompt does or does not meet it.
2. **For each failed principle**, quote the exact weak phrase from the student's prompt (or name what is missing if it's absent entirely).
3. **Ask ONE pointed question per failure** that leads the student toward the fix — never give an example fix.
4. **NEVER write, rewrite, or give an example of a corrected prompt.** Diagnose only. Coaching, not curing.
5. **Reason step by step** before the verdict (chain-of-thought), then output ONLY the JSON verdict.

## Output format

Return ONLY valid JSON with this exact schema. No markdown, no code fences, no commentary outside the JSON:

{{
  "level": {level},
  "principles": [
    {{
      "name": "principle_short_name",
      "pass": true,
      "weakness": "",
      "question": ""
    }}
  ],
  "ran_ok": true,
  "verdict": "revise"
}}

- "pass": true if the principle is satisfied, false if not
- "weakness": for failed principles, quote the exact weak phrase or describe what's missing. Empty string if passed.
- "question": for failed principles, one pointed coaching question. Empty string if passed.
- "verdict": "pass" if ALL principles pass, "revise" if any principle fails

Think step by step, then output ONLY the JSON.
"""


def _build_examiner_user_prompt(student_prompt: str, sample_input: str, level_task: str) -> str:
    """Build the user message for the examiner with the student's prompt and context."""
    return f"""Here is the task the student was asked to solve at Level {level_task}:

---

Now grade this STUDENT PROMPT on the task described above.

## Student's Prompt:
```
{student_prompt}
```

## Sample Input the student's prompt was run on:
```
{sample_input}
```

Evaluate the student's prompt against the principles for this level.
Think step by step about each principle, then output only the JSON verdict."""


def _run_student_and_get_output(student_prompt: str, sample_input: str) -> str:
    """Run the student's prompt on the sample input and return the model output."""
    if not student_prompt or not student_prompt.strip():
        return "[No prompt provided]"

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8501",
        "X-Title": "Prompt Doctor"
    }

    payload = {
        "model": JUDGE_MODEL,
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
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        return f"[Error running student prompt: {str(e)}]"


def _call_examiner(system_prompt: str, user_prompt: str) -> str:
    """Call the judge model with the examiner's prompt."""
    if not OPENROUTER_API_KEY:
        return json.dumps({
            "level": 1,
            "principles": [],
            "ran_ok": False,
            "verdict": "revise",
            "_error": "API key not configured"
        })

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8501",
        "X-Title": "Prompt Doctor Examiner"
    }

    payload = {
        "model": JUDGE_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.2,  # Low temp for consistent grading
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
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        return json.dumps({
            "level": 1,
            "principles": [],
            "ran_ok": False,
            "verdict": "revise",
            "_error": f"Examiner API call failed: {str(e)}"
        })


def _parse_verdict(examiner_output: str, level: int, principles: list) -> dict:
    """
    Parse the examiner's JSON verdict from its output.
    Handles markdown fences, extra text, and malformed JSON gracefully.
    Returns a clean verdict dict.
    """
    # Default fallback structure
    default_principles = [
        {"name": p.split(":")[0].strip(), "pass": False,
         "weakness": "Could not grade — examiner error.",
         "question": "Review the principle and revise your prompt."}
        for p in principles
    ]

    default_verdict = {
        "level": level,
        "principles": default_principles,
        "ran_ok": False,
        "verdict": "revise"
    }

    if not examiner_output or examiner_output.strip().startswith("["):
        return default_verdict

    # Try to extract JSON from markdown code fences
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', examiner_output)
    json_str = json_match.group(1) if json_match else examiner_output.strip()

    # Also try to find JSON object directly (starts with {)
    if not json_match:
        brace_start = examiner_output.find('{')
        brace_end = examiner_output.rfind('}')
        if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
            json_str = examiner_output[brace_start:brace_end + 1]

    try:
        parsed = json.loads(json_str)

        # Validate structure
        if "principles" not in parsed or not isinstance(parsed["principles"], list):
            return default_verdict

        # Normalize principle names to match our short names
        normalized = []
        for p_def in principles:
            short_name = p_def.split(":")[0].strip()
            # Find matching entry in parsed
            matched = None
            for pp in parsed["principles"]:
                pname = pp.get("name", "").strip().lower()
                if short_name.lower() in pname or pname in short_name.lower():
                    matched = pp
                    break

            if matched:
                normalized.append({
                    "name": short_name,
                    "pass": bool(matched.get("pass", False)),
                    "weakness": matched.get("weakness", ""),
                    "question": matched.get("question", "")
                })
            else:
                normalized.append({
                    "name": short_name,
                    "pass": False,
                    "weakness": "Not assessed by examiner.",
                    "question": "Review this principle in your prompt."
                })

        all_pass = all(p["pass"] for p in normalized)
        return {
            "level": level,
            "principles": normalized,
            "ran_ok": True,
            "verdict": "pass" if all_pass else "revise"
        }

    except (json.JSONDecodeError, KeyError, TypeError):
        return default_verdict


def grade_prompt(student_prompt: str, level: int, principles: list,
                 sample_input: str, level_task: str, level_name: str) -> dict:
    """
    Main entry point — grade a student's prompt for a given level.
    
    1. Runs the student's prompt on the sample input (to show live output).
    2. Calls the examiner to grade the prompt against the level's principles.
    3. Returns a verdict dict + the live output.
    
    Returns:
        dict with keys:
            - verdict: the parsed examiner verdict
            - live_output: the output from running the student's prompt
            - examiner_raw: the raw examiner output (for debugging)
    """
    # Step 1: Run the student's prompt
    live_output = _run_student_and_get_output(student_prompt, sample_input)

    # Step 2: Build the examiner prompt
    system_prompt = _build_examiner_system_prompt(level, principles)
    user_prompt = (
        f"Level {level}: {level_name}\n\n"
        f"Task: {level_task}\n\n"
        f"Sample Input:\n{sample_input}\n\n"
        f"Student's Prompt:\n```\n{student_prompt}\n```\n\n"
        f"Evaluate this prompt against the Level {level} principles and return ONLY the JSON verdict."
    )

    # Step 3: Call the examiner
    examiner_raw = _call_examiner(system_prompt, user_prompt)

    # Step 4: Parse the verdict
    verdict = _parse_verdict(examiner_raw, level, principles)

    return {
        "verdict": verdict,
        "live_output": live_output,
        "examiner_raw": examiner_raw
    }