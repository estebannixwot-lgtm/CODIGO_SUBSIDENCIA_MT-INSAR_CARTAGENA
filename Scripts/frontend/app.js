const STEPS = [
  {
    id: 1, endpoint: "/api/step1", title: "TOPSAR-Split + Apply-Orbit",
    desc: "Recorta el subswath (franjas longitudinales de la imagen radar: IW1, IW2 o IW3), aplica orbitas precisas y renombra por fecha.",
    fields: [
      { name: "subswath", label: "Subswaths a procesar", type: "checkboxes", options: ["IW1","IW2","IW3"], default: ["IW2"] },
      { name: "first_burst", label: "Primer Burst", type: "number", default: "1" },
      { name: "last_burst", label: "Ultimo Burst", type: "number", default: "9" },
    ]
  },
  {
    id: 3, endpoint: "/api/step3", title: "Generacion SBAS (Interferogramas)",
    desc: "Genera pares master-slave automaticamente y crea los interferogramas.",
    fields: [
      { name: "max_days", label: "Max dias temporales", type: "number", default: "90" },
      { name: "max_pairs", label: "Max pares/imagen", type: "number", default: "4" },
      { name: "demName", label: "Modelo Digital de Elevacion (DEM)", type: "select", options: ["Copernicus 30m Global DEM","SRTM 1Sec HGT","SRTM 3Sec","ACE30","GETASSE30"], default: "Copernicus 30m Global DEM" },
    ]
  },
  {
    id: 4, endpoint: "/api/step4", title: "Subset Espacial",
    desc: "Recorta los interferogramas a su zona de estudio usando subset_grapho.xml.",
    fields: [
      { name: "lon_min", label: "Lon Min (oeste)", type: "text", default: "-75.65" },
      { name: "lon_max", label: "Lon Max (este)", type: "text", default: "-75.40" },
      { name: "lat_min", label: "Lat Min (sur)", type: "text", default: "10.30" },
      { name: "lat_max", label: "Lat Max (norte)", type: "text", default: "10.52" },
    ],
    buildParams: (vals) => {
      const geo = `POLYGON ((${vals.lon_min} ${vals.lat_min}, ${vals.lon_max} ${vals.lat_min}, ${vals.lon_max} ${vals.lat_max}, ${vals.lon_min} ${vals.lat_max}, ${vals.lon_min} ${vals.lat_min}, ${vals.lon_min} ${vals.lat_min}))`;
      return { geoRegion: geo };
    }
  },
  {
    id: 5, endpoint: "/api/step5", title: "Exportacion a SNAPHU",
    desc: "Exporta los interferogramas al formato SNAPHU para el unwrapping.",
    fields: []
  },
  {
    id: 6, endpoint: null, title: "SNAPHU Unwrapping",
    desc: "Ejecute snaphu.exe desde la terminal. Proceso intensivo en CPU.",
    fields: [], manual: true
  },
  {
    id: 7, endpoint: null, title: "Importacion desde SNAPHU",
    desc: "Ejecute manualmente desde la terminal (paso 7 del pipeline).",
    fields: [], manual: true
  },
  {
    id: 8, endpoint: "/api/step8", title: "Terrain Correction (Pha/Coh)",
    desc: "Correccion geometrica y subset de Fase y Coherencia para MintPy.",
    fields: [
      { name: "lon_min", label: "Lon Min (oeste)", type: "text", default: "-75.65" },
      { name: "lon_max", label: "Lon Max (este)", type: "text", default: "-75.40" },
      { name: "lat_min", label: "Lat Min (sur)", type: "text", default: "10.30" },
      { name: "lat_max", label: "Lat Max (norte)", type: "text", default: "10.52" },
      { name: "demName", label: "DEM", type: "select", options: ["Copernicus 30m Global DEM","SRTM 1Sec HGT","SRTM 3Sec","ACE30","GETASSE30"], default: "Copernicus 30m Global DEM" },
    ],
    buildParams: (vals) => {
      const geo = `POLYGON ((${vals.lon_min} ${vals.lat_min}, ${vals.lon_max} ${vals.lat_min}, ${vals.lon_max} ${vals.lat_max}, ${vals.lon_min} ${vals.lat_max}, ${vals.lon_min} ${vals.lat_min}, ${vals.lon_min} ${vals.lat_min}))`;
      return { geoRegion: geo };
    }
  },
  {
    id: 9, endpoint: "/api/step9", title: "Terrain Correction (UNW)",
    desc: "Correccion geometrica de la fase desenvolvida.",
    fields: [
      { name: "lon_min", label: "Lon Min", type: "text", default: "-75.65" },
      { name: "lon_max", label: "Lon Max", type: "text", default: "-75.40" },
      { name: "lat_min", label: "Lat Min", type: "text", default: "10.30" },
      { name: "lat_max", label: "Lat Max", type: "text", default: "10.52" },
      { name: "demName", label: "DEM", type: "select", options: ["Copernicus 30m Global DEM","SRTM 1Sec HGT","SRTM 3Sec","ACE30","GETASSE30"], default: "Copernicus 30m Global DEM" },
    ],
    buildParams: (vals) => {
      const geo = `POLYGON ((${vals.lon_min} ${vals.lat_min}, ${vals.lon_max} ${vals.lat_min}, ${vals.lon_max} ${vals.lat_max}, ${vals.lon_min} ${vals.lat_max}, ${vals.lon_min} ${vals.lat_min}, ${vals.lon_min} ${vals.lat_min}))`;
      return { geoRegion: geo };
    }
  },
  {
    id: 10, endpoint: "/api/step10", title: "Configurar MintPy",
    desc: "Define el punto de referencia y configura ERA5 en smallbaselineApp.cfg.",
    fields: [
      { name: "ref_lat", label: "Lat referencia", type: "text", default: "10.4225" },
      { name: "ref_lon", label: "Lon referencia", type: "text", default: "-75.5397" },
      { name: "use_era5", label: "Correccion ERA5", type: "toggle", default: true },
      { name: "era5_key", label: "API Key ERA5", type: "text", default: "", placeholder: "12345:abc-def..." },
    ]
  },
  {
    id: 11, endpoint: null, title: "Cartografia Automatica",
    desc: "Ejecute desde terminal: python Scripts/10_pipeline_snap_mintpy.py (Paso 11).",
    fields: [], manual: true
  },
];

