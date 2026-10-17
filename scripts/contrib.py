"""A year of contributions as a flip-disc display board.

The data is the same calendar GitHub draws as green squares on a profile (private work included, as
visitors see it), fetched from the public contributions page so no token is needed. The board has one
disc per day: 53 weeks x 7 weekdays = 371 discs, like the 371 cells of the original. Every few seconds
a wave of clacking discs rewrites the board with a message made from the real numbers, then flips back.

Everything is animated with SMIL only: each disc carries its own flip timeline, so a visitor sees the
heat map, a wave, a message, a wave, and back, with no JavaScript.
"""
import json
import random
import re
import urllib.request
from datetime import date, timedelta
from html import escape

from iso import TEX
from theme import FONT, P

# --------------------------------------------------------------------- data
UA = "profile-pipeline"


def parse_calendar_html(html):
    """GitHub's public calendar: <td data-date data-level id> cells plus <tool-tip for=id>N contributions...</tool-tip>."""
    tips = {m.group(1): m.group(2) for m in re.finditer(r'<tool-tip\b[^>]*\bfor="([^"]+)"[^>]*>([^<]*)</tool-tip>', html)}
    days = []
    for m in re.finditer(r"<td\b([^>]*ContributionCalendar-day[^>]*)>", html):
        a = m.group(1)
        d, lv, cid = (re.search(p, a) for p in (r'data-date="([^"]+)"', r'data-level="(\d)"', r'\bid="([^"]+)"'))
        if not (d and lv):
            continue
        n = re.match(r"(\d+) contribution", tips.get(cid.group(1), "") if cid else "")
        days.append({"date": d.group(1), "level": int(lv.group(1)), "count": int(n.group(1)) if n else 0})
    days.sort(key=lambda x: x["date"])
    return days


