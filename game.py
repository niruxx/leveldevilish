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

# Player collision box. Aspect (44:66 = 2:3) matches the 16x24 hero sprite so
# it upscales without distortion.
PLAYER_W = 44
PLAYER_H = 66

# --- Movement feel ("pixel man" mechanics) --------------------------------
GRAVITY = 0.82
MAX_FALL = 22.0
JUMP_FORCE = 17.0
JUMP_CUT = 0.45          # releasing jump early shortens the hop
MOVE_SPEED = 7.6
GROUND_ACCEL = 1.7       # how fast we reach MOVE_SPEED on the ground
AIR_ACCEL = 0.95         # weaker steering in the air
GROUND_FRICTION = 2.0    # deceleration when no key is held
AIR_FRICTION = 0.35
COYOTE_FRAMES = 6        # grace window to still jump just after leaving a ledge
JUMP_BUFFER_FRAMES = 7   # remember a jump press made just before landing

ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
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

# platform styling (blocky pixel brick)
BRICK_FILL = "#3b4675"
BRICK_TOP = "#6b78ad"
BRICK_SH = "#28305a"
BRICK_MORTAR = "#232a52"
CRUMBLE_FILL = "#7c4a12"
CRUMBLE_TOP = "#b3752a"
CRUMBLE_SH = "#4d2c08"

OUTLINE_DARK = "#0f1120"
SHADOW_COLOR = "#02030a"

FONT = "Segoe UI"


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
# Asset manager: loads pixel-art PNGs and serves crisp nearest-neighbour
# upscales, cached per integer zoom so redraws stay cheap.
# ---------------------------------------------------------------------------

