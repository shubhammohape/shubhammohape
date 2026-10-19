#!/usr/bin/env python3
"""Dev-time tool: collect monochrome tool logos (simple-icons, CC0 1.0) into scripts/icons.json.

The profile's STACK panel draws them in the page's own colours instead of hot-linking brand-coloured
images. Stdlib only. Slugs missing from simple-icons (trademark removals) get a lettered plate instead.
"""
import json
import re
import urllib.request
from pathlib import Path

BASE = "https://raw.githubusercontent.com/simple-icons/simple-icons/develop/icons"
SLUGS = ["python", "selenium", "databricks", "apachespark", "mysql", "cockroachlabs", "snowflake", "git", "kubernetes",
         "helm", "docker", "githubactions", "pytest", "fastapi", "langchain", "jupyter", "linux"]
OUT = Path(__file__).resolve().parent.parent / "scripts" / "icons.json"

icons = {}
for s in SLUGS:
    svg = urllib.request.urlopen(f"{BASE}/{s}.svg", timeout=30).read().decode()
    icons[s] = {"title": re.search(r"<title>([^<]+)</title>", svg).group(1), "d": re.search(r'<path d="([^"]+)"', svg).group(1)}
OUT.write_text(json.dumps(icons, separators=(",", ":")))
print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB, {len(icons)} icons)")
