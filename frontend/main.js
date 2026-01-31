const peopleEl = document.getElementById("people");
const peopleFileEl = document.getElementById("people-file");
const personaEl = document.getElementById("persona");
const personaPreviewEl = document.getElementById("persona-preview");
const companyEl = document.getElementById("company");
const companyFileEl = document.getElementById("company-file");
const companyPopulateButton = document.getElementById("company-populate");
const companyPreviewEl = document.getElementById("company-preview");
const stepsEl = document.getElementById("steps");
const outputBody = document.getElementById("output-body");
const summaryEl = document.getElementById("summary");
const progressEl = document.getElementById("progress");
const downloadEl = document.getElementById("download");
const markdownOutputEl = document.getElementById("markdown-output");
const stepResultsEl = document.getElementById("step-results");
const pipelineScreenEl = document.getElementById("pipeline-screen");
const pipelineLoadingButton = document.getElementById("pipeline-loading");
const pipelineTemplateEl = document.getElementById("pipeline-template");
const rawResponseEl = document.getElementById("raw-response");
const pipelineStepsOverlayEl = document.getElementById("pipeline-steps-overlay");
const pipelineStatusEl = document.getElementById("pipeline-status");
const pipelineErrorEl = document.getElementById("pipeline-error");
const pipelineCloseButton = document.getElementById("pipeline-close");
const pipelineRerunButton = document.getElementById("pipeline-rerun");
const stepProgressEl = document.getElementById("step-progress");
const setupSteps = Array.from(document.querySelectorAll(".setup-step"));
const stepNext1 = document.getElementById("step-next-1");
const stepNext2 = document.getElementById("step-next-2");
const stepBack2 = document.getElementById("step-back-2");
const stepBack3 = document.getElementById("step-back-3");

const runButton = document.getElementById("run");
const savePromptsButton = document.getElementById("save-prompts");
const drawer = document.getElementById("drawer");
const drawerOverlay = document.getElementById("drawer-overlay");
const drawerToggle = document.getElementById("menu-toggle");
const drawerClose = document.getElementById("drawer-close");

let currentSteps = [];
let currentSetupStep = 1;
let pipelineProgressTimer = null;

function buildTemplateMarkdown(people) {
  const topTen = people.slice(0, 10);
  const lines = [];
  lines.push("## Top 10 leads (draft)");
  lines.push("Use this template to kick off outreach once the pipeline completes.");
  lines.push("");
  lines.push("| Company | Lead | Title | Email |");
  lines.push("| --- | --- | --- | --- |");
  topTen.forEach((person) => {
    lines.push(
      `| ${person.company || ""} | ${person.name || ""} | ${person.title || ""} | ${person.email || ""} |`,
    );
  });
  lines.push("");
  lines.push("### Email draft");
  lines.push("Hi {{first_name}},");
  lines.push("");
  lines.push("Noticed {{company}} is scaling outbound in {{industry}}. We help teams like yours secure qualified meetings without hiring a full SDR team.");
  lines.push("");
  lines.push("Open to a 15‑minute chat next week to share benchmarks and see if Throxy is a fit?");
  lines.push("");
  lines.push("— {{sender_name}}");
  return lines.join("\n");
}

