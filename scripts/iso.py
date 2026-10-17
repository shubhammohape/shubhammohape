"""An isometric engine that emits SMIL-animated SVG with a physically-motivated look.

The camera yaw sways inside one quadrant (45 deg +/- SWAY). In that range the visible side
faces and the painter's order of an axis-aligned scene never change, so we precompute K+1
frames and let SMIL interpolate:

  * vertical cylinders have the same silhouette at every yaw, so a unit is one group that only
    translates; details that sit ON the surface (ladders, bolts, seams) are re-projected per frame;
  * boxes, slabs, pipes, shadows and lattices morph their `points` / `d` between frames.

Realism comes from layering, not from SVG filters (a filter on an animated image repaints every
frame): key-light gradients with a specular band, an environment-reflection overlay, brushed-steel
and concrete grain tiles, contact shadows plus real directional cast shadows that move with the
sway, wet-floor reflections, light pools under emissive parts, and a little atmosphere.

No script, no foreignObject, no external resources: it renders as a plain <img> on GitHub.
"""
import itertools
import math
import random
from html import escape

import textures
from theme import FONT, P

SIN_PHI = 0.5
COS_PHI = math.sqrt(3) / 2
SIN45 = COS45 = math.sqrt(0.5)
YAW0, SWAY, K = 45.0, 13.0, 4
# Four keyframes per cycle (yaw 45, 58, 45, 32) with Bezier easing that reproduces the sine exactly:
# each interval's control points are the Hermite end-slopes of sin() divided by three.
KS = "0.333 0.524 0.667 1;0.333 0 0.667 0.476;0.333 0.524 0.667 1;0.333 0 0.667 0.476"
SHADOW = (0.46, -0.30)          # floor-plane shadow offset per unit of height (light from the left)

TEX = {"conc": textures.concrete(7, 128), "brush": textures.brushed(3)}


def thetas(sway=SWAY, k=K):
    return [math.radians(YAW0 + sway * math.sin(2 * math.pi * i / k)) for i in range(k + 1)]


def proj(x, y, z, th):
    """World -> unscaled screen. x grows right-down, y grows left-down, z is up."""
    c, s = math.cos(th), math.sin(th)
    return x * c - y * s, (x * s + y * c) * SIN_PHI - z * COS_PHI


def depth(x, y, z=0.0):
    return x * SIN45 + y * COS45 + z * 0.001


_ids = itertools.count(1)


def reset_ids():
    global _ids
    _ids = itertools.count(1)


def nid(prefix="i"):
    return f"{prefix}{next(_ids)}"


class Fit:
    """Maps projection units to pixels and carries the animation settings."""

    def __init__(self, ths, S, ox, oy, dur="32s", animate=True):
        self.th, self.S, self.ox, self.oy, self.dur, self.animate = ths, S, ox, oy, dur, animate
        self.n = len(ths)

    def pt(self, x, y, z, k):
        px, py = proj(x, y, z, self.th[k])
        return px * self.S + self.ox, py * self.S + self.oy

    def loc(self, x, y, z, k):
        """Unit-local projection (pixels relative to the unit's base centre)."""
        px, py = proj(x, y, z, self.th[k])
        return px * self.S, py * self.S


# ------------------------------------------------------------- animation helpers
def spline(f, values):
    return f'calcMode="spline" keySplines="{KS}" ' if len(values) == 5 else ""


def anim(f, attr, values, extra=""):
    return (f'<animate attributeName="{attr}" dur="{f.dur}" repeatCount="indefinite" {extra}{spline(f, values)}'
            f'values="{";".join(values)}"/>')


def a_translate(frames, f):
    if not f.animate or len({(round(x, 1), round(y, 1)) for x, y in frames}) == 1:
        return ""
    vals = ";".join(f"{x:.1f},{y:.1f}" for x, y in frames)
    return (f'<animateTransform attributeName="transform" type="translate" dur="{f.dur}" '
            f'repeatCount="indefinite" {spline(f, frames)}values="{vals}"/>')


def pts_attr(fr, prec=1):
    return " ".join(f"{x:.{prec}f},{y:.{prec}f}" for x, y in fr)


def morph(f, tag, build, attrs="", attr="d", gate=None, ident=None, inner=""):
    """An element whose geometry (and optionally opacity) is re-evaluated at every sway frame.

    build(k) -> the value of `attr` at frame k; gate(k) -> opacity at frame k (or None)."""
    vals = [build(k) for k in range(f.n)]
    ops = [f"{max(0.0, min(1.0, gate(k))):.2f}" for k in range(f.n)] if gate else None
    idattr = f'id="{ident}" ' if ident else ""
    o = f'<{tag} {idattr}{attr}="{vals[0]}" {attrs}'
    if ops is not None:
        o += f' opacity="{ops[0]}"'
    body = ""
    if f.animate:
        if len(set(vals)) > 1:
            body += anim(f, attr, vals)
        if ops is not None and len(set(ops)) > 1:
            body += anim(f, "opacity", ops)
    body += inner
    return f"{o}>{body}</{tag}>" if body else f"{o}/>"


def poly_morph(f, pts_fn, attrs="", gate=None, ident=None, inner="", prec=1):
    return morph(f, "polygon", lambda k: pts_attr(pts_fn(k), prec), attrs, "points", gate, ident, inner)


def line_morph(f, pts_fn, attrs="", gate=None, ident=None, inner="", prec=1):
    return morph(f, "polyline", lambda k: pts_attr(pts_fn(k), prec), attrs, "points", gate, ident, inner)


def layered(f, build, layers, gate=None, attr="d", tag="path"):
    """Define one morphing shape once and stroke it several times (outline, body, highlight) via <use>."""
    ident = nid("ly")
    shape = morph(f, tag, build, "", attr, gate, ident)
    return f"<defs>{shape}</defs>" + "".join(f'<use href="#{ident}" fill="none" {a}/>' for a in layers)


def poly_layers(f, pts_fn, layers, gate=None):
    return layered(f, lambda k: pts_attr(pts_fn(k)), layers, gate, "points", "polyline")


def facing(az_deg, th):
    """How much a surface point at azimuth az faces the camera (>0 visible, 1 = dead centre)."""
    return math.sin(math.radians(az_deg) + th)


