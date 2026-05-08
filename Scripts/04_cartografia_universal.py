# -*- coding: utf-8 -*-
"""
SCRIPT 04 – CARTOGRAFIA UNIVERSAL InSAR
========================================
Genera mapas profesionales de velocidad de deformacion a partir de cualquier
GeoTIFF de velocidad vertical. NO requiere datos GNSS ni parametros
especificos de una ciudad. Funciona para cualquier zona del mundo.

Entradas:
  - GeoTIFF de velocidad vertical (mm/año) en la carpeta Productos/
    (generado por el Script 01)

Salidas:
  - Mapa de velocidad clasificado (7 categorías)
  - Histograma de distribución de velocidades
  - Mapa de zonas críticas (subsidencia severa resaltada)
  - Reporte estadístico completo (.txt y .csv)
"""

import sys, os, glob, datetime
import numpy as np
import rasterio
from rasterio.transform import array_bounds
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
from matplotlib.ticker import FuncFormatter
from matplotlib import patheffects
from mpl_toolkits.axes_grid1 import make_axes_locatable

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Datos_Profesor"))
PROD_DIR = os.path.join(BASE_DIR, "Productos")
os.makedirs(PROD_DIR, exist_ok=True)

# ── SISTEMA DE CLASIFICACION ─────────────────────────────────────────────────
CLASES = [
    {"nombre": "Subsidencia Critica",   "min": -9999, "max": -10.0, "color": "#0D47A1"},
    {"nombre": "Subsidencia Moderada",  "min": -10.0, "max":  -5.0, "color": "#1976D2"},
    {"nombre": "Subsidencia Leve",      "min":  -5.0, "max":  -2.0, "color": "#64B5F6"},
    {"nombre": "Estabilidad Relativa",  "min":  -2.0, "max":   2.0, "color": "#F5F5F5"},
    {"nombre": "Elevacion Leve",        "min":   2.0, "max":   5.0, "color": "#FFCDD2"},
    {"nombre": "Elevacion Moderada",    "min":   5.0, "max":  10.0, "color": "#E53935"},
    {"nombre": "Elevacion Critica",     "min":  10.0, "max":  9999, "color": "#B71C1C"},
]

# ── HELPERS ───────────────────────────────────────────────────────────────────

def cargar_raster(path):
    """Carga un GeoTIFF y devuelve datos, metadata y extent geografico."""
    with rasterio.open(path) as src:
        data = src.read(1).astype(np.float64)
        nodata = src.nodata
        meta = src.meta.copy()
        bounds = src.bounds
        if nodata is not None:
            data[data == nodata] = np.nan
        data[data == 0.0] = np.nan
    extent = [bounds.left, bounds.right, bounds.bottom, bounds.top]
    return data, meta, extent


def clasificar(data):
    """Clasifica cada pixel segun las categorias de deformacion."""
    clasi = np.full_like(data, np.nan)
    for i, c in enumerate(CLASES):
        mask = (data >= c["min"]) & (data < c["max"])
        clasi[mask] = i
    return clasi


def calcular_estadisticas(data, nombre_archivo):
    """Calcula estadisticas completas del raster."""
    v = data[~np.isnan(data)]
    if len(v) == 0:
        return None
    
    stats = {
        "Archivo": nombre_archivo,
        "N_pixeles_validos": len(v),
        "Media_mm_a": round(float(np.mean(v)), 3),
        "Mediana_mm_a": round(float(np.median(v)), 3),
        "Std_mm_a": round(float(np.std(v)), 3),
        "Min_mm_a": round(float(np.min(v)), 3),
        "Max_mm_a": round(float(np.max(v)), 3),
        "P5_mm_a": round(float(np.percentile(v, 5)), 3),
        "P95_mm_a": round(float(np.percentile(v, 95)), 3),
    }
    
    # Porcentajes por categoria
    total = len(v)
    stats["Pct_Subsidencia_Critica"] = round(float(np.sum(v < -10)) / total * 100, 2)
    stats["Pct_Subsidencia_Moderada"] = round(float(np.sum((v >= -10) & (v < -5))) / total * 100, 2)
    stats["Pct_Subsidencia_Leve"] = round(float(np.sum((v >= -5) & (v < -2))) / total * 100, 2)
    stats["Pct_Estable"] = round(float(np.sum((v >= -2) & (v < 2))) / total * 100, 2)
    stats["Pct_Elevacion_Leve"] = round(float(np.sum((v >= 2) & (v < 5))) / total * 100, 2)
    stats["Pct_Elevacion_Moderada"] = round(float(np.sum((v >= 5) & (v < 10))) / total * 100, 2)
    stats["Pct_Elevacion_Critica"] = round(float(np.sum(v >= 10)) / total * 100, 2)
    stats["Pct_Total_Subsidencia"] = round(stats["Pct_Subsidencia_Critica"] + 
                                           stats["Pct_Subsidencia_Moderada"] + 
                                           stats["Pct_Subsidencia_Leve"], 2)
    
    return stats


