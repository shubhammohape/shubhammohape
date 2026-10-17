"""Industrial detail for the refinery. Everything here is drawn in a unit's local pixel space.

Parts that sit ON a cylinder (ladders, bolts, rails, lattice members) are re-projected at every
sway frame with Fit.loc(), so they slide across the surface exactly like real geometry would.
"""
import math

from iso import COS_PHI, SIN_PHI, P, facing, layered, morph, nid

YELLOW = "#f2c200"
YELLOW_D = "#7a5f00"


def pt(f, r, az_deg, z, k, cx=0.0, cy=0.0):
    a = math.radians(az_deg)
    return f.loc(cx + r * math.cos(a), cy + r * math.sin(a), z, k)


# ---------------------------------------------------------------- fasteners
def ring_dots(f, z, r, n, rad=1.15, color="#aab6c6", phase=0.0, clip=True):
    """A ring of bolt heads on a cylinder. clip=True keeps only the camera-facing half (side walls)."""
    y0 = f.loc(0, 0, z, 0)[1]
    cid = nid("rc")

    def d(k):
        out = []
        for j in range(n):
            x, y = pt(f, r, phase + 360.0 * j / n, z, k)
            out.append(f"M{x:.1f},{y:.1f}l.1,0")
        return "".join(out)

    cp = f'<clipPath id="{cid}"><rect x="-999" y="{y0:.1f}" width="2000" height="999"/></clipPath>' if clip else ""
    ref = f' clip-path="url(#{cid})"' if clip else ""
    return cp + morph(f, "path", d, f'fill="none" stroke="{color}" stroke-width="{2 * rad:.1f}" stroke-linecap="round"{ref}')


# ----------------------------------------------------------------- ladders
def ladder(f, az, r, z0, z1, half=0.15, rung=0.24, off=0.07):
    """A safety-yellow ladder hugging a cylinder. Fades out as it rotates round the far side."""
    R = r + off
    da = math.degrees(half / R)
    zs = [z0 + rung * i for i in range(int((z1 - z0) / rung) + 1)]

    def rails(k):
        out = []
        for a in (az - da, az + da):
            (xa, ya), (xb, yb) = pt(f, R, a, z0, k), pt(f, R, a, z1, k)
            out.append(f"M{xa:.1f},{ya:.1f}L{xb:.1f},{yb:.1f}")
        return "".join(out)

    def rungs(k):
        out = []
        for z in zs:
            (xa, ya), (xb, yb) = pt(f, R, az - da, z, k), pt(f, R, az + da, z, k)
            out.append(f"M{xa:.1f},{ya:.1f}L{xb:.1f},{yb:.1f}")
        return "".join(out)

    gate = lambda k: facing(az, f.th[k]) * 6
    return (layered(f, rails, ['stroke="#060606" stroke-width="4.2" stroke-opacity=".6" stroke-linecap="round"',
                               f'stroke="{YELLOW}" stroke-width="2.3" stroke-linecap="round"',
                               'stroke="#fff6c2" stroke-width=".8" stroke-opacity=".7" transform="translate(-.6,0)"'], gate)
            + layered(f, rungs, ['stroke="#060606" stroke-width="2.6" stroke-opacity=".55"', f'stroke="{YELLOW}" stroke-width="1.5"'], gate))


def cage(f, az, r, z0, z1, hoops=5, rad=0.27, off=0.09, span=105):
    """Ladder safety cage: C-shaped hoops around the climber plus three vertical straps."""
    zs = [z0 + (z1 - z0) * (i + 1) / (hoops + 1) for i in range(hoops)]
    a = math.radians(az)
    R = r + off
    cx, cy, ux, uy, tx, ty = R * math.cos(a), R * math.sin(a), math.cos(a), math.sin(a), -math.sin(a), math.cos(a)

    def at(g, z, k):
        g = math.radians(g)
        return f.loc(cx + rad * (math.sin(g) * tx + math.cos(g) * ux), cy + rad * (math.sin(g) * ty + math.cos(g) * uy), z, k)

    def d(k):
        out = []
        for z in zs:
            for j in range(13):
                x, y = at(-span + 2 * span * j / 12, z, k)
                out.append(("M" if j == 0 else "L") + f"{x:.1f},{y:.1f}")
        for g in (-span * 0.7, 0.0, span * 0.7):
            (xa, ya), (xb, yb) = at(g, z0, k), at(g, z1, k)
            out.append(f"M{xa:.1f},{ya:.1f}L{xb:.1f},{yb:.1f}")
        return "".join(out)

    return layered(f, d, ['stroke="#060606" stroke-width="2.6" stroke-opacity=".5" stroke-linejoin="round"', f'stroke="{YELLOW}" stroke-width="1.2" stroke-opacity=".9" stroke-linejoin="round"'],
                   lambda k: facing(az, f.th[k]) * 6 + 0.3)


