(function () {
  const UI = window.QUEST_UI;
  const app = document.getElementById("app");
  const csrf = document.querySelector('meta[name="csrf-token"]').content;
  let mistakes = 0;

  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const paras = arr => arr.map(t => `<p>${esc(t)}</p>`).join("");

  async function api(path, body) {
    const opts = body === undefined ? {} : {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
      body: JSON.stringify(body),
    };
    const r = await fetch(path, opts);
    if (!r.ok) throw new Error(r.status);
    return r.json();
  }

  function progressBar(i, total) {
    let s = '<div class="progress">';
    for (let k = 0; k < total; k++) s += `<i class="${k < i ? "done" : k === i ? "now" : ""}"></i>`;
    return s + "</div>";
  }

  function render(state) {
    if (state.stage === "intro") return renderIntro();
    if (state.stage === "level") return renderLevel(state.level);
    if (state.stage === "final") return renderFinal(state.final, state.total);
  }

  function renderIntro() {
    const s = UI.intro;
    app.innerHTML = `<div class="card center">
      <div class="big-emoji">${s.emoji}</div>
      <h1>${esc(s.title)}</h1>${paras(s.text)}
      <button id="go">${esc(s.button)}</button></div>`;
    document.getElementById("go").onclick = async () => render(await api("/api/quest/start", {}));
  }

  function renderLevel(lvl) {
    mistakes = 0;
    app.innerHTML = `<div class="card" id="card">
      ${progressBar(lvl.index, lvl.total)}
      <div class="label">Вопрос ${lvl.index + 1} из ${lvl.total}</div>
      ${lvl.image ? `<img class="qimg" src="${esc(lvl.image)}" alt="">` : ""}
      <div class="q">${esc(lvl.question)}</div>
      <form id="f" autocomplete="off">
        <input id="ans" placeholder="Твой ответ…" autocapitalize="off" spellcheck="false" maxlength="200">
        <button type="submit">Ответить</button>
      </form>
      <div class="msg" id="msg"></div>
      <button class="ghost" id="hintBtn" style="display:none">Подсказка 💡</button>
      <div class="hint" id="hint">${esc(lvl.hint || "")}</div>
    </div>`;
    const input = document.getElementById("ans");
    const msg = document.getElementById("msg");
    const btn = document.querySelector("#f button");
    setTimeout(() => input.focus(), 300);

    document.getElementById("f").onsubmit = async e => {
      e.preventDefault();
      if (!input.value.trim()) return;
      btn.disabled = true;
      let res;
      try { res = await api("/api/quest/answer", { answer: input.value }); }
      catch { msg.className = "msg bad"; msg.textContent = "Что-то с интернетом, попробуй ещё раз"; btn.disabled = false; return; }

      if (res.correct) {
        msg.className = "msg ok"; msg.textContent = res.success || "Верно!";
        input.disabled = true; burst(18);
        setTimeout(async () => render(await api("/api/quest")), 1400);
      } else {
        btn.disabled = false;
        mistakes++;
        msg.className = "msg bad";
        msg.textContent = UI.wrong[Math.floor(Math.random() * UI.wrong.length)];
        const card = document.getElementById("card");
        card.classList.remove("shake"); void card.offsetWidth; card.classList.add("shake");
        if (lvl.hint && mistakes >= UI.hintAfter) document.getElementById("hintBtn").style.display = "block";
        input.select();
      }
    };
    document.getElementById("hintBtn").onclick = function () {
      document.getElementById("hint").classList.add("show"); this.style.display = "none";
    };
  }

  function renderFinal(s, total) {
    app.innerHTML = `<div class="card center">
      ${progressBar(total, total)}
      <div class="big-emoji">${s.emoji}</div>
      <h1>${esc(s.title)}</h1>${paras(s.text)}
      <div class="clue">${esc(s.clue)}</div>
      <p style="margin-top:16px;font-family:'Playfair Display',serif;font-style:italic">${esc(s.signature)}</p>
      <a class="btn" href="${esc(UI.homeUrl)}">${esc(s.button || "Дальше →")}</a>
    </div>`;
    burst(120);
  }

  function burst(n) {
    const colors = ["#ff7aa2", "#ffb38a", "#ffd6e0", "#fff", "#ff4d7d"];
    for (let i = 0; i < n; i++) {
      const c = document.createElement("div"); c.className = "confetti";
      c.style.left = Math.random() * 100 + "vw";
      c.style.background = colors[i % colors.length];
      c.style.borderRadius = Math.random() > .5 ? "50%" : "2px";
      c.style.animationDuration = (2 + Math.random() * 2.5) + "s";
      c.style.animationDelay = (Math.random() * .4) + "s";
      document.body.appendChild(c);
      setTimeout(() => c.remove(), 5200);
    }
  }

  api("/api/quest").then(render).catch(() => {
    app.innerHTML = '<div class="card center"><p>Не получилось загрузить. Обнови страницу 🙏</p></div>';
  });
})();
