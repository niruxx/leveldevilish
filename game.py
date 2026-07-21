import json
import math
import os
import random
import tkinter as tk

# Logical/physics space the game is designed and simulated in. The on-screen
# window can be resized freely; everything is scaled + letterboxed to fit.
WIDTH = 1920
HEIGHT = 1080

# Levels are authored in this smaller design space, then scaled up to
# WIDTH x HEIGHT by scale_level_data(). Keeps level coordinates readable.
BASE_WIDTH = 900
BASE_HEIGHT = 550

PLAYER_W = 34
PLAYER_H = 78
GRAVITY = 0.9
JUMP_FORCE = 24
MOVE_SPEED = 8.5

SAVE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "savegame.json")

# ---------------------------------------------------------------------------
# Design system / palette
# ---------------------------------------------------------------------------

MENU_BG_TOP = "#070a18"
MENU_BG_BOTTOM = "#1c1544"
PLAY_BG_TOP = "#03040c"
PLAY_BG_BOTTOM = "#10142c"

SURFACE = "#141a30"
SURFACE_ALT = "#1c2444"
SURFACE_LIGHT = "#2c3560"
BORDER = "#333e6e"
BORDER_SOFT = "#1c2340"

ACCENT = "#818cf8"
ACCENT_STRONG = "#6366f1"
SUCCESS = "#34d399"
DANGER = "#f87171"
DANGER_DARK = "#7f1d1d"
WARNING = "#fbbf24"

TEXT_PRIMARY = "#f8fafc"
TEXT_MUTED = "#a8b3d6"
TEXT_DIM = "#6d7699"
BADGE_TEXT = "#0b1224"

PLAYER_SKIN = "#f59e0b"
PLAYER_SKIN_DARK = "#b45309"
PLAYER_OUTLINE = "#fde68a"
PARTICLE_COLOR = "#39407a"
SHADOW_COLOR = "#02030a"


