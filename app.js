const spirits = [
  { id: "taotie", name: "饕餮", root: "混沌灵根", trait: "吞灵材，炼上下文" },
  { id: "dragon", name: "东方龙", root: "水木灵根", trait: "长线项目守护" },
  { id: "phoenix", name: "凤凰", root: "火灵根", trait: "失败重试与复原" },
  { id: "toad", name: "蟾蜍", root: "土金灵根", trait: "炼丹吐宝" },
  { id: "unicorn", name: "独角兽", root: "光灵根", trait: "文档与创意" },
  { id: "xuanwu", name: "玄武", root: "土水灵根", trait: "测试与安全" }
];

const defaultState = {
  spirit: "taotie",
  born: false,
  shortRemaining: 91,
  weekRemaining: 98,
  fullness: 62,
  digestRate: 72,
  feedCount: 0,
  scrolls: [],
  realm: "炼气",
  source: "Demo",
  planType: "",
  shortResetLabel: "约 02:17 后回转",
  weekResetLabel: "6 月 5 日回转"
};

let state = loadState();

const el = {
  spiritGrid: document.querySelector("#spiritGrid"),
  birthBadge: document.querySelector("#birthBadge"),
  sourceBadge: document.querySelector("#sourceBadge"),
  shortValue: document.querySelector("#shortValue"),
  weekValue: document.querySelector("#weekValue"),
  shortMeter: document.querySelector("#shortMeter"),
  weekMeter: document.querySelector("#weekMeter"),
  shortReset: document.querySelector("#shortReset"),
  weekReset: document.querySelector("#weekReset"),
  fullness: document.querySelector("#fullness"),
  digestRate: document.querySelector("#digestRate"),
  feedCount: document.querySelector("#feedCount"),
  scrollCount: document.querySelector("#scrollCount"),
  realm: document.querySelector("#realm"),
  speech: document.querySelector("#speech"),
  taotie: document.querySelector("#taotie"),
  petShortValue: document.querySelector("#petShortValue"),
  petUsageText: document.querySelector("#petUsageText"),
  dropZone: document.querySelector("#dropZone"),
  fileInput: document.querySelector("#fileInput"),
  chooseFiles: document.querySelector("#chooseFiles"),
  feedLog: document.querySelector("#feedLog"),
  downloadLatest: document.querySelector("#downloadLatest"),
  consumeLight: document.querySelector("#consumeLight"),
  consumeHeavy: document.querySelector("#consumeHeavy"),
  markUseful: document.querySelector("#markUseful"),
  resetDemo: document.querySelector("#resetDemo")
};

renderSpiritChoices();
bindEvents();
refreshRateLimits();
render();

function loadState() {
  try {
    const saved = localStorage.getItem("codex-spirit-demo");
    return saved ? { ...defaultState, ...JSON.parse(saved) } : { ...defaultState };
  } catch {
    return { ...defaultState };
  }
}

function saveState() {
  localStorage.setItem("codex-spirit-demo", JSON.stringify(state));
}

function renderSpiritChoices() {
  el.spiritGrid.innerHTML = "";
  spirits.forEach((spirit) => {
    const button = document.createElement("button");
    button.className = "spirit-card";
    button.type = "button";
    button.dataset.spirit = spirit.id;
    button.innerHTML = `<strong>${spirit.name}</strong><span>${spirit.root}<br>${spirit.trait}</span>`;
    button.addEventListener("click", () => {
      state.spirit = spirit.id;
      state.born = true;
      state.fullness = Math.max(state.fullness, 68);
      speak(`${spirit.name}开灵成功。${spirit.trait}，今日入驻你的洞府。`);
      saveState();
      render();
    });
    el.spiritGrid.appendChild(button);
  });
}

function bindEvents() {
  el.chooseFiles.addEventListener("click", () => el.fileInput.click());
  el.fileInput.addEventListener("change", (event) => feedFiles([...event.target.files]));

  ["dragenter", "dragover"].forEach((name) => {
    el.dropZone.addEventListener(name, (event) => {
      event.preventDefault();
      el.dropZone.classList.add("dragging");
    });
  });

  ["dragleave", "drop"].forEach((name) => {
    el.dropZone.addEventListener(name, (event) => {
      event.preventDefault();
      el.dropZone.classList.remove("dragging");
    });
  });

  el.dropZone.addEventListener("drop", (event) => {
    const files = [...event.dataTransfer.files];
    feedFiles(files);
  });

  el.consumeLight.addEventListener("click", () => consumeQi(2, "轻量推演完成，饕餮舔了舔灵气。"));
  el.consumeHeavy.addEventListener("click", () => consumeQi(7, "大阵推演启动，饕餮认真咀嚼这口灵气。"));
  el.markUseful.addEventListener("click", markUseful);
  el.downloadLatest.addEventListener("click", downloadLatestScroll);
  el.resetDemo.addEventListener("click", () => {
    state = { ...defaultState };
    localStorage.removeItem("codex-spirit-demo");
    speak("洞府已重置，等待新的开灵仪式。");
    render();
  });
}

