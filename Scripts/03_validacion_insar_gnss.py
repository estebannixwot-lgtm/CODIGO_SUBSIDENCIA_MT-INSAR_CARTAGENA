# -*- coding: utf-8 -*-
"""
SCRIPT 03 – VALIDACION InSAR vs GNSS (estadisticas filtradas IQR)
"""
import sys, os, glob, datetime
import numpy as np
import rasterio
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

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

sys.stdout = Logger(os.path.join(PROD_DIR, "REPORTE_03_validacion_insar_gnss.txt"))

raster_dir = os.path.join(BASE_DIR, "RASTERS VELOCIDAD")
if not os.path.exists(raster_dir): raster_dir = BASE_DIR
tif_files = glob.glob(os.path.join(raster_dir, "*.tif"))
ESCENARIOS = [os.path.basename(f).replace("velocity_", "").replace("_masked.tif", "").replace(".tif", "") for f in tif_files]

EXCLUIR = ["GT2", "ULR6B"]

PIXEL_REF = (1021, 923)
PIXEL_LON = -75.5339
PIXEL_LAT = 10.3915

def leer_pixel(rpath, row, col):
    with rasterio.open(rpath) as src:
        data = src.read(1).astype(float)
        nd = src.nodata
        if nd is not None:
            data[data == nd] = np.nan
        val = data[row, col]
        return float(val) if not (np.isnan(val) or np.isinf(val)) else None

def main():
    print("=" * 65)
    print("  SCRIPT 03 – VALIDACION InSAR vs GNSS (filtrado IQR)")
    print("=" * 65)

    if not ESCENARIOS:
        print("Error: No hay rasters en RASTERS VELOCIDAD.")
        sys.exit(1)

    gnss_csv = os.path.join(PROD_DIR, "gnss_velocidades_resumen.csv")
    if not os.path.exists(gnss_csv):
        print("Error: Ejecutar primero el Script 02.")
        sys.exit(1)

    df_gnss = pd.read_csv(gnss_csv)
    df_gnss = df_gnss[~df_gnss["Solucion"].isin(EXCLUIR)]
    df_val = df_gnss.dropna(subset=["Vel_Sentinel_mm_a"])

    vels_gnss = df_val["Vel_Sentinel_mm_a"]
    gnss_media = vels_gnss.mean()
    gnss_std = vels_gnss.std()
    gnss_mediana = vels_gnss.median()

    print(f"\n-- Velocidades GNSS validas ({len(vels_gnss)} soluciones) --")
    print(f"   Media  : {gnss_media:.3f} mm/a")
    print(f"   Mediana: {gnss_mediana:.3f} mm/a")
    print(f"   Std    : {gnss_std:.3f} mm/a")
    print(f"   Rango  : {vels_gnss.min():.3f} a {vels_gnss.max():.3f} mm/a")

    est_csv = os.path.join(PROD_DIR, "estadisticas_conversion.csv")
    df_est = pd.read_csv(est_csv) if os.path.exists(est_csv) else pd.DataFrame()

    print(f"\n-- Extrayendo InSAR en pixel [{PIXEL_REF}] (26m de Lat={PIXEL_LAT}, Lon={PIXEL_LON}) --")
    insar_pixel = {}
    for esc in ESCENARIOS:
        rp = os.path.join(PROD_DIR, f"vertical_{esc}.tif")
        if not os.path.exists(rp): continue
        val = leer_pixel(rp, PIXEL_REF[0], PIXEL_REF[1])
        insar_pixel[esc] = val
        print(f"   {esc.upper():10s}: {val:.3f} mm/a" if val else f"   {esc.upper()}: NoData")

    print("\n-- Metricas de error (InSAR pixel vs GNSS soluciones) --")
    metricas = []
    for esc in ESCENARIOS:
        val = insar_pixel.get(esc)
        if val is None: continue
        diffs = [val - v for v in vels_gnss]
        me = np.mean(diffs)
        mae = np.mean(np.abs(diffs))
        rmse = np.sqrt(np.mean(np.array(diffs) ** 2))
        sd = np.std(diffs)
        print(f"   {esc.upper():10s}: ME={me:+.3f}  MAE={mae:.3f}  RMSE={rmse:.3f}  s={sd:.3f} mm/a")

        media_f = np.nan
        if not df_est.empty and "Escenario" in df_est.columns:
            row_est = df_est[df_est["Escenario"].str.upper() == esc.upper()]
            if len(row_est) > 0 and "Media_Filtrada" in row_est.columns:
                media_f = float(row_est["Media_Filtrada"].iloc[0])

        metricas.append({
            "Escenario": esc, "InSAR_pixel_mm_a": round(val, 3), "InSAR_media_filtrada_mm_a": round(media_f, 3),
            "GNSS_media_mm_a": round(gnss_media, 3), "ME_mm_a": round(me, 4), "MAE_mm_a": round(mae, 4),
            "RMSE_mm_a": round(rmse, 4), "Sigma_mm_a": round(sd, 4)
        })

    if metricas:
        df_met = pd.DataFrame(metricas)
        mejor = df_met.loc[df_met["RMSE_mm_a"].idxmin(), "Escenario"]
        print(f"\n   MEJOR ESCENARIO (menor RMSE): {mejor.upper()}")
        df_met.to_csv(os.path.join(PROD_DIR, "metricas_error.csv"), index=False)

    print("\n" + "=" * 65)
    print("  SCRIPT 03 COMPLETADO")
    print("=" * 65)

if __name__ == "__main__":
    main()
