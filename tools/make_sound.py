#!/usr/bin/env python3
"""
Synthesises every sound for Gerald (chiptune style) -- no samples, no licences.

  romfs/snd/*.raw    signed 16-bit little-endian mono PCM @ 22050 Hz (loaded by NDSP)
  banner/banner.wav  <=3 s jingle played on the HOME menu while the banner is shown

Re-run after tweaking:  python3 tools/make_sound.py
Needs: numpy
"""
import os
import wave

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SR = 22050
rng = np.random.default_rng(7)


def t_(d):
    return np.arange(int(SR * d)) / SR


def env(n, a=0.005, r=0.08, curve=2.0):
    """attack/release envelope"""
    e = np.ones(n)
    na, nr = max(1, int(SR * a)), max(1, int(SR * r))
    e[:na] = np.linspace(0, 1, na)
    nr = min(nr, n)
    e[-nr:] *= np.linspace(1, 0, nr) ** curve
    return e


def square(f, duty=0.5):
    ph = (np.cumsum(f) / SR) % 1.0
    return np.where(ph < duty, 1.0, -1.0)


def tri(f):
    ph = (np.cumsum(f) / SR) % 1.0
    return 4 * np.abs(ph - 0.5) - 1


def sine(f):
    return np.sin(2 * np.pi * np.cumsum(f) / SR)


def noise(n):
    return rng.uniform(-1, 1, n)


def lowpass(x, k):
    c = np.cumsum(np.insert(x, 0, 0))
    y = (c[k:] - c[:-k]) / k
    return np.concatenate([np.full(k - 1, y[0]), y])


def note(freq, d, wave_fn=square, a=0.004, r=0.05, vol=0.5, **kw):
    n = int(SR * d)
    f = np.full(n, freq, float) if np.isscalar(freq) else freq
    return wave_fn(f, **kw) * env(n, a, r) * vol


def seq(notes, gap=0.0):
    out = []
    for n in notes:
        out.append(n)
        if gap:
            out.append(np.zeros(int(SR * gap)))
    return np.concatenate(out)


def mix(*tracks):
    n = max(len(t) for t in tracks)
    o = np.zeros(n)
    for t in tracks:
        o[:len(t)] += t
    return o


def at(x, start, total):
    o = np.zeros(int(SR * total))
    s = int(SR * start)
    o[s:s + len(x)] += x[:max(0, len(o) - s)]
    return o


def save(name, x, peak=0.8, folder='romfs/snd'):
    x = x / max(1e-6, np.max(np.abs(x))) * peak
    x[:48] *= np.linspace(0, 1, 48)   # no click on start
    pcm = (x * 32767).astype(np.int16)
    path = os.path.join(ROOT, folder, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if name.endswith('.wav'):
        with wave.open(path, 'wb') as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes(pcm.tobytes())
    else:
        pcm.tofile(path)
    return path


NOTE = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}


def hz(name):
    """'C4' -> 261.6, 'F#3' -> ..."""
    n = NOTE[name[0]]
    i = 1
    if name[i] == '#':
        n += 1
        i += 1
    elif name[i] == 'b':
        n -= 1
        i += 1
    octave = int(name[i:])
    return 440.0 * 2 ** ((n - 9 + 12 * (octave - 4)) / 12.0)


# ---------------------------------------------------------------- effects
def ribbit():
    """two throaty croaks: 'rib' - 'bit'"""
    def croak(f0, f1, d):
        n = int(SR * d)
        f = np.linspace(f0, f1, n)
        wob = 1 + 0.35 * np.sin(2 * np.pi * 38 * np.arange(n) / SR)   # throat flutter
        w = square(f * wob, 0.35) * 0.7 + tri(f * 0.5) * 0.5
        w = lowpass(w, 3)
        return w * env(n, 0.012, 0.06) * np.hanning(n) ** 0.5
    return seq([croak(210, 150, 0.14), np.zeros(int(SR * 0.04)), croak(260, 120, 0.2)])


def eat():
    out = []
    for i in range(3):
        n = int(SR * 0.09)
        body = noise(n) * np.linspace(1, 0, n) ** 2
        body = lowpass(body, 4) * 0.8
        pop = sine(np.linspace(300 - i * 30, 90, n)) * np.linspace(1, 0, n) ** 1.5
        out.append(body + pop * 0.8)
        out.append(np.zeros(int(SR * 0.05)))
    return np.concatenate(out)


def happy():
    ns = [hz('C5'), hz('E5'), hz('G5'), hz('C6')]
    return seq([note(f, 0.09, square, duty=0.25, r=0.03, vol=0.5) for f in ns[:-1]] +
               [note(ns[-1], 0.28, square, duty=0.25, r=0.2, vol=0.5)])