def lerp_color(c1, c2, t):
    t = max(0.0, min(1.0, t))
    r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
    r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
    r = round(r1 + (r2 - r1) * t)
    g = round(g1 + (g2 - g1) * t)
    b = round(b1 + (b2 - b1) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


def load_progress(total_levels):
    try:
        with open(SAVE_PATH, "r") as f:
            data = json.load(f)
        unlocked = int(data.get("unlocked", 1))
    except Exception:
        unlocked = 1
    return max(1, min(unlocked, total_levels))


def save_progress(unlocked):
    try:
        with open(SAVE_PATH, "w") as f:
            json.dump({"unlocked": unlocked}, f)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Level-building helpers (all in BASE_WIDTH x BASE_HEIGHT design space)
# ---------------------------------------------------------------------------

def plat(x, y, w, h, ptype="solid", **kw):
    d = {"x": x, "y": y, "w": w, "h": h, "type": ptype}
    if ptype == "crumble":
        d["delay"] = kw.get("delay", 16)
        d["timer"] = 0
        d["state"] = "idle"
    elif ptype == "blink":
        d["period"] = kw.get("period", 80)
        d["on_ratio"] = kw.get("on_ratio", 0.55)
        d["offset"] = kw.get("offset", 0)
    return d


def hazard(x, y, w=24, h=24):
    return {"x": x, "y": y, "w": w, "h": h}


def mover(x, y, w, h, direction, speed, min_x, max_x):
    return {"x": x, "y": y, "w": w, "h": h, "dir": direction, "speed": speed, "min": min_x, "max": max_x}


def dart(trigger_x, start_x, direction, speed, y, w=20, h=16):
    return {
        "trigger_x": trigger_x, "start_x": start_x, "dir": direction, "speed": speed,
        "y": y, "w": w, "h": h, "fired": False, "arrow_x": None,
    }


def sign(x, y, text):
    return {"x": x, "y": y, "text": text}


def scale_level_data(data):
    """Scale a level authored in BASE_WIDTH x BASE_HEIGHT up to WIDTH x HEIGHT."""
    sx = WIDTH / BASE_WIDTH
    sy = HEIGHT / BASE_HEIGHT

    def scale_rect(d):
        nd = dict(d)
        nd["x"] = d["x"] * sx
        nd["y"] = d["y"] * sy
        nd["w"] = d["w"] * sx
        nd["h"] = d["h"] * sy
        return nd

    platforms = [scale_rect(p) for p in data["platforms"]]
    hazards = [scale_rect(h) for h in data["hazards"]]

    movers = []
    for m in data["movers"]:
        nm = scale_rect(m)
        nm["speed"] = m["speed"] * sx
        nm["min"] = m["min"] * sx
        nm["max"] = m["max"] * sx
        movers.append(nm)

    dart_traps = []
    for d in data["dart_traps"]:
        dart_traps.append({
            "trigger_x": d["trigger_x"] * sx,
            "start_x": d["start_x"] * sx,
            "dir": d["dir"],
            "speed": d["speed"] * sx,
            "y": d["y"] * sy,
            "w": d["w"] * sx,
            "h": d["h"] * sy,
            "fired": False,
            "arrow_x": None,
        })

    fake_goals = [scale_rect(fg) for fg in data["fake_goals"]]
    goal = scale_rect(data["goal"])
    signs = [{"x": s["x"] * sx, "y": s["y"] * sy, "text": s["text"]} for s in data["signs"]]

    return {
        "platforms": platforms, "hazards": hazards, "movers": movers,
        "dart_traps": dart_traps, "fake_goals": fake_goals, "goal": goal, "signs": signs,
    }


def build_level1():
    return {
        "platforms": [
            plat(0, 510, 900, 40),
            plat(150, 460, 110, 18),
            plat(340, 410, 130, 18, "crumble", delay=20),
            plat(540, 360, 130, 18),
            plat(720, 300, 130, 18),
        ],
        "hazards": [hazard(245, 452), hazard(470, 392), hazard(660, 342)],
        "movers": [],
        "dart_traps": [],
        "fake_goals": [],
        "goal": {"x": 760, "y": 256, "w": 34, "h": 44},
        "signs": [sign(300, 388, "WARNING: CRUMBLES FAST")],
    }


def build_level2():
    return {
        "platforms": [
            plat(0, 510, 900, 40),
            plat(150, 460, 110, 18),
            plat(330, 410, 120, 18, "blink", period=90, on_ratio=0.55, offset=0),
            plat(510, 360, 120, 18, "blink", period=70, on_ratio=0.5, offset=35),
            plat(690, 310, 130, 18),
            plat(620, 250, 110, 18),
        ],
        "hazards": [hazard(250, 452), hazard(470, 392), hazard(630, 302)],
        "movers": [],
        "dart_traps": [],
        "fake_goals": [],
        "goal": {"x": 650, "y": 206, "w": 34, "h": 44},
        "signs": [sign(260, 430, "THEY DON'T STAY SOLID...")],
    }


def build_level3():
    return {
        "platforms": [
            plat(0, 510, 900, 40),
            plat(150, 460, 110, 18),
            plat(330, 410, 120, 18, "crumble", delay=6),
            plat(520, 360, 130, 18),
            plat(700, 300, 130, 18),
        ],
        "hazards": [hazard(470, 392), hazard(640, 342)],
        "movers": [],
        "dart_traps": [],
        "fake_goals": [{"x": 365, "y": 330, "w": 34, "h": 44}],
        "goal": {"x": 730, "y": 256, "w": 34, "h": 44},
        "signs": [
            sign(260, 440, "SAFE! JUMP HERE ->"),
            sign(700, 264, "(the OTHER portal is real...)"),
        ],
    }


def build_level4():
    return {
        "platforms": [
            plat(0, 510, 900, 40),
            plat(400, 430, 120, 18),
            plat(620, 350, 130, 18),
        ],
        "hazards": [hazard(330, 486)],
        "movers": [],
        "dart_traps": [
            dart(250, BASE_WIDTH + 60, -1, 9, 478, 20, 20),
            dart(470, BASE_WIDTH + 60, -1, 11, 398, 20, 20),
            dart(600, -60, 1, 10, 328, 20, 20),
        ],
        "fake_goals": [],
        "goal": {"x": 655, "y": 306, "w": 34, "h": 44},
        "signs": [sign(150, 460, "WATCH THE CORRIDOR...")],
    }


def build_level5():
    return {
        "platforms": [
            plat(0, 510, 900, 40),
            plat(150, 460, 110, 18),
            plat(330, 410, 120, 18),
            plat(520, 360, 130, 18, "blink", period=75, on_ratio=0.55, offset=10),
            plat(705, 300, 120, 18),
            plat(560, 230, 110, 18),
        ],
        "hazards": [hazard(470, 392), hazard(650, 270)],
        "movers": [
            mover(330, 382, 24, 24, 1, 2.4, 300, 430),
            mover(600, 200, 20, 20, -1, 2.0, 540, 680),
        ],
        "dart_traps": [],
        "fake_goals": [],
        "goal": {"x": 590, "y": 186, "w": 34, "h": 44},
        "signs": [sign(260, 420, "SAWS DON'T BLINK. FLOORS DO.")],
    }


def build_level6():
    """Chaos Gauntlet: regenerated at random every attempt."""
    rng = random.Random()
    slots = [(150, 460, 110), (340, 405, 120), (530, 355, 130), (715, 300, 120)]

    platforms = [plat(0, 510, 900, 40)]
    hazards = []
    prev_x_end, prev_y = 0, 510

    for sx, sy, sw in slots:
        y = sy + rng.randint(-10, 10)
        ptype = rng.choice(["solid", "solid", "crumble", "blink"])
        if ptype == "crumble":
            p = plat(sx, y, sw, 18, "crumble", delay=rng.randint(10, 22))
        elif ptype == "blink":
            p = plat(sx, y, sw, 18, "blink", period=rng.randint(60, 100),
                      on_ratio=rng.uniform(0.45, 0.65), offset=rng.randint(0, 40))
        else:
            p = plat(sx, y, sw, 18, "solid")
        platforms.append(p)

        if rng.random() < 0.65:
            gap_x = (prev_x_end + sx) // 2
            hazards.append(hazard(gap_x, max(prev_y, y) - 24))

        prev_x_end, prev_y = sx + sw, y

    movers = []
    if rng.random() < 0.5:
        i = rng.randint(0, len(slots) - 2)
        x0 = slots[i][0]
        x1 = slots[i + 1][0] + slots[i + 1][2]
        movers.append(mover((x0 + x1) // 2, rng.randint(220, 420), 22, 22,
                             rng.choice([1, -1]), rng.uniform(1.8, 2.8), x0, x1))

    dart_traps = []
    if rng.random() < 0.5:
        tx = rng.randint(250, 650)
        direction = rng.choice([1, -1])
        start_x = -60 if direction == 1 else BASE_WIDTH + 60
        dart_traps.append(dart(tx, start_x, direction, rng.uniform(8, 13), rng.randint(360, 480)))

    fake_goals = []
    if rng.random() < 0.4:
        i = rng.randint(1, len(slots) - 1)
        sx, sy, sw = slots[i]
        fake_goals.append({"x": sx + sw // 2 - 17, "y": sy - 70, "w": 34, "h": 44})

    last = platforms[-1]
    goal = {"x": last["x"] + last["w"] // 2 - 17, "y": last["y"] - 44, "w": 34, "h": 44}

    taunts = [
        "GOOD LUCK.", "NOTHING HERE IS WHAT IT SEEMS.", "TRUST NOTHING.",
        "DIFFERENT EVERY TIME.", "YOU WON'T MEMORIZE THIS ONE.",
    ]
    signs = [sign(BASE_WIDTH // 2, 120, rng.choice(taunts))]

    return {
        "platforms": platforms,
        "hazards": hazards,
        "movers": movers,
        "dart_traps": dart_traps,
        "fake_goals": fake_goals,
        "goal": goal,
        "signs": signs,
    }


LEVEL_DEFS = [
    {"name": "First Steps", "build": build_level1},
    {"name": "Blink and You Fall", "build": build_level2},
    {"name": "Trust Issues", "build": build_level3},
    {"name": "Dart Corridor", "build": build_level4},
    {"name": "Saw Gauntlet", "build": build_level5},
    {"name": "Chaos Gauntlet", "build": build_level6},
]


class DevilishPlatformer:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Level Devil-ish")
        self.root.resizable(True, True)
        self.root.minsize(640, 400)

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        pos_x = max(0, (screen_w - WIDTH) // 2)
        pos_y = max(0, (screen_h - HEIGHT) // 2)
        self.root.geometry(f"{WIDTH}x{HEIGHT}+{pos_x}+{pos_y}")

        self.canvas = tk.Canvas(self.root, width=WIDTH, height=HEIGHT, bg="#03040c", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.keys = {"left": False, "right": False, "jump": False}
        self.root.bind("<KeyPress>", self.on_key_press)
        self.root.bind("<KeyRelease>", self.on_key_release)
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<Configure>", self.on_resize)

        self.LEVELS = LEVEL_DEFS
        self.select_cols = 3

        self.state = "menu"
        self.player_x = 100
        self.player_y = 200
        self.vx = 0
        self.vy = 0
        self.on_ground = False
        self.facing = 1
        self.score = 0
        self.deaths = 0
        self.frame_count = 0

        self.platforms = []
        self.hazards = []
        self.movers = []
        self.dart_traps = []
        self.fake_goals = []
        self.signs = []
        self.goal = {"x": 0, "y": 0, "w": 0, "h": 0}

        self.current_level_index = 0
        self.select_index = 0
        self.lose_reason = ""
        self.unlocked = load_progress(len(self.LEVELS))

        self._scale = 1.0
        self._ox = 0.0
        self._oy = 0.0
        self._cw = WIDTH
        self._ch = HEIGHT
        self._gradient_cache = {}

        self.particles = [
            {
                "x": random.uniform(0, WIDTH),
                "y": random.uniform(0, HEIGHT),
                "r": random.uniform(2, 5),
                "vx": random.uniform(-0.15, 0.15),
                "vy": random.uniform(0.05, 0.25),
            }
            for _ in range(28)
        ]

        self.root.update_idletasks()
        self.draw_menu()
        self.root.after(50, self.ambient_tick)
        self.root.mainloop()

    # -- view transform (lets the logical WIDTH x HEIGHT playfield scale to
    #    whatever size the window actually is, letterboxed to keep aspect) --

    def update_transform(self):
        cw = max(1, self.canvas.winfo_width())
        ch = max(1, self.canvas.winfo_height())
        self._cw, self._ch = cw, ch
        self._scale = min(cw / WIDTH, ch / HEIGHT)
        self._ox = (cw - WIDTH * self._scale) / 2
        self._oy = (ch - HEIGHT * self._scale) / 2

    def L(self, x, y):
        return self._ox + x * self._scale, self._oy + y * self._scale

    def rect(self, x0, y0, x1, y1, **kw):
        sx0, sy0 = self.L(x0, y0)
        sx1, sy1 = self.L(x1, y1)
        if "width" in kw:
            kw["width"] = max(1, kw["width"] * self._scale)
        return self.canvas.create_rectangle(sx0, sy0, sx1, sy1, **kw)

    def oval(self, x0, y0, x1, y1, **kw):
        sx0, sy0 = self.L(x0, y0)
        sx1, sy1 = self.L(x1, y1)
        if "width" in kw:
            kw["width"] = max(1, kw["width"] * self._scale)
        return self.canvas.create_oval(sx0, sy0, sx1, sy1, **kw)

    def line(self, coords, **kw):
        pts = []
        for i in range(0, len(coords), 2):
            px, py = self.L(coords[i], coords[i + 1])
            pts += [px, py]
        if "width" in kw:
            kw["width"] = max(1, kw["width"] * self._scale)
        return self.canvas.create_line(*pts, **kw)

    def poly(self, coords, **kw):
        pts = []
        for i in range(0, len(coords), 2):
            px, py = self.L(coords[i], coords[i + 1])
            pts += [px, py]
        if "width" in kw:
            kw["width"] = max(1, kw["width"] * self._scale)
        return self.canvas.create_polygon(*pts, **kw)

    def rrect(self, x0, y0, x1, y1, r=12, **kw):
        r = max(0, min(r, (x1 - x0) / 2, (y1 - y0) / 2))
        pts = [
            x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r,
            x1, y1 - r, x1, y1, x1 - r, y1, x0 + r, y1,
            x0, y1, x0, y1 - r, x0, y0 + r, x0, y0,
        ]
        kw.setdefault("smooth", True)
        kw.setdefault("fill", "")
        return self.poly(pts, **kw)

    def pill(self, x0, y0, x1, y1, **kw):
        return self.rrect(x0, y0, x1, y1, r=(y1 - y0) / 2, **kw)

    def text(self, x, y, **kw):
        px, py = self.L(x, y)
        font = kw.get("font")
        if font:
            size = max(6, int(font[1] * self._scale))
            kw["font"] = (font[0], size) + tuple(font[2:])
        return self.canvas.create_text(px, py, **kw)

    def to_logical(self, ex, ey):
        self.update_transform()
        return (ex - self._ox) / self._scale, (ey - self._oy) / self._scale

    # -- background + ambience -----------------------------------------

    def get_gradient_image(self, w, h, top, bottom, key):
        w, h = max(1, w), max(1, h)
        cached = self._gradient_cache.get(key)
        if cached and cached[0] == (w, h):
            return cached[1]
        img = tk.PhotoImage(width=w, height=h)
        steps = max(2, min(h, 64))
        for i in range(steps):
            t0 = i / steps
            t1 = (i + 1) / steps
            color = lerp_color(top, bottom, (t0 + t1) / 2)
            y0 = int(h * t0)
            y1 = h if i == steps - 1 else int(h * t1)
            if y1 <= y0:
                y1 = y0 + 1
            img.put(color, to=(0, y0, w, y1))
        self._gradient_cache[key] = ((w, h), img)
        return img

    def draw_bg(self, top, bottom, key):
        img = self.get_gradient_image(self._cw, self._ch, top, bottom, key)
        self._bg_ref = img
        self.canvas.create_image(0, 0, anchor="nw", image=img)

    def draw_particles(self):
        for p in self.particles:
            r = p["r"]
            self.oval(p["x"] - r, p["y"] - r, p["x"] + r, p["y"] + r, fill=PARTICLE_COLOR, outline="")

    def ambient_tick(self):
        if self.state in ("menu", "select"):
            for p in self.particles:
                p["x"] += p["vx"]
                p["y"] += p["vy"]
                if p["x"] < -10:
                    p["x"] = WIDTH + 10
                if p["x"] > WIDTH + 10:
                    p["x"] = -10
                if p["y"] < -10:
                    p["y"] = HEIGHT + 10
                if p["y"] > HEIGHT + 10:
                    p["y"] = -10
            self.render_current()
        self.root.after(50, self.ambient_tick)

    # -- input -------------------------------------------------------

    def on_resize(self, _event):
        self.render_current()

    def render_current(self):
        if self.state == "menu":
            self.draw_menu()
        elif self.state == "select":
            self.draw_select()
        else:
            self.draw_frame()

    def on_key_press(self, event):
        key = event.keysym.lower()
        if key in ("left", "a"):
            self.keys["left"] = True
        elif key in ("right", "d"):
            self.keys["right"] = True
        elif key in ("up", "w", "space"):
            self.keys["jump"] = True

        if self.state == "menu":
            if key in ("return", "space", "up", "w"):
                self.state = "select"
                self.draw_select()
        elif self.state == "select":
            self.handle_select_key(key)
        elif self.state == "playing":
            if key == "escape":
                self.state = "select"
                self.draw_select()
        elif self.state == "lost":
            if key in ("return", "space"):
                self.start_level(self.current_level_index)
            elif key == "escape":
                self.state = "select"
                self.draw_select()
        elif self.state == "won":
            if key in ("return", "space"):
                self.start_level(self.current_level_index + 1)
            elif key == "escape":
                self.state = "select"
                self.draw_select()
        elif self.state == "complete":
            if key in ("return", "space", "escape"):
                self.state = "select"
                self.draw_select()

    def on_key_release(self, event):
        key = event.keysym.lower()
        if key in ("left", "a"):
            self.keys["left"] = False
        elif key in ("right", "d"):
            self.keys["right"] = False
        elif key in ("up", "w", "space"):
            self.keys["jump"] = False

    def handle_select_key(self, key):
        cols = self.select_cols
        n = len(self.LEVELS)
        if key in ("left", "a"):
            if self.select_index % cols != 0:
                self.select_index -= 1
        elif key in ("right", "d"):
            if self.select_index % cols != cols - 1 and self.select_index + 1 < n:
                self.select_index += 1
        elif key in ("up", "w"):
            if self.select_index - cols >= 0:
                self.select_index -= cols
        elif key in ("down", "s"):
            if self.select_index + cols < n:
                self.select_index += cols
        elif key in ("return", "space"):
            if self.select_index < self.unlocked:
                self.start_level(self.select_index)
                return
        elif key.isdigit() and key != "0":
            idx = int(key) - 1
            if 0 <= idx < n and idx < self.unlocked:
                self.select_index = idx
                self.start_level(idx)
                return
        elif key == "escape":
            self.state = "menu"
            self.draw_menu()
            return
        self.draw_select()

    def on_click(self, event):
        lx, ly = self.to_logical(event.x, event.y)
        if self.state == "select":
            idx = self.hit_test_select(lx, ly)
            if idx is not None and idx < self.unlocked:
                self.select_index = idx
                self.start_level(idx)
        elif self.state == "menu":
            self.state = "select"
            self.draw_select()
        elif self.state == "lost":
            self.start_level(self.current_level_index)
        elif self.state == "won":
            self.start_level(self.current_level_index + 1)
        elif self.state == "complete":
            self.state = "select"
            self.draw_select()

    # -- level lifecycle ----------------------------------------------

    def start_level(self, idx):
        idx = max(0, min(idx, len(self.LEVELS) - 1))
        self.current_level_index = idx
        data = scale_level_data(self.LEVELS[idx]["build"]())

        self.platforms = data["platforms"]
        self.hazards = data["hazards"]
        self.movers = data["movers"]
        self.dart_traps = data["dart_traps"]
        self.fake_goals = data["fake_goals"]
        self.goal = data["goal"]
        self.signs = data["signs"]

        start_x, start_y = data.get("start", (100, 200))
        self.player_x, self.player_y = start_x, start_y
        self.vx = 0
        self.vy = 0
        self.on_ground = False
        self.facing = 1
        self.frame_count = 0

        self.state = "playing"
        self.update_platforms_dynamics()
        self.draw_frame()
        self.root.after(16, self.update)

    def update(self):
        if self.state != "playing":
            return
        self.update_input()
        self.apply_physics()
        if self.state == "playing":
            self.update_movers()
            self.update_dart_traps()
            self.check_collisions()
        self.draw_frame()
        if self.state == "playing":
            self.root.after(16, self.update)

    def update_input(self):
        if self.keys["left"] and not self.keys["right"]:
            self.vx = -MOVE_SPEED
        elif self.keys["right"] and not self.keys["left"]:
            self.vx = MOVE_SPEED
        else:
            self.vx = 0

        if self.vx > 0:
            self.facing = 1
        elif self.vx < 0:
            self.facing = -1

        if self.keys["jump"] and self.on_ground:
            self.vy = -JUMP_FORCE
            self.on_ground = False
            self.keys["jump"] = False

    def apply_physics(self):
        self.update_platforms_dynamics()

        self.vy += GRAVITY
        self.player_x += self.vx
        self.player_y += self.vy

        if self.player_x < 0:
            self.player_x = 0
        if self.player_x + PLAYER_W > WIDTH:
            self.player_x = WIDTH - PLAYER_W

        self.on_ground = False
        for platform in self.platforms:
            if not platform.get("_solid", True):
                continue
            land_tolerance = max(18, self.vy + 8)
            if (
                self.player_x + PLAYER_W > platform["x"]
                and self.player_x < platform["x"] + platform["w"]
                and self.player_y + PLAYER_H >= platform["y"]
                and self.player_y + PLAYER_H <= platform["y"] + land_tolerance
                and self.vy >= 0
            ):
                self.player_y = platform["y"] - PLAYER_H
                self.vy = 0
                self.on_ground = True
                if platform["type"] == "crumble" and platform["state"] == "idle":
                    platform["state"] = "landed"
                break

        self.update_crumble_timers()

        if self.player_y > HEIGHT + 120:
            self.lose("You fell into the void.")

    def update_platforms_dynamics(self):
        self.frame_count += 1
        for p in self.platforms:
            if p["type"] == "blink":
                phase = (self.frame_count + p.get("offset", 0)) % p["period"]
                p["_solid"] = phase < p["period"] * p["on_ratio"]
            elif p["type"] == "crumble":
                p["_solid"] = p["state"] != "gone"
            else:
                p["_solid"] = True

    def update_crumble_timers(self):
        for p in self.platforms:
            if p["type"] == "crumble" and p["state"] == "landed":
                p["timer"] += 1
                if p["timer"] >= p["delay"]:
                    p["state"] = "gone"

    def update_movers(self):
        for m in self.movers:
            m["x"] += m["speed"] * m["dir"]
            if m["x"] <= m["min"] or m["x"] >= m["max"]:
                m["dir"] *= -1

    def update_dart_traps(self):
        for d in self.dart_traps:
            if not d["fired"] and self.player_x >= d["trigger_x"]:
                d["fired"] = True
                d["arrow_x"] = d["start_x"]
            if d["arrow_x"] is not None:
                d["arrow_x"] += d["speed"] * d["dir"]
                if d["arrow_x"] < -80 or d["arrow_x"] > WIDTH + 80:
                    d["arrow_x"] = None

    def check_collisions(self):
        for fg in self.fake_goals:
            if self.rects_overlap(self.player_x, self.player_y, PLAYER_W, PLAYER_H,
                                   fg["x"], fg["y"], fg["w"], fg["h"]):
                self.lose("It's a trap! That wasn't the real portal.")
                return

        for hz in self.hazards:
            if self.rects_overlap(self.player_x, self.player_y, PLAYER_W, PLAYER_H,
                                   hz["x"], hz["y"], hz["w"], hz["h"]):
                self.lose("Impaled by a spike trap.")
                return

        for mv in self.movers:
            if self.rects_overlap(self.player_x, self.player_y, PLAYER_W, PLAYER_H,
                                   mv["x"], mv["y"], mv["w"], mv["h"]):
                self.lose("Sliced by a saw blade.")
                return

        for d in self.dart_traps:
            if d["arrow_x"] is not None and self.rects_overlap(
                self.player_x, self.player_y, PLAYER_W, PLAYER_H, d["arrow_x"], d["y"], d["w"], d["h"]
            ):
                self.lose("Skewered by a dart trap.")
                return

        if self.rects_overlap(self.player_x, self.player_y, PLAYER_W, PLAYER_H,
                               self.goal["x"], self.goal["y"], self.goal["w"], self.goal["h"]):
            self.win()

    @staticmethod
    def rects_overlap(ax, ay, aw, ah, bx, by, bw, bh):
        return ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by

    def lose(self, reason="You got caught by the trap."):
        self.deaths += 1
        self.state = "lost"
        self.lose_reason = reason
        self.draw_frame()

    def win(self):
        self.score += 100
        if self.current_level_index + 1 >= self.unlocked:
            self.unlocked = min(len(self.LEVELS), self.current_level_index + 2)
            save_progress(self.unlocked)

        if self.current_level_index >= len(self.LEVELS) - 1:
            self.state = "complete"
        else:
            self.state = "won"
        self.draw_frame()

    # -- level select geometry -----------------------------------------

    def select_boxes(self):
        n = len(self.LEVELS)
        cols = self.select_cols
        box_w, box_h = 420, 260
        gap_x, gap_y = 60, 60
        total_w = cols * box_w + (cols - 1) * gap_x
        start_x = (WIDTH - total_w) // 2
        start_y = 260
        boxes = []
        for i in range(n):
            row, col = divmod(i, cols)
            x0 = start_x + col * (box_w + gap_x)
            y0 = start_y + row * (box_h + gap_y)
            boxes.append((i, x0, y0, x0 + box_w, y0 + box_h))
        return boxes

    def hit_test_select(self, x, y):
        for i, x0, y0, x1, y1 in self.select_boxes():
            if x0 <= x <= x1 and y0 <= y <= y1:
                return i
        return None

    # -- drawing: menu / select -----------------------------------------

    def draw_keycap(self, x, y, w, h, label):
        self.rrect(x, y, x + w, y + h, r=10, fill=SURFACE_ALT, outline=BORDER, width=2)
        self.text(x + w / 2, y + h / 2, text=label, fill=TEXT_PRIMARY, font=("Segoe UI", 17, "bold"))

    def draw_badge(self, cx, cy, label, color):
        w = len(label) * 11 + 34
        self.pill(cx - w / 2, cy - 19, cx + w / 2, cy + 19, fill=color, outline="")
        self.text(cx, cy, text=label, fill=BADGE_TEXT, font=("Segoe UI", 13, "bold"))

    def draw_lock_icon(self, cx, cy, size):
        shackle_r = size * 0.5
        self.oval(cx - shackle_r, cy - shackle_r * 1.5, cx + shackle_r, cy + shackle_r * 0.5,
                   outline=TEXT_DIM, width=4)
        body_w, body_h = size * 1.3, size * 0.95
        bx0, by0, bx1, by1 = cx - body_w / 2, cy, cx + body_w / 2, cy + body_h
        self.rrect(bx0, by0, bx1, by1, r=6, fill=TEXT_DIM, outline="")
        self.oval(cx - 4, cy + body_h * 0.3, cx + 4, cy + body_h * 0.3 + 8, fill=SURFACE, outline="")

    def draw_menu(self):
        self.update_transform()
        self.canvas.delete("all")
        self.draw_bg(MENU_BG_TOP, MENU_BG_BOTTOM, "menu")
        self.draw_particles()

        self.text(WIDTH // 2, 200, text="LEVEL DEVIL-ISH", fill=TEXT_PRIMARY, font=("Segoe UI", 66, "bold"))
        self.rrect(WIDTH // 2 - 150, 246, WIDTH // 2 + 150, 254, r=4, fill=ACCENT, outline="")
        self.text(WIDTH // 2, 296, text="A cruel little platformer full of spikes, traps, and lies.",
                  fill=TEXT_MUTED, font=("Segoe UI", 20))

        card_x0, card_y0, card_x1, card_y1 = WIDTH // 2 - 420, 360, WIDTH // 2 + 420, 570
        self.rrect(card_x0 + 8, card_y0 + 12, card_x1 + 8, card_y1 + 12, r=26, fill=SHADOW_COLOR, outline="")
        self.rrect(card_x0, card_y0, card_x1, card_y1, r=26, fill=SURFACE, outline=BORDER, width=2)
        self.text(WIDTH // 2, card_y0 + 44, text="CONTROLS", fill=ACCENT, font=("Segoe UI", 22, "bold"))

        def control_row(y, caps, label):
            x = card_x0 + 70
            for cap in caps:
                w = 130 if len(cap) > 2 else 68
                self.draw_keycap(x, y, w, 56, cap)
                x += w + 14
            self.text(x + 20, y + 28, text=label, fill=TEXT_MUTED, font=("Segoe UI", 18, "bold"), anchor="w")

        control_row(card_y0 + 95, ["A", "D"], "MOVE LEFT / RIGHT")
        control_row(card_y0 + 175, ["W", "SPACE"], "JUMP")

        btn_x0, btn_y0, btn_x1, btn_y1 = WIDTH // 2 - 230, 630, WIDTH // 2 + 230, 700
        self.pill(btn_x0 + 6, btn_y0 + 8, btn_x1 + 6, btn_y1 + 8, fill=SHADOW_COLOR, outline="")
        self.pill(btn_x0, btn_y0, btn_x1, btn_y1, fill=ACCENT_STRONG, outline=ACCENT, width=2)
        self.text(WIDTH // 2, (btn_y0 + btn_y1) / 2, text="PRESS ENTER TO BEGIN",
                  fill="#ffffff", font=("Segoe UI", 22, "bold"))

        self.text(WIDTH // 2, 790, text="Tip: nothing here is as safe as it looks.",
                  fill=DANGER, font=("Segoe UI", 18, "italic"))
        self.text(WIDTH // 2, 840, text=f"{self.unlocked}/{len(self.LEVELS)} levels unlocked",
                  fill=TEXT_DIM, font=("Segoe UI", 16))

    def draw_select(self):
        self.update_transform()
        self.canvas.delete("all")
        self.draw_bg(MENU_BG_TOP, MENU_BG_BOTTOM, "select")
        self.draw_particles()

        self.text(WIDTH // 2, 100, text="SELECT A LEVEL", fill=TEXT_PRIMARY, font=("Segoe UI", 44, "bold"))
        self.text(
            WIDTH // 2, 150,
            text="Arrow keys / click to choose   •   Enter to play   •   1-6 to jump   •   Esc for title",
            fill=TEXT_MUTED, font=("Segoe UI", 16),
        )

        for i, x0, y0, x1, y1 in self.select_boxes():
            level = self.LEVELS[i]
            unlocked = i < self.unlocked
            completed = i < self.unlocked - 1
            selected = i == self.select_index

            self.rrect(x0 + 8, y0 + 12, x1 + 8, y1 + 12, r=22, fill=SHADOW_COLOR, outline="")
            fill = SURFACE_ALT if unlocked else SURFACE
            outline = ACCENT if selected else (BORDER if unlocked else BORDER_SOFT)
            self.rrect(x0, y0, x1, y1, r=22, fill=fill, outline=outline, width=4 if selected else 2)

            cx = (x0 + x1) / 2
            num_color = ACCENT if unlocked else TEXT_DIM
            self.text(cx, y0 + 58, text=str(i + 1), fill=num_color, font=("Segoe UI", 42, "bold"))

            if unlocked:
                self.text(cx, y0 + 148, text=level["name"], fill=TEXT_PRIMARY, font=("Segoe UI", 20, "bold"))
                if completed:
                    self.draw_badge(cx, y0 + 202, "COMPLETE", SUCCESS)
                else:
                    self.draw_badge(cx, y0 + 202, "PLAY", ACCENT)
            else:
                self.draw_lock_icon(cx, y0 + 140, 26)
                self.text(cx, y0 + 205, text="LOCKED", fill=TEXT_DIM, font=("Segoe UI", 15, "bold"))

        bar_x0, bar_y0, bar_x1, bar_y1 = WIDTH // 2 - 300, HEIGHT - 96, WIDTH // 2 + 300, HEIGHT - 76
        self.pill(bar_x0, bar_y0, bar_x1, bar_y1, fill=SURFACE_ALT, outline=BORDER, width=2)
        total = max(1, len(self.LEVELS) - 1)
        frac = (self.unlocked - 1) / total
        if frac > 0:
            fill_x1 = bar_x0 + (bar_x1 - bar_x0) * min(1.0, frac)
            self.pill(bar_x0, bar_y0, max(bar_x0 + (bar_y1 - bar_y0), fill_x1), bar_y1, fill=ACCENT_STRONG, outline="")

        self.text(WIDTH // 2, HEIGHT - 40,
                  text=f"Progress: {self.unlocked - 1}/{len(self.LEVELS)} cleared   •   {self.deaths} total deaths",
                  fill=TEXT_DIM, font=("Segoe UI", 15))

    # -- drawing: gameplay world ------------------------------------------

    def draw_platform(self, p):
        if p["type"] == "crumble":
            if p["state"] == "gone":
                return
            base = SURFACE_ALT if p["state"] == "idle" else "#7c4a12"
            edge = BORDER if p["state"] == "idle" else WARNING
        elif p["type"] == "blink":
            if not p.get("_solid", True):
                self.rrect(p["x"], p["y"], p["x"] + p["w"], p["y"] + p["h"], r=10,
                           fill="", outline=BORDER_SOFT, dash=(6, 4), width=2)
                return
            base, edge = SURFACE_ALT, ACCENT
        else:
            base, edge = SURFACE_ALT, BORDER

        self.rrect(p["x"], p["y"], p["x"] + p["w"], p["y"] + p["h"], r=10, fill=base, outline=edge, width=3)
        hi_h = min(p["h"] * 0.3, 10)
        self.rrect(p["x"] + 6, p["y"] + 4, p["x"] + p["w"] - 6, p["y"] + 4 + hi_h, r=5,
                   fill=SURFACE_LIGHT, outline="")

    def draw_spike(self, x, y, w, h):
        self.poly([x, y + h, x + w / 2, y, x + w, y + h], fill=DANGER, outline=DANGER_DARK, width=2)
        self.poly([x + w * 0.28, y + h, x + w / 2, y + h * 0.25, x + w * 0.72, y + h], fill="#fca5a5", outline="")

    def draw_saw(self, m):
        cx = m["x"] + m["w"] / 2
        cy = m["y"] + m["h"] / 2
        r = max(m["w"], m["h"]) / 2
        teeth = 8
        angle0 = (self.frame_count * 6) % 360
        pts = []
        for i in range(teeth * 2):
            ang = math.radians(angle0 + i * (360 / (teeth * 2)))
            rr = r if i % 2 == 0 else r * 0.62
            pts += [cx + math.cos(ang) * rr, cy + math.sin(ang) * rr]
        self.poly(pts, fill="#94a3b8", outline="#e2e8f0", width=2)
        self.oval(cx - r * 0.4, cy - r * 0.4, cx + r * 0.4, cy + r * 0.4, fill="#475569", outline="#cbd5e1", width=2)
        self.oval(cx - r * 0.12, cy - r * 0.12, cx + r * 0.12, cy + r * 0.12, fill="#1e293b", outline="")

    def draw_dart(self, d):
        x, y, w, h = d["arrow_x"], d["y"], d["w"], d["h"]
        cy = y + h / 2
        if d["dir"] >= 0:
            shaft = [x, y + h * 0.3, x + w * 0.7, y + h * 0.3, x + w * 0.7, y + h * 0.7, x, y + h * 0.7]
            head = [x + w * 0.7, y, x + w, cy, x + w * 0.7, y + h]
        else:
            shaft = [x + w * 0.3, y + h * 0.3, x + w, y + h * 0.3, x + w, y + h * 0.7, x + w * 0.3, y + h * 0.7]
            head = [x + w * 0.3, y, x, cy, x + w * 0.3, y + h]
        self.poly(shaft, fill=WARNING, outline="")
        self.poly(head, fill=WARNING, outline="#78350f", width=2)

    def draw_goal(self, g):
        cx = g["x"] + g["w"] / 2
        cy = g["y"] + g["h"] / 2
        pulse = 1 + 0.06 * math.sin(self.frame_count * 0.12)
        rw, rh = g["w"] / 2 * pulse, g["h"] / 2 * pulse
        self.oval(cx - rw - 10, cy - rh - 10, cx + rw + 10, cy + rh + 10, fill=SURFACE_LIGHT, outline="")
        self.oval(cx - rw, cy - rh, cx + rw, cy + rh, fill=SUCCESS, outline="#a7f3d0", width=3)
        self.oval(cx - rw * 0.55, cy - rh * 0.55, cx + rw * 0.55, cy + rh * 0.55, fill="#d1fae5", outline="")
        cs = min(g["w"], g["h"]) * 0.18
        self.poly([cx - cs, cy + cs * 0.5, cx, cy - cs * 0.6, cx + cs, cy + cs * 0.5, cx, cy + cs * 0.05],
                  fill=SURFACE, outline="")

    def draw_sign(self, s):
        w = len(s["text"]) * 11 + 40
        h = 46
        x0, y0, x1, y1 = s["x"] - w / 2, s["y"] - h, s["x"] + w / 2, s["y"]
        self.poly([s["x"] - 10, y1, s["x"] + 10, y1, s["x"], y1 + 16], fill=SURFACE, outline=WARNING, width=2)
        self.rrect(x0, y0, x1, y1, r=12, fill=SURFACE, outline=WARNING, width=2)
        self.text(s["x"], (y0 + y1) / 2, text=s["text"], fill=WARNING, font=("Segoe UI", 14, "bold"))

    def draw_player(self):
        x, y = self.player_x, self.player_y
        w, h = PLAYER_W, PLAYER_H
        cx = x + w / 2
        airborne = not self.on_ground
        moving = abs(self.vx) > 0.2
        facing = self.facing

        skin, limb, outline, dark = PLAYER_SKIN, PLAYER_SKIN_DARK, PLAYER_OUTLINE, "#1a1206"

        if self.on_ground:
            shadow_w = w * 1.3
            self.oval(cx - shadow_w / 2, y + h - 6, cx + shadow_w / 2, y + h + 14, fill=SHADOW_COLOR, outline="")

        head = w * 0.75
        hx0, hy0 = x + (w - head) / 2, y
        hx1, hy1 = hx0 + head, hy0 + head
        self.rrect(hx0, hy0, hx1, hy1, r=head * 0.28, fill=skin, outline=outline, width=2)

        eye = max(3, head * 0.16)
        ey = hy0 + head * 0.4
        ex = hx0 + head * (0.58 if facing >= 0 else 0.26)
        self.rect(ex, ey, ex + eye, ey + eye, fill=dark, outline="")

        hip_y = y + h * 0.6
        limb_w = max(4, w * 0.18)
        self.line([cx, hy1, cx, hip_y], fill=limb, width=limb_w)
        self.oval(cx - limb_w * 0.6, hy1 - limb_w * 0.6, cx + limb_w * 0.6, hy1 + limb_w * 0.6, fill=limb, outline="")

        shoulder_y = hy1 + (hip_y - hy1) * 0.15
        arm_reach = w * 0.9
        arm_drop = h * 0.22
        arm_width = max(3, w * 0.14)
        if airborne:
            arm_l = (cx - arm_reach * 0.5, shoulder_y - arm_drop * 0.6)
            arm_r = (cx + arm_reach * 0.5, shoulder_y - arm_drop * 0.6)
        else:
            swing = (w * 0.5) if moving and (self.frame_count // 6) % 2 == 0 else (-(w * 0.5) if moving else 0)
            arm_l = (cx - arm_reach * 0.35 + swing * 0.3, shoulder_y + arm_drop)
            arm_r = (cx + arm_reach * 0.35 - swing * 0.3, shoulder_y + arm_drop)
        self.line([cx, shoulder_y, arm_l[0], arm_l[1]], fill=limb, width=arm_width)
        self.line([cx, shoulder_y, arm_r[0], arm_r[1]], fill=limb, width=arm_width)
        for hxp, hyp in (arm_l, arm_r):
            self.oval(hxp - arm_width * 0.5, hyp - arm_width * 0.5, hxp + arm_width * 0.5, hyp + arm_width * 0.5,
                      fill=outline, outline="")

        foot_y = y + h
        leg_width = max(4, w * 0.16)
        if airborne:
            leg_l = (cx - w * 0.4, hip_y + (foot_y - hip_y) * 0.55)
            leg_r = (cx + w * 0.4, hip_y + (foot_y - hip_y) * 0.55)
        else:
            stride = w * 0.55 if moving else w * 0.18
            phase = (self.frame_count // 6) % 2
            leg_l = (cx - stride, foot_y) if phase == 0 else (cx - stride * 0.3, foot_y)
            leg_r = (cx + stride * 0.3, foot_y) if phase == 0 else (cx + stride, foot_y)
        self.line([cx, hip_y, leg_l[0], leg_l[1]], fill=limb, width=leg_width)
        self.line([cx, hip_y, leg_r[0], leg_r[1]], fill=limb, width=leg_width)
        self.oval(cx - limb_w * 0.6, hip_y - limb_w * 0.6, cx + limb_w * 0.6, hip_y + limb_w * 0.6,
                  fill=limb, outline="")

    def draw_hud(self):
        level = self.LEVELS[self.current_level_index]

        self.pill(30, 26, 240, 74, fill=SURFACE, outline=BORDER, width=2)
        self.oval(50, 38, 74, 62, fill=DANGER, outline="")
        self.text(62, 50, text="!", fill=BADGE_TEXT, font=("Segoe UI", 15, "bold"))
        self.text(145, 50, text=f"Deaths {self.deaths}", fill=TEXT_PRIMARY, font=("Segoe UI", 17, "bold"))

        name_w = len(level["name"]) * 13 + 230
        cx0 = WIDTH / 2 - name_w / 2
        self.pill(cx0, 26, cx0 + name_w, 74, fill=SURFACE, outline=BORDER, width=2)
        self.text(WIDTH / 2, 50, text=f"LEVEL {self.current_level_index + 1} — {level['name']}",
                  fill=TEXT_PRIMARY, font=("Segoe UI", 17, "bold"))

        self.pill(WIDTH - 270, 26, WIDTH - 30, 74, fill=SURFACE, outline=BORDER, width=2)
        self.text(WIDTH - 150, 50, text="ESC — Level Select", fill=TEXT_MUTED, font=("Segoe UI", 15))

    def draw_overlay(self):
        specs = {
            "lost": (self.lose_reason, "Press Enter to try again   •   Esc for level select", DANGER, "!"),
            "won": ("LEVEL CLEARED", "Press Enter for the next level   •   Esc for level select", SUCCESS, "✓"),
            "complete": ("YOU BEAT LEVEL DEVIL-ISH", f"Total deaths this session: {self.deaths}", ACCENT, "★"),
        }
        title, sub, color, glyph = specs[self.state]

        w0, h0, w1, h1 = WIDTH / 2 - 380, HEIGHT / 2 - 220, WIDTH / 2 + 380, HEIGHT / 2 + 180
        self.rrect(w0 + 10, h0 + 14, w1 + 10, h1 + 14, r=30, fill=SHADOW_COLOR, outline="")
        self.rrect(w0, h0, w1, h1, r=30, fill=SURFACE, outline=color, width=3)

        self.oval(WIDTH / 2 - 42, h0 + 36, WIDTH / 2 + 42, h0 + 120, fill=color, outline="")
        self.text(WIDTH / 2, h0 + 78, text=glyph, fill=BADGE_TEXT, font=("Segoe UI", 34, "bold"))

        self.text(WIDTH / 2, h0 + 170, text=title, fill=TEXT_PRIMARY, font=("Segoe UI", 28, "bold"))
        self.text(WIDTH / 2, h0 + 218, text=sub, fill=TEXT_MUTED, font=("Segoe UI", 18))

        if self.state == "complete":
            self.text(WIDTH / 2, h0 + 260, text="Press Enter to return to Level Select",
                      fill=color, font=("Segoe UI", 18, "bold"))

    def draw_frame(self):
        self.update_transform()
        self.canvas.delete("all")
        self.draw_bg(PLAY_BG_TOP, PLAY_BG_BOTTOM, "play")

        for gx in range(0, WIDTH, 170):
            self.line([gx, 0, gx, HEIGHT], fill=BORDER_SOFT)
        for gy in range(0, HEIGHT, 170):
            self.line([0, gy, WIDTH, gy], fill=BORDER_SOFT)

        for p in self.platforms:
            self.draw_platform(p)

        for hz in self.hazards:
            self.draw_spike(hz["x"], hz["y"], hz["w"], hz["h"])

        for mv in self.movers:
            self.draw_saw(mv)

        for d in self.dart_traps:
            if d["arrow_x"] is not None:
                self.draw_dart(d)

        for fg in self.fake_goals:
            self.draw_goal(fg)
        self.draw_goal(self.goal)

        for s in self.signs:
            self.draw_sign(s)

        self.draw_player()
        self.draw_hud()

        if self.state in ("lost", "won", "complete"):
            self.draw_overlay()


if __name__ == "__main__":
    DevilishPlatformer()
