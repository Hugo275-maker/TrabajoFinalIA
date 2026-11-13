"""Descarga de Overpass las calles y los lugares de los 43 distritos, uno por uno.

Cada distrito se guarda en data/osm/partes/ apenas termina; si el script se corta,
al volver a ejecutarlo salta los distritos ya descargados.
Al final une todo en data/osm/calles_lima.graphml y data/osm/lugares.geojson.
Uso (desde la raíz): .venv\\Scripts\\python.exe src\\descargar_osm.py
"""
import time

import geopandas as gpd
import networkx as nx
import osmnx as ox
import pandas as pd

from fuente_osm import RAIZ

OSM = RAIZ / "data" / "osm"
PARTES = OSM / "partes"
ETIQUETAS_LUGARES = {"amenity": ["bar", "pub", "nightclub", "marketplace", "bank", "atm", "police"],
                     "highway": "bus_stop"}
ESPERAS_S = [30, 60, 120, 240, 480]
PAUSA_ENTRE_DISTRITOS_S = 3

ox.settings.requests_timeout = 300
ox.settings.useful_tags_way = list(ox.settings.useful_tags_way) + ["lit"]
ox.settings.use_cache = True
ox.settings.cache_folder = OSM / "_cache"


def con_reintentos(nombre, funcion):
    for intento, espera in enumerate([0] + ESPERAS_S):
        if espera:
            print(f"    reintento {intento} de {nombre} en {espera} s", flush=True)
            time.sleep(espera)
        try:
            return funcion()
        except ox._errors.InsufficientResponseError:
            return None  # el distrito no tiene ese tipo de dato
        except Exception as error:
            print(f"    {nombre}: {type(error).__name__}: {str(error)[:120]!r}", flush=True)
    raise RuntimeError(f"{nombre}: sin respuesta tras {len(ESPERAS_S)} reintentos")


def descargar_distrito(ubigeo, poligono):
    ruta_calles = PARTES / f"{ubigeo}_calles.graphml"
    ruta_lugares = PARTES / f"{ubigeo}_lugares.gpkg"
    ruta_vacio = PARTES / f"{ubigeo}_lugares.vacio"

    if not ruta_calles.exists():
        G = con_reintentos(f"{ubigeo} calles", lambda: ox.graph_from_polygon(
            poligono, network_type="drive", retain_all=True, truncate_by_edge=True))
        if G is None:
            raise RuntimeError(f"{ubigeo}: Overpass no devolvió calles")
        ox.save_graphml(G, ruta_calles)

    if not ruta_lugares.exists() and not ruta_vacio.exists():
        f = con_reintentos(f"{ubigeo} lugares", lambda: ox.features_from_polygon(poligono, ETIQUETAS_LUGARES))
        if f is None or f.empty:
            ruta_vacio.touch()
        else:
            columnas = [c for c in ["amenity", "highway", "name", "geometry"] if c in f.columns]
            f = f[columnas].reset_index()
            f["UBIGEO_DESCARGA"] = ubigeo
            f.to_file(ruta_lugares, driver="GPKG")


def unir(ubigeos):
    grafos = [ox.load_graphml(PARTES / f"{u}_calles.graphml") for u in ubigeos]
    G = nx.compose_all(grafos)
    G.graph.update(grafos[0].graph)
    ox.save_graphml(G, OSM / "calles_lima.graphml")

    partes = [gpd.read_file(p) for p in sorted(PARTES.glob("*_lugares.gpkg"))]
    lugares = pd.concat(partes, ignore_index=True)
    lugares = gpd.GeoDataFrame(lugares.drop_duplicates(["element", "id"]), crs=partes[0].crs)
    lugares.to_file(OSM / "lugares.geojson", driver="GeoJSON")
    print(f"Unido: {G.number_of_nodes()} nodos, {G.number_of_edges()} aristas, {len(lugares)} lugares")


def main():
    PARTES.mkdir(parents=True, exist_ok=True)
    limites = gpd.read_file(OSM / "limites_distritos.geojson").sort_values("UBIGEO")
    inicio = time.time()
    for n, (_, d) in enumerate(limites.iterrows(), 1):
        t = time.time()
        descargar_distrito(d["UBIGEO"], d.geometry)
        print(f"[{n}/43] {d['UBIGEO']} {d['DIST_NORM']} listo en {time.time() - t:.0f} s "
              f"(total {(time.time() - inicio) / 60:.1f} min)", flush=True)
        time.sleep(PAUSA_ENTRE_DISTRITOS_S)
    unir(limites["UBIGEO"].tolist())


if __name__ == "__main__":
    main()
