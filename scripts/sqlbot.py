#!/usr/bin/env python3
"""Query this profile. A read-only SQL console over the lake.

A visitor opens an issue titled `sql: SELECT ...` (the README has one-click presets);
a workflow runs this script and replies with the result table.

The query comes from a stranger, so it is treated as hostile:
  * one statement, SELECT/WITH only, 400 characters at most;
  * sqlite3 authorizer: only reads are allowed, everything else (PRAGMA, ATTACH, INSERT,
    DDL, extensions) is denied at prepare time;
  * hard limits on value size, expression depth and compound selects;
  * a 3 second wall-clock budget via the progress handler, and at most 40 rows back;
  * the data is the already-public gold/silver layers, loaded into an in-memory database,
    and the workflow that runs this has no write permissions and no secrets in its env;
  * output goes inside a code fence with backticks and control characters stripped, so it
    cannot ping anyone or inject markup.
"""
import argparse
import json
import os
import re
import sqlite3
import sys
import time
from datetime import date, datetime, timezone
from html import escape
from pathlib import Path

from iso import TEX
from theme import FONT, P

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MAX_ROWS, MAX_LEN, BUDGET = 40, 400, 3.0

SCHEMA = {
    "repos": "name, language, size_kb, stars, pushed_at, tier, score, description",
    "events": "type, repo, created_at",
    "runs": "ts, extract, clean, enrich, load, serve",
    "days": "date, count, level, weekday, month",
}
PRESETS = [
    ("tiers", "SELECT tier, COUNT(*) AS repos, CAST(AVG(size_kb) AS INT) AS avg_kb FROM repos GROUP BY tier ORDER BY repos DESC"),
    ("languages", "SELECT language, COUNT(*) AS repos FROM repos GROUP BY language ORDER BY repos DESC LIMIT 5"),
    ("biggest", "SELECT name, size_kb, tier FROM repos ORDER BY size_kb DESC LIMIT 5"),
    ("dormant", "SELECT name, SUBSTR(pushed_at, 1, 10) AS last_push FROM repos ORDER BY pushed_at LIMIT 5"),
    ("pipeline", "SELECT ts, extract, clean, enrich, load, serve FROM runs ORDER BY ts DESC LIMIT 5"),
    ("busiest", "SELECT date, weekday, count FROM days ORDER BY count DESC LIMIT 5"),
    ("weekdays", "SELECT weekday, SUM(count) AS total, ROUND(AVG(count), 1) AS per_day FROM days GROUP BY weekday ORDER BY total DESC"),
    ("months", "SELECT month, SUM(count) AS total, COUNT(*) FILTER (WHERE count > 0) AS active FROM days GROUP BY month ORDER BY total DESC LIMIT 6"),
]
KEYWORDS = {"SELECT", "FROM", "WHERE", "GROUP", "BY", "ORDER", "LIMIT", "AS", "AND", "OR", "NOT", "DESC", "ASC", "WITH",
            "COUNT", "ROUND", "AVG", "SUM", "MAX", "MIN", "SUBSTR", "LIKE", "IN", "HAVING", "DISTINCT", "JOIN", "ON", "CASE", "WHEN", "THEN", "ELSE", "END"}
ALLOWED_ACTIONS = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE}
DENIED_FUNCS = {"load_extension", "readfile", "writefile", "edit", "randomblob", "zeroblob"}


