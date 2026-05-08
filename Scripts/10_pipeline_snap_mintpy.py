# -*- coding: utf-8 -*-
"""
===================================================================================
 SCRIPT 10 - ORQUESTADOR AUTOMATIZADO SNAP / SNAPHU PARA PREPROCESAMIENTO InSAR
===================================================================================
Este script automatiza el flujo de trabajo metodológico para preparar datos 
Sentinel-1 desde su formato crudo (.zip) hasta el formato ingerible por MintPy 
(.dim con subconjuntos de Fase, Coherencia y Fase Desenvolvida).

Reemplaza todos los scripts en bash (.sh) y powershell (.ps1) originales, 
integrando todo en una sola herramienta interactiva que permite pausar entre pasos 
para validar los grafos en la GUI de SNAP.

Requisitos:
- SNAP instalado y gpt.exe configurado.
- SNAPHU binario configurado.
"""

import os
import sys
import glob
import re
import subprocess
from datetime import datetime, timedelta
from itertools import combinations
import xml.etree.ElementTree as ET

# Variables globales que se llenarán dinámicamente
GPT_BIN = None
SNAPHU_BIN = None

# Rutas del proyecto
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Datos_Profesor"))
GRAPHS_DIR = os.path.join(os.path.dirname(__file__), "SNAP_Graphs")

# Variable global para coordenadas del subset (se pide al usuario una sola vez)
GEO_REGION = None
# Variable global para el modelo digital de elevación seleccionado
DEM_NAME = "Copernicus 30m Global DEM"

# Carpetas de trabajo
RAW_DIR = os.path.join(BASE_DIR, "00_RAW_ZIP")          # Donde van los zips de Sentinel-1
DATOS_DIR = os.path.join(BASE_DIR, "01_DATOS_SLC")      # Archivos .dim renombrados (YYYMMDD.dim)
IFG_DIR = os.path.join(BASE_DIR, "02_INTERFEROGRAMAS")  # Salidas de SBAS
SUBSETS_DIR = os.path.join(BASE_DIR, "03_SUBSETS")      # Salidas del Subset Grafo
EXPORT_DIR = os.path.join(BASE_DIR, "04_SNAPHU_EXPORT") # Exportación para SNAPHU
IMPORT_DIR = os.path.join(BASE_DIR, "05_SNAPHU_IMPORT") # Importación de SNAPHU
MINTPY_DIR = os.path.join(BASE_DIR, "06_MINTPY_INPUTS") # Archivos finales para MintPy
MINTPY_RESULTS = os.path.join(BASE_DIR, "07_MINTPY_RESULTS") # Donde se corre MintPy

# Crear estructura de carpetas si no existe
for d in [RAW_DIR, DATOS_DIR, IFG_DIR, SUBSETS_DIR, EXPORT_DIR, IMPORT_DIR, MINTPY_DIR, MINTPY_RESULTS]:
    os.makedirs(d, exist_ok=True)

import shutil

def find_executable(name, common_paths):
    """Busca un ejecutable en el PATH o en rutas comunes."""
    path = shutil.which(name)
    if path: return path
    for p in common_paths:
        if os.path.exists(p): return p
    return None

def check_dependencies():
    global GPT_BIN, SNAPHU_BIN
    
    # 1. Buscar gpt.exe
    gpt_paths = [
        r"C:\Program Files\snap\bin\gpt.exe",
        r"C:\Program Files\esa-snap\bin\gpt.exe",
        r"C:\snap\bin\gpt.exe"
    ]
    GPT_BIN = find_executable("gpt.exe", gpt_paths)
    
    while not GPT_BIN or not os.path.exists(GPT_BIN):
        print("\nERROR: No se pudo encontrar automáticamente 'gpt.exe' (SNAP).")
        user_path = input("Por favor, arrastre aquí el ejecutable gpt.exe o ingrese su ruta completa:\n> ").strip().strip('"')
        if os.path.exists(user_path) and user_path.lower().endswith("gpt.exe"):
            GPT_BIN = user_path
        else:
            print("Ruta inválida. Asegúrese de apuntar directamente al archivo gpt.exe.")
            
    # 2. Buscar snaphu.exe
    snaphu_paths = [
        r"C:\TESIS\snaphu_bin\bin\snaphu.exe",
        r"C:\snaphu\bin\snaphu.exe"
    ]
    SNAPHU_BIN = find_executable("snaphu.exe", snaphu_paths)
    
    if not SNAPHU_BIN:
        print("\nADVERTENCIA: No se encontró 'snaphu.exe' automáticamente.")
        print("El Desenvolvimiento de Fase (Unwrapping) fallará si no lo configura más adelante.")
        # No bloqueamos el script entero por SNAPHU, ya que solo se usa en el paso 6.

    if not os.path.exists(GRAPHS_DIR):
        print(f"\nERROR: No se encontró la carpeta de grafos XML en {GRAPHS_DIR}")
        sys.exit(1)


