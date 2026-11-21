const $ = (id) => document.getElementById(id);
let currentRewriteId = null;
const COPY_HTML = '<svg class="ic"><use href="#i-copy"/></svg> Copy';
const REWRITE_HTML = '<svg class="ic"><use href="#i-spark"/></svg> Rewrite text <svg class="ic"><use href="#i-arrow"/></svg>';

const strengthDescriptions = {
  Light: "Small edits while keeping your original wording.",
  Medium: "Balanced changes to wording and flow.",
  Strong: "More noticeable rewriting while preserving the meaning."
};

$("strength").addEventListener("change", () => {
  $("strengthNote").textContent = strengthDescriptions[$("strength").value];
});
$("sourceText").addEventListener("input", () => {
  const v = $("sourceText").value;
  const words = (v.match(/\S+/g) || []).length;
  $("charCount").textContent = `${words.toLocaleString()} words · ${v.length.toLocaleString()} characters`;
});
$("clearInput").addEventListener("click", () => {
  $("sourceText").value = "";
  $("charCount").textContent = "0 words · 0 characters";
  $("sourceText").focus();
});
$("fileInput").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  $("sourceText").value = await file.text();
  $("sourceText").dispatchEvent(new Event("input"));
  event.target.value = "";
});
$("rewriteBtn").addEventListener("click", rewrite);
$("sourceText").addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") { e.preventDefault(); rewrite(); }
});
$("regenBtn").addEventListener("click", rewrite);
$("copyBtn").addEventListener("click", async () => {
  await navigator.clipboard.writeText($("resultText").textContent);
  $("copyBtn").textContent = "Copied ✓";
  setTimeout(() => $("copyBtn").innerHTML = COPY_HTML, 1600);
});
$("downloadBtn").addEventListener("click", () => {
  if (currentRewriteId) window.location.href = `/api/export/${currentRewriteId}.txt`;
  else downloadText($("resultText").textContent, "rewritten-text.txt");
});
$("useAsInput").addEventListener("click", () => {
  $("sourceText").value = $("resultText").textContent;
  $("sourceText").dispatchEvent(new Event("input"));
  $("sourceText").focus();
  $("resultCard").hidden = true;
});
$("historyToggle").addEventListener("click", showHistory);
$("newRewriteBtn").addEventListener("click", showEditor);
$("startFromHistory").addEventListener("click", showEditor);
$("clearHistory").addEventListener("click", async () => {
  if (!confirm("Delete all saved rewrite history? This cannot be undone.")) return;
  await fetch("/api/history", {method:"DELETE"});
  loadHistory();
});

let abortController = null;
$("cancelBtn").addEventListener("click", () => { if (abortController) abortController.abort(); });

const SETTINGS_KEY = "humanly.settings";
function saveSettings() {
  try {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify({
      tone: $("tone").value, strength: $("strength").value, model: $("model") ? $("model").value : ""
    }));
  } catch (e) { /* storage unavailable */ }
}
function loadSettings() {
  try {
    const saved = JSON.parse(localStorage.getItem(SETTINGS_KEY) || "{}");
    ["tone", "strength", "model"].forEach((id) => {
      const el = $(id);
      if (el && saved[id] && [...el.options].some((o) => o.value === saved[id])) el.value = saved[id];
    });
    $("strength").dispatchEvent(new Event("change"));
  } catch (e) { /* ignore */ }
}
loadSettings();

async function rewrite() {
  const text = $("sourceText").value.trim();
  hideError();
  if (!text) return showError("Add the text you want to rewrite first.");
  const btn = $("rewriteBtn");
  btn.disabled = true;
  const started = Date.now();
  let progress = "";
  const tick = () => { btn.innerHTML = `<span class="spinner"></span> Rewriting… <span class="timer">${Math.floor((Date.now() - started) / 1000)}s${progress}</span>`; };
  tick();
  const timer = setInterval(tick, 1000);
  $("resultCard").hidden = true;
  abortController = new AbortController();
  $("cancelBtn").hidden = false;
  saveSettings();
  try {
    const response = await fetch("/api/rewrite/stream", {
      method:"POST",
      signal:abortController.signal,
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({
        text,
        tone:$("tone").value,
        strength:$("strength").value,
        model:$("model") ? $("model").value : "",
        previous_text:$("previousText").value
      })
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.error || "Something went wrong.");
    }
    let data = null;
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    const handle = (line) => {
      if (!line.trim()) return;
      const msg = JSON.parse(line);
      if (msg.type === "progress") { progress = ` · section ${msg.done} of ${msg.total} done`; tick(); }
      else if (msg.type === "error") throw new Error(msg.error);
      else if (msg.type === "done") data = msg;
    };
    for (;;) {
      const {value, done} = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, {stream:true});
      const lines = buffer.split(String.fromCharCode(10));
      buffer = lines.pop();
      lines.forEach(handle);
    }
    handle(buffer);
    if (!data) throw new Error("The rewrite ended unexpectedly. Please try again.");
    currentRewriteId = data.id;
    renderDiff(text, data.rewritten_text);
    showWarnings(data.warnings);
    $("resultMeta").textContent = `${$("tone").value} tone · ${$("strength").value.toLowerCase()} rewrite`;
    $("resultCard").hidden = false;
    $("resultCard").scrollIntoView({behavior:"smooth", block:"start"});
    refreshHistoryCount();
  } catch (error) {
    if (error.name !== "AbortError") showError(error.message);
  } finally {
    clearInterval(timer);
    abortController = null;
    $("cancelBtn").hidden = true;
    btn.disabled = false;
    btn.innerHTML = REWRITE_HTML;
  }
}

