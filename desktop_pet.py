import json
import math
import random
import tkinter as tk
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


TRANSPARENT = "#ff00ff"
WIDTH = 180
HEIGHT = 160
GROUND_Y = 122
BASE_DIR = Path(__file__).resolve().parent
PROFILE_PATH = BASE_DIR / "pet_profile.json"
STATE_PATH = BASE_DIR / "pet_state.json"


DEFAULT_PROFILE: dict[str, Any] = {
    "name": "小墨",
    "species": "cat",
    "personality": {
        "traits": ["傲娇", "粘人", "喜欢陪你工作"],
        "energy_style": "normal",
        "talk_style": "short_teasing",
        "walk_chance": 0.32,
        "idle_talk_chance": 0.24,
    },
    "appearance": {
        "body": "#f8fafc",
        "belly": "#fef3c7",
        "outline": "#111827",
        "inner_ear": "#f9a8d4",
        "nose": "#f9a8d4",
        "eye": "#111827",
        "sleep_text": "#2563eb",
    },
    "lines": {
        "hello": ["你好", "终于想起我了？", "今天也要开始了吗"],
        "drag": ["放我去哪？", "别拎太久"],
        "drop": ["这里不错", "我会待着", "继续工作吧"],
        "feed": ["好吃", "再来一点", "能量回来了"],
        "pet": ["舒服", "嘿嘿", "哼，也不是不可以"],
        "walk": ["散步时间", "巡视领地"],
        "tired": ["走累了", "我要歇会儿"],
        "sleep": ["晚安", "别吵，我在省电"],
        "wake": ["醒啦", "发生什么了"],
        "hungry": ["有点饿", "我不是饿，是需要补给"],
        "low_energy": ["困了", "电量不足"],
        "idle": ["你忙你的", "我在旁边", "别忘了休息"],
    },
}


@dataclass
class Mood:
    hunger: int = 28
    energy: int = 78
    affection: int = 45


@dataclass
class PetState:
    hunger: int = 28
    energy: int = 78
    affection: int = 45
    x: int | None = None
    y: int | None = None
    last_seen: str = ""


def clamp(value: int, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, value))


def deep_merge(default: dict[str, Any], saved: dict[str, Any]) -> dict[str, Any]:
    merged = dict(default)
    for key, value in saved.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        write_json(path, default)
        return dict(default)

    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        backup = path.with_suffix(path.suffix + ".broken")
        path.replace(backup)
        write_json(path, default)
        return dict(default)

    if not isinstance(loaded, dict):
        return dict(default)
    return deep_merge(default, loaded)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def default_state() -> dict[str, Any]:
    return asdict(PetState(last_seen=datetime.now().isoformat(timespec="seconds")))


