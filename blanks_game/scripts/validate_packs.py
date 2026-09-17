#!/usr/bin/env python3
"""Check every card pack in data/packs/ for problems.

Usage:  python scripts/validate_packs.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.models import Pack, PackError  # noqa: E402

PACKS_DIR = ROOT / "data" / "packs"
MAX_LEN = 110


def main() -> int:
    problems = 0
    files = sorted(PACKS_DIR.glob("*.json"))
    if not files:
        print(f"No packs found in {PACKS_DIR}")
        return 1
    total_black = total_white = 0
    for path in files:
        if path.name.startswith("_"):
            print(f"-- {path.name}: skipped (starts with '_')")
            continue
        try:
            pack = Pack.load(path)
        except PackError as exc:
            print(f"XX {exc}")
            problems += 1
            continue
        warnings = []
        for c in pack.black:
            if c.blanks > 0 and c.pick != c.blanks:
                warnings.append(f"black '{c.text[:40]}…' has {c.blanks} blanks but pick={c.pick}")
            if len(c.text) > MAX_LEN:
                warnings.append(f"black card is long ({len(c.text)} chars): {c.text[:40]}…")
        for c in pack.white:
            if len(c.text) > MAX_LEN:
                warnings.append(f"white card is long ({len(c.text)} chars): {c.text[:40]}…")
        seen = set()
        for c in pack.white:
            key = c.text.strip().lower()
            if key in seen:
                warnings.append(f"duplicate white card: {c.text}")
            seen.add(key)
        total_black += len(pack.black)
        total_white += len(pack.white)
        print(f"OK {path.name}: '{pack.name}' — {len(pack.black)} black, {len(pack.white)} white")
        for w in warnings:
            print(f"   warning: {w}")
    print(f"\nTotal: {total_black} black, {total_white} white across all packs.")
    if total_white < 40:
        print("Tip: you want at least ~40 white cards for a 3-player game with 10-card hands.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
