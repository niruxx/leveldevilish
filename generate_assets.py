"""
Pixel-art asset generator for Level Devil-ish.

Run this once (``python generate_assets.py``) to (re)create every PNG the game
loads from the ``assets/`` folder. Everything here is procedural, so the art is
fully reproducible and easy to tweak: change a colour or a block and re-run.

Technique: we draw filled silhouettes in body colours onto a small pixel grid,
then a single "outline pass" wraps every shape in a 1px dark edge automatically.
That keeps hand-authoring simple while giving a consistent chunky pixel look.
"""

import math
import os
import tkinter as tk

ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------

OUT = "#120f1c"          # universal outline
SKIN = "#f7c780"
SKIN_SH = "#d98e3d"
HAIR = "#7a4a24"
HAIR_HI = "#9a5f30"
EYE = "#151020"
SHIRT = "#6c6cf5"
SHIRT_SH = "#4a49c8"
SHIRT_HI = "#9aa0ff"
PANTS = "#2b3566"
PANTS_SH = "#1e2547"
SHOE = "#d5deea"
SHOE_SH = "#9aa6bd"

BRICK = "#3b4675"
BRICK_HI = "#556098"
BRICK_SH = "#28305a"
BRICK_LINE = "#20264a"

SPIKE = "#f2606a"
SPIKE_HI = "#ffb3b8"
SPIKE_SH = "#b0323c"

STEEL = "#aab6cc"
STEEL_HI = "#e6ecf7"
STEEL_SH = "#69748f"
STEEL_CORE = "#3a4260"

PORTAL_CORE = "#eafff4"
PORTAL_1 = "#5ff0b0"
PORTAL_2 = "#2bbd82"
PORTAL_3 = "#0f7d57"

GOLD = "#ffcf4d"
GOLD_SH = "#c8930f"

STAR = "#c9d2ff"
SUCCESS_GREEN = "#34d399"


# ---------------------------------------------------------------------------
# Tiny pixel canvas
# ---------------------------------------------------------------------------