def sad():
    n = int(SR * 0.7)
    f = np.linspace(hz('E4'), hz('A3'), n)
    f = f * (1 + 0.02 * np.sin(2 * np.pi * 6 * np.arange(n) / SR))
    return tri(f) * env(n, 0.01, 0.4) * 0.7


def plop():
    n = int(SR * 0.22)
    f = np.linspace(520, 90, n) ** 1.0
    return sine(f) * np.exp(-np.arange(n) / SR * 14) + 0.1 * lowpass(noise(n), 6) * np.exp(-np.arange(n) / SR * 40)


def clean():
    notes = ['E6', 'G6', 'B6', 'E7', 'B6', 'G6', 'E7', 'G7']
    parts = [note(hz(n), 0.07, tri, r=0.05, vol=0.5) for n in notes]
    sparkle = lowpass(noise(int(SR * 0.6)), 2) * 0.05 * np.linspace(1, 0, int(SR * 0.6))
    return mix(seq(parts), sparkle)


def select():
    return note(880, 0.05, square, duty=0.25, r=0.03, vol=0.45)


def back():
    return seq([note(660, 0.04, square, duty=0.25, r=0.02, vol=0.4),
                note(440, 0.06, square, duty=0.25, r=0.04, vol=0.4)])


def confirm():
    return seq([note(hz('E5'), 0.05, square, duty=0.25, r=0.02, vol=0.45),
                note(hz('A5'), 0.09, square, duty=0.25, r=0.06, vol=0.45)])


def tongue():
    n = int(SR * 0.16)
    sweep = lowpass(noise(n), 3) * np.linspace(0.2, 1, n) * 0.5
    pop = sine(np.linspace(900, 350, int(SR * 0.05))) * np.linspace(1, 0, int(SR * 0.05))
    return np.concatenate([sweep * env(n, 0.002, 0.03), pop * 0.8])


def catch():
    return seq([note(hz('B5'), 0.06, square, duty=0.5, r=0.02, vol=0.4),
                note(hz('E6'), 0.2, square, duty=0.5, r=0.15, vol=0.4)])


def miss():
    n = int(SR * 0.15)
    return square(np.linspace(130, 80, n), 0.5) * env(n, 0.005, 0.1) * 0.5


def evolve():
    mel = ['C5', 'E5', 'G5', 'C6', 'G5', 'C6', 'E6', 'G6']
    dur = [0.09] * 7 + [0.5]
    lead = seq([note(hz(n), d, square, duty=0.25, r=min(0.05, d * .6), vol=0.45) for n, d in zip(mel, dur)])
    bass = seq([note(hz(n), d, tri, r=0.05, vol=0.5) for n, d in zip(['C3'] * 4 + ['G2'] * 3 + ['C3'], dur)])
    return mix(lead, bass)


def hatch():
    out = [np.zeros(1)]
    for i in range(3):
        n = int(SR * 0.05)
        out.append(lowpass(noise(n), 2) * np.linspace(1, 0, n) ** 2 * 0.9)
        out.append(np.zeros(int(SR * 0.08)))
    return np.concatenate(out + [evolve()])


def sick():
    n = int(SR * 0.6)
    f = hz('D4') * (1 + 0.06 * np.sin(2 * np.pi * 7 * np.arange(n) / SR)) * np.linspace(1, 0.7, n)
    return square(f, 0.5) * env(n, 0.01, 0.4) * 0.4


def alert():
    return seq([note(hz('A5'), 0.07, square, duty=0.125, r=0.02, vol=0.45),
                np.zeros(int(SR * 0.04)),
                note(hz('A5'), 0.07, square, duty=0.125, r=0.02, vol=0.45)])


def medicine():
    return seq([note(hz(n), 0.06, tri, r=0.04, vol=0.6) for n in ['G4', 'B4', 'D5', 'G5']] +
               [note(hz('B5'), 0.25, tri, r=0.2, vol=0.6)])


def lights_off():
    return seq([note(hz(n), 0.14, tri, r=0.12, vol=0.6) for n in ['G5', 'E5', 'C5', 'G4']])


def lights_on():
    return seq([note(hz(n), 0.1, tri, r=0.08, vol=0.6) for n in ['G4', 'C5', 'E5', 'G5']])


def gameover():
    mel = ['G5', 'E5', 'C5', 'G4', 'C5']
    return seq([note(hz(n), 0.11 if i < 4 else 0.35, square, duty=0.25, r=0.05, vol=0.4) for i, n in enumerate(mel)])