class Assets:
    def __init__(self, directory):
        self.dir = directory
        self.native = {}
        self.flipped = {}
        self.zoom_cache = {}
        self.available = os.path.isdir(directory)
        if self.available:
            self._load_all()

    def _load_all(self):
        for fn in os.listdir(self.dir):
            if fn.endswith(".png") and not fn.startswith("_"):
                name = fn[:-4]
                try:
                    self.native[name] = tk.PhotoImage(file=os.path.join(self.dir, fn))
                except Exception:
                    pass
        # Pre-mirror hero frames so we can face left.
        for name in list(self.native):
            if name.startswith("player_"):
                self.flipped[name] = self._mirror(self.native[name])

    @staticmethod
    def _mirror(img):
        w, h = img.width(), img.height()
        out = tk.PhotoImage(width=w, height=h)
        for y in range(h):
            for x in range(w):
                if not img.transparency_get(x, y):
                    r, g, b = img.get(x, y)
                    out.put(f"#{r:02x}{g:02x}{b:02x}", to=(w - 1 - x, y, w - x, y + 1))
        return out

    def get(self, name, zoom, flip=False):
        zoom = max(1, int(zoom))
        key = (name, zoom, flip)
        cached = self.zoom_cache.get(key)
        if cached is not None:
            return cached
        base = (self.flipped if flip else self.native).get(name)
        if base is None:
            base = self.native.get(name)
        if base is None:
            return None
        img = base.zoom(zoom) if zoom > 1 else base
        self.zoom_cache[key] = img
        return img

    def native_size(self, name):
        img = self.native.get(name)
        return (img.width(), img.height()) if img else (16, 16)


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
        win_w = min(WIDTH, screen_w - 80)
        win_h = min(HEIGHT, screen_h - 120)
        pos_x = max(0, (screen_w - win_w) // 2)
        pos_y = max(0, (screen_h - win_h) // 2)
        self.root.geometry(f"{win_w}x{win_h}+{pos_x}+{pos_y}")

        self.canvas = tk.Canvas(self.root, width=win_w, height=win_h, bg="#03040c", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.assets = Assets(ASSET_DIR)

        self.keys = {"left": False, "right": False, "jump": False}
        self.root.bind("<KeyPress>", self.on_key_press)
        self.root.bind("<KeyRelease>", self.on_key_release)
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<Motion>", self.on_motion)
        self.canvas.bind("<Configure>", self.on_resize)

        self.LEVELS = LEVEL_DEFS

        self.state = "menu"
        self.player_x = 100.0
        self.player_y = 200.0
        self.vx = 0.0
        self.vy = 0.0
        self.on_ground = False
        self.facing = 1
        self.coyote = 0
        self.jump_buffer = 0
        self.deaths = 0
        self.frame_count = 0
        self.anim_timer = 0

        self.platforms = []
        self.hazards = []
        self.movers = []
        self.dart_traps = []
        self.fake_goals = []
        self.signs = []
        self.goal = {"x": 0, "y": 0, "w": 0, "h": 0}

        self.current_level_index = 0
        self.select_index = 0
        self.menu_index = 0
        self.pause_index = 0
        self.show_controls = False
        self.lose_reason = ""
        self.unlocked = load_progress(len(self.LEVELS))

        # menu button hit-boxes for the current screen (logical rects + action)
        self.buttons = []
        self.hover_key = None

        self._scale = 1.0
        self._ox = 0.0
        self._oy = 0.0
        self._cw = win_w
        self._ch = win_h
        self._gradient_cache = {}
        self._img_refs = []

        self.stars = [
            {
                "x": random.uniform(0, WIDTH),
                "y": random.uniform(0, HEIGHT),
                "s": random.randint(0, 2),
                "vx": random.uniform(-0.12, 0.12),
                "vy": random.uniform(0.04, 0.22),
                "tw": random.uniform(0, math.tau),
            }
            for _ in range(46)
        ]

        self.map_nodes = self._build_map_nodes()

        self.root.update_idletasks()
        self.render_current()
        self.root.after(33, self.ambient_tick)
        self.root.mainloop()

    # -- view transform -------------------------------------------------

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

    def blit(self, name, lx, ly, logical_h, anchor="center", flip=False):
        """Draw a pixel-art sprite so it occupies `logical_h` logical px tall,
        crisply nearest-neighbour upscaled for the current view scale."""
        _nw, nh = self.assets.native_size(name)
        if nh == 0:
            return
        target_screen_h = logical_h * self._scale
        zoom = max(1, round(target_screen_h / nh))
        img = self.assets.get(name, zoom, flip=flip)
        if img is None:
            return
        px, py = self.L(lx, ly)
        item = self.canvas.create_image(px, py, image=img, anchor=anchor)
        self._img_refs.append(img)
        return item

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

    def draw_stars(self):
        for s in self.stars:
            twinkle = 0.5 + 0.5 * math.sin(s["tw"] + self.frame_count * 0.06)
            if twinkle > 0.35:
                self.blit(f"star_{s['s']}", s["x"], s["y"], 10 + s["s"] * 3)

    def ambient_tick(self):
        self.frame_count += 1
        if self.state in ("menu", "map"):
            for s in self.stars:
                s["x"] += s["vx"]
                s["y"] += s["vy"]
                if s["x"] < -12:
                    s["x"] = WIDTH + 12
                if s["x"] > WIDTH + 12:
                    s["x"] = -12
                if s["y"] > HEIGHT + 12:
                    s["y"] = -12
            self.render_current()
        self.root.after(33, self.ambient_tick)

    # -- input -------------------------------------------------------

    def on_resize(self, _event):
        self.render_current()

    def render_current(self):
        if self.state == "menu":
            self.draw_menu()
        elif self.state == "map":
            self.draw_map()
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
            if self.state == "playing":
                self.jump_buffer = JUMP_BUFFER_FRAMES

        if self.state == "menu":
            self.handle_menu_key(key)
        elif self.state == "map":
            self.handle_map_key(key)
        elif self.state == "playing":
            if key in ("escape", "p"):
                self.pause_game()
        elif self.state == "paused":
            self.handle_pause_key(key)
        elif self.state in ("lost", "won", "complete"):
            self.handle_result_key(key)

    def on_key_release(self, event):
        key = event.keysym.lower()
        if key in ("left", "a"):
            self.keys["left"] = False
        elif key in ("right", "d"):
            self.keys["right"] = False
        elif key in ("up", "w", "space"):
            self.keys["jump"] = False

    # menu screen keyboard
    def handle_menu_key(self, key):
        opts = self.menu_options()
        if key in ("up", "w"):
            self.menu_index = (self.menu_index - 1) % len(opts)
        elif key in ("down", "s"):
            self.menu_index = (self.menu_index + 1) % len(opts)
        elif key in ("return", "space"):
            opts[self.menu_index][1]()
            return
        elif key == "escape":
            if self.show_controls:
                self.show_controls = False
        self.draw_menu()

    def menu_options(self):
        return [
            ("PLAY", self.open_map),
            ("HOW TO PLAY", self.toggle_controls),
            ("QUIT", self.root.destroy),
        ]

    def toggle_controls(self):
        self.show_controls = not self.show_controls
        self.draw_menu()

    def open_map(self):
        self.state = "map"
        self.select_index = min(self.unlocked - 1, len(self.LEVELS) - 1)
        self.draw_map()

    # map screen keyboard
    def handle_map_key(self, key):
        n = len(self.LEVELS)
        if key in ("left", "a"):
            self.select_index = max(0, self.select_index - 1)
        elif key in ("right", "d"):
            self.select_index = min(n - 1, self.select_index + 1)
        elif key in ("up", "w"):
            self.select_index = max(0, self.select_index - 1)
        elif key in ("down", "s"):
            self.select_index = min(n - 1, self.select_index + 1)
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
        self.draw_map()

    # pause menu keyboard
    def handle_pause_key(self, key):
        opts = self.pause_options()
        if key in ("up", "w"):
            self.pause_index = (self.pause_index - 1) % len(opts)
        elif key in ("down", "s"):
            self.pause_index = (self.pause_index + 1) % len(opts)
        elif key in ("return", "space"):
            opts[self.pause_index][1]()
            return
        elif key in ("escape", "p"):
            self.resume_game()
            return
        self.draw_frame()

    def pause_options(self):
        return [
            ("RESUME", self.resume_game),
            ("RESTART LEVEL", lambda: self.start_level(self.current_level_index)),
            ("WORLD MAP", self.open_map),
            ("MAIN MENU", self.go_menu),
        ]

    def go_menu(self):
        self.state = "menu"
        self.menu_index = 0
        self.draw_menu()

    # result overlay keyboard
    def handle_result_key(self, key):
        opts = self.result_options()
        if key in ("up", "w", "left", "a"):
            self.result_index = (self.result_index - 1) % len(opts)
        elif key in ("down", "s", "right", "d"):
            self.result_index = (self.result_index + 1) % len(opts)
        elif key in ("return", "space"):
            opts[self.result_index][1]()
            return
        elif key == "escape":
            self.open_map()
            return
        self.draw_frame()

    result_index = 0

    def result_options(self):
        if self.state == "lost":
            return [("TRY AGAIN", lambda: self.start_level(self.current_level_index)),
                    ("WORLD MAP", self.open_map)]
        if self.state == "won":
            return [("NEXT LEVEL", lambda: self.start_level(self.current_level_index + 1)),
                    ("REPLAY", lambda: self.start_level(self.current_level_index)),
                    ("WORLD MAP", self.open_map)]
        return [("WORLD MAP", self.open_map), ("MAIN MENU", self.go_menu)]

    def on_motion(self, event):
        if self.state in ("menu", "map", "paused", "lost", "won", "complete"):
            lx, ly = self.to_logical(event.x, event.y)
            new_hover = None
            for b in self.buttons:
                if b["x0"] <= lx <= b["x1"] and b["y0"] <= ly <= b["y1"]:
                    new_hover = b["key"]
                    break
            if new_hover != self.hover_key:
                self.hover_key = new_hover
                if new_hover is not None:
                    if self.state == "menu":
                        for i, (_, _) in enumerate(self.menu_options()):
                            if f"menu{i}" == new_hover:
                                self.menu_index = i
                    elif self.state == "paused":
                        for i, _ in enumerate(self.pause_options()):
                            if f"pause{i}" == new_hover:
                                self.pause_index = i
                    elif self.state in ("lost", "won", "complete"):
                        for i, _ in enumerate(self.result_options()):
                            if f"res{i}" == new_hover:
                                self.result_index = i
                self.render_current()

    def on_click(self, event):
        lx, ly = self.to_logical(event.x, event.y)
        for b in self.buttons:
            if b["x0"] <= lx <= b["x1"] and b["y0"] <= ly <= b["y1"]:
                b["action"]()
                return

    def add_button(self, key, x0, y0, x1, y1, action):
        self.buttons.append({"key": key, "x0": x0, "y0": y0, "x1": x1, "y1": y1, "action": action})

    # -- level lifecycle ----------------------------------------------

    def pause_game(self):
        self.state = "paused"
        self.pause_index = 0
        self.draw_frame()

    def resume_game(self):
        if self.state != "paused":
            return
        self.state = "playing"
        self.jump_buffer = 0
        self.draw_frame()
        self.root.after(16, self.update)

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
        self.player_x, self.player_y = float(start_x), float(start_y)
        self.vx = 0.0
        self.vy = 0.0
        self.on_ground = False
        self.facing = 1
        self.coyote = 0
        self.jump_buffer = 0

        self.state = "playing"
        self.update_platforms_dynamics()
        self.draw_frame()
        self.root.after(16, self.update)

    def update(self):
        if self.state != "playing":
            return
        self.apply_physics()
        if self.state == "playing":
            self.update_movers()
            self.update_dart_traps()
            self.check_collisions()
        self.draw_frame()
        if self.state == "playing":
            self.root.after(16, self.update)

    def apply_physics(self):
        self.update_platforms_dynamics()

        # --- horizontal: accelerate toward target, friction otherwise ---
        want = (1 if self.keys["right"] else 0) - (1 if self.keys["left"] else 0)
        accel = GROUND_ACCEL if self.on_ground else AIR_ACCEL
        friction = GROUND_FRICTION if self.on_ground else AIR_FRICTION
        if want != 0:
            target = want * MOVE_SPEED
            if self.vx < target:
                self.vx = min(self.vx + accel, target)
            elif self.vx > target:
                self.vx = max(self.vx - accel, target)
            self.facing = want
        else:
            if self.vx > 0:
                self.vx = max(0.0, self.vx - friction)
            elif self.vx < 0:
                self.vx = min(0.0, self.vx + friction)

        # --- jump: coyote time + input buffering + variable height ---
        if self.jump_buffer > 0:
            self.jump_buffer -= 1
        if self.coyote > 0:
            self.coyote -= 1
        if self.jump_buffer > 0 and (self.on_ground or self.coyote > 0):
            self.vy = -JUMP_FORCE
            self.on_ground = False
            self.coyote = 0
            self.jump_buffer = 0
        # short hop: cut upward velocity when jump released mid-rise
        if not self.keys["jump"] and self.vy < 0:
            self.vy *= JUMP_CUT

        self.vy += GRAVITY
        if self.vy > MAX_FALL:
            self.vy = MAX_FALL

        self.player_x += self.vx
        self.player_y += self.vy

        if self.player_x < 0:
            self.player_x = 0
            self.vx = 0
        if self.player_x + PLAYER_W > WIDTH:
            self.player_x = WIDTH - PLAYER_W
            self.vx = 0

        was_on_ground = self.on_ground
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

        # refresh coyote grace the moment we leave the ground
        if was_on_ground and not self.on_ground:
            self.coyote = COYOTE_FRAMES
        elif self.on_ground:
            self.coyote = COYOTE_FRAMES

        self.update_crumble_timers()

        if self.player_y > HEIGHT + 120:
            self.lose("You fell into the void.")

    def update_platforms_dynamics(self):
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
        self.result_index = 0
        self.lose_reason = reason
        self.draw_frame()

    def win(self):
        if self.current_level_index + 1 >= self.unlocked:
            self.unlocked = min(len(self.LEVELS), self.current_level_index + 2)
            save_progress(self.unlocked)

        self.result_index = 0
        if self.current_level_index >= len(self.LEVELS) - 1:
            self.state = "complete"
        else:
            self.state = "won"
        self.draw_frame()

    # -- world-map geometry --------------------------------------------

    def _build_map_nodes(self):
        n = len(self.LEVELS)
        left, right = 320, WIDTH - 320
        mid_y = 620
        amp = 150
        nodes = []
        for i in range(n):
            t = i / max(1, n - 1)
            x = left + (right - left) * t
            y = mid_y + amp * math.sin(t * math.pi * 1.6)
            nodes.append((x, y))
        return nodes

    def hit_test_node(self, lx, ly):
        for i, (nx, ny) in enumerate(self.map_nodes):
            if (lx - nx) ** 2 + (ly - ny) ** 2 <= 66 ** 2:
                return i
        return None

    # -- drawing: menu --------------------------------------------------

    def draw_menu(self):
        self.update_transform()
        self.canvas.delete("all")
        self._img_refs = []
        self.buttons = []
        self.draw_bg(MENU_BG_TOP, MENU_BG_BOTTOM, "menu")
        self.draw_stars()

        # animated hero mascot idling by the title
        bob = math.sin(self.frame_count * 0.08) * 6
        self.blit("player_idle_0" if (self.frame_count // 20) % 6 else "player_idle_1",
                  WIDTH // 2 - 470, 250 + bob, 150)

        self.text(WIDTH // 2, 200, text="LEVEL DEVIL-ISH", fill=TEXT_PRIMARY, font=(FONT, 72, "bold"))
        self.rrect(WIDTH // 2 - 160, 250, WIDTH // 2 + 160, 258, r=4, fill=ACCENT, outline="")
        self.text(WIDTH // 2, 300, text="A cruel little platformer full of spikes, traps, and lies.",
                  fill=TEXT_MUTED, font=(FONT, 22))

        if self.show_controls:
            self.draw_controls_card()
        else:
            self.draw_menu_buttons()

        self.text(WIDTH // 2, HEIGHT - 90, text="Tip: nothing here is as safe as it looks.",
                  fill=DANGER, font=(FONT, 18, "italic"))
        self.text(WIDTH // 2, HEIGHT - 55, text=f"{self.unlocked}/{len(self.LEVELS)} levels unlocked",
                  fill=TEXT_DIM, font=(FONT, 16))

    def draw_menu_buttons(self):
        opts = self.menu_options()
        bw, bh, gap = 460, 82, 26
        top = 400
        for i, (label, _) in enumerate(opts):
            x0 = WIDTH // 2 - bw / 2
            y0 = top + i * (bh + gap)
            self._menu_button(f"menu{i}", label, x0, y0, x0 + bw, y0 + bh,
                              i == self.menu_index, opts[i][1],
                              primary=(i == 0))

    def _menu_button(self, key, label, x0, y0, x1, y1, active, action, primary=False):
        self.add_button(key, x0, y0, x1, y1, action)
        self.pill(x0 + 5, y0 + 7, x1 + 5, y1 + 7, fill=SHADOW_COLOR, outline="")
        if active:
            fill = ACCENT_STRONG if primary else SURFACE_LIGHT
            outline = ACCENT
            tcol = "#ffffff"
            width = 3
        else:
            fill = SURFACE if primary else SURFACE_ALT
            outline = BORDER
            tcol = TEXT_MUTED if not primary else TEXT_PRIMARY
            width = 2
        self.pill(x0, y0, x1, y1, fill=fill, outline=outline, width=width)
        if active:
            self.text(x0 + 44, (y0 + y1) / 2, text="▶", fill=ACCENT, font=(FONT, 22, "bold"))
        self.text((x0 + x1) / 2, (y0 + y1) / 2, text=label, fill=tcol, font=(FONT, 26, "bold"))

    def draw_controls_card(self):
        card_x0, card_y0, card_x1, card_y1 = WIDTH // 2 - 430, 380, WIDTH // 2 + 430, 720
        self.rrect(card_x0 + 8, card_y0 + 12, card_x1 + 8, card_y1 + 12, r=26, fill=SHADOW_COLOR, outline="")
        self.rrect(card_x0, card_y0, card_x1, card_y1, r=26, fill=SURFACE, outline=BORDER, width=2)
        self.text(WIDTH // 2, card_y0 + 46, text="HOW TO PLAY", fill=ACCENT, font=(FONT, 24, "bold"))

        def control_row(y, caps, label):
            x = card_x0 + 80
            for cap in caps:
                w = 140 if len(cap) > 2 else 72
                self.rrect(x, y, x + w, y + 58, r=10, fill=SURFACE_ALT, outline=BORDER, width=2)
                self.text(x + w / 2, y + 29, text=cap, fill=TEXT_PRIMARY, font=(FONT, 18, "bold"))
                x += w + 14
            self.text(x + 22, y + 29, text=label, fill=TEXT_MUTED, font=(FONT, 19, "bold"), anchor="w")

        control_row(card_y0 + 84, ["A", "D"], "MOVE LEFT / RIGHT")
        control_row(card_y0 + 160, ["W", "SPACE"], "JUMP  (hold for higher)")
        control_row(card_y0 + 236, ["ESC", "P"], "PAUSE")

        # back button
        bw, bh = 300, 66
        x0 = WIDTH // 2 - bw / 2
        y0 = card_y1 + 24
        self._menu_button("menuback", "BACK", x0, y0, x0 + bw, y0 + bh, True, self.toggle_controls, primary=True)

    # -- drawing: world map ---------------------------------------------

    def draw_map(self):
        self.update_transform()
        self.canvas.delete("all")
        self._img_refs = []
        self.buttons = []
        self.draw_bg(MENU_BG_TOP, MENU_BG_BOTTOM, "map")
        self.draw_stars()

        self.text(WIDTH // 2, 110, text="WORLD MAP", fill=TEXT_PRIMARY, font=(FONT, 48, "bold"))
        self.text(WIDTH // 2, 165,
                  text="Arrows / click to choose   •   Enter to play   •   1-6 jump to a level   •   Esc for title",
                  fill=TEXT_MUTED, font=(FONT, 17))

        # connecting path between nodes (dashed segments, lit up to progress)
        for i in range(len(self.map_nodes) - 1):
            x0, y0 = self.map_nodes[i]
            x1, y1 = self.map_nodes[i + 1]
            reached = (i + 1) < self.unlocked
            col = ACCENT if reached else BORDER_SOFT
            self.line([x0, y0, x1, y1], fill=col, width=6, dash=(3, 3))

        for i, (nx, ny) in enumerate(self.map_nodes):
            self.draw_map_node(i, nx, ny)

        # info panel for the selected level
        self.draw_map_info()

        # progress bar
        bar_x0, bar_y0, bar_x1, bar_y1 = WIDTH // 2 - 320, HEIGHT - 70, WIDTH // 2 + 320, HEIGHT - 50
        self.pill(bar_x0, bar_y0, bar_x1, bar_y1, fill=SURFACE_ALT, outline=BORDER, width=2)
        total = max(1, len(self.LEVELS) - 1)
        frac = (self.unlocked - 1) / total
        if frac > 0:
            fill_x1 = bar_x0 + (bar_x1 - bar_x0) * min(1.0, frac)
            self.pill(bar_x0, bar_y0, max(bar_x0 + (bar_y1 - bar_y0), fill_x1), bar_y1, fill=ACCENT_STRONG, outline="")
        self.text(WIDTH // 2, HEIGHT - 26,
                  text=f"{self.unlocked - 1}/{len(self.LEVELS)} cleared   •   {self.deaths} total deaths",
                  fill=TEXT_DIM, font=(FONT, 15))

    def draw_map_node(self, i, nx, ny):
        unlocked = i < self.unlocked
        completed = i < self.unlocked - 1
        selected = i == self.select_index
        self.add_button(f"node{i}", nx - 60, ny - 60, nx + 60, ny + 60,
                        (lambda idx=i: self.start_level(idx)) if unlocked else (lambda: None))

        r = 54
        if selected:
            pulse = 6 + 4 * math.sin(self.frame_count * 0.12)
            self.oval(nx - r - pulse, ny - r - pulse, nx + r + pulse, ny + r + pulse,
                      outline=ACCENT, width=4, fill="")

        # base disc
        self.oval(nx - r + 4, ny - r + 8, nx + r + 4, ny + r + 8, fill=SHADOW_COLOR, outline="")
        fill = SURFACE_ALT if unlocked else SURFACE
        outline = ACCENT if selected else (BORDER if unlocked else BORDER_SOFT)
        self.oval(nx - r, ny - r, nx + r, ny + r, fill=fill, outline=outline, width=4 if selected else 3)

        if not unlocked:
            self.blit("lock", nx, ny - 4, 42)
        else:
            self.text(nx, ny - 6, text=str(i + 1), fill=ACCENT if not completed else SUCCESS,
                      font=(FONT, 40, "bold"))
            if completed:
                self.blit("flag", nx + 34, ny - 34, 34)

    def draw_map_info(self):
        i = self.select_index
        level = self.LEVELS[i]
        unlocked = i < self.unlocked
        completed = i < self.unlocked - 1
        px0, py0, px1, py1 = WIDTH // 2 - 380, 850, WIDTH // 2 + 380, 990
        self.rrect(px0 + 8, py0 + 10, px1 + 8, py1 + 10, r=22, fill=SHADOW_COLOR, outline="")
        self.rrect(px0, py0, px1, py1, r=22, fill=SURFACE, outline=BORDER, width=2)
        self.text(px0 + 40, py0 + 46, text=f"LEVEL {i + 1}", fill=ACCENT, font=(FONT, 20, "bold"), anchor="w")
        self.text(px0 + 40, py0 + 90, text=level["name"], fill=TEXT_PRIMARY, font=(FONT, 30, "bold"), anchor="w")

        status = "LOCKED" if not unlocked else ("COMPLETE" if completed else "READY")
        scol = TEXT_DIM if not unlocked else (SUCCESS if completed else WARNING)
        self.text(px1 - 40, py0 + 46, text=status, fill=scol, font=(FONT, 20, "bold"), anchor="e")

        if unlocked:
            bw, bh = 300, 60
            bx0 = px1 - 40 - bw
            by0 = py1 - 40 - bh
            self._menu_button(f"play{i}", "▶  PLAY", bx0, by0, bx0 + bw, by0 + bh, True,
                              lambda: self.start_level(i), primary=True)
        else:
            self.text(px1 - 40, py1 - 50, text="Clear the level before to unlock",
                      fill=TEXT_DIM, font=(FONT, 16, "italic"), anchor="e")

    # -- drawing: gameplay world ------------------------------------------

    def draw_platform(self, p):
        if p["type"] == "crumble":
            if p["state"] == "gone":
                return
            base = CRUMBLE_FILL if p["state"] == "idle" else "#8a5417"
            top = CRUMBLE_TOP
            sh = CRUMBLE_SH
        elif p["type"] == "blink":
            if not p.get("_solid", True):
                self.rect(p["x"], p["y"], p["x"] + p["w"], p["y"] + p["h"],
                          fill="", outline=BORDER_SOFT, dash=(6, 4), width=2)
                return
            base, top, sh = BRICK_FILL, "#7f8dff", BRICK_SH
        else:
            base, top, sh = BRICK_FILL, BRICK_TOP, BRICK_SH

        x0, y0, x1, y1 = p["x"], p["y"], p["x"] + p["w"], p["y"] + p["h"]
        self.rect(x0, y0, x1, y1, fill=base, outline="")
        # blocky bevel
        self.rect(x0, y0, x1, y0 + max(4, p["h"] * 0.22), fill=top, outline="")
        self.rect(x0, y1 - max(3, p["h"] * 0.16), x1, y1, fill=sh, outline="")
        # mortar seams
        seam = BRICK_MORTAR if p["type"] != "crumble" else CRUMBLE_SH
        step = max(60, p["w"] / 6)
        gx = x0 + step
        while gx < x1 - 4:
            self.line([gx, y0 + p["h"] * 0.22, gx, y1], fill=seam, width=2)
            gx += step
        self.rect(x0, y0, x1, y1, fill="", outline=OUTLINE_DARK, width=2)

    def draw_hud(self):
        level = self.LEVELS[self.current_level_index]

        self.pill(30, 26, 250, 78, fill=SURFACE, outline=BORDER, width=2)
        self.oval(50, 40, 76, 66, fill=DANGER, outline="")
        self.text(63, 53, text="✖", fill=BADGE_TEXT, font=(FONT, 14, "bold"))
        self.text(150, 53, text=f"Deaths {self.deaths}", fill=TEXT_PRIMARY, font=(FONT, 18, "bold"))

        name_w = len(level["name"]) * 14 + 250
        cx0 = WIDTH / 2 - name_w / 2
        self.pill(cx0, 26, cx0 + name_w, 78, fill=SURFACE, outline=BORDER, width=2)
        self.text(WIDTH / 2, 53, text=f"LEVEL {self.current_level_index + 1} — {level['name']}",
                  fill=TEXT_PRIMARY, font=(FONT, 18, "bold"))

        self.pill(WIDTH - 260, 26, WIDTH - 30, 78, fill=SURFACE, outline=BORDER, width=2)
        self.text(WIDTH - 145, 53, text="ESC — Pause", fill=TEXT_MUTED, font=(FONT, 16))

    def draw_spike(self, hz):
        self.blit("spike", hz["x"] + hz["w"] / 2, hz["y"] + hz["h"], hz["h"] * 1.15, anchor="s")

    def draw_saw(self, m):
        frame = (self.frame_count // 3) % 4
        size = max(m["w"], m["h"]) * 1.4
        self.blit(f"saw_{frame}", m["x"] + m["w"] / 2, m["y"] + m["h"] / 2, size)

    def draw_dart(self, d):
        flip = d["dir"] < 0
        cy = d["y"] + d["h"] / 2
        self.blit("dart", d["arrow_x"] + d["w"] / 2, cy, d["h"] * 1.4, flip=flip)

    def draw_goal(self, g, fake=False):
        cx = g["x"] + g["w"] / 2
        cy = g["y"] + g["h"] / 2
        if fake:
            self.blit("portal_fake", cx, cy, g["h"] * 1.4)
        else:
            frame = (self.frame_count // 6) % 4
            glow = 0.5 + 0.5 * math.sin(self.frame_count * 0.14)
            gr = g["w"] * (0.85 + 0.12 * glow)
            self.oval(cx - gr, cy - gr, cx + gr, cy + gr, fill="", outline=SUCCESS, width=2)
            self.blit(f"portal_{frame}", cx, cy, g["h"] * 1.5)

    def draw_sign(self, s):
        w = len(s["text"]) * 11 + 40
        h = 46
        x0, y0, x1, y1 = s["x"] - w / 2, s["y"] - h, s["x"] + w / 2, s["y"]
        self.poly([s["x"] - 10, y1, s["x"] + 10, y1, s["x"], y1 + 16], fill=SURFACE, outline=WARNING, width=2)
        self.rrect(x0, y0, x1, y1, r=12, fill=SURFACE, outline=WARNING, width=2)
        self.text(s["x"], (y0 + y1) / 2, text=s["text"], fill=WARNING, font=(FONT, 14, "bold"))

    def draw_player(self):
        x, y = self.player_x, self.player_y
        cx = x + PLAYER_W / 2
        flip = self.facing < 0

        # shadow on the ground
        if self.on_ground:
            sw = PLAYER_W * 1.15
            self.oval(cx - sw / 2, y + PLAYER_H - 8, cx + sw / 2, y + PLAYER_H + 10,
                      fill=SHADOW_COLOR, outline="")

        # choose animation frame from motion state
        if not self.on_ground:
            frame = "player_jump" if self.vy < 0 else "player_fall"
        elif abs(self.vx) > 0.6:
            frame = f"player_run_{(self.frame_count // 5) % 4}"
        else:
            frame = "player_idle_1" if (self.frame_count // 10) % 12 == 0 else "player_idle_0"

        self.blit(frame, cx, y + PLAYER_H, PLAYER_H, anchor="s", flip=flip)

    def draw_frame(self):
        self.update_transform()
        self.canvas.delete("all")
        self._img_refs = []
        self.buttons = []
        self.draw_bg(PLAY_BG_TOP, PLAY_BG_BOTTOM, "play")

        for gx in range(0, WIDTH, 170):
            self.line([gx, 0, gx, HEIGHT], fill=BORDER_SOFT)
        for gy in range(0, HEIGHT, 170):
            self.line([0, gy, WIDTH, gy], fill=BORDER_SOFT)

        for p in self.platforms:
            self.draw_platform(p)

        for hz in self.hazards:
            self.draw_spike(hz)

        for mv in self.movers:
            self.draw_saw(mv)

        for d in self.dart_traps:
            if d["arrow_x"] is not None:
                self.draw_dart(d)

        for fg in self.fake_goals:
            self.draw_goal(fg, fake=True)
        self.draw_goal(self.goal)

        for s in self.signs:
            self.draw_sign(s)

        self.draw_player()
        self.draw_hud()

        if self.state == "paused":
            self.draw_pause_overlay()
        elif self.state in ("lost", "won", "complete"):
            self.draw_overlay()

    # -- overlays -------------------------------------------------------

    def _overlay_dim(self):
        # translucent-ish darkening via a solid panel behind content
        self.rect(0, 0, WIDTH, HEIGHT, fill="#05070f", outline="", stipple="gray50")

    def draw_pause_overlay(self):
        self._overlay_dim()
        w0, h0, w1, h1 = WIDTH / 2 - 320, HEIGHT / 2 - 300, WIDTH / 2 + 320, HEIGHT / 2 + 300
        self.rrect(w0 + 10, h0 + 14, w1 + 10, h1 + 14, r=28, fill=SHADOW_COLOR, outline="")
        self.rrect(w0, h0, w1, h1, r=28, fill=SURFACE, outline=ACCENT, width=3)
        self.text(WIDTH / 2, h0 + 70, text="PAUSED", fill=TEXT_PRIMARY, font=(FONT, 40, "bold"))
        self.rrect(WIDTH / 2 - 70, h0 + 104, WIDTH / 2 + 70, h0 + 110, r=3, fill=ACCENT, outline="")

        opts = self.pause_options()
        bw, bh, gap = 480, 76, 22
        top = h0 + 150
        for i, (label, action) in enumerate(opts):
            x0 = WIDTH / 2 - bw / 2
            y0 = top + i * (bh + gap)
            self._menu_button(f"pause{i}", label, x0, y0, x0 + bw, y0 + bh,
                              i == self.pause_index, action, primary=(i == 0))

    def draw_overlay(self):
        self._overlay_dim()
        specs = {
            "lost": (self.lose_reason, DANGER, "✖"),
            "won": ("LEVEL CLEARED", SUCCESS, "✓"),
            "complete": ("YOU BEAT LEVEL DEVIL-ISH", ACCENT, "★"),
        }
        title, color, glyph = specs[self.state]

        w0, h0, w1, h1 = WIDTH / 2 - 400, HEIGHT / 2 - 280, WIDTH / 2 + 400, HEIGHT / 2 + 280
        self.rrect(w0 + 10, h0 + 14, w1 + 10, h1 + 14, r=30, fill=SHADOW_COLOR, outline="")
        self.rrect(w0, h0, w1, h1, r=30, fill=SURFACE, outline=color, width=3)

        self.oval(WIDTH / 2 - 46, h0 + 44, WIDTH / 2 + 46, h0 + 136, fill=color, outline="")
        self.text(WIDTH / 2, h0 + 90, text=glyph, fill=BADGE_TEXT, font=(FONT, 40, "bold"))

        self.text(WIDTH / 2, h0 + 186, text=title, fill=TEXT_PRIMARY, font=(FONT, 30, "bold"))
        if self.state == "complete":
            self.text(WIDTH / 2, h0 + 232, text=f"Total deaths this session: {self.deaths}",
                      fill=TEXT_MUTED, font=(FONT, 20))

        opts = self.result_options()
        bw, bh, gap = 460, 74, 20
        top = h0 + 290
        for i, (label, action) in enumerate(opts):
            x0 = WIDTH / 2 - bw / 2
            y0 = top + i * (bh + gap)
            self._menu_button(f"res{i}", label, x0, y0, x0 + bw, y0 + bh,
                              i == self.result_index, action, primary=(i == 0))


if __name__ == "__main__":
    DevilishPlatformer()
