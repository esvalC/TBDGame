"""Model + API tests. Run with:  pytest"""
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from app.models import BlackCard, Game, GameError, Pack, WhiteCard  # noqa: E402


def make_pack(n_black=5, n_white=60):
    black = [BlackCard.from_text(f"Prompt {i} ____.", pack="t") for i in range(n_black)]
    black.append(BlackCard.from_text("Two ____ and ____.", pack="t"))
    white = [WhiteCard(text=f"Answer {i}", pack="t") for i in range(n_white)]
    return Pack("t", black, white)


def make_game(n_players=3):
    g = Game(code="TEST", packs=[make_pack()], hand_size=5, points_to_win=2, rng=random.Random(1))
    players = [g.add_player(f"P{i}") for i in range(n_players)]
    g.start(players[0].id)
    return g, players


# ----------------------------------------------------------------- models
def test_black_card_pick_inferred():
    assert BlackCard.from_text("a ____ b").pick == 1
    assert BlackCard.from_text("____ and ____").pick == 2
    assert BlackCard.from_text("Question?").pick == 1
    assert BlackCard.from_text("Question?", pick=2).pick == 2


def test_render_fills_blanks_and_appends():
    c = BlackCard.from_text("I like ____.")
    assert c.render(["cats"]) == "I like cats."
    q = BlackCard.from_text("Why?")
    assert q.render(["Because"]) == "Why? Because"


def test_needs_min_players():
    g = Game(code="X", packs=[make_pack()])
    p = g.add_player("A")
    g.add_player("B")
    with pytest.raises(GameError):
        g.start(p.id)


def test_only_host_starts():
    g = Game(code="X", packs=[make_pack()])
    g.add_player("A")
    b = g.add_player("B")
    g.add_player("C")
    with pytest.raises(GameError):
        g.start(b.id)


def test_full_round_flow():
    g, players = make_game()
    assert g.phase == "submitting"
    judge = g.judge
    others = [p for p in players if p.id != judge.id]
    for p in others:
        assert len(p.hand) == 5
    pick = g.black_card.pick

    with pytest.raises(GameError):
        g.submit(judge.id, [judge.hand[0].id])  # judge can't play

    for p in others:
        g.submit(p.id, [c.id for c in p.hand[:pick]])
        assert len(p.hand) == 5 - pick
    assert g.phase == "judging"

    with pytest.raises(GameError):
        g.judge_pick(others[0].id, others[0].id)  # non-judge can't judge

    winner = others[0]
    g.judge_pick(judge.id, winner.id)
    assert winner.score == 1
    assert g.phase == "round_over"

    g.next_round(players[0].id)
    assert g.phase == "submitting"
    assert g.round_number == 2
    assert g.judge_id != judge.id
    for p in players:
        assert len(p.hand) == 5


def test_game_over_at_target():
    g, players = make_game()
    for _ in range(2):
        judge = g.judge
        others = [p for p in players if p.id != judge.id]
        pick = g.black_card.pick
        for p in others:
            g.submit(p.id, [c.id for c in p.hand[:pick]])
        # always award the first non-judge whose name is P1 if possible, else first other
        target = next((p for p in others if p.name == "P1"), others[0])
        g.judge_pick(judge.id, target.id)
        if g.phase == "round_over":
            g.next_round(players[0].id)
    assert g.phase in ("game_over", "submitting")


def test_state_hides_other_hands():
    g, players = make_game()
    s = g.state_for(players[0].id)
    assert s["me"]["name"] == "P0"
    assert "hand" not in s["players"][1]


def test_judge_leaving_restarts_round():
    g, players = make_game(n_players=4)
    old_round = g.round_number
    g.remove_player(g.judge_id)
    assert g.round_number == old_round + 1
    assert g.phase == "submitting"


def test_judge_leaving_with_too_few_players_returns_to_lobby():
    g, players = make_game(n_players=3)
    g.remove_player(g.judge_id)
    assert g.phase == "lobby"


# ----------------------------------------------------------------- HTTP
@pytest.fixture
def app():
    return create_app("config.TestConfig")


def test_http_create_join_and_play(app):
    host = app.test_client()
    r = host.post("/create", data={"name": "Host", "hand_size": "5", "points_to_win": "1"}, follow_redirects=False)
    assert r.status_code == 302
    code = r.headers["Location"].rsplit("/", 1)[-1]

    guests = []
    for name in ("Amy", "Bob"):
        c = app.test_client()
        r = c.post("/join", data={"code": code, "name": name})
        assert r.headers["Location"].endswith(f"/game/{code}")
        guests.append(c)

    assert host.get(f"/game/{code}").status_code == 200
    r = host.post(f"/api/game/{code}/start")
    assert r.status_code == 200, r.get_json()
    state = r.get_json()["state"]
    assert state["phase"] == "submitting"

    clients = {"Host": host, "Amy": guests[0], "Bob": guests[1]}
    judge_name = state["judge_name"]
    for name, client in clients.items():
        if name == judge_name:
            continue
        s = client.get(f"/api/game/{code}/state").get_json()["state"]
        ids = [c["id"] for c in s["me"]["hand"][: s["black_card"]["pick"]]]
        r = client.post(f"/api/game/{code}/submit", json={"card_ids": ids})
        assert r.status_code == 200, r.get_json()

    judge_client = clients[judge_name]
    s = judge_client.get(f"/api/game/{code}/state").get_json()["state"]
    assert s["phase"] == "judging"
    assert all("player_name" not in sub for sub in s["submissions"])  # anonymous while judging
    r = judge_client.post(f"/api/game/{code}/judge", json={"submission_id": s["submissions"][0]["id"]})
    assert r.status_code == 200
    assert r.get_json()["state"]["phase"] == "game_over"  # points_to_win was 1


def test_unseated_client_gets_400(app):
    c = app.test_client()
    host = app.test_client()
    r = host.post("/create", data={"name": "H"})
    code = r.headers["Location"].rsplit("/", 1)[-1]
    assert c.post(f"/api/game/{code}/start").status_code == 400
    assert c.get(f"/api/game/{code}/state").status_code == 200  # spectating state is fine
