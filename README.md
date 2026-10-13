# Gerald 🐸 — a pixel-art virtual pet for the Nintendo 3DS

Raise Gerald the frog from a jelly egg to a wise old elder. Feed him, play with him, keep his pond clean, put him to bed.
Dual-screen: the pond on the top screen, a wooden pixel-art control panel on the touch screen.

## Getting the .cia (GitHub Actions)

1. Create an empty GitHub repo and push this folder to it (`main` branch).
2. Open the **Actions** tab → **Build Gerald (.cia + .3dsx)**. It runs on every push (or press *Run workflow*).
3. When it's green, open the run and download the **gerald-3ds** artifact → unzip → `gerald.cia` (+ `gerald.3dsx` for the Homebrew Launcher).
4. Copy `gerald.cia` to your SD card and install it with **FBI** (*SD → gerald.cia → Install and delete CIA*).
5. Tag a release (`git tag v1.0 && git push --tags`) and the workflow attaches both files to a GitHub Release automatically.

Under the hood the workflow runs in the `devkitpro/devkitarm` container, installs `3ds-dev` (libctru, citro2d/3d, tex3ds…), grabs
`makerom` + `bannertool` (`tools/get_cia_tools.sh`, falls back to building them from source), runs the pet-simulation unit tests,
then `make` produces the `.3dsx` and the `.cia` (with the banner, icon and all sounds/graphics packed in RomFS).

## Sound needs your DSP firmware

3DS sound goes through the DSP. If your console has never had its DSP firmware dumped (the *DSP1* homebrew app does this once),
Gerald still runs — just silently. Luma3DS users usually have this already.

## How to play

| | |
|---|---|
| **D-Pad ◀ ▶ / A** or **touch** | pick and press a button on the panel |
| **B** | back out of a menu |
| **Tap Gerald's portrait** | pet him (ribbit!) |
| **SELECT** | music on/off |
| **START** | save and quit (it also autosaves every 30 s and after every action) |

Buttons: **FEED** (meal or snack) · **PLAY** (fly-catching mini-game: tap the flies on the touch screen, 20 s) · **CLEAN** (poop + bath) ·
**LIGHTS** (put him to sleep; he wakes at full energy) · **MEDS** (cure sickness / wake him if he fainted) · **INFO** (stats).

* The egg hatches ~45 s after you start. Life stages: **egg → tadpole → froglet (4 h) → frog (1 day) → elder (5 days)**.
* Stats: Belly, Joy, Clean, Energy, Health. Neglect them and Gerald gets sick; ignore *that* and he faints — he never dies, medicine always brings him back.
* Gerald keeps living while the 3DS is off or closed: time that passes is simulated at half speed, capped at 10 h, so leaving him asleep overnight is perfectly fine. (Age always keeps counting.)
* Save file: `sdmc:/3ds/gerald/save.dat`. Delete it, or hold **L+R** and press **X** on the INFO screen, to start over with a new egg.
* Cheats for testing: hold **L+R**, then **Y** = +1 hour, **X** = +1 day (watch him grow up).

## Project layout

```
source/main.c        graphics (citro2d), UI, audio (NDSP), input, mini-game
source/gerald.c/.h   the pet simulation — plain C, unit-tested on a PC (tools/test_gerald.c)
source/atlas.h       GENERATED sprite coordinates (by tools/make_art.py)
gfx/                 sprites.png / bg.png / ui.png sprite sheets + .t3s descriptors
romfs/snd/           sound effects + music (raw 16-bit mono, 22.05 kHz)
banner/              HOME-menu banner.png, banner.wav, icon.png
cia/gerald.rsf       makerom settings (title id, permissions, RomFS)
tools/make_art.py    generates ALL pixel art (frog, UI kit, backgrounds, banner, icon)
tools/make_sound.py  synthesises ALL sounds (chiptune, no samples)
```

Change the art or sounds by editing the Python scripts and re-running them (`pip install pillow numpy`):

```
python3 tools/make_art.py
python3 tools/make_sound.py
```

Tuning knobs (decay rates, growth ages, offline cap…) are the `#define`s at the top of `source/gerald.c`.
Run the simulation tests on a PC with:

```
cc -Wall -Isource tools/test_gerald.c source/gerald.c -o /tmp/t && /tmp/t
```

See what the screens look like without a 3DS (renders the real `main.c` on a PC and saves screenshots to `work/preview/`):

```
python3 tools/preview/run_preview.py
```

Building locally instead of on GitHub: install devkitPro with `3ds-dev`, run `./tools/get_cia_tools.sh`, then `make`.

Change `UniqueId` in `cia/gerald.rsf` if it ever clashes with another title you have installed.
