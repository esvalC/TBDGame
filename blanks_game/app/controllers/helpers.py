"""Shared controller helpers: session <-> player identity, store access."""
from __future__ import annotations

from functools import wraps

from flask import current_app, jsonify, session

from ..models import Game, GameError, GameStore


def store() -> GameStore:
    return current_app.extensions["game_store"]


def my_player_id(code: str) -> str | None:
    """Which player this browser session is, in game ``code`` (or None)."""
    return session.get("players", {}).get(code.upper())


def remember_player(code: str, player_id: str) -> None:
    players = dict(session.get("players", {}))
    players[code.upper()] = player_id
    session["players"] = players
    session.permanent = True


def forget_player(code: str) -> None:
    players = dict(session.get("players", {}))
    players.pop(code.upper(), None)
    session["players"] = players


def load_game_and_me(code: str) -> tuple[Game, str | None]:
    game = store().get(code)
    pid = my_player_id(code)
    if pid and pid not in game.players:
        pid = None
    return game, pid


def api_errors(view):
    """Turn GameError into a 400 JSON response instead of a stack trace."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        try:
            return view(*args, **kwargs)
        except GameError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

    return wrapper
