const state = {
  view: "room",
  overview: null,
  detail: null,
  selectedId: "",
  language: "hi",
  pickedRow: null,
};

const MODEL_COLOR = {
  "whisper-small": "#2f5d73",
  "whisper-medium": "#8a5a12",
  vaakku: "#1d6b5a",
  mms: "#5c4d7a",
};

const VIEWS = ["room", "run", "scores", "robust", "marks", "tape", "export"];

document.querySelectorAll(".nav button").forEach((button) => {
  button.addEventListener("click", () => show(button.dataset.view));
});
document.querySelector("#gate-form").addEventListener("submit", onLogin);

boot();

async function boot() {
  const session = await fetch("/api/session").then((response) => response.json());
  if (!session.configured) {
    document.querySelector("#gate").hidden = false;
    document.querySelector("#gate-copy").textContent =
      "This bench will not open until DASHBOARD_TOKEN is set on the machine.";
    document.querySelector("#gate-form button").disabled = true;
    return;
  }
  if (session.auth_required && !session.authenticated) {
    document.querySelector("#gate").hidden = false;
    return;
  }
  document.querySelector("#bench").hidden = false;
  await refresh();
  setInterval(() => {
    if (state.view === "room" || state.view === "run" || running()) refresh();
  }, 2000);
}

async function onLogin(event) {
  event.preventDefault();
  const token = document.querySelector("#token").value;
  const response = await fetch("/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
  });
  const body = await response.json();
  if (!response.ok) {
    document.querySelector("#gate-error").textContent = body.error || "Sign-in failed.";
    return;
  }
  document.querySelector("#gate").hidden = true;
  document.querySelector("#bench").hidden = false;
  await refresh();
}

async function api(path, options) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (response.status === 401) {
    document.querySelector("#bench").hidden = true;
    document.querySelector("#gate").hidden = false;
    throw new Error("Sign in required.");
  }
  const body = await response.json();
  if (!response.ok) {
    const message = body.errors ? body.errors.join(" ") : body.error || "Request failed.";
    throw new Error(message);
  }
  return body;
}

async function refresh() {
  state.overview = await api("/api/overview");
  if (!state.selectedId && state.overview.experiments.length) {
    state.selectedId = state.overview.experiments[0].id;
  }
  if (state.selectedId) {
    try {
      state.detail = await api(`/api/experiments/${state.selectedId}`);
    } catch (_error) {
      state.detail = null;
    }
  }
  paintStatus();
  paint();
}

function running() {
  return (state.overview?.experiments || []).some((item) => item.status === "running");
}

function runColumns() {
  return [
    ["id", "Id"],
    ["name", "Name"],
    ["status", "Status"],
    ["progress_pct", "Progress", "num"],
    ["current_model", "Model"],
    ["current_sample", "Clip"],
    ["error", "Notice"],
  ];
}

function presets(form) {
  const group = document.createElement("div");
  group.className = "checks";
  [
    ["Clean only", { conditions: ["clean"] }],
    ["Noise sweep", { conditions: ["clean", "noise"], snr_levels: ["20", "10", "5"] }],
    ["Full bench", {
      conditions: ["clean", "noise", "speed", "volume", "reverb", "mp3"],
      snr_levels: ["20", "10", "5"],
      speed_factors: ["0.8", "1.2"],
    }],
  ].forEach(([label, patch]) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "preset";
    button.textContent = label;
    button.addEventListener("click", () => {
      Object.entries(patch).forEach(([name, values]) => {
        form.querySelectorAll(`button[data-name="${name}"]`).forEach((item) => {
          item.classList.toggle("is-on", values.includes(item.dataset.value));
        });
      });
      form.dispatchEvent(new Event("change"));
    });
    group.append(button);
  });
  return group;
}

function elapsed(iso) {
  if (!iso) return "just started";
  const seconds = Math.max(0, Math.round((Date.now() - Date.parse(iso)) / 1000));
  const minutes = Math.floor(seconds / 60);
  return minutes ? `${minutes}m ${seconds % 60}s` : `${seconds}s`;
}