def txt(x, y, s, fill, size=11, anchor="start", weight="400", halo=False, extra=""):
    h = f'stroke="{P["bg"]}" stroke-width="3.5" paint-order="stroke" stroke-linejoin="round" ' if halo else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" fill="{fill}" font-size="{size}" text-anchor="{anchor}" '
            f'font-weight="{weight}" font-family="{FONT}" {h}{extra}>{escape(str(s))}</text>')


# ------------------------------------------------------------------- materials
SHADE = {
    # horizontal key-light ramps: edge, rolled shadow, diffuse, specular band, bounce, core shadow, rim bounce
    "graphite": [(0, "#08090b"), (.06, "#14171c"), (.16, "#343c49"), (.235, "#7d8898"), (.29, "#4d5666"),
                 (.42, "#2b313b"), (.62, "#1b1f26"), (.84, "#111419"), (.94, "#3b4553"), (1, "#07080a")],
    "stainless": [(0, "#171a20"), (.07, "#3a424f"), (.17, "#9aa6b6"), (.24, "#eef3fa"), (.30, "#b5c0cf"),
                  (.44, "#707c8e"), (.66, "#424b59"), (.86, "#2b323d"), (.95, "#6c788c"), (1, "#14171c")],
    "mustard": [(0, "#1c1500"), (.06, "#4d3b00"), (.16, "#b08700"), (.235, "#ffe27a"), (.29, "#e8b505"),
                (.44, "#b58b00"), (.66, "#6e5400"), (.86, "#3f3000"), (.95, "#8c6c00"), (1, "#150f00")],
    "rust": [(0, "#150b05"), (.06, "#2f1b0e"), (.16, "#8a4f26"), (.235, "#d99a62"), (.29, "#a9622f"),
             (.44, "#6d3d1c"), (.66, "#3d2211"), (.86, "#25150a"), (.95, "#5c3a20"), (1, "#0d0603")],
    "yellow": [(0, "#201900"), (.1, "#7a5f00"), (.25, "#f2c200"), (.34, "#ffe46b"), (.5, "#d2a600"),
               (.8, "#6d5500"), (1, "#1b1400")],
}
EDGE = {"graphite": "#050608", "stainless": "#0d0f13", "mustard": "#120d00", "rust": "#0a0503", "yellow": "#120d00"}
LIGHT = {"graphite": "#8995a8", "stainless": "#f0f5fb", "mustard": "#ffe58a", "rust": "#e0a674", "yellow": "#ffe985"}
LAMP = {"ok": P["mustard_hi"], "warn": P["warn"], "fail": P["fail"], "skip": "#6b7080"}


def defs_svg():
    d = ["<defs>"]
    for name, stops in SHADE.items():
        d.append(f'<linearGradient id="g_{name}" x1="0" x2="1" y1="0" y2="0">'
                 + "".join(f'<stop offset="{o}" stop-color="{c}"/>' for o, c in stops) + "</linearGradient>")
    # environment reflection on vertical metal: sky on top, a dark horizon band, warm floor bounce, ambient occlusion
    d.append('<linearGradient id="g_env" x1="0" x2="0" y1="0" y2="1">'
             '<stop offset="0" stop-color="#c8d6ee" stop-opacity=".46"/><stop offset=".16" stop-color="#8da0c0" stop-opacity=".18"/>'
             '<stop offset=".42" stop-color="#000" stop-opacity="0"/><stop offset=".70" stop-color="#000" stop-opacity=".18"/>'
             f'<stop offset=".88" stop-color="{P["mustard"]}" stop-opacity=".16"/><stop offset="1" stop-color="#000" stop-opacity=".55"/></linearGradient>')
    d.append('<linearGradient id="g_envtop" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#c8d6ee" stop-opacity=".40"/>'
             '<stop offset=".5" stop-color="#8da0c0" stop-opacity=".08"/><stop offset="1" stop-color="#000" stop-opacity=".12"/></linearGradient>')
    d.append('<linearGradient id="g_streak" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#000" stop-opacity=".55"/><stop offset="1" stop-color="#000" stop-opacity="0"/></linearGradient>')
    d.append('<linearGradient id="g_haze" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#05060a" stop-opacity=".55"/>'
             '<stop offset=".5" stop-color="#05060a" stop-opacity="0"/></linearGradient>')
    d.append('<linearGradient id="g_conc_side" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#3a3d45"/>'
             '<stop offset=".5" stop-color="#23262c"/><stop offset="1" stop-color="#0d0e11"/></linearGradient>')
    d.append('<linearGradient id="g_fade" gradientUnits="userSpaceOnUse" x1="0" y1="2" x2="0" y2="-40"><stop offset="0" stop-color="#fff"/>'
             '<stop offset="1" stop-color="#000"/></linearGradient>')
    d.append('<mask id="m_refl" maskUnits="userSpaceOnUse" x="-500" y="-70" width="1000" height="90"><rect x="-500" y="-70" width="1000" height="90" fill="url(#g_fade)"/></mask>')
    d.append('<radialGradient id="g_ao"><stop offset="0" stop-color="#000" stop-opacity=".7"/>'
             '<stop offset=".6" stop-color="#000" stop-opacity=".3"/><stop offset="1" stop-color="#000" stop-opacity="0"/></radialGradient>')
    d.append(f'<radialGradient id="g_pool"><stop offset="0" stop-color="{P["mustard_hi"]}" stop-opacity=".55"/>'
             f'<stop offset=".45" stop-color="{P["mustard"]}" stop-opacity=".2"/><stop offset="1" stop-color="{P["mustard"]}" stop-opacity="0"/></radialGradient>')
    d.append('<radialGradient id="g_lightpool"><stop offset="0" stop-color="#fff1c9" stop-opacity=".5"/>'
             '<stop offset=".5" stop-color="#ffd98a" stop-opacity=".13"/><stop offset="1" stop-color="#ffd98a" stop-opacity="0"/></radialGradient>')
    d.append('<radialGradient id="g_warm"><stop offset="0" stop-color="#ff9a3c" stop-opacity=".5"/>'
             '<stop offset=".5" stop-color="#ff7a1a" stop-opacity=".18"/><stop offset="1" stop-color="#ff7a1a" stop-opacity="0"/></radialGradient>')
    d.append('<radialGradient id="g_steam"><stop offset="0" stop-color="#e8edf5" stop-opacity=".5"/>'
             '<stop offset=".55" stop-color="#cfd6e2" stop-opacity=".22"/><stop offset="1" stop-color="#cfd6e2" stop-opacity="0"/></radialGradient>')
    d.append('<radialGradient id="g_top" cx=".38" cy=".35" r=".8"><stop offset="0" stop-color="#ffffff" stop-opacity=".32"/>'
             '<stop offset="1" stop-color="#000" stop-opacity=".25"/></radialGradient>')
    d.append('<radialGradient id="g_bg" cx=".5" cy=".66" r=".75"><stop offset="0" stop-color="#1b160c"/>'
             '<stop offset=".5" stop-color="#0e0d0c"/><stop offset="1" stop-color="#050506"/></radialGradient>')
    d.append('<radialGradient id="g_vig" cx=".5" cy=".5" r=".72"><stop offset=".55" stop-color="#000" stop-opacity="0"/>'
             '<stop offset="1" stop-color="#000" stop-opacity=".62"/></radialGradient>')
    d.append('<linearGradient id="g_beam" x1="0" x2="1" y1="0" y2="0"><stop offset="0" stop-color="#ffe58a" stop-opacity=".5"/>'
             '<stop offset="1" stop-color="#ffe58a" stop-opacity="0"/></linearGradient>')
    d.append('<linearGradient id="g_flame" x1="0" x2="0" y1="1" y2="0"><stop offset="0" stop-color="#ff5a12"/>'
             '<stop offset=".5" stop-color="#ff9a1f"/><stop offset="1" stop-color="#ffd36a" stop-opacity=".85"/></linearGradient>')
    d.append('<linearGradient id="g_flame2" x1="0" x2="0" y1="1" y2="0"><stop offset="0" stop-color="#ffd36a"/>'
             '<stop offset="1" stop-color="#fff6d6" stop-opacity=".9"/></linearGradient>')
    for k, c in LAMP.items():
        d.append(f'<radialGradient id="g_lamp_{k}"><stop offset="0" stop-color="{c}" stop-opacity=".9"/>'
                 f'<stop offset=".4" stop-color="{c}" stop-opacity=".3"/><stop offset="1" stop-color="{c}" stop-opacity="0"/></radialGradient>')
    d.append(f'<pattern id="p_conc" width="128" height="128" patternUnits="userSpaceOnUse"><image href="{TEX["conc"]}" width="128" height="128"/></pattern>')
    d.append(f'<pattern id="p_brush" width="64" height="96" patternUnits="userSpaceOnUse"><image href="{TEX["brush"]}" width="64" height="96"/></pattern>')
    d.append('<pattern id="p_grate" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
             '<rect width="6" height="6" fill="#16181d"/><rect width="2" height="6" fill="#2b303a"/></pattern>')
    d.append("</defs>")
    return "".join(d)


