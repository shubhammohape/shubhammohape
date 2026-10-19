#!/usr/bin/env python3
"""Dev-time tool: turn open fonts into vector glyph outlines for scripts/glyphdata.json.

GitHub serves README images through a proxy whose CSP blocks web fonts, so text in the profile
images is drawn as outlines. That also makes it identical on every device. Needs fontTools
(`pip install fonttools`); the generated JSON is committed, so the pipeline itself needs nothing.

Fonts (both SIL Open Font License 1.1, https://openfontlicense.org):
  IBM Plex Mono (Regular, Bold)  https://github.com/IBM/plex
  Saira Stencil One              https://github.com/Omnibus-Type/Saira-Stencil
"""
import json
import sys
import urllib.request
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

BASE = "https://raw.githubusercontent.com/google/fonts/main/ofl"
FONTS = {
    "mono": "ibmplexmono/IBMPlexMono-Regular.ttf",
    "monob": "ibmplexmono/IBMPlexMono-Bold.ttf",
    "stencil": "sairastencilone/SairaStencilOne-Regular.ttf",
}
EXTRA = "·–—…→←×✓─’‘“”•±°≥≤▲▼●○−↗↘↑↓▸◆"
CHARSET = [chr(c) for c in range(32, 127)] + list(EXTRA)
ALIAS = {}
OUT = Path(__file__).resolve().parent.parent / "scripts" / "glyphdata.json"


def _bar(p, q, t):
    """A thick line segment from p to q as a rectangle path (font units, y-down)."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    n = (dx * dx + dy * dy) ** 0.5
    nx, ny = -dy / n * t / 2, dx / n * t / 2
    pts = [(p[0] + nx, p[1] + ny), (q[0] + nx, q[1] + ny), (q[0] - nx, q[1] - ny), (p[0] - nx, p[1] - ny)]
    return "M" + "L".join(f"{round(x)} {round(y)}" for x, y in pts) + "Z"


def custom_status_glyphs(t):
    """A proper tick and cross (Plex's tick reads as a square root at small sizes)."""
    tick = _bar((85, -300), (250, -105), t) + _bar((232, -125), (535, -665), t)
    cross = _bar((90, -665), (510, -145), t) + _bar((510, -665), (90, -145), t)
    return {"✓": tick, "✕": cross}


def load(rel, cache=Path("/tmp/glyph-fonts")):
    cache.mkdir(exist_ok=True)
    p = cache / Path(rel).name
    if not p.exists():
        p.write_bytes(urllib.request.urlopen(f"{BASE}/{rel}", timeout=60).read())
    return TTFont(p)


def main():
    data = {"upm": 1000, "alias": ALIAS, "fonts": {}}
    for key, rel in FONTS.items():
        font = load(rel)
        upm = font["head"].unitsPerEm
        scale = 1000 / upm
        cmap, gs, hmtx = font.getBestCmap(), font.getGlyphSet(), font["hmtx"]
        adv, paths = {}, {}
        for ch in CHARSET:
            if ord(ch) not in cmap:
                continue
            name = cmap[ord(ch)]
            pen = SVGPathPen(gs, ntos=lambda v: str(int(round(v))))
            gs[name].draw(TransformPen(pen, (scale, 0, 0, -scale, 0, 0)))      # flip y: SVG is y-down, baseline at 0
            adv[ch] = int(round(hmtx[name][0] * scale))
            paths[ch] = pen.getCommands()
        if key in ("mono", "monob"):
            for ch, d in custom_status_glyphs(124 if key == "monob" else 92).items():
                adv[ch], paths[ch] = 600, d
        data["fonts"][key] = {"adv": adv, "d": paths,
                              "asc": int(font["hhea"].ascent * scale), "desc": int(font["hhea"].descent * scale)}
        print(f"{key:8s} {len(paths):3d} glyphs  {sum(len(v) for v in paths.values()) // 1024} KB of path data", file=sys.stderr)
    OUT.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False))
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)", file=sys.stderr)


if __name__ == "__main__":
    main()
