const $ = (id) => document.getElementById(id);

const drop = $("drop");
const fileinput = $("fileinput");
const filenameEl = $("filename");
const runbtn = $("runbtn");
const statusbox = $("statusbox");
const statustext = $("statustext");
const statuspct = $("statuspct");
const barfill = $("barfill");
const hint = $("hint");
const resultbox = $("resultbox");
const output = $("output");
const copybtn = $("copybtn");
const resultmeta = $("resultmeta");
const footmsg = $("footmsg");

let selectedFile = null;
let polling = null;
let OPTS = null; // /api/options payload

// --- Options panel --------------------------------------------------------
const optModel = $("opt-model");
const optCompute = $("opt-compute");
const optLanguage = $("opt-language");
const optBeam = $("opt-beam");
const optVad = $("opt-vad");
const hintModel = $("hint-model");
const hintCompute = $("hint-compute");

async function loadOptions() {
  try {
    OPTS = await (await fetch("/api/options")).json();
  } catch {
    footmsg.textContent = "OPTIONS LOAD FAILED";
    return;
  }
  for (const [name, meta] of Object.entries(OPTS.models)) {
    optModel.append(new Option(`${name}  ·  ${meta.params}  ·  ${meta.rel_speed}`, name));
  }
  for (const [name, desc] of Object.entries(OPTS.compute_types)) {
    optCompute.append(new Option(name, name));
  }
  for (const [code, label] of Object.entries(OPTS.languages)) {
    optLanguage.append(new Option(label, code));
  }
  optModel.addEventListener("change", refreshHints);
  optCompute.addEventListener("change", refreshHints);
  applyDefaults();
}

function applyDefaults() {
  if (!OPTS) return;
  const d = OPTS.defaults;
  optModel.value = d.model_size;
  optCompute.value = d.compute_type;
  optLanguage.value = d.language;
  optBeam.value = d.beam_size;
  optVad.checked = d.vad;
  refreshHints();
}

function refreshHints() {
  if (!OPTS) return;
  const m = OPTS.models[optModel.value];
  hintModel.textContent = m ? `${m.ram} RAM · ${m.blurb}` : "";
  hintCompute.textContent = OPTS.compute_types[optCompute.value] || "";
  $("sysmsg").textContent = `SYS://${optModel.value} · ${optCompute.value} · cpu·8t`;
}

$("resetbtn").addEventListener("click", applyDefaults);
loadOptions();

// --- File selection -------------------------------------------------------
drop.addEventListener("click", () => fileinput.click());
fileinput.addEventListener("change", (e) => setFile(e.target.files[0]));

["dragenter", "dragover"].forEach((ev) =>
  drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("drag"); })
);
["dragleave", "drop"].forEach((ev) =>
  drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("drag"); })
);
drop.addEventListener("drop", (e) => {
  if (e.dataTransfer.files.length) setFile(e.dataTransfer.files[0]);
});

function setFile(file) {
  if (!file) return;
  selectedFile = file;
  const mb = (file.size / 1048576).toFixed(1);
  filenameEl.textContent = `▸ ${file.name}  ·  ${mb} MB`;
  runbtn.disabled = false;
  footmsg.textContent = "FILE LOADED";
}

// --- Run ------------------------------------------------------------------
runbtn.addEventListener("click", async () => {
  if (!selectedFile) return;
  runbtn.disabled = true;
  resultbox.classList.add("hidden");
  statusbox.classList.remove("hidden");
  setStatus("UPLOADING…", 0);
  hint.textContent = "First run downloads the model (~3 GB) once, then it's cached.";
  footmsg.textContent = "RUNNING";

  try {
    const fd = new FormData();
    fd.append("file", selectedFile);
    fd.append("model_size", optModel.value);
    fd.append("compute_type", optCompute.value);
    fd.append("language", optLanguage.value);
    fd.append("beam_size", optBeam.value || "5");
    fd.append("vad", optVad.checked ? "true" : "false");
    const res = await fetch("/api/transcribe", { method: "POST", body: fd });
    if (!res.ok) throw new Error(`upload failed (${res.status})`);
    const { job_id } = await res.json();
    poll(job_id);
  } catch (err) {
    fail(err.message);
  }
});

function poll(jobId) {
  clearInterval(polling);
  polling = setInterval(async () => {
    try {
      const res = await fetch(`/api/progress/${jobId}`);
      if (!res.ok) throw new Error("lost job");
      const job = await res.json();

      if (job.status === "queued") setStatus("LOADING MODEL…", 0.02);
      else if (job.status === "transcribing") {
        const pct = job.progress || 0;
        setStatus("TRANSCRIBING…", pct);
        hint.textContent = "Decoding audio on CPU (large-v3 · int8). Long files take a few minutes.";
      } else if (job.status === "done") {
        clearInterval(polling);
        finish(job.result);
      } else if (job.status === "error") {
        clearInterval(polling);
        fail(job.error || "unknown error");
      }
    } catch (err) {
      clearInterval(polling);
      fail(err.message);
    }
  }, 700);
}

function setStatus(text, pct) {
  statustext.textContent = text;
  const p = Math.round((pct || 0) * 100);
  statuspct.textContent = `${p}%`;
  barfill.style.width = `${p}%`;
}

function finish(result) {
  setStatus("COMPLETE", 1);
  statusbox.classList.add("hidden");
  output.value = result.block || "(empty)";
  const info = result.info || {};
  resultmeta.textContent = `${info.model} · ${info.compute_type} · beam=${info.beam_size} · lang=${info.language} · dur=${fmtDur(info.duration)} · segs=${(result.segments || []).length}`;
  resultbox.classList.remove("hidden");
  runbtn.disabled = false;
  footmsg.textContent = "DONE";
}

function fail(msg) {
  setStatus("ERROR", 0);
  hint.textContent = `✖ ${msg}`;
  hint.style.color = "var(--magenta)";
  runbtn.disabled = false;
  footmsg.textContent = "ERROR";
}

function fmtDur(s) {
  if (!s) return "?";
  const m = Math.floor(s / 60), sec = Math.round(s % 60);
  return `${m}m${String(sec).padStart(2, "0")}s`;
}

// --- Copy -----------------------------------------------------------------
copybtn.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(output.value);
  } catch {
    output.select();
    document.execCommand("copy");
  }
  copybtn.textContent = "✓ COPIED";
  copybtn.classList.add("done");
  setTimeout(() => { copybtn.textContent = "⧉ COPY"; copybtn.classList.remove("done"); }, 1600);
});