function renderStepDetails(steps, targetEl, statusMap = {}) {
  if (!targetEl) return;
  targetEl.innerHTML = "";
  if (!steps || !steps.length) return;

  const limitList = (list = []) => list.slice(0, 5);
  const allFields = [
    "name",
    "title",
    "company",
    "email",
    "location",
    "industry",
    "notes",
    "score",
    "score_normalized",
    "company_rank",
    "reason",
  ];
  const renderTable = (rows) => {
    const header = `<tr>${allFields.map((field) => `<th>${escapeHTML(field)}</th>`).join("")}</tr>`;
    const body = rows.map((row) => (
      `<tr>${allFields.map((field) => `<td>${escapeHTML(row?.[field] ?? "")}</td>`).join("")}</tr>`
    )).join("");
    return `<table class="table">${header}${body || ""}</table>`;
  };
  steps.forEach((step) => {
    const details = document.createElement("details");
    details.className = "md-collapse";
    const summary = document.createElement("summary");
    const status = statusMap[step.step_id] || statusMap[step.title] || "";
    const statusLabel = status ? ` — ${status}` : "";
    const counts = Number.isFinite(step.before_count) ? `${step.before_count} → ${step.after_count}` : "";
    const countLabel = counts ? `: ${counts}` : "";
    summary.textContent = `${step.title}${countLabel}${statusLabel}`;
    details.appendChild(summary);

    const container = document.createElement("div");
    container.className = "md-preview";
    const kept = limitList(step.kept || []);
    const removed = limitList(step.removed || []);
    const hasCounts = Number.isFinite(step.before_count) || Number.isFinite(step.after_count);
    if (!hasCounts && (!kept.length && !removed.length)) {
      container.innerHTML = "<em>Awaiting results…</em>";
    } else {
      const keptJustification = step.kept_justification || "";
      const removedJustification = step.removed_justification || "";
      container.innerHTML = `
        <div style="margin-bottom: 8px"><strong>Kept (sample)</strong>: ${kept.length}</div>
        <div class="muted" style="margin-bottom: 8px">${escapeHTML(keptJustification)}</div>
        ${renderTable(kept)}
        <div style="margin-top: 16px; margin-bottom: 8px"><strong>Removed (sample)</strong>: ${removed.length}</div>
        <div class="muted" style="margin-bottom: 8px">${escapeHTML(removedJustification)}</div>
        ${renderTable(removed)}
      `;
    }
    details.appendChild(container);
    targetEl.appendChild(details);
  });
}

function orderedStepList() {
  const order = ["stage-fit", "persona-fit", "company-fit", "final-review"];
  return order.map((stepId) => {
    const match = currentSteps.find((step) => step.step_id === stepId);
    return {
      step_id: stepId,
      title: match ? match.title : stepId.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
    };
  });
}

function renderRunningStatus(activeIndex) {
  const steps = orderedStepList();
  const statusMap = {};
  steps.forEach((step, idx) => {
    if (idx < activeIndex) {
      statusMap[step.step_id] = "Completed";
    } else if (idx === activeIndex) {
      statusMap[step.step_id] = "Running";
    } else {
      statusMap[step.step_id] = "Queued";
    }
  });

  renderStepDetails(
    steps.map((step) => ({
      ...step,
      before_count: undefined,
      after_count: undefined,
      kept: [],
      removed: [],
    })),
    pipelineStepsOverlayEl,
    statusMap,
  );
}

function showPipelineScreen(people) {
  if (!pipelineScreenEl || !pipelineTemplateEl) return;
  pipelineScreenEl.classList.remove("hidden");
  if (pipelineStatusEl) {
    pipelineStatusEl.textContent = "We are ranking the best-fit leads per company using your persona and context.";
  }
  if (pipelineErrorEl) {
    pipelineErrorEl.textContent = "";
  }
  const markdown = buildTemplateMarkdown(people || []);
  const html = (window.marked && window.marked.parse) ? window.marked.parse(markdown) : markdown;
  pipelineTemplateEl.innerHTML = html;
  if (pipelineLoadingButton) {
    pipelineLoadingButton.classList.add("loading");
    pipelineLoadingButton.innerHTML = "";
    const label = document.createElement("span");
    label.textContent = "Pipeline running…";
    const bar = document.createElement("span");
    bar.className = "progress-bar";
    const fill = document.createElement("span");
    fill.className = "progress-fill";
    bar.appendChild(fill);
    pipelineLoadingButton.appendChild(label);
    pipelineLoadingButton.appendChild(bar);
  }
  if (pipelineStepsOverlayEl) {
    pipelineStepsOverlayEl.innerHTML = "";
  }
}

