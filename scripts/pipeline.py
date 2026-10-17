#!/usr/bin/env python3
"""The profile is a pipeline.

extract (GitHub API + the public contribution calendar) -> clean -> enrich (medallion tiers,
yearly stats) -> load (lake + data-quality tests) -> serve (images + README). Every run is timed
and recorded; the refinery, control room, flip-disc board and SQL console on the profile are drawn
from that record, so a red lamp is a real failure. Standard library only.
"""
import json
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from html import escape
from pathlib import Path

from contrib import blank_year, board_svg, fetch_calendar, summarize
from control import control_svg
from refinery import refinery_svg
from sqlbot import PRESETS, console_svg

ROOT = Path(__file__).resolve().parent.parent
DATA, ASSETS = ROOT / "data", ROOT / "assets"
USER = os.environ.get("GH_USER", "shubhammohape")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
SCHEDULE = "17 2 * * *"
HISTORY = 30


# ------------------------------------------------------------------ tasks
def api(path):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-pipeline"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(f"https://api.github.com{path}", headers=headers)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def age_days(iso):
    return (datetime.now(timezone.utc) - datetime.fromisoformat(iso.replace("Z", "+00:00"))).days


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def extract(ctx):
    repos = api(f"/users/{USER}/repos?per_page=100&type=owner")
    events = api(f"/users/{USER}/events/public?per_page=100")
    ctx["repos_raw"] = [
        {k: r.get(k) for k in ("id", "name", "description", "language", "fork", "archived",
                                "stargazers_count", "size", "pushed_at", "topics", "homepage")}
        for r in repos
    ]
    ctx["events_raw"] = [{"type": e["type"], "repo": e["repo"]["name"], "created_at": e["created_at"]}
                         for e in events]
    try:                                   # the name the board signs off with
        ctx["profile_name"] = api(f"/users/{USER}").get("name") or USER
    except Exception:
        ctx["profile_name"] = USER
    try:                                   # the calendar visitors see (private work included); non-fatal
        cal = fetch_calendar(USER)
        if len(cal) < 300:                 # a changed page would parse to a handful of cells: refuse to draw that
            raise ValueError(f"calendar looked wrong ({len(cal)} days)")
        ctx["calendar_raw"] = cal
    except Exception as exc:
        print(f"[extract] calendar: {type(exc).__name__}: {exc}")
        ctx["calendar_raw"] = []
    return 0, len(repos) + len(events) + len(ctx["calendar_raw"])


def clean(ctx):
    n_in = len(ctx["repos_raw"]) + len(ctx["events_raw"]) + len(ctx["calendar_raw"])
    seen, repos = set(), []
    for r in ctx["repos_raw"]:
        if r["fork"] or r["id"] in seen:
            continue
        seen.add(r["id"])
        r = dict(r)
        r["description"] = (r["description"] or "").strip()
        r["language"] = r["language"] or "n/a"
        r["topics"] = r["topics"] or []
        repos.append(r)
    cal = ctx["calendar_raw"]
    ctx["calendar_stale"] = not cal
    if not cal:                            # fetch failed or the page changed shape: keep drawing the last good year
        prev = DATA / "silver.json"
        cal = json.loads(prev.read_text()).get("calendar", []) if prev.exists() else []
    seen_d, days = set(), []
    for x in cal:
        if x["date"] in seen_d:
            continue
        seen_d.add(x["date"])
        days.append({"date": x["date"], "count": int(x["count"]), "level": int(x["level"])})
    days.sort(key=lambda x: x["date"])
    ctx["repos"], ctx["events"], ctx["calendar"] = repos, ctx["events_raw"], days
    return n_in, len(repos) + len(ctx["events"]) + len(days)


def enrich(ctx):
    for r in ctx["repos"]:
        score = sum([
            bool(r["description"]),
            age_days(r["pushed_at"]) < 365,
            r["stargazers_count"] > 0,
            bool(r["topics"] or r["homepage"]),
            r["size"] >= 200,
            r["size"] >= 5000,
        ])
        r["score"] = score
        r["tier"] = "gold" if score >= 3 else "silver" if score >= 2 else "bronze"
    ctx["stats"] = summarize(ctx["calendar"])
    return len(ctx["repos"]) + len(ctx["calendar"]), len(ctx["repos"]) + len(ctx["calendar"])