async function refreshRateLimits() {
  try {
    const response = await fetch("/api/rate-limits");
    const data = await response.json();
    if (!response.ok || !data || data.source !== "codex-app-server") {
      state.source = "Demo";
      if (data?.detail) {
        console.info("Codex rate limit fallback:", data.detail);
      }
      saveState();
      render();
      return;
    }
    if (data.primary) {
      state.shortRemaining = clamp(Math.round(data.primary.remainingPercent), 0, 100);
      state.shortResetLabel = data.primary.resetLabel || "短期灵脉回转时间未知";
    }
    if (data.secondary) {
      state.weekRemaining = clamp(Math.round(data.secondary.remainingPercent), 0, 100);
      state.weekResetLabel = data.secondary.resetLabel || "长期灵脉回转时间未知";
    }
    state.source = "Codex";
    state.planType = data.planType || "";
    if (data.rateLimitReachedType) {
      speak("灵脉触及限制，饕餮建议先消化已有成果。");
    }
    saveState();
    render();
  } catch {
    state.source = "Demo";
    saveState();
  }
}

async function feedFiles(files) {
  if (!files.length) return;
  for (const file of files) {
    const scroll = await createScroll(file);
    const saved = await saveScrollToProject(scroll);
    if (saved?.savedPath) {
      scroll.savedPath = saved.savedPath;
    }
    state.scrolls.unshift(scroll);
    state.scrolls = state.scrolls.slice(0, 12);
    state.feedCount += 1;
    state.fullness = clamp(state.fullness + 8, 0, 100);
    state.digestRate = clamp(state.digestRate + 3, 20, 100);
    state.shortRemaining = clamp(state.shortRemaining - 1, 0, 100);
  }
  animateEat();
  speak(`收下 ${files.length} 份灵材，已炼成投喂玉简。`);
  updateRealm();
  saveState();
  render();
}

async function createScroll(file) {
  const type = file.type || guessType(file.name);
  const text = await readTextPreview(file);
  const summary = summarizeText(text);
  const createdAt = new Date();
  const markdown = [
    `# 投喂玉简：${file.name}`,
    "",
    `- 灵材名称：${file.name}`,
    `- 灵材类型：${type}`,
    `- 灵材大小：${formatBytes(file.size)}`,
    `- 投喂时间：${createdAt.toLocaleString("zh-CN")}`,
    `- 灵兽反馈：${summary ? "此物有文字灵息，已完成初步炼化。" : "此物以形质为主，已记录外相，不读取正文。"}`,
    "",
    "## 初步摘要",
    "",
    summary || "未读取正文。适合后续交给 Codex 做进一步分析。",
    "",
    "## 后续可用 prompt",
    "",
    `请基于这份灵材 ${file.name}，帮我整理重点、风险和下一步行动。`
  ].join("\n");

  return {
    id: crypto.randomUUID(),
    fileName: file.name,
    type,
    size: file.size,
    createdAt: createdAt.toISOString(),
    summary: summary || "记录外相，等待进一步炼化。",
    markdown
  };
}

function readTextPreview(file) {
  const textLike = [
    "text/",
    "application/json",
    "application/xml",
    "application/javascript"
  ].some((prefix) => file.type.startsWith(prefix));
  const extLike = /\.(md|txt|json|csv|log|xml|js|ts|tsx|jsx|html|css)$/i.test(file.name);
  if (!textLike && !extLike) return Promise.resolve("");
  const blob = file.slice(0, 16000);
  return blob.text().catch(() => "");
}

function summarizeText(text) {
  const clean = text.replace(/\s+/g, " ").trim();
  if (!clean) return "";
  const sentences = clean.match(/[^。！？.!?]+[。！？.!?]?/g) || [clean];
  return sentences.slice(0, 3).join(" ").slice(0, 360);
}

function consumeQi(amount, message) {
  state.shortRemaining = clamp(state.shortRemaining - amount, 0, 100);
  state.weekRemaining = clamp(state.weekRemaining - Math.max(1, Math.floor(amount / 2)), 0, 100);
  state.fullness = clamp(state.fullness + Math.floor(amount / 2), 0, 100);
  state.digestRate = clamp(state.digestRate - Math.max(1, Math.floor(amount / 3)), 10, 100);
  animateEat();
  speak(message);
  updateRealm();
  saveState();
  render();
}

