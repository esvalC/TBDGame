"""Flask application factory.

Layout (MVC):
    app/models/       - pure Python game logic (no Flask imports)
    app/controllers/  - Flask blueprints: routes, sessions, request validation
    app/views/        - Jinja2 templates
    app/static/       - CSS, JS, card images
    data/packs/       - card content (JSON)  <-- add your cards here
"""
from __future__ import annotations

import os
from pathlib import Path

from flask import Flask

from .models import GameStore, load_packs


def create_app(config_object: str | object = "config.Config") -> Flask:
    app = Flask(
        __name__,
        template_folder="views",
        static_folder="static",
    )
    app.config.from_object(config_object)

    packs = load_packs(Path(app.config["PACKS_DIR"]))
    app.extensions["packs"] = packs
    store = GameStore(packs, ttl_seconds=app.config["GAME_TTL_SECONDS"])
    app.extensions["game_store"] = store

    # Only start the bot loop once: if Flask's debug reloader is running,
    # it spawns a watcher process too, and we don't want two loops ticking
    # the same in-memory games.
    if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        store.start_bot_loop()

    from .controllers import api_bp, pages_bp

    app.register_blueprint(pages_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    @app.context_processor
    def inject_globals():
        return {"GAME_TITLE": app.config["GAME_TITLE"], "POLL_INTERVAL_MS": app.config["POLL_INTERVAL_MS"]}

    return app
