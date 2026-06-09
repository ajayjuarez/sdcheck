"""
score.py
Combines write speed, stability, integrity, and capacity results
into a single 0-100 risk score with a label.

Score breakdown:
  Write stability   30 pts
  Write speed       25 pts  (relative to card's own baseline if available)
  Integrity         25 pts
  Capacity          20 pts

Lower score = higher risk. Labels:
  80-100  Healthy
  60-79   Watch
  40-59   Warning
  0-39    Critical
"""


def calculate(write_result, integrity_pass, cap_result, history_runs=None):
    """
    Args:
        write_result  : dict from write_test
        integrity_pass: bool
        cap_result    : dict from capacity_test (or None)
        history_runs  : list of past run dicts from history (or None)

    Returns:
        {
            "score": int,       # 0-100
            "label": str,       # Healthy / Watch / Warning / Critical
            "breakdown": dict,  # points per category
            "flags": [str],     # specific issues found
        }
    """
    flags = []
    breakdown = {}

    # --- Write stability (30 pts) ---
    stability = write_result["stability"]
    if stability >= 96:
        stability_pts = 30
    elif stability >= 92:
        stability_pts = 26
    elif stability >= 85:
        stability_pts = 20
    elif stability >= 75:
        stability_pts = 14
    elif stability >= 60:
        stability_pts = 8
    else:
        stability_pts = 3
        flags.append(f"Write stability is low ({stability}%)")
    breakdown["write_stability"] = stability_pts

    # --- Write speed (25 pts) ---
    avg_speed = write_result["avg_speed"]
    min_speed = write_result["min_speed"]
    speed_drop_pct = ((avg_speed - min_speed) / avg_speed * 100) if avg_speed > 0 else 0

    # If we have history, compare to the card's own first recorded speed
    if history_runs and len(history_runs) >= 2:
        baseline_speed = history_runs[0]["avg_write_speed"]
        degradation_pct = ((baseline_speed - avg_speed) / baseline_speed * 100) if baseline_speed > 0 else 0
        if degradation_pct > 30:
            speed_pts = 5
            flags.append(f"Speed degraded {degradation_pct:.0f}% from baseline ({baseline_speed:.0f} -> {avg_speed:.0f} MB/s)")
        elif degradation_pct > 15:
            speed_pts = 14
            flags.append(f"Speed degraded {degradation_pct:.0f}% from baseline")
        elif degradation_pct > 5:
            speed_pts = 20
        else:
            speed_pts = 25
    else:
        # No baseline -- score on speed drop within this run
        if speed_drop_pct > 50:
            speed_pts = 5
            flags.append(f"Large speed drop within test ({speed_drop_pct:.0f}% below avg at worst)")
        elif speed_drop_pct > 35:
            speed_pts = 10
            flags.append(f"Noticeable speed drop during test ({speed_drop_pct:.0f}%)")
        elif speed_drop_pct > 20:
            speed_pts = 16
        elif speed_drop_pct > 10:
            speed_pts = 21
        else:
            speed_pts = 25
    breakdown["write_speed"] = speed_pts

    # --- Integrity (25 pts) ---
    if integrity_pass is True:
        integrity_pts = 25
    elif integrity_pass is False:
        integrity_pts = 0
        flags.append("Integrity check FAILED -- data was corrupted on the card")
    else:
        integrity_pts = 12  # unknown
    breakdown["integrity"] = integrity_pts

    # --- Capacity (20 pts) ---
    if cap_result is None:
        cap_pts = 10  # unknown
    elif cap_result["pass"]:
        cap_pts = 20
    else:
        failed = cap_result["blocks_failed"]
        total = cap_result["blocks_total"]
        failure_rate = failed / total
        if failure_rate > 0.5:
            cap_pts = 0
            flags.append(f"Capacity test: {failed}/{total} regions failed")
        elif failure_rate > 0.2:
            cap_pts = 6
            flags.append(f"Capacity test: {failed}/{total} regions failed")
        else:
            cap_pts = 12
            flags.append(f"Capacity test: {failed}/{total} regions failed")
    breakdown["capacity"] = cap_pts

    # --- History integrity failures ---
    if history_runs:
        past_integrity_fails = sum(1 for r in history_runs if not r.get("integrity_pass", True))
        if past_integrity_fails > 0:
            breakdown["integrity"] = 0
            flags.append(f"{past_integrity_fails} past integrity failure(s) on record")

    score = sum(breakdown.values())
    score = max(0, min(100, score))

    if score >= 80:
        label = "Healthy"
    elif score >= 60:
        label = "Watch"
    elif score >= 40:
        label = "Warning"
    else:
        label = "Critical"

    return {
        "score": score,
        "label": label,
        "breakdown": breakdown,
        "flags": flags,
    }


def print_score(result):
    score = result["score"]
    label = result["label"]

    # Visual bar
    filled = int(score / 5)
    bar = "#" * filled + "-" * (20 - filled)

    label_map = {"Healthy": "HEALTHY", "Watch": "WATCH", "Warning": "WARNING", "Critical": "CRITICAL"}

    print(f"\n  {'=' * 40}")
    print(f"  Health Score: {score}/100  [{label_map[label]}]")
    print(f"  [{bar}]")
    print(f"  {'=' * 40}")
    print(f"  Breakdown:")
    print(f"    Write stability : {result['breakdown']['write_stability']}/30")
    print(f"    Write speed     : {result['breakdown']['write_speed']}/25")
    print(f"    Integrity       : {result['breakdown']['integrity']}/25")
    print(f"    Capacity        : {result['breakdown']['capacity']}/20")
    if result["flags"]:
        print(f"  Issues:")
        for f in result["flags"]:
            print(f"    ! {f}")