# ---------------------------------------------------------------- platforms
def platform(f, rx_px, zr, r_in, r_out, rail=0.55, posts=10, deck="#1a1d23"):
    """A grated ring deck with a yellow handrail. Returns (back, front): draw back BEFORE the shell, front AFTER."""
    S = f.S
    y0 = -zr * COS_PHI * S
    Ro, Ri = r_out * S, r_in * S
    ro_y, ri_y = Ro * SIN_PHI, Ri * SIN_PHI
    yt, ym = y0 - rail * COS_PHI * S, y0 - rail * COS_PHI * S * 0.5
    Rr = Ro * 0.97
    thick = 3.0
    back_posts, front_posts = [], []
    for j in range(posts):
        a = 360.0 * j / posts + 11
        (front_posts if math.sin(math.radians(a + 45)) > 0 else back_posts).append(a)

    def post_d(angles):
        def d(k):
            out = []
            for a in angles:
                (x0, y0_), (x1, y1) = pt(f, r_out * 0.97, a, zr, k), pt(f, r_out * 0.97, a, zr + rail, k)
                out.append(f"M{x0:.1f},{y0_:.1f}L{x1:.1f},{y1:.1f}")
            return "".join(out)
        return d

    post_layers = ['stroke="#060606" stroke-width="3" stroke-opacity=".6" stroke-linecap="round"', f'stroke="{YELLOW}" stroke-width="1.6" stroke-linecap="round"']
    arc = lambda rr, yy, up: (f'M{-rr:.1f},{yy:.1f} A{rr:.1f},{rr * SIN_PHI:.1f} 0 0 {1 if up else 0} {rr:.1f},{yy:.1f}')
    back = [f'<path d="{arc(Ro, y0, True)} Z" fill="{deck}" stroke="#050608" stroke-width="1"/>',
            f'<path d="{arc(Ro, y0, True)}" fill="none" stroke="#7d8898" stroke-width="1" opacity=".5"/>']
    for yy, w in ((yt, 2.2), (ym, 1.4)):
        back.append(f'<path d="{arc(Rr, yy, True)}" fill="none" stroke="#060606" stroke-width="{w + 1.6}" opacity=".5"/>')
        back.append(f'<path d="{arc(Rr, yy, True)}" fill="none" stroke="{YELLOW}" stroke-width="{w}"/>')
    back.append(layered(f, post_d(back_posts), post_layers))
    crescent = f'M{-Ro:.1f},{y0:.1f} A{Ro:.1f},{ro_y:.1f} 0 0 0 {Ro:.1f},{y0:.1f} L{Ri:.1f},{y0:.1f} A{Ri:.1f},{ri_y:.1f} 0 0 1 {-Ri:.1f},{y0:.1f} Z'
    front = [f'<path d="{crescent}" transform="translate(0,{thick})" fill="#07080a"/>',
             f'<path d="{crescent}" fill="url(#p_grate)" stroke="#050608" stroke-width="1"/>',
             f'<path d="{arc(Ro, y0, False)}" fill="none" stroke="#9aa6b6" stroke-width="1.2" opacity=".55"/>']
    for yy, w in ((ym, 1.4), (yt, 2.2)):
        front.append(f'<path d="{arc(Rr, yy, False)}" fill="none" stroke="#060606" stroke-width="{w + 1.6}" opacity=".5"/>')
        front.append(f'<path d="{arc(Rr, yy, False)}" fill="none" stroke="{YELLOW}" stroke-width="{w}"/>')
    front.append(layered(f, post_d(front_posts), post_layers))
    return "".join(back), "".join(front)


