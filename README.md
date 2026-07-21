# leveldevilish

A small Python platformer inspired by the punishing, trap-filled feel of Level Devil.

## Run it

From this folder, run:

```bash
python game.py
```

## Controls

- Left / Right or A / D: move
- Up / W / Space: jump
- Enter or Space: confirm / start / restart / next level
- Escape: back to level select
- Mouse click: also works on the title, level select, and end-of-level screens

## Levels

Beat a level to unlock the next one (progress is saved to `savegame.json`). Each level plays a different dirty trick:

1. **First Steps** — a gentle intro, with one platform that crumbles if you linger.
2. **Blink and You Fall** — platforms flicker between solid and see-through; time your jumps.
3. **Trust Issues** — a sign points you at "safe" ground, and a second green portal that isn't the real one.
4. **Dart Corridor** — invisible tripwires fire darts down the corridor as you pass.
5. **Saw Gauntlet** — patrolling saw blades mixed with a blinking platform.
6. **Chaos Gauntlet** — fully randomized every attempt: platform types, hazards, saws, darts, and decoy portals are reshuffled each time you play it, so it can't be memorized.

The goal is always to reach the green portal — assuming it's the real one.
