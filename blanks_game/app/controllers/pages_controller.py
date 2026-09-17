"""HTML page routes: home, create/join, the game table, the packs page."""
from __future__ import annotations

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for

from ..models import GameError
from .helpers import forget_player, load_game_and_me, remember_player, store

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/")
def index():
    packs = current_app.extensions["packs"]
    return render_template(
        "index.html",
        packs=packs,
        default_hand=current_app.config["DEFAULT_HAND_SIZE"],
        default_points=current_app.config["DEFAULT_POINTS_TO_WIN"],
        prefill_code=request.args.get("code", ""),
    )


@pages_bp.post("/create")
def create_game():
    name = request.form.get("name", "")
    try:
        hand_size = max(4, min(15, int(request.form.get("hand_size", current_app.config["DEFAULT_HAND_SIZE"]))))
        points = max(1, min(30, int(request.form.get("points_to_win", current_app.config["DEFAULT_POINTS_TO_WIN"]))))
        bot_count = max(0, min(11, int(request.form.get("bot_count", 0) or 0)))
    except ValueError:
        flash("Hand size, points, and bots must be numbers.")
        return redirect(url_for("pages.index"))
    pack_names = request.form.getlist("packs") or None

    with store().lock:
        game = store().create(hand_size=hand_size, points_to_win=points, pack_names=pack_names)
        try:
            player = game.add_player(name)
            for _ in range(bot_count):
                game.add_bot()
        except GameError as exc:
            flash(str(exc))
            return redirect(url_for("pages.index"))
    remember_player(game.code, player.id)
    return redirect(url_for("pages.game", code=game.code))


@pages_bp.post("/join")
def join_game():
    code = request.form.get("code", "").upper().strip()
    name = request.form.get("name", "")
    try:
        with store().lock:
            game = store().get(code)
            player = game.add_player(name)
    except GameError as exc:
        flash(str(exc))
        return redirect(url_for("pages.index", code=code))
    remember_player(game.code, player.id)
    return redirect(url_for("pages.game", code=game.code))


@pages_bp.route("/game/<code>")
def game(code: str):
    try:
        game_obj, pid = load_game_and_me(code)
    except GameError:
        flash("That game doesn't exist (or it expired).")
        return redirect(url_for("pages.index"))
    if pid is None:
        # Not seated yet: send them to the join form with the code filled in.
        return redirect(url_for("pages.index", code=game_obj.code))
    return render_template("game.html", code=game_obj.code, player_id=pid)


@pages_bp.post("/game/<code>/leave")
def leave_game(code: str):
    try:
        game_obj, pid = load_game_and_me(code)
        if pid:
            with store().lock:
                game_obj.remove_player(pid)
    except GameError:
        pass
    forget_player(code)
    return redirect(url_for("pages.index"))


@pages_bp.route("/packs")
def packs():
    packs = current_app.extensions["packs"]
    return render_template("packs.html", packs=packs, packs_dir=current_app.config["PACKS_DIR"])