def agregar_escala(ax, extent, pos_y=0.05):
    """Agrega una barra de escala automatica basada en el extent."""
    lon_range = extent[1] - extent[0]
    # Calcular km aproximados (1 grado ≈ 111 km en el ecuador)
    lat_medio = (extent[2] + extent[3]) / 2
    km_por_grado = 111.32 * np.cos(np.deg2rad(lat_medio))
    total_km = lon_range * km_por_grado
    
    # Elegir escala bonita
    escalas = [0.5, 1, 2, 5, 10, 20, 50, 100]
    escala_km = 1
    for e in escalas:
        if e <= total_km * 0.25:
            escala_km = e
    
    escala_deg = escala_km / km_por_grado
    x0 = extent[0] + lon_range * 0.05
    y0 = extent[2] + (extent[3] - extent[2]) * pos_y
    
    ax.plot([x0, x0 + escala_deg], [y0, y0], color="white", lw=3,
            path_effects=[patheffects.withStroke(linewidth=5, foreground="black")])
    ax.text(x0 + escala_deg / 2, y0 + (extent[3] - extent[2]) * 0.015,
            f"{escala_km} km", ha="center", va="bottom", fontsize=8,
            color="white", fontweight="bold",
            path_effects=[patheffects.withStroke(linewidth=2, foreground="black")])


def agregar_norte(ax, extent):
    """Agrega flecha de norte."""
    x = extent[1] - (extent[1] - extent[0]) * 0.08
    y = extent[3] - (extent[3] - extent[2]) * 0.08
    ax.annotate("N", xy=(x, y), fontsize=14, fontweight="bold", color="white",
                ha="center", va="center",
                path_effects=[patheffects.withStroke(linewidth=2, foreground="black")])
    dy = (extent[3] - extent[2]) * 0.04
    ax.annotate("", xy=(x, y + dy), xytext=(x, y - dy * 0.3),
                arrowprops=dict(arrowstyle="->", color="white", lw=2))


# ── GENERADORES DE GRAFICOS ──────────────────────────────────────────────────

def generar_mapa_velocidad(data, extent, nombre, out_path):
    """Genera mapa de velocidad con clasificacion de 7 categorias."""
    fig, ax = plt.subplots(figsize=(14, 12))
    fig.patch.set_facecolor("#0D1117")
    ax.set_facecolor("#161B22")
    
    # Colormap personalizado
    colores = [c["color"] for c in CLASES]
    boundaries = [-30, -10, -5, -2, 2, 5, 10, 30]
    cmap = mcolors.ListedColormap(colores)
    norm = mcolors.BoundaryNorm(boundaries, cmap.N)
    
    v = data[~np.isnan(data)]
    vmin = max(np.percentile(v, 1), -30)
    vmax = min(np.percentile(v, 99), 30)
    
    im = ax.imshow(data, extent=extent, cmap=cmap, norm=norm,
                   interpolation="nearest", aspect="auto")
    
    # Colorbar
    divider = make_axes_locatable(ax)
    cax = divider.append_axes("right", size="3%", pad=0.15)
    cbar = plt.colorbar(im, cax=cax, boundaries=boundaries, ticks=boundaries)
    cbar.set_label("Velocidad Vertical (mm/año)", color="white", fontsize=11)
    cbar.ax.tick_params(colors="white", labelsize=9)
    
    # Leyenda de categorias
    patches = [mpatches.Patch(facecolor=c["color"], edgecolor="#555",
               label=f'{c["nombre"]} [{c["min"]:.0f}, {c["max"]:.0f})' if c["min"] > -9999 
               else f'{c["nombre"]} [< {c["max"]:.0f}]' if c["min"] == -9999
               else f'{c["nombre"]} [≥ {c["min"]:.0f}]')
               for c in CLASES]
    leg = ax.legend(handles=patches, loc="lower left", fontsize=7.5,
                    facecolor="#1C2128", edgecolor="#444", labelcolor="white",
                    title="Clasificacion", title_fontsize=8)
    leg.get_title().set_color("white")
    
    # Decoracion
    agregar_escala(ax, extent)
    agregar_norte(ax, extent)
    
    ax.set_xlabel("Longitud (°)", color="white", fontsize=11)
    ax.set_ylabel("Latitud (°)", color="white", fontsize=11)
    ax.set_title(f"Mapa de Velocidad de Deformacion Vertical\n{nombre}\n"
                 f"Media: {np.nanmean(data):.2f} mm/año | "
                 f"N pixeles: {np.sum(~np.isnan(data)):,}",
                 color="white", fontsize=13, fontweight="bold")
    ax.tick_params(colors="white")
    [s.set_color("#444") for s in ax.spines.values()]
    ax.grid(True, alpha=0.15, color="white", ls=":")
    
    # Coordenadas formateadas
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, p: f"{x:.2f}°"))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, p: f"{x:.2f}°"))
    
    # Timestamp
    ax.text(0.99, 0.01, f"Generado: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
            transform=ax.transAxes, fontsize=6, color="#666", ha="right", va="bottom")
    
    plt.tight_layout()
    plt.savefig(out_path, dpi=200, bbox_inches="tight", facecolor="#0D1117")
    plt.close()
    print(f"  Mapa guardado: {out_path}")


