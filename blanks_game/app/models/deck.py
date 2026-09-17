"""Deck model: loads card packs from JSON and deals cards.

Card packs live in ``data/packs/*.json``. Every ``.json`` file in that folder
that does NOT start with an underscore is loaded automatically.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from .card import BlackCard, WhiteCard


class PackError(ValueError):
    """Raised when a pack file is malformed."""


class Pack:
    """One JSON file of cards."""

    def __init__(self, name: str, black: list[BlackCard], white: list[WhiteCard], path: Path | None = None):
        self.name = name
        self.black = black
        self.white = white
        self.path = path

    @classmethod
    def load(cls, path: Path) -> "Pack":
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise PackError(f"{path.name}: invalid JSON ({exc})") from exc

        name = raw.get("name") or path.stem
        black: list[BlackCard] = []
        white: list[WhiteCard] = []

        for i, entry in enumerate(raw.get("black", [])):
            if isinstance(entry, str):
                black.append(BlackCard.from_text(entry, pack=name))
            elif isinstance(entry, dict) and "text" in entry:
                black.append(BlackCard.from_text(entry["text"], pack=name, pick=entry.get("pick")))
            else:
                raise PackError(f"{path.name}: black card #{i + 1} must be a string or {{'text': ..., 'pick': ...}}")

        for i, entry in enumerate(raw.get("white", [])):
            if isinstance(entry, str):
                white.append(WhiteCard(text=entry, pack=name))
            elif isinstance(entry, dict) and "text" in entry:
                white.append(WhiteCard(text=entry["text"], pack=name))
            else:
                raise PackError(f"{path.name}: white card #{i + 1} must be a string or {{'text': ...}}")

        return cls(name=name, black=black, white=white, path=path)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "file": self.path.name if self.path else None,
            "black_count": len(self.black),
            "white_count": len(self.white),
        }


def load_packs(packs_dir: Path | str) -> list[Pack]:
    """Load every pack in the directory (skips files beginning with '_')."""
    packs_dir = Path(packs_dir)
    packs = []
    for path in sorted(packs_dir.glob("*.json")):
        if path.name.startswith("_"):
            continue
        packs.append(Pack.load(path))
    return packs


class Deck:
    """A shuffled draw pile of black and white cards for one game.

    When a pile runs out, the discard pile is reshuffled into it.
    """

    def __init__(self, packs: list[Pack], rng: random.Random | None = None):
        self.rng = rng or random.Random()
        self.black_draw: list[BlackCard] = [c for p in packs for c in p.black]
        self.white_draw: list[WhiteCard] = [c for p in packs for c in p.white]
        self.black_discard: list[BlackCard] = []
        self.white_discard: list[WhiteCard] = []
        self.rng.shuffle(self.black_draw)
        self.rng.shuffle(self.white_draw)

    # -- black -------------------------------------------------------------
    def draw_black(self) -> BlackCard:
        if not self.black_draw:
            if not self.black_discard:
                raise RuntimeError("No black cards available. Add some to data/packs/.")
            self.black_draw, self.black_discard = self.black_discard, []
            self.rng.shuffle(self.black_draw)
        return self.black_draw.pop()

    def discard_black(self, card: BlackCard) -> None:
        self.black_discard.append(card)

    # -- white -------------------------------------------------------------
    def draw_white(self, n: int = 1) -> list[WhiteCard]:
        drawn = []
        for _ in range(n):
            if not self.white_draw:
                if not self.white_discard:
                    raise RuntimeError("No white cards available. Add some to data/packs/.")
                self.white_draw, self.white_discard = self.white_discard, []
                self.rng.shuffle(self.white_draw)
            drawn.append(self.white_draw.pop())
        return drawn

    def discard_white(self, cards: list[WhiteCard]) -> None:
        self.white_discard.extend(cards)

    @property
    def white_remaining(self) -> int:
        return len(self.white_draw)

    @property
    def black_remaining(self) -> int:
        return len(self.black_draw)