def ask_geo_region():
    """Solicita las coordenadas del area de estudio una sola vez."""
    global GEO_REGION
    if GEO_REGION:
        return GEO_REGION
    print("\n--- CONFIGURACION DEL AREA DE ESTUDIO ---")
    print("Ingrese las coordenadas geograficas del rectangulo de interes.")
    print("(Estas se usaran en todos los Subsets y Terrain Corrections)")
    print("Ejemplo para Cartagena: lonMin=-75.65, lonMax=-75.40, latMin=10.30, latMax=10.52\n")
    lon_min = input("Longitud minima (oeste, ej. -75.65): ").strip()
    lon_max = input("Longitud maxima (este, ej. -75.40): ").strip()
    lat_min = input("Latitud minima (sur, ej. 10.30): ").strip()
    lat_max = input("Latitud maxima (norte, ej. 10.52): ").strip()
    GEO_REGION = (f"POLYGON (({lon_min} {lat_min}, {lon_max} {lat_min}, "
                  f"{lon_max} {lat_max}, {lon_min} {lat_max}, "
                  f"{lon_min} {lat_min}, {lon_min} {lat_min}))")
    print(f"GeoRegion configurado: {GEO_REGION}\n")
    return GEO_REGION


def extract_date_from_sentinel(filename):
    """Extrae la fecha YYYYMMDD del nombre de un archivo Sentinel-1 usando regex."""
    # Patron 1: formato estandar S1A/B_IW_SLC__1SDV_YYYYMMDDTHHMMSS_...
    m = re.search(r'S1[AB]_\w+_(\d{8})T\d{6}', filename)
    if m:
        return m.group(1)
    # Patron 2: cualquier secuencia de 8 digitos que empiece con 20
    m = re.search(r'(20\d{6})', filename)
    if m:
        return m.group(1)
    return None


def ask_continue(step_name):
    """Pausa el script para que el usuario valide el paso anterior."""
    print(f"\n[{step_name}] finalizado.")
    print("Puede verificar los productos en la GUI de SNAP si lo desea.")
    while True:
        resp = input(f"¿Desea continuar con el siguiente paso? (S/N): ").strip().upper()
        if resp == 'S':
            return True
        elif resp == 'N':
            print("Proceso detenido por el usuario.")
            sys.exit(0)
        else:
            print("Por favor, responda S o N.")


def run_gpt(graph_path, params_dict=None):
    """Ejecuta gpt.exe con un grafo XML y parámetros."""
    cmd = [GPT_BIN, graph_path]
    if params_dict:
        for key, val in params_dict.items():
            cmd.append(f"-P{key}={val}")
    cmd.append("-e") # Mostrar errores
    
    print(f"Ejecutando: {' '.join(cmd)}")
    result = subprocess.run(cmd, stdout=sys.stdout, stderr=sys.stderr)
    return result.returncode == 0


