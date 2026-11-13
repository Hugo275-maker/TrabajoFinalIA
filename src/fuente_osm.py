"""Carga los datos geográficos sin llamar a la API de Overpass.

La fuente se elige con la variable de entorno PATRULLA_OSM:
  local (por defecto) -> data/osm/, datos reales de OpenStreetMap
  mock                -> data/osm_mock/, datos INVENTADOS para desarrollar (se generan con mock_osm.py)

Archivos esperados en modo local (ver README):
  limites_distritos.geojson | .gpkg   polígonos con columna name o DIST_NORM
  lugares.geojson | .gpkg             etiquetas amenity/highway de OSM
  calles_lima.graphml | .graphml.gz | .osm   red de calles (en el repositorio va comprimida)
"""
import gzip
import os
import unicodedata
from pathlib import Path

import geopandas as gpd
import osmnx as ox
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
CRS_METROS = "EPSG:32718"  # UTM 18S
CATEGORIAS_AMENITY = {
    "bar": "bar", "pub": "bar", "nightclub": "bar",
    "marketplace": "mercado",
    "bank": "banco_cajero", "atm": "banco_cajero",
    "police": "comisaria",
}


def fuente():
    valor = os.environ.get("PATRULLA_OSM", "local").lower()
    if valor not in ("mock", "local"):
        raise ValueError("PATRULLA_OSM debe ser 'mock' o 'local'")
    return valor


def es_mock():
    return fuente() == "mock"


def carpeta():
    forzada = os.environ.get("PATRULLA_OSM_DIR")
    if forzada:
        return Path(forzada)
    return RAIZ / "data" / ("osm_mock" if es_mock() else "osm")


def ruta_areas():
    """Los resultados simulados nunca van a data/processed/."""
    if es_mock():
        return carpeta() / "areas_distritos_MOCK.csv"
    return RAIZ / "data" / "processed" / "areas_distritos.csv"


def normalizar(nombre):
    sin_tildes = unicodedata.normalize("NFKD", str(nombre)).encode("ascii", "ignore").decode("ascii")
    return sin_tildes.upper().strip()


def _buscar(base, extensiones):
    for ext in extensiones:
        ruta = carpeta() / f"{base}{ext}"
        if ruta.exists():
            return ruta
    opciones = ", ".join(base + e for e in extensiones)
    extra = " Ejecuta mock_osm.generar()." if es_mock() else ""
    raise FileNotFoundError(f"Falta en {carpeta()}: {opciones}.{extra}")


def _ubigeo():
    return pd.read_csv(RAIZ / "data" / "processed" / "ubigeo_lima.csv", dtype={"UBIGEO": str})


def cargar_limites():
    """43 filas: UBIGEO, DIST_NORM, geometry (EPSG:4326)."""
    gdf = gpd.read_file(_buscar("limites_distritos", [".geojson", ".gpkg"])).to_crs("EPSG:4326")
    gdf = gdf[gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
    if "DIST_NORM" not in gdf.columns:
        if "name" not in gdf.columns:
            raise ValueError("Los límites necesitan una columna name o DIST_NORM")
        gdf["DIST_NORM"] = gdf["name"].map(normalizar)

    # Si un nombre se repite (p. ej. un distrito vecino homónimo), queda el polígono mayor
    gdf["_area"] = gdf.to_crs(CRS_METROS).area
    gdf = gdf.sort_values("_area", ascending=False).drop_duplicates("DIST_NORM")

    ubigeo = _ubigeo()
    faltan = sorted(set(ubigeo["DIST_NORM"]) - set(gdf["DIST_NORM"]))
    if faltan:
        raise ValueError(f"Distritos sin polígono: {faltan}")
    return (gdf[["DIST_NORM", "geometry"]]
            .merge(ubigeo[["UBIGEO", "DIST_NORM"]], on="DIST_NORM")
            [["UBIGEO", "DIST_NORM", "geometry"]]
            .sort_values("UBIGEO").reset_index(drop=True))


def _categoria(fila):
    if fila.get("highway") == "bus_stop":
        return "paradero"
    return CATEGORIAS_AMENITY.get(fila.get("amenity"))


def cargar_lugares(limites=None):
    """Puntos con CATEGORIA y el UBIGEO donde caen."""
    gdf = gpd.read_file(_buscar("lugares", [".geojson", ".gpkg"])).to_crs(CRS_METROS)
    if "CATEGORIA" not in gdf.columns:
        gdf["CATEGORIA"] = gdf.apply(_categoria, axis=1)
    gdf = gdf[gdf["CATEGORIA"].notna()].copy()
    gdf["geometry"] = gdf.geometry.centroid  # algunos lugares son polígonos

    limites = cargar_limites() if limites is None else limites
    unidos = gpd.sjoin(gdf[["CATEGORIA", "geometry"]], limites.to_crs(CRS_METROS)[["UBIGEO", "geometry"]],
                       how="inner", predicate="within")
    return unidos.drop(columns="index_right").to_crs("EPSG:4326").reset_index(drop=True)


def cargar_calles():
    """Grafo dirigido de osmnx en lat/lon."""
    ruta = _buscar("calles_lima", [".graphml", ".graphml.gz", ".osm"])
    if ruta.name.endswith(".graphml.gz"):
        with gzip.open(ruta, "rt", encoding="utf-8") as f:
            return ox.load_graphml(graphml_str=f.read())
    if ruta.suffix == ".graphml":
        return ox.load_graphml(ruta)
    return ox.graph_from_xml(ruta, retain_all=True)
