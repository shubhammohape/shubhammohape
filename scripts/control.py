"""Control-room strip under the refinery: a brushed-metal panel with gauges and an LED run history."""
import math
from html import escape

from iso import TEX, txt
from theme import FONT, GLYPH, P

TASKS = ["extract", "clean", "enrich", "load", "serve"]
HISTORY = 30
NEEDLE = {"ok": 328, "warn": 270, "fail": 212}   # degrees; 180 = far left, 360 = far right
LED = {"ok": ("#fff0a0", "#E1AD01", "#7a5d00"), "warn": ("#ffc58a", "#ff8f3a", "#8a3d00"),
       "fail": ("#ff9a9a", "#ff5252", "#8a1010"), "skip": ("#7a808c", "#4a4f59", "#24272d")}


def defs():
    d = ['<defs>',
         '<linearGradient id="cp_panel" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#1f2229"/><stop offset=".5" stop-color="#15171c"/><stop offset="1" stop-color="#0d0e11"/></linearGradient>',
         '<linearGradient id="cp_bezel" x1="0" x2="1" y1="0" y2="1"><stop offset="0" stop-color="#aab4c4"/><stop offset=".35" stop-color="#59627a"/><stop offset=".7" stop-color="#1d2128"/><stop offset="1" stop-color="#3b4350"/></linearGradient>',
         '<radialGradient id="cp_face" cx=".5" cy=".38" r=".75"><stop offset="0" stop-color="#262a33"/><stop offset="1" stop-color="#07080a"/></radialGradient>',
         '<radialGradient id="cp_hub" cx=".35" cy=".3" r=".8"><stop offset="0" stop-color="#e6edf5"/><stop offset=".6" stop-color="#59627a"/><stop offset="1" stop-color="#1b1f26"/></radialGradient>',
         '<radialGradient id="cp_screw" cx=".35" cy=".3" r=".8"><stop offset="0" stop-color="#cfd8e6"/><stop offset=".7" stop-color="#59627a"/><stop offset="1" stop-color="#1b1f26"/></radialGradient>',
         '<linearGradient id="cp_glare" x1="0" x2="1" y1="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".18"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>',
         f'<pattern id="p_brush" width="64" height="96" patternUnits="userSpaceOnUse"><image href="{TEX["brush"]}" width="64" height="96"/></pattern>',
         f'<pattern id="hzc" width="16" height="16" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="8" height="16" fill="{P["mustard"]}"/><rect x="8" width="8" height="16" fill="#101216"/></pattern>',
         '<clipPath id="cr"><rect width="900" height="244" rx="14"/></clipPath>']
    for k, (hi, mid, lo) in LED.items():
        d.append(f'<linearGradient id="led_{k}" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="{hi}"/><stop offset=".45" stop-color="{mid}"/><stop offset="1" stop-color="{lo}"/></linearGradient>')
    d.append("</defs>")
    return "".join(d)


def arc(cx, cy, r, a0, a1):
    p0 = (cx + r * math.cos(math.radians(a0)), cy + r * math.sin(math.radians(a0)))
    p1 = (cx + r * math.cos(math.radians(a1)), cy + r * math.sin(math.radians(a1)))
    return f"M{p0[0]:.1f},{p0[1]:.1f} A{r},{r} 0 0 1 {p1[0]:.1f},{p1[1]:.1f}"


def screw(x, y, ang=30):
    a = math.radians(ang)
    dx, dy = 3.2 * math.cos(a), 3.2 * math.sin(a)
    return (f'<circle cx="{x}" cy="{y}" r="5.6" fill="#050608"/><circle cx="{x}" cy="{y}" r="4.8" fill="url(#cp_screw)"/>'
            f'<line x1="{x - dx:.1f}" y1="{y - dy:.1f}" x2="{x + dx:.1f}" y2="{y + dy:.1f}" stroke="#0b0c0f" stroke-width="1.4"/>')