# ------------------------------------------------------------------ objects
class Cyl:
    """A vertical cylinder unit. Same silhouette at every yaw -> translate-only animation for the shell."""

    def __init__(self, x, y, z0, h, r, mat="graphite", cap=None, bands=(), seams=(), vat=False, liquid=None, level=0.6,
                 window=None, glow=False, back=None, front=None, over=None, reflect=True, tex=0.22, alpha=1.0, uid="c",
                 skirt=0.0, extra_top=0.0, grime=0.0):
        self.x, self.y, self.z0, self.h, self.r, self.mat = x, y, z0, h, r, mat
        self.cap, self.bands, self.seams, self.vat, self.liquid, self.level = cap, bands, seams, vat, liquid, level
        self.window, self.glow, self.back, self.front, self.over = window, glow, back, front, over
        self.reflect, self.tex, self.alpha, self.uid, self.skirt, self.extra_top, self.grime = reflect, tex, alpha, uid, skirt, extra_top, grime

    @property
    def depth(self):
        return depth(self.x, self.y, self.z0)

    def top_z(self):
        return self.z0 + self.h + (self.cap[1] if self.cap else 0.0)

    def bbox_pts(self, th):
        cx, cy = proj(self.x, self.y, self.z0, th)
        tx, ty = proj(self.x, self.y, self.top_z() + self.extra_top, th)
        r = self.r * (1.3 if self.cap and self.cap[0] == "funnel" else 1.0)
        ry = self.r * SIN_PHI
        return [(cx - r, cy + ry), (cx + r, cy + ry), (tx - r, ty - ry), (tx + r, ty - ry)]

    # -- the painted shell: body, bands, top/cap, sight window ----------------------------
    def shell(self, f, reflect=False):
        S = f.S
        rx, ry, H = self.r * S, self.r * S * SIN_PHI, self.h * COS_PHI * S
        m = self.mat
        edge, light = EDGE[m], LIGHT[m]
        o = []
        body = f'M{-rx:.1f},{-H:.1f} L{-rx:.1f},0 A{rx:.1f},{ry:.1f} 0 0 0 {rx:.1f},0 L{rx:.1f},{-H:.1f} Z'
        o.append(f'<path d="{body}" fill="url(#g_{m})" stroke="{edge}" stroke-width="0.8"/>')
        if not reflect:
            o.append(f'<path d="{body}" fill="url(#g_env)"/>')
            if self.tex:
                o.append(f'<path d="{body}" fill="url(#p_brush)" opacity="{self.tex}"/>')
            if self.grime:   # rain-stain streaks running down from the rim
                rng = random.Random(self.uid)
                for _ in range(7):
                    sw, sx = rng.uniform(1.6, 4.8), rng.uniform(-0.86, 0.86) * rx
                    o.append(f'<rect x="{sx - sw / 2:.1f}" y="{-H:.1f}" width="{sw:.1f}" height="{rng.uniform(.25, .75) * H:.1f}" fill="url(#g_streak)" opacity="{self.grime}"/>')
        for b in self.bands:   # weld seams: a dark groove with a lit lip just under it
            yb = -H * b
            o.append(f'<path d="M{-rx:.1f},{yb:.1f} A{rx:.1f},{ry:.1f} 0 0 0 {rx:.1f},{yb:.1f}" fill="none" stroke="{edge}" stroke-width="1.5" opacity=".9"/>')
            if not reflect:
                o.append(f'<path d="M{-rx:.1f},{yb + 1.6:.1f} A{rx:.1f},{ry:.1f} 0 0 0 {rx:.1f},{yb + 1.6:.1f}" fill="none" stroke="{light}" stroke-width="0.8" opacity=".22"/>')
        if self.skirt:
            sy = -self.skirt * COS_PHI * S
            o.append(f'<path d="M{-rx:.1f},{sy:.1f} A{rx:.1f},{ry:.1f} 0 0 0 {rx:.1f},{sy:.1f}" fill="none" stroke="{edge}" stroke-width="2"/>')
        cap = self.cap
        if self.vat:
            o.append(self._vat_top(f, rx, ry, H, reflect))
        elif cap and cap[0] == "dome":
            dh = cap[1] * COS_PHI * S
            d = f'M{-rx:.1f},{-H:.1f} A{rx:.1f},{ry:.1f} 0 0 0 {rx:.1f},{-H:.1f} A{rx:.1f},{dh:.1f} 0 0 0 {-rx:.1f},{-H:.1f} Z'
            o.append(f'<path d="{d}" fill="url(#g_{m})" stroke="{edge}" stroke-width="0.8"/>')
            if not reflect:
                o.append(f'<path d="{d}" fill="url(#g_envtop)"/>')
        elif cap and cap[0] == "cone":
            ch = cap[1] * COS_PHI * S
            d = f'M{-rx * 1.12:.1f},{-H:.1f} L0,{-H - ch:.1f} L{rx * 1.12:.1f},{-H:.1f} A{rx * 1.12:.1f},{ry * 1.12:.1f} 0 0 1 {-rx * 1.12:.1f},{-H:.1f} Z'
            o.append(f'<path d="{d}" fill="url(#g_{m})" stroke="{edge}" stroke-width="0.8"/>')
            if not reflect:
                o.append(f'<path d="{d}" fill="url(#g_envtop)"/>')
        elif cap and cap[0] == "funnel":
            fh = cap[1] * COS_PHI * S
            rt, rty = rx * 1.3, ry * 1.3
            d = (f'M{-rx:.1f},{-H:.1f} L{-rt:.1f},{-H - fh:.1f} A{rt:.1f},{rty:.1f} 0 0 0 {rt:.1f},{-H - fh:.1f} '
                 f'L{rx:.1f},{-H:.1f} A{rx:.1f},{ry:.1f} 0 0 1 {-rx:.1f},{-H:.1f} Z')
            o.append(f'<path d="{d}" fill="url(#g_{m})" stroke="{edge}" stroke-width="0.8"/>')
            if not reflect:
                o.append(f'<path d="{d}" fill="url(#g_envtop)"/>')
            o.append(f'<ellipse cx="0" cy="{-H - fh:.1f}" rx="{rt:.1f}" ry="{rty:.1f}" fill="#07080a" stroke="{EDGE[m]}" stroke-width="2.6"/>')
            o.append(f'<ellipse cx="0" cy="{-H - fh:.1f}" rx="{rt:.1f}" ry="{rty:.1f}" fill="none" stroke="{light}" stroke-width="1" stroke-opacity=".55"/>')
            o.append(f'<ellipse cx="0" cy="{-H - fh + 1.5:.1f}" rx="{rt * 0.78:.1f}" ry="{rty * 0.78:.1f}" fill="url(#g_flame)" opacity=".28"/>')
        else:
            o.append(f'<ellipse cx="0" cy="{-H:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" fill="url(#g_{m})" stroke="{light}" stroke-width="1"/>')
            o.append(f'<ellipse cx="0" cy="{-H:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" fill="url(#g_top)"/>')
        if self.window:
            lvl, col = self.window
            wx = max(5.0, 0.27 * rx)
            y0, y1 = -0.12 * H, -0.88 * H
            o.append(f'<rect x="{-wx - 2.5:.1f}" y="{y1 - 2.5:.1f}" width="{2 * wx + 5:.1f}" height="{y0 - y1 + 5:.1f}" rx="{wx + 2.5:.1f}" fill="{edge}" stroke="{light}" stroke-width="1"/>')
            o.append(f'<rect x="{-wx:.1f}" y="{y1:.1f}" width="{2 * wx:.1f}" height="{y0 - y1:.1f}" rx="{wx:.1f}" fill="#07080a"/>')
            lh = (y0 - y1) * lvl
            pulse = "" if reflect else '<animate attributeName="opacity" values="1;.8;1" dur="2.6s" repeatCount="indefinite"/>'
            o.append(f'<rect x="{-wx + 1.6:.1f}" y="{y0 - lh:.1f}" width="{2 * wx - 3.2:.1f}" height="{lh:.1f}" rx="{max(1.0, wx - 1.6):.1f}" fill="{col}">{pulse}</rect>')
            if not reflect:
                for q in (0.25, 0.5, 0.75):
                    yy = y0 - (y0 - y1) * q
                    o.append(f'<line x1="{wx + 2.5:.1f}" y1="{yy:.1f}" x2="{wx + 7:.1f}" y2="{yy:.1f}" stroke="{light}" stroke-width="1.2"/>')
                o.append(f'<rect x="{-wx + 3:.1f}" y="{y1 + 3:.1f}" width="2" height="{y0 - y1 - 6:.1f}" rx="1" fill="#fff" opacity=".22"/>')
        return "".join(o)

    def _vat_top(self, f, rx, ry, H, reflect):
        m, edge, light = self.mat, EDGE[self.mat], LIGHT[self.mat]
        o = [f'<ellipse cx="0" cy="{-H:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" fill="#060708"/>']
        # the far inner wall catches a little light
        o.append(f'<path d="M{-rx * .96:.1f},{-H:.1f} A{rx * .96:.1f},{ry * .96:.1f} 0 0 1 {rx * .96:.1f},{-H:.1f}" fill="none" stroke="{light}" stroke-width="2.2" opacity=".22"/>')
        if self.liquid:
            lm = {"bronze": ("#2b1608", "#7a4318", "#d98a3d"), "silver": ("#5e6978", "#aab6c6", "#f4f8fd")}[self.liquid]
            ly = -H + (1 - self.level) * H * 0.92
            cid, gid = nid("vc"), nid("vg")
            o.append(f'<clipPath id="{cid}"><ellipse cx="0" cy="{-H:.1f}" rx="{rx * 0.955:.1f}" ry="{ry * 0.955:.1f}"/></clipPath>')
            o.append(f'<radialGradient id="{gid}" cx=".42" cy=".4" r=".75"><stop offset="0" stop-color="{lm[2]}"/><stop offset=".45" stop-color="{lm[1]}"/><stop offset="1" stop-color="{lm[0]}"/></radialGradient>')
            wob = "" if reflect else f'<animate attributeName="cy" values="{ly:.1f};{ly + 1.3:.1f};{ly:.1f}" dur="4s" repeatCount="indefinite"/>'
            o.append(f'<g clip-path="url(#{cid})"><ellipse cx="0" cy="{ly:.1f}" rx="{rx * 0.955:.1f}" ry="{ry * 0.955:.1f}" fill="url(#{gid})">{wob}</ellipse>'
                     f'<ellipse cx="{-rx * 0.22:.1f}" cy="{ly - ry * 0.12:.1f}" rx="{rx * 0.34:.1f}" ry="{ry * 0.2:.1f}" fill="#fff" opacity=".28"/>'
                     f'<ellipse cx="0" cy="{ly:.1f}" rx="{rx * 0.955:.1f}" ry="{ry * 0.955:.1f}" fill="none" stroke="{lm[2]}" stroke-width="1.4" opacity=".5"/></g>')
        o.append(f'<ellipse cx="0" cy="{-H:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" fill="none" stroke="{light}" stroke-width="2.4"/>')
        o.append(f'<ellipse cx="0" cy="{-H:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" fill="none" stroke="{edge}" stroke-width="0.8"/>')
        return "".join(o)

    def svg(self, f):
        S = f.S
        rx, ry, H = self.r * S, self.r * S * SIN_PHI, self.h * COS_PHI * S
        fr = [f.pt(self.x, self.y, self.z0, k) for k in range(f.n)]
        o = [f'<g transform="translate({fr[0][0]:.1f},{fr[0][1]:.1f})" opacity="{self.alpha}">{a_translate(fr, f)}']
        o.append(f'<ellipse cx="{rx * .08:.1f}" cy="{ry * .12:.1f}" rx="{rx * 1.3:.1f}" ry="{ry * 1.3:.1f}" fill="url(#g_ao)"/>')
        if self.glow:
            gid = "g_warm" if self.glow == "warm" else "g_pool"
            gr = 6.0 if self.glow == "warm" else 3.0
            o.append(f'<ellipse cx="0" cy="{ry * .2:.1f}" rx="{rx * gr:.1f}" ry="{rx * gr * .5:.1f}" fill="url(#{gid})">'
                     f'<animate attributeName="opacity" values="1;.7;1" dur="3.4s" repeatCount="indefinite"/></ellipse>')
        if self.reflect:
            o.append(f'<g transform="scale(1,-1)" opacity=".38" mask="url(#m_refl)">{self.shell(f, reflect=True)}</g>')
        if self.back:
            o.append(self.back(rx, ry, H, f))
        o.append(self.shell(f))
        for az in self.seams:
            o.append(seam(f, self, az))
        if self.front:
            o.append(self.front(rx, ry, H, f))
        if self.over:
            o.append(self.over(rx, ry, H, f))
        o.append("</g>")
        return "".join(o)


