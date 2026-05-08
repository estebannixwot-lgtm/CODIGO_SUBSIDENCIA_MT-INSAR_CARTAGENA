# -*- coding: utf-8 -*-
"""
SCRIPT 05 - RECORTE A LOCALIDAD HISTORICA + ANALISIS ESPACIAL
"""
import sys, os, glob, datetime
os.environ["SHAPE_RESTORE_SHX"] = "YES"

import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.mask import mask as rio_mask
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

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

sys.stdout = Logger(os.path.join(PROD_DIR, "REPORTE_05_recorte_localidad_historica.txt"))

shp_files = glob.glob(os.path.join(BASE_DIR, "SHAPE AREA DE ESTUDIO", "*.shp"))
if shp_files:
    SHP_PATH = shp_files[0]
else:
    SHP_PATH = os.path.join(BASE_DIR, "Division_Politica_Localidades.shp")

raster_dir = os.path.join(BASE_DIR, "RASTERS VELOCIDAD")
if not os.path.exists(raster_dir): raster_dir = BASE_DIR
tif_files = glob.glob(os.path.join(raster_dir, "*.tif"))
ESCENARIOS = [os.path.basename(f).replace("velocity_", "").replace("_masked.tif", "").replace(".tif", "") for f in tif_files]

def filtrar_IQR(v, factor=1.5):
    Q1, Q3 = np.percentile(v, 25), np.percentile(v, 75)
    IQR = Q3 - Q1
    return Q1 - factor*IQR, Q3 + factor*IQR

def main():
    print("="*65)
    print("  SCRIPT 05 - ANALISIS RECORTADO A LOCALIDAD HISTORICA")
    print("="*65)

    if not ESCENARIOS:
        print("Error: No hay rasters en RASTERS VELOCIDAD.")
        sys.exit(1)

    try:
        gdf = gpd.read_file(SHP_PATH)
        if gdf.crs is None: gdf = gdf.set_crs("EPSG:4326")
        print(f"Shapefile cargado: {len(gdf)} poligonos")
    except Exception as e:
        print(f"Error cargando shapefile: {e}")
        sys.exit(1)

    try:
        gnss_csv = os.path.join(PROD_DIR, "gnss_velocidades_resumen.csv")
        df_gnss = pd.read_csv(gnss_csv)
        gnss_media = df_gnss["Vel_Sentinel_mm_a"].dropna().mean()
    except:
        gnss_media = 0.0

    print(f"GNSS media de referencia: {gnss_media:.3f} mm/a\n")

    for esc in ESCENARIOS:
        print(f"  Procesando escenario: {esc.upper()}")
        vert_path = os.path.join(PROD_DIR, f"vertical_{esc}.tif")
        if not os.path.exists(vert_path):
            print(f"    Raster no encontrado: {vert_path}")
            continue

        with rasterio.open(vert_path) as src:
            gdf_repro = gdf.to_crs(src.crs)
            
            # Validacion topologica: ¿Se superponen?
            rb = src.bounds
            sb = gdf_repro.total_bounds
            se_cruzan = not (sb[2] < rb[0] or sb[0] > rb[2] or sb[3] < rb[1] or sb[1] > rb[3])
            
            if not se_cruzan:
                print(f"    ALERTA: El shapefile (Area de Estudio) NO coincide geograficamente con el raster {esc}. Se omitira el recorte.")
                continue

            shapes = [geom.__geo_interface__ for geom in gdf_repro.geometry]
            try:
                data_clip, transform_clip = rio_mask(src, shapes, crop=True, nodata=np.nan, filled=True, all_touched=False)
            except Exception as e:
                print(f"    Error al recortar: {e}")
                continue

            meta_clip = src.meta.copy()
            meta_clip.update({"height": data_clip.shape[1], "width": data_clip.shape[2], "transform": transform_clip, "nodata": -9999.0})

        data2d = data_clip[0]
        v_todos = data2d[~np.isnan(data2d)]
        
        if len(v_todos) == 0:
            print("    Ningun pixel dentro del poligono.")
            continue
            
        lower, upper = filtrar_IQR(v_todos, 1.5)
        v_filt = v_todos[(v_todos >= lower) & (v_todos <= upper)]
        
        print(f"    Pixeles historicos: {len(v_todos):,}")
        print(f"    Filtrados (IQR)   : {len(v_filt):,}  Media={np.mean(v_filt):.3f} mm/a")
        
        out_tif = os.path.join(PROD_DIR, f"vertical_historico_{esc}.tif")
        out_arr = data2d.astype(np.float32)
        out_arr[np.isnan(data2d)] = -9999.0
        with rasterio.open(out_tif, "w", **meta_clip) as dst:
            dst.write(out_arr, 1)

    print("="*65)
    print("  SCRIPT 05 COMPLETADO")
    print("="*65)

if __name__ == "__main__":
    main()