def step_1_and_2_split_orbit_rename():
    print("\n" + "="*50)
    print(" PASO 1 & 2: TOPSAR-Split + Apply-Orbit + Rename")
    print("="*50)
    
    zips = glob.glob(os.path.join(RAW_DIR, "*.zip"))
    if not zips:
        print(f"No se encontraron archivos .zip en {RAW_DIR}")
        return

    subswath = input("Ingrese el Subswath deseado (ej. IW1, IW2, IW3): ").strip().upper()
    first_burst = input("Ingrese el índice del primer Burst (ej. 1): ").strip()
    last_burst = input("Ingrese el índice del último Burst (ej. 9): ").strip()

    # Se usa un XML temporal que inyecta estos parámetros
    graph_xml = f"""<graph id="Graph">
    <version>1.0</version>
    <node id="Read">
      <operator>Read</operator>
      <parameters><file>${{input}}</file></parameters>
    </node>
    <node id="TOPSAR-Split">
      <operator>TOPSAR-Split</operator>
      <sources><sourceProduct refid="Read"/></sources>
      <parameters>
        <subswath>{subswath}</subswath>
        <selectedPolarisations>VV</selectedPolarisations>
        <firstBurstIndex>{first_burst}</firstBurstIndex>
        <lastBurstIndex>{last_burst}</lastBurstIndex>
      </parameters>
    </node>
    <node id="Apply-Orbit-File">
      <operator>Apply-Orbit-File</operator>
      <sources><sourceProduct refid="TOPSAR-Split"/></sources>
      <parameters>
        <orbitType>Sentinel Precise (Auto Download)</orbitType>
        <polyDegree>3</polyDegree>
        <continueOnFail>true</continueOnFail>
      </parameters>
    </node>
    <node id="Write">
      <operator>Write</operator>
      <sources><sourceProduct refid="Apply-Orbit-File"/></sources>
      <parameters><file>${{output}}</file><formatName>BEAM-DIMAP</formatName></parameters>
    </node>
    </graph>"""

    temp_graph = os.path.join(GRAPHS_DIR, "temp_split_orbit.xml")
    with open(temp_graph, "w", encoding="utf-8") as f:
        f.write(graph_xml)

    for zip_file in zips:
        basename = os.path.basename(zip_file)
        fecha = extract_date_from_sentinel(basename)
        if not fecha:
            print(f"ADVERTENCIA: No se pudo extraer la fecha automaticamente de: {basename}")
            fecha = input(f"Ingrese la fecha manualmente (YYYYMMDD): ").strip()
            
        out_file = os.path.join(DATOS_DIR, f"{fecha}.dim")
        
        if os.path.exists(out_file):
            print(f"Saltando {fecha}, ya existe.")
            continue
            
        print(f"Procesando {fecha}...")
        success = run_gpt(temp_graph, {"input": zip_file, "output": out_file})
        if not success:
            print(f"Error procesando {fecha}")
            
    if os.path.exists(temp_graph):
        os.remove(temp_graph)


def generate_sbas_pairs(dates, max_temporal_days=90, max_pairs_per_image=4):
    """Genera pares SBAS automaticamente a partir de una lista de fechas."""
    date_objs = sorted([datetime.strptime(d, "%Y%m%d") for d in dates])
    pairs = []
    for i, d1 in enumerate(date_objs):
        count = 0
        for d2 in date_objs[i+1:]:
            delta = (d2 - d1).days
            if delta <= max_temporal_days:
                pairs.append((d1.strftime("%Y%m%d"), d2.strftime("%Y%m%d")))
                count += 1
                if count >= max_pairs_per_image:
                    break
    return pairs


def step_3_sbas():
    print("\n" + "="*50)
    print(" PASO 3: Generacion de Interferogramas (SBAS)")
    print("="*50)
    
    grafo = os.path.join(GRAPHS_DIR, "Grafo_auto_G.xml")
    if not os.path.exists(grafo):
        print(f"No se encontro {grafo}")
        return

    pares_file = os.path.join(BASE_DIR, "pares_sbas.txt")
    
    # Si no existe pares_sbas.txt, generarlo automaticamente
    if not os.path.exists(pares_file):
        print("No se encontro pares_sbas.txt. Se generara automaticamente.")
        dim_files = glob.glob(os.path.join(DATOS_DIR, "*.dim"))
        fechas = [os.path.basename(f).replace(".dim", "") for f in dim_files]
        fechas = [f for f in fechas if re.match(r'^20\d{6}$', f)]
        
        if len(fechas) < 2:
            print("Se necesitan al menos 2 imagenes .dim en 01_DATOS_SLC.")
            return
        
        print(f"Se detectaron {len(fechas)} imagenes.")
        max_days = input("Separacion temporal maxima en dias (default 90): ").strip()
        max_days = int(max_days) if max_days else 90
        max_ppimg = input("Maximo de pares por imagen (default 4): ").strip()
        max_ppimg = int(max_ppimg) if max_ppimg else 4
        
        pares_gen = generate_sbas_pairs(fechas, max_days, max_ppimg)
        
        with open(pares_file, "w") as f:
            for m, s in pares_gen:
                f.write(f"{m}_{s}\n")
        print(f"Se generaron {len(pares_gen)} pares en {pares_file}")
    
    with open(pares_file, "r") as f:
        pares = [line.strip() for line in f if line.strip()]

    for par in pares:
        parts = par.split("_")
        if len(parts) < 2: continue
        m_date, s_date = parts[0], parts[1]
        master_file = os.path.join(DATOS_DIR, f"{m_date}.dim")
        slave_file = os.path.join(DATOS_DIR, f"{s_date}.dim")
        out_dir = os.path.join(IFG_DIR, par)
        out_file = os.path.join(out_dir, f"{par}.dim")
        
        if not os.path.exists(master_file) or not os.path.exists(slave_file):
            print(f"Faltan insumos para el par {par}. Saltando.")
            continue
            
        os.makedirs(out_dir, exist_ok=True)
        if os.path.exists(out_file):
            print(f"El par {par} ya existe.")
            continue
            
        print(f"Generando IFG para {par}...")
        run_gpt(grafo, {
            "master": master_file,
            "slave": slave_file,
            "output": out_file,
            "demName": DEM_NAME
        })


