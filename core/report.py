"""
report.py
Generates a comprehensive PDF report of all test results and card history.
"""

import os
import io
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                 TableStyle, HRFlowable, Image, KeepTogether)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

# Color palette
GREEN  = colors.HexColor("#639922")
AMBER  = colors.HexColor("#d97706")
RED    = colors.HexColor("#dc2626")
DARK   = colors.HexColor("#1a1a1a")
GRAY   = colors.HexColor("#6b7280")
LGRAY  = colors.HexColor("#f3f4f6")
WHITE  = colors.white
BLACK  = colors.black

VERSION = "1.0"


def _score_color(score):
    if score >= 80: return GREEN
    if score >= 60: return AMBER
    if score >= 40: return RED
    return colors.HexColor("#7c2d12")


def _make_speed_chart(samples, avg, mn, mx, width=5.5*inch, height=2.0*inch):
    """Renders a speed chart and returns it as a reportlab Image."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    times  = [s[0] for s in samples]
    speeds = [s[1] for s in samples]
    color  = "#639922" if avg > 80 else ("#d97706" if avg > 50 else "#dc2626")

    fig, ax = plt.subplots(figsize=(width/inch, height/inch), dpi=120)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("#f9fafb")

    ax.fill_between(times, speeds, alpha=0.12, color=color)
    ax.plot(times, speeds, color=color, linewidth=1.5, zorder=3)
    ax.axhline(avg, color="#374151", linewidth=0.8, linestyle="--",
               alpha=0.7, label=f"Avg {avg} MB/s")
    ax.axhline(mn,  color="#dc2626", linewidth=0.8, linestyle=":",
               alpha=0.7, label=f"Min {mn} MB/s")

    ax.set_xlabel("Time (s)", fontsize=8)
    ax.set_ylabel("MB/s",     fontsize=8)
    ax.tick_params(labelsize=7)
    ax.legend(fontsize=7, framealpha=0.8)
    ax.set_ylim(bottom=max(0, mn - 15))
    ax.grid(True, color="#e5e7eb", linewidth=0.5, linestyle="--", alpha=0.8)
    ax.spines[["top","right"]].set_visible(False)
    fig.tight_layout(pad=0.8)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return Image(buf, width=width, height=height)


def _make_trend_chart(runs, width=5.5*inch, height=2.0*inch):
    """Renders the historical trend chart."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    dates  = [datetime.fromisoformat(r["timestamp"]) for r in runs]
    speeds = [r["avg_write_speed"] for r in runs]
    nums   = [(d - dates[0]).total_seconds() / 86400 for d in dates]

    fig, ax = plt.subplots(figsize=(width/inch, height/inch), dpi=120)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("#f9fafb")

    ax.scatter(nums, speeds, color="#639922", s=40, zorder=4)
    ax.plot(nums, speeds, color="#639922", linewidth=1.2, alpha=0.5)

    if len(nums) >= 2 and max(nums) > 0:
        z  = np.polyfit(nums, speeds, 1)
        p  = np.poly1d(z)
        xs = [min(nums), max(nums)]
        tc = "#639922" if z[0] >= -0.1 else ("#d97706" if z[0] >= -0.27 else "#dc2626")
        ax.plot(xs, [p(x) for x in xs], color=tc, linewidth=1.5,
                linestyle="--", label=f"Trend {z[0]*30:+.1f} MB/s/mo")
        ax.legend(fontsize=7, framealpha=0.8)

    # Deduplicate date labels when runs are close together
    date_labels = [d.strftime("%b %d") for d in dates]
    seen = set()
    deduped = []
    for lbl in date_labels:
        if lbl in seen:
            deduped.append("")
        else:
            seen.add(lbl)
            deduped.append(lbl)
    ax.set_xticks(nums)
    ax.set_xticklabels(deduped, rotation=45, ha="right", fontsize=7)
    ax.set_xlabel("Date", fontsize=8)
    ax.set_ylabel("Avg write (MB/s)", fontsize=8)
    ax.tick_params(labelsize=7)
    ax.grid(True, color="#e5e7eb", linewidth=0.5, linestyle="--", alpha=0.8)
    ax.spines[["top","right"]].set_visible(False)
    fig.tight_layout(pad=0.8)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return Image(buf, width=width, height=height)