def seam(f, unit, az):
    """A vertical weld line on the cylinder surface; slides across as the camera sways."""
    r, h, a = unit.r, unit.h, math.radians(az)

    def d(k):
        x0, y0 = f.loc(r * math.cos(a), r * math.sin(a), 0, k)
        x1, y1 = f.loc(r * math.cos(a), r * math.sin(a), h, k)
        return f"M{x0:.1f},{y0:.1f} L{x1:.1f},{y1:.1f}"

    return morph(f, "path", d, f'fill="none" stroke="{EDGE[unit.mat]}" stroke-width="1" stroke-opacity=".55"', "d",
                 lambda k: facing(az, f.th[k]) * 6)


def mix_dark(c):
    r, g, b = (int(c[i:i + 2], 16) for i in (1, 3, 5))
    return f"#{int(r * .62):02x}{int(g * .62):02x}{int(b * .66):02x}"


class Pipe:
    """A straight or bent run of pipe with flanges, supports, a sight glass and a painted flow arrow."""

    def __init__(self, pts, active=True, width=8.0, glass=(0.38, 0.66), flanges=(0.0, 0.5, 1.0), supports=(0.25, 0.75),
                 arrow=0.8, zfloor=0.5):
        self.pts, self.active, self.w, self.glass, self.flanges = pts, active, width, glass, flanges
        self.supports, self.arrow, self.zfloor = supports, arrow, zfloor
        self.depth = sum(depth(*p) for p in pts) / len(pts)
        self.lens = [math.dist(a, b) for a, b in zip(pts, pts[1:])]
        self.total = sum(self.lens)

    def at(self, t):
        d = t * self.total
        for (a, b), ln in zip(zip(self.pts, self.pts[1:]), self.lens):
            if d <= ln + 1e-9:
                u = d / ln if ln else 0
                return tuple(a[i] + (b[i] - a[i]) * u for i in range(3))
            d -= ln
        return self.pts[-1]

    def sub(self, t0, t1):
        """World points of the sub-run between fractions t0..t1, including interior corners."""
        out, acc = [self.at(t0)], 0.0
        for ln, p in zip(self.lens, self.pts[1:]):
            acc += ln
            if t0 * self.total < acc < t1 * self.total:
                out.append(p)
        out.append(self.at(t1))
        return out

    def bbox_pts(self, th):
        return [proj(x, y, z, th) for x, y, z in self.pts]

    def _dir(self, t, eps=0.015):
        return self.at(max(0.0, t - eps)), self.at(min(1.0, t + eps))

    def _frame(self, f, t, k):
        a, b = self._dir(t)
        (ax, ay), (bx, by) = f.pt(*a, k), f.pt(*b, k)
        px, py = f.pt(*self.at(t), k)
        dx, dy = bx - ax, by - ay
        n = math.hypot(dx, dy) or 1
        return px, py, dx / n, dy / n

    def _bar(self, f, t, half):
        def pts(k):
            px, py, dx, dy = self._frame(f, t, k)
            nx, ny = -dy, dx
            return [(px - nx * half, py - ny * half), (px + nx * half, py + ny * half)]
        return pts

    def _arrow(self, f, t):
        def pts(k):
            px, py, dx, dy = self._frame(f, t, k)
            nx, ny = -dy, dx
            L, W = 7.5, 4.2
            return [(px + dx * L, py + dy * L), (px - dx * L * .6 + nx * W, py - dy * L * .6 + ny * W), (px - dx * L * .6 - nx * W, py - dy * L * .6 - ny * W)]
        return pts

    def svg(self, f):
        w, o = self.w, []
        steel = ("#1c1f25", "#39404c", "#8a96a8", "#e1e9f4")
        run = lambda pts: (lambda k: [f.pt(x, y, z, k) for x, y, z in pts])
        main_id = nid("pp")
        sh = [(x + SHADOW[0] * (z - self.zfloor), y + SHADOW[1] * (z - self.zfloor), self.zfloor) for x, y, z in self.pts]
        o.append(line_morph(f, run(sh), f'fill="none" stroke="#000" stroke-opacity=".32" stroke-width="{w + 2}" stroke-linejoin="round" stroke-linecap="round"'))
        for t in self.supports:   # posts to the floor
            x, y, z = self.at(t)
            if z - self.zfloor < 0.15:
                continue
            o.append(poly_layers(f, run([(x, y, z - 0.05), (x, y, self.zfloor)]), ['stroke="#0b0c0f" stroke-width="5" stroke-linecap="round"', 'stroke="#3b4350" stroke-width="2.6" stroke-linecap="round"']))
            o.append(poly_layers(f, run([(x - .12, y - .12, self.zfloor), (x + .12, y + .12, self.zfloor)]), ['stroke="#14161a" stroke-width="4" stroke-linecap="round"']))
        o.append(f'<defs>{line_morph(f, run(self.pts), "", None, main_id)}</defs>')
        layers = [(w + 3.6, "#07080a", 0, 0, 1), (w, steel[0], 0, 0, 1), (w * .72, steel[1], -w * .08, -w * .14, 1),
                  (w * .34, steel[2], -w * .17, -w * .27, .9), (w * .12, steel[3], -w * .2, -w * .33, .6)]
        for lw, col, dx, dy, op in layers:
            col = col if self.active or lw > w + 1 else mix_dark(col)
            o.append(f'<use href="#{main_id}" fill="none" stroke="{col}" stroke-width="{lw:.1f}" stroke-opacity="{op}" '
                     f'stroke-linejoin="round" transform="translate({dx:.1f},{dy:.1f})"/>')
        for t in (0.12, 0.88):   # joint bands
            o.append(line_morph(f, self._bar(f, t, w * .62), 'fill="none" stroke="#07080a" stroke-width="2.2" stroke-opacity=".7"'))
        g0, g1 = self.glass
        if g1 > g0:   # sight glass with the flow inside
            gid = nid("sg")
            o.append(f'<defs>{line_morph(f, run(self.sub(g0, g1)), "", None, gid)}</defs>')
            o.append(f'<use href="#{gid}" fill="none" stroke="#07080a" stroke-width="{w + 2.5:.1f}" stroke-linecap="butt"/>')
            o.append(f'<use href="#{gid}" fill="none" stroke="#9fb4cf" stroke-opacity=".28" stroke-width="{w * .92:.1f}" stroke-linecap="butt"/>')
            if self.active:
                o.append(f'<use href="#{gid}" fill="none" stroke="{P["mustard"]}" stroke-opacity=".85" stroke-width="{w * .52:.1f}"/>')
                dash = '<animate attributeName="stroke-dashoffset" values="0;-11.1" dur="0.8s" repeatCount="indefinite"/>' if f.animate else ""
                o.append(f'<use href="#{gid}" fill="none" stroke="#fff4c4" stroke-width="{w * .34:.1f}" stroke-linecap="round" stroke-dasharray="0.1 11">{dash}</use>')
            o.append(f'<use href="#{gid}" fill="none" stroke="#fff" stroke-opacity=".35" stroke-width="1.2" transform="translate({-w * .2:.1f},{-w * .3:.1f})"/>')
        for t in self.flanges:
            o.append(poly_layers(f, self._bar(f, t, w * .73), ['stroke="#07080a" stroke-width="7" stroke-linecap="round"', 'stroke="#6f7b8d" stroke-width="4.4" stroke-linecap="round"',
                                                               'stroke="#cdd8e6" stroke-width="1.4" stroke-linecap="round" stroke-opacity=".75"']))
        if self.arrow:   # painted flow arrow
            o.append(poly_morph(f, self._arrow(f, self.arrow), f'fill="{P["mustard"]}" stroke="#07080a" stroke-width=".6" fill-opacity="{0.95 if self.active else 0.35}"'))
        return "".join(o)


