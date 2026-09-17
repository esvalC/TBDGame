"""Player model."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from .card import WhiteCard


@dataclass
class Player:
    name: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    hand: list[WhiteCard] = field(default_factory=list)
    score: int = 0
    connected: bool = True
    is_bot: bool = False

    def take_from_hand(self, card_ids: list[str]) -> list[WhiteCard]:
        """Remove and return the given cards from the hand, in the order requested."""
        by_id = {c.id: c for c in self.hand}
        missing = [cid for cid in card_ids if cid not in by_id]
        if missing:
            raise ValueError("You don't hold those cards.")
        if len(set(card_ids)) != len(card_ids):
            raise ValueError("You can't play the same card twice.")
        picked = [by_id[cid] for cid in card_ids]
        self.hand = [c for c in self.hand if c.id not in set(card_ids)]
        return picked

    def to_public_dict(self) -> dict:
        """What other players are allowed to see."""
        return {"id": self.id, "name": self.name, "score": self.score,
                "connected": self.connected, "is_bot": self.is_bot}