# ---------------------------------------------------------------- music
def music_day(bars=8, bpm=96):
    """cheerful pond tune: pentatonic lead over a walking triangle bass"""
    beat = 60.0 / bpm
    total = bars * 4 * beat
    chords = [('C3', 'G3'), ('A2', 'E3'), ('F2', 'C3'), ('G2', 'D3')] * (bars // 4)
    lead_pat = [
        ('E5', 1), ('G5', 1), ('A5', 1), ('G5', 1), ('E5', 2), ('D5', 1), ('C5', 1),
        ('D5', 1), ('E5', 1), ('G5', 2), ('E5', 1), ('D5', 1), ('C5', 2),
        ('A4', 1), ('C5', 1), ('D5', 1), ('E5', 1), ('G5', 2), ('E5', 2),
        ('D5', 1), ('C5', 1), ('D5', 1), ('E5', 1), ('D5', 4),
    ]
    out = np.zeros(int(SR * total))
    t = 0.0
    k = 0
    while t < total - 0.01:
        nm, b = lead_pat[k % len(lead_pat)]
        d = b * beat
        if t + d > total:
            d = total - t
        out += at(note(hz(nm), d * 0.92, square, duty=0.25, a=0.006, r=0.07, vol=0.22), t, total)[:len(out)]
        t += d
        k += 1
    for bar in range(bars):
        root, fifth = chords[bar % len(chords)]
        for b in range(4):
            fr = hz(root if b % 2 == 0 else fifth)
            out += at(note(fr, beat * 0.85, tri, a=0.004, r=0.08, vol=0.38), (bar * 4 + b) * beat, total)[:len(out)]
    # soft tick
    for i in range(bars * 4):
        n = int(SR * 0.02)
        tick = lowpass(noise(n), 3) * np.linspace(1, 0, n) ** 2 * 0.05
        out += at(tick, i * beat + (beat / 2 if i % 2 else 0), total)[:len(out)]
    out[-int(SR * 0.05):] *= np.linspace(1, 0, int(SR * 0.05))
    return out


def music_night(bars=4, bpm=60):
    """music-box lullaby"""
    beat = 60.0 / bpm
    total = bars * 4 * beat
    out = np.zeros(int(SR * total))
    mel = ['E5', 'G5', 'E5', 'D5', 'C5', 'D5', 'E5', None,
           'D5', 'E5', 'D5', 'B4', 'A4', 'B4', 'C5', None]
    for i in range(bars * 4):
        nm = mel[i % len(mel)]
        if nm is None:
            continue
        n = int(SR * beat * 1.8)
        f = hz(nm)
        x = (sine(np.full(n, f)) + 0.3 * sine(np.full(n, f * 3)) * np.exp(-np.arange(n) / SR * 8)) \
            * np.exp(-np.arange(n) / SR * 3.2)
        out += at(x * 0.45, i * beat, total)[:len(out)]
    for bar in range(bars):
        for j, nm in enumerate(['C3', 'G3', 'E3', 'G3'] if bar % 2 == 0 else ['A2', 'E3', 'C3', 'E3']):
            n = int(SR * beat * 1.6)
            x = sine(np.full(n, hz(nm))) * np.exp(-np.arange(n) / SR * 2.5) * 0.35
            out += at(x, (bar * 4 + j) * beat, total)[:len(out)]
    out[-int(SR * 0.05):] *= np.linspace(1, 0, int(SR * 0.05))
    return out


def banner_jingle():
    r = ribbit()
    arp = seq([note(hz(n), 0.1, square, duty=0.25, r=0.05, vol=0.35) for n in ['C5', 'E5', 'G5', 'C6']] +
              [note(hz('G5'), 0.4, square, duty=0.25, r=0.3, vol=0.35)])
    return mix(at(r, 0.1, 2.5), at(arp, 0.85, 2.5))[:int(SR * 2.4)]


def main():
    fx = {
        'ribbit': ribbit(), 'eat': eat(), 'happy': happy(), 'sad': sad(), 'plop': plop(),
        'clean': clean(), 'select': select(), 'back': back(), 'confirm': confirm(),
        'tongue': tongue(), 'catch': catch(), 'miss': miss(), 'evolve': evolve(),
        'hatch': hatch(), 'sick': sick(), 'alert': alert(), 'medicine': medicine(),
        'lights_off': lights_off(), 'lights_on': lights_on(), 'gameover': gameover(),
    }
    for name, x in fx.items():
        save(name + '.raw', x)
    save('bgm_day.raw', music_day(), peak=0.7)
    save('bgm_night.raw', music_night(), peak=0.7)
    save('banner.wav', banner_jingle(), peak=0.85, folder='banner')
    print('sounds written:', len(fx) + 2, 'raw files + banner.wav')


if __name__ == '__main__':
    main()
