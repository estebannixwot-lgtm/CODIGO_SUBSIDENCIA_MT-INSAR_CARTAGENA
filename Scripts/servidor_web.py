# -*- coding: utf-8 -*-
"""
Servidor Web para el Pipeline InSAR - Frontend GUI
Flask backend que expone los pasos del pipeline como API endpoints.
"""
import os, sys, glob, re, json, subprocess, threading, queue, time
from datetime import datetime
from flask import Flask, render_template, request, jsonify, Response, send_from_directory

# Rutas del proyecto
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(SCRIPT_DIR, "frontend")
BASE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "Datos_Profesor"))
GRAPHS_DIR = os.path.join(SCRIPT_DIR, "SNAP_Graphs")

# Carpetas de trabajo
DIRS = {
    "raw": os.path.join(BASE_DIR, "00_RAW_ZIP"),
    "slc": os.path.join(BASE_DIR, "01_DATOS_SLC"),
    "ifg": os.path.join(BASE_DIR, "02_INTERFEROGRAMAS"),
    "sub": os.path.join(BASE_DIR, "03_SUBSETS"),
    "exp": os.path.join(BASE_DIR, "04_SNAPHU_EXPORT"),
    "imp": os.path.join(BASE_DIR, "05_SNAPHU_IMPORT"),
    "mpi": os.path.join(BASE_DIR, "06_MINTPY_INPUTS"),
    "mpr": os.path.join(BASE_DIR, "07_MINTPY_RESULTS"),
}
for d in DIRS.values():
    os.makedirs(d, exist_ok=True)

app = Flask(__name__, static_folder=FRONTEND_DIR, template_folder=FRONTEND_DIR)

# Cola global para logs en tiempo real
log_queue = queue.Queue()
current_process = {"running": False, "step": None, "progress": 0}

import shutil

def find_gpt():
    path = shutil.which("gpt.exe")
    if path: return path
    for p in [r"C:\Program Files\snap\bin\gpt.exe", r"C:\Program Files\esa-snap\bin\gpt.exe", r"C:\snap\bin\gpt.exe"]:
        if os.path.exists(p): return p
    return None

def find_snaphu():
    path = shutil.which("snaphu.exe")
    if path: return path
    for p in [r"C:\TESIS\snaphu_bin\bin\snaphu.exe", r"C:\snaphu\bin\snaphu.exe"]:
        if os.path.exists(p): return p
    return None

GPT_BIN = find_gpt()
SNAPHU_BIN = find_snaphu()

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    log_queue.put(f"[{ts}] {msg}")

def extract_date(filename):
    m = re.search(r'S1[AB]_\w+_(\d{8})T\d{6}', filename)
    if m: return m.group(1)
    m = re.search(r'(20\d{6})', filename)
    if m: return m.group(1)
    return None

def run_gpt(graph, params):
    if not GPT_BIN:
        log("ERROR: gpt.exe no encontrado")
        return False
    cmd = [GPT_BIN, graph]
    for k, v in params.items():
        cmd.append(f"-P{k}={v}")
    cmd.append("-e")
    log(f"CMD: {' '.join(cmd)}")
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
        for line in proc.stdout:
            log(line.strip())
        proc.wait()
        return proc.returncode == 0
    except Exception as e:
        log(f"ERROR: {e}")
        return False

# ============ RUTAS DE LA API ============

@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")

@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(FRONTEND_DIR, path)

@app.route("/api/status")
def api_status():
    return jsonify({
        "gpt": GPT_BIN is not None,
        "gpt_path": GPT_BIN or "No encontrado",
        "snaphu": SNAPHU_BIN is not None,
        "snaphu_path": SNAPHU_BIN or "No encontrado",
        "running": current_process["running"],
        "step": current_process["step"],
        "dirs": {k: os.path.exists(v) for k, v in DIRS.items()},
    })