function show(view) {
  state.view = view;
  document.querySelectorAll(".nav button").forEach((button) => {
    button.classList.toggle("is-on", button.dataset.view === view);
  });
  VIEWS.forEach((name) => {
    document.querySelector(`#view-${name}`).hidden = name !== view;
  });
  paint();
}

function paintStatus() {
  const overview = state.overview;
  const active = (overview.experiments || []).find((item) => item.status === "running" || item.status === "queued");
  const light = document.querySelector("#record-light");
  light.classList.toggle("is-live", Boolean(active));
  document.querySelector("#record-label").textContent = active ? active.status : "Idle";
  document.querySelector("#project-status").textContent = overview.status;
  const progress = active ? active.progress_pct : 0;
  const ruler = document.querySelector("#ruler");
  ruler.setAttribute("aria-valuenow", String(progress));
  ruler.replaceChildren();
  for (let index = 0; index < 40; index += 1) {
    const cell = document.createElement("i");
    if (progress > 0 && index / 40 < progress / 100) cell.className = "is-on";
    ruler.append(cell);
  }
  const caption = document.querySelector("#ruler-caption");
  caption.textContent = active
    ? `${active.name} · ${active.progress_current}/${active.progress_total || "?"} · ${active.current_model || "model pending"} · ${active.current_sample || "waiting for the first clip"} · ${elapsed(active.started_at)}`
    : "The scale stays empty until a run starts.";
  const board = document.querySelector("#status-board");
  board.replaceChildren();
  const gpu = overview.gpu || {};
  const cards = [
    ["Bench", overview.status],
    ["GPU", gpu.available ? `${Math.round(gpu.free_mb)} MB free` : "CPU"],
    ["Queued", String(overview.counts.queued)],
    ["Running", String(overview.counts.running)],
    ["Completed", String(overview.counts.completed)],
    ["Failed", String(overview.counts.failed)],
  ];
  cards.forEach(([label, value]) => {
    const article = document.createElement("article");
    const captionNode = document.createElement("span");
    captionNode.textContent = label;
    const strong = document.createElement("b");
    strong.textContent = value;
    article.append(captionNode, strong);
    board.append(article);
  });
  if (active) {
    const stop = document.createElement("button");
    stop.type = "button";
    stop.className = "stop";
    stop.textContent = "Stop run";
    stop.addEventListener("click", () => stopRun(active.id));
    const wrap = document.createElement("article");
    const captionNode = document.createElement("span");
    captionNode.textContent = "Control";
    wrap.append(captionNode, stop);
    board.append(wrap);
  }
}

async function stopRun(id) {
  await api(`/api/experiments/${id}/cancel`, { method: "POST", body: "{}" });
  await refresh();
}

function paint() {
  if (!state.overview || document.querySelector("#bench").hidden) return;
  const painters = { room: paintRoom, run: paintRun, scores: paintScores, robust: paintRobust, marks: paintMarks, tape: paintTape, export: paintExport };
  painters[state.view]();
}

function paintRoom() {
  const host = document.querySelector("#view-room");
  const overview = state.overview;
  const counts = overview.counts;
  host.replaceChildren(head("Room", "What is loaded, what is running, and which sets can be scored."));
  const stats = document.createElement("div");
  stats.className = "stats";
    [
      ["Datasets you can run", overview.datasets.filter((item) => item.selectable).length],
      ["Models configured", overview.models.length],
      ["Queued", counts.queued],
      ["Running", counts.running],
      ["Completed runs", counts.completed],
      ["Failed runs", counts.failed],
    ].forEach(([label, value]) => {
    const card = document.createElement("div");
    card.className = "stat";
    const number = document.createElement("b");
    number.textContent = String(value);
    const caption = document.createElement("span");
    caption.textContent = label;
    card.append(number, caption);
    stats.append(card);
  });
  host.append(stats);
  host.append(panel("GPU", gpuCopy(overview.gpu)));
  host.append(panel("Latest run", latestCopy(overview.latest)));
  host.append(heading("Runs"));
  table(host, runColumns(), overview.experiments);
  host.append(heading("Datasets"));
  table(
    host,
    [
      ["name", "Dataset"],
      ["languages", "Languages"],
      ["sample_count", "Samples", "num"],
      ["license_name", "License"],
      ["reason", "Status"],
    ],
    overview.datasets.map((item) => ({
      ...item,
      languages: item.languages.join(", "),
      sample_count: item.sample_count === null ? "—" : item.sample_count,
    })),
  );
  host.append(heading("Models"));
  table(
    host,
    [
      ["display_name", "Model"],
      ["hf_id", "Checkpoint"],
      ["languages", "Languages"],
      ["license_name", "License"],
      ["note", "Verified support"],
    ],
    overview.models.map((item) => ({ ...item, languages: item.languages.join(", ") })),
  );
}