class Valve:
    """A gate valve above a pipe: body, bonnet, stem and a hand wheel (mustard = open, red = closed)."""

    def __init__(self, x, y, z, is_open=True, h=0.6):
        self.x, self.y, self.z, self.open, self.h = x, y, z, is_open, h
        self.depth = depth(x, y, z) + 0.002

    def bbox_pts(self, th):
        px, py = proj(self.x, self.y, self.z, th)
        return [(px - .3, py - .9), (px + .3, py + .2)]

    def svg(self, f):
        S = f.S
        fr = [f.pt(self.x, self.y, self.z, k) for k in range(f.n)]
        wheel = P["mustard"] if self.open else P["fail"]
        wr, hh = 0.26 * S, self.h * COS_PHI * S
        bw = 0.17 * S
        o = [f'<g transform="translate({fr[0][0]:.1f},{fr[0][1]:.1f})">{a_translate(fr, f)}']
        o.append(f'<ellipse cx="3" cy="3" rx="{.2 * S:.1f}" ry="{.1 * S:.1f}" fill="#000" opacity=".4"/>')
        o.append(f'<path d="M{-bw:.1f},{-hh * .42:.1f} L{-bw:.1f},{bw * .35:.1f} A{bw:.1f},{bw * .5:.1f} 0 0 0 {bw:.1f},{bw * .35:.1f} L{bw:.1f},{-hh * .42:.1f} Z" fill="url(#g_graphite)" stroke="#050608" stroke-width=".8"/>')
        o.append(f'<ellipse cx="0" cy="{-hh * .42:.1f}" rx="{bw:.1f}" ry="{bw * .5:.1f}" fill="#262b33" stroke="#7d8898" stroke-width=".8"/>')
        o.append(f'<rect x="{-bw * .55:.1f}" y="{-hh * .78:.1f}" width="{bw * 1.1:.1f}" height="{hh * .36:.1f}" fill="url(#g_graphite)" stroke="#050608" stroke-width=".7"/>')
        o.append(f'<rect x="-1.1" y="{-hh:.1f}" width="2.2" height="{hh * .24:.1f}" fill="#9aa6b6"/>')
        o.append(f'<ellipse cx="0" cy="{-hh:.1f}" rx="{wr:.1f}" ry="{wr * .5:.1f}" fill="none" stroke="#050608" stroke-width="3.6"/>')
        o.append(f'<ellipse cx="0" cy="{-hh:.1f}" rx="{wr:.1f}" ry="{wr * .5:.1f}" fill="none" stroke="{wheel}" stroke-width="2.2"/>')
        o.append(f'<path d="M{-wr:.1f},{-hh:.1f} L{wr:.1f},{-hh:.1f} M0,{-hh - wr * .5:.1f} L0,{-hh + wr * .5:.1f}" stroke="{wheel}" stroke-width="1.2"/>')
        o.append("</g>")
        return "".join(o)


