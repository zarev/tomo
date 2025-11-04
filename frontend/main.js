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

document.getElementById("send").addEventListener("click", async () => {
  const text = document.getElementById("input").value;
  const replyEl = document.getElementById("reply");
  replyEl.textContent = "...waiting";
  try {
    const data = await postJSON('/talk', { text });
    replyEl.textContent = data.reply;
    // show memory id
    const mems = document.getElementById('memories');
    const row = document.createElement('div');
    row.textContent = `Saved memory: ${data.memory_id}`;
    mems.prepend(row);
  } catch (err) {
    replyEl.textContent = 'Error: ' + err.message;
  }
});

document.getElementById("search").addEventListener("click", async () => {
  const text = document.getElementById("input").value;
  const mems = document.getElementById('memories');
  mems.textContent = 'Searching...';
  try {
    const rows = await postJSON('/memories/search', { text, k: 5 });
    mems.innerHTML = '';
    if (!rows || rows.length === 0) {
      mems.textContent = 'No memories found.';
      return;
    }
    for (const r of rows) {
      const el = document.createElement('div');
      el.textContent = `${r.content} (dist=${r.distance?.toFixed?.(3) ?? r.distance})`;
      mems.appendChild(el);
    }
  } catch (err) {
    mems.textContent = 'Error: ' + err.message;
  }
});
