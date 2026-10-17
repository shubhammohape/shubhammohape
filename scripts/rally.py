#!/usr/bin/env python3
"""Volleyball rally for the profile README.

  rally.py bump --player <login>   a visitor hits the ball (issue titled "bump")
  rally.py tick                    hourly: drop the ball if nobody hit it for 24h

State lives in data/rally.json; the court image is regenerated from it.
The player name comes from the workflow's event context and is validated here
before it is ever written into an SVG or a comment.
"""
import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path

from iso import TEX
from theme import FONT, P

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "data" / "rally.json"
ASSETS = ROOT / "assets"
WINDOW = timedelta(hours=24)
LOGIN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
FMT = "%Y-%m-%dT%H:%M:%SZ"


def now():
    return datetime.now(timezone.utc).replace(microsecond=0)


def load():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"count": 0, "best": 0, "total": 0, "status": "idle", "last_player": None,
            "last_ts": None, "players": [], "drops": 0}


def save(s):
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(s, indent=1))


def expire(s, t):
    """Drop the ball if a live rally has gone quiet for the whole window."""
    if s["status"] == "live" and t - datetime.strptime(s["last_ts"], FMT).replace(tzinfo=timezone.utc) > WINDOW:
        s.update(status="dropped", count=0, last_player=None)
        s["drops"] += 1
        return True
    return False


def bump(s, player, t):
    expire(s, t)
    if s["status"] == "live" and player == s["last_player"]:
        return False, f"@{player} already hit it. The ball needs a different player."
    s["count"] = s["count"] + 1 if s["status"] == "live" else 1
    s.update(status="live", last_player=player, last_ts=t.strftime(FMT))
    s["best"] = max(s["best"], s["count"])
    s["total"] += 1
    s["players"] = ([player] + [p for p in s["players"] if p != player])[:5]
    return True, f"Nice hit @{player}! Rally is at {s['count']} (best {s['best']})."


SKIN = "#b98b62"


def defs():
    return ('<defs>'
            '<linearGradient id="rf" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#1c1e24"/><stop offset="1" stop-color="#09090b"/></linearGradient>'
            '<radialGradient id="rl"><stop offset="0" stop-color="#fff1c9" stop-opacity=".30"/><stop offset=".55" stop-color="#ffd98a" stop-opacity=".09"/><stop offset="1" stop-color="#ffd98a" stop-opacity="0"/></radialGradient>'
            '<linearGradient id="rc" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#fff1c9" stop-opacity=".22"/><stop offset="1" stop-color="#fff1c9" stop-opacity="0"/></linearGradient>'
            '<radialGradient id="rb" cx=".35" cy=".3" r=".85"><stop offset="0" stop-color="#fff3b0"/><stop offset=".42" stop-color="#E1AD01"/><stop offset="1" stop-color="#6d5200"/></radialGradient>'
            '<linearGradient id="rp" x1="0" x2="1" y1="0" y2="0"><stop offset="0" stop-color="#2b313b"/><stop offset=".35" stop-color="#cfd8e6"/><stop offset="1" stop-color="#1b1f26"/></linearGradient>'
            '<linearGradient id="rj1" x1="0" x2="1" y1="0" y2="0"><stop offset="0" stop-color="#7a5d00"/><stop offset=".4" stop-color="#ffd23f"/><stop offset="1" stop-color="#8a6a00"/></linearGradient>'
            '<linearGradient id="rj2" x1="0" x2="1" y1="0" y2="0"><stop offset="0" stop-color="#4a5362"/><stop offset=".4" stop-color="#e6edf5"/><stop offset="1" stop-color="#59627a"/></linearGradient>'
            '<radialGradient id="rh" cx=".4" cy=".35" r=".8"><stop offset="0" stop-color="#d9b48f"/><stop offset="1" stop-color="#7a5a3c"/></radialGradient>'
            '<radialGradient id="rg"><stop offset="0" stop-color="#000" stop-opacity=".55"/><stop offset="1" stop-color="#000" stop-opacity="0"/></radialGradient>'
            f'<pattern id="p_conc" width="128" height="128" patternUnits="userSpaceOnUse"><image href="{TEX["conc"]}" width="128" height="128"/></pattern>'
            '</defs>')


