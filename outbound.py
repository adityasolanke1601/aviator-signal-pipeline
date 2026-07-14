"""
outbound.py — turns raw GitHub signals into a signal-based, non-templated
outbound message. No {{first_name}} merge tags: every line has to be true
because of the data, not generic flattery.

Supports two providers, picked via LLM_PROVIDER env var:
- "gemini" (default) — Google's free tier, no card needed. Good for demos.
- "claude"            — Anthropic API, paid per token, better prose quality.
"""

import os

PROVIDER = os.getenv("LLM_PROVIDER", "gemini")  # "gemini" or "claude"
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5")

SYSTEM_PROMPT = """You write cold outbound emails for Aviator, a company that sells
MergeQueue (eliminates merge conflicts/broken builds) and FlexReview (intelligent
code review routing) to engineering leaders (staff eng, platform leads, DevEx teams).

Rules:
- Never use generic flattery or merge-tag-style personalization.
- Every claim must be traceable to the signal data provided.
- Reference the SPECIFIC repo, PR volume, or CI setup you were given.
- Keep it under 90 words. No subject line fluff, no "I hope this finds you well."
- End with a low-friction ask (15 min, not "let's hop on a call this week").
- Sound like an engineer wrote it, not a sequencer.
"""


def _build_user_prompt(signal: dict) -> str:
    return f"""
Company/org: {signal['org']}
Biggest repo: {signal['biggest_repo']}
Repos analyzed: {signal['repos_analyzed']}
Combined repo size (KB, proxy for monorepo scale): {signal['total_size_kb']}
CI (GitHub Actions) adoption across analyzed repos: {signal['ci_adoption_pct']}%
PR throughput, last 30 days: {signal['pr_throughput_30d']}
Primary languages: {signal['languages']}
Computed fit score (0-100): {signal['fit_score']}

Write the outbound email.
"""


def _generate_gemini(signal: dict) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    resp = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=_build_user_prompt(signal),
        config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
    )
    return resp.text


def _generate_claude(signal: dict) -> str:
    from anthropic import Anthropic

    client = Anthropic()  # reads ANTHROPIC_API_KEY from env
    resp = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_prompt(signal)}],
    )
    return "".join(block.text for block in resp.content if block.type == "text")


def generate_outbound(signal: dict) -> str:
    if not signal.get("found"):
        return ""

    if PROVIDER == "gemini":
        return _generate_gemini(signal)
    elif PROVIDER == "claude":
        return _generate_claude(signal)
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {PROVIDER!r}, use 'gemini' or 'claude'")


if __name__ == "__main__":
    sample = {
        "org": "supabase",
        "found": True,
        "biggest_repo": "supabase",
        "repos_analyzed": 8,
        "total_size_kb": 240000,
        "ci_adoption_pct": 87.5,
        "pr_throughput_30d": 214,
        "languages": "TypeScript, Go, Rust",
        "fit_score": 82.3,
    }
    print(generate_outbound(sample))
