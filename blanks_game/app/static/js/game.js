/* Client-side "view" for the game table.
 * Polls /api/game/<code>/state and re-renders. All rules live server-side. */
(function () {
  const root = document.getElementById("game");
  const CODE = root.dataset.code;
  const API = root.dataset.api;               // e.g. /api/game/ABCD
  const POLL = parseInt(root.dataset.poll, 10) || 1500;
  const IMG = "/static/img/";

  const $ = (id) => document.getElementById(id);
  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  };

  let state = null;
  let selected = [];        // card ids chosen from hand, in order
  let selectedSubmission = null;  // submission id the judge has tentatively picked
  let busy = false;

  // ---------------------------------------------------------------- network
  async function api(path, body) {
    const res = await fetch(API + path, {
      method: body === undefined ? "GET" : "POST",
      headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({ ok: false, error: "Bad response" }));
    if (!data.ok) throw new Error(data.error || "Something went wrong");
    return data.state;
  }

  async function act(path, body) {
    if (busy) return;
    busy = true;
    try {
      const s = await api(path, body || {});
      setState(s);
    } catch (e) {
      toast(e.message);
    } finally {
      busy = false;
    }
  }

  async function poll() {
    try {
      const s = await api("/state");
      setState(s);
    } catch (e) {
      toast(e.message);
    }
  }

  let lastJSON = "";
  function setState(s) {
    const json = JSON.stringify(s);
    if (json === lastJSON) return;          // nothing changed: don't disturb the DOM
    lastJSON = json;
    const prevPhase = state && state.phase;
    const prevRound = state && state.round;
    state = s;
    if (prevPhase !== s.phase || prevRound !== s.round) {
      selected = [];
      selectedSubmission = null;
    }
    render();
  }

  // ---------------------------------------------------------------- toast
  let toastTimer;
  function toast(msg) {
    const t = $("toast");
    t.textContent = msg;
    t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => (t.hidden = true), 3000);
  }

  // ---------------------------------------------------------------- cards
  function cardNode(card, colour, opts = {}) {
    const c = el("div", `card ${colour}`);
    c.dataset.id = card.id;
    const text = el("div", "text", card.text.replace(/____/g, "______"));
    c.appendChild(text);
    if (card.pack) c.appendChild(el("span", "pack", card.pack));
    if (colour === "black" && card.pick > 1) c.appendChild(el("span", "pick-badge", "PICK " + card.pick));
    if (opts.big) c.classList.add("big");
    if (opts.order) c.appendChild(el("span", "order", String(opts.order)));
    return c;
  }

  function renderedHTML(black, cards) {
    // Highlight the answers inside the prompt.
    let text = escapeHTML(black.text);
    const answers = cards.map((c) => `<mark>${escapeHTML(c.text)}</mark>`);
    while (text.includes("____") && answers.length) text = text.replace("____", answers.shift());
    if (answers.length) text += " " + answers.join(" / ");
    return text;
  }

  function escapeHTML(s) {
    return s.replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
  }

  // ---------------------------------------------------------------- render
  function render() {
    renderPlayers();
    renderTable();
    renderHand();
  }

  function renderPlayers() {
    const ul = $("players");
    ul.innerHTML = "";
    state.players.forEach((p) => {
      const li = el("li");
      if (state.me && p.id === state.me.id) li.classList.add("me");
      const tick = el("span", "tick", state.phase === "submitting" && p.submitted ? "✓" : "");
      li.appendChild(tick);
      const name = el("span", "name", p.name);
      li.appendChild(name);
      if (p.id === state.host_id) li.appendChild(el("span", "tag", "HOST"));
      if (p.is_bot) li.appendChild(el("span", "tag bot", "BOT"));
      if (p.is_judge && state.phase !== "lobby") {
        const img = el("img", "judge-icon");
        img.src = IMG + "gavel.svg";
        img.title = "Judge";
        li.appendChild(img);
      }
      li.appendChild(el("span", "score", String(p.score)));
      ul.appendChild(li);
    });
    $("round-label").textContent = state.round ? `· Round ${state.round}` : "";
    $("deck-info").textContent = state.round
      ? `First to ${state.points_to_win}. Deck: ${state.deck.white_remaining} white / ${state.deck.black_remaining} black left.`
      : `First to ${state.points_to_win} points. Packs: ${state.packs.join(", ") || "none"}.`;
  }

  function renderTable() {
    const status = $("status");
    const slot = $("black-slot");
    const subs = $("submissions");
    const actions = $("actions");
    status.innerHTML = "";
    slot.innerHTML = "";
    subs.innerHTML = "";
    actions.innerHTML = "";
    const me = state.me;

    if (state.phase === "lobby") {
      status.textContent = `Waiting for players… (${state.players.length} joined, need ${state.min_players})`;
      status.appendChild(el("span", "sub", `Share the code ${state.code} — friends join from the home page.`));
      const back = el("div", "card black back-black big");
      slot.appendChild(back);
      if (me && me.is_host) {
        const b = el("button", "btn primary", "Start game");
        b.disabled = state.players.length < state.min_players;
        b.onclick = () => act("/start");
        actions.appendChild(b);
        const bot = el("button", "btn", "Add bot");
        bot.disabled = state.players.length >= 12;
        bot.onclick = () => act("/add_bot");
        actions.appendChild(bot);
      } else {
        actions.appendChild(el("span", "muted", "The host will start the game."));
      }
      return;
    }

    const black = state.black_card;
    slot.appendChild(cardNode(black, "black", { big: true }));

    if (state.phase === "submitting") {
      if (me.is_judge) {
        status.textContent = "You're the Judge this round.";
        status.appendChild(el("span", "sub", `Waiting for ${state.expected_count - state.submitted_count} more player(s)…`));
      } else if (me.has_submitted) {
        status.textContent = "Cards played!";
        status.appendChild(el("span", "sub", `Waiting for ${state.expected_count - state.submitted_count} more player(s)…`));
      } else {
        status.textContent = black.pick > 1 ? `Pick ${black.pick} cards from your hand, in order.` : "Pick a card from your hand.";
        status.appendChild(el("span", "sub", `${state.judge_name} is judging.`));
        const preview = el("div", "rendered");
        const chosen = selected.map((id) => me.hand.find((c) => c.id === id)).filter(Boolean);
        preview.innerHTML = renderedHTML(black, chosen);
        slot.appendChild(preview);
        const b = el("button", "btn primary", selected.length === black.pick ? "Play these" : `Play (${selected.length}/${black.pick})`);
        b.disabled = selected.length !== black.pick;
        b.onclick = () => act("/submit", { card_ids: selected });
        actions.appendChild(b);
        if (selected.length) {
          const clear = el("button", "btn", "Clear");
          clear.onclick = () => { selected = []; render(); };
          actions.appendChild(clear);
        }
      }
      // face-down piles for the cards played so far
      for (let i = 0; i < state.submitted_count; i++) {
        const s = el("div", "submission");
        const g = el("div", "group");
        g.appendChild(el("div", "card white back-white"));
        s.appendChild(g);
        subs.appendChild(s);
      }
      return;
    }

    if (state.phase === "judging") {
      status.textContent = me.is_judge
        ? (selectedSubmission ? "Confirm your pick below." : "Click your favorite, then confirm.")
        : `${state.judge_name} is choosing a winner…`;
      state.submissions.forEach((sub) => {
        const s = el("div", "submission");
        const g = el("div", "group");
        sub.cards.forEach((c, i) => g.appendChild(cardNode(c, "white", { order: sub.cards.length > 1 ? i + 1 : 0 })));
        s.appendChild(g);
        const r = el("div", "rendered small");
        r.innerHTML = renderedHTML(black, sub.cards);
        s.appendChild(r);
        if (me.is_judge) {
          const isChosen = selectedSubmission === sub.id;
          g.querySelectorAll(".card").forEach((c) => {
            c.classList.add("selectable");
            if (isChosen) c.classList.add("selected");
          });
          if (isChosen) s.classList.add("chosen");
          g.onclick = () => { selectedSubmission = sub.id; render(); };
        }
        subs.appendChild(s);
      });
      if (me.is_judge) {
        const b = el("button", "btn primary", "Confirm winner");
        b.disabled = !selectedSubmission;
        b.onclick = () => act("/judge", { submission_id: selectedSubmission });
        actions.appendChild(b);
      }
      return;
    }

    if (state.phase === "round_over" || state.phase === "game_over") {
      if (state.phase === "game_over") {
        status.textContent = `🏆 ${state.game_winner_name} wins the game!`;
      } else {
        status.textContent = `${state.round_winner_name} wins the round!`;
      }
      state.submissions.forEach((sub) => {
        const s = el("div", "submission");
        const g = el("div", "group");
        sub.cards.forEach((c, i) => {
          const n = cardNode(c, "white", { order: sub.cards.length > 1 ? i + 1 : 0 });
          if (sub.winner) n.classList.add("winner");
          g.appendChild(n);
        });
        s.appendChild(g);
        const who = el("div", "who" + (sub.winner ? " winner" : ""), (sub.winner ? "★ " : "") + sub.player_name);
        s.appendChild(who);
        subs.appendChild(s);
      });
      if (state.phase === "round_over") {
        const b = el("button", "btn primary", "Next round");
        b.onclick = () => act("/next");
        actions.appendChild(b);
      } else if (me.is_host) {
        const b = el("button", "btn primary", "Play again");
        b.onclick = () => act("/restart");
        actions.appendChild(b);
      }
      if (state.history.length) {
        const h = el("div", "history");
        const ul = el("ul");
        state.history.slice().reverse().forEach((r) => {
          const li = el("li");
          li.innerHTML = `Round ${r.round}: <b>${escapeHTML(r.winner)}</b> — ${escapeHTML(r.answer)}`;
          ul.appendChild(li);
        });
        h.appendChild(ul);
        actions.appendChild(h);
      }
    }
  }

  function renderHand() {
    const hand = $("hand");
    hand.innerHTML = "";
    const me = state.me;
    if (!me || state.phase === "lobby") {
      $("hand-title").textContent = "Your hand";
      hand.appendChild(el("p", "muted", "You'll be dealt cards when the game starts."));
      return;
    }
    const canPlay = state.phase === "submitting" && !me.is_judge && !me.has_submitted;
    $("hand-title").textContent = me.is_judge && state.phase === "submitting" ? "Your hand (sit tight, Judge)" : "Your hand";
    me.hand.forEach((c) => {
      const idx = selected.indexOf(c.id);
      const n = cardNode(c, "white", { order: idx >= 0 && state.black_card.pick > 1 ? idx + 1 : 0 });
      if (canPlay) {
        n.classList.add("selectable");
        if (idx >= 0) n.classList.add("selected");
        n.onclick = () => {
          const pick = state.black_card.pick;
          if (idx >= 0) selected.splice(idx, 1);
          else if (selected.length < pick) selected.push(c.id);
          else if (pick === 1) selected = [c.id];
          render();
        };
      }
      hand.appendChild(n);
    });
  }

  // ---------------------------------------------------------------- go
  poll();
  setInterval(poll, POLL);
})();
