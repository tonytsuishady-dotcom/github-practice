from __future__ import annotations

import json
import re
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, ttk
from typing import Callable

from codex_usage import get_last_error, read_codex_rate_limits


ROOT = Path(__file__).resolve().parent
INBOX = ROOT / "pet-inbox"
STATE_FILE = INBOX / ".desktop-pet-state.json"
REFRESH_MS = 60_000
FRAME_MS = 140

INK = "#203d3a"
JADE = "#3aa0a0"
JADE_DARK = "#2c7f88"
CREAM = "#f7e7bd"
GOLD = "#c8b983"
CORAL = "#dd786f"
CYAN = "#6eddd7"
GOOD = "#1f8a70"
WARN = "#c9852e"
DANGER = "#c95757"


class SpiritDesktopPet:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Codex 灵兽桌宠")
        self.root.geometry("430x640+80+80")
        self.root.attributes("-topmost", True)
        self.root.resizable(False, False)
        self.root.configure(bg="#f8f6ef")

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

        self._load_local_state()
        self._build_ui()
        self._bind_drag()
        self.refresh()
        self._tick()

    def _build_ui(self) -> None:
        self.card = tk.Frame(self.root, bg="#fffaf0", highlightbackground=INK, highlightthickness=2)
        self.card.pack(fill="both", expand=True, padx=10, pady=10)

        header = tk.Frame(self.card, bg="#fffaf0")
        header.pack(fill="x", padx=12, pady=(10, 4))

        self.title = tk.Label(
            header,
            text="饕餮灵脉",
            bg="#fffaf0",
            fg=INK,
            font=("Microsoft YaHei UI", 16, "bold"),
        )
        self.title.pack(side="left")

        self._icon_button(header, "×", self.root.destroy).pack(side="right", padx=(4, 0))
        self._icon_button(header, "↻", self.refresh).pack(side="right")

        self.plan = tk.Label(
            self.card,
            text="正在同步 Codex 灵脉...",
            bg="#fffaf0",
            fg="#65707f",
            font=("Microsoft YaHei UI", 9),
        )
        self.plan.pack(anchor="w", padx=12)

        self.canvas = tk.Canvas(self.card, width=360, height=330, bg="#fffaf0", highlightthickness=0)
        self.canvas.pack(pady=(2, 0))
        self.canvas.bind("<Button-1>", self.pet)

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
        self.bubble.pack(fill="x", padx=12, pady=(0, 8))

        self.status = tk.Label(
            self.card,
            text="点击灵兽可以互动，投喂文件会生成本地玉简。",
            bg="#fffaf0",
            fg="#65707f",
            font=("Microsoft YaHei UI", 9),
            wraplength=328,
            justify="left",
        )
        self.status.pack(fill="x", padx=12, pady=(0, 8))

        self.short = self._meter("短期灵脉")
        self.week = self._meter("长期灵脉")

        actions = tk.Frame(self.card, bg="#fffaf0")
        actions.pack(fill="x", padx=12, pady=(10, 6))
        self._action_button(actions, "投喂灵材", self.feed_files).pack(side="left", expand=True, fill="x", padx=(0, 6))
        self._action_button(actions, "炼化成功", self.mark_useful).pack(side="left", expand=True, fill="x", padx=(6, 0))

        refine = tk.Frame(self.card, bg="#fffaf0")
        refine.pack(fill="x", padx=12, pady=(4, 6))
        refine_top = tk.Frame(refine, bg="#fffaf0")
        refine_top.pack(fill="x")
        tk.Label(refine_top, text="炼化炉", bg="#fffaf0", fg=INK, font=("Microsoft YaHei UI", 9, "bold")).pack(side="left")
        self.refine_value = tk.Label(refine_top, text="0%", bg="#fffaf0", fg=INK, font=("Microsoft YaHei UI", 9, "bold"))
        self.refine_value.pack(side="right")
        self.refine_bar = ttk.Progressbar(refine, maximum=100, mode="determinate")
        self.refine_bar.pack(fill="x", pady=(3, 0))

        self.progress = tk.Label(
            self.card,
            text="一代闭环：等待灵脉同步",
            bg="#fffaf0",
            fg=INK,
            font=("Microsoft YaHei UI", 9, "bold"),
        )
        self.progress.pack(fill="x", padx=12, pady=(2, 10))

        self.log = tk.Label(
            self.card,
            text="灵兽日志：等待第一份灵材。",
            bg="#fff7dc",
            fg="#65707f",
            font=("Microsoft YaHei UI", 8),
            wraplength=340,
            justify="left",
            padx=10,
            pady=8,
        )
        self.log.pack(fill="x", padx=12, pady=(0, 10))

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

    def _meter(self, label: str) -> dict[str, tk.Widget]:
        frame = tk.Frame(self.card, bg="#fffaf0")
        frame.pack(fill="x", padx=12, pady=(6, 0))

        top = tk.Frame(frame, bg="#fffaf0")
        top.pack(fill="x")
        name = tk.Label(top, text=label, bg="#fffaf0", fg=INK, font=("Microsoft YaHei UI", 9, "bold"))
        name.pack(side="left")
        value = tk.Label(top, text="--%", bg="#fffaf0", fg=INK, font=("Microsoft YaHei UI", 9, "bold"))
        value.pack(side="right")

        bar = ttk.Progressbar(frame, maximum=100, mode="determinate")
        bar.pack(fill="x", pady=(3, 0))
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

    def refresh(self) -> None:
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
        meter["bar"].config(value=value)

    def pet(self, _event: tk.Event | None = None) -> None:
        self.mode = "pet"
        self.mode_until = self.frame + 18
        self._say("饕餮蹭了蹭你：今日也要炼化成真正成果。", "摸摸灵兽，精神 +1。", GOOD)

    def feed_files(self) -> None:
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
        self.mode = "eat"
        self.mode_until = self.frame + 34
        self._say(
            f"咔嚓！收下 {saved} 份灵材，正在炼化成玉简。",
            f"投喂：{', '.join(names[:2])}{' 等' if len(names) > 2 else ''}",
            GOOD,
        )
        self._save_local_state()
        self._render_progress()
        self._update_refine_ui()

    def mark_useful(self) -> None:
        self.useful_count += 1
        self.digest_progress = 100
        self.mode = "shine"
        self.mode_until = self.frame + 42
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
        if self.mode != "idle" and self.frame > self.mode_until:
            self.mode = "idle"
        if self.mode == "eat" and self.digest_progress < 96:
            self.digest_progress = min(96, self.digest_progress + 1)
            self._update_refine_ui()
        elif self.mode == "shine" and self.frame % 3 == 0:
            self.digest_progress = max(0, self.digest_progress - 2)
            self._update_refine_ui()
        self._draw_pet()
        self.root.after(FRAME_MS, self._tick)

    def _draw_pet(self) -> None:
        self.canvas.delete("all")
        stage = self.stage()
        bob = 0 if self.mode == "eat" else (self.frame % 12 > 5) * -4
        if self.mode == "pet":
            bob -= 8
        x = 180
        y = 178 + bob
        scale = 1.15 + (stage - 1) * 0.13
        size = round(18 * scale)
        body_w = 7 * size
        body_h = 6 * size
        left = x - body_w // 2
        top = y - body_h // 2
        spirit_color = self._usage_color(self.short_remaining)
        belly = self._blend(CREAM, spirit_color, self.week_remaining / 100)

        self.canvas.create_rectangle(18, 18, 342, 300, fill="#fff6df", outline="#eadfca")
        self.canvas.create_rectangle(28, 28, 332, 290, fill="#fffaf0", outline="")

        aura_active = stage >= 3 or self.mode in {"eat", "shine", "pet"}
        if aura_active:
            pulse = 6 + (self.frame % 10) * 2
            color = CYAN if self.mode != "eat" else GOLD
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
        self._px(left - size + 4, top + size * 2 + 4, size - 4, size * 2 - 8, JADE_DARK)
        self._px(left + body_w, top + size * 2 + 4, size - 4, size * 2 - 8, JADE_DARK)
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

        self._px(left + size * 2, top + size * 4, size * 3, size * 2, INK)
        self._px(left + size * 2 + 4, top + size * 4 + 4, size * 3 - 8, size * 2 - 4, belly)
        self._px(x - size // 2, top + size * 5, size, size // 2, GOLD)
        self._px(x - size // 4, top + size * 5 + 4, size // 2, size // 2 - 4, CYAN if self.digest_progress > 70 else "#fff6d6")
        if self.digest_progress:
            orb_size = max(8, int(size * self.digest_progress / 100))
            self._px(x - orb_size // 2, top + size * 5 + size // 2, orb_size, orb_size, CYAN if self.mode == "shine" else GOLD)

        self._px(left + size * 2, top + size * 2, size // 2, size // 2, CORAL)
        self._px(left + size * 5 - size // 2, top + size * 2, size // 2, size // 2, CORAL)

        if self.mode == "eat":
            self._px(left + size * 2 - 4, top + size * 3 - 4, size * 3 + 8, size + 8, INK)
            self._px(left + size * 3, top + size * 4, size, size // 2, "#f3a0a9")
            self._px(left + size * 2 + 4, top + size * 3 - 4, size // 2, size // 2, "#ffffff")
            self._px(left + size * 4, top + size * 3 - 4, size // 2, size // 2, "#ffffff")
            item_y = top - 36 + (self.frame % 8) * 5
            self._px(x - 8, item_y, 16, 18, GOLD)
            self._px(x - 4, item_y + 4, 8, 8, "#ffffff")
        elif self.short_remaining < 20:
            self._px(left + size * 2, top + size * 2, size, 5, INK)
            self._px(left + size * 4, top + size * 2, size, 5, INK)
            self._px(left + size * 3, top + size * 3, size, 5, INK)
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

        if stage >= 5 or self.mode == "shine":
            self.canvas.create_arc(x - 112, top - 42, x + 112, top + 76, start=15, extent=150, style="arc", outline=GOLD, width=4)
            self._px(x - 6, top - 52, 12, 12, GOLD)

        self._px(left + size, top + body_h, size * 2, size, INK)
        self._px(left + size * 4, top + body_h, size * 2, size, INK)
        self._px(left + size + 4, top + body_h + 4, size * 2 - 8, size - 4, JADE_DARK)
        self._px(left + size * 4 + 4, top + body_h + 4, size * 2 - 8, size - 4, JADE_DARK)

        self.canvas.create_text(x, 304, text=f"{self.stage_name()} · 玉简 {self.scroll_count}", fill=INK, font=("Microsoft YaHei UI", 10, "bold"))

    def _px(self, x: int, y: int, width: int, height: int, fill: str) -> None:
        self.canvas.create_rectangle(x, y, x + width, y + height, fill=fill, outline="")

    def _shadow(self, x: int, y: int, width: int) -> None:
        self.canvas.create_oval(x - width // 2, y, x + width // 2, y + 16, fill="#d8c8a8", outline="")

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

    def _update_refine_ui(self) -> None:
        self.digest_progress = max(0, min(100, self.digest_progress))
        self.refine_value.config(text=f"{self.digest_progress}%")
        self.refine_bar.config(value=self.digest_progress)

    def _say(self, speech: str, event: str, color: str = GOOD) -> None:
        self.bubble.config(text=speech)
        self.status.config(text=event, fg=color)
        self._append_event(event)

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
