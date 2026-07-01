import json
from datetime import datetime
from pathlib import Path

import httpx

CALLS_DIR = Path("calls")


def _next_prefix() -> str:
    CALLS_DIR.mkdir(exist_ok=True)
    existing = list(CALLS_DIR.glob("call-*.json"))
    return f"call-{len(existing) + 1:02d}"


def save_transcript(call_sid: str, transcript: list[dict], scenario_id: str) -> str:
    CALLS_DIR.mkdir(exist_ok=True)
    prefix = _next_prefix()

    data = {
        "prefix": prefix,
        "call_sid": call_sid,
        "scenario_id": scenario_id,
        "timestamp": datetime.now().isoformat(),
        "transcript": transcript,
    }
    (CALLS_DIR / f"{prefix}.json").write_text(json.dumps(data, indent=2))

    with open(CALLS_DIR / f"{prefix}.txt", "w") as f:
        f.write(f"Scenario: {scenario_id}\n")
        f.write(f"Call SID: {call_sid}\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write("-" * 60 + "\n\n")
        for entry in transcript:
            label = "PATIENT" if entry["role"] == "patient" else "AGENT  "
            f.write(f"[{label}]: {entry['text']}\n\n")

    # Track call_sid → prefix so caller.py can look it up
    mapping_file = CALLS_DIR / ".sid_map.json"
    mapping: dict = {}
    if mapping_file.exists():
        mapping = json.loads(mapping_file.read_text())
    mapping[call_sid] = prefix
    mapping_file.write_text(json.dumps(mapping))

    return prefix


def get_prefix_for_sid(call_sid: str) -> str | None:
    mapping_file = CALLS_DIR / ".sid_map.json"
    if not mapping_file.exists():
        return None
    return json.loads(mapping_file.read_text()).get(call_sid)


def load_transcript(prefix: str) -> dict | None:
    path = CALLS_DIR / f"{prefix}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def download_recording(recording_url: str, prefix: str, account_sid: str, auth_token: str) -> Path:
    mp3_path = CALLS_DIR / f"{prefix}.mp3"
    with httpx.Client(auth=(account_sid, auth_token), timeout=30) as client:
        r = client.get(recording_url, follow_redirects=True)
        r.raise_for_status()
        mp3_path.write_bytes(r.content)
    return mp3_path