@app.route("/api/scan")
def api_scan():
    """Escanear estado de todas las carpetas"""
    data = {}
    for key, path in DIRS.items():
        if os.path.exists(path):
            items = os.listdir(path)
            data[key] = {"count": len(items), "items": items[:20]}
        else:
            data[key] = {"count": 0, "items": []}
    # Contar ZIPs
    zips = glob.glob(os.path.join(DIRS["raw"], "*.zip"))
    data["zips"] = [os.path.basename(z) for z in zips]
    data["zip_dates"] = [extract_date(os.path.basename(z)) for z in zips]
    # Contar DIMs
    dims = glob.glob(os.path.join(DIRS["slc"], "*.dim"))
    data["dims"] = [os.path.basename(d).replace(".dim","") for d in dims]
    return jsonify(data)

@app.route("/api/logs")
def api_logs():
    """SSE endpoint para logs en tiempo real"""
    def stream():
        while True:
            try:
                msg = log_queue.get(timeout=1)
                yield f"data: {json.dumps({'msg': msg})}\n\n"
            except queue.Empty:
                yield f"data: {json.dumps({'heartbeat': True})}\n\n"
    return Response(stream(), mimetype="text/event-stream")

@app.route("/api/step1", methods=["POST"])
def api_step1():
    """TOPSAR-Split + Apply-Orbit + Rename"""
    if current_process["running"]:
        return jsonify({"error": "Ya hay un proceso en ejecucion"}), 400
    
    data = request.json
    subswath = data.get("subswath", "IW2")
    first_burst = data.get("first_burst", "1")
    last_burst = data.get("last_burst", "9")
    
    def run():
        current_process["running"] = True
        current_process["step"] = "Paso 1: TOPSAR-Split"
        try:
            zips = glob.glob(os.path.join(DIRS["raw"], "*.zip"))
            if not zips:
                log("No se encontraron archivos .zip en 00_RAW_ZIP")
                return
            log(f"Procesando {len(zips)} archivos ZIP...")
            
            graph_xml = f"""<graph id="Graph">
    <version>1.0</version>
    <node id="Read"><operator>Read</operator><parameters><file>${{input}}</file></parameters></node>
    <node id="TOPSAR-Split"><operator>TOPSAR-Split</operator>
      <sources><sourceProduct refid="Read"/></sources>
      <parameters><subswath>{subswath}</subswath><selectedPolarisations>VV</selectedPolarisations>
        <firstBurstIndex>{first_burst}</firstBurstIndex><lastBurstIndex>{last_burst}</lastBurstIndex></parameters>
    </node>
    <node id="Apply-Orbit-File"><operator>Apply-Orbit-File</operator>
      <sources><sourceProduct refid="TOPSAR-Split"/></sources>
      <parameters><orbitType>Sentinel Precise (Auto Download)</orbitType><polyDegree>3</polyDegree><continueOnFail>true</continueOnFail></parameters>
    </node>
    <node id="Write"><operator>Write</operator>
      <sources><sourceProduct refid="Apply-Orbit-File"/></sources>
      <parameters><file>${{output}}</file><formatName>BEAM-DIMAP</formatName></parameters>
    </node></graph>"""
            
            temp = os.path.join(GRAPHS_DIR, "_temp_split.xml")
            with open(temp, "w", encoding="utf-8") as f:
                f.write(graph_xml)
            
            for i, zf in enumerate(zips):
                fecha = extract_date(os.path.basename(zf))
                if not fecha:
                    log(f"WARN: No se pudo extraer fecha de {os.path.basename(zf)}")
                    continue
                out = os.path.join(DIRS["slc"], f"{fecha}.dim")
                if os.path.exists(out):
                    log(f"Saltando {fecha}, ya existe.")
                    continue
                current_process["progress"] = int((i/len(zips))*100)
                log(f"Procesando {fecha} ({i+1}/{len(zips)})...")
                run_gpt(temp, {"input": zf, "output": out})
            
            if os.path.exists(temp): os.remove(temp)
            log("Paso 1 completado.")
        finally:
            current_process["running"] = False
            current_process["progress"] = 100
    
    threading.Thread(target=run, daemon=True).start()
    return jsonify({"ok": True})

