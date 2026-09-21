const $ = (id) => document.getElementById(id);
const state = { name: null, imgW: 0, imgH: 0, boxes: [], img: new Image() };

async function api(url, opts) {
  const r = await fetch(url, opts);
  if (!r.ok) throw new Error((await r.text()).slice(0, 300));
  return r;
}

async function loadMethods() {
  const { methods } = await (await api("/api/methods")).json();
  $("method").innerHTML = methods.map((m) =>
    `<option value="${m.id}">${m.label}</option>`).join("");
}

let searchTimer = null;
function fmtTaken(it) {
  if (it.taken) return it.taken.slice(0, 16).replace("T", " ");
  return "file " + new Date(it.mtime * 1000).toISOString().slice(0, 16).replace("T", " ");
}
async function loadPhotos() {
  const q = encodeURIComponent($("search").value);
  const df = $("datefrom").value, dt = $("dateto").value;
  let url = `/api/photos?search=${q}&limit=300`;
  if (df) url += `&date_from=${df}`;
  if (dt) url += `&date_to=${dt}`;
  const { items, total } = await (await api(url)).json();
  const list = $("filelist");
  list.innerHTML = "";
  const note = document.createElement("div");
  note.className = "hint"; note.textContent = `${total} photos, newest first`;
  list.appendChild(note);
  for (const it of items) {
    const d = document.createElement("div");
    d.title = it.name;
    const name = document.createElement("div");
    name.textContent = it.name;
    const when = document.createElement("div");
    when.className = "hint";
    when.textContent = fmtTaken(it);
    d.append(name, when);
    if (it.name === state.name) d.classList.add("active");
    d.onclick = () => selectPhoto(it.name);
    list.appendChild(d);
  }
}

function selectPhoto(name) {
  state.name = name; state.boxes = [];
  $("photoname").textContent = name;
  $("preview").removeAttribute("src");
  state.img.onload = () => {
    state.imgW = state.img.naturalWidth;
    state.imgH = state.img.naturalHeight;
    draw();
  };
  state.img.src = `/api/photo/${encodeURIComponent(name)}`;
  [...$("filelist").children].forEach((d) =>
    d.classList.toggle("active", d.title === name));
  renderBoxes();
}

function viewScale() {
  const canvas = $("canvas");
  const maxW = canvas.parentElement.clientWidth - 24;
  return Math.min(1, maxW / state.imgW);
}

function draw() {
  const canvas = $("canvas");
  if (!state.imgW) return;
  const s = viewScale();
  canvas.width = Math.round(state.imgW * s);
  canvas.height = Math.round(state.imgH * s);
  const ctx = canvas.getContext("2d");
  ctx.drawImage(state.img, 0, 0, canvas.width, canvas.height);
  ctx.strokeStyle = "red"; ctx.lineWidth = 2;
  state.boxes.forEach((b, i) => {
    ctx.strokeRect(b.x * s, b.y * s, b.w * s, b.h * s);
    ctx.fillStyle = "red";
    ctx.fillText(String(i + 1), b.x * s + 3, b.y * s + 13);
  });
  if (dragBox) {
    ctx.strokeStyle = "yellow";
    const { x, y, w, h } = dragBox;
    ctx.strokeRect(x * s, y * s, w * s, h * s);
  }
}

function renderBoxes() {
  const t = $("boxtable");
  t.innerHTML = "";
  state.boxes.forEach((b, i) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>#${i + 1}</td>` +
      ["x", "y", "w", "h"].map((k) =>
        `<td>${k}<input data-i="${i}" data-k="${k}" type="number" value="${b[k]}"></td>`).join("") +
      `<td><button data-del="${i}">✕</button></td>`;
    t.appendChild(tr);
  });
  t.querySelectorAll("input").forEach((inp) => {
    inp.onchange = () => {
      state.boxes[+inp.dataset.i][inp.dataset.k] = Math.max(0, +inp.value || 0);
      draw();
    };
  });
  t.querySelectorAll("[data-del]").forEach((btn) => {
    btn.onclick = () => { state.boxes.splice(+btn.dataset.del, 1); renderBoxes(); draw(); };
  });
}

let dragBox = null, dragAnchor = null;
function canvasPos(e) {
  const r = $("canvas").getBoundingClientRect();
  const s = viewScale();
  return { x: Math.round((e.clientX - r.left) / s), y: Math.round((e.clientY - r.top) / s) };
}
function rectFrom(a, p) {
  return { x: Math.max(0, Math.min(a.x, p.x)), y: Math.max(0, Math.min(a.y, p.y)),
           w: Math.abs(p.x - a.x), h: Math.abs(p.y - a.y) };
}
$("canvas").addEventListener("pointerdown", (e) => {
  if (!state.imgW) return;
  dragAnchor = canvasPos(e);
  dragBox = { ...dragAnchor, w: 0, h: 0 };
  $("canvas").setPointerCapture(e.pointerId);
});
$("canvas").addEventListener("pointermove", (e) => {
  if (!dragAnchor) return;
  dragBox = rectFrom(dragAnchor, canvasPos(e));
  draw();
});
$("canvas").addEventListener("pointerup", (e) => {
  if (!dragAnchor) return;
  const r = rectFrom(dragAnchor, canvasPos(e));
  dragAnchor = null; dragBox = null;
  if (r.w > 4 && r.h > 4) { state.boxes.push(r); renderBoxes(); }
  draw();
});

$("suggest").onclick = async () => {
  if (!state.name) return;
  const d = await (await api(`/api/regions/suggest?name=${encodeURIComponent(state.name)}`)).json();
  state.boxes = d.boxes || [];
  renderBoxes(); draw();
  $("status").textContent = `${state.boxes.length} suggested regions loaded.`;
};
$("clear").onclick = () => { state.boxes = []; renderBoxes(); draw(); };
$("search").oninput = () => { clearTimeout(searchTimer); searchTimer = setTimeout(loadPhotos, 250); };
$("datefrom").onchange = loadPhotos;
$("dateto").onchange = loadPhotos;
window.onresize = draw;

function payload() {
  return {
    name: state.name,
    regions: state.boxes,
    method: $("method").value,
    kernel_size: +$("kernel").value || 31,
    variance_threshold: +$("varth").value || 0,
    inpaint_radius: +$("radius").value || 3,
  };
}

$("previewBtn").onclick = async () => {
  if (!state.name || !state.boxes.length) { $("status").textContent = "Pick a photo and draw a region first."; return; }
  $("status").textContent = "Rendering preview…";
  try {
    const r = await api("/api/preview", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload()) });
    $("preview").src = URL.createObjectURL(await r.blob());
    $("status").textContent = "Preview ready. Save writes a _fix copy next to the original.";
  } catch (e) { $("status").textContent = "Preview failed: " + e.message; }
};

$("saveBtn").onclick = async () => {
  if (!state.name || !state.boxes.length) { $("status").textContent = "Pick a photo and draw a region first."; return; }
  $("status").textContent = "Saving _fix copy…";
  try {
    const d = await (await api("/api/save", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload()) })).json();
    $("status").textContent = `Saved ${d.saved} (EXIF ${d.exif_copied ? "preserved" : "not found"}). Original untouched.`;
  } catch (e) { $("status").textContent = "Save failed: " + e.message; }
};

loadMethods().then(loadPhotos).catch((e) => { $("filelist").textContent = "Failed to load: " + e.message; });
