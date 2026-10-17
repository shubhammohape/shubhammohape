"""Procedural surface textures as tiny seamless PNGs (standard library only).

Each tile is gray+alpha: white pixels lighten, black pixels darken, alpha is the strength.
Dropped over a flat fill at low opacity they give concrete grain and brushed-steel streaks
without any SVG filter, so the animated image stays cheap to repaint.
"""
import base64
import math
import random
import struct
import zlib


def _png_la(w, h, rows):
    raw = b"".join(b"\x00" + bytes(r) for r in rows)

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 4, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def _lattice(rng, nx, ny):
    return [[rng.uniform(-1, 1) for _ in range(nx)] for _ in range(ny)]


def _vnoise(lat, x, y, w, h):
    """Wrapping bilinear value noise; x,y in pixels of a w*h tile."""
    ny, nx = len(lat), len(lat[0])
    gx, gy = x / w * nx, y / h * ny
    x0, y0 = int(gx) % nx, int(gy) % ny
    x1, y1 = (x0 + 1) % nx, (y0 + 1) % ny
    tx, ty = gx - int(gx), gy - int(gy)
    tx, ty = tx * tx * (3 - 2 * tx), ty * ty * (3 - 2 * ty)
    a = lat[y0][x0] * (1 - tx) + lat[y0][x1] * tx
    b = lat[y1][x0] * (1 - tx) + lat[y1][x1] * tx
    return a * (1 - ty) + b * ty


def _encode(w, h, field, strength):
    rows = []
    for y in range(h):
        row = []
        for x in range(w):
            n = max(-1.0, min(1.0, field(x, y)))
            row += [255 if n > 0 else 0, int(min(255, abs(n) * strength * 255))]
        rows.append(row)
    return "data:image/png;base64," + base64.b64encode(_png_la(w, h, rows)).decode()


def concrete(seed=7, size=96, strength=0.9):
    """Mottled concrete: soft blotches, fine grain and a few pits."""
    rng = random.Random(seed)
    big, mid = _lattice(rng, 4, 4), _lattice(rng, 12, 12)
    pits = {(rng.randrange(size), rng.randrange(size)): rng.choice((-1, -1, -1, 1)) for _ in range(int(size * size * 0.01))}

    def field(x, y):
        v = 0.30 * _vnoise(big, x, y, size, size) + 0.30 * _vnoise(mid, x, y, size, size) + 0.28 * rng.uniform(-1, 1)
        return v + 0.55 * pits.get((x, y), 0)

    return _encode(size, size, field, strength)


def brushed(seed=3, w=64, h=96, strength=0.9):
    """Anisotropic streaks that run vertically, like a rolled and brushed steel sheet."""
    rng = random.Random(seed)
    cols = [rng.uniform(-1, 1) for _ in range(w)]
    smooth = [(cols[i - 1] + 2 * cols[i] + cols[(i + 1) % w]) / 4 for i in range(w)]
    slow = _lattice(rng, 3, 5)

    def field(x, y):
        return smooth[x] * (0.75 + 0.25 * _vnoise(slow, x, y, w, h)) + 0.12 * rng.uniform(-1, 1)

    return _encode(w, h, field, strength)
