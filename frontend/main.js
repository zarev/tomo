const stageEl = document.getElementById("stage");
const peopleEl = document.getElementById("people");
const personaEl = document.getElementById("persona");
const companyEl = document.getElementById("company");
const stepsEl = document.getElementById("steps");
const outputBody = document.getElementById("output-body");
const summaryEl = document.getElementById("summary");
const progressEl = document.getElementById("progress");
const downloadEl = document.getElementById("download");

const runButton = document.getElementById("run");
const saveProfileButton = document.getElementById("save-profile");
const savePromptsButton = document.getElementById("save-prompts");

let currentSteps = [];

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
  const hasHeader = ["name", "title", "company", "email"].some((key) => headerTokens.includes(key));
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
  return people;
}

function updateOutput(steps, finalPeople, csvUrl) {
  outputBody.innerHTML = "";
  progressEl.innerHTML = "";

  if (!steps.length) {
    summaryEl.textContent = "No steps run.";
    return;
  }

  summaryEl.textContent = `Pipeline complete. ${finalPeople.length} targets ready for outbound.`;

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

  finalPeople.forEach((person) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${person.name || ""}</td>
      <td>${person.title || ""}</td>
      <td>${person.company || ""}</td>
      <td>${person.email || ""}</td>
      <td>${person.location || ""}</td>
    `;
    outputBody.appendChild(row);
  });

  if (csvUrl) {
    downloadEl.innerHTML = `<a href="${csvUrl}" class="button secondary" target="_blank">Download CSV</a>`;
  } else {
    downloadEl.innerHTML = "";
  }
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
}

saveProfileButton.addEventListener("click", async () => {
  saveProfileButton.disabled = true;
  try {
    await fetchJSON("/api/profile", {
      method: "PUT",
      body: JSON.stringify({
        persona: personaEl.value,
        company: companyEl.value,
      }),
    });
    saveProfileButton.textContent = "Saved";
    setTimeout(() => {
      saveProfileButton.textContent = "Save profile";
    }, 1200);
  } catch (error) {
    alert(`Failed to save profile: ${error.message}`);
  } finally {
    saveProfileButton.disabled = false;
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

runButton.addEventListener("click", async () => {
  runButton.disabled = true;
  try {
    const people = parsePeople(peopleEl.value);
    if (!people.length) {
      alert("Please paste at least one person into the list.");
      return;
    }

    const steps = collectPrompts();
    const payload = {
      people,
      stage: stageEl.value,
      prompts: steps,
    };

    const data = await fetchJSON("/api/pipeline/run", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    updateOutput(data.steps, data.final_people, data.csv_download_url);
  } catch (error) {
    alert(`Pipeline failed: ${error.message}`);
  } finally {
    runButton.disabled = false;
  }
});

loadInitial().catch((error) => {
  console.error(error);
  alert("Failed to load initial data.");
});
