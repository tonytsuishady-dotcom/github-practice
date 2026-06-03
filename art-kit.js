const stateGrid = document.querySelector("#stateGrid");
const manifestGrid = document.querySelector("#manifestGrid");
const manifestStatus = document.querySelector("#manifestStatus");
const anchorGrid = document.querySelector("#anchorGrid");
const anchorStage = document.querySelector("#anchorStage");
const directionGoal = document.querySelector("#directionGoal");
const directionGrid = document.querySelector("#directionGrid");

const fallbackStates = [
  ["idle", "待机呼吸", "No recent input", "Neutral eyes, small breathing bounce"],
  ["typing", "敲玉简", "Keyboard or mouse input", "Alternating paw strike, small hit spark"],
  ["clicking", "被摸醒", "Pet click", "Happy face, lifted paws, +1 feedback"],
  ["eating", "吞灵材", "File feeding starts", "Open mouth, falling material"],
  ["digesting", "炼化中", "After feeding", "Belly glow and small cyan particles"],
  ["happy", "发光开心", "Useful result confirmed", "Gold arc, bright belly orb"],
  ["low_energy", "灵脉偏低", "Short-term usage below 20%", "Dim expression, red status color"],
  ["sleeping", "打坐犯困", "Long idle time", "Closed eyes and sleep marks"],
].map(([id, label, trigger, visual]) => ({ id, label, trigger, visual }));

function glyphMarkup(stateId, glyphData) {
  const glyph = glyphData?.glyphs?.[stateId];
  const palette = glyphData?.palette || {};
  if (!Array.isArray(glyph)) return "";
  const cells = glyph
    .flatMap((row) =>
      String(row)
        .split("")
        .map((key) => {
          const color = palette[key];
          const fill = !color || color === "transparent" ? "transparent" : color;
          return `<i style="--fill:${fill}"></i>`;
        }),
    )
    .join("");
  return `<div class="state-glyph" aria-hidden="true">${cells}</div>`;
}

function renderStates(states, glyphData = {}) {
  if (!stateGrid) return;
  stateGrid.innerHTML = states
    .map(
      (state) => `
        <article>
          ${glyphMarkup(state.id, glyphData)}
          <strong>${state.label}</strong>
          <code>${state.id}</code>
          <span><b>触发：</b>${state.trigger}</span>
          <span><b>视觉：</b>${state.visual}</span>
        </article>
      `,
    )
    .join("");
}

function renderManifest(assets) {
  if (!manifestGrid) return;
  manifestGrid.innerHTML = assets
    .map((asset) => {
      const href = asset.path.startsWith("../") ? asset.path : `assets/art/${asset.path}`;
      const isPreviewable = /\.(png|jpg|jpeg|webp|gif|svg)$/i.test(asset.path);
      const preview = isPreviewable
        ? `<img class="manifest-thumb" src="${href}" alt="${asset.id} preview" />`
        : `<div class="manifest-filetype">${asset.type}</div>`;
      return `
        <article>
          ${preview}
          <strong>${asset.id}</strong>
          <code>${asset.type}</code>
          <span><b>用途：</b>${asset.usage}</span>
          <a href="${href}">${asset.path}</a>
          <button class="copy-path" type="button" data-path="${asset.path}">复制路径</button>
        </article>
      `;
    })
    .join("");
}

function renderAnchors(anchors) {
  if (!anchorGrid || !anchorStage) return;
  anchorStage.querySelectorAll(".anchor-marker").forEach((node) => node.remove());
  anchorGrid.innerHTML = anchors
    .map((anchor) => {
      const accepts = Array.isArray(anchor.accepts) ? anchor.accepts.join(", ") : "";
      return `
        <article>
          <strong>${anchor.label}</strong>
          <code>${anchor.id}</code>
          <span><b>坐标：</b>${anchor.x}, ${anchor.y} · r${anchor.radius}</span>
          <span><b>可挂：</b>${accepts}</span>
          <span>${anchor.note}</span>
        </article>
      `;
    })
    .join("");
  anchors.forEach((anchor) => {
    const marker = document.createElement("span");
    marker.className = "anchor-marker";
    marker.textContent = anchor.label;
    marker.style.setProperty("--diameter", `${anchor.radius * 2}px`);
    marker.style.setProperty("--left", `${anchor.x - anchor.radius}px`);
    marker.style.setProperty("--top", `${anchor.y - anchor.radius}px`);
    marker.style.setProperty("--anchor-color", anchor.color || "#c8b983");
    anchorStage.append(marker);
  });
}

function renderDirection(direction) {
  if (!directionGrid) return;
  if (directionGoal && direction?.goal) {
    directionGoal.textContent = direction.goal;
  }
  const principles = direction?.principles || [];
  directionGrid.innerHTML = principles
    .map(
      (item) => `
        <article>
          <strong>${item.label}</strong>
          <code>${item.id}</code>
          <span>${item.summary}</span>
          <span><b>检查：</b>${item.check}</span>
        </article>
      `,
    )
    .join("");
}

async function copyText(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const helper = document.createElement("textarea");
  helper.value = text;
  helper.setAttribute("readonly", "");
  helper.style.position = "fixed";
  helper.style.opacity = "0";
  document.body.append(helper);
  helper.select();
  document.execCommand("copy");
  helper.remove();
}

manifestGrid?.addEventListener("click", async (event) => {
  const button = event.target.closest(".copy-path");
  if (!button) return;
  const path = button.dataset.path || "";
  try {
    await copyText(path);
    button.textContent = "已复制";
    if (manifestStatus) manifestStatus.textContent = `已复制：${path}`;
    window.setTimeout(() => {
      button.textContent = "复制路径";
    }, 1200);
  } catch (_error) {
    if (manifestStatus) manifestStatus.textContent = `复制失败，请手动选择：${path}`;
  }
});

async function loadStates() {
  try {
    const [statesResponse, glyphResponse] = await Promise.all([
      fetch("assets/art/states.json"),
      fetch("assets/art/state-glyphs.json"),
    ]);
    if (!statesResponse.ok) throw new Error(`HTTP ${statesResponse.status}`);
    const data = await statesResponse.json();
    const glyphData = glyphResponse.ok ? await glyphResponse.json() : {};
    renderStates(data.states || fallbackStates, glyphData);
  } catch (_error) {
    renderStates(fallbackStates);
  }
}

async function loadManifest() {
  try {
    const response = await fetch("assets/art/manifest.json");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    renderManifest(data.assets || []);
  } catch (_error) {
    renderManifest([
      {
        id: "manifest-fallback",
        path: "assets/art/manifest.json",
        type: "fallback",
        usage: "Use the local server to render the full resource list.",
      },
    ]);
  }
}

async function loadAnchors() {
  try {
    const response = await fetch("assets/art/cosmetic-anchors.json");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    renderAnchors(data.anchors || []);
  } catch (_error) {
    renderAnchors([]);
  }
}

async function loadDirection() {
  try {
    const response = await fetch("assets/art/art-direction.json");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    renderDirection(data);
  } catch (_error) {
    renderDirection({ principles: [] });
  }
}

loadStates();
loadManifest();
loadAnchors();
loadDirection();
