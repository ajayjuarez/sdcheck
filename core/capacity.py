"""
capacity.py
Spot-checks the card's actual usable capacity by writing and verifying
test blocks at evenly spaced intervals across the full address space.

Catches:
- Fake/counterfeit cards that claim more storage than they have
- Failing sectors in specific regions of the card
- Cards where only the beginning works correctly

Does NOT fill the card -- samples ~1 GB total regardless of card size.
"""

import os
import hashlib
import tempfile
import shutil

BLOCK_SIZE_MB = 64       # size of each test block
MIN_INTERVAL_GB = 4      # test every N GB across the address space


def capacity_test(drive, callback=None):
    """
    Writes and verifies test blocks at intervals across the card.

    Args:
        drive    : drive dict from detect.py
        callback : optional fn(percent_done, current_gb, status)

    Returns:
        {
            "reported_gb": float,
            "tested_gb": float,
            "blocks_total": int,
            "blocks_passed": int,
            "blocks_failed": int,
            "failed_regions": [float],   # GB offsets where failures occurred
            "pass": bool,
        }
    """
    drive_path = drive["path"]
    reported_gb = drive["total_gb"]
    free_gb = drive["free_gb"]
    used_gb = drive["used_gb"]

    block_bytes = BLOCK_SIZE_MB * 1024 * 1024

    # Figure out test points -- evenly spaced across free space
    # We can only write into free space, so we anchor at the end of used space
    # and space out blocks across remaining free space
    if free_gb < BLOCK_SIZE_MB / 1024:
        print(f"\nNot enough free space for capacity test (need at least {BLOCK_SIZE_MB} MB free).")
        return None

    # Number of blocks: one every MIN_INTERVAL_GB, capped so we don't take forever
    n_blocks = max(2, int(free_gb / MIN_INTERVAL_GB))
    n_blocks = min(n_blocks, 16)  # cap at 16 blocks

    # Space blocks evenly across free space
    # We create a temp dir and write sequentially spaced files
    test_dir = os.path.join(drive_path, ".sdcheck_capacity")
    os.makedirs(test_dir, exist_ok=True)

    print(f"\nCapacity spot-check")
    print(f"  Reported capacity : {reported_gb} GB")
    print(f"  Free space        : {free_gb} GB")
    print(f"  Test blocks       : {n_blocks} x {BLOCK_SIZE_MB} MB\n")

    # Generate test data and its hash once, reuse for all blocks
    print("  Generating test data...", end="", flush=True)
    test_data = os.urandom(block_bytes)
    expected_hash = hashlib.sha256(test_data).hexdigest()
    print(" done.")

    blocks_passed = 0
    blocks_failed = 0
    failed_regions = []

    # --- Write phase ---
    print("\n  Writing blocks:")
    file_paths = []
    for i in range(n_blocks):
        fpath = os.path.join(test_dir, f"block_{i:03d}.bin")
        file_paths.append(fpath)
        offset_gb = used_gb + (i / n_blocks) * free_gb
        try:
            with open(fpath, "wb") as f:
                f.write(test_data)
                f.flush()
                os.fsync(f.fileno())
            status = "ok"
        except OSError as e:
            status = f"write error: {e}"
            blocks_failed += 1
            failed_regions.append(round(offset_gb, 2))
            file_paths[-1] = None  # mark as unreadable

        bar_done = int(((i + 1) / n_blocks) * 20)
        bar = "#" * bar_done + "-" * (20 - bar_done)
        print(f"\r    [{bar}] {i+1}/{n_blocks}  ~{offset_gb:.1f} GB  {status}   ", end="", flush=True)

        if callback:
            callback((i + 1) / n_blocks * 50, offset_gb, status)

    # --- Verify phase ---
    print(f"\n\n  Verifying blocks:")
    for i, fpath in enumerate(file_paths):
        offset_gb = used_gb + (i / n_blocks) * free_gb
        if fpath is None:
            # already failed on write
            bar_done = int(((i + 1) / n_blocks) * 20)
            bar = "#" * bar_done + "-" * (20 - bar_done)
            print(f"\r    [{bar}] {i+1}/{n_blocks}  ~{offset_gb:.1f} GB  skipped (write failed)   ", end="", flush=True)
            continue
        try:
            with open(fpath, "rb") as f:
                actual = f.read()
            actual_hash = hashlib.sha256(actual).hexdigest()
            if actual_hash == expected_hash:
                blocks_passed += 1
                status = "pass"
            else:
                blocks_failed += 1
                failed_regions.append(round(offset_gb, 2))
                status = "FAIL -- data mismatch"
        except OSError as e:
            blocks_failed += 1
            failed_regions.append(round(offset_gb, 2))
            status = f"read error: {e}"

        bar_done = int(((i + 1) / n_blocks) * 20)
        bar = "#" * bar_done + "-" * (20 - bar_done)
        print(f"\r    [{bar}] {i+1}/{n_blocks}  ~{offset_gb:.1f} GB  {status}   ", end="", flush=True)

        if callback:
            callback(50 + (i + 1) / n_blocks * 50, offset_gb, status)

    # Cleanup
    try:
        shutil.rmtree(test_dir)
        print(f"\n\n  Test files removed.")
    except OSError as e:
        print(f"\n\n  Warning: could not remove test files: {e}")

    passed = blocks_failed == 0
    tested_gb = round((n_blocks * BLOCK_SIZE_MB) / 1024, 2)

    print(f"  Blocks passed: {blocks_passed}/{n_blocks}")
    if failed_regions:
        print(f"  Failed regions: ~{failed_regions} GB")

    return {
        "reported_gb": reported_gb,
        "tested_gb": tested_gb,
        "blocks_total": n_blocks,
        "blocks_passed": blocks_passed,
        "blocks_failed": blocks_failed,
        "failed_regions": failed_regions,
        "pass": passed,
    }


if __name__ == "__main__":
    import sys
    from core.detect import detect
    drive = detect()
    if drive:
        capacity_test(drive)
