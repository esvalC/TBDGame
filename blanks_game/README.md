# Blanks — a fill-in-the-blank party game (Flask, MVC)

One player is the Judge and reads a black prompt card. Everyone else plays a white
answer card from their hand. The Judge picks the funniest. First to N points wins.
Everyone plays from their own phone or laptop on the same Wi-Fi.

## Run it

```bash
pip install -r requirements.txt
python run.py            # http://localhost:5000  (this machine only)
python run.py --lan      # also reachable from phones on your Wi-Fi at http://<your-ip>:5000
```

Create a game, share the 4-letter code, friends join from the home page. Needs 3+ players.

Tests: `pytest`

## >>> WHERE TO ADD YOUR CARDS <<<

**`data/packs/`** — every `.json` file in this folder is loaded automatically when the
server starts. Files whose name starts with `_` are ignored.

1. Copy `data/packs/_template.json` to something like `data/packs/calvin.json`.
2. Fill in `black` (prompts) and `white` (answers).
3. Run `python scripts/validate_packs.py` to catch typos.
4. Restart the server. Your pack shows up as a checkbox on the home page and on `/packs`.
5. Delete `data/packs/starter_placeholders.json` once you have your own cards — it only
   exists so the game runs out of the box.

Format:

```json
{
  "name": "Calvin's Pack",
  "black": [
    "____ is why I can't go back to that restaurant.",
    { "text": "First ____, then ____.", "pick": 2 },
    "What did I find under the couch?"
  ],
  "white": [
    "A suspiciously warm chair",
    "Forty raccoons in a trench coat"
  ]
}
```

- A blank is four underscores: `____`. The number of blanks sets how many white cards
  players must play, so `pick` is optional — only use it on cards with no blanks that
  want more than one answer.
- Black cards with no blank (questions) get the answer appended after them.
- Keep cards under ~100 characters so they fit on the card face.
- You can have as many pack files as you like; players tick which packs to use when
  creating a game.

## Project layout (MVC)

```
blanks_game/
├── run.py                      # entry point
├── config.py                   # settings (hand size, points to win, packs folder…)
├── requirements.txt
├── data/
│   └── packs/                  # <-- CARD CONTENT (JSON). Add files here.
│       ├── _template.json      #     copy me
│       └── starter_placeholders.json   # bland stand-ins; delete when you have your own
├── scripts/
│   └── validate_packs.py       # checks your JSON packs
├── tests/
│   └── test_game.py            # rules + HTTP tests
└── app/
    ├── __init__.py             # Flask app factory (wires M, V and C together)
    ├── models/                 # M — pure Python, no Flask
    │   ├── card.py             #   BlackCard / WhiteCard, blank rendering
    │   ├── deck.py             #   Pack loading, shuffled draw/discard piles
    │   ├── player.py           #   Player, hand, score
    │   ├── game.py             #   Rules engine / state machine (lobby → submitting → judging → round_over → game_over)
    │   └── store.py            #   In-memory registry of live games by code
    ├── controllers/            # C — Flask blueprints
    │   ├── pages_controller.py #   HTML routes: /, /create, /join, /game/<code>, /packs
    │   ├── api_controller.py   #   JSON API: /api/game/<code>/{state,start,submit,judge,next,restart}
    │   └── helpers.py          #   session ↔ player identity, error handling
    ├── views/                  # V — Jinja2 templates
    │   ├── base.html
    │   ├── index.html          #   create / join
    │   ├── game.html           #   the table (rendered live by static/js/game.js)
    │   └── packs.html          #   lists loaded packs + how to add more
    └── static/
        ├── css/style.css
        ├── js/game.js          #   polls the API and draws the table
        └── img/                #   card art (SVG)
            ├── black_card.svg      # black card face (text is overlaid by CSS)
            ├── white_card.svg      # white card face
            ├── card_back_black.svg # face-down black card
            ├── card_back_white.svg # face-down white card
            ├── logo.svg / favicon.svg / gavel.svg / hero_cards.svg
```

## Changing the look of the cards

The card faces are plain SVGs in `app/static/img/`. Edit them in any vector editor (or by
hand) and the text overlay in `static/css/style.css` (`.card`, `.card.black`, `.card.white`)
adjusts to it. Rename the game by setting `GAME_TITLE=...` in your environment (the word
on the card art itself lives in the SVG files).

## Notes

- Game state is in memory; it's reset when the server restarts (fine for a party, not
  for the public internet). `models/store.py` is the single place to swap in Redis/DB.
- Set `SECRET_KEY` before exposing it beyond your Wi-Fi.
