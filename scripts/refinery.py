"""The hero image: this profile's nightly pipeline drawn as a 3D data refinery.

Each pipeline task is a physical unit; the numbers on the tags, the fill levels, the lamps, the
valves, the flow in the sight glasses and the size of the flare flame all come from the last real
run. A failed task turns its lamp red, leaks, and starves everything downstream.
"""
import math
import re
from html import escape

from details import (beam, bridge, cage, dish, flame, ladder, lamp, lattice, layered, leak, platform, pt, ring_dots,
                     ripples, rings, steam, tower_legs)
from iso import (COS_PHI, Cyl, Fit, Floor, Pipe, Scene, Shadow, Slab, Tag, Valve, a_translate, defs_svg, depth, proj,
                 reset_ids, thetas, txt)
from theme import GLYPH, P

SLAB_T = 0.55     # concrete thickness; the top of the pad is z = ZT
ZT = SLAB_T
GAP = 1.35        # visible pipe length between units
TASKS = ["extract", "clean", "enrich", "load", "serve"]


class Mast:
    """A three-legged lattice radio mast with a railed platform, dishes, strobe and a sweeping beam."""

    r = 0.5

    def __init__(self, x, y, z0, h, status):
        self.x, self.y, self.z0, self.h, self.status = x, y, z0, h, status
        self.depth = depth(x, y, z0)

    def top_z(self):
        return self.z0 + self.h

    def bbox_pts(self, th):
        cx, cy = proj(self.x, self.y, self.z0, th)
        tx, ty = proj(self.x, self.y, self.top_z() + 0.7, th)
        return [(cx - .5, cy + .25), (cx + .5, cy + .25), (tx - .3, ty), (tx + .3, ty)]

    def svg(self, f):
        S, h = f.S, self.h
        fr = [f.pt(self.x, self.y, self.z0, k) for k in range(f.n)]
        alive = self.status in ("ok", "warn")
        o = [f'<g transform="translate({fr[0][0]:.1f},{fr[0][1]:.1f})">{a_translate(fr, f)}']
        o.append(f'<ellipse cx="3" cy="3" rx="{.8 * S:.1f}" ry="{.42 * S:.1f}" fill="url(#g_ao)"/>')
        o.append(f'<ellipse cx="0" cy="2" rx="{.62 * S:.1f}" ry="{.31 * S:.1f}" fill="#0a0b0d" stroke="#3b4350" stroke-width="1.2"/>')
        o.append(f'<ellipse cx="0" cy="0" rx="{.55 * S:.1f}" ry="{.275 * S:.1f}" fill="url(#g_graphite)" stroke="#050608" stroke-width=".8"/>')
        back, front = platform(f, 0, h * 0.9, 0.2, 0.46, rail=0.34, posts=6)
        o.append(back)
        o.append(lattice(f, 0.5, 0.18, 0.0, h * 0.9, levels=10))
        o.append(front)
        for zz, dx, tilt in ((0.62, -0.30, -48), (0.8, 0.28, 140)):   # dishes bolted to the mast
            o.append(dish(dx * S, -h * zz * COS_PHI * S, 9, tilt))
        top = -(h * 0.9 + 0.36) * COS_PHI * S
        o.append(f'<line x1="0" y1="{-h * .9 * COS_PHI * S:.1f}" x2="0" y2="{top - 14:.1f}" stroke="#3b4350" stroke-width="2"/>')
        o.append(lamp(self.status, top - 14, 3.2))
        o.append(rings(alive, top - 14, 3, 78))
        if alive:
            o.append(beam(top - 14, 320))
        o.append("</g>")
        return "".join(o)


def compact(svg):
    """Shave bytes off animated geometry: 12.0 -> 12, 0.5 -> .5 (only inside points/d/values attributes)."""
    def tidy(m):
        v = re.sub(r"(?<![\d.])(-?)0\.(\d)", r"\1.\2", re.sub(r"(\d)\.0(?!\d)", r"\1", m.group(2)))
        return f'{m.group(1)}="{v}"'
    return re.sub(r'\b(points|d|values)="([^"]*)"', tidy, svg)


