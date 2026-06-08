"""
history.py
Logs test results per card and detects trends over time.
Cards are fingerprinted by capacity + filesystem label since SD cards
don't reliably expose serial numbers on Mac.

History is stored as a simple JSON file at ~/.sdcheck/history.json
"""

import os
import json
import time
import statistics
from datetime import datetime

HISTORY_DIR = os.path.expanduser("~/.sdcheck")
HISTORY_FILE = os.path.join(HISTORY_DIR, "history.json")


def _card_id(drive):
    """
    Fingerprint a card by label + reported capacity.
    Not perfect but workable without serial number access.
    """
    label = os.path.basename(drive["path"])
    capacity = drive["total_gb"]
    return f"{label}_{capacity}GB"


def _load():
    if not os.path.exists(HISTORY_FILE):
        return {}
    with open(HISTORY_FILE, "r") as f:
        return json.load(f)


def _save(data):
    os.makedirs(HISTORY_DIR, exist_ok=True)
    with open(HISTORY_FILE, "w") as f:
        json.dump(data, f, indent=2)


def log_result(drive, write_result, integrity_pass, cap_result=None):
    """
    Appends a test result to the card's history.
    """
    card_id = _card_id(drive)
    data = _load()

    if card_id not in data:
        data[card_id] = {
            "label": os.path.basename(drive["path"]),
            "capacity_gb": drive["total_gb"],
            "filesystem": drive["fstype"],
            "runs": []
        }

    entry = {
        "timestamp": datetime.now().isoformat(),
        "avg_write_speed": write_result["avg_speed"],
        "min_write_speed": write_result["min_speed"],
        "stability": write_result["stability"],
        "integrity_pass": integrity_pass,
        "capacity_pass": cap_result["pass"] if cap_result else None,
        "capacity_blocks_failed": cap_result["blocks_failed"] if cap_result else 0,
    }

    data[card_id]["runs"].append(entry)
    _save(data)
    return card_id


def analyze(drive):
    """
    Looks at this card's history and returns a trend analysis.

    Returns:
        {
            "run_count": int,
            "first_seen": str,
            "avg_speed_trend": float,   # MB/s change per month (negative = degrading)
            "integrity_failures": int,
            "health_assessment": str,   # "Good" / "Watch" / "Warning" / "Critical"
            "notes": [str],
        }
    """
    card_id = _card_id(drive)
    data = _load()

    if card_id not in data or len(data[card_id]["runs"]) < 2:
        return None

    runs = data[card_id]["runs"]
    speeds = [r["avg_write_speed"] for r in runs]
    timestamps = [datetime.fromisoformat(r["timestamp"]) for r in runs]
    integrity_failures = sum(1 for r in runs if not r["integrity_pass"])

    n = len(runs)
    t0 = timestamps[0]
    days_spread = (timestamps[-1] - t0).total_seconds() / (60 * 60 * 24)
    months = [(t - t0).total_seconds() / (60 * 60 * 24 * 30) for t in timestamps]

    # Skip slope if all runs are within 3 days -- near-zero time denominator
    # produces absurd numbers like -11000 MB/s per month
    if days_spread >= 3 and max(months) > 0:
        mean_t = sum(months) / n
        mean_s = sum(speeds) / n
        numerator = sum((months[i] - mean_t) * (speeds[i] - mean_s) for i in range(n))
        denominator = sum((months[i] - mean_t) ** 2 for i in range(n))
        slope = numerator / denominator if denominator != 0 else 0
    else:
        slope = 0

    # Speed drop from first to last run
    speed_drop_pct = ((speeds[0] - speeds[-1]) / speeds[0]) * 100 if speeds[0] > 0 else 0

    notes = []
    assessment = "Good"

    if integrity_failures > 0:
        notes.append(f"{integrity_failures} integrity failure(s) detected -- back up data immediately.")
        assessment = "Critical"
    if speed_drop_pct > 30:
        notes.append(f"Write speed has dropped {speed_drop_pct:.0f}% since first test.")
        assessment = "Warning" if assessment != "Critical" else assessment
    elif speed_drop_pct > 15:
        notes.append(f"Write speed has dropped {speed_drop_pct:.0f}% since first test.")
        assessment = "Watch" if assessment == "Good" else assessment
    if slope < -5:
        notes.append(f"Speed declining at ~{abs(slope):.1f} MB/s per month.")
        assessment = "Watch" if assessment == "Good" else assessment

    if not notes:
        notes.append("No concerning trends detected.")

    return {
        "run_count": n,
        "first_seen": runs[0]["timestamp"][:10],
        "avg_speed_trend": round(slope, 2),
        "integrity_failures": integrity_failures,
        "health_assessment": assessment,
        "notes": notes,
    }


def print_history(drive):
    """Prints the full run history for a card."""
    card_id = _card_id(drive)
    data = _load()

    if card_id not in data:
        print("  No history found for this card.")
        return

    runs = data[card_id]["runs"]
    print(f"\n  Card: {data[card_id]['label']} ({data[card_id]['capacity_gb']} GB)")
    print(f"  {'Date':<12} {'Avg Write':>10} {'Min Write':>10} {'Stability':>10} {'Integrity':>10}")
    print("  " + "-" * 58)
    for r in runs:
        date = r["timestamp"][:10]
        integrity = "PASS" if r["integrity_pass"] else "FAIL"
        print(f"  {date:<12} {r['avg_write_speed']:>9.1f}  {r['min_write_speed']:>9.1f}  {r['stability']:>9.1f}%  {integrity:>10}")
