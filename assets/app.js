/* EarnScout dashboard — vanilla JS, no build step. */
const state = {
  items: [],
  q: "",
  tier: "all",
  audience: "entry",
  category: "all",
  rail: "all",
  source: "all",
  showOld: false,
};

const $ = (sel) => document.querySelector(sel);
const grid = $("#grid");
const empty = $("#empty");
const stats = $("#stats");
const updated = $("#updated");

const TIER_LABEL = {
  verified: "✅ Verified",
  screened: "🟢 Screened",
  unverified: "🟡 Unverified",
  speculative: "🔮 Speculative",
};

function text(el, value) {
  el.textContent = value == null ? "" : String(value);
  return el;
}

function el(tag, cls, value) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (value != null) node.textContent = String(value);
  return node;
}

function safeUrl(value) {
  if (typeof value !== "string") return "#";
  const v = value.trim();
  return /^https?:\/\//i.test(v) ? v : "#";
}

function ageLabel(iso) {
  if (!iso) return "date unknown";
  const then = Date.parse(iso);
  if (Number.isNaN(then)) return "date unknown";
  const hours = Math.max(0, (Date.now() - then) / 36e5);
  if (hours < 1) return "just now";
  if (hours < 24) return `${Math.round(hours)}h ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days}d ago`;
  return `${Math.round(days / 30)}mo ago`;
}

function railBucket(rails) {
  const r = (rails || []).map((x) => String(x).toLowerCase());
  if (r.some((x) => ["usdt", "usdc", "btc", "eth", "sol", "crypto"].includes(x))) return "crypto";
  if (r.includes("gift_card")) return "gift_card";
  if (r.some((x) => ["usd", "eur", "gbp", "cad", "aud", "chf", "sgd"].includes(x))) return "usd";
  if (r.some((x) => ["payoneer", "deel", "wise", "grey", "cleva", "daya", "chipper"].includes(x))) return "payoneer";
  if (r.includes("ngn")) return "ngn";
  return "other";
}

function matches(item) {
  if (!state.showOld && item.status !== "active") return false;
  if (item.tier === "blocked") return false;
  if (state.audience !== "all" && (item.audience || "unknown") !== state.audience) return false;
  if (state.tier !== "all" && item.tier !== state.tier) return false;
  if (state.tier === "all" && item.tier === "speculative" && item.status !== "active") return false;
  if (state.category !== "all" && item.category !== state.category) return false;
  if (state.source !== "all" && item.source !== state.source) return false;
  if (state.rail !== "all" && railBucket(item.payment_rails) !== state.rail) return false;
  if (state.q) {
    const hay = [item.title, item.company, item.snippet, (item.payment_rails || []).join(" ")]
      .join(" ")
      .toLowerCase();
    if (!hay.includes(state.q)) return false;
  }
  return true;
}

