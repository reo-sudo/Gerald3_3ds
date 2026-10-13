#!/usr/bin/env python3
"""Render the real game code on a PC and stitch 3DS-style screenshots (top 400x240 over bottom 320x240).
   usage: python3 tools/preview/run_preview.py [outdir]
"""
import os, struct, subprocess, sys
import numpy as np
from PIL import Image

root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
out = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(root, 'work', 'preview'))
os.makedirs(out, exist_ok=True)
for n in ('sprites', 'bg', 'ui'):                      # PNG atlas -> raw RGBA the stub can load
    im = Image.open(os.path.join(root, 'gfx', n + '.png')).convert('RGBA')
    with open(os.path.join(out, n + '.rgba'), 'wb') as f:
        f.write(struct.pack('<II', *im.size)); f.write(im.tobytes())
exe = os.path.join(out, 'preview')
subprocess.check_call(['cc', '-std=gnu11', '-O1', '-w', '-I', os.path.join(root, 'tools/preview/stub'),
                       '-I', os.path.join(root, 'source'), os.path.join(root, 'tools/preview/preview_main.c'),
                       os.path.join(root, 'source/gerald.c'), '-lm', '-o', exe])
env = dict(os.environ, PREVIEW_DIR=out)
subprocess.check_call([exe, out], cwd=out, env=env)
names = sorted({f[:-8] for f in os.listdir(out) if f.endswith('_top.ppm')})
for n in names:
    top = np.array(Image.open(os.path.join(out, n + '_top.ppm')))
    bot = np.array(Image.open(os.path.join(out, n + '_bot.ppm')))
    canvas = np.full((480, 400, 3), 24, np.uint8)
    canvas[:240] = top
    canvas[240:, 40:360] = bot
    Image.fromarray(canvas).save(os.path.join(out, n + '.png'))
print('wrote', len(names), 'screenshots to', out)