function updatePipelineTemplate(people) {
  if (!pipelineTemplateEl) return;
  const markdown = buildTemplateMarkdown(people || []);
  const html = (window.marked && window.marked.parse) ? window.marked.parse(markdown) : markdown;
  pipelineTemplateEl.innerHTML = html;
}

function hidePipelineScreen() {
  if (!pipelineScreenEl) return;
  pipelineScreenEl.classList.add("hidden");
}

async function fetchJSON(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json();
}

function escapeHTML(value) {
  if (value === undefined || value === null) return "";
  return String(value).replace(/[&<>"']/g, (char) => {
    switch (char) {
      case "&":
        return "&amp;";
      case "<":
        return "&lt;";
      case ">":
        return "&gt;";
      case '"':
        return "&quot;";
      case "'":
        return "&#39;";
      default:
        return char;
    }
  });
}

function formatScore(value) {
  if (value === undefined || value === null) return "";
  const number = Number(value);
  if (!Number.isFinite(number)) return "";
  return number.toFixed(2);
}

function formatStageLabel(label) {
  if (!label) return "";
  return label
    .replace(/-/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function buildStepCard(step) {
  const wrapper = document.createElement("div");
  wrapper.className = "pipeline-step";
  wrapper.dataset.stepId = step.step_id;

  const header = document.createElement("div");
  header.className = "step-header";
  const title = document.createElement("div");
  title.innerHTML = `<strong>${step.title}</strong>`;
  const badge = document.createElement("span");
  badge.className = "badge";
  badge.textContent = "Ready";
  header.appendChild(title);
  header.appendChild(badge);

  const label = document.createElement("label");
  label.textContent = "Prompt";
  label.setAttribute("for", `prompt-${step.step_id}`);

  const textarea = document.createElement("textarea");
  textarea.id = `prompt-${step.step_id}`;
  textarea.value = step.prompt || "";

  wrapper.appendChild(header);
  wrapper.appendChild(label);
  wrapper.appendChild(textarea);
  return wrapper;
}

function renderSteps(steps) {
  stepsEl.innerHTML = "";
  steps.forEach((step) => stepsEl.appendChild(buildStepCard(step)));
}

function showSetupStep(stepNumber) {
  currentSetupStep = stepNumber;
  setupSteps.forEach((step) => {
    const stepIndex = Number(step.dataset.step || 0);
    if (stepIndex === stepNumber) {
      step.hidden = false;
    } else {
      step.hidden = true;
    }
  });
  if (stepProgressEl) {
    stepProgressEl.textContent = `Step ${stepNumber} of 3`;
  }
}

function renderPersonaPreview(text) {
  if (!personaPreviewEl) return;
  const html = (window.marked && window.marked.parse) ? window.marked.parse(text || "") : (text || "");
  personaPreviewEl.innerHTML = html;
}

function renderCompanyPreview(text) {
  if (!companyPreviewEl) return;
  const html = (window.marked && window.marked.parse) ? window.marked.parse(text || "") : (text || "");
  companyPreviewEl.innerHTML = html;
}

function renderMarkdownOutput(steps, finalPeople, stageLabel) {
  if (!markdownOutputEl) return;
  if (!steps.length) {
    markdownOutputEl.innerHTML = "";
    return;
  }

  const escapeCell = (value = "") => String(value || "").replace(/\|/g, "\\|");
  const lines = [];
  lines.push("## Pipeline results");
  steps.forEach((step) => {
    lines.push(`- **${step.title}**: ${step.before_count} → ${step.after_count}`);
  });

  lines.push("");
  const stageText = stageLabel ? formatStageLabel(stageLabel) : "Unknown";
  lines.push(`**Inferred stage:** ${stageText}`);
  lines.push("");
  lines.push(`## Final targets (${finalPeople.length})`);
  if (finalPeople.length) {
    lines.push("| Company | Name | Title | Score | Rank | Reason |");
    lines.push("| --- | --- | --- | --- | --- | --- |");
    finalPeople.forEach((person) => {
      const scoreText = formatScore(person.score);
      const reasonText = escapeCell(person.reason || "");
      lines.push(
        `| ${escapeCell(person.company)} | ${escapeCell(person.name)} | ${escapeCell(person.title)} | ${scoreText} | ${escapeCell(person.company_rank || "")} | ${reasonText} |`,
      );
    });
  } else {
    lines.push("No targets kept.");
  }

  const markdown = lines.join("\n");
  const html = (window.marked && window.marked.parse) ? window.marked.parse(markdown) : markdown;
  markdownOutputEl.innerHTML = html;
}

function collectPrompts() {
  return currentSteps.map((step) => {
    const textarea = document.getElementById(`prompt-${step.step_id}`);
    return {
      step_id: step.step_id,
      title: step.title,
      prompt: textarea ? textarea.value : step.prompt,
    };
  });
}

function parsePeople(input) {
  const lines = input
    .split(/\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  if (lines.length === 0) return [];

  const hasComma = lines.some((line) => line.includes(","));
  const headerTokens = lines[0].split(",").map((token) => token.trim().toLowerCase());
  const hasHeader = ["name", "title", "company", "email"].some((key) =>
    headerTokens.some((token) => token === key || token.includes(key)),
  );
  let startIndex = 0;
  let headers = ["name", "title", "company", "email", "location", "industry", "notes"];

  if (hasComma && hasHeader) {
    headers = headerTokens;
    startIndex = 1;
  }

  const people = [];
  for (let i = startIndex; i < lines.length; i += 1) {
    const line = lines[i];
    if (!hasComma) {
      people.push({ name: line, title: "", company: "", email: "", location: "", industry: "", notes: "" });
      continue;
    }
    const values = line.split(",").map((value) => value.trim());
    const person = {
      name: values[0] || "",
      title: values[1] || "",
      company: values[2] || "",
      email: values[3] || "",
      location: values[4] || "",
      industry: values[5] || "",
      notes: values.slice(6).join(", ").trim(),
    };
    headers.forEach((header, idx) => {
      if (idx < values.length) {
        person[header] = values[idx];
      }
    });
    people.push(person);
  }
  if (people.length) {
    const first = people[0];
    const headerish = ["name", "title", "company", "email"].every((key) => {
      const value = String(first[key] || "").trim().toLowerCase();
      return value === key || value.includes(key);
    });
    if (headerish) {
      return people.slice(1);
    }
  }
  return people;
}

function updateOutput(steps, finalPeople, csvUrl, stageLabel) {
  outputBody.innerHTML = "";
  progressEl.innerHTML = "";
  if (stepResultsEl) stepResultsEl.innerHTML = "";
  if (rawResponseEl) rawResponseEl.textContent = "";

  if (!steps.length) {
    summaryEl.textContent = "No steps run.";
    renderMarkdownOutput([], [], stageLabel);
    return;
  }

  const stageText = stageLabel ? `Stage inferred: ${formatStageLabel(stageLabel)}. ` : "";
  const targetText = finalPeople.length
    ? `${finalPeople.length} top target${finalPeople.length === 1 ? "" : "s"} ready for outbound.`
    : "No recommended targets after ranking.";
  summaryEl.textContent = `${stageText}${targetText}`;

  steps.forEach((step) => {
    const pill = document.createElement("span");
    pill.textContent = `${step.title}: ${step.before_count} → ${step.after_count}`;
    progressEl.appendChild(pill);

    const stepCard = stepsEl.querySelector(`[data-step-id="${step.step_id}"]`);
    if (stepCard) {
      const badge = stepCard.querySelector(".badge");
      if (badge) {
        badge.textContent = `${step.after_count} kept`;
      }
    }
  });

  const statusMap = {};
  steps.forEach((step) => {
    statusMap[step.step_id] = "Completed";
  });
  renderStepDetails(steps, stepResultsEl, statusMap);
  renderStepDetails(steps, pipelineStepsOverlayEl, statusMap);

  finalPeople.forEach((person) => {
    const row = document.createElement("tr");
    const reasonSafe = escapeHTML(person.reason || "").replace(/\n/g, "<br>");
    row.innerHTML = `
      <td>${escapeHTML(person.name || "")}</td>
      <td>${escapeHTML(person.title || "")}</td>
      <td>${escapeHTML(person.company || "")}</td>
      <td>${escapeHTML(person.email || "")}</td>
      <td>${escapeHTML(person.location || "")}</td>
      <td>${formatScore(person.score)}</td>
      <td>${person.company_rank || ""}</td>
      <td>${reasonSafe}</td>
    `;
    outputBody.appendChild(row);
  });

  if (csvUrl) {
    downloadEl.innerHTML = `<a href="${csvUrl}" class="button secondary" target="_blank">Download CSV</a>`;
  } else {
    downloadEl.innerHTML = "";
  }

  renderMarkdownOutput(steps, finalPeople, stageLabel);
}

function showButtonLoading(button, activeLabel = "Working...") {
  const previous = { html: button.innerHTML, disabled: button.disabled };
  button.disabled = true;
  button.classList.add("loading");
  button.innerHTML = "";

  const label = document.createElement("span");
  label.textContent = activeLabel;
  const bar = document.createElement("span");
  bar.className = "progress-bar";
  const fill = document.createElement("span");
  fill.className = "progress-fill";
  bar.appendChild(fill);

  button.appendChild(label);
  button.appendChild(bar);

  return () => {
    button.classList.remove("loading");
    button.innerHTML = previous.html;
    button.disabled = previous.disabled;
  };
}

async function loadInitial() {
  const [promptData, profileData] = await Promise.all([
    fetchJSON("/api/prompts"),
    fetchJSON("/api/profile"),
  ]);

  currentSteps = promptData.steps;
  renderSteps(currentSteps);
  personaEl.value = profileData.persona || "";
  companyEl.value = profileData.company || "";
  renderPersonaPreview(personaEl.value);
  renderCompanyPreview(companyEl.value);
}

function openDrawer() {
  drawer.classList.add("open");
  drawerOverlay.classList.add("open");
  drawerToggle.setAttribute("aria-expanded", "true");
  drawer.setAttribute("aria-hidden", "false");
}

function closeDrawer() {
  drawer.classList.remove("open");
  drawerOverlay.classList.remove("open");
  drawerToggle.setAttribute("aria-expanded", "false");
  drawer.setAttribute("aria-hidden", "true");
}

drawerToggle.addEventListener("click", () => {
  const isOpen = drawer.classList.contains("open");
  if (isOpen) {
    closeDrawer();
  } else {
    openDrawer();
  }
});

drawerClose.addEventListener("click", closeDrawer);
drawerOverlay.addEventListener("click", closeDrawer);
personaEl.addEventListener("input", () => renderPersonaPreview(personaEl.value));
companyEl.addEventListener("input", () => renderCompanyPreview(companyEl.value));

if (stepNext1) {
  stepNext1.addEventListener("click", () => {
    if (!peopleEl.value.trim()) {
      alert("Please paste at least one person into the list.");
      return;
    }
    showSetupStep(2);
  });
}

if (stepNext2) {
  stepNext2.addEventListener("click", () => {
    showSetupStep(3);
  });
}

if (stepBack2) {
  stepBack2.addEventListener("click", () => showSetupStep(1));
}

if (stepBack3) {
  stepBack3.addEventListener("click", () => showSetupStep(2));
}

companyFileEl.addEventListener("change", async (event) => {
  const file = event.target.files && event.target.files[0];
  if (!file) return;
  try {
    const text = await file.text();
    companyEl.value = text;
    renderCompanyPreview(text);
  } catch (error) {
    alert("Failed to read company file.");
  }
});

companyPopulateButton.addEventListener("click", async () => {
  const stopLoading = showButtonLoading(companyPopulateButton, "Populating...");
  try {
    const data = await fetchJSON("/api/company/auto", {
      method: "POST",
      body: JSON.stringify({
        persona: personaEl.value,
      }),
    });
    if (data.company) {
      companyEl.value = data.company;
      renderCompanyPreview(data.company);
    }
  } catch (error) {
    alert(`Failed to populate company profile: ${error.message}`);
  } finally {
    stopLoading();
  }
});

peopleFileEl.addEventListener("change", async (event) => {
  const file = event.target.files && event.target.files[0];
  if (!file) return;
  try {
    const text = await file.text();
    peopleEl.value = text;
  } catch (error) {
    alert("Failed to read file.");
  }
});

savePromptsButton.addEventListener("click", async () => {
  savePromptsButton.disabled = true;
  try {
    const steps = collectPrompts();
    await fetchJSON("/api/prompts", {
      method: "PUT",
      body: JSON.stringify({ steps }),
    });
    savePromptsButton.textContent = "Saved";
    setTimeout(() => {
      savePromptsButton.textContent = "Save prompts";
    }, 1200);
  } catch (error) {
    alert(`Failed to save prompts: ${error.message}`);
  } finally {
    savePromptsButton.disabled = false;
  }
});

async function handleRunPipeline() {
  const stopLoading = showButtonLoading(runButton, "Running pipeline...");
  try {
    const people = parsePeople(peopleEl.value).slice(0, 100);
    if (!people.length) {
      alert("Please paste at least one person into the list.");
      return;
    }

    showPipelineScreen(people);
    let activeIndex = 0;
    renderRunningStatus(activeIndex);
    if (pipelineProgressTimer) {
      clearInterval(pipelineProgressTimer);
    }
    pipelineProgressTimer = setInterval(() => {
      activeIndex = Math.min(activeIndex + 1, orderedStepList().length - 1);
      renderRunningStatus(activeIndex);
    }, 2500);

    const steps = collectPrompts();
    const payload = {
      people,
      prompts: steps,
    };

    const data = await fetchJSON("/api/pipeline/run", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    updateOutput(data.steps, data.final_people, data.csv_download_url, data.stage);
    if (rawResponseEl) {
      rawResponseEl.textContent = JSON.stringify(data, null, 2);
    }
    updatePipelineTemplate(data.final_people || []);
    if (pipelineStatusEl) {
      pipelineStatusEl.textContent = "Pipeline complete. Review each step below.";
    }
    if (pipelineLoadingButton) {
      pipelineLoadingButton.classList.remove("loading");
      pipelineLoadingButton.textContent = "Pipeline complete";
    }
  } catch (error) {
    alert(`Pipeline failed: ${error.message}`);
    if (pipelineErrorEl) {
      pipelineErrorEl.textContent = `Pipeline failed: ${error.message}`;
    }
    if (pipelineLoadingButton) {
      pipelineLoadingButton.classList.remove("loading");
      pipelineLoadingButton.textContent = "Pipeline failed";
    }
  } finally {
    if (pipelineProgressTimer) {
      clearInterval(pipelineProgressTimer);
      pipelineProgressTimer = null;
    }
    stopLoading();
  }
}

runButton.addEventListener("click", handleRunPipeline);
if (pipelineRerunButton) {
  pipelineRerunButton.addEventListener("click", handleRunPipeline);
}

loadInitial().catch((error) => {
  console.error(error);
  alert("Failed to load initial data.");
});

if (pipelineCloseButton) {
  pipelineCloseButton.addEventListener("click", hidePipelineScreen);
}

showSetupStep(1);