def step_4_subset():
    print("\n" + "="*50)
    print(" PASO 4: Subset Espacial (Reducir área)")
    print("="*50)
    
    grafo = os.path.join(GRAPHS_DIR, "subset_grapho.xml")
    if not os.path.exists(grafo):
        print("Grafo subset_grapho.xml no encontrado.")
        return
        
    print("Por favor, ingrese las coordenadas de su area de estudio.")
    print("Ejemplo para Cartagena: lonMin=-75.65, lonMax=-75.40, latMin=10.30, latMax=10.52\n")
    lon_min = input("Longitud minima (oeste, ej. -75.65): ").strip()
    lon_max = input("Longitud maxima (este, ej. -75.40): ").strip()
    lat_min = input("Latitud minima (sur, ej. 10.30): ").strip()
    lat_max = input("Latitud maxima (norte, ej. 10.52): ").strip()
    
    if not all([lon_min, lon_max, lat_min, lat_max]):
        print("Debe ingresar todas las coordenadas. Operacion cancelada.")
        return
        
    geo_region = f"POLYGON (({lon_min} {lat_min}, {lon_max} {lat_min}, {lon_max} {lat_max}, {lon_min} {lat_max}, {lon_min} {lat_min}, {lon_min} {lat_min}))"
        
    ifg_folders = glob.glob(os.path.join(IFG_DIR, "*_*"))
    for folder in ifg_folders:
        par = os.path.basename(folder)
        input_dim = os.path.join(folder, f"{par}.dim")
        out_dir = os.path.join(SUBSETS_DIR, par)
        out_dim = os.path.join(out_dir, f"{par}.dim")
        
        if not os.path.exists(input_dim): continue
        os.makedirs(out_dir, exist_ok=True)
        
        if os.path.exists(out_dim):
            print(f"Subset {par} ya existe.")
            continue
            
        print(f"Subset para {par}...")
        run_gpt(grafo, {"input": input_dim, "geoRegion": geo_region, "output": out_dim})


def step_5_snaphu_export():
    print("\n" + "="*50)
    print(" PASO 5: Exportacion a SNAPHU")
    print("="*50)
    print("NOTA: Se corrige la ruta de salida para evitar el problema")
    print("de la doble carpeta (output folder fuera del directorio esperado).\n")
    
    grafo = os.path.join(GRAPHS_DIR, "snaphu_export.xml")
    subset_folders = glob.glob(os.path.join(SUBSETS_DIR, "*_*"))
    
    for folder in subset_folders:
        par = os.path.basename(folder)
        input_dim = os.path.join(folder, f"{par}.dim")
        out_dir = os.path.join(EXPORT_DIR, par)
        
        if not os.path.exists(input_dim): continue
        os.makedirs(out_dir, exist_ok=True)
        
        # Verificar si ya se exporto (buscando .conf en cualquier subcarpeta)
        if glob.glob(os.path.join(out_dir, "**", "snaphu.conf"), recursive=True):
            print(f"Export {par} ya existe.")
            continue
        
        # FIX Error #4: Usar targetFolder apuntando directamente a out_dir
        # SNAP crea una subcarpeta con el nombre del producto dentro de targetFolder.
        # Pasamos out_dir como targetFolder para que la subcarpeta quede DENTRO.
        print(f"Exportando SNAPHU para {par}...")
        run_gpt(grafo, {"input": input_dim, "targetFolder": out_dir})
        
        # FIX Error #4: Si SNAP creo la carpeta fuera (en la raiz del proyecto),
        # buscarla y moverla al lugar correcto
        possible_stray = glob.glob(os.path.join(BASE_DIR, "..", "*snaphu*"), recursive=False)
        for stray in possible_stray:
            if os.path.isdir(stray):
                stray_conf = glob.glob(os.path.join(stray, "snaphu.conf"))
                if stray_conf:
                    import shutil as _sh
                    dest = os.path.join(out_dir, os.path.basename(stray))
                    if not os.path.exists(dest):
                        print(f"  -> Moviendo carpeta perdida: {stray} -> {dest}")
                        _sh.move(stray, dest)


