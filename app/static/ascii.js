const $ = (id) => document.getElementById(id);
let frames = [], timer = null, idx = 0, jobId = null;

async function api(url, opts) {
  const r = await fetch(url, opts);
  if (!r.ok) throw new Error((await r.text()).slice(0, 300));
  return r;
}

async function loadJobs() {
  const { jobs } = await (await api("/api/ascii/jobs")).json();
  const box = $("jobs");
  box.innerHTML = "";
  if (!jobs.length) box.innerHTML = '<p class="hint">No conversions yet.</p>';
  for (const j of jobs) {
    const d = document.createElement("div");
    d.className = "row";
    d.innerHTML = `<button data-job="${j.id}">${j.source} (${j.n_frames}f)</button>
      <button data-del="${j.id}">✕</button>`;
    box.appendChild(d);
  }
  box.querySelectorAll("[data-job]").forEach((b) => { b.onclick = () => loadJob(b.dataset.job); });
  box.querySelectorAll("[data-del]").forEach((b) => {
    b.onclick = async () => { await api(`/api/ascii/jobs/${b.dataset.del}`, { method: "DELETE" }); loadJobs(); };
  });
}

async function loadJob(id) {
  const j = await (await api(`/api/ascii/jobs/${id}`)).json();
  stop();
  jobId = id; frames = j.frames; idx = 0;
  $("jobtitle").textContent = `${j.source} — ${j.n_frames} frames`;
  $("download").href = `/api/ascii/jobs/${id}/download`;
  show(0);
}

function show(i) {
  if (!frames.length) return;
  idx = (i + frames.length) % frames.length;
  $("screen").textContent = frames[idx];
}

function play() {
  stop();
  const fps = Math.max(1, Math.min(60, +$("fps").value || 12));
  timer = setInterval(() => show(idx + 1), 1000 / fps);
}
function stop() { if (timer) clearInterval(timer); timer = null; }

$("play").onclick = play;
$("stop").onclick = stop;

$("convert").onclick = async () => {
  const f = $("file").files[0];
  if (!f) { $("status").textContent = "Choose an mp4 first."; return; }
  $("status").textContent = "Converting… (large videos take a while)";
  const fd = new FormData();
  fd.append("file", f);
  fd.append("width", $("width").value);
  fd.append("max_frames", $("maxframes").value);
  try {
    const j = await (await api("/api/ascii/jobs", { method: "POST", body: fd })).json();
    $("status").textContent = `Done: ${j.n_frames} frames.`;
    await loadJobs();
    loadJob(j.id);
  } catch (e) { $("status").textContent = "Convert failed: " + e.message; }
};

loadJobs().catch((e) => { $("jobs").textContent = "Failed to load: " + e.message; });