def load(ctx):
    DATA.mkdir(exist_ok=True)
    layers = {
        "bronze.json": {"repos": ctx["repos_raw"], "events": ctx["events_raw"], "calendar": ctx["calendar_raw"]},
        "silver.json": {"repos": ctx["repos"], "events": ctx["events"], "calendar": ctx["calendar"]},
        "gold.json": {"repos": ctx["repos"], "stats": ctx["stats"], "name": ctx["profile_name"], "built_at": now_iso()},
    }
    rows = 0
    for name, body in layers.items():
        (DATA / name).write_text(json.dumps(body, indent=1, sort_keys=True))
        rows += len(body["repos"]) + len(body.get("events", [])) + len(body.get("calendar", []))

    days, stats = ctx["calendar"], ctx["stats"]
    ages = [min((age_days(e["created_at"]) for e in ctx["events"]), default=None)]
    if stats["last_active"]:
        ages.append((datetime.now(timezone.utc).date() - date.fromisoformat(stats["last_active"])).days)
    ages = [a for a in ages if a is not None]
    newest = min(ages) if ages else None
    checks = []
    if newest is None:
        checks.append(("freshness", "warn", "no activity 90d"))
    elif newest > 30:
        checks.append(("freshness", "warn", f"active {newest}d ago"))
    else:
        checks.append(("freshness", "ok", f"active {newest}d ago"))
    if not ctx["repos"]:
        checks.append(("volume", "fail", "0 repos"))
    elif ctx["calendar_stale"] or len(days) < 360:
        checks.append(("volume", "warn", "calendar stale" if ctx["calendar_stale"] else f"{len(days)} days only"))
    else:
        checks.append(("volume", "ok", f"{len(ctx['repos'])} repos {len(days)}d"))
    need = ("name", "language", "pushed_at", "tier")
    bad = sum(1 for r in ctx["repos"] if any(k not in r or r[k] is None for k in need))
    bad += sum(1 for x in days if not (0 <= x["level"] <= 4 and x["count"] >= 0))
    checks.append(("schema", "fail" if bad else "ok", f"{bad} bad rows" if bad else "all keys set"))
    dup = len(ctx["repos"]) - len({r["id"] for r in ctx["repos"]}) + len(days) - len({x["date"] for x in days})
    checks.append(("unique", "fail" if dup else "ok", f"{dup} dupes" if dup else "ids unique"))
    ctx["checks"] = checks
    states = [c[1] for c in checks]
    ctx["load_status"] = "fail" if "fail" in states else "warn" if "warn" in states else "ok"
    return len(ctx["repos_raw"]) + len(ctx["events_raw"]) + len(ctx["calendar_raw"]), rows


def serve(ctx):
    """Render everything from the in-memory run (provisional serve result) and refresh the README tables."""
    update_readme(ctx["repos"])
    render_all(ctx, ctx["results"] + [{"name": "serve", "status": "ok", "secs": 0.0,
                                       "rows_in": len(ctx["repos"]), "rows_out": len(ctx["repos"])}],
               ctx["history"] + [stub_entry(ctx["results"], "ok")])
    return len(ctx["repos"]) + len(ctx["calendar"]), len(ctx["repos"]) + len(ctx["calendar"])


# ---------------------------------------------------------------- driver
def run_task(name, fn, ctx, upstream_ok):
    if not upstream_ok:
        return {"name": name, "status": "skip", "secs": 0.0, "rows_in": 0, "rows_out": 0}
    t0 = time.perf_counter()
    try:
        rows_in, rows_out = fn(ctx)
        status = ctx.pop("load_status", "ok") if name == "load" else "ok"
    except Exception as exc:  # a failed unit is the product, not a crash
        print(f"[{name}] {type(exc).__name__}: {exc}")
        rows_in = rows_out = 0
        status = "fail"
    return {"name": name, "status": status, "secs": round(time.perf_counter() - t0, 2),
            "rows_in": rows_in, "rows_out": rows_out}