def generate(drive, write_result, read_result, integrity, cap_result,
             score_result, trend, history_runs, output_path=None):
    """
    Generates the full PDF report.

    Returns the output path.
    """
    if output_path is None:
        card_label = drive["path"].split("/")[-1] or "card"
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.expanduser(f"~/Desktop/sdcheck_{card_label}_{ts}.pdf")

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=0.75*inch, rightMargin=0.75*inch,
        topMargin=0.75*inch,  bottomMargin=0.75*inch,
    )

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", fontSize=20, leading=24, textColor=DARK,
                         fontName="Helvetica-Bold", spaceAfter=4)
    h2 = ParagraphStyle("h2", fontSize=13, leading=16, textColor=DARK,
                         fontName="Helvetica-Bold", spaceBefore=14, spaceAfter=6)
    h3 = ParagraphStyle("h3", fontSize=10, leading=13, textColor=GRAY,
                         fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=4)
    body = ParagraphStyle("body", fontSize=9, leading=13, textColor=DARK,
                           fontName="Helvetica", spaceAfter=4)
    mono = ParagraphStyle("mono", fontSize=8, leading=11, textColor=DARK,
                           fontName="Courier", spaceAfter=2)
    caption = ParagraphStyle("caption", fontSize=8, leading=11, textColor=GRAY,
                              fontName="Helvetica", spaceAfter=4, alignment=TA_CENTER)

    story = []

    # ── Header ──────────────────────────────────────────────────────────────
    story.append(Paragraph("sdcheck", h1))
    story.append(Paragraph(
        f"SD Card Health Report  ·  {datetime.now().strftime('%B %d, %Y at %I:%M %p')}  ·  v{VERSION}",
        ParagraphStyle("sub", fontSize=9, textColor=GRAY, fontName="Helvetica", spaceAfter=8)
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=LGRAY, spaceAfter=14))

    # ── Card info ───────────────────────────────────────────────────────────
    story.append(Paragraph("Card", h2))
    card_label = drive["path"].split("/")[-1] or drive["path"]
    card_data = [
        ["Label",      card_label],
        ["Capacity",   f"{drive['total_gb']} GB (reported)"],
        ["Used",       f"{drive['used_gb']} GB"],
        ["Free",       f"{drive['free_gb']} GB"],
        ["Filesystem", drive["fstype"]],
        ["Mount path", drive["path"]],
    ]
    card_table = Table(card_data, colWidths=[1.4*inch, 4.5*inch])
    card_table.setStyle(TableStyle([
        ("FONTNAME",  (0,0), (-1,-1), "Helvetica"),
        ("FONTSIZE",  (0,0), (-1,-1), 9),
        ("FONTNAME",  (0,0), (0,-1),  "Helvetica-Bold"),
        ("TEXTCOLOR", (0,0), (0,-1),  GRAY),
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [WHITE, LGRAY]),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LEFTPADDING",   (0,0), (-1,-1), 8),
    ]))
    story.append(card_table)

    # ── Health score ─────────────────────────────────────────────────────────
    story.append(Paragraph("Health Score", h2))
    score = score_result["score"]
    label = score_result["label"]
    sc    = _score_color(score)
    bd    = score_result["breakdown"]

    story.append(Paragraph(
        f'<font size="26" color="{sc.hexval()}"><b>{score}/100</b></font>'
        f'&nbsp;&nbsp;&nbsp;<font size="14" color="{sc.hexval()}"><b>{label.upper()}</b></font>',
        ParagraphStyle("score_line", fontSize=26, leading=32, spaceBefore=4, spaceAfter=8,
                       leftIndent=12)
    ))

    breakdown_data = [
        ["Category",       "Points", "Max"],
        ["Write stability", str(bd.get("write_stability", 0)), "30"],
        ["Write speed",     str(bd.get("write_speed",     0)), "25"],
        ["Integrity",       str(bd.get("integrity",       0)), "25"],
        ["Capacity",        str(bd.get("capacity",        0)), "20"],
        ["Total",           str(score), "100"],
    ]
    bt = Table(breakdown_data, colWidths=[3*inch, 1.2*inch, 1.2*inch])
    bt.setStyle(TableStyle([
        ("FONTNAME",    (0,0), (-1,0),  "Helvetica-Bold"),
        ("FONTNAME",    (0,1), (-1,-1), "Helvetica"),
        ("FONTSIZE",    (0,0), (-1,-1), 9),
        ("BACKGROUND",  (0,0), (-1,0),  DARK),
        ("TEXTCOLOR",   (0,0), (-1,0),  WHITE),
        ("ROWBACKGROUNDS", (0,1), (-1,-2), [WHITE, LGRAY]),
        ("BACKGROUND",  (0,-1), (-1,-1), LGRAY),
        ("FONTNAME",    (0,-1), (-1,-1), "Helvetica-Bold"),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING",   (0,0), (-1,-1), 8),
        ("ALIGN",       (1,0), (-1,-1), "CENTER"),
    ]))
    story.append(bt)

    if score_result.get("flags"):
        story.append(Spacer(1, 6))
        story.append(Paragraph("Issues flagged:", h3))
        for flag in score_result["flags"]:
            story.append(Paragraph(f"• {flag}", body))

    # ── Write speed ──────────────────────────────────────────────────────────
    story.append(Paragraph("Write Speed", h2))
    ws_data = [
        ["Average",   f"{write_result['avg_speed']} MB/s"],
        ["Minimum",   f"{write_result['min_speed']} MB/s"],
        ["Maximum",   f"{write_result['max_speed']} MB/s"],
        ["Stability", f"{write_result['stability']}%"],
        ["Data written", f"{write_result['total_mb']} MB"],
        ["Duration",  f"{write_result['duration_s']}s"],
    ]
    wt = Table(ws_data, colWidths=[1.4*inch, 4.5*inch])
    wt.setStyle(TableStyle([
        ("FONTNAME",  (0,0), (-1,-1), "Helvetica"),
        ("FONTNAME",  (0,0), (0,-1),  "Helvetica-Bold"),
        ("FONTSIZE",  (0,0), (-1,-1), 9),
        ("TEXTCOLOR", (0,0), (0,-1),  GRAY),
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [WHITE, LGRAY]),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LEFTPADDING",   (0,0), (-1,-1), 8),
    ]))
    story.append(wt)
    story.append(Spacer(1, 8))

    if write_result.get("samples"):
        chart = _make_speed_chart(
            write_result["samples"],
            write_result["avg_speed"],
            write_result["min_speed"],
            write_result["max_speed"],
        )
        story.append(chart)
        story.append(Paragraph("Write speed over time (MB/s)", caption))

    # ── Integrity ────────────────────────────────────────────────────────────
    story.append(Paragraph("Data Integrity", h2))
    ic    = GREEN if integrity else RED
    ilbl  = "PASS" if integrity else "FAIL"
    integ_data = [
        ["Result",       f"{ilbl}"],
        ["Method",       "SHA-256 checksum"],
        ["Data checked", f"{read_result['total_mb']} MB"],
        ["SHA-256",      read_result["sha256"][:32] + "…"],
    ]
    it = Table(integ_data, colWidths=[1.4*inch, 4.5*inch])
    it.setStyle(TableStyle([
        ("FONTNAME",    (0,0), (-1,-1), "Helvetica"),
        ("FONTNAME",    (0,0), (0,-1),  "Helvetica-Bold"),
        ("FONTSIZE",    (0,0), (-1,-1), 9),
        ("TEXTCOLOR",   (0,0), (0,-1),  GRAY),
        ("TEXTCOLOR",   (1,0), (1,0),   ic),
        ("FONTNAME",    (1,0), (1,0),   "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [WHITE, LGRAY]),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LEFTPADDING",   (0,0), (-1,-1), 8),
    ]))
    story.append(it)

    # ── Capacity ─────────────────────────────────────────────────────────────
    if cap_result:
        story.append(Paragraph("Capacity Check", h2))
        cap_status = "PASS" if cap_result["pass"] else "FAIL"
        cc = GREEN if cap_result["pass"] else RED
        cap_data = [
            ["Result",         cap_status],
            ["Reported",       f"{cap_result['reported_gb']} GB"],
            ["Tested",         f"{cap_result['tested_gb']} GB sampled"],
            ["Blocks passed",  f"{cap_result['blocks_passed']}/{cap_result['blocks_total']}"],
            ["Blocks failed",  str(cap_result["blocks_failed"])],
        ]
        if cap_result["failed_regions"]:
            cap_data.append(["Failed at",
                             ", ".join(f"~{g} GB" for g in cap_result["failed_regions"])])
        ct = Table(cap_data, colWidths=[1.4*inch, 4.5*inch])
        ct.setStyle(TableStyle([
            ("FONTNAME",    (0,0), (-1,-1), "Helvetica"),
            ("FONTNAME",    (0,0), (0,-1),  "Helvetica-Bold"),
            ("FONTSIZE",    (0,0), (-1,-1), 9),
            ("TEXTCOLOR",   (0,0), (0,-1),  GRAY),
            ("TEXTCOLOR",   (1,0), (1,0),   cc),
            ("FONTNAME",    (1,0), (1,0),   "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0,0), (-1,-1), [WHITE, LGRAY]),
            ("TOPPADDING",    (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("LEFTPADDING",   (0,0), (-1,-1), 8),
        ]))
        story.append(ct)

    # ── Trend ────────────────────────────────────────────────────────────────
    if trend:
        story.append(Paragraph("Health Trend", h2))
        t = trend["avg_speed_trend"]
        trend_data = [
            ["Runs logged",      str(trend["run_count"])],
            ["Since",            trend["first_seen"]],
            ["Speed trend",      f"{t:+.1f} MB/s per month"],
            ["Assessment",       trend["health_assessment"]],
            ["Integrity fails",  str(trend["integrity_failures"])],
        ]
        trt = Table(trend_data, colWidths=[1.4*inch, 4.5*inch])
        trt.setStyle(TableStyle([
            ("FONTNAME",  (0,0), (-1,-1), "Helvetica"),
            ("FONTNAME",  (0,0), (0,-1),  "Helvetica-Bold"),
            ("FONTSIZE",  (0,0), (-1,-1), 9),
            ("TEXTCOLOR", (0,0), (0,-1),  GRAY),
            ("ROWBACKGROUNDS", (0,0), (-1,-1), [WHITE, LGRAY]),
            ("TOPPADDING",    (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("LEFTPADDING",   (0,0), (-1,-1), 8),
        ]))
        story.append(trt)

        if trend["notes"]:
            story.append(Spacer(1, 4))
            for note in trend["notes"]:
                story.append(Paragraph(f"• {note}", body))

        if len(history_runs) >= 2:
            story.append(Spacer(1, 8))
            tchart = _make_trend_chart(history_runs)
            story.append(tchart)
            story.append(Paragraph("Write speed trend across all runs", caption))

    # ── Run history ──────────────────────────────────────────────────────────
    if history_runs:
        story.append(Paragraph("Full Run History", h2))
        hist_data = [["Date", "Avg Write", "Min Write", "Stability", "Integrity"]]
        for r in history_runs:
            hist_data.append([
                r["timestamp"][:10],
                f"{r['avg_write_speed']:.1f} MB/s",
                f"{r['min_write_speed']:.1f} MB/s",
                f"{r['stability']:.1f}%",
                "PASS" if r["integrity_pass"] else "FAIL",
            ])
        ht = Table(hist_data, colWidths=[1.1*inch, 1.3*inch, 1.3*inch, 1.1*inch, 1.0*inch])
        row_colors = []
        for i, r in enumerate(history_runs, 1):
            if not r["integrity_pass"]:
                row_colors.append(("BACKGROUND", (0,i), (-1,i), colors.HexColor("#fee2e2")))
        ht.setStyle(TableStyle([
            ("FONTNAME",    (0,0), (-1,0),  "Helvetica-Bold"),
            ("FONTNAME",    (0,1), (-1,-1), "Helvetica"),
            ("FONTSIZE",    (0,0), (-1,-1), 8),
            ("BACKGROUND",  (0,0), (-1,0),  DARK),
            ("TEXTCOLOR",   (0,0), (-1,0),  WHITE),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [WHITE, LGRAY]),
            ("ALIGN",       (1,0), (-1,-1), "CENTER"),
            ("TOPPADDING",    (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("LEFTPADDING",   (0,0), (-1,-1), 6),
        ] + row_colors))
        story.append(ht)

    # ── Footer ───────────────────────────────────────────────────────────────
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.5, color=LGRAY))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"Generated by sdcheck v{VERSION}  ·  github.com/ajayjuarez/sdcheck",
        ParagraphStyle("footer", fontSize=7, textColor=GRAY,
                       fontName="Helvetica", alignment=TA_CENTER)
    ))

    doc.build(story)
    return output_path