const FLOW_NAMES = ["00_RAW","01_SLC","02_IFG","03_SUB","04_EXP","05_IMP","06_MPI","07_MPR","Productos"];

let activeStep = null;
let isRunning = false;

// ============ INIT ============
document.addEventListener("DOMContentLoaded", () => {
  checkStatus();
  renderFlow();
  renderSteps();
  scanFolders();
  connectSSE();
  setInterval(scanFolders, 15000);
});

async function checkStatus() {
  try {
    const r = await fetch("/api/status");
    const d = await r.json();
    document.getElementById("dot-gpt").className = `dot ${d.gpt ? 'green' : 'red'}`;
    document.getElementById("dot-snaphu").className = `dot ${d.snaphu ? 'green' : 'red'}`;
    document.getElementById("lbl-gpt").textContent = d.gpt ? "SNAP OK" : "SNAP ?";
    document.getElementById("lbl-snaphu").textContent = d.snaphu ? "SNAPHU OK" : "SNAPHU ?";
    isRunning = d.running;
  } catch(e) {
    console.error(e);
  }
}

function renderFlow() {
  const el = document.getElementById("flowDiagram");
  el.innerHTML = FLOW_NAMES.map((n, i) =>
    `<div class="flow-node" id="flow-${i}">${n}</div>${i < FLOW_NAMES.length-1 ? '<span class="flow-arrow">&#9654;</span>' : ''}`
  ).join("");
}

function renderSteps() {
  const panel = document.getElementById("stepsPanel");
  panel.innerHTML = STEPS.map(s => {
    let fieldsHTML = "";
    if (s.fields && s.fields.length > 0) {
      const rows = [];
      for (let i = 0; i < s.fields.length; i += 2) {
        const f1 = s.fields[i];
        const f2 = s.fields[i+1];
        let row = '<div class="form-row">';
        row += renderField(f1, s.id);
        if (f2) row += renderField(f2, s.id);
        row += '</div>';
        rows.push(row);
      }
      fieldsHTML = rows.join("");
    }
    const btnHTML = s.manual
      ? `<div style="padding:0.5rem;background:var(--bg-input);border-radius:8px;font-size:0.8rem;color:var(--warning);">Ejecutar desde terminal</div>`
      : `<button class="btn btn-primary" id="btn-${s.id}" onclick="runStep(${s.id})">Ejecutar Paso ${s.id}</button>`;

    return `
      <div class="step-card" id="card-${s.id}">
        <div class="step-header" onclick="toggleStep(${s.id})" style="cursor:pointer;">
          <div class="step-number">${s.id}</div>
          <div>
            <div class="step-title">${s.title}</div>
            <div class="step-desc">${s.desc}</div>
          </div>
        </div>
        <div class="step-form" id="form-${s.id}">
          ${fieldsHTML}
          ${btnHTML}
        </div>
      </div>`;
  }).join("");
}

function renderField(f, stepId) {
  const id = `field-${stepId}-${f.name}`;
  if (f.type === "select") {
    const opts = f.options.map(o => `<option value="${o}" ${o===f.default?'selected':''}>${o}</option>`).join("");
    return `<div class="form-group"><label>${f.label}</label><select id="${id}">${opts}</select></div>`;
  }
  if (f.type === "checkboxes") {
    const opts = f.options.map(o => `
      <label style="display:flex;align-items:center;gap:0.3rem;text-transform:none;font-weight:400;color:var(--text);cursor:pointer;">
        <input type="checkbox" name="${id}" value="${o}" ${(f.default||[]).includes(o)?'checked':''}> ${o}
      </label>
    `).join("");
    return `<div class="form-group"><label>${f.label}</label><div style="display:flex;gap:1.5rem;padding:0.6rem 0.2rem;">${opts}</div></div>`;
  }
  if (f.type === "toggle") {
    return `<div class="form-group"><label>${f.label}</label>
      <div class="toggle-row"><div class="toggle ${f.default?'on':''}" id="${id}" onclick="this.classList.toggle('on')"></div>
      <span style="font-size:0.8rem;color:var(--text-muted)">Activar</span></div></div>`;
  }
  return `<div class="form-group"><label>${f.label}</label>
    <input type="${f.type||'text'}" id="${id}" value="${f.default||''}" placeholder="${f.placeholder||''}"></div>`;
}