def generar_histograma(data, nombre, out_path):
    """Genera histograma de distribucion de velocidades."""
    v = data[~np.isnan(data)]
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7), gridspec_kw={"width_ratios": [2, 1]})
    fig.patch.set_facecolor("#0D1117")
    
    # Panel 1: Histograma
    ax1.set_facecolor("#161B22")
    p1, p99 = np.percentile(v, 1), np.percentile(v, 99)
    v_plot = v[(v >= p1) & (v <= p99)]
    
    n, bins, patches_hist = ax1.hist(v_plot, bins=80, edgecolor="#333", alpha=0.9)
    
    # Colorear barras segun categoria
    for patch, left_edge in zip(patches_hist, bins[:-1]):
        if left_edge < -10:
            patch.set_facecolor("#0D47A1")
        elif left_edge < -5:
            patch.set_facecolor("#1976D2")
        elif left_edge < -2:
            patch.set_facecolor("#64B5F6")
        elif left_edge < 2:
            patch.set_facecolor("#BDBDBD")
        elif left_edge < 5:
            patch.set_facecolor("#FFCDD2")
        elif left_edge < 10:
            patch.set_facecolor("#E53935")
        else:
            patch.set_facecolor("#B71C1C")
    
    ax1.axvline(x=np.mean(v), color="#FFD600", lw=2, ls="--",
                label=f"Media: {np.mean(v):.2f} mm/a")
    ax1.axvline(x=np.median(v), color="#00E676", lw=2, ls=":",
                label=f"Mediana: {np.median(v):.2f} mm/a")
    ax1.axvline(x=0, color="white", lw=1, alpha=0.5)
    
    ax1.set_xlabel("Velocidad Vertical (mm/año)", color="white", fontsize=11)
    ax1.set_ylabel("Numero de Pixeles", color="white", fontsize=11)
    ax1.set_title(f"Distribucion de Velocidades\n{nombre}", 
                  color="white", fontsize=12, fontweight="bold")
    ax1.tick_params(colors="white")
    [s.set_color("#444") for s in ax1.spines.values()]
    ax1.grid(True, alpha=0.15, color="white", axis="y")
    ax1.legend(facecolor="#1C2128", edgecolor="#444", labelcolor="white", fontsize=9)
    
    # Panel 2: Torta de categorias
    ax2.set_facecolor("#0D1117")
    total = len(v)
    sizes = []
    labels_pie = []
    colors_pie = []
    for c in CLASES:
        if c["min"] == -9999:
            count = np.sum(v < c["max"])
        elif c["max"] == 9999:
            count = np.sum(v >= c["min"])
        else:
            count = np.sum((v >= c["min"]) & (v < c["max"]))
        pct = count / total * 100
        if pct > 0.5:  # Solo mostrar categorias con >0.5%
            sizes.append(pct)
            labels_pie.append(f'{c["nombre"]}\n({pct:.1f}%)')
            colors_pie.append(c["color"])
    
    wedges, texts = ax2.pie(sizes, labels=None, colors=colors_pie,
                            startangle=90, wedgeprops={"edgecolor": "#333", "linewidth": 0.5})
    ax2.legend(wedges, labels_pie, loc="center left", bbox_to_anchor=(0.85, 0.5),
               fontsize=7, facecolor="#1C2128", edgecolor="#444", labelcolor="white")
    ax2.set_title("Distribucion por Categoria", color="white", fontsize=11, fontweight="bold")
    
    plt.suptitle(f"Analisis Estadistico de Deformacion | N = {total:,} pixeles",
                 color="white", fontsize=13, fontweight="bold")
    plt.tight_layout()
    plt.savefig(out_path, dpi=180, bbox_inches="tight", facecolor="#0D1117")
    plt.close()
    print(f"  Histograma guardado: {out_path}")