def fetch_calendar(user, timeout=25):
    req = urllib.request.Request(f"https://github.com/users/{user}/contributions", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return parse_calendar_html(r.read().decode("utf-8", "replace"))


def grid_of(days):
    """-> (weeks, grid) where grid[w][d] is the day dict (d: 0 = Sunday) or None; weeks = number of columns."""
    if not days:
        return 0, []
    first = date.fromisoformat(days[0]["date"])
    start = first - timedelta(days=(first.weekday() + 1) % 7)   # the Sunday on or before the first day
    cells = {}
    for x in days:
        dt = date.fromisoformat(x["date"])
        cells[((dt - start).days // 7, (dt.weekday() + 1) % 7)] = x
    weeks = max(w for w, _ in cells) + 1
    return weeks, [[cells.get((w, d)) for d in range(7)] for w in range(weeks)]


def summarize(days):
    act = [x for x in days if x["count"]]
    total = sum(x["count"] for x in days)
    best = max(days, key=lambda x: x["count"]) if days else {"date": "", "count": 0}
    run = longest = 0
    l_end = l_start = None
    for i, x in enumerate(days):
        run = run + 1 if x["count"] else 0
        if run > longest:
            longest, l_end, l_start = run, x["date"], days[i - run + 1]["date"]
    cur = 0
    for x in reversed(days):
        if x["count"]:
            cur += 1
        elif x is days[-1]:
            continue            # today may simply not have happened yet
        else:
            break
    wd = {}
    for x in days:
        k = (date.fromisoformat(x["date"]).weekday() + 1) % 7
        wd[k] = wd.get(k, 0) + x["count"]
    months = {}
    for x in days:
        months[x["date"][:7]] = months.get(x["date"][:7], 0) + x["count"]
    names = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
    return {
        "total": total, "active": len(act), "days": len(days), "best": best["count"], "best_date": best["date"],
        "avg": round(total / len(act), 1) if act else 0.0, "longest": longest, "current": cur,
        "longest_start": l_start, "longest_end": l_end, "last_count": act[-1]["count"] if act else 0,
        "last_active": act[-1]["date"] if act else None,
        "top_weekday": names[max(wd, key=wd.get)] if wd else "",
        "top_month": max(months, key=months.get) if months else "",
    }


def blank_year(end=None):
    """53 empty weeks ending on the Saturday of this week, for a board with nothing to show yet."""
    end = end or date.today()
    end = end + timedelta(days=(5 - end.weekday()) % 7)
    return [{"date": (end - timedelta(days=370 - i)).isoformat(), "count": 0, "level": 0} for i in range(371)]


def short(n):
    return str(n) if n < 10000 else f"{n // 1000}K"


def messages(stats, name):
    msgs = [f"{short(stats['total'])}/YEAR", f"{stats['active']} DAYS", f"PEAK {stats['best']}", name.upper()[:9]]
    return [m[:9] for m in msgs if m.strip()]


# --------------------------------------------------------- 5x7 dot-matrix font
_F = {
    "0": "01110 10001 10011 10101 11001 10001 01110", "1": "00100 01100 00100 00100 00100 00100 01110",
    "2": "01110 10001 00001 00010 00100 01000 11111", "3": "11111 00010 00100 00010 00001 10001 01110",
    "4": "00010 00110 01010 10010 11111 00010 00010", "5": "11111 10000 11110 00001 00001 10001 01110",
    "6": "00110 01000 10000 11110 10001 10001 01110", "7": "11111 00001 00010 00100 01000 01000 01000",
    "8": "01110 10001 10001 01110 10001 10001 01110", "9": "01110 10001 10001 01111 00001 00010 01100",
    "A": "01110 10001 10001 11111 10001 10001 10001", "B": "11110 10001 10001 11110 10001 10001 11110",
    "C": "01110 10001 10000 10000 10000 10001 01110", "D": "11100 10010 10001 10001 10001 10010 11100",
    "E": "11111 10000 10000 11110 10000 10000 11111", "F": "11111 10000 10000 11110 10000 10000 10000",
    "G": "01110 10001 10000 10111 10001 10001 01111", "H": "10001 10001 10001 11111 10001 10001 10001",
    "I": "01110 00100 00100 00100 00100 00100 01110", "J": "00111 00010 00010 00010 00010 10010 01100",
    "K": "10001 10010 10100 11000 10100 10010 10001", "L": "10000 10000 10000 10000 10000 10000 11111",
    "M": "10001 11011 10101 10101 10001 10001 10001", "N": "10001 10001 11001 10101 10011 10001 10001",
    "O": "01110 10001 10001 10001 10001 10001 01110", "P": "11110 10001 10001 11110 10000 10000 10000",
    "Q": "01110 10001 10001 10001 10101 10010 01101", "R": "11110 10001 10001 11110 10100 10010 10001",
    "S": "01111 10000 10000 01110 00001 00001 11110", "T": "11111 00100 00100 00100 00100 00100 00100",
    "U": "10001 10001 10001 10001 10001 10001 01110", "V": "10001 10001 10001 10001 10001 01010 00100",
    "W": "10001 10001 10001 10101 10101 10101 01010", "X": "10001 10001 01010 00100 01010 10001 10001",
    "Y": "10001 10001 10001 01010 00100 00100 00100", "Z": "11111 00001 00010 00100 01000 10000 11111",
    " ": "00000 00000 00000 00000 00000 00000 00000", ".": "00000 00000 00000 00000 00000 01100 01100",
    "/": "00001 00010 00010 00100 01000 01000 10000", "-": "00000 00000 00000 11111 00000 00000 00000",
    "+": "00000 00100 00100 11111 00100 00100 00000", ":": "00000 01100 01100 00000 01100 01100 00000",
    "%": "11000 11001 00010 00100 01000 10011 00011", "!": "00100 00100 00100 00100 00100 00000 00100",
}
FONT5 = {k: [[int(c) for c in row] for row in v.split()] for k, v in _F.items()}


def text_pixels(msg, cols=53):
    """Set of (col, row) that are lit when `msg` is centred on a cols x 7 board."""
    width = 6 * len(msg) - 1
    c0 = (cols - width) // 2
    px = set()
    for i, ch in enumerate(msg):
        g = FONT5.get(ch, FONT5[" "])
        for r in range(7):
            for c in range(5):
                if g[r][c]:
                    px.add((c0 + i * 6 + c, r))
    return px


# ----------------------------------------------------------------- the board
FACE = {"D": "#0e0f12", "1": "#7a5c00", "2": "#b48a00", "3": "#E1AD01", "4": "#FFD84A", "M": "#FFE9A6"}
BRIGHTER = {"1": "#E1AD01", "2": "#FFD84A", "3": "#FFE9A6", "4": "#FFF6D6", "D": "#3b3f48"}
MONTH = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def _hash01(*xs):
    return random.Random("|".join(map(str, xs))).random()


def _pc(ts):
    return f"{ts:.3f}".rstrip("0").rstrip(".") or "0"


def board_svg(days, stats, ts, name, W=900, animate=True, cycle=26.0, cfg=None):
    weeks, grid = grid_of(days)
    cols = weeks
    pitch, R = 14.4, 5.5
    msgs = messages(stats, name)
    # -- states: heat map first, then one per message, then back to the heat map
    def heat(w, d):
        x = grid[w][d] if w < len(grid) else None
        return str(x["level"]) if x and x["level"] else "D"
    states = [{(w, d): heat(w, d) for w in range(cols) for d in range(7)}]
    for m in msgs:
        px = text_pixels(m, cols)
        states.append({(w, d): ("M" if (w, d) in px else "D") for w in range(cols) for d in range(7)})
    states.append(states[0])
    # -- timeline: hold on the heat map, then a wave into each message, then a wave back
    FLIP, WAVE, HOLD0, HOLD = 0.30, 1.5, 6.5, 2.3
    waves = []
    t = HOLD0
    for k in range(len(states) - 1):
        waves.append(t)
        t += WAVE + (HOLD if k < len(states) - 2 else 0)
    cycle = max(cycle, t + 0.8)

    H = 286
    gx, gy, gw, gh = 40, 62, W - 80, 148
    gridw = pitch * cols
    lab = 30
    lx = gx + (gw - gridw - lab) / 2
    x0 = lx + lab + pitch / 2
    y0 = gy + 38
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
         f'aria-label="A flip-disc display board showing {stats["total"]} contributions over the last year as a heat map of {stats["days"]} discs, '
         f'then flipping to messages: {escape(", ".join(msgs))}. Busiest weekday {stats["top_weekday"]}, best day {stats["best"]}, '
         f'{stats["active"]} active days, longest streak {stats["longest"]} days.">']
    o.append(_defs(pitch, R, cols))
    # wall, spot light, soft frame shadow
    o.append(f'<rect width="{W}" height="{H}" rx="14" fill="#08090b"/><rect width="{W}" height="{H}" rx="14" fill="url(#p_conc)" opacity=".3"/>')
    o.append(f'<ellipse cx="{W / 2}" cy="30" rx="520" ry="150" fill="url(#bs_spot)"/>')
    for i, a in enumerate((.20, .14, .09)):
        o.append(f'<rect x="{20 - i * 3}" y="{22 - i * 3 + 7}" width="{W - 40 + i * 6}" height="{H - 36 + i * 6}" rx="{16 + i * 3}" fill="#000" opacity="{a}"/>')
    # frame
    fy, fh = 16, H - 36
    o.append(f'<rect x="22" y="{fy}" width="{W - 44}" height="{fh}" rx="13" fill="url(#bs_frame)" stroke="#000"/>')
    o.append(f'<rect x="22" y="{fy}" width="{W - 44}" height="{fh}" rx="13" fill="url(#p_brush)" opacity=".16"/>')
    o.append(f'<rect x="23.5" y="{fy + 1.5}" width="{W - 47}" height="{fh - 3}" rx="12" fill="none" stroke="#fff" stroke-opacity=".12"/>')
    o.append(f'<g clip-path="url(#bs_clip)"><rect x="22" y="{fy}" width="{W - 44}" height="5" fill="url(#bs_hz)"/></g>')
    # glass recess
    o.append(f'<rect x="{gx - 6}" y="{gy - 6}" width="{gw + 12}" height="{gh + 12}" rx="9" fill="#050506" stroke="#000" stroke-width="2"/>')
    o.append(f'<rect x="{gx - 5}" y="{gy - 5}" width="{gw + 10}" height="{gh + 10}" rx="8" fill="none" stroke="#fff" stroke-opacity=".07"/>')
    o.append(f'<rect x="{gx}" y="{gy}" width="{gw}" height="{gh}" rx="5" fill="#040405"/>')
    # month stencil: above the column that holds the 1st of each month (the first column for the opening, partial month)
    placed = {}
    for w in range(cols):
        for d in range(7):
            x = grid[w][d]
            if x:
                ym = x["date"][:7]
                if ym not in placed and (x["date"][8:] == "01" or not placed):
                    placed[ym] = w
    for ym, w in placed.items():
        o.append(f'<text x="{x0 + w * pitch - pitch / 2:.1f}" y="{gy + 20}" fill="{P["mustard"]}" fill-opacity=".85" font-size="9" font-weight="700" letter-spacing="1.2" font-family="{FONT}">{MONTH[int(ym[5:7]) - 1]}</text>')
    for d, s in ((1, "MON"), (3, "WED"), (5, "FRI")):
        o.append(f'<text x="{lx + lab - 6}" y="{y0 + d * pitch + 3.2:.1f}" fill="{P["muted"]}" font-size="8.5" font-weight="700" text-anchor="end" font-family="{FONT}">{s}</text>')
    o.append(f'<rect x="{x0 - pitch / 2:.1f}" y="{y0 - pitch / 2:.1f}" width="{gridw:.1f}" height="{pitch * 7:.1f}" fill="url(#bs_holes)"/>')
    # discs
    rng = random.Random(cfg or 7)
    twinkle = {}
    cand = [(w, d) for w in range(cols) for d in range(7) if states[0][(w, d)] in "123"]
    quiet_end = waves[-1] + WAVE + 0.3                     # the heat map is back and settled after the final wave
    for (w, d) in rng.sample(cand, min(16, len(cand))):
        twinkle[(w, d)] = [rng.uniform(0.6, HOLD0 - 1.0) if rng.random() < .7 else rng.uniform(quiet_end, cycle - 0.6)]
    for w in range(cols):
        o.append(_column(x0 + w * pitch, y0, pitch, w, states, waves, cols, FLIP, WAVE, cycle, R, twinkle, animate))
    o.append(f'<rect x="{x0 - pitch / 2:.1f}" y="{y0 - pitch / 2:.1f}" width="{gridw:.1f}" height="{pitch * 7:.1f}" fill="url(#bs_inner)"/>')
    o.append(_tooltips(days, grid, stats, x0, y0, pitch, R, gx, gw, cycle, quiet_end, HOLD0, animate))
    # glass: reflection, sweeping glare
    o.append(f'<rect x="{gx}" y="{gy}" width="{gw}" height="{gh}" rx="5" fill="url(#bs_glass)"/>')
    o.append(f'<g clip-path="url(#bs_gclip)"><polygon points="-40,{gy} 20,{gy} 100,{gy + gh} 40,{gy + gh}" fill="url(#bs_glare)" transform="translate(0,0)">'
             + (f'<animateTransform attributeName="transform" type="translate" values="-120 0;-120 0;1000 0" keyTimes="0;.30;1" dur="{cycle * 0.62:.1f}s" repeatCount="indefinite"/>' if animate else "")
             + '</polygon></g>')
    # furniture: nameplate, status lamp, screws, conduit
    o.append(f'<rect x="40" y="{fy + 14}" width="212" height="22" rx="4" fill="#0b0c0f" stroke="#59627a" stroke-opacity=".6"/>')
    o.append(_engraved(52, fy + 29.5, "OUTPUT BOARD  FD-371", 11, P["mustard"], 2.2))
    o.append(f'<text x="{W - 104}" y="{fy + 29.5}" fill="{P["muted"]}" font-size="10" text-anchor="end" font-family="{FONT}">last 12 months · {escape(ts)}</text>')
    o.append(f'<circle cx="{W - 76}" cy="{fy + 25}" r="11" fill="url(#bs_led_glow)"><animate attributeName="opacity" values="1;.55;1" dur="2.4s" repeatCount="indefinite"/></circle>'
             f'<circle cx="{W - 76}" cy="{fy + 25}" r="4.6" fill="{P["mustard_hi"]}" stroke="#050608"/>'
             f'<text x="{W - 62}" y="{fy + 29}" fill="{P["mustard"]}" font-size="9" font-weight="700" letter-spacing="1.5" font-family="{FONT}">LIVE</text>')
    for sx, sy in ((34, fy + 9), (W - 34, fy + 9), (34, fy + fh - 9), (W - 34, fy + fh - 9), (W // 2, fy + 10), (W // 2, fy + fh - 9)):
        o.append(f'<circle cx="{sx}" cy="{sy}" r="4.6" fill="#050608"/><circle cx="{sx}" cy="{sy}" r="3.9" fill="url(#bs_screw)"/>'
                 f'<line x1="{sx - 2.4}" y1="{sy - 1.4}" x2="{sx + 2.4}" y2="{sy + 1.4}" stroke="#0b0c0f" stroke-width="1.1"/>')
    # footer: legend and the headline numbers
    ly = fy + fh - 28
    o.append(f'<text x="44" y="{ly + 4}" fill="{P["muted"]}" font-size="9.5" font-family="{FONT}">LESS</text>')
    for i, k in enumerate(("D", "1", "2", "3", "4")):
        o.append(f'<circle cx="{80 + i * 15}" cy="{ly}" r="5.5" fill="#000"/><circle cx="{80 + i * 15}" cy="{ly}" r="4.7" fill="{FACE[k]}"/><circle cx="{80 + i * 15 - 1}" cy="{ly - 1.2}" r="1.6" fill="#fff" opacity=".28"/>')
    o.append(f'<text x="{80 + 5 * 15 + 2}" y="{ly + 4}" fill="{P["muted"]}" font-size="9.5" font-family="{FONT}">MORE</text>')
    best = f'{MONTH[int(stats["best_date"][5:7]) - 1]} {int(stats["best_date"][8:])}' if stats["best_date"] else "–"
    o.append(f'<text x="{W - 44}" y="{ly + 4}" fill="{P["text"]}" font-size="10.5" text-anchor="end" font-family="{FONT}">'
             f'<tspan fill="{P["mustard_hi"]}" font-weight="700">{stats["total"]:,}</tspan> contributions · '
             f'<tspan fill="{P["mustard_hi"]}" font-weight="700">{stats["active"]}</tspan> active days · '
             f'best <tspan fill="{P["mustard_hi"]}" font-weight="700">{stats["best"]}</tspan> ({best}) · '
             f'longest streak <tspan fill="{P["mustard_hi"]}" font-weight="700">{stats["longest"]}</tspan> · busiest <tspan fill="{P["mustard_hi"]}" font-weight="700">{stats["top_weekday"]}</tspan></text>')
    o.append(f'<rect width="{W}" height="{H}" rx="14" fill="none" stroke="{P["border"]}"/>')
    o.append("</svg>")
    return "\n".join(o)


def _loc(grid, iso):
    for w, col in enumerate(grid):
        for d, x in enumerate(col):
            if x and x["date"] == iso:
                return w, d
    return None


def _nice(iso):
    return f"{MONTH[int(iso[5:7]) - 1]} {int(iso[8:])}"


def _tooltips(days, grid, stats, x0, y0, pitch, R, gx, gw, cycle, quiet_end, hold0, animate):
    """The hover tooltips GitHub shows on a square, but they appear on their own: best day, longest streak, last active day."""
    names = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
    items = []
    if stats["best"]:
        w_d = _loc(grid, stats["best_date"])
        d = date.fromisoformat(stats["best_date"])
        items.append((w_d, f"{names[(d.weekday() + 1) % 7]}, {_nice(stats['best_date'])} · {stats['best']} contributions", (0.8, 3.0)))
    if stats["longest"] > 1 and stats.get("longest_end"):
        items.append((_loc(grid, stats["longest_end"]), f"{stats['longest']}-DAY STREAK · {_nice(stats['longest_start'])}–{_nice(stats['longest_end'])}", (3.4, hold0 - 0.4)))
    if stats.get("last_active"):
        items.append((_loc(grid, stats["last_active"]), f"LAST ACTIVE · {_nice(stats['last_active'])} · {stats['last_count']}", (quiet_end + 0.3, min(cycle - 0.3, quiet_end + 2.4))))
    out = []
    for loc, text, (t0, t1) in items:
        if not loc:
            continue
        w, d = loc
        cx, cy = x0 + w * pitch, y0 + d * pitch
        tw, th = len(text) * 6.0 + 18, 20
        above = d >= 2
        px = max(gx + 8, min(cx - tw / 2, gx + gw - 8 - tw))
        py = cy - R - 9 - th if above else cy + R + 9
        tip = (f"{cx - 5:.1f},{py + th:.1f} {cx + 5:.1f},{py + th:.1f} {cx:.1f},{py + th + 6:.1f}" if above
               else f"{cx - 5:.1f},{py:.1f} {cx + 5:.1f},{py:.1f} {cx:.1f},{py - 6:.1f}")
        kt = [0.0, t0 / cycle, (t0 + 0.18) / cycle, (t1 - 0.18) / cycle, t1 / cycle, 1.0]
        fade = (f'<animate attributeName="opacity" dur="{cycle:.1f}s" repeatCount="indefinite" keyTimes="{";".join(_pc(k) for k in kt)}" values="0;0;1;1;0;0"/>' if animate else "")
        out.append(f'<g opacity="0">{fade}'
                   f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{R + 2.6}" fill="none" stroke="{P["mustard_hi"]}" stroke-width="1.5"/>'
                   f'<polygon points="{tip}" fill="#0a0b0e" stroke="{P["mustard"]}" stroke-opacity=".7" stroke-width="1"/>'
                   f'<rect x="{px:.1f}" y="{py:.1f}" width="{tw:.1f}" height="{th}" rx="5" fill="#0a0b0e" stroke="{P["mustard"]}" stroke-opacity=".7"/>'
                   f'<polygon points="{tip}" fill="#0a0b0e"/>'
                   f'<text x="{px + tw / 2:.1f}" y="{py + 13.5:.1f}" fill="{P["text"]}" font-size="10" font-weight="700" text-anchor="middle" font-family="{FONT}">{escape(text)}</text></g>')
    return "".join(out)


def _engraved(x, y, s, size, fill, spacing):
    return (f'<text x="{x + 1}" y="{y + 1.3}" fill="#000" fill-opacity=".8" font-size="{size}" font-weight="700" letter-spacing="{spacing}" font-family="{FONT}">{escape(s)}</text>'
            f'<text x="{x}" y="{y}" fill="{fill}" font-size="{size}" font-weight="700" letter-spacing="{spacing}" font-family="{FONT}">{escape(s)}</text>')


def _defs(pitch, R, cols):
    d = ['<defs>',
         '<linearGradient id="bs_frame" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#3a3f4a"/><stop offset=".25" stop-color="#23262d"/><stop offset="1" stop-color="#0e0f13"/></linearGradient>',
         '<radialGradient id="bs_spot" cx=".5" cy=".3" r=".6"><stop offset="0" stop-color="#E1AD01" stop-opacity=".13"/><stop offset="1" stop-color="#E1AD01" stop-opacity="0"/></radialGradient>',
         '<radialGradient id="bs_screw" cx=".35" cy=".3" r=".8"><stop offset="0" stop-color="#cfd8e6"/><stop offset=".7" stop-color="#59627a"/><stop offset="1" stop-color="#1b1f26"/></radialGradient>',
         '<radialGradient id="bs_led_glow"><stop offset="0" stop-color="#FFD23F" stop-opacity=".9"/><stop offset="1" stop-color="#E1AD01" stop-opacity="0"/></radialGradient>',
         '<radialGradient id="bs_glow"><stop offset="0" stop-color="#FFD84A" stop-opacity=".6"/><stop offset="1" stop-color="#FFD84A" stop-opacity="0"/></radialGradient>',
         '<radialGradient id="bs_hl" cx=".34" cy=".3" r=".75"><stop offset="0" stop-color="#fff" stop-opacity=".6"/><stop offset=".45" stop-color="#fff" stop-opacity=".06"/><stop offset="1" stop-color="#000" stop-opacity=".3"/></radialGradient>',
         '<linearGradient id="bs_glass" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".07"/><stop offset=".3" stop-color="#fff" stop-opacity=".0"/><stop offset="1" stop-color="#000" stop-opacity=".18"/></linearGradient>',
         '<linearGradient id="bs_glare" x1="0" x2="1" y1="0" y2="0"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".16"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>',
         '<linearGradient id="bs_inner" x1="0" x2="1" y1="0" y2="1"><stop offset="0" stop-color="#000" stop-opacity=".35"/><stop offset=".25" stop-color="#000" stop-opacity="0"/></linearGradient>',
         f'<pattern id="bs_hz" width="16" height="16" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="8" height="16" fill="{P["mustard"]}"/><rect x="8" width="8" height="16" fill="#101216"/></pattern>',
         f'<pattern id="bs_holes" width="{pitch}" height="{pitch}" patternUnits="userSpaceOnUse"><circle cx="{pitch / 2 + .5}" cy="{pitch / 2 + .8}" r="{R + 1.2}" fill="#000" opacity=".7"/>'
         f'<circle cx="{pitch / 2}" cy="{pitch / 2}" r="{R + 1.1}" fill="#050506" stroke="#1d2027" stroke-width=".6"/></pattern>',
         f'<pattern id="p_conc" width="128" height="128" patternUnits="userSpaceOnUse"><image href="{TEX["conc"]}" width="128" height="128"/></pattern>',
         f'<pattern id="p_brush" width="64" height="96" patternUnits="userSpaceOnUse"><image href="{TEX["brush"]}" width="64" height="96"/></pattern>',
         '<clipPath id="bs_clip"><rect x="22" y="16" width="856" height="250" rx="13"/></clipPath>',
         f'<clipPath id="bs_gclip"><rect x="40" y="62" width="820" height="148" rx="5"/></clipPath>',
         f'<g id="bs_hlg"><circle r="{R}" fill="url(#bs_hl)"/><circle r="{R}" fill="none" stroke="#000" stroke-opacity=".45" stroke-width=".7"/></g>',
         '</defs>']
    return "".join(d)


def _column(cx, y0, pitch, w, states, waves, cols, FLIP, WAVE, cycle, R, twinkle, animate):
    """One column of 7 discs. Like a real flip-dot sign the board refreshes column by column: the whole column
    squashes edge-on together (one animation), and every disc whose face changes swaps colour at that instant."""
    K = len(states) - 1
    faces = [[st[(w, d)] for st in states] for d in range(7)]
    flip_t = {}
    for k in range(K):
        if any(faces[d][k] != faces[d][k + 1] for d in range(7)):
            frac = (w / max(1, cols - 1)) if k % 2 == 0 else 1 - (w / max(1, cols - 1))
            flip_t[k] = waves[k] + frac * (WAVE - FLIP - 0.1) + _hash01(w, k) * 0.07
    out, glows = [], []
    for d in range(7):
        cy = y0 + d * pitch
        first = faces[d][0]
        ev = [(flip_t[k] + FLIP / 2, faces[d][k + 1]) for k in flip_t if faces[d][k] != faces[d][k + 1]]
        for t in twinkle.get((w, d), []):
            ev += [(t, "T"), (t + 0.22, first)]
        ev.sort()
        anim = ""
        if animate and ev:
            kt, vals, cur = [0.0], [FACE[first]], first
            for t, f in ev:
                if f == "T":
                    col = BRIGHTER.get(cur, "#FFE9A6")
                else:
                    col, cur = FACE[f], f
                kt.append(t / cycle)
                vals.append(col)
            anim = (f'<animate attributeName="fill" calcMode="discrete" dur="{cycle:.1f}s" repeatCount="indefinite" '
                    f'keyTimes="{";".join(_pc(k) for k in kt)}" values="{";".join(vals)}"/>')
        out.append(f'<circle cy="{cy:.1f}" r="{R}" fill="{FACE[first]}">{anim}</circle><use href="#bs_hlg" y="{cy:.1f}"/>' if anim else
                   f'<circle cy="{cy:.1f}" r="{R}" fill="{FACE[first]}"/><use href="#bs_hlg" y="{cy:.1f}"/>')
        if first == "4":
            on = [(0.0, "1")] + [(flip_t[k] + FLIP / 2, "1" if faces[d][k + 1] == first else "0") for k in flip_t if faces[d][k] != faces[d][k + 1]]
            ga = ""
            if animate:
                if len(on) > 1:
                    ga += (f'<animate attributeName="opacity" calcMode="discrete" dur="{cycle:.1f}s" repeatCount="indefinite" '
                           f'keyTimes="{";".join(_pc(t / cycle) for t, _ in on)}" values="{";".join(v for _, v in on)}"/>')
                ga += '<animate attributeName="r" values="12;15;12" dur="2.6s" repeatCount="indefinite"/>'
            glows.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="13" fill="url(#bs_glow)">{ga}</circle>')
    scale = ""
    if animate and flip_t:
        skt, sv = [0.0], ["1 1"]
        for k in sorted(flip_t):
            tf = flip_t[k]
            skt += [tf / cycle, (tf + FLIP / 2) / cycle, (tf + FLIP) / cycle]
            sv += ["1 1", "0.07 1", "1 1"]
        skt.append(1.0)
        sv.append("1 1")
        scale = (f'<animateTransform attributeName="transform" type="scale" dur="{cycle:.1f}s" repeatCount="indefinite" '
                 f'keyTimes="{";".join(_pc(k) for k in skt)}" values="{";".join(sv)}"/>')
    return "".join(glows) + f'<g transform="translate({cx:.1f},0)"><g>{scale}{"".join(out)}</g></g>'
