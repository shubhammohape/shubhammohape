#!/usr/bin/env python3
"""Local-only: summarise my pull-request and code-review activity into data/work.json.

My day job is in private repositories, so GitHub's public APIs (and the nightly Action) can't see it.
This script uses *my own* `gh` login to count it, and writes AGGREGATES ONLY: counts, medians and
monthly totals. It never writes repository names, PR titles, branch names, authors, file paths or
the organisation's name. Review data/work.json before committing it.

  python3 tools/snapshot_work.py            # last 365 days, for the authenticated gh user
"""
import json
import statistics as st
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "work.json"
Q = """query($q:String!, $after:String){ search(query:$q, type:ISSUE, first:100, after:$after){ pageInfo{hasNextPage endCursor}
 nodes{ ... on PullRequest{ createdAt mergedAt state additions deletions changedFiles reviews(first:1){ totalCount } } } } }"""


def gh(*args):
    r = subprocess.run(["gh", *args], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"gh failed: {r.stderr.strip()[:300]}")
    return r.stdout


def fetch(query):
    rows, after = [], None
    while True:
        args = ["api", "graphql", "-f", f"query={Q}", "-f", f"q={query}"] + (["-f", f"after={after}"] if after else [])
        s = json.loads(gh(*args))["data"]["search"]
        rows += [n for n in s["nodes"] if n]
        if not s["pageInfo"]["hasNextPage"]:
            return rows
        after = s["pageInfo"]["endCursor"]


def parse(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def main():
    me = json.loads(gh("api", "user"))["login"]
    today = datetime.now(timezone.utc).date()
    since = today - timedelta(days=364)
    authored = fetch(f"author:{me} is:pr created:>={since}")
    reviewed = fetch(f"reviewed-by:{me} -author:{me} is:pr created:>={since}")
    merged = [p for p in authored if p["mergedAt"]]
    hours = sorted((parse(p["mergedAt"]) - parse(p["createdAt"])).total_seconds() / 3600 for p in merged)
    months, y, m = [], since.year, since.month
    while (y, m) <= (today.year, today.month):
        months.append(f"{y}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    count = lambda rows, key: sum(1 for p in rows if p["createdAt"][:7] == key)
    out = {
        "as_of": today.isoformat(), "window_days": 365,
        "raised": len(authored), "reviewed": len(reviewed),
        "merged_pct": round(100 * len(merged) / max(1, len(authored))),
        "median_hours_to_merge": round(st.median(hours), 1) if hours else 0,
        "median_additions": round(st.median(p["additions"] for p in authored)) if authored else 0,
        "median_deletions": round(st.median(p["deletions"] for p in authored)) if authored else 0,
        "median_files": round(st.median(p["changedFiles"] for p in authored)) if authored else 0,
        "small_pct": round(100 * sum(1 for p in authored if p["additions"] + p["deletions"] < 100) / max(1, len(authored))),
        "reviewed_before_merge_pct": round(100 * sum(1 for p in authored if p["reviews"]["totalCount"]) / max(1, len(authored))),
        "reviews_per_pr": round(len(reviewed) / max(1, len(authored)), 1),
        "monthly": [{"m": k, "raised": count(authored, k), "reviewed": count(reviewed, k)} for k in months],
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "monthly"}, indent=1))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