class Grid:
    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.px = [[None] * w for _ in range(h)]

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h and c is not None:
            self.px[y][x] = c

    def rect(self, x0, y0, x1, y1, c):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self.set(x, y, c)

    def hline(self, x0, x1, y, c):
        for x in range(x0, x1 + 1):
            self.set(x, y, c)

    def vline(self, x, y0, y1, c):
        for y in range(y0, y1 + 1):
            self.set(x, y, c)

    def get(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.px[y][x]
        return None

    def outline(self, color=OUT):
        """Add a 1px outline around every filled region (into empty cells)."""
        adds = []
        for y in range(self.h):
            for x in range(self.w):
                if self.px[y][x] is not None:
                    continue
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1),
                               (1, 1), (1, -1), (-1, 1), (-1, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < self.w and 0 <= ny < self.h and self.px[ny][nx] is not None \
                            and self.px[ny][nx] != color:
                        adds.append((x, y))
                        break
        for x, y in adds:
            self.px[y][x] = color

    def to_photo(self):
        img = tk.PhotoImage(width=self.w, height=self.h)
        # Build one row string at a time for speed; transparent cells are skipped
        # by writing them individually is slow, so we render opaque runs.
        for y in range(self.h):
            x = 0
            row = self.px[y]
            while x < self.w:
                if row[x] is None:
                    x += 1
                    continue
                run_c = row[x]
                x0 = x
                while x < self.w and row[x] == run_c:
                    x += 1
                img.put(run_c, to=(x0, y, x, y + 1))
        return img


def save(grid, name):
    img = grid.to_photo()
    path = os.path.join(ASSET_DIR, name)
    img.write(path, format="png")
    return img


# ---------------------------------------------------------------------------
# Hero
# ---------------------------------------------------------------------------

HERO_W, HERO_H = 16, 24


def hero_base():
    """Filled hero silhouette, facing right. Legs/arms drawn by caller."""
    g = Grid(HERO_W, HERO_H)
    # Head (skin)
    g.rect(5, 3, 10, 8, SKIN)
    g.vline(4, 4, 7, SKIN)
    g.vline(11, 4, 7, SKIN)
    # skin shading on the left/underside
    g.vline(5, 5, 8, SKIN_SH)
    g.hline(5, 10, 8, SKIN_SH)
    # Hair
    g.rect(5, 2, 10, 3, HAIR)
    g.vline(4, 3, 5, HAIR)
    g.vline(11, 3, 4, HAIR)
    g.set(6, 2, HAIR_HI)
    g.set(8, 2, HAIR_HI)
    # Eyes (facing right -> toward higher x)
    g.set(8, 6, EYE)
    g.set(10, 6, EYE)
    # Torso (shirt)
    g.rect(5, 9, 10, 15, SHIRT)
    g.vline(5, 9, 15, SHIRT_SH)
    g.hline(6, 9, 9, SHIRT_HI)
    g.set(9, 11, SHIRT_HI)
    return g


def draw_arm(g, x, y0, y1, front):
    col = SHIRT if front else SHIRT_SH
    g.vline(x, y0, y1 - 1, col)
    g.set(x, y1, SKIN)  # hand


def draw_leg(g, x, y0, y1, foot_dx):
    g.vline(x, y0, y1, PANTS)
    g.vline(x, y0, y0, PANTS_SH if x < 8 else PANTS)
    # shoe
    fx = x + foot_dx
    g.set(x, y1 + 1, SHOE)
    g.set(fx, y1 + 1, SHOE)
    g.set(fx, y1 + 1, SHOE_SH if foot_dx < 0 else SHOE)


def hero_frame(pose):
    g = hero_base()
    # arms
    if pose == "jump":
        # arms up
        g.vline(4, 7, 10, SHIRT_SH); g.set(4, 6, SKIN)
        g.vline(11, 7, 10, SHIRT); g.set(11, 6, SKIN)
    elif pose == "fall":
        g.vline(3, 10, 12, SHIRT_SH); g.set(3, 13, SKIN)
        g.vline(12, 10, 12, SHIRT); g.set(12, 13, SKIN)
    else:
        draw_arm(g, 4, 10, 13, front=False)
        draw_arm(g, 11, 10, 13, front=True)

    # legs per pose
    if pose in ("idle0", "idle1"):
        draw_leg(g, 6, 16, 20, -1)
        draw_leg(g, 9, 16, 20, +1)
    elif pose == "run0":
        draw_leg(g, 5, 16, 19, -1)
        draw_leg(g, 10, 16, 21, +2)
    elif pose == "run1":
        draw_leg(g, 6, 16, 21, 0)
        draw_leg(g, 9, 16, 20, +1)
    elif pose == "run2":
        draw_leg(g, 7, 16, 21, +2)
        draw_leg(g, 10, 16, 19, +1)
    elif pose == "run3":
        draw_leg(g, 6, 16, 20, -1)
        draw_leg(g, 9, 16, 21, 0)
    elif pose == "jump":
        draw_leg(g, 6, 16, 19, -1)
        draw_leg(g, 9, 16, 18, +1)
    elif pose == "fall":
        draw_leg(g, 5, 16, 20, -2)
        draw_leg(g, 10, 16, 20, +2)

    # tiny idle bob: idle1 nudges head/eyes look already fine; add blink variant
    if pose == "idle1":
        g.set(8, 6, SKIN_SH)  # half-closed eye
        g.set(10, 6, SKIN_SH)

    g.outline()
    return g


def build_hero():
    frames = {
        "player_idle_0": "idle0",
        "player_idle_1": "idle1",
        "player_run_0": "run0",
        "player_run_1": "run1",
        "player_run_2": "run2",
        "player_run_3": "run3",
        "player_jump": "jump",
        "player_fall": "fall",
    }
    for name, pose in frames.items():
        save(hero_frame(pose), name + ".png")


# ---------------------------------------------------------------------------
# Tiles & hazards
# ---------------------------------------------------------------------------

def build_brick():
    g = Grid(16, 16)
    g.rect(0, 0, 15, 15, BRICK)
    g.hline(0, 15, 0, BRICK_HI)
    g.vline(0, 0, 15, BRICK_HI)
    g.hline(0, 15, 15, BRICK_SH)
    g.vline(15, 0, 15, BRICK_SH)
    # brick mortar lines (offset courses)
    g.hline(0, 15, 5, BRICK_LINE)
    g.hline(0, 15, 10, BRICK_LINE)
    g.vline(7, 1, 4, BRICK_LINE)
    g.vline(3, 6, 9, BRICK_LINE)
    g.vline(11, 6, 9, BRICK_LINE)
    g.vline(7, 11, 14, BRICK_LINE)
    save(g, "brick.png")


def build_crumble():
    g = Grid(16, 16)
    g.rect(0, 0, 15, 15, "#7c4a12")
    g.hline(0, 15, 0, "#a4671e")
    g.vline(0, 0, 15, "#a4671e")
    g.hline(0, 15, 15, "#563008")
    g.vline(15, 0, 15, "#563008")
    # cracks
    g.set(4, 2, OUT); g.set(5, 3, OUT); g.set(4, 4, OUT); g.set(5, 5, OUT)
    g.set(10, 3, OUT); g.set(11, 4, OUT); g.set(10, 5, OUT); g.set(11, 6, OUT)
    g.set(7, 8, OUT); g.set(8, 9, OUT); g.set(7, 10, OUT); g.set(8, 11, OUT); g.set(7, 12, OUT)
    g.set(12, 10, OUT); g.set(13, 11, OUT)
    save(g, "crumble.png")


def build_spike():
    g = Grid(16, 16)
    # base
    g.rect(1, 13, 14, 15, STEEL_SH)
    # three spikes
    for cx in (3, 8, 13):
        for i, y in enumerate(range(13, 3, -1)):
            half = max(0, (i) // 2)
            g.hline(cx - half, cx + half, y, SPIKE)
        g.vline(cx, 4, 12, SPIKE_HI)
        g.set(cx + 1, 12, SPIKE_SH)
    g.outline()
    save(g, "spike.png")


def build_saw():
    """Circular saw, several rotation frames (rasterized)."""
    N, R = 20, 20
    for f in range(4):
        g = Grid(N, N)
        cx = cy = (N - 1) / 2
        a0 = f * (360 / 8 / 4)  # small step so it visibly spins
        teeth = 8
        for yy in range(N):
            for xx in range(N):
                dx, dy = xx - cx, yy - cy
                dist = math.hypot(dx, dy)
                ang = math.degrees(math.atan2(dy, dx)) + a0
                tooth = (math.sin(math.radians(ang * teeth)) + 1) / 2
                r_edge = R / 2 * (0.78 + 0.22 * tooth)
                if dist <= r_edge:
                    if dist <= R * 0.14:
                        g.set(xx, yy, STEEL_SH)     # hub hole
                    elif dist <= R * 0.24:
                        g.set(xx, yy, STEEL_HI)      # hub ring
                    elif dist >= r_edge - 1.6:
                        g.set(xx, yy, STEEL_HI)      # bright cutting edge
                    else:
                        g.set(xx, yy, STEEL)
        g.outline()
        save(g, f"saw_{f}.png")


def build_dart():
    g = Grid(14, 8)
    # shaft
    g.rect(1, 3, 9, 4, GOLD)
    g.hline(1, 9, 3, GOLD_SH)
    # head
    g.set(10, 2, GOLD); g.set(11, 3, GOLD); g.set(12, 3, GOLD)
    g.set(10, 5, GOLD); g.set(11, 4, GOLD); g.set(12, 4, GOLD)
    g.set(13, 3, GOLD); g.set(13, 4, GOLD)
    # fletching
    g.set(0, 2, SPIKE); g.set(0, 5, SPIKE); g.set(1, 2, SPIKE); g.set(1, 5, SPIKE)
    g.outline()
    save(g, "dart.png")


def build_portal():
    W, H = 16, 24
    for f in range(4):
        g = Grid(W, H)
        cx = (W - 1) / 2
        phase = f / 4 * math.tau
        for yy in range(2, H - 2):
            ty = (yy - 2) / (H - 4)
            width = 2 + 4.5 * math.sin(ty * math.pi)
            wob = 0.9 * math.sin(ty * 6 + phase)
            cxx = cx + wob
            for xx in range(W):
                d = abs(xx - cxx)
                if d <= width:
                    if d <= width * 0.35:
                        g.set(xx, yy, PORTAL_CORE)
                    elif d <= width * 0.7:
                        g.set(xx, yy, PORTAL_1)
                    else:
                        g.set(xx, yy, PORTAL_2)
        # sparkle
        sy = int(4 + (H - 8) * ((f / 4 + 0.2) % 1))
        g.set(int(cx), sy, PORTAL_CORE)
        g.outline(PORTAL_3)
        save(g, f"portal_{f}.png")


def build_fake_portal():
    """Looks like a portal but tinted 'off' / reddish — a lie."""
    W, H = 16, 24
    g = Grid(W, H)
    cx = (W - 1) / 2
    for yy in range(2, H - 2):
        ty = (yy - 2) / (H - 4)
        width = 2 + 4.5 * math.sin(ty * math.pi)
        for xx in range(W):
            d = abs(xx - cx)
            if d <= width:
                if d <= width * 0.35:
                    g.set(xx, yy, "#ffe1b0")
                elif d <= width * 0.7:
                    g.set(xx, yy, "#f0a35f")
                else:
                    g.set(xx, yy, "#c85a3a")
    g.outline("#6e2a1c")
    save(g, "portal_fake.png")


# ---------------------------------------------------------------------------
# Decor & map icons
# ---------------------------------------------------------------------------

def build_stars():
    for i, col in enumerate([STAR, "#8f9bd8", "#e7ecff"]):
        g = Grid(7, 7)
        g.set(3, 0, col); g.set(3, 6, col)
        g.set(0, 3, col); g.set(6, 3, col)
        g.set(3, 3, "#ffffff")
        g.set(2, 2, col); g.set(4, 2, col); g.set(2, 4, col); g.set(4, 4, col)
        save(g, f"star_{i}.png")


def build_flag():
    g = Grid(16, 16)
    g.vline(4, 1, 15, "#c8cede")   # pole
    g.vline(5, 1, 15, STEEL_SH)
    # banner
    g.rect(6, 1, 13, 6, SUCCESS_GREEN)
    g.hline(6, 13, 1, "#9af5cf")
    g.set(13, 3, "#0f7d57")
    g.outline()
    save(g, "flag.png")


def build_lock():
    g = Grid(16, 16)
    # shackle
    g.hline(5, 10, 3, "#7d86ad")
    g.vline(5, 3, 6, "#7d86ad")
    g.vline(10, 3, 6, "#7d86ad")
    # body
    g.rect(4, 7, 11, 14, "#565f82")
    g.hline(4, 11, 7, "#7d86ad")
    g.set(7, 10, OUT); g.set(8, 10, OUT)
    g.set(7, 11, OUT); g.set(8, 11, OUT)
    g.set(7, 12, OUT)
    g.outline()
    save(g, "lock.png")


def build_check():
    g = Grid(16, 16)
    g.set(3, 8, SUCCESS_GREEN); g.set(4, 9, SUCCESS_GREEN); g.set(5, 10, SUCCESS_GREEN)
    g.set(6, 11, SUCCESS_GREEN)
    g.set(7, 10, SUCCESS_GREEN); g.set(8, 9, SUCCESS_GREEN); g.set(9, 8, SUCCESS_GREEN)
    g.set(10, 7, SUCCESS_GREEN); g.set(11, 6, SUCCESS_GREEN); g.set(12, 5, SUCCESS_GREEN)
    g.outline()
    save(g, "check.png")


# ---------------------------------------------------------------------------
# Preview sheet (so we can eyeball everything at once)
# ---------------------------------------------------------------------------

def build_preview():
    names = [
        "player_idle_0", "player_idle_1", "player_run_0", "player_run_1",
        "player_run_2", "player_run_3", "player_jump", "player_fall",
        "brick", "crumble", "spike", "saw_0", "saw_1", "dart",
        "portal_0", "portal_1", "portal_fake", "star_0", "flag", "lock", "check",
    ]
    zoom = 6
    pad = 6
    cell = 24 * zoom + pad
    cols = 8
    rows = (len(names) + cols - 1) // cols
    W = cols * cell + pad
    H = rows * cell + pad
    sheet = tk.PhotoImage(width=W, height=H)
    sheet.put("#181d33", to=(0, 0, W, H))
    for i, n in enumerate(names):
        img = tk.PhotoImage(file=os.path.join(ASSET_DIR, n + ".png"))
        z = img.zoom(zoom)
        r, c = divmod(i, cols)
        ox = pad + c * cell
        oy = pad + r * cell
        for yy in range(z.height()):
            for xx in range(z.width()):
                if not z.transparency_get(xx, yy):
                    sheet.put(_hex(z.get(xx, yy)), to=(ox + xx, oy + yy))
    sheet.write(os.path.join(ASSET_DIR, "_preview.png"), format="png")


def _hex(rgb):
    return "#%02x%02x%02x" % (rgb[0], rgb[1], rgb[2])


def main():
    os.makedirs(ASSET_DIR, exist_ok=True)
    root = tk.Tk()
    root.withdraw()
    build_hero()
    build_brick()
    build_crumble()
    build_spike()
    build_saw()
    build_dart()
    build_portal()
    build_fake_portal()
    build_stars()
    build_flag()
    build_lock()
    build_check()
    build_preview()
    root.destroy()
    print("Assets written to", ASSET_DIR)


if __name__ == "__main__":
    main()
