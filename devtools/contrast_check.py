"""Contrast check of the theme tokens (design-system/tokens.md "Contrast Requirements").

Reads frontend/src/styles/tokens.css and evaluates WCAG contrast ratios for the required pairs in the
dark (default) and light themes. Exit code 1 when a pair fails. Development tool.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

CSS = Path(__file__).resolve().parents[1] / "frontend" / "src" / "styles" / "tokens.css"

PAIRS = [  # (foreground, background, minimum ratio, description)
    ("text", "background", 4.5, "text on background"),
    ("text", "surface", 4.5, "text on surface"),
    ("text", "surface-raised", 4.5, "text on raised surface"),
    ("text-muted", "background", 3.0, "muted text on background"),
    ("text-muted", "surface", 3.0, "muted text on surface"),
    ("on-primary", "primary", 4.5, "button text on primary"),
    ("error", "background", 4.5, "error text on background"),
    ("error", "surface", 4.5, "error text on surface"),
    ("success", "surface", 4.5, "success text on surface"),
    ("primary", "background", 3.0, "primary (UI component) on background"),
    ("accent", "background", 3.0, "accent (UI component) on background"),
    ("secondary", "surface", 4.5, "link colour on surface"),
]


def parse_blocks(css: str) -> dict[str, dict[str, str]]:
    blocks: dict[str, dict[str, str]] = {}
    for selector, body in re.findall(r"(:root(?:\[data-theme=\"light\"\])?)\s*\{(.*?)\n\}", css, re.S):
        values = dict(re.findall(r"--color-([a-z-]+):\s*(#[0-9a-fA-F]{6})", body))
        key = "light" if "light" in selector else "dark"
        if values and key not in blocks:  # ignore the reduced-motion block that also starts with :root
            blocks[key] = values
    return blocks


def luminance(hex_color: str) -> float:
    channels = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def ratio(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def main() -> int:
    themes = parse_blocks(CSS.read_text(encoding="utf-8"))
    dark = themes["dark"]
    light = {**dark, **themes["light"]}
    failed = 0
    for name, tokens in (("dark", dark), ("light", light)):
        print(f"[{name}]")
        for fg, bg, minimum, label in PAIRS:
            value = ratio(tokens[fg], tokens[bg])
            status = "ok  " if value >= minimum else "FAIL"
            failed += value < minimum
            print(f"  {status} {value:5.2f}:1 (min {minimum}) {label}  {tokens[fg]} on {tokens[bg]}")
    print(f"{failed} pair(s) below the minimum")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