@app.route("/api/step3", methods=["POST"])
def api_step3():
    """Generar pares SBAS e interferogramas"""
    if current_process["running"]:
        return jsonify({"error": "Ya hay un proceso en ejecucion"}), 400
    
    data = request.json
    max_days = int(data.get("max_days", 90))
    max_pairs = int(data.get("max_pairs", 4))
    dem_name = data.get("demName", "Copernicus 30m Global DEM")
    
    def run():
        current_process["running"] = True
        current_process["step"] = "Paso 3: SBAS"
        try:
            dims = glob.glob(os.path.join(DIRS["slc"], "*.dim"))
            fechas = sorted([os.path.basename(f).replace(".dim","") for f in dims if re.match(r'^20\d{6}$', os.path.basename(f).replace(".dim",""))])
            
            if len(fechas) < 2:
                log("Se necesitan al menos 2 imagenes .dim")
                return
            
            log(f"DEM seleccionado: {dem_name}")
            
            # Generar pares
            date_objs = sorted([datetime.strptime(d, "%Y%m%d") for d in fechas])
            pairs = []
            for i, d1 in enumerate(date_objs):
                count = 0
                for d2 in date_objs[i+1:]:
                    if (d2-d1).days <= max_days:
                        pairs.append((d1.strftime("%Y%m%d"), d2.strftime("%Y%m%d")))
                        count += 1
                        if count >= max_pairs: break
            
            pf = os.path.join(BASE_DIR, "pares_sbas.txt")
            with open(pf, "w") as f:
                for m, s in pairs:
                    f.write(f"{m}_{s}\n")
            log(f"Generados {len(pairs)} pares SBAS.")
            
            grafo = os.path.join(GRAPHS_DIR, "Grafo_auto_G.xml")
            for i, (m, s) in enumerate(pairs):
                par = f"{m}_{s}"
                mf = os.path.join(DIRS["slc"], f"{m}.dim")
                sf = os.path.join(DIRS["slc"], f"{s}.dim")
                od = os.path.join(DIRS["ifg"], par)
                of = os.path.join(od, f"{par}.dim")
                if not os.path.exists(mf) or not os.path.exists(sf): continue
                os.makedirs(od, exist_ok=True)
                if os.path.exists(of):
                    log(f"Par {par} ya existe.")
                    continue
                current_process["progress"] = int((i/len(pairs))*100)
                log(f"Generando IFG {par} ({i+1}/{len(pairs)})...")
                run_gpt(grafo, {"master": mf, "slave": sf, "output": of, "demName": dem_name})
            log("Paso 3 completado.")
        finally:
            current_process["running"] = False
            current_process["progress"] = 100
    
    threading.Thread(target=run, daemon=True).start()
    return jsonify({"ok": True, "msg": "Generacion SBAS iniciada"})

@app.route("/api/step4", methods=["POST"])
def api_step4():
    """Subset Espacial"""
    if current_process["running"]:
        return jsonify({"error": "Proceso en ejecucion"}), 400
    data = request.json
    geo = data.get("geoRegion", "")
    if not geo:
        return jsonify({"error": "Falta parametro geoRegion"}), 400

    def run():
        current_process["running"] = True
        current_process["step"] = "Paso 4: Subset"
        try:
            grafo = os.path.join(GRAPHS_DIR, "subset_grapho.xml")
            ifg_dirs = glob.glob(os.path.join(DIRS["ifg"], "*_*"))
            if not ifg_dirs:
                log("No se encontraron interferogramas en 02_INTERFEROGRAMAS")
                return
            for i, folder in enumerate(ifg_dirs):
                par = os.path.basename(folder)
                inp = os.path.join(folder, f"{par}.dim")
                if not os.path.exists(inp): continue
                
                od = os.path.join(DIRS["sub"], par)
                os.makedirs(od, exist_ok=True)
                out = os.path.join(od, f"{par}.dim")
                
                if os.path.exists(out):
                    log(f"Subset {par} ya existe.")
                    continue
                    
                current_process["progress"] = int((i/len(ifg_dirs))*100)
                log(f"Subset espacial IFG {par} ({i+1}/{len(ifg_dirs)})...")
                run_gpt(grafo, {"input": inp, "geoRegion": geo, "output": out})
            log("Paso 4 completado.")
        finally:
            current_process["running"] = False
            current_process["progress"] = 100
            
    threading.Thread(target=run, daemon=True).start()
    return jsonify({"ok": True})

