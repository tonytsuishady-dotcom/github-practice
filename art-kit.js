const stateGrid = document.querySelector("#stateGrid");

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

function renderStates(states) {
  if (!stateGrid) return;
  stateGrid.innerHTML = states
    .map(
      (state) => `
        <article>
          <strong>${state.label}</strong>
          <code>${state.id}</code>
          <span><b>触发：</b>${state.trigger}</span>
          <span><b>视觉：</b>${state.visual}</span>
        </article>
      `,
    )
    .join("");
}

async function loadStates() {
  try {
    const response = await fetch("assets/art/states.json");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    renderStates(data.states || fallbackStates);
  } catch (_error) {
    renderStates(fallbackStates);
  }
}

loadStates();
