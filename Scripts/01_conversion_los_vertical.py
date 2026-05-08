# -*- coding: utf-8 -*-
"""
SCRIPT 01 - CONVERSION LOS -> VERTICAL + FILTRO IQR
"""
import sys, os, glob, datetime
import numpy as np
import rasterio
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Datos_Profesor"))
PROD_DIR = os.path.join(BASE_DIR, "Productos")
os.makedirs(PROD_DIR, exist_ok=True)

class Logger(object):
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.log = open(filename, "a", encoding="utf-8")
        self.log.write("\n======================================================\n")
        self.log.write(f" EFEMÉRIDES DE EJECUCIÓN - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        self.log.write("======================================================\n")
    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
    def flush(self):
        self.terminal.flush()
        self.log.flush()

sys.stdout = Logger(os.path.join(PROD_DIR, "REPORTE_01_conversion_los_vertical.txt"))

raster_dir = os.path.join(BASE_DIR, "RASTERS VELOCIDAD")
if not os.path.exists(raster_dir): raster_dir = BASE_DIR
tif_files = glob.glob(os.path.join(raster_dir, "*.tif"))
ESCENARIOS = [os.path.basename(f).replace("velocity_", "").replace("_masked.tif", "").replace(".tif", "") for f in tif_files]
if not ESCENARIOS:
    print("Error: No se encontraron archivos .tif en RASTERS VELOCIDAD")
    sys.exit(1)

LIA_PATH = os.path.join(BASE_DIR, "RASTER INCIDENCIA", "local_incidente_angle.tif")
IQR_FACTOR = 1.5

CLASES = [
    {"nombre": "Subsidencia Critica",  "de": -9999, "hasta": -10.0, "color": "#0D47A1", "codigo": 1},
    {"nombre": "Subsidencia Moderada", "de": -10.0, "hasta":  -5.0, "color": "#1976D2", "codigo": 2},
    {"nombre": "Subsidencia Leve",     "de":  -5.0, "hasta":  -2.0, "color": "#64B5F6", "codigo": 3},
    {"nombre": "Estabilidad Relativa", "de":  -2.0, "hasta":   2.0, "color": "#FFFFFF", "codigo": 4},
    {"nombre": "Elevacion Leve",       "de":   2.0, "hasta":   5.0, "color": "#FFCDD2", "codigo": 5},
    {"nombre": "Elevacion Moderada",   "de":   5.0, "hasta":  10.0, "color": "#E53935", "codigo": 6},
    {"nombre": "Elevacion Critica",    "de":  10.0, "hasta":  9999, "color": "#B71C1C", "codigo": 7},
]

def cargar_raster(path):
    with rasterio.open(path) as src:
        data = src.read(1).astype(np.float64)
        nodata = src.nodata
        meta = src.meta.copy()
        if nodata is not None:
            data[data == nodata] = np.nan
        data[data == 0.0] = np.nan
    return data, meta

def filtrar_IQR(v, factor=1.5):
    Q1, Q3 = np.percentile(v, 25), np.percentile(v, 75)
    IQR = Q3 - Q1
    return Q1 - factor*IQR, Q3 + factor*IQR

def main():
    print("="*65)
    print("  SCRIPT 01 - CONVERSION LOS -> VERTICAL + FILTRO IQR")
    print("="*65)
    
    try:
        lia, _ = cargar_raster(LIA_PATH)
        cos_lia = np.cos(np.deg2rad(lia))
        lia_validos = lia[~np.isnan(lia)]
        print(f"LIA valido: media={np.mean(lia_validos):.2f} deg  N={len(lia_validos):,}")
    except Exception as e:
        print(f"Error cargando LIA: {e}. Asumiendo incidencia=0 (cos=1)")
        cos_lia = 1.0

    print(f"Factor IQR: {IQR_FACTOR}")
    print("-" * 65)
    
    todas_stats = []
    
    for esc, tif_path in zip(ESCENARIOS, tif_files):
        print(f"\n  Escenario: {esc.upper()}")
        los, meta = cargar_raster(tif_path)
        
        vert = (los / cos_lia) * 1000.0
        
        v_todos = vert[~np.isnan(vert)]
        if len(v_todos) == 0:
            print("    Raster vacio o corrupto. Saltando...")
            continue
            
        print(f"    Bruto   : N={len(v_todos):,}  media={np.mean(v_todos):.2f}  std={np.std(v_todos):.2f} mm/a")
        
        lower, upper = filtrar_IQR(v_todos, factor=IQR_FACTOR)
        v_filt = v_todos[(v_todos >= lower) & (v_todos <= upper)]
        outliers = len(v_todos) - len(v_filt)
        
        print(f"    Rango IQR [{lower:.2f}, {upper:.2f}]  Outliers={outliers:,} ({(outliers/len(v_todos))*100:.1f}%)")
        print(f"    Filtrado: N={len(v_filt):,}  media={np.mean(v_filt):.3f}  std={np.std(v_filt):.3f} mm/a")
        
        vert_clean = vert.copy()
        vert_clean[(vert_clean < lower) | (vert_clean > upper)] = np.nan
        
        out_tif = os.path.join(PROD_DIR, f"vertical_{esc}.tif")
        meta.update(dtype="float32", nodata=-9999.0)
        out_arr = vert_clean.astype(np.float32)
        out_arr[np.isnan(vert_clean)] = -9999.0
        with rasterio.open(out_tif, "w", **meta) as dst:
            dst.write(out_arr, 1)
        print(f"    Raster: {out_tif}")
        
        todas_stats.append({
            "Escenario": esc.upper(), "N_Bruto": len(v_todos), "Media_Bruta": np.mean(v_todos),
            "Limite_Inf_IQR": lower, "Limite_Sup_IQR": upper, "N_Outliers": outliers,
            "N_Filtrado": len(v_filt), "Media_Filtrada": np.mean(v_filt), "Std_Filtrada": np.std(v_filt)
        })

    if todas_stats:
        pd.DataFrame(todas_stats).to_csv(os.path.join(PROD_DIR, "estadisticas_conversion.csv"), index=False)
        print(f"\nCSV: {os.path.join(PROD_DIR, 'estadisticas_conversion.csv')}")

    print("="*65)
    print("  SCRIPT 01 COMPLETADO")
    print("="*65)

if __name__ == "__main__":
    main()