class Shadow:
    """The real cast shadow of a cylinder: a stadium on the floor that follows the camera."""

    def __init__(self, unit, zfloor, zbottom=None):
        self.u, self.zf = unit, zfloor
        self.zb = zfloor if zbottom is None else zbottom
        self.depth = -5e8 + unit.depth * 1e-3

    def bbox_pts(self, th):
        return []

    def svg(self, f):
        u = self.u
        zt = u.top_z()
        bx, by = SHADOW[0] * (self.zb - self.zf), SHADOW[1] * (self.zb - self.zf)
        tx, ty = SHADOW[0] * (zt - self.zf), SHADOW[1] * (zt - self.zf)
        phi = math.atan2(ty - by, tx - bx)
        n = 6

        def poly(grow):
            r = u.r * grow
            pts = [(u.x + tx + r * math.cos(phi - math.pi / 2 + math.pi * i / n), u.y + ty + r * math.sin(phi - math.pi / 2 + math.pi * i / n)) for i in range(n + 1)]
            pts += [(u.x + bx + r * math.cos(phi + math.pi / 2 + math.pi * i / n), u.y + by + r * math.sin(phi + math.pi / 2 + math.pi * i / n)) for i in range(n + 1)]
            return lambda k: [f.pt(x, y, self.zf, k) for x, y in pts]

        return (poly_morph(f, poly(1.34), 'fill="#000" fill-opacity=".13"', prec=0)
                + poly_morph(f, poly(1.0), 'fill="#000" fill-opacity=".30"', prec=0))


