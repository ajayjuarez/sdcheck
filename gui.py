"""
gui.py
Photographer-focused GUI for sdcheck.
Run with: python3 gui.py
"""

import threading
import platform
import subprocess
import tkinter as tk
import customtkinter as ctk
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from core.detect import get_removable_drives
from core.write_test import write_test
from core.read_test import read_test
from core.capacity import capacity_test
from core.history import log_result, analyze, _load, _card_id
from core.score import calculate
from core.report import generate as generate_report

ctk.set_appearance_mode("system")
ctk.set_default_color_theme("blue")

HEALTHY  = "#639922"
WATCH    = "#d97706"
WARNING  = "#dc2626"
CRITICAL = "#7c2d12"
MUTED    = ("gray50", "gray60")
BG       = "#1e1e1e"
SURFACE  = "#2b2b2b"
TEXT     = "#e0e0e0"
GRIDCOL  = "#3a3a3a"


def chart_style(ax, fig):
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(SURFACE)
    ax.tick_params(colors=TEXT, labelsize=9)
    ax.spines[:].set_color(GRIDCOL)
    ax.yaxis.label.set_color(TEXT)
    ax.xaxis.label.set_color(TEXT)
    ax.grid(True, color=GRIDCOL, linewidth=0.5, linestyle="--", alpha=0.7)
    fig.tight_layout(pad=1.2)


def make_speed_chart(parent, samples, avg, mn, mx):
    times  = [s[0] for s in samples]
    speeds = [s[1] for s in samples]
    color  = HEALTHY if avg > 80 else (WATCH if avg > 50 else WARNING)

    fig = Figure(figsize=(4.8, 2.4), dpi=96)
    ax  = fig.add_subplot(111)
    chart_style(ax, fig)

    ax.fill_between(times, speeds, alpha=0.15, color=color)
    ax.plot(times, speeds, color=color, linewidth=1.5, zorder=3)
    ax.axhline(avg, color=TEXT,    linewidth=0.8, linestyle="--", alpha=0.6, label=f"Avg {avg} MB/s")
    ax.axhline(mn,  color=WARNING, linewidth=0.8, linestyle=":",  alpha=0.6, label=f"Min {mn} MB/s")

    ax.set_xlabel("Time (s)", fontsize=9)
    ax.set_ylabel("MB/s",     fontsize=9)
    ax.legend(fontsize=8, facecolor=SURFACE, edgecolor=GRIDCOL, labelcolor=TEXT)
    ax.set_ylim(bottom=max(0, mn - 20))

    canvas = FigureCanvasTkAgg(fig, master=parent)
    canvas.draw()
    return canvas.get_tk_widget()


def make_integrity_chart(parent, integrity, total_mb, sha256):
    fig = Figure(figsize=(4.8, 2.0), dpi=96)
    ax  = fig.add_subplot(111)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.axis("off")

    color  = HEALTHY if integrity else WARNING
    symbol = "✓" if integrity else "✗"
    label  = "PASS" if integrity else "FAIL"

    ax.text(0.5, 0.72, symbol, transform=ax.transAxes,
            fontsize=42, color=color, ha="center", va="center", fontweight="bold")
    ax.text(0.5, 0.42, label, transform=ax.transAxes,
            fontsize=16, color=color, ha="center", va="center", fontweight="bold")
    ax.text(0.5, 0.22, f"{total_mb} MB verified via SHA-256", transform=ax.transAxes,
            fontsize=9, color=TEXT, ha="center", va="center")
    ax.text(0.5, 0.08, f"Hash: {sha256[:32]}…", transform=ax.transAxes,
            fontsize=7, color="#777", ha="center", va="center", family="monospace")

    fig.tight_layout(pad=0.5)
    canvas = FigureCanvasTkAgg(fig, master=parent)
    canvas.draw()
    return canvas.get_tk_widget()