function paintRun() {
  const host = document.querySelector("#view-run");
  if (host.querySelector("form")) {
    const language = host.querySelector('[name="language"]');
    if (language && document.activeElement !== language) language.value = state.language;
    const runs = host.querySelector(".run-list");
    if (runs) {
      runs.replaceChildren(heading("Runs"));
      table(runs, runColumns(), state.overview.experiments);
    }
    return;
  }
  const kept = null;
  host.replaceChildren(head("Run", "FLEURS test is the measured set. One model loads at a time."));
  const split = document.createElement("div");
  split.className = "split";
  const form = document.createElement("form");
  form.className = "panel fields";
  const datasets = state.overview.datasets.filter((item) => item.selectable);
  form.append(fieldSelect("dataset_id", "Dataset", datasets.map((item) => [item.dataset_id, item.name]), kept?.dataset_id || "fleurs"));
  form.append(fieldSelect("language", "Language", [["te", "Telugu"], ["ta", "Tamil"], ["hi", "Hindi"], ["kn", "Kannada"], ["ml", "Malayalam"], ["en", "English (demo only)"]], kept?.language || state.language));
  form.append(fieldSelect("split", "Split", [["test", "Test"], ["validation", "Validation"]], kept?.split || "test"));
  form.append(fieldInput("limit", "Sample limit", "number", kept?.limit || "10"));
  form.append(fieldInput("name", "Run name", "text", kept?.name || defaultName()));
  form.append(presets(form));
  form.append(checks("models", "Models", [
    ["whisper-small", "Whisper Small"],
    ["whisper-medium", "Whisper Medium"],
    ["vaakku", "Vaakku"],
    ["mms", "Meta MMS"],
  ], kept?.models || ["whisper-small", "vaakku", "mms"]));
  form.append(checks("conditions", "Audio", [
    ["clean", "Clean"],
    ["noise", "Noise"],
    ["speed", "Speed"],
    ["volume", "Volume"],
    ["reverb", "Reverb"],
    ["mp3", "MP3"],
  ], kept?.conditions || ["clean"]));
  form.append(checks("snr_levels", "SNR", [["20", "20 dB"], ["10", "10 dB"], ["5", "5 dB"]], kept?.snr_levels || ["20", "10", "5"]));
  form.append(checks("speed_factors", "Speed", [["0.8", "0.8×"], ["1.2", "1.2×"]], kept?.speed_factors || ["0.8", "1.2"]));
  form.append(fieldInput("batch_size", "Batch size", "number", kept?.batch_size || "1"));
  form.append(fieldInput("seed", "Seed", "number", kept?.seed || "13"));
  form.append(fieldInput("volume_db", "Volume (dB)", "number", kept?.volume_db || "-6"));
  form.append(fieldInput("reverb_decay", "Reverb decay", "number", kept?.reverb_decay || "0.45"));
  form.append(fieldSelect("mp3_bitrate", "MP3 bitrate", [["64", "64 kbps"], ["32", "32 kbps"], ["96", "96 kbps"], ["128", "128 kbps"]], kept?.mp3_bitrate || "64"));
  form.append(fieldInput("manifest_path", "Manifest path", "text", kept?.manifest_path || ""));
  form.append(fieldInput("audio_dir", "Audio directory", "text", kept?.audio_dir || ""));
  const button = document.createElement("button");
  button.className = "primary";
  button.type = "submit";
  button.textContent = "Run experiment";
  form.append(button);
  const error = document.createElement("p");
  error.className = "form-error";
  form.append(error);
  const summary = document.createElement("aside");
  summary.className = "summary";
  split.append(form, summary);
  host.append(split);
  const sync = () => {
    const values = readForm();
    state.language = values.language;
    summary.replaceChildren();
    const title = document.createElement("h3");
    title.textContent = "This run will score";
    const list = document.createElement("ul");
    [
      `${values.dataset_id} · ${values.language} · ${values.split}`,
      `${values.limit} samples · seed ${values.seed} · batch ${values.batch_size}`,
      values.models.join(", ") || "no model",
      values.conditions.join(", ") || "no condition",
      `noise ${values.snr_levels.join(", ") || "—"} dB · speed ${values.speed_factors.join(", ") || "—"}`,
      `volume ${values.volume_db} dB · reverb ${values.reverb_decay} · mp3 ${values.mp3_bitrate} kbps`,
    ].forEach((line) => {
      const item = document.createElement("li");
      item.textContent = line;
      list.append(item);
    });
    summary.append(title, list);
  };
  form.addEventListener("change", sync);
  form.addEventListener("input", sync);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    error.textContent = "";
    const values = readForm();
    try {
      const created = await api("/api/experiments", {
        method: "POST",
        body: JSON.stringify({
          ...values,
          limit: Number(values.limit),
          batch_size: Number(values.batch_size),
          seed: Number(values.seed),
          volume_db: Number(values.volume_db),
          reverb_decay: Number(values.reverb_decay),
          mp3_bitrate: Number(values.mp3_bitrate),
          snr_levels: values.snr_levels.map(Number),
          speed_factors: values.speed_factors.map(Number),
          manifest_path: values.manifest_path || null,
          audio_dir: values.audio_dir || null,
        }),
      });
      state.selectedId = created.id;
      await refresh();
      show("scores");
    } catch (failure) {
      error.textContent = failure.message;
    }
  });
  sync();
  const runs = document.createElement("div");
  runs.className = "run-list";
  host.append(runs);
  runs.append(heading("Runs"));
  table(runs, runColumns(), state.overview.experiments);
}

