from __future__ import annotations

import ctypes
import json
import re
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog
from typing import Callable

from codex_usage import get_last_error, read_codex_rate_limits


ROOT = Path(__file__).resolve().parent
INBOX = ROOT / "pet-inbox"
STATE_FILE = INBOX / ".desktop-pet-state.json"
ART_DIR = ROOT / "assets" / "art"
ART_MANIFEST_FILE = ART_DIR / "manifest.json"
ART_STATES_FILE = ART_DIR / "states.json"
ART_GLYPHS_FILE = ART_DIR / "state-glyphs.json"
ART_ANCHORS_FILE = ART_DIR / "cosmetic-anchors.json"
REFRESH_MS = 60_000
FRAME_MS = 140

INK = "#203d3a"
JADE = "#3aa0a0"
JADE_DARK = "#2c7f88"
PAPER = "#fff8e7"
CREAM = "#f7e7bd"
GOLD = "#c8b983"
CORAL = "#dd786f"
CYAN = "#6eddd7"
GOOD = "#1f8a70"
WARN = "#c9852e"
DANGER = "#c95757"
KEY_CODES = list(range(0x30, 0x5B)) + [0x08, 0x09, 0x0D, 0x20, 0x25, 0x26, 0x27, 0x28]
MOUSE_CODES = [0x01, 0x02]
GLOBAL_INPUT_CODES = KEY_CODES + MOUSE_CODES


