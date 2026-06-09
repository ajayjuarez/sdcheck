"""
detect.py
Finds mounted SD cards and pulls basic metadata.
"""

import os
import platform
import psutil


def get_removable_drives():
    """
    Returns a list of dicts for each mounted removable drive.
    Each dict has: path, device, fstype, total_gb, used_gb, free_gb
    """
    drives = []
    partitions = psutil.disk_partitions(all=False)

    for p in partitions:
        # Skip optical drives and virtual filesystems
        if not p.mountpoint:
            continue
        if p.fstype in ("", "devfs", "autofs", "squashfs", "hfs"):
            continue

        # Platform-specific removable detection
        if platform.system() == "Darwin":
            # On Mac, removable cards show up under /Volumes but not as the main disk
            if not p.mountpoint.startswith("/Volumes/"):
                continue
        elif platform.system() == "Windows":
            if "removable" not in p.opts:
                continue
        elif platform.system() == "Linux":
            # On Linux, SD cards are usually /dev/mmcblkX or mounted under /media
            is_mmc = "mmcblk" in p.device
            is_media = p.mountpoint.startswith("/media") or p.mountpoint.startswith("/run/media")
            if not (is_mmc or is_media):
                continue

        try:
            usage = psutil.disk_usage(p.mountpoint)
        except PermissionError:
            continue

        drives.append({
            "path": p.mountpoint,
            "device": p.device,
            "fstype": p.fstype,
            "total_gb": round(usage.total / 1e9, 2),
            "used_gb": round(usage.used / 1e9, 2),
            "free_gb": round(usage.free / 1e9, 2),
        })

    return drives


def pick_drive(drives):
    """
    If multiple drives found, prompt user to pick one.
    Returns the selected drive dict.
    """
    if not drives:
        return None
    if len(drives) == 1:
        return drives[0]

    print("\nMultiple removable drives found:")
    for i, d in enumerate(drives):
        print(f"  [{i}] {d['path']}  ({d['total_gb']} GB, {d['fstype']})")
    while True:
        try:
            choice = int(input("Select drive number: "))
            if 0 <= choice < len(drives):
                return drives[choice]
        except ValueError:
            pass
        print("Invalid choice, try again.")


def detect():
    """
    Main entry point. Returns the selected drive dict or None.
    """
    drives = get_removable_drives()
    if not drives:
        print("No removable drives detected.")
        return None

    drive = pick_drive(drives)
    print(f"\nSelected: {drive['path']}")
    print(f"  Reported capacity : {drive['total_gb']} GB")
    print(f"  Used              : {drive['used_gb']} GB")
    print(f"  Free              : {drive['free_gb']} GB")
    print(f"  Filesystem        : {drive['fstype']}")
    return drive


if __name__ == "__main__":
    detect()