function paintScores() {
  paintMeasured("view-scores", "Scores", "Lower word error is the better score. Figures are micro-averages.", (host, detail) => {
    table(host, metricColumns(), detail.by_model);
    const grid = document.createElement("div");
    grid.className = "chart-grid";
    host.append(grid);
    bars(grid, "WER by model", detail.by_model, "model_id", "wer");
    bars(grid, "CER by model", detail.by_model, "model_id", "cer");
    bars(grid, "Latency (seconds)", detail.by_model, "model_id", "latency_s", false);
    bars(grid, "Real-time factor", detail.by_model, "model_id", "rtf", false);
    host.append(heading("By language"));
    table(host, [["model_id", "Model"], ["language", "Language"], ...metricColumns().slice(1)], detail.by_language);
    grouped(host, "WER by language", detail.by_language, "language");
    host.append(heading("By dataset"));
    table(host, [["model_id", "Model"], ["dataset", "Dataset"], ...metricColumns().slice(1)], detail.by_dataset);
    host.append(heading("GPU memory"));
    bars(host, "Peak GPU memory (MB)", detail.by_model, "model_id", "peak_gpu_mb", false);
  });
}

function paintRobust() {
  paintMeasured("view-robust", "Robustness", "Clean FLEURS is the headline. Noise and speed stay in this view.", (host, detail) => {
    const noise = detail.by_condition
      .filter((row) => row.audio_condition === "clean" || String(row.audio_condition).startsWith("noise_"))
      .map((row) => ({ ...row, label: `${row.model_id} · ${row.audio_condition}` }));
    lineChart(host, "WER against SNR", snrPoints(detail.by_condition));
    bars(host, "Clean and noisy WER", noise, "label", "wer");
    host.append(heading("Degradation from clean"));
    table(host, [["model_id", "Model"], ["audio_condition", "Condition"], ["clean_wer", "Clean WER", "pct"], ["wer", "Condition WER", "pct"], ["absolute", "Absolute", "pct"], ["relative", "Relative", "pct"]], degradation(detail.by_condition));
    const speed = detail.by_condition.filter((row) => String(row.audio_condition).startsWith("speed_"));
    host.append(heading("Speed"));
    table(host, [["model_id", "Model"], ["audio_condition", "Condition"], ["wer", "WER", "pct"], ["cer", "CER", "pct"]], speed);
  });
}