class SpiritDesktopPet:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Codex 灵兽桌宠")
        self.root.geometry("450x700+80+80")
        self.root.attributes("-topmost", True)
        self.root.resizable(False, False)
        self.root.configure(bg="#f8f6ef")
        self.root.bind("<KeyPress>", self.on_key_press)
        self.root.bind("<Button-1>", self.on_root_click)

        self.drag_start: tuple[int, int] | None = None
        self.frame = 0
        self.mode = "idle"
        self.mode_until = 0
        self.short_remaining = 0
        self.week_remaining = 0
        self.plan_type = "读取中"
        self.feed_count = 0
        self.useful_count = 0
        self.scroll_count = 0
        self.last_reset_label = ""
        self.digest_progress = 0
        self.last_material = ""
        self.events: list[str] = []
        self.tap_side = 0
        self.key_taps = 0
        self.hit_flash_frame = 0
        self.mini_mode = False
        self.last_activity_frame = 0
        self.sleep_after_frames = 360
        self.was_sleeping = False
        self.global_sensing = False
        self.global_thread_started = False
        self.global_down: set[int] = set()
        self.last_global_input_at = 0.0
        self.art_manifest, self.art_states, self.art_glyphs, self.art_anchors = self._load_art_kit()

        self._load_local_state()
        self._build_ui()
        self._bind_drag()
        self.refresh()
        self._tick()

    def _build_ui(self) -> None:
        self.card = tk.Frame(self.root, bg=PAPER, highlightbackground=INK, highlightthickness=2)
        self.card.pack(fill="both", expand=True, padx=10, pady=10)

        header = tk.Frame(self.card, bg=PAPER)
        header.pack(fill="x", padx=14, pady=(12, 4))

        title_stack = tk.Frame(header, bg=PAPER)
        title_stack.pack(side="left", fill="x", expand=True)
        tk.Label(
            title_stack,
            text="CODEX SPIRIT COMPANION",
            bg=PAPER,
            fg=GOOD,
            font=("Microsoft YaHei UI", 8, "bold"),
        ).pack(anchor="w")
        self.title = tk.Label(
            title_stack,
            text="饕餮灵脉",
            bg=PAPER,
            fg=INK,
            font=("Microsoft YaHei UI", 18, "bold"),
        )
        self.title.pack(anchor="w")

        self.stage_badge = tk.Label(
            header,
            text="幼体",
            bg="#e8f3ef",
            fg=INK,
            font=("Microsoft YaHei UI", 9, "bold"),
            padx=10,
            pady=5,
        )
        self.stage_badge.pack(side="right", padx=(0, 8))

        self._icon_button(header, "×", self.root.destroy).pack(side="right", padx=(4, 0))
        self._icon_button(header, "↻", self.refresh).pack(side="right")
        self.mini_button = self._icon_button(header, "▣", self.toggle_mini_mode)
        self.mini_button.pack(side="right", padx=(0, 4))

        self.plan = tk.Label(
            self.card,
            text="正在同步 Codex 灵脉...",
            bg="#fff1cc",
            fg="#65707f",
            font=("Microsoft YaHei UI", 9),
            padx=10,
            pady=5,
        )
        self.plan.pack(fill="x", padx=14, pady=(2, 8))

        self.canvas = tk.Canvas(self.card, width=390, height=340, bg=PAPER, highlightthickness=0)
        self.canvas.pack(pady=(2, 0))
        self.canvas.bind("<Button-1>", self.pet)

        self.stats = tk.Frame(self.card, bg=PAPER)
        self.stats.pack(fill="x", padx=14, pady=(0, 8))
        self.stage_chip = self._stat_chip(self.stats, "境界", "幼体")
        self.scroll_chip = self._stat_chip(self.stats, "玉简", "0")
        self.digest_chip = self._stat_chip(self.stats, "炼化", "0%")
        self.art_chip = self._stat_chip(self.stats, "美术", "状态表")

        self.bubble = tk.Label(
            self.card,
            text="我能吞灵材，也要帮你炼成真正成果。",
            bg="#e8f3ef",
            fg=INK,
            font=("Microsoft YaHei UI", 9, "bold"),
            wraplength=340,
            justify="left",
            padx=10,
            pady=8,
        )
        self.bubble.pack(fill="x", padx=14, pady=(0, 8))

        self.detail = tk.Frame(self.card, bg=PAPER)
        self.detail.pack(fill="both", expand=True)

        self.status = tk.Label(
            self.detail,
            text="点击灵兽可以互动，投喂文件会生成本地玉简。",
            bg=PAPER,
            fg="#65707f",
            font=("Microsoft YaHei UI", 9),
            wraplength=360,
            justify="left",
        )
        self.status.pack(fill="x", padx=14, pady=(0, 8))

        self.short = self._meter("短期灵脉")
        self.week = self._meter("长期灵脉")

        actions = tk.Frame(self.detail, bg=PAPER)
        actions.pack(fill="x", padx=14, pady=(10, 6))
        self._action_button(actions, "投喂", self.feed_files).pack(side="left", expand=True, fill="x", padx=(0, 4))
        self._action_button(actions, "敲玉简", self.tap_jade_slip).pack(side="left", expand=True, fill="x", padx=4)
        self._action_button(actions, "炼化", self.mark_useful).pack(side="left", expand=True, fill="x", padx=(4, 0))

        self.sense_button = self._action_button(self.detail, "开启全局输入感应", self.toggle_global_sensing)
        self.sense_button.pack(fill="x", padx=14, pady=(0, 6))

        refine = tk.Frame(self.detail, bg=PAPER)
        refine.pack(fill="x", padx=14, pady=(4, 6))
        refine_top = tk.Frame(refine, bg=PAPER)
        refine_top.pack(fill="x")
        tk.Label(refine_top, text="炼化炉", bg=PAPER, fg=INK, font=("Microsoft YaHei UI", 9, "bold")).pack(side="left")
        self.refine_value = tk.Label(refine_top, text="0%", bg=PAPER, fg=INK, font=("Microsoft YaHei UI", 9, "bold"))
        self.refine_value.pack(side="right")
        self.refine_bar = self._pixel_bar(refine, GOLD)
        self.refine_bar["canvas"].pack(fill="x", pady=(3, 0))

        self.progress = tk.Label(
            self.detail,
            text="一代闭环：等待灵脉同步",
            bg=PAPER,
            fg=INK,
            font=("Microsoft YaHei UI", 9, "bold"),
        )
        self.progress.pack(fill="x", padx=14, pady=(2, 10))

        self.log = tk.Label(
            self.detail,
            text="灵兽日志：等待第一份灵材。",
            bg="#fff7dc",
            fg="#65707f",
            font=("Microsoft YaHei UI", 8),
            wraplength=340,
            justify="left",
            padx=10,
            pady=8,
        )
        self.log.pack(fill="x", padx=14, pady=(0, 10))

    def _icon_button(self, parent: tk.Widget, text: str, command: Callable[[], object]) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg="#ffffff",
            fg=INK,
            activebackground="#e8f3ef",
            relief="flat",
            width=3,
            cursor="hand2",
            font=("Microsoft YaHei UI", 10, "bold"),
        )

    def _action_button(self, parent: tk.Widget, text: str, command: Callable[[], object]) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=INK,
            fg="#ffffff",
            activebackground="#2d4e49",
            activeforeground="#ffffff",
            relief="flat",
            cursor="hand2",
            font=("Microsoft YaHei UI", 10, "bold"),
            height=2,
        )

    def _stat_chip(self, parent: tk.Widget, label: str, value: str) -> tk.Label:
        frame = tk.Frame(parent, bg="#fff7dc", highlightbackground="#eadfca", highlightthickness=1)
        frame.pack(side="left", expand=True, fill="x", padx=3)
        tk.Label(frame, text=label, bg="#fff7dc", fg="#65707f", font=("Microsoft YaHei UI", 8)).pack(anchor="w", padx=8, pady=(5, 0))
        value_label = tk.Label(frame, text=value, bg="#fff7dc", fg=INK, font=("Microsoft YaHei UI", 11, "bold"))
        value_label.pack(anchor="w", padx=8, pady=(0, 5))
        return value_label

    def _pixel_bar(self, parent: tk.Widget, color: str) -> dict[str, tk.Widget | int | str]:
        canvas = tk.Canvas(parent, height=14, bg=PAPER, highlightthickness=0)
        border = canvas.create_rectangle(0, 1, 10, 13, outline=INK, width=2, fill="#fff7dc")
        fill = canvas.create_rectangle(3, 4, 3, 10, outline="", fill=color)
        return {"canvas": canvas, "border": border, "fill": fill, "color": color}

    def _meter(self, label: str) -> dict[str, tk.Widget]:
        frame = tk.Frame(self.detail, bg=PAPER)
        frame.pack(fill="x", padx=14, pady=(6, 0))

        top = tk.Frame(frame, bg=PAPER)
        top.pack(fill="x")
        name = tk.Label(top, text=label, bg=PAPER, fg=INK, font=("Microsoft YaHei UI", 9, "bold"))
        name.pack(side="left")
        value = tk.Label(top, text="--%", bg=PAPER, fg=INK, font=("Microsoft YaHei UI", 9, "bold"))
        value.pack(side="right")

        bar = self._pixel_bar(frame, GOOD)
        bar["canvas"].pack(fill="x", pady=(3, 0))
        return {"value": value, "bar": bar}

    def _bind_drag(self) -> None:
        for widget in (self.root, self.card, self.title, self.plan, self.status, self.progress, self.bubble, self.log):
            widget.bind("<ButtonPress-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._drag)

    def _start_drag(self, event: tk.Event) -> None:
        self.drag_start = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def _drag(self, event: tk.Event) -> None:
        if not self.drag_start:
            return
        offset_x, offset_y = self.drag_start
        self.root.geometry(f"+{event.x_root - offset_x}+{event.y_root - offset_y}")

    def on_root_click(self, _event: tk.Event) -> None:
        self.root.focus_force()

    def on_key_press(self, event: tk.Event) -> None:
        if event.keysym in {"Escape", "Tab", "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R"}:
            return
        self.tap_jade_slip(from_key=True)

    def toggle_global_sensing(self) -> None:
        self._touch_activity()
        self.global_sensing = not self.global_sensing
        if self.global_sensing and not self.global_thread_started:
            self.global_thread_started = True
            threading.Thread(target=self._global_input_loop, daemon=True).start()
        if self.global_sensing:
            self.sense_button.config(text="关闭全局输入感应")
            self._say("我开始听电脑的动静了，只感应输入发生，不记录内容。", "全局输入感应开启。", GOOD)
        else:
            self.sense_button.config(text="开启全局输入感应")
            self.global_down.clear()
            self._say("我收回耳朵了。现在只响应窗口内互动。", "全局输入感应关闭。", WARN)

    def toggle_mini_mode(self) -> None:
        self._touch_activity()
        self.mini_mode = not self.mini_mode
        if self.mini_mode:
            self.plan.pack_forget()
            self.stats.pack_forget()
            self.detail.pack_forget()
            self.root.geometry("420x445")
            self.root.attributes("-alpha", 0.96)
            self.mini_button.config(text="□")
            self.bubble.config(text=f"小窗伴随 · 短期灵脉 {self.short_remaining}% · 炼化 {self.digest_progress}%")
            self.status.config(text="迷你桌宠模式开启。", fg=GOOD)
            return

        self.plan.pack(fill="x", padx=14, pady=(2, 8), before=self.canvas)
        self.stats.pack(fill="x", padx=14, pady=(0, 8), after=self.canvas)
        self.detail.pack(fill="both", expand=True)
        self.root.geometry("450x700")
        self.root.attributes("-alpha", 1.0)
        self.mini_button.config(text="▣")
        self._say("完整面板展开，可以查看灵脉、炼化炉和日志。", "完整面板已展开。", GOOD)

    def _global_input_loop(self) -> None:
        try:
            user32 = ctypes.windll.user32
        except AttributeError:
            self.root.after(0, lambda: self._say("这套感应只支持 Windows。", "全局输入感应不可用。", DANGER))
            return

        while True:
            if not self.global_sensing:
                time.sleep(0.12)
                continue

            pressed = {code for code in GLOBAL_INPUT_CODES if user32.GetAsyncKeyState(code) & 0x8000}
            newly_pressed = pressed - self.global_down
            self.global_down = pressed
            if newly_pressed:
                now = time.monotonic()
                if now - self.last_global_input_at > 0.08:
                    self.last_global_input_at = now
                    source = "鼠标" if any(code in MOUSE_CODES for code in newly_pressed) else "键盘"
                    self.root.after(0, lambda source=source: self.tap_jade_slip(from_global=True, source=source))
            time.sleep(0.035)

    def refresh(self) -> None:
        self._touch_activity()
        self.status.config(text="正在同步 Codex 灵脉...")
        threading.Thread(target=self._load_usage, daemon=True).start()

    def _load_usage(self) -> None:
        snapshot = read_codex_rate_limits()
        self.root.after(0, lambda: self._render_snapshot(snapshot))

    def _render_snapshot(self, snapshot: dict | None) -> None:
        if not snapshot:
            self.plan_type = "Demo"
            self.short_remaining = 0
            self.week_remaining = 0
            self.plan.config(text="Demo / 未连接")
            self._set_meter(self.short, 0)
            self._set_meter(self.week, 0)
            self.status.config(text=f"读取失败：{get_last_error()}", fg=DANGER)
            self._render_progress()
            self.root.after(REFRESH_MS, self.refresh)
            return

        primary = snapshot.get("primary") or {}
        secondary = snapshot.get("secondary") or {}
        self.short_remaining = self._clamp_int(primary.get("remainingPercent"), 0, 100)
        self.week_remaining = self._clamp_int(secondary.get("remainingPercent"), 0, 100)
        self.plan_type = str(snapshot.get("planType") or "unknown")
        self.last_reset_label = str(primary.get("resetLabel") or "")

        self.plan.config(text=f"Codex · {self.plan_type} · {self.stage_name()}")
        self._set_meter(self.short, self.short_remaining)
        self._set_meter(self.week, self.week_remaining)
        self.status.config(text=self._status_text(), fg=self._usage_color(self.short_remaining))
        self._render_progress()
        self._save_local_state()
        self.root.after(REFRESH_MS, self.refresh)

    def _set_meter(self, meter: dict[str, tk.Widget], value: int) -> None:
        value = max(0, min(100, value))
        meter["value"].config(text=f"{value}%")
        color = self._usage_color(value)
        self._set_pixel_bar(meter["bar"], value, color)

    def _set_pixel_bar(self, bar: dict[str, tk.Widget | int | str], value: int, color: str | None = None) -> None:
        canvas = bar["canvas"]
        if not isinstance(canvas, tk.Canvas):
            return
        canvas.update_idletasks()
        width = max(80, canvas.winfo_width())
        fill_width = max(3, int((width - 6) * max(0, min(100, value)) / 100))
        canvas.coords(bar["border"], 0, 1, width - 1, 13)
        canvas.coords(bar["fill"], 3, 4, fill_width, 10)
        canvas.itemconfig(bar["fill"], fill=color or str(bar["color"]))

    def pet(self, _event: tk.Event | None = None) -> None:
        self._touch_activity()
        self._set_mode("clicking", 18)
        self._say("饕餮蹭了蹭你：今日也要炼化成真正成果。", "摸摸灵兽，精神 +1。", GOOD)

    def tap_jade_slip(self, from_key: bool = False, from_global: bool = False, source: str = "键盘") -> None:
        self._touch_activity()
        self.tap_side = 1 - self.tap_side
        self.key_taps += 1
        self.hit_flash_frame = self.frame
        self._set_mode("typing", 9 + (self.key_taps % 3))
        action_source = f"全局{source}" if from_global else ("键盘输入" if from_key else "敲玉简")
        if self.key_taps % 12 == 0:
            self.digest_progress = min(99, self.digest_progress + 6)
        self.bubble.config(text="哒、哒、哒。饕餮正跟着你的节奏敲玉简。")
        self.status.config(text=f"{action_source}驱动动作 · {self.key_taps} 次", fg=GOOD)
        if not from_global or self.key_taps % 8 == 1:
            self._append_event(f"{action_source}驱动动作 · {self.key_taps} 次")
        self._update_refine_ui()

    def feed_files(self) -> None:
        self._touch_activity()
        self._say("张嘴等灵材中。文件只会在本地生成玉简。", "正在打开文件选择框。", GOOD)
        self.root.attributes("-topmost", False)
        self.root.update_idletasks()
        paths = filedialog.askopenfilenames(parent=self.root, title="选择要投喂的灵材")
        self.root.attributes("-topmost", True)
        self.root.lift()
        if not paths:
            self._say("没选到灵材。再投一次也可以。", "投喂取消。", WARN)
            return
        self._feed_paths([Path(raw_path) for raw_path in paths])

    def _feed_paths(self, paths: list[Path]) -> None:
        self._touch_activity()
        INBOX.mkdir(exist_ok=True)
        saved = 0
        names = []
        for path in paths:
            markdown = self._make_scroll(path)
            target = self._unique_scroll_path(path.name)
            target.write_text(markdown, encoding="utf-8")
            saved += 1
            names.append(path.name)
        self.feed_count += saved
        self.scroll_count += saved
        self.digest_progress = min(95, self.digest_progress + 34 + saved * 8)
        self.last_material = names[0] if names else ""
        self._set_mode("eating", 30)
        self._say(
            f"咔嚓！收下 {saved} 份灵材，正在炼化成玉简。",
            f"投喂：{', '.join(names[:2])}{' 等' if len(names) > 2 else ''}",
            GOOD,
        )
        self._save_local_state()
        self._render_progress()
        self._update_refine_ui()

    def mark_useful(self) -> None:
        self._touch_activity()
        self.useful_count += 1
        self.digest_progress = 100
        self._set_mode("happy", 42)
        self._say("炼化完成！这次消耗转成了修为。", "有效成果 +1，灵兽发光。", GOOD)
        self._save_local_state()
        self._render_progress()
        self._update_refine_ui()

    def _make_scroll(self, path: Path) -> str:
        now = datetime.now()
        preview = self._text_preview(path)
        summary = preview if preview else "此物以形质为主，桌宠只记录外相，不读取正文。"
        return "\n".join(
            [
                f"# 桌宠投喂玉简：{path.name}",
                "",
                f"- 灵材名称：{path.name}",
                f"- 灵材大小：{self._format_size(path)}",
                f"- 投喂时间：{now.strftime('%Y-%m-%d %H:%M:%S')}",
                "- 来源：桌面悬浮灵兽",
                "",
                "## 初步炼化",
                "",
                summary,
                "",
                "## 后续可用 prompt",
                "",
                f"请基于这份灵材 {path.name}，帮我整理重点、风险和下一步行动。",
                "",
            ]
        )

    def _text_preview(self, path: Path) -> str:
        if path.suffix.lower() not in {".txt", ".md", ".json", ".csv", ".log", ".xml", ".html", ".css", ".js", ".ts"}:
            return ""
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")[:1200]
        except OSError:
            return ""
        clean = re.sub(r"\s+", " ", text).strip()
        return clean[:360]

    def _unique_scroll_path(self, name: str) -> Path:
        safe = re.sub(r"[^\w.\-\u4e00-\u9fff]+", "-", name, flags=re.UNICODE).strip("-")[:80]
        safe = safe or "spirit-material"
        stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        path = INBOX / f"{stamp}-{safe}.md"
        for index in range(2, 1000):
            if not path.exists():
                return path
            path = INBOX / f"{stamp}-{safe}-{index}.md"
        raise RuntimeError("too many duplicate feed records")

    def _tick(self) -> None:
        self.frame += 1
        if self.mode == "eating" and self.frame > self.mode_until:
            self._set_mode("digesting", 46)
            self.bubble.config(text="咕噜咕噜。灵材正在肚子里炼成玉简。")
            self.status.config(text="炼化中：把投喂转成可用成果。", fg=GOOD)
        elif self.mode != "idle" and self.frame > self.mode_until:
            self.mode = "idle"
        sleeping = self._is_sleeping()
        if sleeping and not self.was_sleeping:
            self.bubble.config(text="灵兽盘起来打坐了。敲键盘、点它或投喂灵材，都能把它唤醒。")
            self.status.config(text="空闲中：进入打坐/犯困状态。", fg="#65707f")
        self.was_sleeping = sleeping
        if self.mode in {"eating", "digesting"} and self.digest_progress < 96:
            self.digest_progress = min(96, self.digest_progress + 1)
            self._update_refine_ui()
        elif self.mode == "happy" and self.frame % 3 == 0:
            self.digest_progress = max(0, self.digest_progress - 2)
            self._update_refine_ui()
        elif self.mode == "typing" and self.frame % 2 == 0:
            self.digest_progress = min(99, self.digest_progress + 1)
            self._update_refine_ui()
        if self.mini_mode and self.frame % 10 == 0:
            self.bubble.config(text=f"{self._state_label()} · 短期灵脉 {self.short_remaining}% · 炼化 {self.digest_progress}%")
        self._draw_pet()
        self.root.after(FRAME_MS, self._tick)

    def _set_mode(self, mode: str, frames: int) -> None:
        self.mode = mode
        self.mode_until = self.frame + frames

    def _touch_activity(self) -> None:
        self.last_activity_frame = self.frame
        self.was_sleeping = False

    def _is_sleeping(self) -> bool:
        idle_frames = self.frame - self.last_activity_frame
        return self.mode == "idle" and idle_frames > self.sleep_after_frames

    def _visual_state(self) -> str:
        if self._is_sleeping():
            return "sleeping"
        if self.mode == "idle" and self.short_remaining < 20:
            return "low_energy"
        return self.mode

    def _state_label(self) -> str:
        labels = {
            "idle": "待机呼吸",
            "sleeping": "打坐犯困",
            "typing": "敲玉简",
            "clicking": "被摸醒",
            "eating": "吞灵材",
            "digesting": "炼化中",
            "happy": "发光开心",
            "low_energy": "灵脉偏低",
        }
        return labels.get(self._visual_state(), "待机呼吸")

    def _draw_pet(self) -> None:
        self.canvas.delete("all")
        stage = self.stage()
        state = self._visual_state()
        sleeping = state == "sleeping"
        bob = 0 if state in {"eating", "typing", "sleeping", "digesting"} else (self.frame % 12 > 5) * -4
        if state == "clicking":
            bob -= 8
        if state == "typing":
            bob += (-2, 0, 2, 0)[self.frame % 4]
        elif state == "digesting":
            bob += (self.frame % 8 in {0, 1}) * 2
        x = 180
        if state == "typing":
            x += (-4, 0, 4, 0)[self.frame % 4]
        elif state == "clicking":
            x += (self.frame % 6 in {0, 1, 2}) * 3
        y = 178 + bob
        scale = 1.15 + (stage - 1) * 0.13
        size = round(18 * scale)
        body_w = 7 * size
        body_h = 6 * size
        left = x - body_w // 2
        top = y - body_h // 2
        spirit_color = self._usage_color(self.short_remaining)
        belly = self._blend(CREAM, spirit_color, self.week_remaining / 100)

        self.canvas.create_rectangle(12, 14, 348, 314, fill="#eadfca", outline="")
        self.canvas.create_rectangle(18, 18, 342, 308, fill="#fff6df", outline="")
        self.canvas.create_rectangle(28, 28, 332, 268, fill="#fffaf0", outline="")
        self.canvas.create_rectangle(28, 268, 332, 290, fill="#efe1c4", outline="")
        for tile_x in range(34, 330, 28):
            self.canvas.create_line(tile_x, 268, tile_x - 10, 290, fill="#dfcfad")
        for tile_y in (52, 92, 132, 172, 212):
            self.canvas.create_line(34, tile_y, 326, tile_y, fill="#f3ecd9")
        for tile_x in (42, 86, 130, 174, 218, 262, 306):
            self.canvas.create_line(tile_x, 34, tile_x, 258, fill="#f3ecd9")
        self._px(20, 20, 18, 6, GOLD)
        self._px(20, 20, 6, 18, GOLD)
        self._px(322, 20, 18, 6, GOLD)
        self._px(334, 20, 6, 18, GOLD)
        self._px(20, 288, 6, 18, GOLD)
        self._px(20, 300, 18, 6, GOLD)
        self._px(322, 300, 18, 6, GOLD)
        self._px(334, 288, 6, 18, GOLD)

        aura_active = not sleeping and (stage >= 3 or state in {"eating", "digesting", "happy", "clicking", "typing"})
        if aura_active:
            pulse = 6 + (self.frame % 10) * 2
            color = GOLD if state == "eating" else CYAN
            self.canvas.create_oval(x - 112 - pulse, y - 118 - pulse, x + 112 + pulse, y + 118 + pulse, outline=color, width=3)
            self.canvas.create_oval(x - 91 + pulse // 2, y - 96 + pulse // 2, x + 91 - pulse // 2, y + 96 - pulse // 2, outline="#d3f4ee", width=2)
            for index, offset in enumerate((-116, -78, -38, 44, 86, 118)):
                spark_y = top - 28 + ((self.frame * 3 + index * 7) % 58)
                self._px(x + offset, spark_y, 7, 7, color)

        self._shadow(x, top + body_h + 15, body_w)

        if stage >= 2:
            self._px(left + body_w - size, top + body_h - size, size * 2, size, INK)
            self._px(left + body_w, top + body_h - size * 2, size, size, JADE_DARK)
            self._px(left + body_w + size, top + body_h - size * 2, size, size, CREAM)
            if stage >= 3:
                self._px(left + body_w + size * 2, top + body_h - size * 3, size, size * 2, GOLD)
                self._px(left + body_w + size * 2 + 4, top + body_h - size * 3 + 4, size - 8, size - 8, CYAN)

        if stage >= 2:
            pack_x = left + body_w - size
            pack_y = top + size * 2
            self._px(pack_x, pack_y, size * 2, size * 3, INK)
            self._px(pack_x + 4, pack_y + 4, size * 2 - 8, size * 3 - 8, "#2e3d3e")
            self._px(pack_x + size // 2, pack_y + size, size, size, GOLD)
            self._px(pack_x + size // 2 + 4, pack_y + size + 4, size - 8, size - 8, CYAN if stage >= 5 else CREAM)
            self._px(pack_x + size * 2 - 6, pack_y + size * 2, 6, size, CORAL)

        self._px(left - size, top + size * 2, size, size * 2, INK)
        self._px(left + body_w, top + size * 2, size, size * 2, INK)
        typing_drop = 16 + (self.key_taps % 3) * 2
        left_arm_drop = typing_drop if state == "typing" and self.tap_side == 0 else 0
        right_arm_drop = typing_drop if state == "typing" and self.tap_side == 1 else 0
        if state == "eating":
            left_arm_drop = right_arm_drop = 8
        elif state == "clicking":
            left_arm_drop = right_arm_drop = -6
        self._px(left - size + 4, top + size * 2 + 4 + left_arm_drop, size - 4, size * 2 - 8, JADE_DARK)
        self._px(left + body_w, top + size * 2 + 4 + right_arm_drop, size - 4, size * 2 - 8, JADE_DARK)
        self._px(left - size + 6, top + size * 2 + 6, size - 8, size - 8, "#d79074")
        self._px(left + body_w + 2, top + size * 2 + 6, size - 8, size - 8, "#d79074")

        horn_h = size * (2 if stage < 4 else 3)
        for side in (0, 1):
            hx = left + size * (2 if side == 0 else 5)
            self._px(hx - 4, top - horn_h + size, size + 8, horn_h, INK)
            self._px(hx, top - horn_h + size + 4, size, horn_h - 4, GOLD)
            self._px(hx + 6, top - horn_h + size + 10, size // 2, 6, "#f3d27b")
            if stage >= 3:
                self._px(hx + (size // 2), top - horn_h, size, size, GOLD)
                self._px(hx + (size // 2) + 4, top - horn_h + 4, size - 8, size - 8, "#f6df9d")

        if stage >= 4:
            self._px(x - size // 2, top - horn_h - size // 2, size, size, GOLD)
            self._px(x - size // 4, top - horn_h - size // 4, size // 2, size // 2, CYAN)

        self._px(left + size, top, size * 5, size, INK)
        self._px(left, top + size, size * 7, size * 4, INK)
        self._px(left + size, top + size * 5, size * 5, size, INK)
        self._px(left + size, top + size, size * 5, size * 4, JADE)
        self._px(left + size * 2, top + size * 5, size * 3, size, JADE)
        self._px(left + size * 2, top + size, size, size // 2, "#f2dda4")
        self._px(left + size * 4, top + size, size, size // 2, "#f2dda4")
        self._px(left + size * 3, top + size * 2 - 4, size, 5, "#26746f")
        self._px(left + size + 5, top + size + 5, size, 5, "#6bc2b8")
        self._px(left + size * 5 - 5, top + size + 8, 5, size, "#2c8f87")
        if stage >= 2:
            self._px(left + size, top + size * 3, size // 2, size // 2, "#f2dda4")
            self._px(left + size * 5, top + size * 3, size // 2, size // 2, "#f2dda4")
        if stage >= 4:
            self._px(left + size * 5, top + size * 4, size // 2, size // 2, CYAN)
            self._px(left + size, top + size * 4, size // 2, size // 2, CYAN)

        self._px(left + size * 2, top + size * 4, size * 3, size * 2, INK)
        self._px(left + size * 2 + 4, top + size * 4 + 4, size * 3 - 8, size * 2 - 4, belly)
        self._px(x - size // 2, top + size * 5, size, size // 2, GOLD)
        self._px(x - size // 4, top + size * 5 + 4, size // 2, size // 2 - 4, CYAN if self.digest_progress > 70 else "#fff6d6")
        if self.digest_progress:
            orb_size = max(8, int(size * self.digest_progress / 100))
            orb_y = top + size * 5 + size // 2
            if state == "digesting":
                orb_size += (self.frame % 6 in {0, 1, 2}) * 4
                orb_y -= (self.frame % 5)
            self._px(x - orb_size // 2, orb_y, orb_size, orb_size, CYAN if state == "happy" else GOLD)

        self._px(left + size * 2, top + size * 2, size // 2, size // 2, CORAL)
        self._px(left + size * 5 - size // 2, top + size * 2, size // 2, size // 2, CORAL)

        if state == "eating":
            self._px(left + size * 2 - 4, top + size * 3 - 4, size * 3 + 8, size + 8, INK)
            self._px(left + size * 3, top + size * 4, size, size // 2, "#f3a0a9")
            self._px(left + size * 2 + 4, top + size * 3 - 4, size // 2, size // 2, "#ffffff")
            self._px(left + size * 4, top + size * 3 - 4, size // 2, size // 2, "#ffffff")
            item_y = top - 36 + (self.frame % 8) * 5
            self._px(x - 8, item_y, 16, 18, GOLD)
            self._px(x - 4, item_y + 4, 8, 8, "#ffffff")
        elif state == "digesting":
            self._px(left + size * 2, top + size * 2, size // 2, size // 2, INK)
            self._px(left + size * 4, top + size * 2, size // 2, size // 2, INK)
            self._px(left + size * 3 - 4, top + size * 3, size * 2, 5, INK)
            for offset in (-28, 0, 28):
                spark_y = top + size * 5 + ((self.frame + offset) % 18)
                self._px(x + offset, spark_y, 6, 6, CYAN)
        elif sleeping:
            self._px(left + size * 2, top + size * 2, size, 5, INK)
            self._px(left + size * 4, top + size * 2, size, 5, INK)
            self._px(left + size * 3, top + size * 3, size, 5, INK)
            self._px(left + size * 3, top + size * 3 + 7, size // 2, 4, "#f3a0a9")
            self.canvas.create_text(x + 84, top + 24, text="Z", fill=INK, font=("Microsoft YaHei UI", 14, "bold"))
            self.canvas.create_text(x + 104, top + 4, text="z", fill="#65707f", font=("Microsoft YaHei UI", 11, "bold"))
            self.canvas.create_text(x + 118, top - 14, text="z", fill="#8da19a", font=("Microsoft YaHei UI", 9, "bold"))
        elif state == "typing":
            self._px(x - size * 2, top + size * 6 + 8, size * 4, size // 2, INK)
            self._px(x - size * 2 + 4, top + size * 6 + 12, size * 4 - 8, size // 2 - 4, "#fff7dc")
            hit_x = left - size // 2 if self.tap_side == 0 else left + body_w - size // 2
            self._px(hit_x, top + size * 6, size, 6, GOLD)
            self._px(hit_x + size // 2, top + size * 6 - 8, 6, 8, CYAN)
            if self.frame - self.hit_flash_frame < 5:
                self._px(hit_x - 8, top + size * 6 - 18, 8, 8, GOLD)
                self._px(hit_x + size + 2, top + size * 6 - 22, 8, 8, CYAN)
                self.canvas.create_text(hit_x + size // 2, top + size * 6 - 32, text="哒", fill=INK, font=("Microsoft YaHei UI", 10, "bold"))
        elif state == "low_energy":
            self._px(left + size * 2, top + size * 2, size, 5, INK)
            self._px(left + size * 4, top + size * 2, size, 5, INK)
            self._px(left + size * 3, top + size * 3, size, 5, INK)
            self._px(left + size * 3, top + size * 3 + 8, size // 2, 4, "#65707f")
        elif state == "clicking":
            self._px(left + size * 2, top + size * 2, size // 2, size // 2, INK)
            self._px(left + size * 4, top + size * 2, size // 2, size // 2, INK)
            self._px(left + size * 3 - 2, top + size * 3, size * 2, 6, INK)
            self._px(left + size * 3, top + size * 3 + 6, size, 6, "#f3a0a9")
            self.canvas.create_text(x, top - 36, text="精神 +1", fill=GOOD, font=("Microsoft YaHei UI", 10, "bold"))
        else:
            blink = self.frame % 32 in {0, 1}
            eye_h = 4 if blink else size // 2
            self._px(left + size * 2, top + size * 2, size // 2, eye_h, INK)
            self._px(left + size * 4, top + size * 2, size // 2, eye_h, INK)
            self._px(left + size * 3, top + size * 3, size, 6, INK)
            self._px(left + size * 3, top + size * 3 + 6, size, 5, "#f3a0a9")

        if stage >= 3:
            self._px(x - size // 2, top + size // 2, size, size // 2, GOLD)
            self._px(x - size // 4, top + size // 2 + 3, size // 2, size // 2 - 4, CYAN)
            self._px(x - size // 2, top + size * 5, size, size, GOLD)

        if stage >= 5 or state == "happy":
            self.canvas.create_arc(x - 112, top - 42, x + 112, top + 76, start=15, extent=150, style="arc", outline=GOLD, width=4)
            self._px(x - 6, top - 52, 12, 12, GOLD)

        self._px(left + size, top + body_h, size * 2, size, INK)
        self._px(left + size * 4, top + body_h, size * 2, size, INK)
        self._px(left + size + 4, top + body_h + 4, size * 2 - 8, size - 4, JADE_DARK)
        self._px(left + size * 4 + 4, top + body_h + 4, size * 2 - 8, size - 4, JADE_DARK)
        for claw_x in (left + size + 8, left + size * 2, left + size * 4 + 8, left + size * 5):
            self._px(claw_x, top + body_h + size - 5, 6, 4, CREAM)

        art_state = self._art_state(state)
        art_text = art_state.get("label") or self._state_label()
        self._draw_cosmetic_anchors(state)
        self._draw_state_glyph(42, 278, state, 5)
        self.canvas.create_text(x, 292, text=f"ART · {art_text}", fill="#65707f", font=("Microsoft YaHei UI", 9, "bold"))
        self.canvas.create_text(x, 308, text=f"{self.stage_name()} · 玉简 {self.scroll_count}", fill=INK, font=("Microsoft YaHei UI", 10, "bold"))

    def _px(self, x: int, y: int, width: int, height: int, fill: str) -> None:
        self.canvas.create_rectangle(x, y, x + width, y + height, fill=fill, outline="")

    def _shadow(self, x: int, y: int, width: int) -> None:
        self.canvas.create_oval(x - width // 2, y, x + width // 2, y + 16, fill="#d8c8a8", outline="")

    def _draw_state_glyph(self, x: int, y: int, state: str, pixel: int) -> None:
        palette = self.art_glyphs.get("palette", {})
        glyphs = self.art_glyphs.get("glyphs", {})
        glyph = glyphs.get(state) or glyphs.get("idle") or []
        if not isinstance(glyph, list):
            return
        self.canvas.create_rectangle(x - 4, y - 4, x + 39, y + 39, fill="#fffaf0", outline=INK, width=2)
        for row_index, row in enumerate(glyph):
            if not isinstance(row, str):
                continue
            for column_index, key in enumerate(row):
                color = palette.get(key)
                if not color or color == "transparent":
                    continue
                self._px(x + column_index * pixel, y + row_index * pixel, pixel, pixel, color)

    def _draw_cosmetic_anchors(self, state: str) -> None:
        anchors = self.art_anchors.get("anchors", [])
        if not isinstance(anchors, list):
            return
        preview_active = state in {"clicking", "happy", "digesting"} or self.frame % 28 < 12
        if not preview_active:
            return
        for anchor in anchors:
            if not isinstance(anchor, dict):
                continue
            x = self._clamp_int(anchor.get("x"), 0, 390)
            y = self._clamp_int(anchor.get("y"), 0, 340)
            radius = self._clamp_int(anchor.get("radius"), 8, 28)
            color = str(anchor.get("color") or GOLD)
            label = str(anchor.get("label") or anchor.get("id") or "")
            self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius, outline=color, width=2)
            self.canvas.create_oval(x - 3, y - 3, x + 3, y + 3, fill=color, outline="")
            if state in {"clicking", "happy"}:
                self.canvas.create_text(x, y + radius + 10, text=label, fill=INK, font=("Microsoft YaHei UI", 8, "bold"))

    def _render_progress(self) -> None:
        checks = [
            self.plan_type not in {"读取中", "Demo"},
            self.feed_count > 0,
            self.useful_count > 0,
            self.scroll_count > 0,
        ]
        score = sum(checks) * 25
        next_steps = ["同步灵脉", "投喂灵材", "确认炼化", "玉简入洞府"]
        next_step = next((next_steps[index] for index, done in enumerate(checks) if not done), "闭环已通")
        self.progress.config(text=f"一代闭环 {score}% · 下一步：{next_step}")
        stage = self.stage_name()
        self.stage_badge.config(text=stage)
        self.stage_chip.config(text=stage)
        self.scroll_chip.config(text=str(self.scroll_count))
        if hasattr(self, "art_chip"):
            self.art_chip.config(text=self._art_state(self._visual_state()).get("label") or "状态表")

    def _update_refine_ui(self) -> None:
        self.digest_progress = max(0, min(100, self.digest_progress))
        self.refine_value.config(text=f"{self.digest_progress}%")
        self._set_pixel_bar(self.refine_bar, self.digest_progress, CYAN if self.digest_progress >= 100 else GOLD)
        self.digest_chip.config(text=f"{self.digest_progress}%")

    def _say(self, speech: str, event: str, color: str = GOOD) -> None:
        self.bubble.config(text=speech)
        self.status.config(text=event, fg=color)
        self._append_event(event)

    def _load_art_kit(self) -> tuple[dict, dict[str, dict], dict, dict]:
        try:
            manifest = json.loads(ART_MANIFEST_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            manifest = {}
        try:
            states_data = json.loads(ART_STATES_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            states_data = {}
        try:
            glyphs = json.loads(ART_GLYPHS_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            glyphs = {}
        try:
            anchors = json.loads(ART_ANCHORS_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            anchors = {}
        states = {
            str(item.get("id")): item
            for item in states_data.get("states", [])
            if isinstance(item, dict) and item.get("id")
        }
        return manifest, states, glyphs, anchors

    def _art_state(self, state: str) -> dict:
        return self.art_states.get(state, {})

    def _append_event(self, event: str) -> None:
        stamp = datetime.now().strftime("%H:%M")
        self.events.insert(0, f"{stamp} · {event}")
        self.events = self.events[:4]
        self.log.config(text="灵兽日志：\n" + "\n".join(self.events))

    def stage(self) -> int:
        score = self.feed_count * 2 + self.useful_count * 4 + (1 if self.plan_type not in {"读取中", "Demo"} else 0)
        if score >= 18:
            return 5
        if score >= 12:
            return 4
        if score >= 7:
            return 3
        if score >= 3:
            return 2
        return 1

    def stage_name(self) -> str:
        return ["幼体", "开灵", "筑基", "金丹", "化神"][self.stage() - 1]

    def _status_text(self) -> str:
        synced = datetime.now().strftime("%H:%M")
        if self.short_remaining < 20:
            mood = "短期灵脉告急，先收束任务"
        elif self.short_remaining < 45:
            mood = "灵气偏紧，适合小步炼化"
        else:
            mood = "灵脉平稳，适合继续修行"
        reset = self.last_reset_label or "回转时间未知"
        return f"{mood}\n同步 {synced} · {reset}"

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

    def _format_size(self, path: Path) -> str:
        try:
            size = path.stat().st_size
        except OSError:
            return "未知"
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / 1024 / 1024:.1f} MB"

    def _clamp_int(self, value: object, minimum: int, maximum: int) -> int:
        try:
            number = int(round(float(value or 0)))
        except (TypeError, ValueError):
            number = 0
        return max(minimum, min(maximum, number))

    def _load_local_state(self) -> None:
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        self.feed_count = self._clamp_int(data.get("feed_count"), 0, 9999)
        self.useful_count = self._clamp_int(data.get("useful_count"), 0, 9999)
        self.scroll_count = self._clamp_int(data.get("scroll_count"), 0, 9999)

    def _save_local_state(self) -> None:
        INBOX.mkdir(exist_ok=True)
        STATE_FILE.write_text(
            json.dumps(
                {
                    "feed_count": self.feed_count,
                    "useful_count": self.useful_count,
                    "scroll_count": self.scroll_count,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    SpiritDesktopPet().run()