# ----------------------------------------------------- legs / lattice / bridge
def tower_legs(f, r_top, r_bot, height, n=4, az0=45):
    """Splayed tower legs with a ring beam and X bracing; local z runs from 0 (tank bottom) down to -height."""
    legs = [az0 + 360.0 * j / n for j in range(n)]

    def d(k):
        out = []
        for a in legs:
            (xa, ya), (xb, yb) = pt(f, r_top, a, 0, k), pt(f, r_bot, a, -height, k)
            out.append(f"M{xa:.1f},{ya:.1f}L{xb:.1f},{yb:.1f}")
        for j in range(n):
            a0, a1 = legs[j], legs[(j + 1) % n]
            ra = r_top + (r_bot - r_top) * 0.2
            rb = r_top + (r_bot - r_top) * 0.75
            for (aa, za, ab, zb) in ((a0, -height * 0.2, a1, -height * 0.75), (a1, -height * 0.2, a0, -height * 0.75)):
                ra_ = r_top + (r_bot - r_top) * (-za / height)
                rb_ = r_top + (r_bot - r_top) * (-zb / height)
                (xa, ya), (xb, yb) = pt(f, ra_, aa, za, k), pt(f, rb_, ab, zb, k)
                out.append(f"M{xa:.1f},{ya:.1f}L{xb:.1f},{yb:.1f}")
            rr = r_top + (r_bot - r_top) * 0.5
            (xa, ya), (xb, yb) = pt(f, rr, a0, -height * 0.5, k), pt(f, rr, a1, -height * 0.5, k)
            out.append(f"M{xa:.1f},{ya:.1f}L{xb:.1f},{yb:.1f}")
        return "".join(out)

    return layered(f, d, ['stroke="#050608" stroke-width="5.4" stroke-linecap="round" stroke-linejoin="round"',
                          'stroke="#3b4350" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"',
                          'stroke="#9aa6b6" stroke-width="1" stroke-opacity=".7" transform="translate(-.8,-.8)"'])


def lattice(f, r_base, r_top, z0, z1, levels=9, az0=90):
    """A three-legged lattice radio mast: legs, ring triangles and zig-zag bracing."""
    legs = [az0 + 120 * j for j in range(3)]
    rad = lambda i: r_base + (r_top - r_base) * i / levels
    zed = lambda i: z0 + (z1 - z0) * i / levels

    def d(k):
        out = []
        for a in legs:
            (xa, ya), (xb, yb) = pt(f, r_base, a, z0, k), pt(f, r_top, a, z1, k)
            out.append(f"M{xa:.1f},{ya:.1f}L{xb:.1f},{yb:.1f}")
        for i in range(levels + 1):
            p = [pt(f, rad(i), a, zed(i), k) for a in legs]
            out.append(f"M{p[0][0]:.1f},{p[0][1]:.1f}L{p[1][0]:.1f},{p[1][1]:.1f}L{p[2][0]:.1f},{p[2][1]:.1f}Z")
        for i in range(levels):
            for j, a in enumerate(legs):
                b = legs[(j + (1 if i % 2 == 0 else -1)) % 3]
                (xa, ya), (xb, yb) = pt(f, rad(i), a, zed(i), k), pt(f, rad(i + 1), b, zed(i + 1), k)
                out.append(f"M{xa:.1f},{ya:.1f}L{xb:.1f},{yb:.1f}")
        return "".join(out)

    return layered(f, d, ['stroke="#050608" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"',
                          'stroke="#8f9bad" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"'])


def bridge(f, r, z, zrim, ang=25, half_w=0.11, thick=0.07):
    """A beam across the top of a vat on end supports (carries the agitator motor)."""
    ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    L = r * 1.08

    def top(k):
        c = [(-L, -half_w), (L, -half_w), (L, half_w), (-L, half_w)]
        return " ".join("%.1f,%.1f" % f.loc(ca * u - sa * v, sa * u + ca * v, z + thick, k) for u, v in c)

    def side(k):
        c = [(-L, half_w, z), (L, half_w, z), (L, half_w, z + thick), (-L, half_w, z + thick)]
        return " ".join("%.1f,%.1f" % f.loc(ca * u - sa * v, sa * u + ca * v, zz, k) for u, v, zz in c)

    def legs(k):
        out = []
        for s in (-1, 1):
            xa, ya = f.loc(ca * L * s, sa * L * s, z, k)
            xb, yb = f.loc(ca * L * s * 0.96, sa * L * s * 0.96, zrim, k)
            out.append(f"M{xa:.1f},{ya:.1f}L{xb:.1f},{yb:.1f}")
        return "".join(out)

    return (layered(f, legs, ['stroke="#050608" stroke-width="4.2" stroke-linecap="round"', 'stroke="#59627a" stroke-width="2.4" stroke-linecap="round"'])
            + morph(f, "polygon", side, 'fill="#1b1f26" stroke="#050608" stroke-width=".8"', "points")
            + morph(f, "polygon", top, f'fill="{YELLOW}" stroke="#050608" stroke-width=".8"', "points"))