// ---- Word-level diff: highlight words that differ from the original ----
function normWord(w) { return w.toLowerCase().replace(/^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu, ""); }

function renderDiff(original, rewritten) {
  const out = $("resultText");
  out.textContent = "";
  const tokens = rewritten.split(/(\s+)/);          // keeps whitespace/newlines
  const words = [];                                  // indexes of word tokens
  tokens.forEach((t, i) => { if (t && !/^\s+$/.test(t)) words.push(i); });
  const a = original.split(/\s+/).filter(Boolean).map(normWord);
  const b = words.map(i => normWord(tokens[i]));
  const n = a.length, m = b.length;
  if (!m || n * m > 36e6) { out.textContent = rewritten; setChangeStats(null); return; }

  // LCS table (original = rows, rewritten = columns)
  const w = m + 1;
  const dp = new Uint16Array((n + 1) * w);
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i * w + j] = a[i] === b[j] ? dp[(i + 1) * w + j + 1] + 1
                                    : Math.max(dp[(i + 1) * w + j], dp[i * w + j + 1]);
    }
  }
  const kept = new Array(m).fill(false);
  for (let i = 0, j = 0; i < n && j < m;) {
    if (a[i] === b[j]) { kept[j] = true; i++; j++; }
    else if (dp[(i + 1) * w + j] >= dp[i * w + j + 1]) i++;
    else j++;
  }

  let changed = 0, wi = 0;
  const frag = document.createDocumentFragment();
  tokens.forEach((t, i) => {
    if (!t) return;
    if (wi < words.length && words[wi] === i) {
      if (kept[wi]) frag.append(document.createTextNode(t));
      else { const mark = document.createElement("mark"); mark.textContent = t; frag.append(mark); changed++; }
      wi++;
    } else frag.append(document.createTextNode(t));
  });
  out.append(frag);
  setChangeStats({changed, total: m, original: n});
}

function setChangeStats(stats) {
  const el = $("changeStats");
  if (!stats) { el.hidden = true; return; }
  const pct = Math.round(stats.changed / stats.total * 100);
  el.textContent = `${stats.changed.toLocaleString()} of ${stats.total.toLocaleString()} words changed (${pct}%)`;
  el.hidden = false;
}

function showWarnings(list) {
  const el = $("warnBanner");
  if (!list || !list.length) { el.hidden = true; return; }
  el.textContent = "Please double-check this rewrite — " + list.join(" ");
  el.hidden = false;
}
function showError(message) {
  $("errorBanner").textContent = message;
  $("errorBanner").hidden = false;
}
function hideError() { $("errorBanner").hidden = true; }
function downloadText(content, filename) {
  const blob = new Blob([content], {type:"text/plain;charset=utf-8"});
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}
function showEditor() {
  $("editorView").hidden = false;
  $("historyView").hidden = true;
  $("newRewriteBtn").classList.add("active");
  $("historyToggle").classList.remove("active");
}
async function showHistory() {
  $("editorView").hidden = true;
  $("historyView").hidden = false;
  $("newRewriteBtn").classList.remove("active");
  $("historyToggle").classList.add("active");
  await loadHistory();
}
async function loadHistory() {
  const response = await fetch("/api/history");
  const data = await response.json();
  $("historyCount").textContent = data.items.length;
  $("emptyHistory").hidden = data.items.length > 0;
  $("historyList").innerHTML = "";
  data.items.forEach(item => {
    const article = document.createElement("article");
    article.className = "history-item";
    const info = document.createElement("div");
    info.className = "history-info";
    const title = document.createElement("strong");
    title.textContent = item.original_text.slice(0, 75) || "Untitled rewrite";
    const preview = document.createElement("p");
    preview.textContent = item.rewritten_text.slice(0, 150);
    const meta = document.createElement("div");
    meta.className = "history-meta";
    meta.textContent = `${item.tone} · ${item.strength} · ${item.created_at}`;
    info.append(title, preview, meta);
    const actions = document.createElement("div");
    actions.className = "history-buttons";
    const open = document.createElement("button");
    open.className = "outline-btn"; open.textContent = "Open";
    open.addEventListener("click", () => openHistoryItem(item.id));
    const remove = document.createElement("button");
    remove.className = "outline-btn"; remove.textContent = "Delete";
    remove.addEventListener("click", async () => {
      await fetch(`/api/history/${item.id}`, {method:"DELETE"});
      loadHistory();
    });
    actions.append(open, remove);
    article.append(info, actions);
    $("historyList").append(article);
  });
}
async function openHistoryItem(id) {
  const response = await fetch(`/api/history/${id}`);
  const data = await response.json();
  const item = data.item;
  $("sourceText").value = item.original_text;
  $("sourceText").dispatchEvent(new Event("input"));
  $("previousText").value = item.previous_text || "";
  $("tone").value = item.tone;
  $("strength").value = item.strength;
  $("strength").dispatchEvent(new Event("change"));
  renderDiff(item.original_text, item.rewritten_text);
  showWarnings([]);
  $("resultMeta").textContent = `${item.tone} tone · ${item.strength.toLowerCase()} rewrite`;
  currentRewriteId = item.id;
  $("resultCard").hidden = false;
  showEditor();
  $("resultCard").scrollIntoView({behavior:"smooth"});
}
async function refreshHistoryCount() {
  const response = await fetch("/api/history");
  const data = await response.json();
  $("historyCount").textContent = data.items.length;
}
refreshHistoryCount();
