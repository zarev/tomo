function setLoadingState(isLoading) {
  const sendBtn = document.getElementById("send");
  const searchBtn = document.getElementById("search");
  sendBtn.disabled = isLoading;
  searchBtn.disabled = isLoading;
}

async function postJSON(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json();
}

const replyEl = document.getElementById("reply");
const spriteEl = document.getElementById("pet-sprite");
const inputEl = document.getElementById("input");
const memoriesEl = document.getElementById("memories");

function addMemoryRow(text) {
  const row = document.createElement("div");
  row.className = "memory-row";
  row.textContent = text;
  memoriesEl.prepend(row);
}

document.getElementById("send").addEventListener("click", async () => {
  const text = inputEl.value.trim();
  if (!text) {
    inputEl.focus();
    return;
  }
  replyEl.textContent = "...connecting";
  setLoadingState(true);
  try {
    const data = await postJSON("/talk", { text });
    replyEl.textContent = data.reply;
    spriteEl.textContent = data.reply?.charAt(0) || "9";
    addMemoryRow(`Saved memory: ${data.memory_id}`);
    inputEl.value = "";
  } catch (err) {
    replyEl.textContent = "Error: " + err.message;
  } finally {
    setLoadingState(false);
    inputEl.focus();
  }
});

document.getElementById("search").addEventListener("click", async () => {
  const text = inputEl.value.trim();
  if (!text) {
    inputEl.focus();
    return;
  }
  memoriesEl.innerHTML = "";
  addMemoryRow("Searching...");
  setLoadingState(true);
  try {
    const rows = await postJSON("/memories/search", { text, k: 5 });
    memoriesEl.innerHTML = "";
    if (!rows || rows.length === 0) {
      addMemoryRow("No memories found.");
      return;
    }
    for (const r of rows) {
      addMemoryRow(`${r.content} (dist=${r.distance?.toFixed?.(3) ?? r.distance})`);
    }
  } catch (err) {
    memoriesEl.innerHTML = "";
    addMemoryRow("Error: " + err.message);
  } finally {
    setLoadingState(false);
  }
});

inputEl.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    document.getElementById("send").click();
  }
});