def step_6_unwrap():
    print("\n" + "="*50)
    print(" PASO 6: Desenvolvimiento de Fase (Unwrapping con SNAPHU)")
    print("="*50)
    
    global SNAPHU_BIN
    
    if not SNAPHU_BIN or not os.path.exists(SNAPHU_BIN):
        print(f"ADVERTENCIA: SNAPHU no fue detectado en el sistema.")
        user_snaphu = input("Por favor, ingrese la ruta completa a snaphu.exe (o presione Enter para cancelar): ").strip().strip('"')
        if os.path.exists(user_snaphu) and user_snaphu.lower().endswith("snaphu.exe"):
            SNAPHU_BIN = user_snaphu
        else:
            print("Operación cancelada o ruta inválida.")
            return

    export_folders = sorted(glob.glob(os.path.join(EXPORT_DIR, "*_*")))
    if not export_folders:
        print("No hay carpetas de exportación.")
        return
        
    start_from = input("Ingrese el par desde donde retomar (ej. 20210716_20210728) o presione Enter para procesar todos: ").strip()
    start_found = False if start_from else True
    
    nproc = "16" # Número de hilos
    
    for folder in export_folders:
        par = os.path.basename(folder)
        
        if not start_found:
            if par == start_from:
                start_found = True
            else:
                continue
                
        # SNAPHU Export crea una subcarpeta con el nombre del producto, hay que entrar allí
        subdirs = [os.path.join(folder, d) for d in os.listdir(folder) if os.path.isdir(os.path.join(folder, d))]
        if not subdirs: continue
        work_dir = subdirs[0]
        
        phase_img = glob.glob(os.path.join(work_dir, "Phase*.img"))
        phase_hdr = glob.glob(os.path.join(work_dir, "Phase*.hdr"))
        if not phase_img or not phase_hdr:
            print(f"Falta Phase.img/hdr en {par}")
            continue
            
        phase_img = os.path.basename(phase_img[0])
        hdr_path = phase_hdr[0]
        
        # Extraer 'samples' del hdr
        width = None
        with open(hdr_path, "r") as f:
            for line in f:
                if "samples" in line.lower():
                    width = line.split("=")[1].strip()
                    break
                    
        if not width:
            print(f"Error leyendo samples en {par}")
            continue
            
        out_unw = "UnwPhase.img"
        cmd = [SNAPHU_BIN, phase_img, width, "-f", "snaphu.conf", "--nproc", nproc, "-o", out_unw]
        
        print(f"Desenvolviendo {par}...")
        try:
            subprocess.run(cmd, cwd=work_dir, check=True)
            # Renombrar
            baseName = phase_img.replace("Phase_ifg_", "").replace(".snaphu.img", "")
            final_name = f"UnwPhase_ifg_{baseName}.snaphu.img"
            os.rename(os.path.join(work_dir, out_unw), os.path.join(work_dir, final_name))
            print(f"OK -> {final_name}")
        except subprocess.CalledProcessError:
            print(f"Error en SNAPHU para {par}")


def step_7_snaphu_import():
    print("\n" + "="*50)
    print(" PASO 7: Importación de Fase Desenvolvida (SNAPHU Import)")
    print("="*50)
    
    grafo = os.path.join(GRAPHS_DIR, "snaphu_import.xml")
    ifg_folders = glob.glob(os.path.join(SUBSETS_DIR, "*_*"))
    
    for folder in ifg_folders:
        par = os.path.basename(folder)
        ifg_dim = glob.glob(os.path.join(folder, "*.dim"))
        if not ifg_dim: continue
        ifg_dim = ifg_dim[0]
        
        unw_hdr = glob.glob(os.path.join(EXPORT_DIR, par, "*", "UnwPhase*.hdr"))
        if not unw_hdr: continue
        unw_hdr = unw_hdr[0]
        
        out_dir = os.path.join(IMPORT_DIR, par)
        out_dim = os.path.join(out_dir, f"{par}.dim")
        
        os.makedirs(out_dir, exist_ok=True)
        if os.path.exists(out_dim):
            print(f"Import {par} ya existe.")
            continue
            
        print(f"Importando SNAPHU para {par}...")
        run_gpt(grafo, {
            "input_ifg": ifg_dim,
            "input_unw": unw_hdr,
            "output": out_dim
        })


