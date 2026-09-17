"""Card models.

A BlackCard is a prompt with one or more blanks ("____").
A WhiteCard is an answer that gets played into a blank.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

BLANK = "____"


def _new_id() -> str:
    return uuid.uuid4().hex[:10]


@dataclass(frozen=True)
class WhiteCard:
    text: str
    pack: str = "unknown"
    id: str = field(default_factory=_new_id)

    def to_dict(self) -> dict:
        return {"id": self.id, "text": self.text, "pack": self.pack}


@dataclass(frozen=True)
class BlackCard:
    text: str
    pack: str = "unknown"
    pick: int = 1
    id: str = field(default_factory=_new_id)

    @classmethod
    def from_text(cls, text: str, pack: str = "unknown", pick: int | None = None) -> "BlackCard":
        """Build a black card, inferring `pick` from the number of blanks if not given."""
        blanks = text.count(BLANK)
        if pick is None:
            pick = max(1, blanks)
        return cls(text=text, pack=pack, pick=pick)

    @property
    def blanks(self) -> int:
        return self.text.count(BLANK)

    def render(self, answers: list[str]) -> str:
        """Fill the blanks with the given answers, in order.

        If the card has no blanks (e.g. a question), the answers are appended.
        """
        text = self.text
        remaining = list(answers)
        while BLANK in text and remaining:
            text = text.replace(BLANK, remaining.pop(0), 1)
        if remaining:
            text = text.rstrip() + " " + " / ".join(remaining)
        return text

    def to_dict(self) -> dict:
        return {"id": self.id, "text": self.text, "pack": self.pack, "pick": self.pick}