@app.route("/api/step5", methods=["POST"])
def api_step5():
    """SNAPHU Export"""
    if current_process["running"]:
        return jsonify({"error": "Proceso en ejecucion"}), 400
    def run():
        current_process["running"] = True
        current_process["step"] = "Paso 5: SNAPHU Export"
        try:
            grafo = os.path.join(GRAPHS_DIR, "snaphu_export.xml")
            folders = glob.glob(os.path.join(DIRS["sub"], "*_*"))
            for i, folder in enumerate(folders):
                par = os.path.basename(folder)
                inp = os.path.join(folder, f"{par}.dim")
                out = os.path.join(DIRS["exp"], par)
                if not os.path.exists(inp): continue
                os.makedirs(out, exist_ok=True)
                if glob.glob(os.path.join(out, "**", "snaphu.conf"), recursive=True):
                    log(f"Export {par} ya existe.")
                    continue
                current_process["progress"] = int((i/len(folders))*100)
                log(f"Exportando SNAPHU {par}...")
                run_gpt(grafo, {"input": inp, "targetFolder": out})
            log("Paso 5 completado.")
        finally:
            current_process["running"] = False
            current_process["progress"] = 100
    threading.Thread(target=run, daemon=True).start()
    return jsonify({"ok": True})

@app.route("/api/step8", methods=["POST"])
def api_step8():
    """Terrain Correction Pha/Coh"""
    if current_process["running"]:
        return jsonify({"error": "Proceso en ejecucion"}), 400
    data = request.json
    geo = data.get("geoRegion", "")
    dem_name = data.get("demName", "Copernicus 30m Global DEM")
    def run():
        current_process["running"] = True
        current_process["step"] = "Paso 8: TC Pha/Coh"
        try:
            import xml.etree.ElementTree as ET
            grafo = os.path.join(GRAPHS_DIR, "subset_Pha_Coh.xml")
            log(f"DEM seleccionado: {dem_name}")
            dirs = glob.glob(os.path.join(DIRS["sub"], "*_*"))
            for i, folder in enumerate(dirs):
                par = os.path.basename(folder)
                dim_files = glob.glob(os.path.join(folder, "*.dim"))
                if not dim_files: continue
                inp = dim_files[0]
                try:
                    tree = ET.parse(inp)
                    root = tree.getroot()
                    bands = [b.text for b in root.findall(".//Spectral_Band_Info/BAND_NAME")]
                    phase = next((b for b in bands if b.startswith("Phase_ifg")), None)
                    coh = next((b for b in bands if b.startswith("coh_")), None)
                except: continue
                if not phase or not coh: continue
                od = os.path.join(DIRS["mpi"], par)
                os.makedirs(od, exist_ok=True)
                op = os.path.join(od, f"{par}_filt_int_sub_tc.dim")
                oc = os.path.join(od, f"{par}_coh_tc.dim")
                if os.path.exists(op) and os.path.exists(oc):
                    log(f"Ya procesado: {par}")
                    continue
                current_process["progress"] = int((i/len(dirs))*100)
                log(f"TC Pha/Coh {par}...")
                run_gpt(grafo, {"source": inp, "phase": phase, "coh": coh, "geoRegion": geo, "demName": dem_name, "out_phase": op, "out_coh": oc})
            log("Paso 8 completado.")
        finally:
            current_process["running"] = False
            current_process["progress"] = 100
    threading.Thread(target=run, daemon=True).start()
    return jsonify({"ok": True})

