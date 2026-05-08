# -*- coding: utf-8 -*-
"""
SCRIPT 02 – ANALISIS GNSS (sin GT2 – excluido por outlier)
===========================================================
Tesis: Subsidencia en Cartagena de Indias - InSAR Sentinel-1

ACTUALIZACION:
  - GT2 ELIMINADO DEFINITIVAMENTE: sus datos terminan en 2015 y su velocidad
    (+8.93 mm/a, R2=0.036) esta muy por fuera de la tendencia del conjunto.
  - ULR6B excluido del analisis Sentinel-1 (datos terminan en 2014).
  - Analisis estadistico con 6 soluciones validas: GT3, JPL14, NGL08, NGL14, NGL20, ULR20
  - Se incluye nota sobre el sesgo del punto de referencia MintPy.
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats
import pandas as pd
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Datos_Profesor"))
GNSS_DIR = os.path.join(BASE_DIR, "GNSS")
PROD_DIR = os.path.join(BASE_DIR, "Productos")
os.makedirs(PROD_DIR, exist_ok=True)
os.makedirs(PROD_DIR, exist_ok=True)

# GT2 EXCLUIDO definitivamente por ser outlier (+8.93 mm/a, R2=0.036, datos hasta 2015)
# ULR6B excluido por no tener datos en periodo Sentinel-1
EXCLUIR = ["GT2", "ULR6B"]

OFFSETS = [2010.68767, 2012.94809, 2016.28962, 2020.07377, 2023.39452]
OFFSET_LABELS = ["Cambio\ncutoff\n2010", "Cambio\nantena\n2012",
                 "Mw7.8\nEcuador\n2016", "Mw7.7\n2020", "Mw6.5\n2023"]

COLORES = ["#E91E63", "#4CAF50", "#FF9800", "#9C27B0", "#00BCD4", "#F44336"]

# ── HELPERS ───────────────────────────────────────────────────────────────────

def leer_neu(filepath):
    nombre = os.path.basename(filepath).replace("dCART00COL_41902M001_", "").replace(".neu", "")
    datos  = []
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                v = line.split()
                if len(v) >= 7:
                    datos.append({"year": float(v[0]), "du": float(v[3]), "sdu": float(v[6])})
            except:
                continue
    df = pd.DataFrame(datos)
    df["solucion"] = nombre
    df["du_mm"]    = df["du"] * 1000.0
    df["sdu_mm"]   = df["sdu"] * 1000.0
    return df


def corregir_offsets(df, offsets):
    df    = df.copy().sort_values("year").reset_index(drop=True)
    du_c  = df["du_mm"].values.copy()
    t_min = df["year"].min()
    t_max = df["year"].max()
    W     = 60 / 365.25   # ventana de 60 dias

    for ofs in sorted([o for o in offsets if t_min < o < t_max]):
        m1 = (df["year"] >= ofs - W) & (df["year"] < ofs)
        m2 = (df["year"] >= ofs) & (df["year"] < ofs + W)
        if m1.sum() < 3 or m2.sum() < 3:
            continue
        salto = np.median(du_c[m2]) - np.median(du_c[m1])
        du_c[df["year"] >= ofs] -= salto

    df["du_mm_corr"] = du_c
    return df


def vel_segmento(df, t0, t1):
    mask = (df["year"] >= t0) & (df["year"] <= t1)
    seg  = df[mask].dropna(subset=["du_mm_corr"])
    if len(seg) < 10:
        return np.nan, np.nan, np.nan
    s, ic, r, p, se = stats.linregress(seg["year"], seg["du_mm_corr"])
    return s, r**2, se


# ── PROGRAMA PRINCIPAL ────────────────────────────────────────────────────────

def main():
    print("=" * 65)
    print("  SCRIPT 02 – ANALISIS GNSS (GT2 EXCLUIDO)")
    print("=" * 65)

    archivos = sorted([os.path.join(GNSS_DIR, f)
                       for f in os.listdir(GNSS_DIR) if f.endswith(".neu")])
    print(f"\nArchivos .neu encontrados: {len(archivos)}")
    print(f"Excluidos del analisis  : {EXCLUIR}")

    resultados = []
    todos_df   = []

    for fp in archivos:
        df  = leer_neu(fp)
        sol = df["solucion"].iloc[0]

        # Excluir GT2 completamente
        if sol in EXCLUIR:
            print(f"\n  EXCLUIDO: {sol} ({' / '.join(EXCLUIR)})")
            continue

        df_c = corregir_offsets(df, OFFSETS)
        t0, t1 = df_c["year"].min(), df_c["year"].max()
        vel_s, r2_s, se_s = vel_segmento(df_c, 2014.5, 2024.0)
        vel_t, r2_t, se_t = vel_segmento(df_c, t0, t1)

        print(f"\n  Solucion: {sol}")
        print(f"    Periodo: {t0:.1f}-{t1:.1f}  N={len(df_c)} obs.")
        print(f"    Vel. Sentinel-1: {vel_s:.3f} +/- {se_s:.3f} mm/a  R2={r2_s:.3f}")
        print(f"    Vel. total     : {vel_t:.3f} +/- {se_t:.3f} mm/a")

        resultados.append({
            "Solucion"        : sol,
            "N_obs"           : len(df_c),
            "T_inicio"        : round(t0, 2),
            "T_fin"           : round(t1, 2),
            "Vel_total_mm_a"  : round(float(vel_t), 4) if not np.isnan(vel_t) else None,
            "SE_total"        : round(float(se_t),  4) if not np.isnan(se_t)  else None,
            "Vel_Sentinel_mm_a": round(float(vel_s), 4) if not np.isnan(vel_s) else None,
            "SE_Sentinel"     : round(float(se_s),  4) if not np.isnan(se_s)  else None,
            "R2_Sentinel"     : round(float(r2_s),  4) if not np.isnan(r2_s)  else None,
        })
        todos_df.append(df_c)

    # Resumen estadistico de soluciones validas
    df_vel = pd.DataFrame(resultados)
    vels   = df_vel["Vel_Sentinel_mm_a"].dropna()
    print(f"\n== RESUMEN (soluciones validas: {len(vels)}) ==")
    print(f"   Media  : {vels.mean():.3f} mm/a")
    print(f"   Mediana: {vels.median():.3f} mm/a")
    print(f"   Std    : {vels.std():.3f} mm/a")
    print(f"   Rango  : {vels.min():.3f} a {vels.max():.3f} mm/a")

    # Guardar CSV
    df_vel.to_csv(os.path.join(PROD_DIR, "gnss_velocidades_resumen.csv"), index=False)

    # ── GRAFICA 1: Todas las soluciones validas ──
    print("\nGenerando grafica 1 (serie temporal todas soluciones)...")
    fig, ax = plt.subplots(figsize=(16, 8))
    fig.patch.set_facecolor("#0D1117"); ax.set_facecolor("#0D1117")

    for i, (df_c, fp) in enumerate(zip(todos_df, [f for f in archivos
                            if not any(e in f for e in EXCLUIR)])):
        sol   = df_c["solucion"].iloc[0]
        color = COLORES[i % len(COLORES)]
        ax.plot(df_c["year"], df_c["du_mm_corr"], lw=0.4, alpha=0.4, color=color)
        ax.scatter(df_c["year"], df_c["du_mm_corr"], s=0.8, alpha=0.3, color=color)

        mask_s = (df_c["year"] >= 2014.5) & (df_c["year"] <= 2024.0)
        seg    = df_c[mask_s].dropna(subset=["du_mm_corr"])
        if len(seg) >= 10:
            s, ic, *_ = stats.linregress(seg["year"], seg["du_mm_corr"])
            x2 = np.array([2014.5, 2024.0])
            ax.plot(x2, s * x2 + ic, color=color, lw=2.5, ls="--",
                    label=f"{sol}: {s:.2f} mm/a")

    for ofs, lbl in zip(OFFSETS, OFFSET_LABELS):
        ax.axvline(x=ofs, color="#FF6B6B", lw=1.2, ls=":", alpha=0.8)

    ax.axvspan(2014.5, 2024.0, alpha=0.07, color="#4CAF50", label="Periodo Sentinel-1")
    ax.set_xlabel("Anio", color="white", fontsize=12)
    ax.set_ylabel("DU vertical (mm)", color="white", fontsize=12)
    ax.set_title(
        "Serie Temporal GNSS – Estacion CART00COL Cartagena\n"
        "Componente Vertical DU – 6 soluciones validas (GT2 y ULR6B excluidos)",
        color="white", fontsize=13, fontweight="bold"
    )
    ax.tick_params(colors="white")
    [s.set_color("#444") for s in ax.spines.values()]
    ax.grid(True, alpha=0.15, color="white")
    ax.legend(loc="upper right", fontsize=8, facecolor="#1C2128",
              edgecolor="#444", labelcolor="white")
    plt.tight_layout()
    out1 = os.path.join(PROD_DIR, "gnss_serie_temporal_todas_soluciones.png")
    plt.savefig(out1, dpi=180, bbox_inches="tight", facecolor="#0D1117")
    plt.close()
    print(f"  Guardado: {out1}")

    # ── GRAFICA 2: NGL20 detallada ──
    print("Generando grafica 2 (NGL20 detallada)...")
    df_ngl = next((d for d in todos_df if "NGL20" in d["solucion"].iloc[0]), todos_df[0])

    fig2, axes = plt.subplots(2, 1, figsize=(16, 12))
    fig2.patch.set_facecolor("#0D1117")

    ax1 = axes[0]; ax1.set_facecolor("#161B22")
    ax1.errorbar(df_ngl["year"], df_ngl["du_mm_corr"], yerr=df_ngl["sdu_mm"],
                 fmt="o", ms=1.2, lw=0.4, color="#4FC3F7",
                 ecolor="#1976D2", alpha=0.5, label="DU corr. +/- SDU")
    sa, ia, *_ = stats.linregress(df_ngl["year"], df_ngl["du_mm_corr"])
    xa = np.array([df_ngl["year"].min(), df_ngl["year"].max()])
    ax1.plot(xa, sa * xa + ia, color="#FFD600", lw=2.5,
             label=f"Tendencia global: {sa:.3f} mm/a")
    for ofs in OFFSETS:
        ax1.axvline(x=ofs, color="#FF6B6B", lw=1.2, alpha=0.9)
    ax1.set_ylabel("DU (mm)", color="white")
    ax1.set_title("NGL20 – Serie completa (offsets corregidos)", color="white", fontweight="bold")
    ax1.tick_params(colors="white"); [s.set_color("#444") for s in ax1.spines.values()]
    ax1.grid(True, alpha=0.15, color="white")
    ax1.legend(facecolor="#1C2128", edgecolor="#444", labelcolor="white", fontsize=9)

    ax2 = axes[1]; ax2.set_facecolor("#161B22")
    mask_s1 = (df_ngl["year"] >= 2014.5) & (df_ngl["year"] <= 2024.0)
    df_s1   = df_ngl[mask_s1].dropna(subset=["du_mm_corr"])
    ax2.errorbar(df_s1["year"], df_s1["du_mm_corr"], yerr=df_s1["sdu_mm"],
                 fmt="o", ms=2, lw=0.8, color="#81C784",
                 ecolor="#388E3C", alpha=0.7, label="DU +/- SDU")
    if len(df_s1) >= 10:
        ss, ics, rs, *_ = stats.linregress(df_s1["year"], df_s1["du_mm_corr"])
        xs = np.linspace(df_s1["year"].min(), df_s1["year"].max(), 100)
        ax2.plot(xs, ss * xs + ics, color="#FFD600", lw=2.5,
                 label=f"Tendencia Sentinel-1: {ss:.3f} mm/a  (R2={rs**2:.3f})")
        res = df_s1["du_mm_corr"] - (ss * df_s1["year"] + ics)
        sig = np.std(res)
        ax2.fill_between(xs, ss * xs + ics - sig, ss * xs + ics + sig,
                         alpha=0.15, color="#FFD600",
                         label=f"Banda +/-1sigma ({sig:.2f} mm)")
    ax2.set_xlabel("Anio", color="white")
    ax2.set_ylabel("DU (mm)", color="white")
    ax2.set_title("Periodo Sentinel-1 (2014.5-2024.0) – Velocidad de referencia GNSS",
                  color="white", fontweight="bold")
    ax2.tick_params(colors="white"); [s.set_color("#444") for s in ax2.spines.values()]
    ax2.grid(True, alpha=0.15, color="white")
    ax2.legend(facecolor="#1C2128", edgecolor="#444", labelcolor="white", fontsize=9)

    plt.suptitle("Analisis GNSS – Estacion CART00COL – Cartagena de Indias\n"
                 "(Lat: 10.3913, Lon: -75.5339 | Datum ITRF20)",
                 color="white", fontsize=13, fontweight="bold")
    plt.tight_layout()
    out2 = os.path.join(PROD_DIR, "gnss_serie_NGL20_detallada.png")
    plt.savefig(out2, dpi=180, bbox_inches="tight", facecolor="#0D1117")
    plt.close()
    print(f"  Guardado: {out2}")

    # ── GRAFICA 3: Comparacion barras ──
    print("Generando grafica 3 (comparacion velocidades)...")
    df_vc = df_vel.dropna(subset=["Vel_Sentinel_mm_a"])
    fig3, ax3 = plt.subplots(figsize=(12, 6))
    fig3.patch.set_facecolor("#0D1117"); ax3.set_facecolor("#161B22")
    sols  = df_vc["Solucion"].tolist()
    vels3 = df_vc["Vel_Sentinel_mm_a"].tolist()
    errs3 = df_vc["SE_Sentinel"].tolist()
    bars  = ax3.bar(sols, vels3, color=COLORES[:len(sols)], edgecolor="#333", alpha=0.85)
    ax3.errorbar(sols, vels3, yerr=errs3, fmt="none", color="white", capsize=5, lw=1.5)
    for bar, v, e in zip(bars, vels3, errs3):
        ax3.text(bar.get_x() + bar.get_width() / 2.,
                 bar.get_height() + abs(e) + 0.05,
                 f"{v:.2f}", ha="center", va="bottom",
                 color="white", fontsize=9, fontweight="bold")
    med_v = np.nanmean(vels3)
    ax3.axhline(y=med_v, color="#FFD600", lw=2, ls="--",
                label=f"Media 6 soluciones: {med_v:.2f} mm/a")
    ax3.axhline(y=0, color="white", lw=0.8, alpha=0.4)
    ax3.set_xlabel("Solucion", color="white")
    ax3.set_ylabel("Velocidad Vertical GNSS (mm/a)", color="white")
    ax3.set_title("Velocidad Vertical GNSS periodo Sentinel-1 (2014-2024)\n"
                  "6 soluciones validas – GT2 y ULR6B excluidos",
                  color="white", fontweight="bold")
    ax3.tick_params(colors="white"); [s.set_color("#444") for s in ax3.spines.values()]
    ax3.grid(True, alpha=0.15, color="white", axis="y")
    ax3.legend(facecolor="#1C2128", edgecolor="#444", labelcolor="white")
    plt.tight_layout()
    out3 = os.path.join(PROD_DIR, "gnss_comparacion_velocidades.png")
    plt.savefig(out3, dpi=180, bbox_inches="tight", facecolor="#0D1117")
    plt.close()
    print(f"  Guardado: {out3}")

    print("\n" + "=" * 65)
    print("  SCRIPT 02 COMPLETADO")
    print("=" * 65)


if __name__ == "__main__":
    main()
