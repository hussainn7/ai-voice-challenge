from __future__ import annotations

import os
import time
from typing import Optional

from twilio.rest import Client


def get_client() -> Client:
    return Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))


def make_call(scenario_id: str) -> dict:
    client = get_client()
    public_url = os.getenv("PUBLIC_URL", "").rstrip("/")
    target = os.getenv("TARGET_NUMBER", "+18054398008")
    from_number = os.getenv("TWILIO_PHONE_NUMBER")

    call = client.calls.create(
        to=target,
        from_=from_number,
        url=f"{public_url}/voice?scenario_id={scenario_id}",
        record=True,
        time_limit=180,
    )

    call_sid = call.sid
    print(f"  → SID: {call_sid}")

    while True:
        call = client.calls(call_sid).fetch()
        if call.status in ("completed", "failed", "busy", "no-answer", "canceled"):
            break
        time.sleep(3)

    print(f"  → Status: {call.status}, duration: {call.duration}s")

    recording_url = _get_recording_url(client, call_sid)
    return {
        "call_sid": call_sid,
        "status": call.status,
        "duration": call.duration,
        "recording_url": recording_url,
        "scenario_id": scenario_id,
    }


def _get_recording_url(client: Client, call_sid: str, retries: int = 8) -> Optional[str]:
    for attempt in range(retries):
        recordings = client.recordings.list(call_sid=call_sid, limit=1)
        if recordings:
            rec = recordings[0]
            return f"https://api.twilio.com{rec.uri.replace('.json', '.mp3')}"
        wait = 5 if attempt < 3 else 10
        print(f"  Recording not ready, retrying in {wait}s... ({attempt + 1}/{retries})")
        time.sleep(wait)
    return None
