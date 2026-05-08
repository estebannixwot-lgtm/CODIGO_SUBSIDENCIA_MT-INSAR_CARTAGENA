# Pipeline Automatizado: Monitoreo de Subsidencia en Cartagena mediante InSAR

Este repositorio contiene todo el código fuente, \textit{scripts} de geoprocesamiento espacial y flujos de trabajo metodológicos desarrollados para la tesis de grado: **"Análisis de Subsidencia en Cartagena de Indias mediante técnicas InSAR"** (Universidad Distrital Francisco José de Caldas).

## 🌍 Descripción General del Proyecto

Este sistema fue diseñado para procesar de manera automatizada grandes volúmenes de datos satelitales (imágenes Radar de Apertura Sintética - Sentinel-1) con el objetivo de cuantificar y mapear espacialmente la deformación vertical (subsidencia y levantamiento) de la corteza en la Localidad Histórica y del Caribe Norte en Cartagena, Colombia, durante el periodo 2019-2024.

El flujo de trabajo automatizado redujo el tiempo operativo manual de procesamiento de **más de 2 meses a tan solo una semana**.

## 💻 Arquitectura y Lenguajes

- **Python (3.x):** Lenguaje principal. Se utilizaron librerías geoespaciales avanzadas como `rasterio`, `geopandas`, `matplotlib`, `contextily`, y `numpy`.
- **Bash / Shell:** Para la orquestación masiva y el empaquetado de comandos de la herramienta *SNAP* (ESA) y *MintPy*.
- **XML / SNAP Graphs:** Modelos paramétricos de grafos de procesamiento para el motor satelital.

## 📂 Estructura del Repositorio

1. **`/Scripts`:** Corazón del proyecto.
   - `01_conversion_los_vertical.py`: Transforma los vectores espaciales de la Línea de Vista del Satélite (LOS) a velocidades puramente verticales usando la geometría del ángulo de incidencia local.
   - `02_analisis_gnss.py` & `03_validacion_insar_gnss.py`: Cálculos matemáticos para homologar, filtrar y cruzar estadísticamente los datos de las estaciones físicas GNSS (ej. CART00COL) con los reflectores de radar (InSAR).
   - `11_layouts_blanco_negro.py`: Algoritmo de renderizado masivo cartográfico para producir los "Layouts Híbridos" listos para formato académico en LaTeX. Normaliza las ortofotos, aplica Rango Intercuartil (IQR) para filtrar ruido, y embebe metadatos, cajetines y logos de la universidad automáticamente.
   - `10_pipeline_snap_mintpy.py`: El script maestro de orquestación, encadena las ejecuciones de interferogramas, desenrollado de fase (SNAPHU) y la inversión de la red SBAS en MintPy.
   - `/SNAP_Graphs`: Grafos XML utilizados por el motor Java de SNAP (`gpt`) para estandarizar el procesamiento de los subconjuntos, interferogramas y coherencia espacial.
2. **`/EXPLICACION`:** Documentación teórica, manuales matemáticos y guías detalladas de replicación tanto para Windows Subsystem for Linux (WSL) como flujos de Anaconda.
3. **`/Datos_Profesor`:** (Estructura modelo) Directorio base donde el pipeline almacena y localiza los insumos geométricos, las series de tiempo extraídas (`TS_*.txt`), polígonos de corte (`.shp`), y capas de velocidad calibradas (`.tif`).

## 🚀 Impacto y Escalabilidad

El diseño de este *pipeline* se rige bajo una arquitectura estandarizada. Su lógica algorítmica permite que, simplemente cambiando los *shapefiles* de entrada y los polígonos de anclaje, este código se pueda utilizar de forma escalable para auditar dinámicas de deformación estructural en **cualquier otra ciudad o región**. Adicionalmente, el código está listo para integrar inteligencia artificial predictiva en futuras líneas de investigación.

## 📝 Autor y Agradecimientos

- **Esteban Pinto** - Investigador Principal
- Proyecto vinculado al Semillero GEIPER, ICG. Universidad Distrital Francisco José de Caldas.