function paintMarks() {
  paintMeasured("view-marks", "Marks", "Exact match is exact. Digit accuracy is character accuracy on the digit string.", (host, detail) => {
    const entities = detail.entities || {};
    const rows = ["phone", "time", "date", "name", "address"].map((kind) => ({
      kind,
      applicable: entities[kind]?.applicable ?? 0,
      exact_rate: entities[kind]?.exact_rate,
      digit_accuracy: entities[kind]?.digit_accuracy,
    }));
    table(host, [["kind", "Mark"], ["applicable", "Rows", "num"], ["exact_rate", "Exact match", "pct"], ["digit_accuracy", "Digit accuracy", "pct"]], rows);
    const mix = entities.code_mix || {};
    host.append(panel("Telugu–English code mix", mix.applicable ? `${mix.applicable} rows · Latin WER ${pct(mix.latin_wer)} · Telugu WER ${pct(mix.indic_wer)}` : "No code-mixed Telugu–English rows in this run."));
  });
}

function paintTape() {
  const host = document.querySelector("#view-tape");
  host.replaceChildren(head("Tape", "Reference and prediction, with substitutions marked."));
  const detail = state.detail;
  if (!detail) {
    host.append(panel("No run", "Start a run, then come back to read a clip."));
    return;
  }
  addRunPicker(host);
  const rows = detail.rows || [];
  table(host, [["sample_id", "Sample"], ["language", "Language"], ["dataset", "Dataset"], ["model_id", "Model"], ["audio_condition", "Condition"], ["wer", "WER", "pct"], ["cer", "CER", "pct"], ["inference_time_s", "Latency", "sec"]], rows, (row) => {
    state.pickedRow = row;
    paintTape();
  });
  const picked = state.pickedRow || rows[0];
  if (!picked) return;
  const tape = document.createElement("div");
  tape.className = "tape";
  tape.append(quote("Reference", picked.reference, null));
  tape.append(quote("Prediction", picked.prediction || picked.error || "", picked.alignment));
  host.append(tape);
  if (picked.id && picked.audio_path) {
    const player = document.createElement("audio");
    player.controls = true;
    player.src = `/api/audio/${picked.id}`;
    host.append(player);
  }
}

function paintExport() {
  const host = document.querySelector("#view-export");
  host.replaceChildren(head("Export", "Download the rows, the JSON, or a short summary."));
  addRunPicker(host);
  if (!state.selectedId) {
    host.append(panel("No run", "Exports appear after a run exists."));
    return;
  }
  const links = document.createElement("div");
  links.className = "links";
  [
    [`/api/experiments/${state.selectedId}/export.csv`, "Download CSV"],
    [`/api/experiments/${state.selectedId}/export.json`, "Download JSON"],
    [`/api/experiments/${state.selectedId}/summary.txt`, "Download summary"],
  ].forEach(([href, label]) => {
    const link = document.createElement("a");
    link.href = href;
    link.textContent = label;
    links.append(link);
  });
  host.append(links);
  const log = document.createElement("pre");
  log.className = "log";
  log.textContent = "Loading the log…";
  host.append(log);
  api(`/api/experiments/${state.selectedId}/log`).then((body) => {
    log.textContent = body.log || "No log lines yet.";
  }).catch((error) => {
    log.textContent = error.message;
  });
  host.append(panel("Upload", "Comparing an uploaded file across models is not in this version. The extension point is src/inference/upload.py."));
}