class Slab:
    """A thick concrete pad: textured top, painted safety lines, a yellow steel curb and expansion joints."""

    def __init__(self, poly, edges, zt, grid, lines):
        self.poly, self.edges, self.zt, self.grid, self.lines = poly, edges, zt, grid, lines
        self.depth = -1e9

    def bbox_pts(self, th):
        return [proj(x, y, z, th) for x, y in self.poly for z in (0, self.zt)]

    def svg(self, f):
        zt, o = self.zt, []
        for (x0, y0), (x1, y1) in self.edges:
            q = lambda z0, z1, x0=x0, y0=y0, x1=x1, y1=y1: [(x0, y0, z0), (x1, y1, z0), (x1, y1, z1), (x0, y0, z1)]
            side = lambda k, q=q: [f.pt(*c, k) for c in q(0, zt)]
            curb = lambda k, q=q: [f.pt(*c, k) for c in q(zt - 0.16, zt)]
            o.append(poly_morph(f, side, 'fill="url(#g_conc_side)" stroke="#050608" stroke-width="1"', prec=0))
            o.append(poly_morph(f, side, 'fill="url(#p_conc)" fill-opacity=".45"', prec=0))
            o.append(poly_morph(f, curb, 'fill="#c79a00" stroke="#120d00" stroke-width=".8"', prec=0))
            o.append(poly_morph(f, curb, 'fill="url(#p_conc)" fill-opacity=".55"', prec=0))
        top = lambda k: [f.pt(x, y, zt, k) for x, y in self.poly]
        o.append(poly_morph(f, top, 'fill="#14161b" stroke="#2a2e36" stroke-width="1"', prec=0))
        o.append(poly_morph(f, top, 'fill="url(#p_conc)" fill-opacity=".5"', prec=0))
        for (x0, y0), (x1, y1) in self.grid:
            a = lambda k, x0=x0, y0=y0, x1=x1, y1=y1: [f.pt(x0, y0, zt, k), f.pt(x1, y1, zt, k)]
            o.append(poly_layers(f, a, ['stroke="#050608" stroke-width="1.1" stroke-opacity=".55"', 'stroke="#4a505c" stroke-width=".7" stroke-opacity=".28" transform="translate(1,1)"']))
        for pts in self.lines:   # worn safety paint
            ln = lambda k, p=pts: [f.pt(x, y, zt, k) for x, y in p]
            o.append(line_morph(f, ln, f'fill="none" stroke="{P["mustard"]}" stroke-width="3.2" stroke-opacity=".78" stroke-dasharray="46 3 14 4 30 2"'))
            o.append(line_morph(f, ln, 'fill="none" stroke="url(#p_conc)" stroke-width="3.2" stroke-opacity=".7" stroke-dasharray="46 3 14 4 30 2"'))
        return "".join(o)


