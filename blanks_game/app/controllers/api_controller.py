"""JSON API used by static/js/game.js (polling + actions)."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..models import GameError
from .helpers import api_errors, load_game_and_me, store

api_bp = Blueprint("api", __name__)


def _require_me(code: str):
    game, pid = load_game_and_me(code)
    if pid is None:
        raise GameError("You're not seated at this game.")
    return game, pid


@api_bp.get("/game/<code>/state")
@api_errors
def state(code: str):
    game, pid = load_game_and_me(code)
    with store().lock:
        return jsonify({"ok": True, "state": game.state_for(pid)})


@api_bp.post("/game/<code>/start")
@api_errors
def start(code: str):
    game, pid = _require_me(code)
    with store().lock:
        game.start(pid)
        return jsonify({"ok": True, "state": game.state_for(pid)})


@api_bp.post("/game/<code>/add_bot")
@api_errors
def add_bot(code: str):
    """Solo testing: let the host fill empty seats with CPU players instead
    of opening more browser tabs. Only makes sense before the game starts."""
    game, pid = _require_me(code)
    with store().lock:
        if pid != game.host_id:
            raise GameError("Only the host can add bots.")
        if game.phase != "lobby":
            raise GameError("Bots can only be added before the game starts.")
        game.add_bot()
        return jsonify({"ok": True, "state": game.state_for(pid)})


@api_bp.post("/game/<code>/submit")
@api_errors
def submit(code: str):
    game, pid = _require_me(code)
    payload = request.get_json(silent=True) or {}
    card_ids = payload.get("card_ids")
    if not isinstance(card_ids, list) or not all(isinstance(c, str) for c in card_ids):
        raise GameError("Send card_ids as a list of card ids.")
    with store().lock:
        game.submit(pid, card_ids)
        return jsonify({"ok": True, "state": game.state_for(pid)})


@api_bp.post("/game/<code>/judge")
@api_errors
def judge(code: str):
    game, pid = _require_me(code)
    payload = request.get_json(silent=True) or {}
    winner = payload.get("submission_id")
    if not isinstance(winner, str):
        raise GameError("Send submission_id.")
    with store().lock:
        game.judge_pick(pid, winner)
        return jsonify({"ok": True, "state": game.state_for(pid)})


@api_bp.post("/game/<code>/next")
@api_errors
def next_round(code: str):
    game, pid = _require_me(code)
    with store().lock:
        game.next_round(pid)
        return jsonify({"ok": True, "state": game.state_for(pid)})


@api_bp.post("/game/<code>/restart")
@api_errors
def restart(code: str):
    game, pid = _require_me(code)
    with store().lock:
        game.restart(pid)
        return jsonify({"ok": True, "state": game.state_for(pid)})