def player(x, fy, side, jersey, keys, vals, rest, live, dur):
    """A shaded player; the hitting arm swings up exactly when the ball arrives (same cycle as the ball)."""
    arm = f'<line x1="0" y1="0" x2="{side * 18}" y2="0" stroke="{SKIN}" stroke-width="5.2" stroke-linecap="round"/>'
    if live:
        arm = (f'<g transform="translate(0,-52)"><g transform="rotate({rest})">{arm}'
               f'<animateTransform attributeName="transform" type="rotate" keyTimes="{keys}" values="{vals}" '
               f'dur="{dur:.2f}s" repeatCount="indefinite"/></g></g>')
    else:
        arm = f'<g transform="translate(0,-52) rotate({rest})">{arm}</g>'
    return (f'<g transform="translate({x},{fy})">'
            f'<ellipse cx="{side * -9}" cy="3" rx="19" ry="4" fill="#000" opacity=".45"/>'
            f'<path d="M-3,-24 L-9,0 M3,-24 L9,0" stroke="#0e0f12" stroke-width="6" stroke-linecap="round"/>'
            f'<path d="M-3,-24 L-9,0 M3,-24 L9,0" stroke="{SKIN}" stroke-width="3.4" stroke-linecap="round" opacity=".9" transform="translate(0,-6) scale(1,.75)"/>'
            f'<rect x="-8.5" y="-36" width="17" height="14" rx="3" fill="#15171c" stroke="#000" stroke-width=".8"/>'
            f'<rect x="-9.5" y="-60" width="19" height="26" rx="5" fill="url(#{jersey})" stroke="#050608" stroke-width=".9"/>'
            f'<path d="M-9.5,-46 L9.5,-46" stroke="#000" stroke-opacity=".25" stroke-width="1"/>'
            f'<circle cx="0" cy="-69" r="7.4" fill="url(#rh)" stroke="#050608" stroke-width=".8"/>'
            f'<path d="M-7.2,-71 A7.4,7.4 0 0 1 7.2,-71 L7.2,-73 A8.4,8 0 0 0 -7.2,-73 Z" fill="#14100c"/>'
            f'{arm}</g>')


def ball_shape(r=11):
    return (f'<circle r="{r}" fill="url(#rb)" stroke="#2a2000" stroke-width="1"/>'
            f'<path d="M{-r},0 Q0,{-r * .85} {r},0" fill="none" stroke="#4d3a00" stroke-width="1.2"/>'
            f'<path d="M{-r * .72},{-r * .72} Q{r * .25},{-r * .1} {r * .5},{r * .88}" fill="none" stroke="#4d3a00" stroke-width="1.2"/>'
            f'<path d="M{r * .72},{-r * .72} Q{-r * .25},{-r * .1} {-r * .5},{r * .88}" fill="none" stroke="#4d3a00" stroke-width="1.2"/>'
            f'<path d="M{-r * .55},{-r * .6} A{r * .8},{r * .8} 0 0 1 {r * .1},{-r * .86}" fill="none" stroke="#fff" stroke-opacity=".55" stroke-width="1.6" stroke-linecap="round"/>')