function card(item) {
  const node = el("article", "card");
  const top = el("div", "card-top");

  const badge = el("span", `badge ${item.tier}`, TIER_LABEL[item.tier] || item.tier);
  top.appendChild(badge);

  const score = item.score && typeof item.score.total === "number" ? item.score.total : null;
  const scoreNode = el("span", "score");
  if (score != null) {
    scoreNode.append(document.createTextNode(String(score)));
    scoreNode.append(el("small", null, " /score"));
  } else {
    scoreNode.textContent = "—";
  }
  top.appendChild(scoreNode);
  node.appendChild(top);

  const h3 = el("h3");
  const a = el("a", null, item.title || "(untitled)");
  a.href = safeUrl(item.url);
  a.target = "_blank";
  a.rel = "noopener noreferrer nofollow";
  h3.appendChild(a);
  node.appendChild(h3);

  const metaBits = [item.company, item.source, item.location_raw].filter(Boolean);
  node.appendChild(el("div", "meta", metaBits.join(" · ")));

  const chips = el("div", "chips");
  for (const rail of item.payment_rails || []) {
    chips.appendChild(el("span", "chip pay", rail));
  }
  if (item.payment_protection && item.payment_protection !== "unknown") {
    chips.appendChild(el("span", "chip protect", item.payment_protection === "escrow" ? "escrow" : "platform"));
  }
  if (item.nigeria_ok === true) chips.appendChild(el("span", "chip", "Nigeria-eligible"));
  if (item.audience === "entry") chips.appendChild(el("span", "chip", "entry-level"));
  node.appendChild(chips);

  if (item.evidence) {
    const ev = item.evidence;
    if (ev.self_hosted && ev.age_days != null) {
      chips.appendChild(el("span", "chip", `domain ${(ev.age_days / 365).toFixed(1)}y`));
    }
    if (ev.http_status === 404 || ev.http_status === 410) {
      chips.appendChild(el("span", "chip warn", "page missing"));
    }
    const det = el("details");
    det.appendChild(el("summary", null, "evidence"));
    const rows = [
      ["domain", ev.domain || "—"],
      ["registered", ev.registered_at ? ev.registered_at.slice(0, 10) : "unknown"],
      ["age", ev.age_days != null ? `${ev.age_days} days` : "unknown"],
      ["registrar", ev.registrar || "unknown"],
      ["resolves", ev.resolves ? "yes" : "no"],
      ["http", ev.http_status != null ? String(ev.http_status) : "error"],
      ["checked", ev.checked_at ? ev.checked_at.slice(0, 10) : "—"],
    ];
    for (const [key, value] of rows) {
      const row = el("div", "row");
      row.appendChild(el("span", null, key));
      row.appendChild(el("span", null, value));
      det.appendChild(row);
    }
    node.appendChild(det);
  }

  if (item.snippet) node.appendChild(el("p", "snippet", item.snippet));

  const foot = el("div", "card-foot");
  foot.appendChild(el("span", null, ageLabel(item.posted_at)));
  if (item.deadline) {
    const d = new Date(item.deadline);
    if (!Number.isNaN(d.getTime())) {
      foot.appendChild(el("span", "deadline", `closes ${d.toISOString().slice(0, 10)}`));
    }
  }
  node.appendChild(foot);

  const signals = (item.signals || []).filter((s) => s.severity !== "block");
  if (signals.length) {
    const det = el("details");
    det.appendChild(el("summary", null, `${signals.length} signal${signals.length === 1 ? "" : "s"}`));
    for (const sig of signals) {
      const row = el("div", "row");
      row.appendChild(el("span", sig.severity === "weak" ? "warn" : null, sig.id));
      row.appendChild(el("span", null, sig.evidence || ""));
      det.appendChild(row);
    }
    node.appendChild(det);
  }

  if (item.score && item.score.components) {
    const det = el("details");
    det.appendChild(el("summary", null, "why this score"));
    for (const [key, value] of Object.entries(item.score.components)) {
      const row = el("div", "row");
      row.appendChild(el("span", null, key));
      row.appendChild(el("span", null, String(value)));
      det.appendChild(row);
    }
    node.appendChild(det);
  }

  return node;
}

function render() {
  const visible = state.items.filter(matches).sort((a, b) => {
    const sa = (a.score && a.score.total) || 0;
    const sb = (b.score && b.score.total) || 0;
    return sb - sa;
  });

  grid.replaceChildren(...visible.map(card));
  empty.hidden = visible.length !== 0;

  const counts = { verified: 0, screened: 0, unverified: 0, entry: 0 };
  for (const item of state.items) {
    if (item.status === "active" && counts[item.tier] != null) counts[item.tier] += 1;
    if (item.status === "active" && item.audience === "entry") counts.entry += 1;
  }
  stats.replaceChildren();
  for (const [label, value] of [
    ["entry-level", counts.entry],
    ["verified", counts.verified],
    ["screened", counts.screened],
    ["unverified", counts.unverified],
    ["shown", visible.length],
  ]) {
    const s = el("span");
    s.append(el("b", null, value));
    s.append(document.createTextNode(` ${label}`));
    stats.appendChild(s);
  }
}

function fillSources() {
  const select = $("#source");
  const sources = [...new Set(state.items.map((i) => i.source).filter(Boolean))].sort();
  for (const source of sources) {
    const opt = document.createElement("option");
    opt.value = source;
    opt.textContent = source;
    select.appendChild(opt);
  }
}

async function load() {
  try {
    const res = await fetch("data/listings.json", { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    state.items = Array.isArray(data.items) ? data.items : [];
    updated.textContent = data.updated_at
      ? `Data updated ${new Date(data.updated_at).toLocaleString()} · ${state.items.length} stored listings`
      : "No data yet — run the pipeline.";
    fillSources();
    render();
  } catch (err) {
    updated.textContent = `Could not load data: ${err.message}`;
    empty.hidden = false;
    empty.textContent = "Data file missing. Run: python3 -m src.run";
  }
}

$("#q").addEventListener("input", (e) => { state.q = e.target.value.trim().toLowerCase(); render(); });
$("#audience").addEventListener("change", (e) => { state.audience = e.target.value; render(); });
$("#tier").addEventListener("change", (e) => { state.tier = e.target.value; render(); });
$("#category").addEventListener("change", (e) => { state.category = e.target.value; render(); });
$("#rail").addEventListener("change", (e) => { state.rail = e.target.value; render(); });
$("#source").addEventListener("change", (e) => { state.source = e.target.value; render(); });
$("#expired").addEventListener("change", (e) => { state.showOld = e.target.checked; render(); });

load();