def step_8_subset_pha_coh():
    print("\n" + "="*50)
    print(" PASO 8: Terrain Correction de Fase y Coherencia (MintPy Inputs)")
    print("="*50)
    
    geo_region = ask_geo_region()
    grafo = os.path.join(GRAPHS_DIR, "subset_Pha_Coh.xml")
    dirs = glob.glob(os.path.join(SUBSETS_DIR, "*_*"))
    
    for folder in dirs:
        par = os.path.basename(folder)
        dim_files = glob.glob(os.path.join(folder, "*.dim"))
        if not dim_files: continue
        input_dim = dim_files[0]
        
        try:
            tree = ET.parse(input_dim)
            root = tree.getroot()
            band_names = [b.text for b in root.findall(".//Spectral_Band_Info/BAND_NAME")]
            phase_band = next((b for b in band_names if b.startswith("Phase_ifg")), None)
            coh_band = next((b for b in band_names if b.startswith("coh_")), None)
        except:
            print(f"Error leyendo bandas en {par}")
            continue
            
        if not phase_band or not coh_band:
            print(f"Faltan bandas en {par}")
            continue
            
        out_dir = os.path.join(MINTPY_DIR, par)
        os.makedirs(out_dir, exist_ok=True)
        
        out_phase = os.path.join(out_dir, f"{par}_filt_int_sub_tc.dim")
        out_coh = os.path.join(out_dir, f"{par}_coh_tc.dim")
        
        if os.path.exists(out_phase) and os.path.exists(out_coh):
            print(f"Ya procesado: {par}")
            continue
            
        print(f"Terrain Correction (Pha/Coh) para {par}...")
        run_gpt(grafo, {
            "source": input_dim,
            "phase": phase_band,
            "coh": coh_band,
            "geoRegion": geo_region,
            "demName": DEM_NAME,
            "out_phase": out_phase,
            "out_coh": out_coh
        })


def step_9_subset_unw():
    print("\n" + "="*50)
    print(" PASO 9: Terrain Correction de Fase Desenvolvida (UNW)")
    print("="*50)
    
    geo_region = ask_geo_region()
    grafo = os.path.join(GRAPHS_DIR, "subset_unw.xml")
    dirs = glob.glob(os.path.join(IMPORT_DIR, "*_*"))
    
    for folder in dirs:
        par = os.path.basename(folder)
        dim_files = glob.glob(os.path.join(folder, "*.dim"))
        if not dim_files: continue
        input_dim = dim_files[0]
        
        try:
            tree = ET.parse(input_dim)
            root = tree.getroot()
            band_names = [b.text for b in root.findall(".//Spectral_Band_Info/BAND_NAME")]
            unw_band = next((b for b in band_names if b.startswith("Unw")), None)
        except:
            continue
            
        if not unw_band: continue
        
        out_dir = os.path.join(MINTPY_DIR, par)
        if not os.path.exists(out_dir):
            print(f"Advertencia: no existe carpeta MintPy para {par}. Ejecute Paso 8 primero.")
            continue
            
        out_unw = os.path.join(out_dir, f"{par}_unw_tc.dim")
        
        if os.path.exists(out_unw):
            print(f"UNW de {par} ya existe.")
            continue
            
        print(f"Terrain Correction (UNW) para {par}...")
        run_gpt(grafo, {
            "source": input_dim,
            "unwphase": unw_band,
            "geoRegion": geo_region,
            "demName": DEM_NAME,
            "out_unw": out_unw
        })


