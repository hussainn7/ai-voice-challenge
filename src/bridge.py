from __future__ import annotations

import asyncio
import json
import os
from typing import Optional

import websockets
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse
from twilio.twiml.voice_response import VoiceResponse, Connect

from .scenarios import get_scenario
from .storage import save_transcript

app = FastAPI()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.api_route("/voice", methods=["GET", "POST"])
async def voice(request: Request):
    scenario_id = request.query_params.get("scenario_id", "schedule_basic")
    public_url = os.getenv("PUBLIC_URL", "").rstrip("/")
    ws_host = public_url.replace("https://", "").replace("http://", "")

    response = VoiceResponse()
    connect = Connect()
    connect.stream(url=f"wss://{ws_host}/media-stream?scenario_id={scenario_id}")
    response.append(connect)
    return HTMLResponse(content=str(response), media_type="text/xml")


@app.websocket("/media-stream")
async def media_stream(websocket: WebSocket, scenario_id: str = "schedule_basic"):
    await websocket.accept()

    try:
        scenario = get_scenario(scenario_id)
    except ValueError:
        scenario = get_scenario("schedule_basic")

    transcript: list = []
    call_sid: Optional[str] = None
    stream_sid: Optional[str] = None

    async with websockets.connect(
        "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-12-17",
        additional_headers={
            "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
            "OpenAI-Beta": "realtime=v1",
        },
    ) as openai_ws:
        await openai_ws.send(json.dumps({
            "type": "session.update",
            "session": {
                "input_audio_format": "g711_ulaw",
                "output_audio_format": "g711_ulaw",
                "input_audio_transcription": {"model": "whisper-1"},
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 700,
                },
                "instructions": scenario.system_prompt,
                "voice": "shimmer",
            },
        }))

        async def twilio_to_openai():
            nonlocal call_sid, stream_sid
            try:
                async for message in websocket.iter_text():
                    data = json.loads(message)
                    event = data.get("event")

                    if event == "start":
                        call_sid = data["start"]["callSid"]
                        stream_sid = data["start"]["streamSid"]

                    elif event == "media":
                        await openai_ws.send(json.dumps({
                            "type": "input_audio_buffer.append",
                            "audio": data["media"]["payload"],
                        }))

                    elif event == "stop":
                        break
            except Exception:
                pass
            finally:
                await openai_ws.close()

        async def openai_to_twilio():
            try:
                async for raw in openai_ws:
                    data = json.loads(raw)
                    t = data.get("type", "")

                    if t == "response.audio.delta" and stream_sid:
                        await websocket.send_text(json.dumps({
                            "event": "media",
                            "streamSid": stream_sid,
                            "media": {"payload": data["delta"]},
                        }))

                    elif t == "input_audio_buffer.speech_started" and stream_sid:
                        # Agent started speaking — clear buffered bot audio (barge-in)
                        await websocket.send_text(json.dumps({
                            "event": "clear",
                            "streamSid": stream_sid,
                        }))

                    elif t == "response.audio_transcript.done":
                        text = data.get("transcript", "").strip()
                        if text:
                            transcript.append({"role": "patient", "text": text})

                    elif t == "conversation.item.input_audio_transcription.completed":
                        text = data.get("transcript", "").strip()
                        if text:
                            transcript.append({"role": "agent", "text": text})

            except Exception:
                pass

        await asyncio.gather(twilio_to_openai(), openai_to_twilio())

    if call_sid and transcript:
        save_transcript(call_sid, transcript, scenario_id)
