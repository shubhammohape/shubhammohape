"""Every piece of page text, designed: panels, cards and buttons in the profile's own type and colour.

README text can't be styled, so the words live in SVG panels. They are written here as ordinary
<text> elements and turned into outlines by typeset.outline() (one typeface everywhere). Content comes
from data/profile.json (editable, public-safe) and data/work.json (aggregates only, see
tools/snapshot_work.py).
"""
import json
import math
import re
from datetime import date
from html import escape

from iso import TEX
from theme import FONT, P
from typeset import measure

HZ = f'<pattern id="pz" width="16" height="16" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="8" height="16" fill="{P["mustard"]}"/><rect x="8" width="8" height="16" fill="#101216"/></pattern>'
MONTH = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


# ---------------------------------------------------------------- building blocks
def T(x, y, s, size, fill, anchor="start", bold=False, stencil=False, spacing=0, extra=""):
    """One text element; typeset.outline() turns it into outlines."""
    return (f'<text x="{x:.1f}" y="{y:.1f}" fill="{fill}" font-size="{size}" text-anchor="{anchor}" font-family="{FONT}"'
            f'{" font-weight=" + chr(34) + "700" + chr(34) if bold else ""}{" data-font=" + chr(34) + "stencil" + chr(34) if stencil else ""}'
            f'{f" letter-spacing={chr(34)}{spacing}{chr(34)}" if spacing else ""} {extra}>{escape(str(s))}</text>')


def rich_line(x, y, tokens, size, fill, hi=None):
    """A line of (word, bold, glued) tokens: bold words are set heavy and bright; glued ones follow without a space."""
    hi = hi or P["mustard_hi"]
    html = ""
    for i, (w, b, glued) in enumerate(tokens):
        html += "" if (i == 0 or glued) else " "
        html += f'<tspan fill="{hi}" font-weight="700">{escape(w)}</tspan>' if b else escape(w)
    return f'<text x="{x}" y="{y}" fill="{fill}" font-size="{size}" font-family="{FONT}">{html}</text>'


def parse_rich(text):
    """'a **bold**, word' -> [('a', False, False), ('bold', True, False), (',', False, True), ('word', False, False)]
    The third field says the word follows the previous one with no space between them in the source."""
    out, bold, prev_space = [], False, True
    for chunk in re.split(r"(\*\*)", text):
        if chunk == "**":
            bold = not bold
        elif chunk:
            first = True
            for w in chunk.split():
                out.append((w, bold, first and not chunk[0].isspace() and not prev_space and bool(out)))
                first = False
            prev_space = chunk[-1].isspace()
    return out


def wrap(tokens, width, size):
    lines, cur, cur_w = [], [], 0.0
    space = measure(" ", size)
    for w, b, g in tokens:
        ww = measure(w, size, "monob" if b else "mono")
        if cur and cur_w + (0 if g else space) + ww > width:
            lines.append(cur)
            cur, cur_w, g = [], 0.0, False
        cur_w += (0 if g or not cur else space) + ww
        cur.append((w, b, g))
    if cur:
        lines.append(cur)
    return lines


