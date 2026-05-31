from __future__ import annotations

import threading
import tkinter as tk
from datetime import datetime
from tkinter import ttk

from codex_usage import get_last_error, read_codex_rate_limits


REFRESH_MS = 60_000


class SpiritDesktopPet:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Codex 灵兽")
        self.root.geometry("280x180+80+80")
        self.root.attributes("-topmost", True)
        self.root.resizable(False, False)
        self.root.configure(bg="#f8f6ef")

        self.drag_start: tuple[int, int] | None = None
        self._build_ui()
        self._bind_drag()
        self.refresh()

    def _build_ui(self) -> None:
        self.card = tk.Frame(self.root, bg="#fffaf0", highlightbackground="#203d3a", highlightthickness=2)
        self.card.pack(fill="both", expand=True, padx=10, pady=10)

        header = tk.Frame(self.card, bg="#fffaf0")
        header.pack(fill="x", padx=12, pady=(10, 6))

        self.title = tk.Label(
            header,
            text="饕餮灵脉",
            bg="#fffaf0",
            fg="#203d3a",
            font=("Microsoft YaHei UI", 15, "bold"),
        )
        self.title.pack(side="left")

        refresh_button = tk.Button(
            header,
            text="↻",
            command=self.refresh,
            bg="#ffffff",
            fg="#203d3a",
            relief="flat",
            width=3,
            cursor="hand2",
        )
        refresh_button.pack(side="right")

        self.plan = tk.Label(
            self.card,
            text="读取中...",
            bg="#fffaf0",
            fg="#65707f",
            font=("Microsoft YaHei UI", 9),
        )
        self.plan.pack(anchor="w", padx=12)

        self.short = self._meter("短期灵脉")
        self.week = self._meter("长期灵脉")

        self.status = tk.Label(
            self.card,
            text="正在同步 Codex 用量",
            bg="#fffaf0",
            fg="#65707f",
            font=("Microsoft YaHei UI", 9),
            wraplength=238,
            justify="left",
        )
        self.status.pack(fill="x", padx=12, pady=(6, 10))

    def _meter(self, label: str) -> dict[str, tk.Widget]:
        frame = tk.Frame(self.card, bg="#fffaf0")
        frame.pack(fill="x", padx=12, pady=(8, 0))

        top = tk.Frame(frame, bg="#fffaf0")
        top.pack(fill="x")
        name = tk.Label(top, text=label, bg="#fffaf0", fg="#203d3a", font=("Microsoft YaHei UI", 10, "bold"))
        name.pack(side="left")
        value = tk.Label(top, text="--%", bg="#fffaf0", fg="#203d3a", font=("Microsoft YaHei UI", 10, "bold"))
        value.pack(side="right")

        bar = ttk.Progressbar(frame, maximum=100, mode="determinate")
        bar.pack(fill="x", pady=(4, 0))
        return {"value": value, "bar": bar}

    def _bind_drag(self) -> None:
        for widget in (self.root, self.card, self.title, self.plan, self.status):
            widget.bind("<ButtonPress-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._drag)

    def _start_drag(self, event: tk.Event) -> None:
        self.drag_start = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def _drag(self, event: tk.Event) -> None:
        if not self.drag_start:
            return
        offset_x, offset_y = self.drag_start
        self.root.geometry(f"+{event.x_root - offset_x}+{event.y_root - offset_y}")

    def refresh(self) -> None:
        self.status.config(text="正在同步 Codex 用量...")
        threading.Thread(target=self._load_usage, daemon=True).start()

    def _load_usage(self) -> None:
        snapshot = read_codex_rate_limits()
        self.root.after(0, lambda: self._render_snapshot(snapshot))

    def _render_snapshot(self, snapshot: dict | None) -> None:
        if not snapshot:
            self.plan.config(text="Demo / 未连接")
            self._set_meter(self.short, 0)
            self._set_meter(self.week, 0)
            self.status.config(text=f"读取失败：{get_last_error()}")
            self.root.after(REFRESH_MS, self.refresh)
            return

        primary = snapshot.get("primary") or {}
        secondary = snapshot.get("secondary") or {}
        short_remaining = int(round(float(primary.get("remainingPercent") or 0)))
        week_remaining = int(round(float(secondary.get("remainingPercent") or 0)))

        self.plan.config(text=f"Codex · {snapshot.get('planType') or 'unknown'}")
        self._set_meter(self.short, short_remaining)
        self._set_meter(self.week, week_remaining)
        self.status.config(text=self._status_text(short_remaining, primary.get("resetLabel")))
        self.root.after(REFRESH_MS, self.refresh)

    def _set_meter(self, meter: dict[str, tk.Widget], value: int) -> None:
        value = max(0, min(100, value))
        meter["value"].config(text=f"{value}%")
        meter["bar"].config(value=value)

    def _status_text(self, short_remaining: int, reset_label: object) -> str:
        synced = datetime.now().strftime("%H:%M")
        if short_remaining < 20:
            mood = "短期灵脉告急，先收束任务"
        elif short_remaining < 45:
            mood = "灵气偏紧，适合小步炼化"
        else:
            mood = "灵脉平稳，适合继续修行"
        reset = str(reset_label) if reset_label else "回转时间未知"
        return f"{mood}\n同步 {synced} · {reset}"

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    SpiritDesktopPet().run()
