from __future__ import annotations

import os
import time
import threading
from pathlib import Path
from typing import Optional

import typer
import uvicorn
import httpx
from dotenv import load_dotenv

load_dotenv()

app = typer.Typer(help="PGAI voice bot — automated patient call simulator")


def _start_server():
    uvicorn.run("src.bridge:app", host="0.0.0.0", port=8000, log_level="warning", access_log=False)


def _wait_for_server(timeout: int = 15) -> bool:
    for _ in range(timeout):
        try:
            r = httpx.get("http://localhost:8000/health", timeout=1)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def _run_scenario(scenario_id: str, analyze: bool = True) -> Optional[str]:
    from src.caller import make_call
    from src.storage import get_prefix_for_sid, download_recording, load_transcript
    from src.scenarios import get_scenario
    from src.analyzer import analyze_call

    result = make_call(scenario_id)

    # Wait for the bridge to finish writing the transcript
    time.sleep(4)

    prefix = get_prefix_for_sid(result["call_sid"])
    if not prefix:
        print("  ⚠  Transcript not saved (call may have failed before connecting)")
        return None

    if result["recording_url"]:
        try:
            download_recording(
                result["recording_url"],
                prefix,
                os.getenv("TWILIO_ACCOUNT_SID"),
                os.getenv("TWILIO_AUTH_TOKEN"),
            )
            print(f"  ✓ calls/{prefix}.mp3")
        except Exception as e:
            print(f"  ⚠  Recording download failed: {e}")

    if analyze:
        data = load_transcript(prefix)
        if data and data.get("transcript"):
            scenario = get_scenario(scenario_id)
            analysis = analyze_call(data["transcript"], scenario)
            _append_bug_report(prefix, scenario_id, analysis)
            goal = "✓" if analysis.get("goal_achieved") else "✗"
            bugs = len(analysis.get("bugs", []))
            score = analysis.get("quality_score", "?")
            print(f"  Goal {goal}  |  Score: {score}/10  |  Bugs found: {bugs}")
        else:
            print("  ⚠  Transcript empty — skipping analysis")

    print(f"  → calls/{prefix}.*")
    return prefix


def _append_bug_report(prefix: str, scenario_id: str, analysis: dict):
    bugs = analysis.get("bugs", [])
    if not bugs and analysis.get("goal_achieved"):
        return

    report = Path("bug-report.md")
    with open(report, "a") as f:
        f.write(f"\n## {prefix} — {scenario_id}\n\n")
        f.write(f"**Quality score:** {analysis.get('quality_score')}/10  ")
        f.write(f"**Goal achieved:** {'Yes' if analysis.get('goal_achieved') else 'No'}\n\n")
        if analysis.get("goal_notes"):
            f.write(f"{analysis['goal_notes']}\n\n")
        for bug in bugs:
            sev = bug.get("severity", "medium").upper()
            f.write(f"### [{sev}] {bug.get('description', '')}\n\n")
            if bug.get("excerpt"):
                f.write(f"**Transcript excerpt:** _{bug['excerpt']}_\n\n")
            if bug.get("expected"):
                f.write(f"**Expected behavior:** {bug['expected']}\n\n")


@app.command()
def call(
    scenario_id: str = typer.Argument("schedule_basic", help="Scenario ID to run"),
    no_analyze: bool = typer.Option(False, "--no-analyze", help="Skip post-call analysis"),
):
    """Run a single call with the given scenario."""
    print("Starting bridge server...")
    threading.Thread(target=_start_server, daemon=True).start()
    if not _wait_for_server():
        print("Server failed to start. Check that port 8000 is free.")
        raise typer.Exit(1)
    print("Server ready.\n")

    print(f"Scenario: {scenario_id}")
    _run_scenario(scenario_id, analyze=not no_analyze)


@app.command()
def batch(
    cooldown: int = typer.Option(30, help="Seconds to wait between calls"),
    no_analyze: bool = typer.Option(False, "--no-analyze", help="Skip post-call analysis"),
):
    """Run all 12 scenarios in sequence."""
    from src.scenarios import SCENARIOS

    print("Starting bridge server...")
    threading.Thread(target=_start_server, daemon=True).start()
    if not _wait_for_server():
        print("Server failed to start. Check that port 8000 is free.")
        raise typer.Exit(1)
    print(f"Server ready. Running {len(SCENARIOS)} scenarios.\n")

    # Initialize bug report header if it doesn't exist
    report = Path("bug-report.md")
    if not report.exists():
        report.write_text("# Bug Report\n\nIssues found by the automated call analysis.\n")

    for i, scenario in enumerate(SCENARIOS, 1):
        print(f"[{i}/{len(SCENARIOS)}] {scenario.name}")
        _run_scenario(scenario.id, analyze=not no_analyze)
        if i < len(SCENARIOS):
            print(f"  Waiting {cooldown}s...\n")
            time.sleep(cooldown)

    print("\nAll done. See calls/ for recordings and transcripts, bug-report.md for findings.")


@app.command(name="list-scenarios")
def list_scenarios():
    """List all available scenario IDs."""
    from src.scenarios import SCENARIOS

    print(f"{'ID':<25} {'Name'}")
    print("-" * 60)
    for s in SCENARIOS:
        print(f"{s.id:<25} {s.name}")


if __name__ == "__main__":
    app()