function markUseful() {
  state.digestRate = clamp(state.digestRate + 10, 0, 100);
  state.fullness = clamp(state.fullness + 5, 0, 100);
  speak("炼化成功，灵气转为修为。不是烧得多，是用得准。");
  updateRealm();
  saveState();
  render();
}

function updateRealm() {
  const score = state.feedCount * 12 + state.digestRate + (100 - state.shortRemaining);
  if (score > 210) state.realm = "金丹";
  else if (score > 145) state.realm = "筑基";
  else state.realm = "炼气";
}

function render() {
  const current = spirits.find((spirit) => spirit.id === state.spirit) || spirits[0];
  document.querySelectorAll(".spirit-card").forEach((card) => {
    card.classList.toggle("active", card.dataset.spirit === state.spirit);
  });
  el.birthBadge.textContent = state.born ? `${current.root}` : "未开灵";
  el.sourceBadge.textContent = state.planType ? `${state.source} · ${state.planType}` : state.source;
  el.shortValue.textContent = `${state.shortRemaining}%`;
  el.weekValue.textContent = `${state.weekRemaining}%`;
  el.shortMeter.style.width = `${state.shortRemaining}%`;
  el.weekMeter.style.width = `${state.weekRemaining}%`;
  el.shortReset.textContent = state.shortResetLabel;
  el.weekReset.textContent = state.weekResetLabel;
  el.petShortValue.textContent = `${state.shortRemaining}%`;
  el.petUsageText.textContent = `${state.shortRemaining}%`;
  el.taotie.style.setProperty("--short-qi", `${state.shortRemaining}%`);
  el.taotie.style.setProperty("--week-qi", `${state.weekRemaining}%`);
  el.fullness.textContent = state.fullness;
  el.digestRate.textContent = `${state.digestRate}%`;
  el.feedCount.textContent = state.feedCount;
  el.scrollCount.textContent = state.scrolls.length;
  el.realm.textContent = state.realm;
  el.downloadLatest.disabled = state.scrolls.length === 0;
  el.taotie.classList.toggle("sleepy", state.fullness < 24 || state.shortRemaining < 12);
  el.taotie.classList.toggle("qi-low", state.shortRemaining < 25);
  el.taotie.classList.toggle("qi-mid", state.shortRemaining >= 25 && state.shortRemaining < 60);
  el.taotie.classList.toggle("qi-high", state.shortRemaining >= 60);
  renderLog();
}

function renderLog() {
  if (!state.scrolls.length) {
    el.feedLog.innerHTML = `<div class="log-item"><strong>暂无玉简</strong><span>拖入第一份灵材后，这里会出现记录。</span></div>`;
    return;
  }
  el.feedLog.innerHTML = "";
  state.scrolls.forEach((scroll) => {
    const item = document.createElement("div");
    item.className = "log-item";
    const saved = scroll.savedPath ? `<br>已入洞府：${scroll.savedPath}` : "";
    item.innerHTML = `<strong>${scroll.fileName}</strong><span>${formatBytes(scroll.size)} · ${new Date(scroll.createdAt).toLocaleString("zh-CN")}<br>${scroll.summary}${saved}</span>`;
    el.feedLog.appendChild(item);
  });
}

async function saveScrollToProject(scroll) {
  try {
    const response = await fetch("/api/feed", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        fileName: scroll.fileName,
        createdAt: scroll.createdAt,
        markdown: scroll.markdown
      })
    });
    if (!response.ok) return null;
    return await response.json();
  } catch {
    return null;
  }
}

function downloadLatestScroll() {
  const latest = state.scrolls[0];
  if (!latest) return;
  const blob = new Blob([latest.markdown], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${toStamp(new Date(latest.createdAt))}-${sanitizeName(latest.fileName)}.md`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function animateEat() {
  el.taotie.classList.remove("eating");
  requestAnimationFrame(() => el.taotie.classList.add("eating"));
}

function speak(text) {
  el.speech.textContent = text;
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function guessType(name) {
  const ext = name.split(".").pop()?.toLowerCase() || "unknown";
  return `${ext} 文件`;
}

function toStamp(date) {
  const pad = (number) => String(number).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}-${pad(date.getHours())}${pad(date.getMinutes())}${pad(date.getSeconds())}`;
}

function sanitizeName(name) {
  return name.replace(/[^\w\u4e00-\u9fa5.-]+/g, "-").slice(0, 80);
}