class Floor:
    """Things lying flat on the floor (manhole covers): a horizontal circle is yaw-invariant, so it only translates."""

    def __init__(self, x, y, z, r, dep=-4e8, kind="manhole"):
        self.x, self.y, self.z, self.r, self.depth, self.kind = x, y, z, r, dep, kind

    def bbox_pts(self, th):
        return []

    def svg(self, f):
        fr = [f.pt(self.x, self.y, self.z, k) for k in range(f.n)]
        rx = self.r * f.S
        ry = rx * SIN_PHI
        o = [f'<g transform="translate({fr[0][0]:.1f},{fr[0][1]:.1f})">{a_translate(fr, f)}']
        if self.kind == "light":
            o.append(f'<ellipse cx="0" cy="0" rx="{rx:.1f}" ry="{ry:.1f}" fill="url(#g_lightpool)"/>')
            o.append("</g>")
            return "".join(o)
        if self.kind == "stain":
            o.append(f'<ellipse cx="0" cy="0" rx="{rx:.1f}" ry="{ry:.1f}" fill="url(#g_ao)" opacity=".85"/>')
            o.append(f'<ellipse cx="{rx * .15:.1f}" cy="{ry * .1:.1f}" rx="{rx * .55:.1f}" ry="{ry * .55:.1f}" fill="#000" opacity=".28"/>')
            o.append("</g>")
            return "".join(o)
        o.append(f'<ellipse cx="0" cy="1.5" rx="{rx:.1f}" ry="{ry:.1f}" fill="#07080a"/>')
        o.append(f'<ellipse cx="0" cy="0" rx="{rx:.1f}" ry="{ry:.1f}" fill="#1d2026" stroke="#3d4450" stroke-width="1.2"/>')
        o.append(f'<ellipse cx="0" cy="0" rx="{rx * .78:.1f}" ry="{ry * .78:.1f}" fill="none" stroke="#0a0b0e" stroke-width="1.4"/>')
        o.append(f'<ellipse cx="0" cy="0" rx="{rx * .5:.1f}" ry="{ry * .5:.1f}" fill="none" stroke="#2c323c" stroke-width="1"/>')
        o.append(f'<ellipse cx="0" cy="0" rx="{rx:.1f}" ry="{ry:.1f}" fill="url(#p_conc)" opacity=".5"/>')
        o.append("</g>")
        return "".join(o)


class Tag:
    """A small information plaque that follows a point in the scene."""

    def __init__(self, x, y, z, lines, leader=16, dx=0.0):
        self.x, self.y, self.z, self.lines, self.leader, self.dx = x, y, z, lines, leader, dx
        self.depth = 1e9

    def bbox_pts(self, th):
        px, py = proj(self.x, self.y, self.z, th)
        return [(px, py - 1.5), (px, py)]

    def size(self):
        w = max((len(ln[0]) + (2 if len(ln) > 4 else 0)) * ln[2] * 0.62 for ln in self.lines) + 14
        h = sum(ln[2] + 4 for ln in self.lines) + 8
        return w, h

    def box(self, f, k):
        x, y = f.pt(self.x, self.y, self.z, k)
        w, h = self.size()
        x += self.dx
        return (x - w / 2, y - self.leader - h, x + w / 2, y - self.leader)

    def svg(self, f):
        fr = [f.pt(self.x, self.y, self.z, k) for k in range(f.n)]
        w, h = self.size()
        o = [f'<g transform="translate({fr[0][0]:.1f},{fr[0][1]:.1f})">{a_translate(fr, f)}']
        o.append(f'<line x1="0" y1="-2" x2="0" y2="{-self.leader}" stroke="{P["mustard"]}" stroke-width="1" opacity=".75"/>')
        o.append(f'<circle cx="0" cy="-2" r="2.2" fill="{P["mustard"]}" stroke="#07080a" stroke-width=".8"/>')
        tx = self.dx
        o.append(f'<rect x="{tx - w / 2:.1f}" y="{-self.leader - h:.1f}" width="{w:.1f}" height="{h:.1f}" rx="5" fill="#0a0b0e" fill-opacity=".8" stroke="{P["mustard"]}" stroke-opacity=".45"/>')
        n = len(self.lines)
        for i, ln in enumerate(self.lines):
            text, fill, size, weight = ln[:4]
            badge = ln[4] if len(ln) > 4 else None
            y = -self.leader - 5 - (n - 1 - i) * (size + 4)
            if badge:
                g, gc = badge
                o.append(f'<text x="{tx:.1f}" y="{y:.1f}" fill="{fill}" font-size="{size}" text-anchor="middle" font-weight="{weight}" '
                         f'font-family="{FONT}"><tspan fill="{gc}">{escape(g)}</tspan> {escape(text)}</text>')
            else:
                o.append(txt(tx, y, text, fill, size, "middle", weight))
        o.append("</g>")
        return "".join(o)


class Scene:
    def __init__(self, ths, dur="32s", animate=True):
        self.ths, self.dur, self.animate = ths, dur, animate
        self.items = []

    def add(self, obj):
        self.items.append(obj)
        return obj

    def fit(self, W, H, left, top, right, bottom):
        pts = [p for it in self.items for th in self.ths for p in it.bbox_pts(th)]
        minx, maxx = min(p[0] for p in pts), max(p[0] for p in pts)
        miny, maxy = min(p[1] for p in pts), max(p[1] for p in pts)
        S = min((W - left - right) / (maxx - minx), (H - top - bottom) / (maxy - miny))
        ox = left + ((W - left - right) - S * (maxx - minx)) / 2 - minx * S
        oy = top + ((H - top - bottom) - S * (maxy - miny)) / 2 - miny * S
        return Fit(self.ths, S, ox, oy, self.dur, self.animate)

    def check_order(self, f):
        """Pairs of cylinders whose painter's order flips somewhere in the sway AND that overlap on screen."""
        bad = []
        objs = [i for i in self.items if isinstance(i, Cyl)]
        for a in range(len(objs)):
            for b in range(a + 1, len(objs)):
                A, B = objs[a], objs[b]
                base = A.depth < B.depth
                for th in self.ths:
                    da = A.x * math.sin(th) + A.y * math.cos(th)
                    db = B.x * math.sin(th) + B.y * math.cos(th)
                    if (da < db) != base:
                        ra, rb = A.bbox_pts(th), B.bbox_pts(th)
                        if not (max(p[0] for p in ra) < min(p[0] for p in rb) or max(p[0] for p in rb) < min(p[0] for p in ra)):
                            bad.append((A.uid, B.uid))
                            break
        return bad

    def check_tags(self, f):
        tags = [i for i in self.items if isinstance(i, Tag)]
        hits = set()
        for k in range(f.n):
            boxes = [t.box(f, k) for t in tags]
            for a in range(len(tags)):
                for b in range(a + 1, len(tags)):
                    A, B = boxes[a], boxes[b]
                    if A[0] < B[2] and B[0] < A[2] and A[1] < B[3] and B[1] < A[3]:
                        hits.add((tags[a].lines[0][0], tags[b].lines[0][0]))
        return sorted(hits)

    def body(self, f, tags=False):
        order = sorted((i for i in self.items if not isinstance(i, Tag)), key=lambda i: i.depth)
        return "".join(i.svg(f) for i in order)

    def tags_svg(self, f):
        return "".join(i.svg(f) for i in self.items if isinstance(i, Tag))