@app.route("/api/step9", methods=["POST"])
def api_step9():
    """Terrain Correction UNW"""
    if current_process["running"]:
        return jsonify({"error": "Proceso en ejecucion"}), 400
    data = request.json
    geo = data.get("geoRegion", "")
    dem_name = data.get("demName", "Copernicus 30m Global DEM")
    def run():
        current_process["running"] = True
        current_process["step"] = "Paso 9: TC UNW"
        try:
            import xml.etree.ElementTree as ET
            grafo = os.path.join(GRAPHS_DIR, "subset_unw.xml")
            log(f"DEM seleccionado: {dem_name}")
            dirs = glob.glob(os.path.join(DIRS["imp"], "*_*"))
            for i, folder in enumerate(dirs):
                par = os.path.basename(folder)
                dim_files = glob.glob(os.path.join(folder, "*.dim"))
                if not dim_files: continue
                inp = dim_files[0]
                try:
                    tree = ET.parse(inp)
                    root = tree.getroot()
                    bands = [b.text for b in root.findall(".//Spectral_Band_Info/BAND_NAME")]
                    unw = next((b for b in bands if b.startswith("Unw")), None)
                except: continue
                if not unw: continue
                od = os.path.join(DIRS["mpi"], par)
                if not os.path.exists(od): continue
                ou = os.path.join(od, f"{par}_unw_tc.dim")
                if os.path.exists(ou):
                    log(f"UNW {par} ya existe.")
                    continue
                current_process["progress"] = int((i/len(dirs))*100)
                log(f"TC UNW {par}...")
                run_gpt(grafo, {"source": inp, "unwphase": unw, "geoRegion": geo, "demName": dem_name, "out_unw": ou})
            log("Paso 9 completado.")
        finally:
            current_process["running"] = False
            current_process["progress"] = 100
    threading.Thread(target=run, daemon=True).start()
    return jsonify({"ok": True})

@app.route("/api/step10", methods=["POST"])
def api_step10():
    """Configurar MintPy"""
    data = request.json
    ref_lat = data.get("ref_lat", "")
    ref_lon = data.get("ref_lon", "")
    era5_key = data.get("era5_key", "")
    era5_url = data.get("era5_url", "https://cds.climate.copernicus.eu/api")
    use_era5 = data.get("use_era5", False)
    
    cfg_path = os.path.join(DIRS["mpr"], "smallbaselineApp.cfg")
    if os.path.exists(cfg_path):
        with open(cfg_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Reference point
        if ref_lat and ref_lon:
            content = re.sub(r'mintpy\.reference\.lalo\s*=\s*.*', f'mintpy.reference.lalo       = {ref_lat}:{ref_lon}', content)
        # ERA5
        if not use_era5:
            content = re.sub(r'mintpy\.troposphericDelay\.method\s*=\s*.*', 'mintpy.troposphericDelay.method        = no', content)
        else:
            content = re.sub(r'mintpy\.troposphericDelay\.method\s*=\s*.*', 'mintpy.troposphericDelay.method        = pyaps', content)
            if era5_key:
                cds = os.path.join(DIRS["mpr"], ".cdsapirc")
                with open(cds, "w") as f:
                    f.write(f"url: {era5_url}\nkey: {era5_key}\n")
        with open(cfg_path, "w", encoding="utf-8") as f:
            f.write(content)
    
    wsl = DIRS["mpr"].replace("\\", "/").replace("C:", "/mnt/c")
    return jsonify({"ok": True, "wsl_path": wsl, "cfg": cfg_path})

if __name__ == "__main__":
    print("=" * 50)
    print("  PIPELINE InSAR - Interfaz Web")
    print("  Abra su navegador en: http://localhost:5000")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000, debug=False)