function paintMeasured(viewId, title, copy, draw) {
  const host = document.querySelector(`#${viewId}`);
  host.replaceChildren(head(title, copy));
  addRunPicker(host);
  if (!state.detail) {
    host.append(emptyChartFrame("No measured rows yet."));
    return;
  }
  if (state.detail.experiment.error) {
    const banner = document.createElement("p");
    banner.className = "banner";
    banner.textContent = state.detail.experiment.error;
    host.append(banner);
  }
  draw(host, state.detail);
}

function addRunPicker(host) {
  const runs = state.overview.experiments;
  if (!runs.length) return;
  const wrap = document.createElement("div");
  wrap.className = "filters";
  const label = document.createElement("label");
  label.textContent = "Run";
  const select = document.createElement("select");
  runs.forEach((run) => {
    const option = document.createElement("option");
    option.value = run.id;
    option.textContent = `${run.name} · ${run.status}`;
    option.selected = run.id === state.selectedId;
    select.append(option);
  });
  select.addEventListener("change", async () => {
    state.selectedId = select.value;
    state.pickedRow = null;
    state.detail = await api(`/api/experiments/${state.selectedId}`);
    paint();
  });
  label.append(select);
  wrap.append(label);
  host.append(wrap);
}

function head(title, copy) {
  const header = document.createElement("div");
  header.className = "section-head";
  const h2 = document.createElement("h2");
  h2.textContent = title;
  const p = document.createElement("p");
  p.textContent = copy;
  header.append(h2, p);
  return header;
}

function heading(text) {
  const h3 = document.createElement("h3");
  h3.textContent = text;
  h3.style.margin = "18px 0 8px";
  return h3;
}

function panel(title, copy) {
  const node = document.createElement("section");
  node.className = "panel";
  const h3 = document.createElement("h3");
  h3.textContent = title;
  const p = document.createElement("p");
  p.textContent = copy;
  node.append(h3, p);
  return node;
}

function table(host, columns, rows, onPick) {
  const wrap = document.createElement("div");
  wrap.className = "table-wrap";
  const element = document.createElement("table");
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  columns.forEach((column) => {
    const cell = document.createElement("th");
    cell.textContent = column[1];
    if (column[2]) cell.className = "num";
    headRow.append(cell);
  });
  thead.append(headRow);
  const body = document.createElement("tbody");
  if (!rows.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = columns.length;
    cell.className = "empty";
    cell.textContent = "No measured rows yet.";
    row.append(cell);
    body.append(row);
  }
  rows.forEach((item) => {
    const row = document.createElement("tr");
    if (state.pickedRow && item.id && state.pickedRow.id === item.id) row.className = "is-picked";
    columns.forEach((column) => {
      const cell = document.createElement("td");
      if (column[2]) cell.className = "num";
      cell.textContent = format(item[column[0]], column[2]);
      row.append(cell);
    });
    if (onPick) row.addEventListener("click", () => onPick(item));
    body.append(row);
  });
  element.append(thead, body);
  wrap.append(element);
  host.append(wrap);
}

function metricColumns() {
  return [
    ["model_id", "Model"],
    ["samples", "Samples", "num"],
    ["wer", "WER", "pct"],
    ["cer", "CER", "pct"],
    ["ser", "SER", "pct"],
    ["substitutions", "Sub", "num"],
    ["deletions", "Del", "num"],
    ["insertions", "Ins", "num"],
    ["latency_s", "Latency", "sec"],
    ["rtf", "RTF", "num"],
    ["peak_gpu_mb", "GPU MB", "num"],
  ];
}

