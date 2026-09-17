"""Game model: the rules engine / state machine.

Phases
------
lobby       -> waiting for players; host starts the game
submitting  -> everyone except the Judge plays white card(s)
judging     -> submissions are revealed (anonymously, shuffled); Judge picks a winner
round_over  -> winner announced; anyone can advance to the next round
game_over   -> someone reached the points-to-win target

The model knows nothing about HTTP. Controllers call its methods and
serialise ``state_for(player_id)`` to the views.
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field

from .card import BlackCard, WhiteCard
from .deck import Deck, Pack
from .player import Player


class GameError(Exception):
    """A rules violation that should be shown to the user."""


@dataclass
class Submission:
    player_id: str
    cards: list[WhiteCard]


@dataclass
class Game:
    code: str
    packs: list[Pack]
    hand_size: int = 10
    points_to_win: int = 5
    min_players: int = 3
    rng: random.Random = field(default_factory=random.Random)

    phase: str = "lobby"
    players: dict[str, Player] = field(default_factory=dict)   # insertion order = seating order
    host_id: str | None = None
    round_number: int = 0
    judge_id: str | None = None
    black_card: BlackCard | None = None
    submissions: dict[str, Submission] = field(default_factory=dict)
    reveal_order: list[str] = field(default_factory=list)        # player ids, shuffled for judging
    round_winner_id: str | None = None
    game_winner_id: str | None = None
    last_activity: float = field(default_factory=time.time)
    deck: Deck | None = None
    history: list[dict] = field(default_factory=list)

    # ------------------------------------------------------------------ helpers
    def touch(self) -> None:
        self.last_activity = time.time()

    @property
    def seating(self) -> list[Player]:
        return list(self.players.values())

    @property
    def judge(self) -> Player | None:
        return self.players.get(self.judge_id) if self.judge_id else None

    def player(self, player_id: str) -> Player:
        try:
            return self.players[player_id]
        except KeyError:
            raise GameError("You're not in this game.") from None

    # ------------------------------------------------------------------ lobby
    def add_player(self, name: str) -> Player:
        name = name.strip()
        if not name:
            raise GameError("Pick a name.")
        if len(name) > 20:
            raise GameError("Name must be 20 characters or fewer.")
        if any(p.name.lower() == name.lower() for p in self.players.values()):
            raise GameError("That name is taken in this game.")
        if len(self.players) >= 12:
            raise GameError("This game is full (12 players).")
        player = Player(name=name)
        self.players[player.id] = player
        if self.host_id is None:
            self.host_id = player.id
        # Late joiners during a running game get a hand right away.
        if self.phase not in ("lobby", "game_over") and self.deck is not None:
            player.hand = self.deck.draw_white(self.hand_size)
        self.touch()
        return player

    def remove_player(self, player_id: str) -> None:
        player = self.players.pop(player_id, None)
        if not player:
            return
        if self.deck is not None:
            self.deck.discard_white(player.hand)
        self.submissions.pop(player_id, None)
        if self.host_id == player_id:
            self.host_id = next(iter(self.players), None)
        if self.judge_id == player_id and self.phase in ("submitting", "judging"):
            # Judge left: scrap the round and start a fresh one.
            self._abort_round()
        elif self.phase == "submitting":
            self._maybe_advance_to_judging()
        self.touch()

    def start(self, player_id: str) -> None:
        if self.phase != "lobby":
            raise GameError("The game has already started.")
        if player_id != self.host_id:
            raise GameError("Only the host can start the game.")
        if len(self.players) < self.min_players:
            raise GameError(f"You need at least {self.min_players} players.")
        total_white = sum(len(p.white) for p in self.packs)
        if total_white < self.hand_size * len(self.players) + 5:
            raise GameError(
                f"Not enough white cards ({total_white}) for {len(self.players)} players. "
                "Add more cards to data/packs/."
            )
        if not any(p.black for p in self.packs):
            raise GameError("There are no black cards. Add some to data/packs/.")

        self.deck = Deck(self.packs, rng=self.rng)
        for p in self.players.values():
            p.score = 0
            p.hand = self.deck.draw_white(self.hand_size)
        self.round_number = 0
        self.judge_id = None
        self.game_winner_id = None
        self.history = []
        self._begin_round()

    # ------------------------------------------------------------------ rounds
    def _next_judge_id(self) -> str:
        ids = list(self.players)
        if self.judge_id not in ids:
            return ids[0]
        return ids[(ids.index(self.judge_id) + 1) % len(ids)]

    def _begin_round(self) -> None:
        assert self.deck is not None
        self.round_number += 1
        self.judge_id = self._next_judge_id()
        self.black_card = self.deck.draw_black()
        self.submissions = {}
        self.reveal_order = []
        self.round_winner_id = None
        self.phase = "submitting"
        self.touch()

    def _abort_round(self) -> None:
        assert self.deck is not None
        for sub in self.submissions.values():
            self.deck.discard_white(sub.cards)
        if self.black_card:
            self.deck.discard_black(self.black_card)
        if len(self.players) < self.min_players:
            self.phase = "lobby"
            return
        self._begin_round()

    def submit(self, player_id: str, card_ids: list[str]) -> None:
        if self.phase != "submitting":
            raise GameError("It's not time to play cards.")
        player = self.player(player_id)
        if player_id == self.judge_id:
            raise GameError("The Judge doesn't play cards this round.")
        if player_id in self.submissions:
            raise GameError("You've already played this round.")
        assert self.black_card is not None
        if len(card_ids) != self.black_card.pick:
            raise GameError(f"Pick exactly {self.black_card.pick} card(s).")
        cards = player.take_from_hand(card_ids)
        self.submissions[player_id] = Submission(player_id=player_id, cards=cards)
        self.touch()
        self._maybe_advance_to_judging()

    def _maybe_advance_to_judging(self) -> None:
        expected = [pid for pid in self.players if pid != self.judge_id]
        if expected and all(pid in self.submissions for pid in expected):
            self.reveal_order = list(self.submissions)
            self.rng.shuffle(self.reveal_order)
            self.phase = "judging"
            self.touch()

    def judge_pick(self, judge_player_id: str, winner_player_id: str) -> None:
        if self.phase != "judging":
            raise GameError("It's not time to judge yet.")
        if judge_player_id != self.judge_id:
            raise GameError("Only the Judge can pick a winner.")
        if winner_player_id not in self.submissions:
            raise GameError("That's not one of the submissions.")
        assert self.deck is not None and self.black_card is not None
        winner = self.player(winner_player_id)
        winner.score += 1
        self.round_winner_id = winner_player_id
        self.history.append({
            "round": self.round_number,
            "black": self.black_card.text,
            "winner": winner.name,
            "answer": self.black_card.render([c.text for c in self.submissions[winner_player_id].cards]),
        })
        if winner.score >= self.points_to_win:
            self.game_winner_id = winner_player_id
            self.phase = "game_over"
        else:
            self.phase = "round_over"
        self.touch()

    def next_round(self, player_id: str) -> None:
        if self.phase != "round_over":
            raise GameError("The round isn't over yet.")
        self.player(player_id)  # must be a participant
        assert self.deck is not None and self.black_card is not None
        # clean up the table
        for sub in self.submissions.values():
            self.deck.discard_white(sub.cards)
        self.deck.discard_black(self.black_card)
        # refill hands
        for p in self.players.values():
            need = self.hand_size - len(p.hand)
            if need > 0:
                p.hand.extend(self.deck.draw_white(need))
        self._begin_round()

    def restart(self, player_id: str) -> None:
        if self.phase != "game_over":
            raise GameError("The game isn't over.")
        if player_id != self.host_id:
            raise GameError("Only the host can start a new game.")
        self.phase = "lobby"
        self.start(player_id)

    # ------------------------------------------------------------------ views
    def state_for(self, player_id: str | None) -> dict:
        """Serialise the game as seen by one player (hides other hands & authorship)."""
        me = self.players.get(player_id) if player_id else None
        black = self.black_card.to_dict() if self.black_card else None

        submissions_view: list[dict] = []
        if self.phase in ("judging", "round_over", "game_over") and self.black_card:
            for pid in self.reveal_order:
                sub = self.submissions.get(pid)
                if not sub:
                    continue
                entry = {
                    "id": pid,  # the judge posts this back; players can't map it to a name until reveal
                    "cards": [c.to_dict() for c in sub.cards],
                    "rendered": self.black_card.render([c.text for c in sub.cards]),
                }
                if self.phase in ("round_over", "game_over"):
                    entry["player_name"] = self.players[pid].name if pid in self.players else "(left)"
                    entry["winner"] = pid == self.round_winner_id
                submissions_view.append(entry)

        return {
            "code": self.code,
            "phase": self.phase,
            "round": self.round_number,
            "points_to_win": self.points_to_win,
            "hand_size": self.hand_size,
            "min_players": self.min_players,
            "host_id": self.host_id,
            "judge_id": self.judge_id,
            "judge_name": self.judge.name if self.judge else None,
            "black_card": black,
            "players": [
                {**p.to_public_dict(), "submitted": p.id in self.submissions, "is_judge": p.id == self.judge_id}
                for p in self.players.values()
            ],
            "submissions": submissions_view,
            "submitted_count": len(self.submissions),
            "expected_count": max(0, len(self.players) - (1 if self.judge_id else 0)),
            "round_winner_id": self.round_winner_id,
            "round_winner_name": self.players[self.round_winner_id].name
            if self.round_winner_id in self.players else None,
            "game_winner_name": self.players[self.game_winner_id].name
            if self.game_winner_id in self.players else None,
            "history": self.history[-10:],
            "me": {
                "id": me.id,
                "name": me.name,
                "score": me.score,
                "is_host": me.id == self.host_id,
                "is_judge": me.id == self.judge_id,
                "has_submitted": me.id in self.submissions,
                "hand": [c.to_dict() for c in me.hand],
            } if me else None,
            "deck": {
                "white_remaining": self.deck.white_remaining if self.deck else 0,
                "black_remaining": self.deck.black_remaining if self.deck else 0,
            },
            "packs": [p.name for p in self.packs],
        }
