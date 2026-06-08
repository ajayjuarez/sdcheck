"""
write_test.py
Writes a large test file to the card in chunks, measuring speed over time.
Returns a list of (elapsed_seconds, mb_per_second) samples.
"""

import os
import time
import hashlib
import tempfile

# Defaults
CHUNK_SIZE_MB = 16          # write in 16 MB chunks
DEFAULT_FILE_SIZE_MB = 512  # total file to write


def write_test(drive_path, file_size_mb=DEFAULT_FILE_SIZE_MB, chunk_size_mb=CHUNK_SIZE_MB, callback=None):
    """
    Writes a test file to drive_path in chunks.

    Args:
        drive_path      : mount point of the SD card
        file_size_mb    : total size of test file in MB
        chunk_size_mb   : size of each write chunk in MB
        callback        : optional fn(elapsed, speed_mbs, percent_done) called after each chunk

    Returns:
        {
            "samples": [(elapsed_s, speed_mbs), ...],
            "avg_speed": float,
            "min_speed": float,
            "max_speed": float,
            "stability": float,   # 0-100, higher = more stable
            "file_path": str,
            "sha256": str,
            "total_mb": float,
            "duration_s": float,
        }
    """
    chunk_bytes = chunk_size_mb * 1024 * 1024
    total_bytes = file_size_mb * 1024 * 1024
    chunk_data = os.urandom(chunk_bytes)  # random data defeats compression tricks

    test_file = os.path.join(drive_path, ".sdcheck_write_test.bin")
    hasher = hashlib.sha256()
    samples = []
    bytes_written = 0
    start_time = time.time()

    print(f"\nWrite test: {file_size_mb} MB in {chunk_size_mb} MB chunks")
    print(f"Target: {test_file}\n")

    try:
        with open(test_file, "wb") as f:
            while bytes_written < total_bytes:
                # last chunk may be smaller
                remaining = total_bytes - bytes_written
                data = chunk_data if remaining >= chunk_bytes else os.urandom(remaining)

                chunk_start = time.time()
                f.write(data)
                f.flush()
                os.fsync(f.fileno())  # force actual write to card, not OS cache
                chunk_elapsed = time.time() - chunk_start

                hasher.update(data)
                bytes_written += len(data)

                speed_mbs = (len(data) / 1e6) / chunk_elapsed if chunk_elapsed > 0 else 0
                total_elapsed = time.time() - start_time
                percent = (bytes_written / total_bytes) * 100

                samples.append((round(total_elapsed, 2), round(speed_mbs, 2)))

                bar = "#" * int(percent / 5) + "-" * (20 - int(percent / 5))
                print(f"\r  [{bar}] {percent:5.1f}%  {speed_mbs:6.1f} MB/s", end="", flush=True)

                if callback:
                    callback(total_elapsed, speed_mbs, percent)

    except OSError as e:
        print(f"\nWrite error: {e}")
        return None

    total_duration = time.time() - start_time
    speeds = [s[1] for s in samples]
    avg = sum(speeds) / len(speeds)
    mn = min(speeds)
    mx = max(speeds)

    # stability: how tight the speed distribution is (0=wildly variable, 100=rock solid)
    import statistics
    std = statistics.stdev(speeds) if len(speeds) > 1 else 0
    stability = max(0, round(100 - (std / avg * 100), 1)) if avg > 0 else 0

    print(f"\n\n  Done in {total_duration:.1f}s")
    print(f"  Avg: {avg:.1f} MB/s  |  Min: {mn:.1f} MB/s  |  Max: {mx:.1f} MB/s  |  Stability: {stability}%")

    return {
        "samples": samples,
        "avg_speed": round(avg, 2),
        "min_speed": round(mn, 2),
        "max_speed": round(mx, 2),
        "stability": stability,
        "file_path": test_file,
        "sha256": hasher.hexdigest(),
        "total_mb": round(bytes_written / 1e6, 2),
        "duration_s": round(total_duration, 2),
    }


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "/Volumes/SDCARD"
    result = write_test(path, file_size_mb=128)
    if result:
        print(f"\nSHA256: {result['sha256']}")
