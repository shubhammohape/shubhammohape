"""One palette: near-black and mustard, with hazard-tape accents.

GitHub serves README images through camo, so there is no page CSS to inherit. The
images are dark cards (rounded, with a border), which read fine on a light or a
dark GitHub page, so we ship a single scheme instead of light/dark pairs.
"""

FONT = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

P = {
    "bg": "#0b0c0f", "panel": "#14161b", "panel2": "#1b1e25", "border": "#2a2e36",
    "text": "#ece8dc", "muted": "#8b8f98", "dim": "#4a4f59",
    "mustard": "#E1AD01", "mustard_hi": "#FFD23F", "mustard_lo": "#8a6a00",
    # status. ok is the brand colour; warn/fail are far enough away to read at a glance,
    # and every use pairs the colour with a glyph and a word.
    "ok": "#E1AD01", "warn": "#ff8f3a", "fail": "#ff5252", "skip": "#5b606b",
    "bronze": "#c0763c", "silver": "#a9b4c2", "gold": "#E1AD01",
}

GLYPH = {"ok": "✓", "warn": "!", "fail": "✕", "skip": "–"}

# (dark, mid, light) ramps used for shaded solids
MATS = {
    "steel": ("#1d2128", "#3a414d", "#6a7384"),
    "mustard": ("#7a5d00", "#E1AD01", "#FFE07A"),
    "bronze": ("#5e3413", "#c0763c", "#f0b17c"),
    "silver": ("#566170", "#a9b4c2", "#e6edf5"),
    "night": ("#0f1115", "#1b1e25", "#2f343e"),
}


def mix(hex_a, hex_b, t):
    """Blend hex_a toward hex_b by t (0..1)."""
    a = [int(hex_a[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(hex_b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))