# ------------------------------------------------------------------ small parts
def lamp(status, cy, r=3.4):
    """A signal lamp with a soft glow (radial gradient, no filter)."""
    blink = status in ("warn", "fail")
    vals = "1;.15;1" if blink else "1;.65;1"
    dur = "0.9s" if blink else "3s"
    glow = "" if status == "skip" else (f'<circle cx="0" cy="{cy:.1f}" r="{r * 3.6:.1f}" fill="url(#g_lamp_{status})">'
                                        f'<animate attributeName="opacity" values="{vals}" dur="{dur}" repeatCount="indefinite"/></circle>')
    col = {"ok": P["mustard_hi"], "warn": P["warn"], "fail": P["fail"], "skip": "#4a4f59"}[status]
    return (glow + f'<circle cx="0" cy="{cy:.1f}" r="{r + 1.6:.1f}" fill="#07080a" stroke="#59627a" stroke-width=".8"/>'
            f'<circle cx="0" cy="{cy:.1f}" r="{r:.1f}" fill="{col}"><animate attributeName="opacity" values="{vals}" dur="{dur}" repeatCount="indefinite"/></circle>'
            f'<circle cx="{-r * .3:.1f}" cy="{cy - r * .3:.1f}" r="{r * .35:.1f}" fill="#fff" opacity=".7"/>')


def leak(on, rx, ry, H):
    if not on:
        return ""
    out = []
    for i, dx in enumerate((-0.5, 0.1, 0.6)):
        x = dx * rx
        out.append(f'<circle cx="{x:.1f}" cy="{-H * 0.3:.1f}" r="2.2" fill="{P["fail"]}">'
                   f'<animate attributeName="cy" values="{-H * 0.3:.1f};{ry + 16:.1f}" dur="1.1s" begin="{i * 0.35}s" repeatCount="indefinite"/>'
                   f'<animate attributeName="opacity" values="1;0" dur="1.1s" begin="{i * 0.35}s" repeatCount="indefinite"/></circle>')
    return "".join(out)


def steam(on, cx, cy, n=4, rise=70, spread=1.0):
    """Soft rising puffs (radial gradients, drifting right with the wind)."""
    if not on:
        return ""
    out = []
    for i in range(n):
        b = i * 3.4 / n
        out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="4" fill="url(#g_steam)" opacity="0">'
                   f'<animate attributeName="cy" values="{cy:.1f};{cy - rise:.1f}" dur="3.4s" begin="{b:.2f}s" repeatCount="indefinite"/>'
                   f'<animate attributeName="cx" values="{cx:.1f};{cx + 16 * spread:.1f}" dur="3.4s" begin="{b:.2f}s" repeatCount="indefinite"/>'
                   f'<animate attributeName="r" values="4;22" dur="3.4s" begin="{b:.2f}s" repeatCount="indefinite"/>'
                   f'<animate attributeName="opacity" values="0;.85;0" dur="3.4s" begin="{b:.2f}s" repeatCount="indefinite"/></circle>')
    return "".join(out)


def rings(on, cy, n=3, reach=64.0, color=None):
    if not on:
        return ""
    color = color or P["mustard_hi"]
    out = []
    for i in range(n):
        out.append(f'<ellipse cx="0" cy="{cy:.1f}" rx="4" ry="2" fill="none" stroke="{color}" stroke-width="1.4" opacity="0">'
                   f'<animate attributeName="rx" values="4;{reach}" dur="3s" begin="{i}s" repeatCount="indefinite"/>'
                   f'<animate attributeName="ry" values="2;{reach / 2}" dur="3s" begin="{i}s" repeatCount="indefinite"/>'
                   f'<animate attributeName="opacity" values=".8;0" dur="3s" begin="{i}s" repeatCount="indefinite"/></ellipse>')
    return "".join(out)


def ripples(cx, cy, rx, ry, n=3):
    """Concentric ripples spreading across a liquid surface from an agitator."""
    out = []
    for i in range(n):
        out.append(f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="2" ry="1" fill="none" stroke="#ffd9a0" stroke-width="1" opacity="0">'
                   f'<animate attributeName="rx" values="2;{rx:.1f}" dur="3.6s" begin="{i * 1.2}s" repeatCount="indefinite"/>'
                   f'<animate attributeName="ry" values="1;{ry:.1f}" dur="3.6s" begin="{i * 1.2}s" repeatCount="indefinite"/>'
                   f'<animate attributeName="opacity" values=".55;0" dur="3.6s" begin="{i * 1.2}s" repeatCount="indefinite"/></ellipse>')
    return "".join(out)