def court_svg(s):
    W, H = 900, 274
    live = s["status"] == "live"
    fy = 206
    dur = max(1.0, 3.2 - 0.15 * s["count"])
    hy = fy - 61
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
         f'aria-label="Volleyball rally: {s["count"]} hits in a row, best {s["best"]}. {"Ball in play." if live else "The ball is on the floor."}">',
         defs(),
         f'<rect width="{W}" height="{H}" rx="14" fill="#08080a"/>',
         f'<rect y="{fy - 6}" width="{W}" height="{H - fy + 6}" fill="url(#rf)"/>',
         f'<rect y="{fy - 6}" width="{W}" height="{H - fy + 6}" fill="url(#p_conc)" opacity=".45"/>']
    # floodlights with soft cones of light
    for x in (70, W - 70):
        o.append(f'<polygon points="{x - 4},40 {x + 4},40 {x + (190 if x < 450 else -190)},{fy + 30} {x + (-60 if x < 450 else 60)},{fy + 30}" fill="url(#rc)"/>')
        o.append(f'<rect x="{x - 1.6}" y="40" width="3.2" height="{fy - 34}" fill="url(#rp)"/>')
        o.append(f'<rect x="{x - 11}" y="32" width="22" height="9" rx="2.5" fill="#1b1f26" stroke="#59627a" stroke-width=".9"/><rect x="{x - 8}" y="39" width="16" height="3" rx="1.5" fill="#fff4d2"/>')
        o.append(f'<ellipse cx="{x}" cy="42" rx="46" ry="26" fill="url(#rl)"/>')
    o.append(f'<ellipse cx="450" cy="{fy + 16}" rx="360" ry="34" fill="url(#rl)" opacity=".8"/>')
    # court paint (side view): far baseline, centre line running toward the viewer, near boundary
    o.append(f'<line x1="40" y1="{fy + 2}" x2="{W - 40}" y2="{fy + 2}" stroke="#e8e2cf" stroke-opacity=".35" stroke-width="1.6"/>')
    o.append(f'<line x1="26" y1="{fy + 34}" x2="{W - 26}" y2="{fy + 34}" stroke="{P["mustard"]}" stroke-opacity=".5" stroke-width="2.4"/>')
    o.append(f'<line x1="450" y1="{fy + 2}" x2="450" y2="{fy + 34}" stroke="{P["mustard"]}" stroke-opacity=".45" stroke-width="2"/>')
    # net: shadow, posts, mesh, tape
    o.append(f'<polygon points="414,{fy + 2} 486,{fy + 2} 516,{fy + 12} 446,{fy + 12}" fill="#000" opacity=".32"/>')
    for x in (414, 486):
        o.append(f'<ellipse cx="{x}" cy="{fy + 2}" rx="9" ry="2.6" fill="#0b0c0f" stroke="#3b4350"/>')
        o.append(f'<rect x="{x - 2.6}" y="{fy - 92}" width="5.2" height="{94}" fill="url(#rp)" stroke="#050608" stroke-width=".6"/>')
    top, bot = fy - 88, fy - 50
    o.append(f'<rect x="416" y="{top}" width="68" height="{bot - top}" fill="#0b0c0f" opacity=".55"/>')
    for i in range(1, 11):
        o.append(f'<line x1="{416 + i * 6.2:.1f}" y1="{top}" x2="{416 + i * 6.2:.1f}" y2="{bot}" stroke="#aab4c4" stroke-width=".7" opacity=".55"/>')
    for i in range(1, 7):
        o.append(f'<line x1="416" y1="{top + i * 5.4:.1f}" x2="484" y2="{top + i * 5.4:.1f}" stroke="#aab4c4" stroke-width=".7" opacity=".55"/>')
    o.append(f'<rect x="414" y="{top - 3}" width="72" height="6" rx="1.5" fill="#f1f3f6" stroke="#050608" stroke-width=".6"/><rect x="414" y="{top - 3}" width="72" height="2" fill="#fff" opacity=".7"/>')
    o.append(f'<rect x="414" y="{bot - 1}" width="72" height="2.6" fill="#cfd5de" stroke="#050608" stroke-width=".4"/>')
    o.append(player(190, fy, 1, "rj1", "0;.15;.3;.85;1", "-30;30;60;60;-30", 60, live, dur))
    o.append(player(710, fy, -1, "rj2", "0;.35;.5;.65;1", "-60;-60;30;-60;-60", -60, live, dur))
    for x, label in ((190, "your side"), (710, "their side")):
        o.append(f'<text x="{x}" y="{fy + 24}" fill="{P["muted"]}" font-size="10.5" text-anchor="middle" font-family="{FONT}">{label}</text>')
    if live:
        path = f"M206,{hy} Q450,-40 694,{hy} Q450,-40 206,{hy}"
        spl = 'calcMode="spline" keyTimes="0;.5;1" keySplines=".3 0 .7 1;.3 0 .7 1"'
        # ground shadow follows the ball and shrinks as it rises
        o.append(f'<g><ellipse rx="13" ry="3.2" fill="#000" opacity=".5"><animate attributeName="rx" values="13;6;13;6;13" keyTimes="0;.25;.5;.75;1" dur="{dur:.2f}s" repeatCount="indefinite"/>'
                 f'<animate attributeName="opacity" values=".5;.2;.5;.2;.5" keyTimes="0;.25;.5;.75;1" dur="{dur:.2f}s" repeatCount="indefinite"/></ellipse>'
                 f'<animateMotion dur="{dur:.2f}s" repeatCount="indefinite" path="M206,{fy + 4} L694,{fy + 4} L206,{fy + 4}" {spl}/></g>')
        for lag, op in ((0.07, .22), (0.14, .11)):   # motion trail: the same flight, a beat behind
            o.append(f'<g opacity="{op}"><animateMotion dur="{dur:.2f}s" begin="{-(dur - lag):.2f}s" repeatCount="indefinite" path="{path}" {spl}/>{ball_shape()}</g>')
        o.append(f'<g><animateMotion dur="{dur:.2f}s" repeatCount="indefinite" path="{path}" {spl}/><g><animateTransform attributeName="transform" type="rotate" values="0;360" '
                 f'dur="{dur:.2f}s" repeatCount="indefinite"/>{ball_shape()}</g></g>')
        status = f"drops after {(datetime.strptime(s['last_ts'], FMT) + WINDOW).strftime('%Y-%m-%d %H:%M')} UTC"
    else:
        o.append(f'<ellipse cx="571" cy="{fy + 4}" rx="13" ry="3.2" fill="#000" opacity=".5"/><g transform="translate(560,{fy - 8})">{ball_shape()}</g>')
        status = "the ball is on the floor. hit it to start a new rally."
    # scoreboard
    o.append(f'<rect x="24" y="22" width="132" height="76" rx="8" fill="#050506" stroke="#2a2e36" stroke-width="1.5"/><rect x="26" y="24" width="128" height="72" rx="6" fill="none" stroke="#000" stroke-width="2"/>')
    o.append(f'<text x="38" y="42" fill="{P["mustard"]}" fill-opacity=".9" font-size="11" font-weight="700" letter-spacing="4" font-family="{FONT}">RALLY</text>')
    cnt = str(s["count"])
    o.append(f'<text x="38" y="82" fill="none" stroke="{P["mustard"]}" stroke-opacity=".28" stroke-width="4" stroke-linejoin="round" font-size="40" font-weight="700" font-family="{FONT}">{cnt}</text>'
             f'<text x="38" y="82" fill="{P["mustard_hi"]}" font-size="40" font-weight="700" font-family="{FONT}">{cnt}</text>')
    who = ", ".join("@" + escape(x) for x in s["players"]) or "nobody yet"
    o.append(f'<text x="28" y="{H - 14}" fill="{P["mustard"]}" font-size="11" font-family="{FONT}">{escape(status)}</text>')
    o.append(f'<text x="{W - 28}" y="{H - 14}" fill="{P["muted"]}" font-size="10.5" text-anchor="end" font-family="{FONT}">'
             f'best {s["best"]} · {s["total"]} hits all-time · {s["drops"]} drops · recent: {who}</text>')
    o.append(f'<rect width="{W}" height="{H}" rx="14" fill="none" stroke="{P["border"]}"/>')
    o.append("</svg>")
    return "\n".join(o)


def render(s):
    ASSETS.mkdir(exist_ok=True)
    (ASSETS / "rally.svg").write_text(court_svg(s))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("bump")
    b.add_argument("--player", required=True)
    b.add_argument("--message-file")
    sub.add_parser("tick")
    a = ap.parse_args()

    s, t, msg = load(), now(), ""
    if a.cmd == "bump":
        if not LOGIN.match(a.player):
            sys.exit("invalid player name")
        _, msg = bump(s, a.player, t)
    else:
        expire(s, t)
    save(s)
    render(s)
    if a.cmd == "bump" and a.message_file:
        Path(a.message_file).write_text(msg)
    print(msg or f"status={s['status']} count={s['count']}")


if __name__ == "__main__":
    main()