def engraved(x, y, s, size, fill, anchor="start", weight="700", spacing=0, stencil=False):
    sp = (f' letter-spacing="{spacing}"' if spacing else "") + (' data-font="stencil"' if stencil else "")
    return (f'<text x="{x + 1:.1f}" y="{y + 1.4:.1f}" fill="#000" fill-opacity=".75" font-size="{size}" text-anchor="{anchor}" font-weight="{weight}" font-family="{FONT}"{sp}>{escape(s)}</text>'
            f'<text x="{x:.1f}" y="{y:.1f}" fill="{fill}" font-size="{size}" text-anchor="{anchor}" font-weight="{weight}" font-family="{FONT}"{sp}>{escape(s)}</text>')


def dial(cx, cy, name, status, detail):
    R = 30
    o = [f'<circle cx="{cx + 2}" cy="{cy + 3}" r="49" fill="#000" opacity=".5"/>',
         f'<circle cx="{cx}" cy="{cy}" r="48" fill="url(#cp_bezel)" stroke="#050608" stroke-width="1"/>',
         f'<circle cx="{cx}" cy="{cy}" r="44.5" fill="#050608"/>',
         f'<circle cx="{cx}" cy="{cy}" r="43" fill="url(#cp_face)"/>']
    for a in range(180, 361, 15):           # scale ticks
        major = (a - 180) % 45 == 0
        r0, r1 = (36.5 if major else 38), 41.5
        ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        o.append(f'<line x1="{cx + r0 * ca:.1f}" y1="{cy + r0 * sa:.1f}" x2="{cx + r1 * ca:.1f}" y2="{cy + r1 * sa:.1f}" stroke="#aab4c4" stroke-width="{1.5 if major else .9}" opacity=".8"/>')
    o.append(f'<path d="{arc(cx, cy, R, 180, 360)}" fill="none" stroke="#000" stroke-width="10" opacity=".6"/>')
    for a0, a1, key in ((181, 239, "fail"), (241, 299, "warn"), (301, 359, "ok")):
        live = status == key
        if live:
            o.append(f'<path d="{arc(cx, cy, R, a0, a1)}" fill="none" stroke="{P[key]}" stroke-width="12" opacity=".28"/>')
        o.append(f'<path d="{arc(cx, cy, R, a0, a1)}" fill="none" stroke="{P[key]}" stroke-width="6.5" opacity="{1 if live else 0.3}"/>')
    if status in NEEDLE:
        a = math.radians(NEEDLE[status])
        x, y = cx + (R + 3) * math.cos(a), cy + (R + 3) * math.sin(a)
        o.append(f'<g><line x1="{cx + 1.6}" y1="{cy + 2.4}" x2="{x + 1.6:.1f}" y2="{y + 2.4:.1f}" stroke="#000" stroke-width="2.4" stroke-linecap="round" opacity=".55"/>'
                 f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="#f4efe0" stroke-width="2" stroke-linecap="round"/>'
                 f'<animateTransform attributeName="transform" type="rotate" values="0 {cx} {cy};2 {cx} {cy};-1.5 {cx} {cy};0 {cx} {cy}" dur="4.5s" repeatCount="indefinite"/></g>')
    else:
        o.append(txt(cx, cy - 10, "–", P["skip"], 16, "middle", "700"))
    o.append(f'<circle cx="{cx}" cy="{cy}" r="5.5" fill="url(#cp_hub)" stroke="#050608" stroke-width="1"/>')
    o.append(f'<path d="M{cx - 40},{cy - 6} A42,42 0 0 1 {cx + 14},{cy - 40} L{cx + 4},{cy - 22} A24,24 0 0 0 {cx - 22},{cy - 4} Z" fill="url(#cp_glare)"/>')   # glass glare
    col = P.get(status, P["skip"])
    o.append(f'<text x="{cx}" y="{cy + 66}" fill="{P["text"]}" font-size="11" font-weight="700" text-anchor="middle" font-family="{FONT}"><tspan fill="{col}">{GLYPH.get(status, "–")}</tspan> {escape(name)}</text>')
    o.append(txt(cx, cy + 80, detail[:20], P["muted"], 9.5, "middle"))
    return "".join(o)