def generar_mapa_critico(data, extent, nombre, out_path):
    """Genera mapa resaltando unicamente las zonas de subsidencia critica."""
    fig, ax = plt.subplots(figsize=(14, 12))
    fig.patch.set_facecolor("#0D1117")
    ax.set_facecolor("#161B22")
    
    # Fondo: todos los pixeles validos en gris suave
    fondo = np.where(~np.isnan(data), 0.15, np.nan)
    ax.imshow(fondo, extent=extent, cmap="gray", vmin=0, vmax=1,
              interpolation="nearest", aspect="auto", alpha=0.5)
    
    # Resaltar zonas criticas con gradiente
    critico = data.copy()
    critico[data >= -5] = np.nan  # Solo mostrar subsidencia moderada y critica
    
    cmap_hot = plt.cm.YlOrRd_r
    im = ax.imshow(critico, extent=extent, cmap=cmap_hot, vmin=-25, vmax=-5,
                   interpolation="nearest", aspect="auto")
    
    divider = make_axes_locatable(ax)
    cax = divider.append_axes("right", size="3%", pad=0.15)
    cbar = plt.colorbar(im, cax=cax)
    cbar.set_label("Velocidad (mm/año) - Solo zonas criticas", color="white", fontsize=10)
    cbar.ax.tick_params(colors="white")
    
    # Estadisticas de zonas criticas
    v = data[~np.isnan(data)]
    n_critico = np.sum(v < -5)
    pct_critico = n_critico / len(v) * 100
    
    agregar_escala(ax, extent)
    agregar_norte(ax, extent)
    
    ax.set_xlabel("Longitud (°)", color="white", fontsize=11)
    ax.set_ylabel("Latitud (°)", color="white", fontsize=11)
    ax.set_title(f"Zonas de Subsidencia Significativa (< -5 mm/año)\n{nombre}\n"
                 f"Pixeles afectados: {n_critico:,} ({pct_critico:.1f}% del area)",
                 color="white", fontsize=13, fontweight="bold")
    ax.tick_params(colors="white")
    [s.set_color("#444") for s in ax.spines.values()]
    ax.grid(True, alpha=0.15, color="white", ls=":")
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, p: f"{x:.2f}°"))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, p: f"{x:.2f}°"))
    
    plt.tight_layout()
    plt.savefig(out_path, dpi=200, bbox_inches="tight", facecolor="#0D1117")
    plt.close()
    print(f"  Mapa critico guardado: {out_path}")


# ── PROGRAMA PRINCIPAL ────────────────────────────────────────────────────────