def shell(W, H, title, caption, hazard=True, texture=False, extra_defs=""):
    """The common panel: dark plate, border, optional hazard strip, stencil title and a muted caption."""
    tex = f'<pattern id="pb" width="64" height="96" patternUnits="userSpaceOnUse"><image href="{TEX["brush"]}" width="64" height="96"/></pattern>' if texture else ""
    o = [f'<defs>{HZ}{tex}<linearGradient id="pp" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#1b1e25"/><stop offset=".5" stop-color="#121418"/><stop offset="1" stop-color="#0b0c0f"/></linearGradient>'
         f'<radialGradient id="ps" cx=".15" cy="0" r=".9"><stop offset="0" stop-color="{P["mustard"]}" stop-opacity=".10"/><stop offset="1" stop-color="{P["mustard"]}" stop-opacity="0"/></radialGradient>'
         f'<clipPath id="pc"><rect width="{W}" height="{H}" rx="14"/></clipPath>{extra_defs}</defs>',
         f'<rect width="{W}" height="{H}" rx="14" fill="url(#pp)"/>',
         f'<rect width="{W}" height="{H}" rx="14" fill="url(#ps)"/>']
    if texture:
        o.append(f'<rect width="{W}" height="{H}" rx="14" fill="url(#pb)" opacity=".10"/>')
    if hazard:
        o.append(f'<g clip-path="url(#pc)"><rect width="{W}" height="6" fill="url(#pz)"/></g>')
    o.append(f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="14" fill="none" stroke="{P["border"]}"/>')
    if title:
        o.append(T(40, 62, title, 32, P["mustard"], stencil=True, spacing=4))
    if caption:
        o.append(T(W - 40, 56, caption, 11.5, P["muted"], anchor="end"))
    if title:
        o.append(f'<line x1="40" y1="76" x2="{W - 40}" y2="76" stroke="{P["border"]}"/><rect x="40" y="75" width="64" height="2.5" fill="{P["mustard"]}"/>')
    return o


def svg_doc(W, H, label, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
            f'aria-label="{escape(label, quote=True)}">' + "".join(body) + "</svg>")


# -------------------------------------------------------------------------- ABOUT
def about_svg(cfg):
    W, size, lh = 900, 22, 34
    paras = cfg["about"]
    lines = []
    for p in paras:
        lines.append(wrap(parse_rich(p), W - 80, size))
    H = 112 + sum(len(l) for l in lines) * lh + (len(paras) - 1) * 14 + 34
    o = shell(W, H, "ABOUT", f'{cfg["name"].upper()} · {cfg["tagline"].upper()}'.replace("·", "·"), hazard=True)
    y = 124
    for block in lines:
        for ln in block:
            o.append(rich_line(40, y, ln, size, P["text"]))
            y += lh
        y += 14
    label = "About " + cfg["name"] + ". " + " ".join(re.sub(r"\*\*", "", p) for p in paras)
    return svg_doc(W, H, label, o)


# ------------------------------------------------------------------ HOW I WORK
def _odometer(x, y, value, digits, delay, W_=30, H_=46):
    """A mechanical odometer: each wheel rolls from 0 to its digit when the cycle starts."""
    s = str(value).zfill(digits)
    o = [f'<rect x="{x - 4}" y="{y - 4}" width="{digits * (W_ + 2) + 6}" height="{H_ + 8}" rx="6" fill="#050506" stroke="#2f343d"/>']
    for i, ch in enumerate(s):
        d = int(ch)
        cx = x + i * (W_ + 2)
        cid = f"od{x}{y}{i}"
        strip = "".join(T(cx + W_ / 2, y + H_ - 9 + k * H_, str(k % 10), 34, P["mustard_hi"] if k >= 10 else P["mustard_hi"], anchor="middle", bold=True) for k in range(20))
        target = (10 + d) * H_
        roll = (f'<animateTransform attributeName="transform" type="translate" dur="14s" repeatCount="indefinite" calcMode="spline" '
                f'keyTimes="0;{(1.2 + delay) / 14:.3f};1" keySplines=".15 0 .1 1;0 0 1 1" values="0 0;0 -{target};0 -{target}"/>')
        o.append(f'<clipPath id="{cid}"><rect x="{cx}" y="{y}" width="{W_}" height="{H_}" rx="3"/></clipPath>'
                 f'<rect x="{cx}" y="{y}" width="{W_}" height="{H_}" rx="3" fill="#0d0e11"/>'
                 f'<g clip-path="url(#{cid})"><g transform="translate(0,-{target})">{roll}{strip}</g>'
                 f'<rect x="{cx}" y="{y}" width="{W_}" height="{H_ / 2}" fill="url(#odg)"/></g>'
                 f'<rect x="{cx}" y="{y}" width="{W_}" height="{H_}" rx="3" fill="none" stroke="#000" stroke-opacity=".6"/>')
    return "".join(o)


def desk_svg(w, ts_label):
    W, H = 900, 388
    o = shell(W, H, "HOW I WORK", f"pull requests · last 12 months · synced {ts_label}", hazard=True, texture=True,
              extra_defs='<linearGradient id="odg" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#000" stop-opacity=".65"/><stop offset="1" stop-color="#000" stop-opacity="0"/></linearGradient>'
                         f'<linearGradient id="bm" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="{P["mustard_hi"]}"/><stop offset="1" stop-color="{P["mustard_lo"]}"/></linearGradient>'
                         '<linearGradient id="bs" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#e6edf5"/><stop offset="1" stop-color="#59627a"/></linearGradient>'
                         '<linearGradient id="cr" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#2b313b"/><stop offset="1" stop-color="#14161b"/></linearGradient>')
    # -- left: odometers
    for i, (label, sub, val, delay) in enumerate((("RAISED", "pull requests I opened", w["raised"], 0.0), ("REVIEWED", "pull requests I reviewed", w["reviewed"], 0.35))):
        y = 108 + i * 78
        o.append(T(40, y + 20, label, 20, P["muted"], stencil=True, spacing=3))
        o.append(T(40, y + 40, sub, 11, P["muted"]))
        o.append(_odometer(214, y, val, 3 if val < 1000 else 4, delay))
    # -- middle: the review line (conveyor + stamp press)
    x0, x1, by = 340, 660, 214
    L, D = x1 - x0, 7.7
    N = 7
    dt = D / N
    xp = (x0 + x1) / 2
    f = (xp - x0) / L
    o.append(f'<rect x="{x0 - 14}" y="{by}" width="{L + 28}" height="16" rx="8" fill="#0c0d10" stroke="#2f343d"/>')
    o.append(f'<rect x="{x0 - 14}" y="{by}" width="{L + 28}" height="16" rx="8" fill="url(#pb)" opacity=".5"/>')
    o.append(f'<line x1="{x0}" y1="{by + 8}" x2="{x1}" y2="{by + 8}" stroke="{P["mustard"]}" stroke-opacity=".6" stroke-width="2" stroke-dasharray="3 13">'
             f'<animate attributeName="stroke-dashoffset" values="0;-16" dur="0.55s" repeatCount="indefinite"/></line>')
    for rx_ in (x0 - 14, x1 + 14):
        o.append(f'<circle cx="{rx_}" cy="{by + 8}" r="11" fill="#1b1f26" stroke="#59627a"/><circle cx="{rx_}" cy="{by + 8}" r="3" fill="#8b8f98"/>')
    # press frame + piston (moves down on every crate that reaches the middle)
    press_phase = (f * D - 0.5 * dt) % dt
    o.append(f'<rect x="{xp - 48}" y="116" width="8" height="{by - 116}" fill="url(#cr)" stroke="#050608"/><rect x="{xp + 40}" y="116" width="8" height="{by - 116}" fill="url(#cr)" stroke="#050608"/>'
             f'<rect x="{xp - 52}" y="112" width="104" height="14" rx="3" fill="#2a2f39" stroke="#050608"/>')
    o.append(f'<g><animateTransform attributeName="transform" type="translate" dur="{dt:.3f}s" begin="{press_phase:.3f}s" repeatCount="indefinite" calcMode="spline" '
             f'keyTimes="0;.40;.50;.60;1" keySplines="0 0 1 1;.5 0 1 .6;0 .4 .5 1;0 0 1 1" values="0 0;0 0;0 52;0 0;0 0"/>'
             f'<rect x="{xp - 3}" y="126" width="6" height="34" fill="#8b95a6"/><rect x="{xp - 22}" y="158" width="44" height="14" rx="2" fill="{P["mustard"]}" stroke="#050608"/>'
             f'<rect x="{xp - 22}" y="158" width="44" height="4" fill="#fff" opacity=".3"/></g>')
    # crates: 6 merge, 1 closes (87% merged, as in real life)
    for j in range(N):
        merged = j != 4
        stamp = (f'<g opacity="0"><animate attributeName="opacity" dur="{D}s" begin="{-j * dt:.3f}s" repeatCount="indefinite" keyTimes="0;{f + 0.012:.3f};{f + 0.04:.3f};1" values="0;0;1;1"/>'
                 + (f'<rect x="-14" y="-12" width="28" height="10" rx="2" fill="{P["mustard_hi"]}"/>' + T(0, -4.5, "MERGED", 7.6, "#14100a", anchor="middle", bold=True)
                    if merged else f'<rect x="-14" y="-12" width="28" height="10" rx="2" fill="#3a3f4a"/>' + T(0, -4.5, "CLOSED", 7.6, "#ece8dc", anchor="middle", bold=True)) + '</g>')
        o.append(f'<g><animateMotion dur="{D}s" begin="{-j * dt:.3f}s" repeatCount="indefinite" path="M{x0},{by} L{x1},{by}"/>'
                 f'<rect x="-17" y="-28" width="34" height="28" rx="3" fill="url(#cr)" stroke="#59627a"/><rect x="-17" y="-28" width="34" height="4" rx="2" fill="#fff" opacity=".12"/>'
                 + T(0, -9, "PR", 11, P["muted"], anchor="middle", stencil=True, spacing=1) + stamp + '</g>')
    o.append(T(xp, 258, f'{w["merged_pct"]}% of mine get merged', 12, P["muted"], anchor="middle"))
    o.append(T(x0 - 14, 104, "THE REVIEW LINE", 13, P["mustard"], stencil=True, spacing=3))
    # -- right: monthly bars
    mx0, base, hmax = 690, 226, 96
    top = max(max(m["raised"], m["reviewed"]) for m in w["monthly"]) or 1
    months = w["monthly"][-13:]
    o.append(T(mx0, 104, "BY MONTH", 13, P["mustard"], stencil=True, spacing=3))
    for i, m in enumerate(months):
        bx = mx0 + i * 14
        for k, (key, grad) in enumerate((("raised", "bm"), ("reviewed", "bs"))):
            h = max(2, hmax * m[key] / top)
            o.append(f'<g transform="translate({bx + k * 6},{base})"><g><animateTransform attributeName="transform" type="scale" dur="14s" repeatCount="indefinite" '
                     f'calcMode="spline" keyTimes="0;.14;1" keySplines=".2 0 .1 1;0 0 1 1" values="1 0;1 1;1 1"/>'
                     f'<rect x="0" y="-{h:.1f}" width="5" height="{h:.1f}" rx="1.5" fill="url(#{grad})"/></g></g>')
        o.append(T(bx + 5.5, base + 13, MONTH[int(m["m"][5:7]) - 1][0], 8.5, P["muted"], anchor="middle"))
    o.append(f'<rect x="{mx0}" y="{base + 22}" width="8" height="8" rx="2" fill="{P["mustard"]}"/>' + T(mx0 + 13, base + 30, "raised", 10, P["muted"])
             + f'<rect x="{mx0 + 66}" y="{base + 22}" width="8" height="8" rx="2" fill="#a9b4c2"/>' + T(mx0 + 79, base + 30, "reviewed", 10, P["muted"]))
    # -- bottom: four stat plates
    ttm = w["median_hours_to_merge"]
    stats = [(f'{w["merged_pct"]}%', "OF MY PRS MERGED"),
             (f'{ttm:.0f}H' if ttm < 48 else f'{ttm / 24:.0f}D', "MEDIAN TIME TO MERGE"),
             (f'+{w["median_additions"]} −{w["median_deletions"]}', f'TYPICAL PR · {w["median_files"]} FILES'),
             (f'{w["reviews_per_pr"]}×', "REVIEWS PER PR I RAISE")]
    pw = (W - 80 - 3 * 14) / 4
    for i, (big, small) in enumerate(stats):
        px = 40 + i * (pw + 14)
        o.append(f'<rect x="{px:.1f}" y="288" width="{pw:.1f}" height="60" rx="8" fill="#0a0b0e" stroke="#2f343d"/><rect x="{px:.1f}" y="288" width="4" height="60" rx="2" fill="{P["mustard"]}"/>')
        o.append(T(px + 18, 322, big, 30, P["mustard_hi"], stencil=True))
        o.append(T(px + 18, 340, small, 9.5, P["muted"], spacing=.5))
    o.append(T(W - 40, 374, "synced from my work repositories · private details omitted", 9.5, P["muted"], anchor="end"))
    label = (f'How I work: in the last 12 months I raised {w["raised"]} pull requests and reviewed {w["reviewed"]}; {w["merged_pct"]}% of mine merge, '
             f'median time to merge {ttm:.0f} hours, a typical PR is +{w["median_additions"]} −{w["median_deletions"]} lines across {w["median_files"]} files, '
             f'and I review about {w["reviews_per_pr"]} PRs for every one I raise.')
    return svg_doc(W, H, label, o)


# ------------------------------------------------------- headings, cards, buttons
def head_svg(title, caption, W=900, H=96):
    """A slim section heading plate."""
    o = shell(W, H, title, caption, hazard=False)
    return svg_doc(W, H, f"{title.title()}. {caption}", o)


TIER = {"gold": P["gold"], "silver": P["silver"], "bronze": P["bronze"]}


def project_svg(p, repo_info, owner):
    """One clickable project card: tier bar, name, language chip, one honest sentence."""
    W, H = 900, 108
    name, note = p["repo"], p["note"]
    lang = (repo_info or {}).get("language") or "n/a"
    tier = (repo_info or {}).get("tier", "gold")
    col = TIER.get(tier, P["gold"])
    o = [f'<defs><linearGradient id="pk" x1="0" x2="1" y1="0" y2="0"><stop offset="0" stop-color="#1a1d23"/><stop offset="1" stop-color="#0f1013"/></linearGradient></defs>',
         f'<rect width="{W}" height="{H}" rx="12" fill="url(#pk)" stroke="{P["border"]}"/>',
         f'<rect x="0" y="0" width="8" height="{H}" rx="4" fill="{col}"/>',
         T(40, 50, name, 28, P["text"], bold=True),
         T(40, 86, note, 19, "#b9b6ab")]
    cw = measure(lang, 13) + 26
    o.append(f'<rect x="{W - 86 - cw:.1f}" y="26" width="{cw:.1f}" height="28" rx="14" fill="none" stroke="{col}" stroke-opacity=".7"/>')
    o.append(T(W - 86 - cw / 2, 45, lang, 13, col, anchor="middle"))
    o.append(T(W - 40, 64, "↗", 36, P["mustard"], anchor="end", bold=True))
    return svg_doc(W, H, f"{name} ({lang}): {note}", o)


STACK_LABEL = {"apachespark": "PySpark", "cockroachlabs": "CockroachDB", "githubactions": "GitHub Actions", "aws": "AWS", "azure": "Azure",
               "playwright": "Playwright", "mysql": "MySQL", "langchain": "LangChain", "pytest": "pytest", "git": "Git", "helm": "Helm"}


STACK_NOTE = {"playwright": "browser automation", "aws": "cloud", "azure": "cloud"}


def stack_svg(cfg, icons):
    W, cols, pw, ph, gap = 900, 6, 125, 112, 14
    keys = cfg["stack"]
    rows = math.ceil(len(keys) / cols)
    H = 118 + rows * (ph + gap)
    o = shell(W, H, "STACK", "what I reach for, at work and off the clock", hazard=False)
    for i, k in enumerate(keys):
        r, c = divmod(i, cols)
        x = 40 + c * (pw + gap) + (W - 80 - cols * pw - (cols - 1) * gap) / 2
        y = 100 + r * (ph + gap)
        label = STACK_LABEL.get(k, icons.get(k, {}).get("title", k))
        o.append(f'<rect x="{x:.1f}" y="{y}" width="{pw}" height="{ph}" rx="10" fill="#0c0d10" stroke="{P["border"]}"/>')
        o.append(f'<rect x="{x:.1f}" y="{y}" width="{pw}" height="3" rx="1.5" fill="{P["mustard"]}" opacity=".55"/>')
        if k in icons:
            o.append(f'<g transform="translate({x + pw / 2 - 22:.1f},{y + 20}) scale(1.83)"><path d="{icons[k]["d"]}" fill="{P["mustard"]}"/></g>')
            o.append(T(x + pw / 2, y + 98, label, 12.5, P["text"], anchor="middle"))
        else:   # no monochrome logo available: a stencil plate with the name
            size = min(30, (pw - 22) / (0.62 * max(1, len(label))) * 1.0)
            o.append(T(x + pw / 2, y + 62, label.upper(), size, P["mustard"], anchor="middle", stencil=True, spacing=1))
            o.append(T(x + pw / 2, y + 98, STACK_NOTE.get(k, ""), 11, P["dim"], anchor="middle"))
    names = ", ".join(STACK_LABEL.get(k, icons.get(k, {}).get("title", k)) for k in keys)
    return svg_doc(W, H, "Stack: " + names, o)


def writing_svg(i, w):
    W, H = 900, 88
    o = [f'<rect width="{W}" height="{H}" rx="12" fill="#12141a" stroke="{P["border"]}"/>',
         T(40, 56, f"{i:02d}", 30, P["mustard"], stencil=True),
         T(100, 42, w["title"], 22, P["text"], bold=True),
         T(100, 66, re.sub(r"^https?://", "", w["url"]).split("/")[0], 12, P["muted"]),
         T(W - 40, 58, "↗", 32, P["mustard"], anchor="end", bold=True)]
    return svg_doc(W, H, f'Article {i}: {w["title"]}', o)


def contact_svg(c):
    W, H = 290, 96
    o = [f'<rect width="{W}" height="{H}" rx="12" fill="#12141a" stroke="{P["border"]}"/>',
         f'<rect x="14" y="0" width="{W - 28}" height="3" rx="1.5" fill="{P["mustard"]}"/>',
         T(24, 44, c["label"], 22, P["mustard"], stencil=True, spacing=3),
         T(24, 70, c["value"], 12.5 if len(c["value"]) < 28 else 11, P["text"]),
         T(W - 22, 44, "↗", 24, P["mustard"], anchor="end", bold=True)]
    return svg_doc(W, H, f'{c["label"].title()}: {c["value"]}', o)


def build_all(cfg, work, repos_by_name, owner, icons, synced):
    """Every text panel the README uses, as {filename: svg}."""
    out = {"about.svg": about_svg(cfg), "desk.svg": desk_svg(work, synced),
           "head-workshop.svg": head_svg("THE WORKSHOP", "things I build for fun and to learn"),
           "stack.svg": stack_svg(cfg, icons),
           "head-writing.svg": head_svg("WRITING", "notes on RAG, LangChain and prompting")}
    for i, p in enumerate(cfg["projects"], 1):
        out[f"project-{i}.svg"] = project_svg(p, repos_by_name.get(p["repo"]), owner)
    for i, w in enumerate(cfg["writing"], 1):
        out[f"writing-{i}.svg"] = writing_svg(i, w)
    for i, c in enumerate(cfg["contact"], 1):
        out[f"contact-{i}.svg"] = contact_svg(c)
    return out


def legacy_svg(cfg):
    """The notice for the old profile repo (FABULOUSSAM), which stays up so old links keep working."""
    W, size, lh = 900, 21, 33
    paras = ["This repository was my profile README back when my GitHub username was **FABULOUSSAM**. I've since renamed my account to **shubhammohape**.",
             "My live profile now lives in **shubhammohape/shubhammohape**: a real data pipeline that rebuilds a 3D refinery, a contribution board and a work dashboard every night.",
             "I'm keeping this repo so old links keep working."]
    blocks = [wrap(parse_rich(p), W - 80, size) for p in paras]
    H = 112 + sum(len(b) for b in blocks) * lh + (len(paras) - 1) * 14 + 30
    o = shell(W, H, "OLD PROFILE REPO", f'{cfg["name"].upper()}', hazard=True)
    y = 124
    for block in blocks:
        for ln in block:
            o.append(rich_line(40, y, ln, size, P["text"]))
            y += lh
        y += 14
    return svg_doc(W, H, "Old profile repository. " + " ".join(re.sub(r"\*\*", "", p) for p in paras), o)