class DesktopPet:
    def __init__(self) -> None:
        self.profile = read_json(PROFILE_PATH, DEFAULT_PROFILE)
        self.state = read_json(STATE_PATH, default_state())

        self.root = tk.Tk()
        self.root.title(self.profile.get("name", "桌面宠物"))
        self.root.overrideredirect(True)
        self.root.wm_attributes("-topmost", True)
        self.root.configure(bg=TRANSPARENT)

        try:
            self.root.wm_attributes("-transparentcolor", TRANSPARENT)
        except tk.TclError:
            pass

        self.canvas = tk.Canvas(
            self.root,
            width=WIDTH,
            height=HEIGHT,
            bg=TRANSPARENT,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack()

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        default_x = max(40, screen_w - WIDTH - 80)
        default_y = max(40, screen_h - HEIGHT - 80)
        self.x = int(self.state.get("x") if self.state.get("x") is not None else default_x)
        self.y = int(self.state.get("y") if self.state.get("y") is not None else default_y)
        self.x = max(0, min(screen_w - WIDTH, self.x))
        self.y = max(0, min(screen_h - HEIGHT, self.y))
        self.root.geometry(f"{WIDTH}x{HEIGHT}+{self.x}+{self.y}")

        self.mood = Mood(
            hunger=clamp(int(self.state.get("hunger", 28))),
            energy=clamp(int(self.state.get("energy", 78))),
            affection=clamp(int(self.state.get("affection", 45))),
        )
        self.apply_offline_progress()

        self.mode = "idle"
        self.direction = -1
        self.tick = 0
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        self.dragging = False
        self.message = self.line("hello")
        self.message_until = 140
        self.walk_until = 0

        self.menu = tk.Menu(self.root, tearoff=False)
        self.menu.add_command(label="喂它", command=self.feed)
        self.menu.add_command(label="摸摸头", command=self.pet)
        self.menu.add_command(label="让它散步", command=self.walk)
        self.menu.add_command(label="睡觉 / 醒来", command=self.toggle_sleep)
        self.menu.add_separator()
        self.menu.add_command(label="保存", command=self.save_state)
        self.menu.add_command(label="退出", command=self.close)

        self.root.bind("<ButtonPress-1>", self.start_drag)
        self.root.bind("<B1-Motion>", self.on_drag)
        self.root.bind("<ButtonRelease-1>", self.stop_drag)
        self.root.bind("<Double-Button-1>", lambda _event: self.pet())
        self.root.bind("<Button-3>", self.show_menu)
        self.root.bind("<Escape>", lambda _event: self.close())
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def run(self) -> None:
        self.animate()
        self.root.mainloop()

    @property
    def appearance(self) -> dict[str, str]:
        return self.profile.get("appearance", {})

    @property
    def personality(self) -> dict[str, Any]:
        return self.profile.get("personality", {})

    def color(self, key: str, fallback: str) -> str:
        return str(self.appearance.get(key, fallback))

    def line(self, key: str) -> str:
        lines = self.profile.get("lines", {})
        choices = lines.get(key) if isinstance(lines, dict) else None
        if isinstance(choices, list) and choices:
            return str(random.choice(choices))
        fallback = DEFAULT_PROFILE["lines"].get(key, ["..."])
        return str(random.choice(fallback))

    def apply_offline_progress(self) -> None:
        last_seen = self.state.get("last_seen")
        if not last_seen:
            return

        try:
            then = datetime.fromisoformat(str(last_seen))
        except ValueError:
            return

        minutes = max(0, int((datetime.now() - then).total_seconds() // 60))
        if minutes < 5:
            return

        self.mood.hunger = clamp(self.mood.hunger + min(35, minutes // 12))
        self.mood.energy = clamp(self.mood.energy + min(45, minutes // 8))

    def save_state(self) -> None:
        data = {
            "hunger": self.mood.hunger,
            "energy": self.mood.energy,
            "affection": self.mood.affection,
            "x": self.x,
            "y": self.y,
            "last_seen": datetime.now().isoformat(timespec="seconds"),
        }
        write_json(STATE_PATH, data)
        self.state = data

    def close(self) -> None:
        self.save_state()
        self.root.destroy()

    def start_drag(self, event: tk.Event) -> None:
        self.dragging = True
        self.drag_offset_x = event.x
        self.drag_offset_y = event.y
        self.say(self.line("drag"), 70)

    def on_drag(self, event: tk.Event) -> None:
        self.x = self.root.winfo_pointerx() - self.drag_offset_x
        self.y = self.root.winfo_pointery() - self.drag_offset_y
        self.root.geometry(f"+{self.x}+{self.y}")

    def stop_drag(self, _event: tk.Event) -> None:
        self.dragging = False
        self.say(self.line("drop"), 90)
        self.save_state()

    def show_menu(self, event: tk.Event) -> None:
        self.menu.tk_popup(event.x_root, event.y_root)

    def say(self, text: str, duration: int = 100) -> None:
        self.message = text
        self.message_until = self.tick + duration

    def feed(self) -> None:
        self.mood.hunger = clamp(self.mood.hunger - 28)
        self.mood.affection = clamp(self.mood.affection + 8)
        self.mode = "eat"
        self.say(self.line("feed"), 110)
        self.save_state()

    def pet(self) -> None:
        self.mood.affection = clamp(self.mood.affection + 12)
        self.mood.energy = clamp(self.mood.energy + 3)
        self.mode = "happy"
        self.say(self.line("pet"), 105)
        self.save_state()

    def walk(self) -> None:
        self.mode = "walk"
        self.walk_until = self.tick + 260
        self.say(self.line("walk"), 95)

    def toggle_sleep(self) -> None:
        if self.mode == "sleep":
            self.mode = "idle"
            self.say(self.line("wake"), 90)
        else:
            self.mode = "sleep"
            self.say(self.line("sleep"), 80)
        self.save_state()

    def update_state(self) -> None:
        if self.dragging:
            return

        energy_style = self.personality.get("energy_style", "normal")
        energy_cost = 1 if energy_style == "lazy" else 3 if energy_style == "active" else 2

        if self.tick % 180 == 0:
            self.mood.hunger = clamp(self.mood.hunger + 4)
            self.mood.energy = clamp(self.mood.energy - energy_cost)
            self.save_state()

        if self.mode == "sleep":
            if self.tick % 60 == 0:
                self.mood.energy = clamp(self.mood.energy + 4)
            return

        if self.mode in {"eat", "happy"} and self.tick % 95 == 0:
            self.mode = "idle"

        if self.mode == "walk":
            if self.tick > self.walk_until:
                self.mode = "idle"
                self.say(self.line("tired"), 85)
                self.save_state()
                return
            self.move_pet()
            return

        if self.mood.energy < 16:
            self.mode = "sleep"
            self.say(self.line("low_energy"), 100)
            return

        if self.mood.hunger > 78 and self.tick % 220 == 0:
            self.say(self.line("hungry"), 120)

        idle_talk_chance = float(self.personality.get("idle_talk_chance", 0.2))
        if self.tick % 360 == 0 and random.random() < idle_talk_chance:
            self.say(self.line("idle"), 105)

        walk_chance = float(self.personality.get("walk_chance", 0.32))
        if self.tick % 260 == 0:
            self.mode = "walk" if random.random() < walk_chance else "idle"
            if self.mode == "walk":
                self.walk_until = self.tick + random.randint(120, 240)

        if self.mode == "walk":
            self.move_pet()

    def move_pet(self) -> None:
        screen_w = self.root.winfo_screenwidth()
        step = 2 * self.direction
        self.x += step
        if self.x < 10:
            self.x = 10
            self.direction = 1
        elif self.x > screen_w - WIDTH - 10:
            self.x = screen_w - WIDTH - 10
            self.direction = -1
        self.root.geometry(f"+{self.x}+{self.y}")

    def draw(self) -> None:
        self.canvas.delete("all")
        bob = math.sin(self.tick / 8) * (3 if self.mode != "sleep" else 1)
        blink = self.tick % 95 in (0, 1, 2, 3)
        walk_swing = math.sin(self.tick / 5) if self.mode == "walk" else 0
        happy = self.mode == "happy"
        sleeping = self.mode == "sleep"

        self.draw_shadow()
        self.draw_body(90, GROUND_Y + bob, walk_swing)
        self.draw_head(90, 68 + bob, blink, happy, sleeping)
        self.draw_status()
        if self.tick < self.message_until:
            self.draw_bubble(self.message)

    def draw_shadow(self) -> None:
        self.canvas.create_oval(46, 128, 134, 144, fill="#4b5563", outline="", stipple="gray50")

    def draw_body(self, cx: int, cy: float, walk_swing: float) -> None:
        body = self.color("body", "#f8fafc")
        belly = self.color("belly", "#fef3c7")
        outline = self.color("outline", "#111827")
        self.canvas.create_oval(cx - 42, cy - 48, cx + 42, cy + 12, fill=body, outline=outline, width=3)
        self.canvas.create_oval(cx - 26, cy - 34, cx + 26, cy + 9, fill=belly, outline="")

        tail_x = cx + 39 * self.direction
        tail_end = tail_x + 26 * self.direction
        self.canvas.create_line(tail_x, cy - 27, tail_end, cy - 45 + walk_swing * 8, fill=outline, width=7, capstyle=tk.ROUND)
        self.canvas.create_line(tail_x, cy - 27, tail_end, cy - 45 + walk_swing * 8, fill=body, width=4, capstyle=tk.ROUND)

        for side in (-1, 1):
            foot_x = cx + side * 20
            lift = abs(walk_swing) * 6 if side == self.direction else 0
            self.canvas.create_oval(foot_x - 14, cy - 1 - lift, foot_x + 14, cy + 15 - lift, fill=outline, outline="")
            self.canvas.create_oval(foot_x - 10, cy - 4 - lift, foot_x + 10, cy + 9 - lift, fill=body, outline="")

    def draw_head(self, cx: int, cy: float, blink: bool, happy: bool, sleeping: bool) -> None:
        body = self.color("body", "#f8fafc")
        outline = self.color("outline", "#111827")
        inner_ear = self.color("inner_ear", "#f9a8d4")
        nose = self.color("nose", "#f9a8d4")
        eye = self.color("eye", "#111827")

        self.canvas.create_polygon(cx - 39, cy - 17, cx - 26, cy - 51, cx - 8, cy - 22, fill=body, outline=outline, width=3)
        self.canvas.create_polygon(cx + 39, cy - 17, cx + 26, cy - 51, cx + 8, cy - 22, fill=body, outline=outline, width=3)
        self.canvas.create_polygon(cx - 29, cy - 23, cx - 24, cy - 38, cx - 17, cy - 25, fill=inner_ear, outline="")
        self.canvas.create_polygon(cx + 29, cy - 23, cx + 24, cy - 38, cx + 17, cy - 25, fill=inner_ear, outline="")

        self.canvas.create_oval(cx - 42, cy - 38, cx + 42, cy + 33, fill=body, outline=outline, width=3)
        self.canvas.create_oval(cx - 12, cy - 4, cx + 12, cy + 11, fill=nose, outline=outline, width=2)

        if sleeping:
            self.canvas.create_line(cx - 24, cy - 8, cx - 9, cy - 8, fill=outline, width=3, capstyle=tk.ROUND)
            self.canvas.create_line(cx + 9, cy - 8, cx + 24, cy - 8, fill=outline, width=3, capstyle=tk.ROUND)
            self.canvas.create_text(cx + 47, cy - 43, text="Z", fill=self.color("sleep_text", "#2563eb"), font=("Segoe UI", 15, "bold"))
            self.canvas.create_text(cx + 61, cy - 56, text="z", fill=self.color("sleep_text", "#2563eb"), font=("Segoe UI", 11, "bold"))
        elif happy:
            self.canvas.create_arc(cx - 27, cy - 15, cx - 8, cy + 7, start=15, extent=150, style=tk.ARC, outline=outline, width=3)
            self.canvas.create_arc(cx + 8, cy - 15, cx + 27, cy + 7, start=15, extent=150, style=tk.ARC, outline=outline, width=3)
            self.canvas.create_text(cx, cy + 20, text="w", fill=outline, font=("Segoe UI", 12, "bold"))
        elif blink:
            self.canvas.create_line(cx - 25, cy - 8, cx - 11, cy - 8, fill=outline, width=3, capstyle=tk.ROUND)
            self.canvas.create_line(cx + 11, cy - 8, cx + 25, cy - 8, fill=outline, width=3, capstyle=tk.ROUND)
        else:
            self.canvas.create_oval(cx - 26, cy - 17, cx - 10, cy, fill=eye, outline="")
            self.canvas.create_oval(cx + 10, cy - 17, cx + 26, cy, fill=eye, outline="")
            self.canvas.create_oval(cx - 20, cy - 13, cx - 16, cy - 9, fill="#ffffff", outline="")
            self.canvas.create_oval(cx + 16, cy - 13, cx + 20, cy - 9, fill="#ffffff", outline="")

        self.canvas.create_line(cx - 34, cy + 8, cx - 56, cy + 1, fill=outline, width=2)
        self.canvas.create_line(cx - 34, cy + 15, cx - 58, cy + 15, fill=outline, width=2)
        self.canvas.create_line(cx + 34, cy + 8, cx + 56, cy + 1, fill=outline, width=2)
        self.canvas.create_line(cx + 34, cy + 15, cx + 58, cy + 15, fill=outline, width=2)

    def draw_status(self) -> None:
        items = [
            ("饱", 100 - self.mood.hunger, "#10b981"),
            ("能", self.mood.energy, "#3b82f6"),
            ("亲", self.mood.affection, "#ec4899"),
        ]
        x = 16
        for label, value, color in items:
            self.canvas.create_text(x, 150, text=label, fill="#111827", font=("Microsoft YaHei UI", 8, "bold"))
            self.canvas.create_rectangle(x + 13, 146, x + 45, 153, fill="#e5e7eb", outline="#111827")
            self.canvas.create_rectangle(x + 14, 147, x + 14 + int(value * 0.3), 152, fill=color, outline="")
            x += 54

    def draw_bubble(self, text: str) -> None:
        text_width = min(112, max(44, len(text) * 14 + 22))
        left = int((WIDTH - text_width) / 2)
        right = left + text_width
        self.canvas.create_oval(left, 4, left + 18, 28, fill="#ffffff", outline="#111827", width=2)
        self.canvas.create_oval(right - 18, 4, right, 28, fill="#ffffff", outline="#111827", width=2)
        self.canvas.create_rectangle(left + 9, 4, right - 9, 28, fill="#ffffff", outline="")
        self.canvas.create_line(left + 9, 4, right - 9, 4, fill="#111827", width=2)
        self.canvas.create_line(left + 9, 28, right - 9, 28, fill="#111827", width=2)
        self.canvas.create_text(WIDTH / 2, 16, text=text, fill="#111827", font=("Microsoft YaHei UI", 9, "bold"))

    def animate(self) -> None:
        self.tick += 1
        self.update_state()
        self.draw()
        self.root.after(33, self.animate)


if __name__ == "__main__":
    DesktopPet().run()