def _authorizer(action, arg1, arg2, dbname, source):
    if action not in ALLOWED_ACTIONS:
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_FUNCTION and (arg2 or "").lower() in DENIED_FUNCS:
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def build_db(repos, events, runs, days=()):
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE repos(name TEXT, language TEXT, size_kb INTEGER, stars INTEGER, pushed_at TEXT, tier TEXT, score INTEGER, description TEXT)")
    con.execute("CREATE TABLE events(type TEXT, repo TEXT, created_at TEXT)")
    con.execute("CREATE TABLE runs(ts TEXT, extract TEXT, clean TEXT, enrich TEXT, load TEXT, serve TEXT)")
    con.execute("CREATE TABLE days(date TEXT, count INTEGER, level INTEGER, weekday TEXT, month TEXT)")
    con.executemany("INSERT INTO repos VALUES (?,?,?,?,?,?,?,?)",
                    [(r["name"], r["language"], r["size"], r["stargazers_count"], r["pushed_at"], r["tier"], r["score"], r["description"]) for r in repos])
    con.executemany("INSERT INTO events VALUES (?,?,?)", [(e["type"], e["repo"], e["created_at"]) for e in events])
    names = ("SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT")
    con.executemany("INSERT INTO days VALUES (?,?,?,?,?)",
                    [(x["date"], x["count"], x["level"], names[(date.fromisoformat(x["date"]).weekday() + 1) % 7], x["date"][:7]) for x in days])
    con.executemany("INSERT INTO runs VALUES (?,?,?,?,?,?)",
                    [(h["ts"], *(h["tasks"].get(k, "skip") for k in ("extract", "clean", "enrich", "load", "serve"))) for h in runs])
    con.commit()
    # lock it down only after the data is in
    con.execute("PRAGMA query_only = ON")
    con.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 100_000)
    con.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, MAX_LEN + 100)
    con.setlimit(sqlite3.SQLITE_LIMIT_EXPR_DEPTH, 40)
    con.setlimit(sqlite3.SQLITE_LIMIT_COMPOUND_SELECT, 5)
    con.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, 0)
    con.set_authorizer(_authorizer)
    return con


def load_db():
    gold = json.loads((DATA / "gold.json").read_text())
    silver = json.loads((DATA / "silver.json").read_text())
    runs_path = DATA / "runs.json"
    runs = json.loads(runs_path.read_text()) if runs_path.exists() else []
    return build_db(gold["repos"], silver.get("events", []), runs, silver.get("calendar", []))


def clip(v, n=44):
    s = "NULL" if v is None else str(v)
    s = re.sub(r"[\x00-\x1f\x7f`]", " ", s)
    return s if len(s) <= n else s[: n - 1] + "…"


def run_query(con, sql):
    """Return (cols, rows, truncated, ms) or raise ValueError with a safe message."""
    sql = (sql or "").strip().rstrip(";").strip()
    if not sql:
        raise ValueError("empty query")
    if len(sql) > MAX_LEN:
        raise ValueError(f"query too long ({len(sql)} > {MAX_LEN} chars)")
    if "\x00" in sql:
        raise ValueError("invalid character in query")
    if sql.split(None, 1)[0].lower() not in ("select", "with"):
        raise ValueError("only SELECT queries are allowed")
    t0 = time.monotonic()
    con.set_progress_handler(lambda: 1 if time.monotonic() - t0 > BUDGET else 0, 2000)
    try:
        cur = con.execute(sql)
        cols = [d[0] for d in (cur.description or [])]
        rows = cur.fetchmany(MAX_ROWS + 1)
    except sqlite3.OperationalError as exc:
        msg = "query ran out of time" if "interrupted" in str(exc) else str(exc)
        raise ValueError(clip(msg, 120)) from None
    except (sqlite3.DatabaseError, sqlite3.ProgrammingError, OverflowError) as exc:
        raise ValueError(clip(str(exc), 120)) from None
    finally:
        con.set_progress_handler(None, 0)
    return cols, rows[:MAX_ROWS], len(rows) > MAX_ROWS, round((time.monotonic() - t0) * 1000)


def fmt_table(cols, rows, gap="  "):
    cells = [[clip(v) for v in r] for r in rows]
    head = [clip(c, 24) for c in cols]
    widths = [max([len(h)] + [len(r[i]) for r in cells]) for i, h in enumerate(head)]
    line = lambda r: gap.join(c.ljust(w) for c, w in zip(r, widths)).rstrip()
    return [line(head), gap.join("─" * w for w in widths)] + [line(r) for r in cells]


def reply(sql):
    con = load_db()
    schema = "\n".join(f"  {t}({c})" for t, c in SCHEMA.items())
    echo = clip(sql, MAX_LEN)
    try:
        cols, rows, trunc, ms = run_query(con, sql)
    except ValueError as exc:
        return (f"**✕ {clip(str(exc), 120)}**\n\n```text\n{schema}\n```\n"
                f"Read-only SQLite over this profile's lake. One `SELECT` per issue, title format `sql: SELECT ...`.")
    table = "\n".join(fmt_table(cols, rows)) if cols else "(no columns)"
    note = f" (first {MAX_ROWS} shown)" if trunc else ""
    return (f"**✓ {len(rows)} row{'s' if len(rows) != 1 else ''}{note} · {ms} ms · read-only sqlite**\n\n"
            f"```sql\n{echo}\n```\n```text\n{table}\n```\n"
            f"<sub>tables: " + ", ".join(f"`{t}`" for t in SCHEMA) + " · data is rebuilt nightly by the pipeline</sub>")


