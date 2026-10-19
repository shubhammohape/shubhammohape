"""Draw every piece of text as vector outlines, so the whole profile shares one typeface and one palette.

GitHub serves README images through a proxy whose content-security policy blocks web fonts, and
the page's own text can't be styled at all. So text lives inside the images, drawn from glyph
outlines (IBM Plex Mono for text, Saira Stencil One for headings; both OFL) that tools/build_glyphs.py
extracted into glyphdata.json. Result: identical letters on every device, no font dependency.

Author text as normal <text>/<tspan> elements and run the finished SVG through outline(); add
data-font="stencil" to a <text> to set it in the stencil display face.
"""
import json
import re
from html import unescape
from pathlib import Path

_D = json.loads(Path(__file__).with_name("glyphdata.json").read_text(encoding="utf-8"))
UPM, ALIAS, FONTS = _D["upm"], _D["alias"], _D["fonts"]
FID = {"mono": "a", "monob": "b", "stencil": "c"}


class Glyphs:
    """The set of glyph outlines one SVG uses; each is defined once and referenced with <use>."""

    def __init__(self):
        self.used = {}

    def ref(self, font, ch):
        ch = ALIAS.get(ch, ch)
        for key in (font, "mono"):                     # fall back to the text face for symbols the display face lacks
            f = FONTS[key]
            if ch in f["d"]:
                gid = f"{FID[key]}{ord(ch):x}"
                if f["d"][ch]:
                    self.used[gid] = f["d"][ch]
                return (gid if f["d"][ch] else None), f["adv"][ch]
        return None, FONTS["mono"]["adv"][" "]

    def defs(self):
        return "<defs>" + "".join(f'<path id="{g}" d="{d}"/>' for g, d in sorted(self.used.items())) + "</defs>"


def _num(s, default=0.0):
    try:
        return float(s)
    except (TypeError, ValueError):
        return default


def measure(text, size, font="mono", spacing=0.0):
    """Width in px of `text` set at `size` (letter-spacing counted after every glyph, as SVG does)."""
    f = FONTS[font]
    return sum(f["adv"].get(ALIAS.get(c, c), f["adv"][" "]) for c in text) * size / UPM + spacing * len(text)


_ATTR = re.compile(r'([\w:.-]+)="([^"]*)"')
_TEXT = re.compile(r"<text\b([^>]*?)>(.*?)</text>", re.S)
_TSPAN = re.compile(r"(<tspan\b[^>]*>.*?</tspan>)", re.S)


def _convert(m, gs):
    attrs = dict(_ATTR.findall(m.group(1)))
    size = _num(attrs.get("font-size"), 16.0)
    spacing = _num(attrs.get("letter-spacing"))
    base_font = "stencil" if attrs.get("data-font") == "stencil" else ("monob" if _num(attrs.get("font-weight"), 400) >= 600 else "mono")
    preserve = attrs.get("xml:space") == "preserve"
    fill = attrs.get("fill")
    # segments: (text, font, fill)
    segs = []
    for part in _TSPAN.split(m.group(2)):
        if part.startswith("<tspan"):
            ta = dict(_ATTR.findall(re.match(r"<tspan\b([^>]*)>", part).group(1)))
            font = base_font if base_font == "stencil" else ("monob" if _num(ta.get("font-weight"), 0) >= 600 else base_font)
            segs.append((unescape(re.sub(r"<[^>]+>", "", part)), font, ta.get("fill")))
        elif part:
            segs.append((unescape(re.sub(r"<[^>]+>", "", part)), base_font, None))
    if not preserve:                                   # SVG default whitespace handling
        joined = "".join(t for t, _, _ in segs)
        if not joined.strip():
            return ""
        out, prev_space = [], True
        for t, f, fl in segs:
            buf = []
            for c in re.sub(r"[\r\n\t]", " ", t):
                if c == " " and prev_space:
                    continue
                prev_space = c == " "
                buf.append(c)
            out.append(("".join(buf), f, fl))
        segs = out
        if segs:                                       # drop the trailing space of the whole run
            segs[-1] = (segs[-1][0].rstrip(" "), segs[-1][1], segs[-1][2])
    s = size / UPM
    sp = spacing / s
    x_units, groups = 0.0, []
    for text, font, fl in segs:
        uses = []
        for ch in text:
            gid, adv = gs.ref(font, ch)
            if gid:
                uses.append(f'<use href="#{gid}" x="{x_units:.0f}"/>')
            x_units += adv + sp
        if uses:
            groups.append(f'<g fill="{fl}">{"".join(uses)}</g>' if fl else "".join(uses))
    width = x_units * s
    anchor = attrs.get("text-anchor", "start")
    x0 = _num(attrs.get("x")) - (width if anchor == "end" else width / 2 if anchor == "middle" else 0)
    g = [f'transform="{attrs["transform"] + " " if "transform" in attrs else ""}translate({x0:.2f},{_num(attrs.get("y")):.2f}) scale({s:.5f})"']
    if fill is not None:
        g.append(f'fill="{fill}"')
    for k in ("fill-opacity", "opacity", "stroke", "stroke-opacity", "stroke-linejoin", "paint-order"):
        if k in attrs:
            g.append(f'{k}="{attrs[k]}"')
    if "stroke-width" in attrs:
        g.append(f'stroke-width="{_num(attrs["stroke-width"]) / s:.1f}"')
    return f'<g {" ".join(g)}>{"".join(groups)}</g>'


def outline(svg):
    """Replace every <text> in an SVG string by outlined glyphs and add the glyph definitions."""
    gs = Glyphs()
    out = _TEXT.sub(lambda m: _convert(m, gs), svg)
    return re.sub(r"(<svg\b[^>]*>)", lambda m: m.group(1) + gs.defs(), out, count=1)
