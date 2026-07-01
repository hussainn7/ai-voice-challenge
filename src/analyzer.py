import json

from openai import OpenAI

from .scenarios import Scenario

_client = OpenAI()


def analyze_call(transcript: list[dict], scenario: Scenario) -> dict:
    if not transcript:
        return {"bugs": [], "goal_achieved": False, "quality_score": 0, "notes": "Empty transcript."}

    formatted = "\n".join(
        f"[{'PATIENT' if e['role'] == 'patient' else 'AGENT'}]: {e['text']}"
        for e in transcript
    )

    prompt = f"""You are reviewing a call between a patient (caller) and an AI medical office agent.

Scenario: {scenario.name}
Patient goal: {scenario.goal}
Expected agent behavior: {scenario.expected_behavior}

Transcript:
{formatted}

Identify any bugs or quality issues in the agent's responses. For each issue found, note:
- What happened
- Why it's a problem
- Severity: high, medium, or low
- The relevant transcript excerpt

Also assess whether the patient ultimately achieved their goal.

Respond ONLY in valid JSON:
{{
  "goal_achieved": true,
  "goal_notes": "brief explanation",
  "bugs": [
    {{
      "severity": "high|medium|low",
      "description": "what went wrong",
      "excerpt": "relevant quote from transcript",
      "expected": "what should have happened"
    }}
  ],
  "quality_score": 7,
  "notes": "overall observations"
}}"""

    response = _client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )

    return json.loads(response.choices[0].message.content)