function toggleStep(id) {
  const card = document.getElementById(`card-${id}`);
  if (activeStep === id) {
    card.classList.remove("active");
    activeStep = null;
  } else {
    document.querySelectorAll(".step-card").forEach(c => c.classList.remove("active"));
    card.classList.add("active");
    activeStep = id;
  }
}

async function runStep(id) {
  if (isRunning) { addLog("Ya hay un proceso en ejecucion. Espere.", "error"); return; }
  
  const step = STEPS.find(s => s.id === id);
  if (!step || !step.endpoint) return;

  // Collect field values
  const vals = {};
  step.fields.forEach(f => {
    if (f.type === "toggle") {
      const el = document.getElementById(`field-${id}-${f.name}`);
      vals[f.name] = el.classList.contains("on");
    } else if (f.type === "checkboxes") {
      const els = document.querySelectorAll(`input[name="field-${id}-${f.name}"]:checked`);
      vals[f.name] = Array.from(els).map(e => e.value).join(",");
    } else {
      const el = document.getElementById(`field-${id}-${f.name}`);
      vals[f.name] = el.value;
    }
  });

  // Build params
  let params = { ...vals };
  if (step.buildParams) {
    params = { ...params, ...step.buildParams(vals) };
  }

  const btn = document.getElementById(`btn-${id}`);
  btn.disabled = true;
  btn.textContent = "Procesando...";
  isRunning = true;
  addLog(`Iniciando Paso ${id}: ${step.title}`, "info");

  try {
    const r = await fetch(step.endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params)
    });
    const d = await r.json();
    if (d.error) {
      addLog(`Error: ${d.error}`, "error");
    } else {
      addLog(`Paso ${id} enviado correctamente.`, "success");
      if (d.wsl_path) {
        addLog(`Ruta WSL: cd ${d.wsl_path}`, "info");
        addLog(`Ejecute: mamba activate mintpy && smallbaselineApp.py smallbaselineApp.cfg`, "info");
      }
    }
  } catch(e) {
    addLog(`Error de conexion: ${e.message}`, "error");
  }

  // Poll for completion
  const poll = setInterval(async () => {
    try {
      const r = await fetch("/api/status");
      const d = await r.json();
      document.getElementById("progressBar").style.width = (d.progress || 0) + "%";
      if (!d.running) {
        clearInterval(poll);
        btn.disabled = false;
        btn.textContent = `Ejecutar Paso ${id}`;
        isRunning = false;
        document.getElementById(`card-${id}`).classList.add("completed");
        scanFolders();
      }
    } catch(e) {}
  }, 2000);
}

async function scanFolders() {
  try {
    const r = await fetch("/api/scan");
    const d = await r.json();
    const el = document.getElementById("scanSummary");
    const items = [
      { label: "ZIPs Crudos", count: d.zips?.length || 0 },
      { label: "Imagenes SLC", count: d.dims?.length || 0 },
      { label: "Interferogramas", count: d.ifg?.count || 0 },
      { label: "MintPy Inputs", count: d.mpi?.count || 0 },
    ];
    el.innerHTML = items.map(i => `
      <div class="scan-item">
        <div class="count">${i.count}</div>
        <div class="label">${i.label}</div>
      </div>`).join("");

    // Update flow nodes
    const counts = [d.raw?.count, d.slc?.count, d.ifg?.count, d.sub?.count, d.exp?.count, d.imp?.count, d.mpi?.count, d.mpr?.count];
    counts.forEach((c, i) => {
      const node = document.getElementById(`flow-${i}`);
      if (node) {
        node.classList.remove("done", "active");
        if (c > 0) node.classList.add("done");
      }
    });
  } catch(e) {}
}

function connectSSE() {
  const es = new EventSource("/api/logs");
  es.onmessage = (e) => {
    const d = JSON.parse(e.data);
    if (d.msg) addLog(d.msg);
  };
  es.onerror = () => setTimeout(connectSSE, 3000);
}

function addLog(msg, type) {
  const body = document.getElementById("logBody");
  const cls = type || (msg.includes("ERROR") ? "error" : msg.includes("[OK]") || msg.includes("completado") ? "success" : msg.includes("CMD:") ? "info" : "");
  const line = document.createElement("div");
  line.className = `log-line ${cls}`;
  line.textContent = msg;
  body.appendChild(line);
  body.scrollTop = body.scrollHeight;
}

function clearLogs() {
  document.getElementById("logBody").innerHTML = '<div class="log-line info">Consola limpiada.</div>';
}