def main():
    print("=" * 65)
    print("  SCRIPT 04 – CARTOGRAFIA UNIVERSAL InSAR")
    print("  Generacion automatica de mapas de deformacion")
    print("=" * 65)
    print(f"  Fecha: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Directorio: {PROD_DIR}")
    print("-" * 65)
    
    # Buscar GeoTIFFs de velocidad vertical
    tif_files = sorted(glob.glob(os.path.join(PROD_DIR, "vertical_*.tif")))
    
    if not tif_files:
        # Intentar buscar cualquier velocity*.tif
        tif_files = sorted(glob.glob(os.path.join(PROD_DIR, "velocity*.tif")))
    
    if not tif_files:
        # Buscar en la carpeta raiz de rasters
        raster_dir = os.path.join(BASE_DIR, "RASTERS VELOCIDAD")
        if os.path.exists(raster_dir):
            tif_files = sorted(glob.glob(os.path.join(raster_dir, "*.tif")))
    
    if not tif_files:
        print("\nERROR: No se encontraron archivos GeoTIFF de velocidad.")
        print("Asegurese de haber ejecutado primero el Script 01 (conversion LOS->Vertical)")
        print("o coloque sus archivos .tif en la carpeta Productos/")
        return
    
    print(f"\nArchivos GeoTIFF encontrados: {len(tif_files)}")
    for f in tif_files:
        print(f"  - {os.path.basename(f)}")
    
    todas_stats = []
    
    for tif_path in tif_files:
        nombre = os.path.basename(tif_path).replace(".tif", "")
        print(f"\n{'='*50}")
        print(f"  Procesando: {nombre}")
        print(f"{'='*50}")
        
        data, meta, extent = cargar_raster(tif_path)
        v = data[~np.isnan(data)]
        
        if len(v) == 0:
            print("  Raster vacio. Saltando...")
            continue
        
        # Estadisticas
        stats = calcular_estadisticas(data, nombre)
        if stats:
            todas_stats.append(stats)
            print(f"  Pixeles validos : {stats['N_pixeles_validos']:,}")
            print(f"  Media           : {stats['Media_mm_a']:.3f} mm/a")
            print(f"  Mediana         : {stats['Mediana_mm_a']:.3f} mm/a")
            print(f"  Desv. Estandar  : {stats['Std_mm_a']:.3f} mm/a")
            print(f"  Rango           : [{stats['Min_mm_a']:.1f}, {stats['Max_mm_a']:.1f}] mm/a")
            print(f"  Subsidencia total: {stats['Pct_Total_Subsidencia']:.1f}% del area")
            print(f"  Estable          : {stats['Pct_Estable']:.1f}% del area")
        
        # Generar las 3 salidas graficas
        print(f"\n  Generando salidas graficas...")
        
        generar_mapa_velocidad(
            data, extent, nombre,
            os.path.join(PROD_DIR, f"MAPA_{nombre}.png")
        )
        
        generar_histograma(
            data, nombre,
            os.path.join(PROD_DIR, f"HISTOGRAMA_{nombre}.png")
        )
        
        generar_mapa_critico(
            data, extent, nombre,
            os.path.join(PROD_DIR, f"MAPA_CRITICO_{nombre}.png")
        )
    
    # Guardar CSV consolidado
    if todas_stats:
        csv_path = os.path.join(PROD_DIR, "estadisticas_universales.csv")
        pd.DataFrame(todas_stats).to_csv(csv_path, index=False)
        print(f"\n  CSV estadisticas: {csv_path}")
    
    # Generar reporte de texto
    report_path = os.path.join(PROD_DIR, "REPORTE_04_cartografia_universal.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("=" * 65 + "\n")
        f.write(f" REPORTE DE CARTOGRAFIA UNIVERSAL InSAR\n")
        f.write(f" Generado: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 65 + "\n\n")
        for s in todas_stats:
            f.write(f"Escenario: {s['Archivo']}\n")
            f.write(f"  Pixeles validos    : {s['N_pixeles_validos']:,}\n")
            f.write(f"  Media              : {s['Media_mm_a']:.3f} mm/a\n")
            f.write(f"  Mediana            : {s['Mediana_mm_a']:.3f} mm/a\n")
            f.write(f"  Desv. Estandar     : {s['Std_mm_a']:.3f} mm/a\n")
            f.write(f"  Percentil 5        : {s['P5_mm_a']:.3f} mm/a\n")
            f.write(f"  Percentil 95       : {s['P95_mm_a']:.3f} mm/a\n")
            f.write(f"  --- Distribucion por categoria ---\n")
            f.write(f"  Subsidencia Critica  : {s['Pct_Subsidencia_Critica']:.2f}%\n")
            f.write(f"  Subsidencia Moderada : {s['Pct_Subsidencia_Moderada']:.2f}%\n")
            f.write(f"  Subsidencia Leve     : {s['Pct_Subsidencia_Leve']:.2f}%\n")
            f.write(f"  Estable              : {s['Pct_Estable']:.2f}%\n")
            f.write(f"  Elevacion Leve       : {s['Pct_Elevacion_Leve']:.2f}%\n")
            f.write(f"  Elevacion Moderada   : {s['Pct_Elevacion_Moderada']:.2f}%\n")
            f.write(f"  Elevacion Critica    : {s['Pct_Elevacion_Critica']:.2f}%\n")
            f.write(f"  TOTAL SUBSIDENCIA    : {s['Pct_Total_Subsidencia']:.2f}%\n")
            f.write("\n")
    print(f"  Reporte: {report_path}")
    
    print("\n" + "=" * 65)
    print("  SCRIPT 04 COMPLETADO")
    print(f"  Archivos generados en: {PROD_DIR}")
    print("=" * 65)


if __name__ == "__main__":
    main()