def make_trend_chart(parent, runs):
    from datetime import datetime
    import numpy as np

    dates  = [datetime.fromisoformat(r["timestamp"]) for r in runs]
    speeds = [r["avg_write_speed"] for r in runs]
    nums   = [(d - dates[0]).total_seconds() / 86400 for d in dates]

    fig = Figure(figsize=(4.8, 2.4), dpi=96)
    ax  = fig.add_subplot(111)
    chart_style(ax, fig)

    ax.scatter(nums, speeds, color=HEALTHY, s=40, zorder=4)
    ax.plot(nums, speeds, color=HEALTHY, linewidth=1.2, alpha=0.6)

    if len(nums) >= 2 and max(nums) > 0:
        z = np.polyfit(nums, speeds, 1)
        p = np.poly1d(z)
        xs = [min(nums), max(nums)]
        tc = HEALTHY if z[0] >= -0.1 else (WATCH if z[0] >= -0.27 else WARNING)
        ax.plot(xs, [p(x) for x in xs], color=tc, linewidth=1.5,
                linestyle="--", label=f"Trend {z[0]*30:+.1f} MB/s/mo")
        ax.legend(fontsize=8, facecolor=SURFACE, edgecolor=GRIDCOL, labelcolor=TEXT)

    ax.set_xlabel("Days since first test", fontsize=9)
    ax.set_ylabel("Avg write (MB/s)",      fontsize=9)

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

    canvas = FigureCanvasTkAgg(fig, master=parent)
    canvas.draw()
    return canvas.get_tk_widget()


def make_speed_icon(parent, size=28, color="#888"):
    import math
    c = tk.Canvas(parent, width=size, height=size, highlightthickness=0, bg=SURFACE)
    cx, cy, r = size//2, size//2, size//2 - 2
    c.create_arc(cx-r, cy-r, cx+r, cy+r, start=30, extent=120, style="arc", outline="#444", width=2)
    c.create_arc(cx-r, cy-r, cx+r, cy+r, start=30, extent=80,  style="arc", outline=color,  width=2)
    angle = math.radians(180 - 30 - 40)
    nx = cx + int((r-3) * math.cos(angle))
    ny = cy - int((r-3) * math.sin(angle))
    c.create_line(cx, cy, nx, ny, fill=color, width=2, capstyle="round")
    c.create_oval(cx-2, cy-2, cx+2, cy+2, fill=color, outline="")
    return c


def make_integrity_icon(parent, size=28, color="#888"):
    c = tk.Canvas(parent, width=size, height=size, highlightthickness=0, bg=SURFACE)
    cx, cy, r = size//2, size//2, size//2 - 2
    c.create_oval(cx-r, cy-r, cx+r, cy+r, outline=color, width=2)
    c.create_line(cx-r*0.35, cy, cx-r*0.05, cy+r*0.38,
                  cx+r*0.42, cy-r*0.32,
                  fill=color, width=2, joinstyle="round", capstyle="round")
    return c


def make_trend_icon(parent, size=28, color="#888"):
    c = tk.Canvas(parent, width=size, height=size, highlightthickness=0, bg=SURFACE)
    pad = 4
    c.create_line(pad, size-pad, size-pad, size-pad, fill="#444", width=1)
    c.create_line(pad, size-pad, pad, pad, fill="#444", width=1)
    pts = [pad+1, size-pad-3, pad+(size-2*pad)*0.3, size-pad-7,
           pad+(size-2*pad)*0.6, size-pad-13, size-pad-1, size-pad-20]
    c.create_line(*pts, fill=color, width=2, smooth=True, capstyle="round", joinstyle="round")
    ex, ey = pts[-2], pts[-1]
    c.create_oval(ex-2, ey-2, ex+2, ey+2, fill=color, outline="")
    return c


class SDCheckApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("sdcheck")
        self.minsize(480, 580)
        self.geometry("560x760")
        self._drive      = None
        self._running    = False
        self._last_results = {}
        self._build_ui()
        self._poll_drives()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        # Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, padx=20, pady=(20, 0), sticky="ew")
        hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hdr, text="sdcheck", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, sticky="w")
        right = ctk.CTkFrame(hdr, fg_color="transparent")
        right.grid(row=0, column=1, sticky="e")
        self._status_dot   = ctk.CTkLabel(right, text="●", font=ctk.CTkFont(size=12), text_color="gray")
        self._status_dot.pack(side="left", padx=(0,4))
        self._status_label = ctk.CTkLabel(right, text="No card", text_color=MUTED, font=ctk.CTkFont(size=12))
        self._status_label.pack(side="left")

        # Card info
        cf = ctk.CTkFrame(self)
        cf.grid(row=1, column=0, padx=20, pady=12, sticky="ew")
        cf.grid_columnconfigure(0, weight=1)
        self._card_name = ctk.CTkLabel(cf, text="—", font=ctk.CTkFont(size=16, weight="bold"))
        self._card_name.grid(row=0, column=0, padx=16, pady=(12,2), sticky="w")
        self._card_meta = ctk.CTkLabel(cf, text="Insert a card to begin", text_color=MUTED, font=ctk.CTkFont(size=12))
        self._card_meta.grid(row=1, column=0, padx=16, pady=(0,12), sticky="w")

        # Score
        sf = ctk.CTkFrame(self)
        sf.grid(row=2, column=0, padx=20, pady=(0,12), sticky="ew")
        sf.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(sf, text="Can I trust this card for my next shoot?",
                     text_color=MUTED, font=ctk.CTkFont(size=12)).grid(row=0, column=0, pady=(14,4))
        self._score_label = ctk.CTkLabel(sf, text="—", font=ctk.CTkFont(size=48, weight="bold"))
        self._score_label.grid(row=1, column=0)
        ctk.CTkLabel(sf, text="out of 100", text_color=MUTED, font=ctk.CTkFont(size=12)).grid(row=2, column=0)
        self._progress = ctk.CTkProgressBar(sf, height=6, corner_radius=3)
        self._progress.set(0)
        self._progress.grid(row=3, column=0, padx=32, pady=(8,4), sticky="ew")
        self._score_badge = ctk.CTkLabel(sf, text="", font=ctk.CTkFont(size=12, weight="bold"))
        self._score_badge.grid(row=4, column=0, pady=(0,14))

        # Stats container
        self._stats_container = ctk.CTkFrame(self, fg_color="transparent")
        self._stats_container.grid(row=3, column=0, padx=20, pady=(0,12), sticky="ew")
        self._stats_container.grid_columnconfigure((0,1,2), weight=1)
        self._stat_widgets = {}
        self._build_stat_cards()

        # Log
        lf = ctk.CTkFrame(self)
        lf.grid(row=4, column=0, padx=20, pady=(0,8), sticky="nsew")
        lf.grid_columnconfigure(0, weight=1)
        lf.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(lf, text="Test log", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=0, column=0, padx=14, pady=(10,4), sticky="w")
        self._log_box = ctk.CTkTextbox(lf, font=ctk.CTkFont(family="Courier", size=11),
                                        state="disabled", wrap="word")
        self._log_box.grid(row=1, column=0, padx=10, pady=(0,10), sticky="nsew")

        # Op bar
        self._op_label = ctk.CTkLabel(self, text="", text_color=MUTED, font=ctk.CTkFont(size=11))
        self._op_label.grid(row=5, column=0, padx=20, pady=(0,2), sticky="w")
        self._op_bar = ctk.CTkProgressBar(self, height=4, corner_radius=2)
        self._op_bar.set(0)
        self._op_bar.grid(row=6, column=0, padx=20, pady=(0,8), sticky="ew")

        # Buttons row
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.grid(row=7, column=0, padx=20, pady=(0,20), sticky="ew")
        btn_row.grid_columnconfigure(0, weight=1)

        self._run_btn = ctk.CTkButton(btn_row, text="Run test", height=42,
                                       font=ctk.CTkFont(size=14, weight="bold"),
                                       command=self._start_test, state="disabled")
        self._run_btn.grid(row=0, column=0, sticky="ew")

        self._export_btn = ctk.CTkButton(btn_row, text="Export PDF", height=32,
                                          font=ctk.CTkFont(size=12),
                                          fg_color="transparent",
                                          border_width=1,
                                          command=self._export_pdf, state="disabled")
        self._export_btn.grid(row=1, column=0, pady=(6,0), sticky="ew")

    def _build_stat_cards(self):
        for w in self._stats_container.winfo_children():
            w.destroy()
        self._stat_widgets = {}
        for i, (key, label, icon_fn) in enumerate([
            ("speed",     "Write speed", make_speed_icon),
            ("integrity", "Integrity",   make_integrity_icon),
            ("trend",     "Trend",       make_trend_icon),
        ]):
            f = ctk.CTkFrame(self._stats_container)
            f.grid(row=0, column=i, padx=4, sticky="ew")
            f.grid_columnconfigure(0, weight=1)

            ifrm = ctk.CTkFrame(f, fg_color="transparent")
            ifrm.grid(row=0, column=0, pady=(12,2))
            icon = icon_fn(ifrm, size=28, color="#888")
            icon.pack()

            lbl  = ctk.CTkLabel(f, text=label, text_color=MUTED, font=ctk.CTkFont(size=11))
            lbl.grid(row=1, column=0)
            val  = ctk.CTkLabel(f, text="—", font=ctk.CTkFont(size=15, weight="bold"))
            val.grid(row=2, column=0, pady=(2,4))
            hint = ctk.CTkLabel(f, text="", text_color=MUTED, font=ctk.CTkFont(size=9))
            hint.grid(row=3, column=0, pady=(0,10))

            self._stat_widgets[key] = {
                "frame": f, "icon_frame": ifrm, "icon_fn": icon_fn,
                "val": val, "hint": hint, "_detail_fn": None
            }
            for w in [f, ifrm, icon, lbl, val, hint]:
                try:
                    w.bind("<Button-1>", lambda e, k=key: self._show_detail(k))
                    w.configure(cursor="hand2")
                except Exception:
                    pass

    def _update_stat(self, key, text, color, detail_fn=None):
        w = self._stat_widgets.get(key)
        if not w:
            return
        w["val"].configure(text=text, text_color=color)
        w["hint"].configure(text="tap for details" if detail_fn else "")
        w["_detail_fn"] = detail_fn
        for child in w["icon_frame"].winfo_children():
            child.destroy()
        icon = w["icon_fn"](w["icon_frame"], size=28, color=color)
        icon.pack()
        try:
            icon.bind("<Button-1>", lambda e, k=key: self._show_detail(k))
            icon.configure(cursor="hand2")
        except Exception:
            pass

    def _reset_stat(self, key):
        w = self._stat_widgets.get(key)
        if not w:
            return
        w["val"].configure(text="—", text_color=("gray50","gray60"))
        w["hint"].configure(text="")
        w["_detail_fn"] = None
        for child in w["icon_frame"].winfo_children():
            child.destroy()
        icon = w["icon_fn"](w["icon_frame"], size=28, color="#888")
        icon.pack()

    def _show_detail(self, key):
        w = self._stat_widgets.get(key, {})
        fn = w.get("_detail_fn")
        if not fn:
            return

        for widget in self._stats_container.winfo_children():
            widget.grid_forget()

        panel = ctk.CTkFrame(self._stats_container)
        panel.grid(row=0, column=0, columnspan=3, sticky="ew")
        panel.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(panel, fg_color="transparent")
        top.grid(row=0, column=0, padx=12, pady=(10,4), sticky="ew")
        top.grid_columnconfigure(1, weight=1)
        def _back():
            self.focus_force()
            self._hide_detail()
        ctk.CTkButton(top, text="← Back", width=70, height=26,
                      font=ctk.CTkFont(size=12),
                      command=_back).grid(row=0, column=0, sticky="w")
        title = {"speed": "Write speed", "integrity": "Integrity", "trend": "Trend"}.get(key, key)
        ctk.CTkLabel(top, text=title, font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=0, column=1, padx=12, sticky="w")

        chart_widget = fn(panel)
        chart_widget.grid(row=1, column=0, padx=10, pady=(0,10), sticky="ew")

    def _hide_detail(self):
        for w in self._stats_container.winfo_children():
            w.destroy()
        self._build_stat_cards()
        if self._last_results:
            self._apply_results(self._last_results)

    def _log(self, msg):
        self._log_box.configure(state="normal")
        self._log_box.insert("end", msg + "\n")
        self._log_box.see("end")
        self._log_box.configure(state="disabled")

    def _clear_log(self):
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.configure(state="disabled")

    def _export_pdf(self):
        self._log("Export PDF clicked...")
        if not self._last_results:
            self._log("No results yet — run a test first.")
            return
        drive = self._drive or getattr(self, "_ejected_drive", None)
        if not drive:
            self._log("No drive info.")
            return
        r = self._last_results
        try:
            self._log("Generating PDF...")
            path = generate_report(
                drive,
                r["write_result"], r["read_result"], r["integrity"],
                r["cap_result"], r["score_result"], r["trend"],
                r.get("history_runs", [])
            )
            import subprocess, platform
            self._log(f"PDF saved: {path}")
            if platform.system() == "Darwin":
                subprocess.run(["open", path])
        except Exception as e:
            import traceback
            self._log(f"PDF export failed: {e}")
            self._log(traceback.format_exc())

    def _poll_drives(self):
        if not self._running:
            drives = get_removable_drives()
            if drives:
                self._drive = drives[0]
                name = self._drive["path"].split("/")[-1] or self._drive["path"]
                self._card_name.configure(text=name)
                self._card_meta.configure(
                    text=f"{self._drive['total_gb']} GB  ·  {self._drive['fstype']}  ·  {self._drive['free_gb']} GB free")
                self._status_dot.configure(text_color=HEALTHY)
                self._status_label.configure(text="Card detected")
                self._run_btn.configure(state="normal")
            else:
                self._drive = None
                self._card_name.configure(text="—")
                self._card_meta.configure(text="Insert a card to begin")
                self._status_dot.configure(text_color="gray")
                self._status_label.configure(text="No card")
                self._run_btn.configure(state="disabled")
        self.after(2000, self._poll_drives)

    def _start_test(self):
        self.focus_force()
        if not self._drive or self._running:
            return
        self._running = True
        self._run_btn.configure(state="disabled", text="Testing…")
        self._clear_log()
        self._score_label.configure(text="—", text_color=("gray70","gray40"))
        self._score_badge.configure(text="")
        self._progress.set(0)
        self._last_results = {}
        self._build_stat_cards()
        self.update_idletasks()
        threading.Thread(target=self._run_tests, daemon=True).start()

    def _run_tests(self):
        drive = self._drive
        self._ui_log("Starting test...")
        self._ui_op("Write test", 0)
        test_size_mb = min(512, int(drive["free_gb"] * 1024 * 0.8))

        def write_cb(elapsed, speed, pct):
            self._ui_op(f"Write test  {speed:.0f} MB/s", pct / 100)

        write_result = write_test(drive["path"], file_size_mb=test_size_mb, callback=write_cb)
        if not write_result:
            self._ui_log("Write test failed.")
            self.after(0, lambda: self._run_btn.configure(state="normal", text="Run test"))
            self._running = False
            return

        self._ui_log(f"Write: avg {write_result['avg_speed']} MB/s  "
                     f"min {write_result['min_speed']} MB/s  "
                     f"stability {write_result['stability']}%")
        self._ui_op("Integrity check", 0)

        def read_cb(pct):
            self._ui_op("Integrity check", pct / 100)

        read_result = read_test(drive["path"], expected_sha256=write_result["sha256"], callback=read_cb)
        if not read_result:
            self._ui_log("Integrity check failed.")
            self.after(0, lambda: self._run_btn.configure(state="normal", text="Run test"))
            self._running = False
            return

        integrity = read_result["integrity_pass"]
        self._ui_log(f"Integrity: {'PASS' if integrity else 'FAIL'}")
        self._ui_op("Capacity check", 0)

        def cap_cb(pct, gb, status):
            self._ui_op(f"Capacity  ~{gb:.0f} GB", pct / 100)

        cap_result = capacity_test(drive, callback=cap_cb)
        if cap_result:
            self._ui_log(f"Capacity: {cap_result['blocks_passed']}/{cap_result['blocks_total']} blocks passed")

        log_result(drive, write_result, integrity, cap_result)
        history_data = _load()
        card_id      = _card_id(drive)
        history_runs = history_data.get(card_id, {}).get("runs", [])
        score_result = calculate(write_result, integrity, cap_result, history_runs)
        trend        = analyze(drive)

        self._ui_log(f"Health score: {score_result['score']}/100  [{score_result['label']}]")

        results = {
            "score_result":  score_result,
            "write_result":  write_result,
            "read_result":   read_result,
            "integrity":     integrity,
            "cap_result":    cap_result,
            "trend":         trend,
            "history_runs":  history_runs,
        }
        self._last_results = results
        self.after(0, lambda: self._finish(results))

    def _ui_log(self, msg):
        self.after(0, self._log, msg)

    def _ui_op(self, label, pct):
        self.after(0, lambda: self._op_label.configure(text=label))
        self.after(0, lambda: self._op_bar.set(pct))

    def _apply_results(self, r):
        score_result  = r["score_result"]
        write_result  = r["write_result"]
        read_result   = r["read_result"]
        integrity     = r["integrity"]
        trend         = r["trend"]
        history_runs  = r.get("history_runs", [])

        score = score_result["score"]
        label = score_result["label"]
        color = {"Healthy": HEALTHY, "Watch": WATCH,
                 "Warning": WARNING, "Critical": CRITICAL}.get(label, "gray")

        self._score_label.configure(text=str(score), text_color=color)
        self._progress.set(score / 100)
        self._score_badge.configure(text=label.upper(), text_color=color)

        # Speed card
        def speed_chart(parent):
            return make_speed_chart(parent,
                write_result["samples"], write_result["avg_speed"],
                write_result["min_speed"], write_result["max_speed"])

        self._update_stat("speed", f"{write_result['avg_speed']} MB/s", color, speed_chart)

        # Integrity card
        def integ_chart(parent):
            return make_integrity_chart(parent, integrity,
                read_result["total_mb"], read_result["sha256"])

        ic = HEALTHY if integrity else WARNING
        self._update_stat("integrity", "Pass" if integrity else "Fail", ic, integ_chart)

        # Trend card
        if trend:
            t     = trend["avg_speed_trend"]
            ttext = f"{t:+.1f} MB/s/mo" if abs(t) > 0.1 else "Stable"
            tc    = HEALTHY if t >= -3 else (WATCH if t >= -8 else WARNING)

            def trend_chart(parent, runs=history_runs):
                return make_trend_chart(parent, runs)

            self._update_stat("trend", ttext, tc, trend_chart)
        else:
            self._update_stat("trend", "Need more runs", "gray")

    def _finish(self, results):
        self._running = False
        self._run_btn.configure(state="normal", text="Run test")
        self._export_btn.configure(state="normal")
        self._op_label.configure(text="")
        self._op_bar.set(1)
        self._apply_results(results)
        try:
            if platform.system() == "Darwin":
                subprocess.run(["diskutil", "eject", self._drive["path"]], capture_output=True)
                self._log("Card ejected safely.")
        except Exception:
            pass
        self._ejected_drive = self._drive


if __name__ == "__main__":
    app = SDCheckApp()
    app.mainloop()