def step_10_mintpy():
    print("\n" + "="*50)
    print(" PASO 10: Inversion en MintPy (WSL)")
    print("="*50)
    print("Los interferogramas estan listos en:")
    print(f"  ENTRADA: {MINTPY_DIR}")
    print(f"  SALIDA:  {MINTPY_RESULTS}")
    print("")
    
    # --- Solicitar punto de referencia al usuario ---
    print("--- CONFIGURACION DEL PUNTO DE REFERENCIA ---")
    print("Ingrese las coordenadas del punto donde la velocidad sera 0 mm/a.")
    print("Debe ser un punto estable (ej. estacion GNSS, cerro rocoso).")
    print("Ejemplo Cartagena (Castillo San Felipe): lat=10.4225, lon=-75.5397\n")
    ref_lat = input("Latitud del punto de referencia (ej. 10.4225): ").strip()
    ref_lon = input("Longitud del punto de referencia (ej. -75.5397): ").strip()
    ref_lalo = f"{ref_lat}:{ref_lon}"
    
    # --- Escribir en el .cfg ---
    cfg_path = os.path.join(MINTPY_RESULTS, "smallbaselineApp.cfg")
    if os.path.exists(cfg_path):
        with open(cfg_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Reemplazar la linea de reference.lalo
        import re as _re
        content = _re.sub(
            r'mintpy\.reference\.lalo\s*=\s*.*',
            f'mintpy.reference.lalo       = {ref_lalo}',
            content
        )
        with open(cfg_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"\n[OK] Punto de referencia guardado en smallbaselineApp.cfg: {ref_lalo}")
    else:
        print(f"\nADVERTENCIA: No se encontro {cfg_path}")
        print(f"Debera configurar manualmente: mintpy.reference.lalo = {ref_lalo}")
    
    # --- Configuracion ERA5 ---
    print("\n--- CONFIGURACION DE CORRECCION ATMOSFERICA (ERA5) ---")
    print("La correccion atmosferica mejora la precision removiendo")
    print("retardos troposfericos de cada interferograma.")
    print("Requiere una cuenta GRATUITA en: https://cds.climate.copernicus.eu")
    print("")
    tiene_era5 = input("Tiene cuenta en CDS/ERA5? (S/N): ").strip().upper()
    
    if tiene_era5 == 'S':
        print("\nIngrese sus credenciales de la API de CDS.")
        print("Las encuentra en: https://cds.climate.copernicus.eu/how-to-api")
        era5_url = input("URL de la API (default: https://cds.climate.copernicus.eu/api): ").strip()
        if not era5_url:
            era5_url = "https://cds.climate.copernicus.eu/api"
        era5_key = input("API Key (ej. 12345:abcdef-1234-5678-...): ").strip()
        
        if era5_key:
            # Crear el archivo .cdsapirc en la carpeta del proyecto
            # (el usuario debera copiarlo a ~/.cdsapirc en WSL)
            cdsapi_content = f"url: {era5_url}\nkey: {era5_key}\n"
            cdsapi_path = os.path.join(MINTPY_RESULTS, ".cdsapirc")
            with open(cdsapi_path, "w") as f:
                f.write(cdsapi_content)
            print(f"\n[OK] Archivo .cdsapirc guardado en {cdsapi_path}")
            print("IMPORTANTE: En WSL, copie este archivo a su home:")
            print(f"   cp {cdsapi_path.replace(chr(92), '/')} ~/.cdsapirc")
        else:
            print("No se ingreso API Key. ERA5 puede fallar.")
    else:
        print("\nSe desactivara la correccion atmosferica en el .cfg.")
        # Desactivar ERA5 en el cfg
        if os.path.exists(cfg_path):
            with open(cfg_path, "r", encoding="utf-8") as f:
                content = f.read()
            import re as _re2
            content = _re2.sub(
                r'mintpy\.troposphericDelay\.method\s*=\s*.*',
                'mintpy.troposphericDelay.method        = no',
                content
            )
            with open(cfg_path, "w", encoding="utf-8") as f:
                f.write(content)
            print("[OK] Correccion atmosferica desactivada en smallbaselineApp.cfg")
    
    # --- Instrucciones WSL ---
    wsl_results = MINTPY_RESULTS.replace("\\", "/").replace("C:", "/mnt/c")
    print("\n--- INSTRUCCIONES PARA EJECUTAR EN WSL ---")
    print("1. Abra su terminal de Ubuntu/WSL")
    print("2. Navegue a la carpeta de resultados:")
    print(f"   cd {wsl_results}")
    print("3. Active el entorno MintPy:")
    print("   mamba activate mintpy")
    if tiene_era5 == 'S':
        print("4. Copie las credenciales ERA5 a su home:")
        print("   cp .cdsapirc ~/.cdsapirc")
        print("5. Ejecute la inversion:")
    else:
        print("4. Ejecute la inversion:")
    print("   smallbaselineApp.py smallbaselineApp.cfg")
    print("")
    print("5. Al terminar, exporte los resultados a GeoTIFF:")
    print("   save_gdal.py velocity.h5 -o velocity.tif")
    print("   save_gdal.py inputs/geometryRadar.h5 incidenceAngle -o incidenceAngle.tif")
    print("")
    print("Los .tif exportados se usaran en el Paso 11 (cartografia).")
    print("="*50)


def step_11_postprocesamiento_cartografico():
    print("\n" + "="*50)
    print(" PASO 11: Post-Procesamiento y Cartografía (Automático)")
    print("="*50)
    print("Este paso consolida la FASE 2 de la tesis.")
    print("Ejecutará secuencialmente los scripts de visualización (01 al 09)")
    print("para generar mapas de velocidad, series temporales, efemérides y layouts.\n")
    
    scripts_dir = os.path.dirname(__file__)
    
    # Buscar scripts python numerados del 01 al 09
    carto_scripts = sorted(glob.glob(os.path.join(scripts_dir, "0*.py")))
    
    if not carto_scripts:
        print("No se detectaron scripts de cartografía (01_... a 09_...) en la carpeta Scripts.")
        return
        
    print("Se han detectado los siguientes módulos de salida gráfica:")
    for s in carto_scripts:
        print(f" - {os.path.basename(s)}")
        
    resp = input("\n¿Desea iniciar la cadena de generación cartográfica ahora? (S/N): ").strip().upper()
    if resp == 'S':
        for s in carto_scripts:
            print(f"\n>>>>> EJECUTANDO: {os.path.basename(s)} <<<<<")
            try:
                subprocess.run([sys.executable, s], check=True)
            except subprocess.CalledProcessError:
                print(f"Ocurrió un error crítico ejecutando {os.path.basename(s)}.")
                print("Proceso de cartografía detenido.")
                break
        print("\nCartografía finalizada con éxito. Revise la carpeta Productos.")
    else:
        print("Proceso omitido. Puede correr los scripts manualmente cuando desee.")


def main():
    print("*" * 65)
    print("  PIPELINE AUTOMATIZADO DE PREPROCESAMIENTO InSAR (SNAP)")
    print("*" * 65)
    
    check_dependencies()
    
    # Selección del DEM
    global DEM_NAME
    print("\nModelos Digitales de Elevacion disponibles:")
    dem_options = [
        "Copernicus 30m Global DEM",
        "SRTM 1Sec HGT",
        "SRTM 3Sec",
        "ACE30",
        "GETASSE30"
    ]
    for i, d in enumerate(dem_options, 1):
        default_tag = " (default)" if i == 1 else ""
        print(f"  {i}. {d}{default_tag}")
    dem_choice = input("Seleccione DEM (Enter para default): ").strip()
    if dem_choice and dem_choice.isdigit() and 1 <= int(dem_choice) <= len(dem_options):
        DEM_NAME = dem_options[int(dem_choice) - 1]
    print(f"DEM seleccionado: {DEM_NAME}\n")
    
    pasos = [
        ("TOPSAR-Split + Apply-Orbit + Rename", step_1_and_2_split_orbit_rename),
        ("Generación SBAS (Interferogramas)", step_3_sbas),
        ("Subset Espacial", step_4_subset),
        ("Exportación a SNAPHU", step_5_snaphu_export),
        ("SNAPHU Unwrapping", step_6_unwrap),
        ("Importación desde SNAPHU", step_7_snaphu_import),
        ("Subset y Terrain Correction (Pha/Coh)", step_8_subset_pha_coh),
        ("Subset y Terrain Correction (UNW)", step_9_subset_unw),
        ("Inversión de Serie de Tiempo en MintPy", step_10_mintpy),
        ("Generación de Salidas Gráficas y Cartografía Oficial", step_11_postprocesamiento_cartografico)
    ]
    
    print("\nSeleccione desde qué paso desea iniciar (1-11):")
    for i, (nombre, _) in enumerate(pasos, 1):
        print(f" {i}. {nombre}")
        
    try:
        inicio = int(input("Su elección: ")) - 1
        if inicio < 0 or inicio >= len(pasos):
            raise ValueError
    except ValueError:
        print("Elección inválida. Saliendo.")
        sys.exit(1)
        
    for i in range(inicio, len(pasos)):
        nombre_paso, funcion = pasos[i]
        funcion()
        if i < len(pasos) - 1:
            ask_continue(nombre_paso)


if __name__ == "__main__":
    main()
