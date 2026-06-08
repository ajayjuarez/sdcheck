"""
read_test.py
Reads back the test file written by write_test.py and verifies the SHA-256 checksum.
Speed measurement is intentionally skipped -- Mac caches make it unreliable without ejecting.
The checksum comparison is the meaningful output here.
"""

import os
import hashlib

TEST_FILE_NAME = ".sdcheck_write_test.bin"
CHUNK_SIZE_MB = 16


def read_test(drive_path, expected_sha256=None, callback=None):
    """
    Reads the test file back and verifies integrity via SHA-256.

    Returns:
        {
            "total_mb": float,
            "sha256": str,
            "integrity_pass": bool or None,
        }
    """
    test_file = os.path.join(drive_path, TEST_FILE_NAME)

    if not os.path.exists(test_file):
        print(f"\nTest file not found at {test_file}")
        print("Run the write test first.")
        return None

    file_size = os.path.getsize(test_file)
    chunk_bytes = CHUNK_SIZE_MB * 1024 * 1024
    hasher = hashlib.sha256()
    bytes_read = 0

    print(f"\nIntegrity check: reading back {round(file_size / 1e6)} MB and verifying checksum...\n")

    try:
        with open(test_file, "rb") as f:
            while True:
                data = f.read(chunk_bytes)
                if not data:
                    break
                hasher.update(data)
                bytes_read += len(data)
                percent = (bytes_read / file_size) * 100
                bar = "#" * int(percent / 5) + "-" * (20 - int(percent / 5))
                print(f"\r  [{bar}] {percent:5.1f}%", end="", flush=True)

                if callback:
                    callback(percent)

    except OSError as e:
        print(f"\nRead error: {e}")
        return None

    sha256 = hasher.hexdigest()

    if expected_sha256:
        integrity_pass = sha256 == expected_sha256
        result_str = "PASS" if integrity_pass else "FAIL -- data mismatch, card may be corrupted"
    else:
        integrity_pass = None
        result_str = "skipped (no expected hash provided)"

    print(f"\n\n  Integrity: {result_str}")

    try:
        os.remove(test_file)
        print(f"  Test file removed.")
    except OSError as e:
        print(f"  Warning: could not remove test file: {e}")

    return {
        "total_mb": round(bytes_read / 1e6, 2),
        "sha256": sha256,
        "integrity_pass": integrity_pass,
    }


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "/Volumes/Untitled"
    read_test(path)