# ----------------------------------------------------------- console image
def _wrap(sql, width=92):
    lines, cur = [], ""
    for w in sql.split():
        if len(cur) + len(w) + 1 > width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    return lines + ([cur] if cur else [])


def _kw(line):
    out = []
    for w in re.split(r"(\s+)", line):
        base = re.sub(r"[^A-Za-z]", "", w).upper()
        col = P["mustard_hi"] if base in KEYWORDS and w.strip() else P["text"]
        out.append(f'<tspan fill="{col}">{escape(w)}</tspan>')
    return "".join(out)


def _glow(x, y, inner, size, weight="400", fill=None, glow=None, extra=""):
    """Phosphor text: a soft halo (wide translucent stroke) under the crisp glyphs."""
    halo = (f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" font-family="{FONT}" xml:space="preserve" {extra} fill="none" '
            f'stroke="{glow or P["mustard"]}" stroke-opacity=".22" stroke-width="3.2" stroke-linejoin="round">{inner}</text>')
    return halo + f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" font-family="{FONT}" xml:space="preserve" {extra} fill="{fill or P["text"]}">{inner}</text>'


def console_svg(repos, events, runs, ts, days=(), W=900):
    day = datetime.now(timezone.utc).timetuple().tm_yday
    label, sql = PRESETS[day % len(PRESETS)]
    con = build_db(repos, events, runs, days)
    cols, rows, trunc, ms = run_query(con, sql)
    qlines = _wrap(sql)
    table = fmt_table(cols, rows)
    body_h = 30 + 18 * len(qlines) + 14 + 17 * len(table) + 34
    sx, sy, sw = 18, 18, W - 36
    H = sy + 26 + body_h + 48
    sh = H - sy - 48 - 4
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
         f'aria-label="A SQL terminal over this profile\'s data. Query of the day ({label}): {escape(sql)}. {len(rows)} rows returned.">',
         '<defs>'
         '<linearGradient id="mb" x1="0" x2="1" y1="0" y2="1"><stop offset="0" stop-color="#2d323c"/><stop offset=".5" stop-color="#171a20"/><stop offset="1" stop-color="#0c0d10"/></linearGradient>'
         '<radialGradient id="mv" cx=".5" cy=".5" r=".75"><stop offset=".55" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".6"/></radialGradient>'
         '<linearGradient id="mg" x1="0" x2="1" y1="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".09"/><stop offset=".45" stop-color="#fff" stop-opacity="0"/></linearGradient>'
         '<radialGradient id="ms" cx=".35" cy=".3" r=".8"><stop offset="0" stop-color="#cfd8e6"/><stop offset=".7" stop-color="#59627a"/><stop offset="1" stop-color="#1b1f26"/></radialGradient>'
         f'<radialGradient id="mp"><stop offset="0" stop-color="{P["mustard_hi"]}"/><stop offset="1" stop-color="{P["mustard"]}" stop-opacity="0"/></radialGradient>'
         f'<pattern id="mscan" width="4" height="3" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="#000" opacity=".3"/></pattern>'
         f'<pattern id="p_brush" width="64" height="96" patternUnits="userSpaceOnUse"><image href="{TEX["brush"]}" width="64" height="96"/></pattern>'
         f'<clipPath id="mc"><rect x="{sx}" y="{sy}" width="{sw}" height="{sh}" rx="12"/></clipPath></defs>',
         f'<rect width="{W}" height="{H}" rx="16" fill="url(#mb)" stroke="#000"/>',
         f'<rect width="{W}" height="{H}" rx="16" fill="url(#p_brush)" opacity=".14"/>',
         f'<rect x="1.5" y="1.5" width="{W - 3}" height="{H - 3}" rx="15" fill="none" stroke="#fff" stroke-opacity=".08"/>',
         f'<rect x="{sx - 4}" y="{sy - 4}" width="{sw + 8}" height="{sh + 8}" rx="15" fill="#000" opacity=".75"/>',
         f'<rect x="{sx}" y="{sy}" width="{sw}" height="{sh}" rx="12" fill="#060505"/>']
    o.append('<g clip-path="url(#mc)">')
    # status line
    o.append(f'<rect x="{sx}" y="{sy}" width="{sw}" height="26" fill="#0d0b07"/><line x1="{sx}" y1="{sy + 26}" x2="{sx + sw}" y2="{sy + 26}" stroke="#2a2418"/>')
    o.append(_glow(sx + 14, sy + 17, f"lake.sql  ·  read-only sqlite  ·  query of the day: {escape(label)}", 11, fill=P["muted"], glow=P["muted"]))
    y = sy + 26 + 30
    for i, ln in enumerate(qlines):
        prompt = f'<tspan fill="{P["mustard"]}" font-weight="700">lake&gt;</tspan> ' if i == 0 else "      "
        o.append(_glow(sx + 14, y, prompt + _kw(ln), 13))
        y += 18
    cx = sx + 14 + 7.8 * (len(qlines[-1]) + 7)
    o.append(f'<rect x="{cx:.1f}" y="{y - 31}" width="8" height="15" fill="{P["mustard"]}"><animate attributeName="opacity" values="1;1;0;0" dur="1.1s" repeatCount="indefinite"/></rect>')
    y += 14
    for i, ln in enumerate(table):
        fill = P["mustard"] if i == 0 else "#6b5a22" if i == 1 else P["text"]
        o.append(_glow(sx + 14, y, escape(ln), 12.5, "700" if i == 0 else "400", fill=fill))
        y += 17
    o.append(_glow(sx + 14, sy + sh - 12, f"{len(rows)} rows · {ms} ms · rebuilt {escape(ts)} · tables: repos, events, runs", 10.5, fill=P["muted"], glow=P["muted"]))
    # CRT: scanlines, vignette, glare
    o.append(f'<rect x="{sx}" y="{sy}" width="{sw}" height="{sh}" fill="url(#mscan)"/>')
    o.append(f'<rect x="{sx}" y="{sy}" width="{sw}" height="{sh}" fill="url(#mv)"/>')
    o.append(f'<polygon points="{sx},{sy} {sx + sw * .55:.0f},{sy} {sx + sw * .3:.0f},{sy + sh} {sx},{sy + sh}" fill="url(#mg)"/>')
    o.append("</g>")
    o.append(f'<rect x="{sx}" y="{sy}" width="{sw}" height="{sh}" rx="12" fill="none" stroke="#000" stroke-width="2"/>')
    # bezel furniture: nameplate, vents, power LED, screws
    by = H - 26
    o.append(f'<text x="{sx + 2}" y="{by + 4}" fill="#000" fill-opacity=".8" font-size="10" font-weight="700" letter-spacing="3" font-family="{FONT}">LAKE-TERMINAL  LT-1</text>'
             f'<text x="{sx + 1}" y="{by + 3}" fill="#8b8f98" font-size="10" font-weight="700" letter-spacing="3" font-family="{FONT}">LAKE-TERMINAL  LT-1</text>')
    for i in range(7):
        o.append(f'<rect x="{W // 2 - 40 + i * 12}" y="{by - 6}" width="6" height="14" rx="3" fill="#050608" stroke="#fff" stroke-opacity=".06"/>')
    o.append(f'<circle cx="{W - 60}" cy="{by + 1}" r="9" fill="url(#mp)" opacity=".5"><animate attributeName="opacity" values=".5;.25;.5" dur="3s" repeatCount="indefinite"/></circle>'
             f'<circle cx="{W - 60}" cy="{by + 1}" r="3.6" fill="{P["mustard_hi"]}" stroke="#050608"/>')
    for x, yy in ((10, 10), (W - 10, 10), (10, H - 10), (W - 10, H - 10)):
        o.append(f'<circle cx="{x}" cy="{yy}" r="3.4" fill="url(#ms)" stroke="#050608" stroke-width=".8"/>')
    o.append("</svg>")
    return "\n".join(o)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    title = os.environ.get("QUERY", "")
    m = re.match(r"(?is)^\s*sql\s*:\s*(.*)$", title)
    sql = m.group(1) if m else ""
    Path(a.out).write_text(reply(sql))
    print("replied")


if __name__ == "__main__":
    main()