def dish(cx, cy, size, tilt=-35, mat="stainless"):
    """A small parabolic dish with a feed horn."""
    return (f'<g transform="translate({cx:.1f},{cy:.1f}) rotate({tilt})">'
            f'<line x1="0" y1="0" x2="0" y2="{size * .9:.1f}" stroke="#3b4350" stroke-width="2"/>'
            f'<ellipse cx="0" cy="0" rx="{size * .28:.1f}" ry="{size:.1f}" fill="url(#g_{mat})" stroke="#050608" stroke-width=".8"/>'
            f'<ellipse cx="{size * .05:.1f}" cy="0" rx="{size * .18:.1f}" ry="{size * .8:.1f}" fill="#0d0f13" opacity=".7"/>'
            f'<line x1="{size * .05:.1f}" y1="0" x2="{size * .9:.1f}" y2="0" stroke="#aab6c6" stroke-width="1.2"/>'
            f'<circle cx="{size * .9:.1f}" cy="0" r="2" fill="#aab6c6"/></g>')


def flame(level, cy=0.0):
    """A live flare flame. level 0 = pilot light, 1 = warning burn, 2 = emergency."""
    h = (14, 46, 78)[level]
    w = (3.4, 10.5, 17)[level]

    def drop(wv, hv, sway):
        tip = sway * wv
        return (f"M0,0 C{-wv:.1f},{-hv * .15:.1f} {-wv * .85:.1f},{-hv * .62:.1f} {tip:.1f},{-hv:.1f} "
                f"C{wv * .85:.1f},{-hv * .62:.1f} {wv:.1f},{-hv * .15:.1f} 0,0 Z")

    outer = [drop(w, h * a, s) for a, s in ((0.9, -.25), (1.05, .15), (1.15, .4), (.95, -.1), (1.0, .25))]
    inner = [drop(w * .55, h * a * .62, s) for a, s in ((1.0, .1), (.9, -.2), (1.1, .3), (.95, 0.0), (1.05, -.15))]
    glow_r = (34, 100, 170)[level]
    o = [f'<g transform="translate(0,{cy:.1f})">',
         f'<ellipse cx="0" cy="{-h * .5:.1f}" rx="{glow_r:.1f}" ry="{glow_r * .85:.1f}" fill="url(#g_warm)"><animate attributeName="opacity" values=".9;.55;1;.7;.9" dur="0.7s" repeatCount="indefinite"/></ellipse>',
         f'<path d="{outer[0]}" fill="url(#g_flame)"><animate attributeName="d" values="{";".join(outer + [outer[0]])}" dur="0.95s" repeatCount="indefinite"/></path>',
         f'<path d="{inner[0]}" fill="url(#g_flame2)"><animate attributeName="d" values="{";".join(inner + [inner[0]])}" dur="0.72s" repeatCount="indefinite"/></path>']
    for i in range(2 + level * 3):   # embers
        dx = (i * 7 % 13 - 6) * (1 + level)
        o.append(f'<circle cx="0" cy="{-h * .6:.1f}" r="{1.0 + level * .4:.1f}" fill="#ffb24a" opacity="0">'
                 f'<animate attributeName="cy" values="{-h * .6:.1f};{-h - 50 - level * 25:.1f}" dur="{1.6 + (i % 3) * .5:.1f}s" begin="{i * .37:.2f}s" repeatCount="indefinite"/>'
                 f'<animate attributeName="cx" values="0;{dx:.1f}" dur="{1.6 + (i % 3) * .5:.1f}s" begin="{i * .37:.2f}s" repeatCount="indefinite"/>'
                 f'<animate attributeName="opacity" values="0;1;0" dur="{1.6 + (i % 3) * .5:.1f}s" begin="{i * .37:.2f}s" repeatCount="indefinite"/></circle>')
    o.append("</g>")
    return "".join(o)


def beam(cy, length=300):
    """A slow lighthouse sweep seen at isometric angle (a rotating wedge squashed to the ground plane)."""
    return (f'<g transform="translate(0,{cy:.1f}) scale(1,.5)"><g>'
            f'<polygon points="0,0 {length},-44 {length},44" fill="url(#g_beam)" opacity=".16"/>'
            f'<polygon points="0,0 {length},-16 {length},16" fill="url(#g_beam)" opacity=".26"/>'
            f'<animateTransform attributeName="transform" type="rotate" values="0;360" dur="9s" repeatCount="indefinite"/></g></g>')