def refinery_svg(results, checks, repos, ts, ths=None, animate=True, W=900, H=545, check=False, yaw_deg=None,
                 name="SHUBHAM MOHAPE", tagline="data engineer · pipelines, scraping, ML ops · Mumbai"):
    reset_ids()
    st = {r["name"]: r for r in results}
    s = {k: st[k]["status"] for k in TASKS}
    counts = {t: sum(1 for r in repos if r["tier"] == t) for t in ("gold", "silver", "bronze")}
    total = max(len(repos), 1)
    n_raw, n_clean = st["extract"]["rows_out"], st["clean"]["rows_out"]
    nwarn = sum(1 for v in s.values() if v == "warn") + sum(1 for c in checks if c[1] == "warn")
    nfail = sum(1 for v in s.values() if v == "fail")
    flare_level = 2 if nfail else 1 if nwarn else 0

    def alpha(k):
        return 0.42 if s[k] == "skip" else 1.0

    def lvl(frac, ok=True):
        return 0.12 + 0.76 * max(0.0, min(1.0, frac)) if ok else 0.08

    # ---- layout: an inverted V so the flow reads left -> apex -> right
    rA, rB, rF, rS, rC, rG = 0.8, 1.5, 0.95, 1.35, 0.62, 1.3
    yF = rS + GAP + rF
    yB = yF + rF + GAP + rB
    yA = yB + rB + GAP + rA
    xC = rS + GAP + rC
    xG = xC + rC + GAP + rG
    xK = xG + rG + GAP + 0.5
    z0 = ZT
    legsH = 1.25

    sc = Scene(ths or thetas(), animate=animate)

    # ---- the pad
    x_min, y_min, x_max, y_max, arm = -2.1, -2.1, xK + 1.3, yA + 1.2, 2.1
    poly = [(x_min, y_min), (x_max, y_min), (x_max, arm), (arm, arm), (arm, y_max), (x_min, y_max)]
    edges = [((x_max, y_min), (x_max, arm)), ((x_max, arm), (arm, arm)), ((arm, arm), (arm, y_max)), ((arm, y_max), (x_min, y_max))]
    grid = []
    for j in range(int(y_min) + 1, int(y_max) + 1, 2):
        if y_min < j < y_max:
            grid.append(((x_min, j), (x_max if j < arm else arm, j)))
    for i in range(int(x_min) + 1, int(x_max) + 1, 2):
        if x_min < i < x_max:
            grid.append(((i, y_min), (i, y_max if i < arm else arm)))
    ins = 0.42
    paint = [[(x_max - ins, y_min + ins), (x_max - ins, arm - ins)], [(x_max - ins, arm - ins), (arm - ins, arm - ins)],
             [(arm - ins, arm - ins), (arm - ins, y_max - ins)], [(arm - ins, y_max - ins), (x_min + ins, y_max - ins)]]
    sc.add(Slab(poly, edges, ZT, grid, paint))
    for mx, my in ((1.7, 1.7), (xC + 0.2, -1.5), (-1.5, yB - 1.0)):
        sc.add(Floor(mx, my, ZT, 0.3, dep=-6e8))
    # floodlight poles: a warm pool of light on the concrete under each lamp head
    def pole_front(rx, ry, Hh, f):
        return (f'<rect x="-9" y="{-Hh - 3:.1f}" width="18" height="5" rx="2.5" fill="#1b1f26" stroke="#59627a" stroke-width=".8"/>'
                f'<ellipse cx="0" cy="{-Hh + 2.5:.1f}" rx="6.5" ry="2.2" fill="#fff4d2"/>'
                f'<ellipse cx="0" cy="{-Hh + 2:.1f}" rx="26" ry="14" fill="url(#g_lamp_ok)" opacity=".75"/>')

    for px, py, tx, ty in ((-1.8, 5.3, 0.9, 0.0), (4.95, -1.7, 0.0, 1.5), (-1.8, 10.2, 1.0, 0.0)):
        pole = sc.add(Cyl(px, py, z0, 3.3, 0.055, "graphite", tex=0, reflect=False, uid="pole", front=pole_front))
        sc.add(Shadow(pole, ZT))
        sc.add(Floor(px + tx * 1.2, py + ty * 1.2, ZT, 2.4, dep=-5.8e8, kind="light"))
    for mx, my, mr in ((0.9, yB - 2.6, 0.7), (-0.9, 1.0, 0.55), (xC + 1.6, 0.9, 0.6), (xG - 1.1, 1.4, 0.5), (1.1, yA - 2.3, 0.5)):
        sc.add(Floor(mx, my, ZT, mr, dep=-5.9e8, kind="stain"))

    # ---- units ---------------------------------------------------------------------------
    def api_front(rx, ry, Hh, f):
        ch = 0.7 * COS_PHI * f.S
        top = -Hh - ch
        return (ring_dots(f, 0.05, rA * 1.0, 16) + ladder(f, 100, rA, -legsH, 1.25, half=0.13, rung=0.24, off=0.17)
                + f'<line x1="0" y1="{top:.1f}" x2="0" y2="{top - 13:.1f}" stroke="#59627a" stroke-width="2"/>'
                + dish(7, top - 13, 11, -42) + lamp(s["extract"], top - 22, 3.2)
                + rings(s["extract"] in ("ok", "warn"), top - 13, 2, 46) + leak(s["extract"] == "fail", rx, ry, Hh))

    API = sc.add(Cyl(0, yA, z0 + legsH, 1.25, rA, "graphite", cap=("cone", 0.7), bands=(0.33, 0.66), seams=(10, 90, 170, 250),
                     reflect=False, alpha=alpha("extract"), uid="api", tex=0.2, grime=0.5,
                     back=lambda rx, ry, Hh, f: tower_legs(f, rA * 0.82, rA * 1.18, legsH), front=api_front))

    bronze_ok = s["extract"] not in ("fail", "skip")
    bronze_lvl = lvl(1.0 if n_raw else 0.05, bronze_ok)

    def brz_front(rx, ry, Hh, f):
        zb = 0.95
        ly = -Hh + (1 - bronze_lvl) * Hh * 0.92
        my = -(zb + 0.3) * COS_PHI * f.S
        motor = (f'<rect x="-8" y="{my - 14:.1f}" width="16" height="15" rx="2" fill="url(#g_graphite)" stroke="#050608" stroke-width=".8"/>'
                 f'<ellipse cx="0" cy="{my - 14:.1f}" rx="8" ry="3.6" fill="#2a2f39" stroke="#7d8898" stroke-width=".8"/>'
                 f'<rect x="-3" y="{my + 1:.1f}" width="6" height="5" fill="#59627a"/>'
                 f'<line x1="0" y1="{my + 6:.1f}" x2="0" y2="{ly:.1f}" stroke="#aab6c6" stroke-width="2.2"/>')
        return (ring_dots(f, zb, rB * 0.965, 22, clip=False) + ring_dots(f, 0.1, rB, 18)
                + ladder(f, 112, rB, 0, zb + 0.28, half=0.16, rung=0.22, off=0.08)
                + ripples(0, ly, rx * 0.85, ry * 0.85, 3) + bridge(f, rB, zb + 0.14, zb, ang=28) + motor
                + steam(bronze_ok, rx * 0.2, -Hh - 6, 3, 52, 0.5))

    BRZ = sc.add(Cyl(0, yB, z0, 0.95, rB, "rust", vat=True, liquid="bronze", level=bronze_lvl, bands=(0.5,), seams=(25, 95, 155),
                     skirt=0.14, alpha=alpha("extract"), uid="brz", tex=0.16, grime=0.45, front=brz_front))

    def flt_front(rx, ry, Hh, f):
        fh = 0.75 * COS_PHI * f.S
        gx, gy = rx * 0.62, -Hh * 0.55
        gauge = (f'<g transform="translate({gx:.1f},{gy:.1f})"><circle r="6.5" fill="#07080a" stroke="#aab6c6" stroke-width="1.4"/>'
                 f'<circle r="5" fill="#e9edf3"/><path d="M0,0 L3.2,-2.6" stroke="#c0392b" stroke-width="1.2"/><circle r="1" fill="#222"/></g>')
        return (ring_dots(f, 1.35, rF * 1.04, 16) + ring_dots(f, 0.12, rF * 1.04, 14) + gauge
                + ladder(f, 108, rF, 0, 1.35, half=0.14, rung=0.22, off=0.08)
                + lamp(s["clean"], -Hh - fh - 7, 3.2) + leak(s["clean"] == "fail", rx, ry, Hh))

    FLT = sc.add(Cyl(0, yF, z0, 1.35, rF, "stainless", cap=("funnel", 0.75), bands=(0.2, 0.52, 0.8), seams=(30, 120), skirt=0.16,
                     alpha=alpha("clean"), uid="flt", grime=0.4, front=flt_front))

    def slv_front(rx, ry, Hh, f):
        zb = 1.05
        return ring_dots(f, zb, rS * 0.965, 20, clip=False) + ring_dots(f, 0.1, rS, 16) + ladder(f, 105, rS, 0, zb + 0.26, half=0.15, rung=0.22, off=0.08)

    SLV = sc.add(Cyl(0, 0, z0, 1.05, rS, "stainless", vat=True, liquid="silver",
                     level=lvl(n_clean / max(n_raw, 1) if n_raw else 0.05, s["clean"] in ("ok", "warn")),
                     bands=(0.5,), seams=(20, 90, 160), skirt=0.14, alpha=alpha("clean"), uid="slv", grime=0.35, front=slv_front))

    colH = 4.4
    plats = [(1.45, 0.98), (2.85, 0.98)]

    def col_back(rx, ry, Hh, f):
        return "".join(platform(f, rx, zr, rC, ro, rail=0.5, posts=10)[0] for zr, ro in plats)

    def col_front(rx, ry, Hh, f):
        fronts = "".join(platform(f, rx, zr, rC, ro, rail=0.5, posts=10)[1] for zr, ro in plats)
        riser = layered(f, lambda k: "M%.1f,%.1fL%.1f,%.1f" % (*pt(f, rC + 0.06, -28, 0.2, k), *pt(f, rC + 0.06, -28, colH - 0.2, k)),
                        ['stroke="#050608" stroke-width="4.4" stroke-linecap="round"', 'stroke="#59627a" stroke-width="2.6" stroke-linecap="round"',
                         'stroke="#cfd8e6" stroke-width=".8" stroke-opacity=".6" transform="translate(-.7,0)"'],
                        lambda k: math.sin(math.radians(-28) + f.th[k]) * 6)
        top = -Hh - 0.5 * COS_PHI * f.S
        return (fronts + riser + ring_dots(f, 0.18, rC, 12) + ring_dots(f, colH - 0.1, rC, 12)
                + ladder(f, 112, rC, 0, colH - 0.1, half=0.12, rung=0.24, off=0.09) + cage(f, 112, rC, 1.5, colH - 0.2, 6)
                + f'<line x1="0" y1="{top:.1f}" x2="0" y2="{top - 12:.1f}" stroke="#59627a" stroke-width="2"/>'
                + lamp(s["enrich"], top - 18, 3.2) + steam(s["enrich"] in ("ok", "warn"), 0, top - 14, 4, 80)
                + leak(s["enrich"] == "fail", rx, ry, Hh))

    bands = [round(i * 0.3 / colH, 4) for i in range(1, int(colH / 0.3))]
    COL = sc.add(Cyl(xC, 0, z0, colH, rC, "stainless", cap=("dome", 0.5), bands=bands, skirt=0.4, alpha=alpha("enrich"), uid="col",
                     tex=0.3, grime=0.4, back=col_back, front=col_front))

    def gld_front(rx, ry, Hh, f):
        dome = 0.4 * COS_PHI * f.S
        return (ring_dots(f, 0.16, rG, 18) + ring_dots(f, 1.9 - 0.16, rG, 18) + ladder(f, 112, rG, 0, 2.0, half=0.15, rung=0.22, off=0.08)
                + f'<rect x="-2" y="{-Hh - dome - 12:.1f}" width="4" height="14" fill="#59627a"/><rect x="-5" y="{-Hh - dome - 15:.1f}" width="10" height="4" rx="1" fill="#aab6c6"/>'
                + lamp(s["load"], -Hh - dome - 21, 3.2) + steam(s["load"] in ("ok", "warn"), 0, -Hh - dome - 16, 2, 44, 0.6) + leak(s["load"] == "fail", rx, ry, Hh))

    GLD = sc.add(Cyl(xG, 0, z0, 1.9, rG, "mustard", cap=("dome", 0.4), bands=(0.1, 0.9), seams=(30, 100, 165), glow=s["load"] in ("ok", "warn"),
                     window=(lvl(counts["gold"] / total, s["load"] in ("ok", "warn")), P["mustard_hi"]), alpha=alpha("load"), uid="gld", grime=0.5, front=gld_front))

    BCN = sc.add(Mast(xK, 0, z0, 4.0, s["serve"]))

    # ---- the flare stack burns off warnings: a pilot light when quiet, a bigger flame when something is wrong
    flareH = 4.4

    def flare_front(rx, ry, Hh, f):
        wires = layered(f, lambda k: "".join("M%.1f,%.1fL%.1f,%.1f" % (*f.loc(0, 0, flareH * 0.78, k), *pt(f, 2.1, a, 0, k)) for a in (155, 275)),
                        ['stroke="#05060a" stroke-width="1.8" stroke-opacity=".55"', 'stroke="#7a8496" stroke-width=".7" stroke-opacity=".7"'])
        ch = 0.2 * COS_PHI * f.S
        return (wires + f'<rect x="-6" y="{-Hh - 4:.1f}" width="12" height="6" rx="1.5" fill="#1b1f26" stroke="#59627a" stroke-width=".8"/>'
                + flame(flare_level, -Hh - ch - 2) + ladder(f, 112, 0.14, 0, flareH - 0.4, half=0.06, rung=0.26, off=0.05))

    flare = sc.add(Cyl(-1.65, -1.65, z0, flareH, 0.14, "graphite", cap=("cone", 0.2), bands=(0.2, 0.4, 0.6, 0.8), glow="warm", uid="flare", tex=0.3, front=flare_front, extra_top=1.7))

    # ---- props: yellow bollards on the pad edge and a few drums for scale
    for i in range(5):
        b = sc.add(Cyl(arm - 0.48, arm + 1.2 + i * 2.15, z0, 0.62, 0.12, "yellow", bands=(0.55,), uid="bol", tex=0, reflect=False))
        sc.add(Shadow(b, ZT))
    for i in range(4):
        b = sc.add(Cyl(arm + 1.5 + i * 2.2, arm - 0.48, z0, 0.62, 0.12, "yellow", bands=(0.55,), uid="bol", tex=0, reflect=False))
        sc.add(Shadow(b, ZT))
    for px, py, mat in ((1.25, yA - 0.6, "rust"), (1.65, yA - 0.2, "graphite"), (1.45, yA + 0.45, "rust"), (-1.2, yF + 0.9, "graphite")):
        dr = sc.add(Cyl(px, py, z0, 0.6, 0.21, mat, bands=(0.1, 0.5, 0.9), uid="drum", tex=0.2))
        sc.add(Shadow(dr, ZT))

    for u, zb in ((API, z0 + legsH), (BRZ, None), (FLT, None), (SLV, None), (COL, None), (GLD, None), (flare, None)):
        sc.add(Shadow(u, ZT, zb))

    # ---- pipes and valves (flow only when the producing task succeeded)
    zp = z0 + 0.62
    okA = s["extract"] in ("ok", "warn")
    sc.add(Pipe([(0, yA, z0 + legsH - 0.05), (0, yA, zp), (0, yB + rB * 0.9, zp)], active=okA, glass=(0.62, 0.84),
                flanges=(0.0, 0.62, 0.84, 1.0), supports=(0.9,), zfloor=ZT, arrow=0.95))
    sc.add(Valve(0, yA - 0.75, zp, is_open=okA))

    def run(a, b, task, axis, glass=(0.45, 0.72)):
        ok = s[task] in ("ok", "warn")
        if axis == "y":
            p0, p1 = (0, a[0] - a[1] * 0.9, zp), (0, b[0] + b[1] * 0.9, zp)
        else:
            p0, p1 = (a[0] + a[1] * 0.9, 0, zp), (b[0] - b[1] * 0.9, 0, zp)
        sc.add(Pipe([p0, p1], active=ok, glass=glass, flanges=(0.0, glass[0], glass[1], 1.0), supports=(0.2, 0.9), zfloor=ZT))
        t = 0.24
        sc.add(Valve(p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t, zp, is_open=ok))

    run((yB, rB), (yF, rF), "extract", "y")
    run((yF, rF), (0, rS), "clean", "y")
    run((0, rS), (xC, rC), "clean", "x")
    run((xC, rC), (xG, rG), "enrich", "x")
    run((xG, rG), (xK, 0.5), "load", "x")

    # ---- tags
    def b(task):
        return (GLYPH[s[task]], P[s[task]])

    def meta(task, extra):
        return f'{st[task]["secs"]:.2f}s · {extra}'

    tags = [
        (API, 1.0, -34, [("GITHUB API", P["text"], 11, "700", b("extract")), (meta("extract", f"{n_raw} rows"), P["muted"], 9.5, "400")]),
        (BRZ, 2.6, 14, [("BRONZE", P["bronze"], 11, "700"), (f"{n_raw} raw rows", P["muted"], 9.5, "400")]),
        (FLT, 1.2, 0, [("CLEAN", P["text"], 11, "700", b("clean")), (meta("clean", f'{st["clean"]["rows_in"]}→{st["clean"]["rows_out"]}'), P["muted"], 9.5, "400")]),
        (SLV, 2.9, -52, [("SILVER", P["silver"], 11, "700"), (f"{n_clean} clean rows", P["muted"], 9.5, "400")]),
        (COL, 1.5, 38, [("ENRICH", P["text"], 11, "700", b("enrich")), (meta("enrich", "score → tiers"), P["muted"], 9.5, "400")]),
        (GLD, 0.8, 54, [("GOLD · LOAD", P["mustard_hi"], 11, "700", b("load")), (meta("load", f'{counts["gold"]}/{total} repos'), P["muted"], 9.5, "400")]),
        (BCN, 2.4, 30, [("SERVE", P["text"], 11, "700", b("serve")), (meta("serve", "README"), P["muted"], 9.5, "400")]),
    ]
    for u, dz, dx, lines_ in tags:
        sc.add(Tag(u.x, u.y, u.top_z() + dz, lines_, dx=dx))

    f = sc.fit(W, H, left=22, top=54, right=22, bottom=38)
    if yaw_deg is not None:   # test hook: one exact yaw, same scale and offset as the animated render
        f = Fit([math.radians(yaw_deg)] * f.n, f.S, f.ox, f.oy, f.dur, False)
    bad = (sc.check_order(f), sc.check_tags(f)) if check else []

    overall = "fail" if nfail else "warn" if nwarn else "ok"
    word = {"ok": "all systems nominal", "warn": "running with warnings", "fail": "unit down"}[overall]
    flare_word = ("pilot light only", "flare burning off warnings", "flare at full burn")[flare_level]
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
           f'aria-label="{escape(name.title())}: {escape(tagline)}. A realistic 3D isometric data refinery that is this profile\'s own nightly pipeline: GitHub API tower, bronze vat, clean filter, '
           f'silver vat, enrich column, gold tank, a serve mast and a flare stack. Status: {word}; {flare_word}. Last run {escape(ts)}.">',
           defs_svg(),
           f'<rect width="{W}" height="{H}" rx="14" fill="url(#g_bg)"/>']
    cx0, cy0 = f.pt((x_min + x_max) / 2, (y_min + y_max) / 2, 0, 0)
    out.append(f'<ellipse cx="{cx0:.1f}" cy="{cy0 + 30:.1f}" rx="{W * 0.5:.1f}" ry="{H * 0.22:.1f}" fill="url(#g_ao)" opacity=".9"/>')
    out.append(sc.body(f))
    out.append(f'<rect width="{W}" height="{H}" rx="14" fill="url(#g_haze)"/>')
    out.append(f'<rect width="{W}" height="{H}" rx="14" fill="url(#p_conc)" opacity=".08"/>')
    out.append(f'<rect width="{W}" height="{H}" rx="14" fill="url(#g_vig)"/>')
    out.append(sc.tags_svg(f))
    out.append(f'<rect width="{W}" height="{H}" rx="14" fill="none" stroke="{P["border"]}"/>')
    out.append(txt(28, 50, name, P["mustard"], 34, "start", "400", extra='data-font="stencil" letter-spacing="4"'))
    out.append(txt(30, 73, tagline, P["text"], 12.5))
    out.append(txt(30, 91, "this profile is a pipeline. below is its last run.", P["muted"], 10.5))
    out.append(txt(W - 28, 40, f"{GLYPH[overall]} {word}", P[overall], 12, "end", "700"))
    out.append(txt(W - 28, 58, f"last run {ts}", P["muted"], 10.5, "end"))
    lx = 28
    for name, col in (("gold", P["gold"]), ("silver", P["silver"]), ("bronze", P["bronze"])):
        out.append(f'<rect x="{lx}" y="{H - 30}" width="11" height="11" rx="2" fill="{col}"/>')
        out.append(txt(lx + 17, H - 20.5, name, P["muted"], 10.5))
        lx += 78
    out.append(txt(W - 28, H - 20.5, f"vat level = share of rows · valves open = task ok · {flare_word}", P["muted"], 10.5, "end"))
    out.append("</svg>")
    svg = compact("\n".join(out))
    return (svg, bad) if check else svg
