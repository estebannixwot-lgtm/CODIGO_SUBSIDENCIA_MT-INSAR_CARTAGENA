# -*- coding: utf-8 -*-
"""
SCRIPT 09 - SALIDAS GRAFICAS HIBRIDAS (ALTA RESOLUCION + WMS)
"""
import os, sys, glob, datetime, math
if 'PROJ_LIB' in os.environ:
    del os.environ['PROJ_LIB']

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.dates as mdates
import matplotlib.gridspec as gridspec
from matplotlib.colors import LinearSegmentedColormap, Normalize
from datetime import datetime as dt
from PIL import Image
import rasterio
import contextily as ctx
import geopandas as gpd
import numpy as np

# Configurar PROJ
os.environ['PROJ_LIB'] = os.path.join(os.path.dirname(rasterio.__file__), 'proj_data')

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Datos_Profesor"))
PROD_DIR = os.path.join(BASE_DIR, "Productos")
LAYOUT_DIR = os.path.join(PROD_DIR, "LAYOUTS_TESIS_OFICIAL")
os.makedirs(LAYOUT_DIR, exist_ok=True)

class Logger(object):
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.log = open(filename, "a", encoding="utf-8")
        self.log.write("\n======================================================\n")
        self.log.write(f" EFEMÉRIDES DE EJECUCIÓN - {dt.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        self.log.write("======================================================\n")
    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
    def flush(self):
        self.terminal.flush()
        self.log.flush()

sys.stdout = Logger(os.path.join(PROD_DIR, "REPORTE_09_layouts.txt"))

COLORS_RWB = [(0.0, "#08306b"), (0.2, "#2171b5"), (0.4, "#9ecae1"),
              (0.5, "#ffffff"),
              (0.6, "#fee0d2"), (0.8, "#ef3b2c"), (1.0, "#67000d")]
CMAP_TESIS = LinearSegmentedColormap.from_list("RdBu_Tesis", COLORS_RWB)

CLASES = [
    {"n": "Subsidencia Critica (<-10)", "c": "#08306b"},
    {"n": "Subsidencia Moderada (-10 a -5)", "c": "#2171b5"},
    {"n": "Subsidencia Leve (-5 a -2)", "c": "#9ecae1"},
    {"n": "Estabilidad (-2 a +2)", "c": "#f7f7f7"},
    {"n": "Elevacion Leve (+2 a +5)", "c": "#fee0d2"},
    {"n": "Elevacion Moderada (+5 a +10)", "c": "#ef3b2c"},
    {"n": "Elevacion Critica (>+10)", "c": "#67000d"},
]

def cargar_raster(path):
    with rasterio.open(path) as src:
        d = src.read(1).astype(np.float64)
        tf = src.transform
        d[d == src.nodata] = np.nan
        ext = [tf.c, tf.c + src.width * tf.a, tf.f + src.height * tf.e, tf.f]
    return d, ext

def leer_serie(path):
    fechas, valores, meta = [], [], {}
    with open(path, "r") as f:
        for line in f:
            if line.startswith("#"):
                if "lat/lon =" in line:
                    c = line.split("lat/lon =")[1].strip().split(",")
                    meta['lat'], meta['lon'] = float(c[0]), float(c[1])
            else:
                p = line.strip().split("\t")
                if len(p) == 2:
                    fechas.append(dt.strptime(p[0], "%Y%m%d"))
                    valores.append(float(p[1]) * 10)
    return fechas, valores, meta

def generar_layout(esc, nombre_punto, txt_path, v_data, v_ext, idx=1001, sin_serie=False, gdf_valido=None):
    if not sin_serie:
        fechas, valores, meta = leer_serie(txt_path)
        if not fechas or 'lat' not in meta: return
        dias = [(f - fechas[0]).days for f in fechas]
        z = np.polyfit(dias, valores, 1)
        p = np.poly1d(z)
        vel_anual = z[0] * 365.25
        rmse = np.sqrt(np.mean((valores - p(dias))**2))
        lon_c, lat_c = meta['lon'], meta['lat']
    else:
        lon_c = v_ext[0] + (v_ext[1] - v_ext[0]) / 2.0
        lat_c = v_ext[3] + (v_ext[2] - v_ext[3]) / 2.0
        vel_anual = rmse = 0.0
        valores = [0]

    fig = plt.figure(figsize=(18, 11), facecolor='white')
    if not sin_serie:
        gs = gridspec.GridSpec(2, 2, width_ratios=[2.8, 1], height_ratios=[1.4, 1], wspace=0.05, hspace=0.25)
        ax_map = fig.add_subplot(gs[0, 0])
        ax_box = fig.add_subplot(gs[:, 1])
        ax_ts = fig.add_subplot(gs[1, 0])
    else:
        gs = gridspec.GridSpec(1, 2, width_ratios=[2.8, 1], wspace=0.05)
        ax_map = fig.add_subplot(gs[0, 0])
        ax_box = fig.add_subplot(gs[0, 1])

    zoom = 0.005 if not sin_serie else max((v_ext[1]-v_ext[0])/2, (v_ext[2]-v_ext[3])/2) * 1.1
    lon_min, lon_max = lon_c - zoom, lon_c + zoom
    lat_min, lat_max = lat_c - zoom, lat_c + zoom

    ax_map.set_xlim(lon_min, lon_max)
    ax_map.set_ylim(lat_min, lat_max)
    ax_map.set_aspect('equal', adjustable='datalim')

    # Base Ortografica Perfectamente Alineada
    try:
        ctx.add_basemap(ax_map, crs="EPSG:4326", source=ctx.providers.Esri.WorldImagery, zorder=1)
        ax_map.text(0.01, 0.01, "Ortofoto (c) Esri", transform=ax_map.transAxes, fontsize=8, color='white',
                    bbox=dict(boxstyle='square,pad=0.3', fc='black', alpha=0.6, ec='none'))
    except Exception as e:
        print(f"    Aviso: No se pudo cargar el mapa base WMS: {e}")

    # Dibujar Shapefile encima de la ortofoto
    if gdf_valido is not None:
        gdf_valido.plot(ax=ax_map, facecolor='none', edgecolor='#FFD600', linewidth=2.5, zorder=2)

    # Plot Raster
    v_plot = v_data.copy()
    v_plot[(v_plot >= -2) & (v_plot <= 2)] = np.nan # Transparente en zonas estables
    norm = Normalize(vmin=-15, vmax=15)
    im = ax_map.imshow(v_plot, extent=v_ext, cmap=CMAP_TESIS, norm=norm, alpha=0.85, zorder=3)

    if not sin_serie:
        ax_map.plot(lon_c, lat_c, 'o', mfc='#39FF14', mec='k', ms=12, mew=2, zorder=5)
        ax_map.annotate(f"PS {idx}", xy=(lon_c, lat_c), xytext=(8, 8), 
                        textcoords='offset points', fontsize=11, fontweight='bold', color='black',
                        bbox=dict(boxstyle='round,pad=0.3', fc='white', alpha=0.9, ec='black'), zorder=6)

    ax_map.set_title(f"Mapa de Velocidad Vertical InSAR - Archivo: {esc.upper()}", fontsize=15, fontweight='bold', pad=15)
    cbar = plt.colorbar(im, ax=ax_map, fraction=0.03, pad=0.02)
    cbar.set_label("Velocidad Vertical (mm/año)", fontsize=12, fontweight='bold')
    
    ax_map.tick_params(axis='both', which='major', labelsize=11, direction='out', length=6, width=1.5)
    for spine in ax_map.spines.values():
        spine.set_linewidth(1.5)

    # ── PANEL B: CAJETIN ──
    ax_box.axis('off')
    ax_box.add_patch(mpatches.Rectangle((0, 0), 1, 1, fill=False, ec='black', lw=2, transform=ax_box.transAxes))
    
    ax_box.text(0.5, 0.94, "Cartografía InSAR", ha='center', va='top', fontsize=16, fontweight='bold', transform=ax_box.transAxes)
    ax_box.plot([0.1, 0.9], [0.89, 0.89], color='black', lw=2, transform=ax_box.transAxes)
    ax_box.text(0.5, 0.84, "Análisis de Subsidencia", ha='center', va='top', fontsize=14, fontweight='bold', transform=ax_box.transAxes)
    
    ax_box.text(0.08, 0.77, "Leyenda", fontweight='bold', fontsize=15, ha='left', va='top', transform=ax_box.transAxes)
    
    y_start = 0.72
    if gdf_valido is not None:
        ax_box.plot([0.08, 0.15], [y_start, y_start], color='#FFD600', lw=3, transform=ax_box.transAxes)
        ax_box.text(0.18, y_start, "Polígono Área de Estudio", fontsize=12, va='center', transform=ax_box.transAxes)
        y_start -= 0.05

    if not sin_serie:
        ax_box.plot(0.12, y_start, 'o', mfc='#39FF14', mec='k', ms=12, transform=ax_box.transAxes)
        ax_box.text(0.18, y_start, "PS Seleccionado", fontsize=12, va='center', transform=ax_box.transAxes)
        y_start -= 0.05

    # UNA SOLA COLUMNA CON AMPLIO ESPACIADO
    y_start -= 0.01
    for i, cl in enumerate(CLASES):
        y_p = y_start - (i * 0.055)
        ax_box.plot(0.12, y_p, 's', mfc=cl['c'], mec='k', ms=12, transform=ax_box.transAxes)
        ax_box.text(0.18, y_p, cl['n'], fontsize=11, va='center', transform=ax_box.transAxes)

    if not sin_serie:
        ax_box.plot([0.1, 0.9], [0.25, 0.25], color='gray', lw=1.5, transform=ax_box.transAxes)
        stats_txt = f"Velocidad PS: {vel_anual:+.2f} mm/a\nDespl. Máx: {max(valores):.1f} mm\nRMSE: {rmse:.2f} mm"
        ax_box.text(0.10, 0.23, stats_txt, va='top', fontsize=12, family='monospace', linespacing=1.8, transform=ax_box.transAxes)

    sys_txt = "Coordinate System: WGS 84 (EPSG:4326)\nDatum: WGS 84\nUnidades: Milímetros/año"
    ax_box.text(0.5, 0.02, sys_txt, ha='center', va='bottom', fontsize=10, linespacing=1.5, transform=ax_box.transAxes)

    # ── PANEL C: SERIE DE TIEMPO ──
    if not sin_serie:
        ax_ts.set_title(f"Serie Temporal PS: {idx} | {nombre_punto}", fontsize=13, fontweight='bold')
        ax_ts.plot(fechas, valores, '-s', color='gray', mfc='black', mec='black', ms=5, lw=1.2, zorder=3, alpha=0.8)
        ax_ts.plot(fechas, p(dias), '-', color='#e74c3c', lw=3, zorder=2, label=f"Tendencia: {vel_anual:+.2f} mm/a")
        ax_ts.set_ylabel("Desplazamiento [mm]", fontsize=11, fontweight='bold')
        ax_ts.set_xlabel("Fecha", fontsize=11, fontweight='bold')
        ax_ts.grid(True, linestyle='--', color='lightgray', lw=1)
        ax_ts.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        plt.setp(ax_ts.get_xticklabels(), rotation=30, ha='right', fontsize=10)
        ax_ts.legend(loc='upper left', fontsize=11)
        for sp in ax_ts.spines.values(): sp.set_linewidth(1.5)

    out_name = f"LAYOUT_{esc.upper()}_{nombre_punto.replace(' ', '_')}.png" if not sin_serie else f"LAYOUT_GENERAL_{esc.upper()}.png"
    plt.savefig(os.path.join(LAYOUT_DIR, out_name), dpi=200, bbox_inches='tight')
    plt.close()
    print(f"    Guardado: {out_name}")

def main():
    print("=" * 65)
    print("  SCRIPT 09 - CARTOGRAFÍA HÍBRIDA UNIVERSAL (WMS + InSAR)")
    print("=" * 65)

    raster_dir = os.path.join(BASE_DIR, "RASTERS VELOCIDAD")
    if not os.path.exists(raster_dir): raster_dir = BASE_DIR
    tif_files = glob.glob(os.path.join(raster_dir, "*.tif"))
    if not tif_files:
        print("Error: No se encontraron archivos .tif")
        sys.exit(1)

    try:
        lia, _ = cargar_raster(os.path.join(BASE_DIR, "RASTER INCIDENCIA", "local_incidente_angle.tif"))
        cos_lia = np.cos(np.deg2rad(lia))
    except:
        cos_lia = 1.0

    # Cargar Shapefile
    gdf_shp = None
    shp_files = glob.glob(os.path.join(BASE_DIR, "SHAPE AREA DE ESTUDIO", "*.shp"))
    shp_path = shp_files[0] if shp_files else os.path.join(BASE_DIR, "Division_Politica_Localidades.shp")
    if os.path.exists(shp_path):
        try:
            gdf_shp = gpd.read_file(shp_path)
            if gdf_shp.crs is None: gdf_shp = gdf_shp.set_crs("EPSG:4326")
            gdf_shp = gdf_shp.to_crs("EPSG:4326")
            print("  Shapefile cargado exitosamente para superposición.")
        except Exception as e:
            print(f"  Aviso: Error cargando shapefile ({e})")

    for v_path in tif_files:
        esc = os.path.basename(v_path).replace("velocity_", "").replace("_masked.tif", "").replace(".tif", "")
        print(f"\n  Procesando escenario: {esc.upper()}")
        v_data, v_ext = cargar_raster(v_path)
        v_vert = (v_data / cos_lia) * 1000.0

        gdf_valido = None
        if gdf_shp is not None:
            with rasterio.open(v_path) as src:
                gdf_repro = gdf_shp.to_crs(src.crs)
                rb = src.bounds
                sb = gdf_repro.total_bounds
                se_cruzan = not (sb[2] < rb[0] or sb[0] > rb[2] or sb[3] < rb[1] or sb[1] > rb[3])
                if se_cruzan:
                    gdf_valido = gdf_shp.to_crs("EPSG:4326")
                else:
                    print(f"    ALERTA: El shapefile no coincide geograficamente con {esc}.")

        txts = glob.glob(os.path.join(BASE_DIR, f"desplazamiento_{esc}", "TS_*_ts.txt"))
        if txts:
            print(f"    Generando layouts temporales ({len(txts)} puntos)...")
            idx = 1001
            for t in txts:
                p_nombre = os.path.basename(t).replace("TS_", "").replace("_ts.txt", "")[3:]
                generar_layout(esc, p_nombre, t, v_vert, v_ext, idx, sin_serie=False, gdf_valido=gdf_valido)
                idx += 1
        else:
            print("    Sin series de tiempo. Generando mapa general...")
            generar_layout(esc, "GENERAL", "", v_vert, v_ext, sin_serie=True, gdf_valido=gdf_valido)

    print("\n" + "=" * 65)
    print("  SCRIPT 09 COMPLETADO")
    print("=" * 65)

if __name__ == "__main__":
    main()
