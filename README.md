# sdcheck

A command-line SD card health analyzer built for photographers who need to know if their card can be trusted for tomorrow's shoot — not just whether it works right now.

Most existing tools (H2testw, CrystalDiskMark, Disk Drill) give you a snapshot: is the card healthy *today*? That's useful but incomplete. A card can pass every test and still fail six months from now. **sdcheck tracks card health over time**, logging each test run and detecting degradation trends before they become data loss.

---

## The problem with existing tools

SD cards don't expose internal health data the way SSDs do. There's no SMART equivalent — no wear count, no bad block count, no remaining life percentage. So any tool that claims to "predict" SD card failure is doing what sdcheck does: inferring health from observed behavior.

The difference is that a single test can't tell you much. Speed varies run to run. What matters is whether speed is *declining over time*, whether integrity checks are *consistently passing*, and whether the card behaves the same across its full address space. sdcheck builds that picture automatically.

---

## What it tests

| Test | What it catches |
|------|----------------|
| Write speed + stability | Dying NAND cells, cache exhaustion, fake high-speed cards |
| Data integrity (SHA-256) | Corrupt writes, bit flips, controller failures |
| Capacity spot-check | Counterfeit cards, failing regions across address space |
| Longitudinal trend analysis | Gradual degradation invisible in single-run tools |

---

## Example output

```
==================================================
  sdcheck - SD Card Health Analyzer
==================================================

Selected: /Volumes/Untitled
  Reported capacity : 128.0 GB
  Filesystem        : exFAT

Write test: 512 MB in 16 MB chunks

  [####################] 100.0%   99.4 MB/s

  Done in 5.3s
  Avg: 105.4 MB/s  |  Min: 88.2 MB/s  |  Max: 115.3 MB/s  |  Stability: 93.0%

Integrity check: reading back 537 MB and verifying checksum...

  [####################] 100.0%
  Integrity: PASS

Capacity spot-check
  Reported capacity : 128.0 GB
  Free space        : 122.8 GB
  Test blocks       : 16 x 64 MB

  Writing blocks:   [####################] 16/16  ~120.3 GB  ok
  Verifying blocks: [####################] 16/16  ~120.3 GB  pass
  Blocks passed: 16/16

  ========================================
  Health Score: 100/100  [HEALTHY]
  [####################]
  ========================================
  Breakdown:
    Write stability : 30/30
    Write speed     : 25/25
    Integrity       : 25/25
    Capacity        : 20/20

  Write speed avg  : 105.4 MB/s
  Write speed min  : 88.2 MB/s
  Write stability  : 93.0%
  Integrity        : PASS
  Capacity check   : PASS

  --- Health Trend (6 runs since 2026-01-10) ---
  Speed trend      : -3.2 MB/s per month
  Integrity fails  : 0
  * Speed declining at ~3.2 MB/s per month.

  --- Run History ---
  Card: Untitled (128.0 GB)
  Date           Avg Write  Min Write  Stability   Integrity
  ----------------------------------------------------------
  2026-01-10       112.3       98.1      96.1%       PASS
  2026-02-15       110.8       95.2      95.4%       PASS
  2026-03-22       108.1       91.7      93.8%       PASS
  2026-04-30       106.5       89.4      93.1%       PASS
  2026-05-18       105.9       88.8      93.2%       PASS
  2026-06-08       105.4       88.2      93.0%       PASS

Ejecting /Volumes/Untitled ...
  Card ejected safely. You can remove it.
```

History is stored at `~/.sdcheck/history.json` and persists across runs. Cards are fingerprinted by label and reported capacity.

---

## Health score

The 0–100 score combines four categories:

| Category | Weight | Notes |
|----------|--------|-------|
| Write stability | 30 pts | Consistency of speed across the write |
| Write speed | 25 pts | Compared against card's own baseline if available |
| Integrity | 25 pts | SHA-256 checksum pass/fail; past failures count against score |
| Capacity | 20 pts | Block-level verification across full address space |

**Labels:** Healthy (80–100) / Watch (60–79) / Warning (40–59) / Critical (0–39)

---

## Setup

```bash
pip install -r requirements.txt
python main.py
```

Requires Python 3.8+. Only external dependency is `psutil`.

Insert your SD card before running. On Mac it appears under `/Volumes/`, on Windows as a drive letter, on Linux under `/media/`.

The tool auto-ejects the card safely when finished.

---

## Project structure

```
sdcheck/
├── main.py               # entry point
├── requirements.txt
└── core/
    ├── detect.py         # card detection and metadata
    ├── write_test.py     # timed write with per-chunk speed sampling
    ├── read_test.py      # integrity verification via SHA-256
    ├── capacity.py       # block-level spot-check across address space
    ├── history.py        # per-card run logging and trend analysis
    └── score.py          # weighted health score calculation
```

---

## Roadmap

- [x] Card detection (Mac / Windows / Linux)
- [x] Write speed test with stability measurement
- [x] Data integrity check (SHA-256)
- [x] Capacity spot-check
- [x] Longitudinal history tracking
- [x] Health score (0–100)
- [ ] GUI with live speed graph
- [ ] PDF report export
- [ ] Hardware version (Raspberry Pi + OLED display)

---

## Why not just use H2testw or CrystalDiskMark?

Those tools are good at answering "is this card broken right now." sdcheck is trying to answer "is this card getting worse." The distinction matters if you shoot professionally and care about catching decline before it becomes a failed shoot.

The longitudinal tracking is the part no existing consumer tool does well. A card that writes at 112 MB/s in January and 88 MB/s in June isn't broken — but it's telling you something.
