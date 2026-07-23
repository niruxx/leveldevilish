# leveldevilish

A small Python platformer inspired by the punishing, trap-filled feel of Level Devil.
Now with a hand-made pixel-art hero, a start menu, a world-map level select, and an
in-game pause menu.

## Run it

From this folder, run:

```bash
python game.py
```

Requires only Python 3 with Tkinter (bundled with the standard CPython installer).

## Controls

- **A / D** or **Left / Right**: move (with acceleration + friction, so it slides a little)
- **W / Space / Up**: jump — *hold for a higher jump, tap for a short hop*
- **Esc / P**: pause (opens the in-game pause menu)
- **Enter / Space**: confirm menu selections
- **Mouse**: every menu, map node, and button is clickable, and hovering highlights it
- On the world map: **1–6** jumps straight to an unlocked level

### Movement feel ("pixel man" mechanics)

The character now moves like a proper retro platformer hero:

- **Acceleration & friction** instead of instant start/stop.
- **Variable jump height** — release jump early to hop, hold it to leap.
- **Coyote time** — a few frames of grace to still jump just after walking off a ledge.
- **Jump buffering** — a jump pressed slightly before landing still fires on touchdown.
- **Fall-speed cap** for a controlled, readable descent.
- **State-driven sprite animation**: idle (with an occasional blink), a 4-frame run
  cycle, plus distinct jump and fall poses, mirrored to face either direction.

## Screens

- **Start menu** — Play, How to Play (control card), and Quit, with the hero idling beside the title.
- **World map** — levels are nodes on a winding, dotted path. Locked levels show a padlock,
  cleared levels get a flag, and the selected level pulses. A panel shows the level name/status
  with a Play button.
- **Pause menu** — Resume, Restart Level, World Map, or Main Menu.
- **Result overlays** — try again / next level / replay / back to map.

## Assets

All art is pixel-art PNG, kept in the [`assets/`](assets/) folder and generated
procedurally by [`generate_assets.py`](generate_assets.py). To regenerate or tweak the art:

```bash
python generate_assets.py
```

It writes the hero animation frames, tiles, hazards (spike, spinning saw, dart), portals
(real and fake), stars, and map icons (flag/lock/check), plus an `_preview.png` sheet
showing everything at once. The game loads these at startup and upscales them crisply with
nearest-neighbour zoom, so the pixels stay sharp at any window size. If the `assets/` folder
is missing, the game still runs — sprites simply won't be drawn.

## Levels

Beat a level to unlock the next one (progress is saved to `savegame.json`). Each level plays a different dirty trick:

1. **First Steps** — a gentle intro, with one platform that crumbles if you linger.
2. **Blink and You Fall** — platforms flicker between solid and see-through; time your jumps.
3. **Trust Issues** — a sign points you at "safe" ground, and a second green portal that isn't the real one.
4. **Dart Corridor** — invisible tripwires fire darts down the corridor as you pass.
5. **Saw Gauntlet** — patrolling saw blades mixed with a blinking platform.
6. **Chaos Gauntlet** — fully randomized every attempt: platform types, hazards, saws, darts, and decoy portals are reshuffled each time you play it, so it can't be memorized.

The goal is always to reach the green portal — assuming it's the real one.
