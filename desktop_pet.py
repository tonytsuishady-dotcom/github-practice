from __future__ import annotations

import threading
import tkinter as tk
from datetime import datetime
from tkinter import ttk
from typing import Callable

from codex_usage import get_last_error, read_codex_rate_limits


REFRESH_MS = 60_000
GOOD = "#1f8a70"
WARN = "#c9852e"
DANGER = "#c95757"


class SpiritDesktopPet:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Codex 灵兽")
        self.root.geometry("320x270+80+80")
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

        close_button = self._icon_button(header, "×", self.root.destroy)
        close_button.pack(side="right", padx=(4, 0))

        refresh_button = self._icon_button(header, "↻", self.refresh)
        refresh_button.pack(side="right")

        self.plan = tk.Label(
            self.card,
            text="读取中...",
            bg="#fffaf0",
            fg="#65707f",
            font=("Microsoft YaHei UI", 9),
        )
        self.plan.pack(anchor="w", padx=12)

        self.canvas = tk.Canvas(self.card, width=128, height=96, bg="#fffaf0", highlightthickness=0)
        self.canvas.pack(pady=(2, 0))
        self._draw_pet(0, 0)

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

    def _icon_button(self, parent: tk.Widget, text: str, command: Callable[[], object]) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg="#ffffff",
            fg="#203d3a",
            activebackground="#e8f3ef",
            relief="flat",
            width=3,
            cursor="hand2",
            font=("Microsoft YaHei UI", 10, "bold"),
        )

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
        for widget in (self.root, self.card, self.title, self.plan, self.status, self.canvas):
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
            self._draw_pet(0, 0)
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
        self._draw_pet(short_remaining, week_remaining)
        self._set_meter(self.short, short_remaining)
        self._set_meter(self.week, week_remaining)
        self.status.config(text=self._status_text(short_remaining, primary.get("resetLabel")), fg=self._usage_color(short_remaining))
        self.root.after(REFRESH_MS, self.refresh)

    def _set_meter(self, meter: dict[str, tk.Widget], value: int) -> None:
        value = max(0, min(100, value))
        meter["value"].config(text=f"{value}%")
        meter["bar"].config(value=value)

    def _draw_pet(self, short_remaining: int, week_remaining: int) -> None:
        short_remaining = max(0, min(100, short_remaining))
        week_remaining = max(0, min(100, week_remaining))
        spirit_color = self._usage_color(short_remaining)
        belly_fill = self._blend("#f7e7bd", spirit_color, week_remaining / 100)

        self.canvas.delete("all")

        ink = "#203d3a"
        jade = "#3aa0a0"
        jade_shadow = "#2c7f88"
        horn = "#c8b983"
        blush = "#dd786f"
        aura = self._blend("#dff4ef", spirit_color, short_remaining / 100)

        self._pixel(22, 18, 14, 14, "#e6f3ed")
        self._pixel(90, 18, 14, 14, "#e6f3ed")
        self._pixel(18, 42, 10, 18, ink)
        self._pixel(100, 42, 10, 18, ink)
        self._pixel(22, 46, 10, 18, jade_shadow)
        self._pixel(96, 46, 10, 18, jade_shadow)

        self._pixel(38, 10, 10, 24, ink)
        self._pixel(80, 10, 10, 24, ink)
        self._pixel(40, 12, 8, 22, horn)
        self._pixel(80, 12, 8, 22, horn)

        self._pixel(34, 28, 60, 6, ink)
        self._pixel(28, 34, 72, 12, ink)
        self._pixel(24, 46, 80, 30, ink)
        self._pixel(30, 34, 68, 10, jade)
        self._pixel(28, 44, 72, 28, jade)
        self._pixel(34, 72, 60, 8, jade)

        self._pixel(42, 62, 44, 22, ink)
        self._pixel(46, 64, 36, 18, belly_fill)
        self._pixel(52, 68, 8, 6, aura)
        self._pixel(68, 68, 8, 6, aura)

        self._pixel(38, 52, 10, 4, blush)
        self._pixel(80, 52, 10, 4, blush)

        if short_remaining < 20:
            self._pixel(44, 44, 10, 4, ink)
            self._pixel(74, 44, 10, 4, ink)
            self._pixel(56, 54, 16, 6, ink)
        elif short_remaining < 45:
            self._pixel(44, 42, 8, 8, ink)
            self._pixel(76, 42, 8, 8, ink)
            self._pixel(54, 54, 20, 6, ink)
        else:
            self._pixel(44, 42, 8, 4, ink)
            self._pixel(76, 42, 8, 4, ink)
            self._pixel(48, 54, 32, 6, ink)
            self._pixel(54, 60, 20, 6, "#f3a0a9")

        self.canvas.create_text(64, 90, text=f"{short_remaining}%", fill=ink, font=("Microsoft YaHei UI", 8, "bold"))

    def _pixel(self, x: int, y: int, width: int, height: int, fill: str) -> None:
        self.canvas.create_rectangle(x, y, x + width, y + height, fill=fill, outline="")

    def _usage_color(self, remaining: int) -> str:
        if remaining < 20:
            return DANGER
        if remaining < 45:
            return WARN
        return GOOD

    def _blend(self, start: str, end: str, ratio: float) -> str:
        ratio = max(0.0, min(1.0, ratio))
        start_rgb = tuple(int(start[index : index + 2], 16) for index in (1, 3, 5))
        end_rgb = tuple(int(end[index : index + 2], 16) for index in (1, 3, 5))
        mixed = tuple(round(a + (b - a) * ratio) for a, b in zip(start_rgb, end_rgb))
        return f"#{mixed[0]:02x}{mixed[1]:02x}{mixed[2]:02x}"

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