function format(value, kind) {
  if (value === null || value === undefined || value === "") return "—";
  if (kind === "pct") return pct(value);
  if (kind === "sec") return `${Number(value).toFixed(2)} s`;
  if (kind === "num" && typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(2);
  return String(value);
}

function pct(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return `${(Number(value) * 100).toFixed(1)}%`;
}

function bars(host, title, rows, labelKey, valueKey, asPercent = true) {
  const card = document.createElement("section");
  card.className = "chart";
  const h3 = document.createElement("h3");
  h3.textContent = title;
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 640 220");
  const usable = rows.filter((row) => row[valueKey] !== null && row[valueKey] !== undefined);
  if (!usable.length) {
    svg.append(text(24, 40, "No measured rows."));
  } else {
    const max = Math.max(...usable.map((row) => Number(row[valueKey])), 0.001);
    usable.slice(0, 8).forEach((row, index) => {
      const y = 16 + index * 24;
      const width = 360 * (Number(row[valueKey]) / max);
      const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      rect.setAttribute("x", "180");
      rect.setAttribute("y", String(y));
      rect.setAttribute("width", String(Math.max(width, 2)));
      rect.setAttribute("height", "14");
      rect.setAttribute("fill", MODEL_COLOR[row.model_id] || "#2f5d73");
      svg.append(text(8, y + 12, String(row[labelKey] || row.model_id)), rect);
      svg.append(text(550, y + 12, asPercent ? pct(row[valueKey]) : Number(row[valueKey]).toFixed(2)));
    });
  }
  const caption = document.createElement("p");
  caption.className = "chart-caption";
  caption.textContent = asPercent ? "Percent. Lower is better for error rates." : "Measured on this run.";
  card.append(h3, svg, caption);
  host.append(card);
}

function grouped(host, title, rows, key) {
  const card = document.createElement("section");
  card.className = "chart";
  const h3 = document.createElement("h3");
  h3.textContent = title;
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 640 220");
  const languages = [...new Set(rows.map((row) => row[key]))];
  if (!languages.length) svg.append(text(24, 40, "No measured rows."));
  languages.forEach((language, index) => {
    const group = rows.filter((row) => row[key] === language && row.wer !== null);
    group.forEach((row, series) => {
      const x = 40 + index * 110 + series * 18;
      const height = Math.min(160, 160 * Number(row.wer));
      const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      rect.setAttribute("x", String(x));
      rect.setAttribute("y", String(180 - height));
      rect.setAttribute("width", "14");
      rect.setAttribute("height", String(height));
      rect.setAttribute("fill", MODEL_COLOR[row.model_id] || "#2f5d73");
      svg.append(rect);
    });
    svg.append(text(40 + index * 110, 204, language));
  });
  card.append(h3, svg);
  host.append(card);
}

function lineChart(host, title, series) {
  const card = document.createElement("section");
  card.className = "chart";
  const h3 = document.createElement("h3");
  h3.textContent = title;
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 640 220");
  const axis = document.createElementNS("http://www.w3.org/2000/svg", "line");
  axis.setAttribute("x1", "40");
  axis.setAttribute("y1", "180");
  axis.setAttribute("x2", "600");
  axis.setAttribute("y2", "180");
  axis.setAttribute("class", "axis");
  svg.append(axis);
  const names = Object.keys(series);
  if (!names.length) svg.append(text(48, 40, "No noisy rows yet. Add the noise condition to a run."));
  names.forEach((name) => {
    const points = series[name];
    const poly = points.map((point, index) => {
      const x = 80 + index * 160;
      const y = 180 - Math.min(150, 150 * point.wer);
      return `${x},${y}`;
    }).join(" ");
    const node = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
    node.setAttribute("points", poly);
    node.setAttribute("fill", "none");
    node.setAttribute("stroke", MODEL_COLOR[name] || "#14232c");
    node.setAttribute("stroke-width", "2");
    svg.append(node);
  });
  [20, 10, 5].forEach((snr, index) => svg.append(text(70 + index * 160, 204, `${snr} dB`)));
  card.append(h3, svg);
  host.append(card);
}

function emptyChartFrame(message) {
  const card = document.createElement("section");
  card.className = "chart";
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 640 180");
  const axis = document.createElementNS("http://www.w3.org/2000/svg", "line");
  axis.setAttribute("x1", "40");
  axis.setAttribute("y1", "140");
  axis.setAttribute("x2", "600");
  axis.setAttribute("y2", "140");
  axis.setAttribute("class", "axis");
  svg.append(axis, text(48, 70, message));
  card.append(svg);
  return card;
}

function text(x, y, value) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", "text");
  node.setAttribute("x", String(x));
  node.setAttribute("y", String(y));
  node.setAttribute("class", "tick");
  node.textContent = value;
  return node;
}