def control_svg(results, checks, history, repos, ts, schedule, W=900, H=244):
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
         f'aria-label="Control room: four data-quality gauges (freshness, volume, schema, uniqueness) and an LED history of each pipeline task over the last {HISTORY} runs.">',
         defs(),
         f'<rect width="{W}" height="{H}" rx="14" fill="url(#cp_panel)"/>',
         f'<rect width="{W}" height="{H}" rx="14" fill="url(#p_brush)" opacity=".16"/>',
         f'<g clip-path="url(#cr)"><rect width="{W}" height="6" fill="url(#hzc)"/></g>',
         f'<rect x="7" y="13" width="{W - 14}" height="{H - 20}" rx="9" fill="none" stroke="#000" stroke-opacity=".45"/>',
         f'<rect x="8" y="14" width="{W - 16}" height="{H - 22}" rx="9" fill="none" stroke="#fff" stroke-opacity=".05"/>']
    for x, y, a in ((20, 26, 20), (W - 20, 26, 70), (20, H - 14, 120), (W - 20, H - 14, 160)):
        o.append(screw(x, y, a))
    o.append(engraved(44, 40, "CONTROL ROOM", 20, P["mustard"], spacing=3, stencil=True))
    o.append(txt(W - 44, 38, f"schedule {schedule}  ·  {ts}", P["muted"], 10.5, "end"))
    o.append(engraved(28, 70, "DATA-QUALITY TESTS", 10, P["muted"], spacing=2))
    for i, (name, status, detail) in enumerate(checks[:4]):
        o.append(dial(75 + i * 102, 132, name, status, detail))

    gx, gy, cw, ch, step = 508, 92, 9, 11, 11.2
    o.append(engraved(gx - 46, 70, f"LAST {HISTORY} RUNS", 10, P["muted"], spacing=2))
    o.append(f'<rect x="{gx - 52}" y="{gy - 10}" width="{HISTORY * step + 60:.0f}" height="{5 * 20 + 6}" rx="6" fill="#07080a" stroke="#000" stroke-opacity=".6"/>')
    o.append(f'<rect x="{gx - 52}" y="{gy - 10}" width="{HISTORY * step + 60:.0f}" height="{5 * 20 + 6}" rx="6" fill="none" stroke="#fff" stroke-opacity=".06"/>')
    for ri, name in enumerate(TASKS):
        y = gy + ri * 20
        o.append(txt(gx - 46, y + 9, name, P["muted"], 9.5))
        for ci in range(HISTORY):
            x = gx + ci * step
            idx = ci - (HISTORY - len(history))
            if idx < 0:
                o.append(f'<rect x="{x:.1f}" y="{y}" width="{cw}" height="{ch}" rx="2" fill="#0d0e11" stroke="#1b1e24"/>')
                continue
            st = history[idx]["tasks"].get(name, "skip")
            o.append(f'<rect x="{x - 1.2:.1f}" y="{y - 1.2}" width="{cw + 2.4}" height="{ch + 2.4}" rx="2.6" fill="#030304"/>')
            o.append(f'<rect x="{x:.1f}" y="{y}" width="{cw}" height="{ch}" rx="1.8" fill="url(#led_{st})"/>')
            o.append(f'<rect x="{x + 1.2:.1f}" y="{y + 1}" width="{cw - 2.4}" height="{ch / 3:.1f}" rx="1" fill="#fff" opacity=".22"/>')
            if st in ("warn", "fail"):
                o.append(txt(x + cw / 2, y + 9.2, GLYPH[st], "#0b0c0f", 8.5, "middle", "700"))
    o.append(txt(gx - 46, 214, "✓ ok   ! warning   ✕ failed   – skipped (upstream failed)", P["muted"], 9.5))
    o.append("</svg>")
    return "\n".join(o)
