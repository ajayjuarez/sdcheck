"""
main.py
Entry point. Runs detect -> write -> integrity -> capacity -> score -> log -> trend -> eject.
"""

import platform
import subprocess

from core.detect import detect
from core.write_test import write_test
from core.read_test import read_test
from core.capacity import capacity_test
from core.history import log_result, analyze, print_history, _load, _card_id
from core.score import calculate, print_score


def eject(drive):
    path = drive["path"]
    system = platform.system()
    print(f"\nEjecting {path} ...")
    try:
        if system == "Darwin":
            result = subprocess.run(["diskutil", "eject", path], capture_output=True, text=True)
            if result.returncode == 0:
                print("  Card ejected safely. You can remove it.")
            else:
                print(f"  Could not auto-eject: {result.stderr.strip()}")
                print("  Eject manually from Finder before removing.")
        elif system == "Linux":
            subprocess.run(["umount", path], check=True)
            print("  Card unmounted. Safe to remove.")
        else:
            print("  Eject from your system tray before removing.")
    except Exception as e:
        print(f"  Eject failed: {e}. Please eject manually.")


def main():
    print("=" * 50)
    print("  sdcheck - SD Card Health Analyzer")
    print("=" * 50)

    drive = detect()
    if not drive:
        return

    if drive["free_gb"] < 0.6:
        print(f"\nWarning: only {drive['free_gb']} GB free. Need at least 512 MB.")
        return

    max_test_mb = int(drive["free_gb"] * 1024 * 0.8)
    test_size_mb = min(512, max_test_mb)

    write_result = write_test(drive["path"], file_size_mb=test_size_mb)
    if not write_result:
        print("Write test failed.")
        eject(drive)
        return

    read_result = read_test(drive["path"], expected_sha256=write_result["sha256"])
    if not read_result:
        print("Integrity check failed.")
        eject(drive)
        return

    integrity = read_result["integrity_pass"]
    cap_result = capacity_test(drive)

    log_result(drive, write_result, integrity, cap_result)

    history_data = _load()
    card_id = _card_id(drive)
    history_runs = history_data.get(card_id, {}).get("runs", [])

    score_result = calculate(write_result, integrity, cap_result, history_runs)
    print_score(score_result)

    print(f"\n  Write speed avg  : {write_result['avg_speed']} MB/s")
    print(f"  Write speed min  : {write_result['min_speed']} MB/s")
    print(f"  Write stability  : {write_result['stability']}%")
    print(f"  Integrity        : {'PASS' if integrity else 'FAIL -- card may be corrupted'}")
    if cap_result:
        cap_status = "PASS" if cap_result["pass"] else f"FAIL -- {cap_result['blocks_failed']} block(s) failed"
        print(f"  Capacity check   : {cap_status}")

    trend = analyze(drive)
    if trend:
        print(f"\n  --- Health Trend ({trend['run_count']} runs since {trend['first_seen']}) ---")
        print(f"  Speed trend      : {trend['avg_speed_trend']:+.1f} MB/s per month")
        print(f"  Integrity fails  : {trend['integrity_failures']}")
        for note in trend["notes"]:
            print(f"  * {note}")
    else:
        print(f"\n  Run again in a few days to start building a speed trend.")

    print("\n  --- Run History ---")
    print_history(drive)

    eject(drive)


if __name__ == "__main__":
    main()