def stub_entry(results, serve_status):
    tasks = {r["name"]: r["status"] for r in results if r["name"] != "serve"}
    tasks["serve"] = serve_status
    return {"ts": now_iso(), "tasks": tasks}


def main():
    hist_file = DATA / "runs.json"
    history = json.loads(hist_file.read_text()) if hist_file.exists() else []
    results = []
    ctx, ok = {"history": history, "results": results}, True
    for name, fn in zip(["extract", "clean", "enrich", "load"], (extract, clean, enrich, load)):
        res = run_task(name, fn, ctx, ok)
        results.append(res)
        ok = ok and res["status"] != "fail"
    results.append(run_task("serve", serve, ctx, ok))

    history = (history + [stub_entry(results, results[-1]["status"])])[-HISTORY:]
    DATA.mkdir(exist_ok=True)
    hist_file.write_text(json.dumps(history, indent=1))

    # If the run died before `load`, redraw from the last good lake so the failure is visible.
    if "repos" not in ctx or "checks" not in ctx or "stats" not in ctx:
        gold = json.loads((DATA / "gold.json").read_text())
        silver = json.loads((DATA / "silver.json").read_text())
        ctx["repos"], ctx["stats"], ctx["profile_name"] = gold["repos"], gold.get("stats"), gold.get("name", USER)
        ctx["events"], ctx["calendar"] = silver.get("events", []), silver.get("calendar", [])
        ctx["checks"] = [(n, "skip", "no run") for n in ("freshness", "volume", "schema", "unique")]
    render_all(ctx, results, history)
    print(json.dumps(results, indent=1))


def board_name(ctx):
    first = re.sub(r"[^A-Za-z0-9]", "", (ctx.get("profile_name") or USER).split()[0]) if (ctx.get("profile_name") or USER).split() else USER
    return (first or USER).upper()[:9]


def render_all(ctx, results, history):
    ASSETS.mkdir(exist_ok=True)
    ts = history[-1]["ts"] if history else now_iso()
    checks = ctx.get("checks", [])
    days = ctx.get("calendar") or blank_year()
    stats = ctx.get("stats") or summarize(days)
    (ASSETS / "refinery.svg").write_text(refinery_svg(results, checks, ctx["repos"], ts))
    (ASSETS / "control.svg").write_text(control_svg(results, checks, history, ctx["repos"], ts, SCHEDULE))
    (ASSETS / "contributions.svg").write_text(board_svg(days, stats, ts, board_name(ctx)))
    (ASSETS / "console.svg").write_text(console_svg(ctx["repos"], ctx.get("events", []), history, ts, days))


# ------------------------------------------------------------------ README
def update_readme(repos):
    path = ROOT / "README.md"
    if not path.exists():
        return
    rank = {"gold": 0, "silver": 1, "bronze": 2}
    top = sorted((r for r in repos if r["tier"] != "bronze"),
                 key=lambda r: (rank[r["tier"]], -r["score"], r["name"]))[:8]
    lines = ["| tier | repo | language | what it is |", "|---|---|---|---|"]
    for r in top:
        desc = escape(r["description"] or "–").replace("|", "/")
        lines.append(f"| {r['tier']} | [{r['name']}](https://github.com/{USER}/{r['name']}) | {r['language']} | {desc} |")

    body = urllib.parse.quote("Press **Submit new issue**. A workflow runs the query and replies here in about 30 seconds.", safe="")
    links = " · ".join(
        f"[`{label}`](https://github.com/{USER}/{USER}/issues/new?title={urllib.parse.quote('sql: ' + sql, safe='')}&body={body})"
        for label, sql in PRESETS)
    text = path.read_text()
    for tag, block in (("LAKE", "\n".join(lines)), ("SQL", f"**One-click queries:** {links}")):
        text = re.sub(rf"<!--{tag}:START-->.*?<!--{tag}:END-->",
                      lambda _, t=tag, b=block: f"<!--{t}:START-->\n{b}\n<!--{t}:END-->", text, flags=re.S)
    path.write_text(text)


if __name__ == "__main__":
    main()
