# PatrullaIA

Predice denuncias por robo y hurto en los 43 distritos de Lima, reparte patrullas y traza rutas en los distritos piloto.
Detalle completo: `docs/PatrullaIA_Hoja_de_ruta.docx`.

## Estructura

```
data/raw/         Datos originales (no se modifican)
data/processed/   Tablas limpias que usan los notebooks
data/osm/         Datos de OpenStreetMap (límites, lugares y calles)
src/              Scripts de descarga y lectura de OSM
notebooks/        Un notebook por módulo (ejecutar desde esta carpeta)
outputs/          Figuras y mapas para el informe
docs/             Hoja de ruta y planes
```

## Notebooks y archivos que se pasan entre módulos

| Notebook | Responsable | Produce (en `data/processed/`) | Lo usa |
|---|---|---|---|
| `01_datos` | Miguel | `lima_robo_hurto_mensual.csv`, `ubigeo_lima.csv` | Todos |
| `01b_osm` | Hugo | `areas_distritos.csv` (UBIGEO, DIST_NORM, AREA_KM2) | Flavia, Deivis |
| `02_prediccion` | Flavia | `prediccion_distritos.csv` (UBIGEO, D_ESPERADAS) | Deivis |
| `03_riesgo` | Hugo | `riesgo_calles.csv`, `puntos_criticos.csv` | `05_rutas` |
| `04_ga` | Deivis | `reparto_patrullas.csv` (UBIGEO, PATRULLAS) | Informe |
| `05_rutas` | Hugo | Mapas en `outputs/mapas/` | Informe |

El UBIGEO se lee siempre como texto: `dtype={"UBIGEO": str}`.

`riesgo_calles.csv` tiene una fila por tramo **sin dirección** (`u`, `v`, `key` del grafo sin dirección). Para usarlo en el grafo dirigido de rutas, se busca cada arista por el par `{u, v}` sin importar el orden. `RIESGO` va de 0 a 1 (para A*) y `RIESGO_CRUDO` es el valor sin recortar.
Los nombres de `prediccion_distritos.csv` y `reparto_patrullas.csv` son una propuesta por confirmar con el equipo.

## Datos de OpenStreetMap sin depender de la API

`src/fuente_osm.py` lee archivos y no llama a Overpass. La fuente se elige con la variable `PATRULLA_OSM`:

| Valor | Carpeta | Para qué | `01b_osm` guarda las áreas en |
|---|---|---|---|
| `local` (por defecto) | `data/osm/` | Resultados reales | `data/processed/areas_distritos.csv` |
| `mock` | `data/osm_mock/` | Programar con datos **inventados** (se generan con `src/mock_osm.py`) | `data/osm_mock/areas_distritos_MOCK.csv` |

Los resultados con `mock` no van al informe ni se pasan al equipo; `03_riesgo` y `05_rutas` se detienen si se ejecutan en ese modo.

Archivos de `data/osm/` (ya incluidos en el repositorio):

| Archivo | Contenido | Origen |
|---|---|---|
| `limites_distritos.geojson` | Polígonos de los 43 distritos | `src/descargar_limites.py` (Nominatim) |
| `lugares.geojson` | Lugares con `amenity`, `highway` y `name` (Tabla 3 de la hoja de ruta) | `src/osm_desde_pbf.py` |
| `calles_lima.graphml.gz` | Red de calles `drive`, comprimida para no pasar el límite de 100 MB de GitHub | `src/osm_desde_pbf.py` |

`fuente_osm.cargar_calles()` lee el `.graphml.gz` directamente; no hace falta descomprimirlo.

Las calles y los lugares salen del extracto de Perú de Geofabrik del 8 de noviembre de 2026. Para actualizarlos, se descarga `peru-latest.osm.pbf` de https://download.geofabrik.de/south-america/peru.html en `data/osm/fuente/` (no se sube: pesa 257 MB) y se ejecuta `src/osm_desde_pbf.py`. La comparación con Overpass y las cifras están en `docs/revision_osm.md`.

Las áreas de `data/processed/areas_distritos.csv` salen de los polígonos de OSM y pueden diferir algo de las cifras oficiales.

`src/descargar_osm.py` es la alternativa por Overpass (distrito por distrito, continúa donde quedó si se corta). No se usa: Overpass dejó de responder a mitad de la descarga.

## Instalación

Python 3.12 en Windows, desde la raíz del proyecto. Con 3.14 aparecieron errores internos de Python al ejecutar los notebooks.

```
git clone https://github.com/Hugo275-maker/TrabajoFinalIA.git
cd TrabajoFinalIA
uv python install 3.12
uv venv --seed --python 3.12 .venv
.venv\Scripts\activate
pip install -r requirements.txt
```
