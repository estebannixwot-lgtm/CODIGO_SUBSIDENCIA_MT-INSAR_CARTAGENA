# Guía Técnica de Replicación: Ecosistema Algorítmico InSAR (End-to-End)

**Ingeniería Catastral y Geodesia**  
**Universidad Distrital Francisco José de Caldas**

---

## Introducción
El presente documento constituye la guía oficial para la ejecución del ecosistema analítico desarrollado en la tesis **"Análisis de la dinámica de subsidencia en Cartagena de Indias mediante interferometría SAR multitemporal"**. 

Se ha estructurado un flujo de trabajo **100% replicable y automatizado**, dividido en tres fases principales que llevan el dato desde su descarga cruda del satélite (Nivel 1) hasta el plano cartográfico de deformación listo para impresión.

---

## REQUISITOS DEL SISTEMA Y ENTORNO ANACONDA

Para replicar la investigación desde cero, se requieren los siguientes componentes de software:
1. **SNAP (Sentinel Application Platform):** Para el pre-procesamiento radar (se invoca automáticamente en segundo plano).
2. **SNAPHU:** Binario compilado para el desenvolvimiento de fase.
3. **WSL / Ubuntu:** Para correr la inversión de la serie temporal (MintPy).
4. **Python 3.10 - 3.13:** Con librerías espaciales gestionadas vía Anaconda.

### Creación del Entorno Virtual (Anaconda Prompt / PowerShell)
Ejecute los siguientes comandos para configurar el ecosistema Python:

```bash
# Creación y activación del entorno
conda create -n insar_tesis python=3.13 -y
conda activate insar_tesis

# Instalación de librerías espaciales
conda install -c conda-forge geopandas rasterio rioxarray matplotlib contextily scipy pandas -y
```

> **Nota Técnica sobre PROJ_LIB:**
> Si el equipo cuenta con QGIS o PostGIS, pueden existir conflictos en las variables de entorno para proyección de coordenadas. Todos nuestros módulos Python incluyen rutinas dinámicas que solucionan esto en tiempo de ejecución.

---

## FASE 1: PRE-PROCESAMIENTO AUTOMATIZADO (SNAP)

En esta fase, la imagen satelital cruda pasa por coregistro, interferometría y corrección del terreno sin usar la GUI de SNAP (liberando memoria RAM y acelerando el proceso).

1. Deposite los archivos `.zip` originales de Sentinel-1 en la carpeta: `Entregable_Universidad/Datos_Profesor/00_RAW_ZIP/`
2. Si va a ejecutar el SBAS, asegúrese de tener la lista de pares en `Datos_Profesor/pares_sbas.txt`.
3. Abra su terminal con el entorno `insar_tesis` activado y ejecute el Orquestador:

```bash
python Scripts/10_pipeline_snap_mintpy.py
```

El **Orquestador Maestro** le presentará un menú interactivo del **Paso 1 al 10**. Usted puede decidir qué paso correr, y el script le preguntará dinámicamente parámetros como el Subswath, creará los XML temporales, inyectará nombres de banda ocultos y ejecutará el motor `gpt.exe`. Entre cada paso, el sistema se pausa para que valide visualmente en SNAP si así lo desea.

---

## FASE 2: INVERSIÓN MULTITEMPORAL (MINTPY)

Una vez que el Paso 10 del Orquestador finaliza, los insumos de fase, coherencia y unwrapping corregidos geográficamente estarán ordenados en `Datos_Profesor/06_MINTPY_INPUTS/`.

1. Abra su entorno Linux (WSL).
2. Navegue hasta la carpeta del proyecto.
3. Ejecute la cadena de inversión basada en su plantilla personalizada:

```bash
smallbaselineApp.py smallbaselineApp.cfg
```

Los resultados de esta inversión serán mapas de velocidad en formato `velocity.h5` que luego se exportan a `.tif`, así como series temporales exportadas en formato `.txt`.

---

## FASE 3: POST-PROCESAMIENTO Y CARTOGRAFÍA (AUTOMÁTICA)

Esta última fase consume los `.tif` y `.txt` generados por MintPy y los GNSS de control, aplicando filtros analíticos severos y produciendo planos híbridos profesionales.

### Disposición de Datos
Mueva las salidas de la FASE 2 y los datos de control GNSS a las subcarpetas dentro de `Datos_Profesor/`:
- **RASTERS VELOCIDAD/:** Archivos .tif de MintPy.
- **GNSS/:** Archivos de series de control GNSS (.neu / .pos).
- **SHAPE AREA DE ESTUDIO/:** Archivo .shp del límite de interés (ej. Centro Histórico).
- **desplazamiento_<escenario>/:** Archivos .txt de la serie temporal (para gráfica cruzada).

### Ejecución de Cartografía
Puede correr este proceso desde el menú del **Orquestador (Paso 11)** o manualmente módulo a módulo:

```bash
# Módulo 1: Proyección de LOS a Vertical y Filtrado Estadístico Intercuartílico (IQR)
python Scripts/01_conversion_los_vertical.py

# Módulo 2: Calibración, Descarte de GNSS Anómalos y Cálculo de Sesgo (RMSE)
python Scripts/02_analisis_gnss.py
python Scripts/03_validacion_insar_gnss.py

# Módulo 3: Máscara Geográfica y Validación Topológica del Shapefile
python Scripts/05_recorte_localidad_historica.py

# Módulo 4: Motor Gráfico de Diagramación (WMS Híbrido Automático)
python Scripts/09_layouts_tesis_oficial.py
```

---

## AUDITORÍA Y TRAZABILIDAD (EFEMÉRIDES)
Para cumplir con estándares de rigor científico, todo el ecosistema (tanto el orquestador SNAP como la cartografía final) integra un *Logger Silencioso*. Cada vez que se ejecuta un módulo, el script guarda un reporte en formato `.txt` dentro de la carpeta `Productos/`.

Allí quedarán registradas las "efemérides" del procesamiento: porcentajes de píxeles excluidos por ruido IQR, los desplazamientos máximos detectados, los errores residuales GNSS y la confirmación de topología espacial. Las salidas gráficas (Planos InSAR) quedan alojados en `Productos/LAYOUTS_TESIS_OFICIAL`.