function snrPoints(rows) {
  const series = {};
  rows.forEach((row) => {
    const match = String(row.audio_condition).match(/^noise_snr_(\d+)$/);
    if (!match || row.wer === null) return;
    series[row.model_id] = series[row.model_id] || [];
    series[row.model_id].push({ snr: Number(match[1]), wer: row.wer });
  });
  Object.values(series).forEach((points) => points.sort((a, b) => b.snr - a.snr));
  return series;
}

function degradation(rows) {
  const clean = {};
  rows.forEach((row) => {
    if (row.audio_condition === "clean") clean[row.model_id] = row.wer;
  });
  return rows
    .filter((row) => row.audio_condition !== "clean" && clean[row.model_id] !== undefined && row.wer !== null)
    .map((row) => {
      const base = clean[row.model_id];
      const absolute = row.wer - base;
      return {
        ...row,
        clean_wer: base,
        absolute,
        relative: base > 0 ? absolute / base : null,
      };
    });
}

function quote(title, copy, alignment) {
  const article = document.createElement("article");
  const h3 = document.createElement("h3");
  h3.textContent = title;
  const paragraph = document.createElement("p");
  if (!alignment || title === "Reference") {
    paragraph.textContent = copy || "—";
  } else {
    alignment.forEach((piece) => {
      const span = document.createElement("span");
      span.className = piece.op === "substitution" ? "mark-sub" : piece.op === "deletion" ? "mark-del" : piece.op === "insertion" ? "mark-ins" : "";
      span.textContent = `${piece.op === "deletion" ? piece.ref : piece.hyp || piece.ref} `;
      paragraph.append(span);
    });
  }
  article.append(h3, paragraph);
  return article;
}

function gpuCopy(gpu) {
  if (!gpu?.available) return gpu?.error || "CUDA is not available. Models can fall back to CPU when that option is on.";
  return `${gpu.name} · ${gpu.free_mb.toFixed(0)} MB free of ${gpu.total_mb.toFixed(0)} MB.`;
}

function latestCopy(latest) {
  if (!latest) return "No runs yet.";
  return `${latest.name} is ${latest.status}. ${latest.progress_current}/${latest.progress_total} rows. ${latest.error || ""}`.trim();
}

function defaultName() {
  const stamp = new Date().toISOString().slice(0, 16).replace(/[:T]/g, "-");
  return `fleurs-${state.language}-${stamp}`;
}

function fieldSelect(name, labelText, options, current) {
  const label = document.createElement("label");
  label.textContent = labelText;
  const select = document.createElement("select");
  select.name = name;
  options.forEach(([value, text]) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = text;
    option.selected = value === current;
    select.append(option);
  });
  label.append(select);
  return label;
}

function fieldInput(name, labelText, type, value) {
  const label = document.createElement("label");
  label.textContent = labelText;
  const input = document.createElement("input");
  input.name = name;
  input.type = type;
  if (type === "number") input.step = "any";
  input.value = value;
  label.append(input);
  return label;
}

function checks(name, labelText, options, selected) {
  const group = document.createElement("fieldset");
  group.className = "fields";
  const legend = document.createElement("legend");
  legend.textContent = labelText;
  const row = document.createElement("div");
  row.className = "checks";
  group.append(legend, row);
  options.forEach(([value, text]) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "choice";
    button.dataset.name = name;
    button.dataset.value = value;
    button.textContent = text;
    button.classList.toggle("is-on", selected.includes(value));
    button.addEventListener("click", () => button.classList.toggle("is-on"));
    row.append(button);
  });
  return group;
}

function readForm() {
  const form = document.querySelector("#view-run form");
  const data = Object.fromEntries(new FormData(form).entries());
  ["models", "conditions", "snr_levels", "speed_factors"].forEach((name) => {
    data[name] = [...form.querySelectorAll(`button[data-name="${name}"].is-on`)].map((button) => button.dataset.value);
  });
  return data;
}
