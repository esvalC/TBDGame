"""In-memory registry of running games.

Swap this for Redis / a database if you ever deploy across several server
processes; the rest of the app only talks to ``GameStore``.
"""
from __future__ import annotations

import random
import string
import threading
import time

from .deck import Pack
from .game import Game, GameError

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no confusable 0/O/1/I


class GameStore:
    def __init__(self, packs: list[Pack], ttl_seconds: int = 6 * 3600):
        self.packs = packs
        self.ttl = ttl_seconds
        self._games: dict[str, Game] = {}
        self._lock = threading.RLock()

    def _new_code(self) -> str:
        while True:
            code = "".join(random.choices(CODE_ALPHABET, k=4))
            if code not in self._games:
                return code

    def create(self, hand_size: int = 10, points_to_win: int = 5, pack_names: list[str] | None = None) -> Game:
        with self._lock:
            self._sweep()
            packs = self.packs
            if pack_names:
                packs = [p for p in self.packs if p.name in pack_names] or self.packs
            game = Game(code=self._new_code(), packs=packs, hand_size=hand_size, points_to_win=points_to_win)
            self._games[game.code] = game
            return game

    def get(self, code: str) -> Game:
        with self._lock:
            game = self._games.get(code.upper().strip())
            if game is None:
                raise GameError("No game with that code.")
            return game

    def all(self) -> list[Game]:
        with self._lock:
            return list(self._games.values())

    def _sweep(self) -> None:
        cutoff = time.time() - self.ttl
        for code in [c for c, g in self._games.items() if g.last_activity < cutoff]:
            del self._games[code]

    @property
    def lock(self) -> threading.RLock:
        return self._lock
