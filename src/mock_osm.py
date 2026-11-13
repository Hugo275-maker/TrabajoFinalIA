"""Genera datos geográficos INVENTADOS en data/osm_mock/ para desarrollar sin internet.

Los distritos son cuadrados en una cuadrícula y las calles forman rejillas.
Los UBIGEO y las denuncias usados son reales, pero la geometría, los lugares y el
alumbrado no: la cantidad de lugares se generó proporcional a las denuncias, así que
cualquier ajuste sobre estos datos saldrá bien por construcción.
No usar estos resultados en el informe ni pasarlos al equipo.
"""
import networkx as nx
import numpy as np
import pandas as pd
import geopandas as gpd
import osmnx as ox
from pyproj import Transformer
from shapely.geometry import Point, box

from fuente_osm import CRS_METROS, RAIZ

CARPETA = RAIZ / "data" / "osm_mock"
PASO_CALLE_M = 250
ORIGEN = (270_000, 8_640_000)  # zona de Lima en UTM 18S
CELDA_M = 9_000
PILOTOS = {"150101", "150132"}
LUGARES_POR_DENUNCIA = {"bar": 0.15, "paradero": 0.40, "mercado": 0.03, "banco_cajero": 0.20}


def _denuncias():
    datos = pd.read_csv(RAIZ / "data" / "processed" / "lima_robo_hurto_mensual.csv", dtype={"UBIGEO": str})
    return datos[datos["CONJUNTO"] == "entrenamiento"].groupby("UBIGEO")["TOTAL"].mean()


def generar(semilla=42):
    CARPETA.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(semilla)
    ubigeo = pd.read_csv(RAIZ / "data" / "processed" / "ubigeo_lima.csv", dtype={"UBIGEO": str})
    denuncias = _denuncias()
    a_latlon = Transformer.from_crs(CRS_METROS, "EPSG:4326", always_xy=True)

    limites, lugares = [], []
    G = nx.MultiDiGraph(crs="EPSG:4326")

    for i, fila in ubigeo.iterrows():
        fil, col = divmod(i, 7)
        x0, y0 = ORIGEN[0] + col * CELDA_M, ORIGEN[1] + fil * CELDA_M
        lado = PASO_CALLE_M * int(rng.integers(10, 31))
        if fila["UBIGEO"] in PILOTOS:
            lado = PASO_CALLE_M * 30
        limites.append({"UBIGEO": fila["UBIGEO"], "DIST_NORM": fila["DIST_NORM"],
                        "geometry": box(x0, y0, x0 + lado, y0 + lado)})

        n = lado // PASO_CALLE_M + 1
        base = int(fila["UBIGEO"]) * 10_000
        nodo = lambda a, b: base + a * n + b
        for a in range(n):
            for b in range(n):
                lon, lat = a_latlon.transform(x0 + a * PASO_CALLE_M, y0 + b * PASO_CALLE_M)
                G.add_node(nodo(a, b), x=lon, y=lat, street_count=4)

        for a in range(n):
            for b in range(n):
                for da, db in [(1, 0), (0, 1)]:
                    if a + da >= n or b + db >= n:
                        continue
                    u, v = nodo(a, b), nodo(a + da, b + db)
                    sentido_unico = bool(rng.random() < 0.10)
                    azar = rng.random()
                    lit = "yes" if azar < 0.20 else "no" if azar < 0.30 else None
                    atributos = dict(length=float(PASO_CALLE_M), highway="residential", oneway=sentido_unico)
                    if lit:
                        atributos["lit"] = lit
                    G.add_edge(u, v, **atributos)
                    if not sentido_unico:
                        G.add_edge(v, u, **atributos)

        cantidades = {c: rng.poisson(max(denuncias[fila["UBIGEO"]] * f, 0.5))
                      for c, f in LUGARES_POR_DENUNCIA.items()}
        cantidades["comisaria"] = int(rng.integers(2, 6))
        for categoria, cantidad in cantidades.items():
            for _ in range(cantidad):
                # dentro del margen del distrito, para que el cruce espacial no los pierda
                px, py = rng.uniform(1, lado - 1, 2)
                lugares.append({"CATEGORIA": categoria, "geometry": Point(x0 + px, y0 + py)})

    (gpd.GeoDataFrame(limites, crs=CRS_METROS).to_crs("EPSG:4326")
     .to_file(CARPETA / "limites_distritos.geojson", driver="GeoJSON"))
    (gpd.GeoDataFrame(lugares, crs=CRS_METROS).to_crs("EPSG:4326")
     .to_file(CARPETA / "lugares.geojson", driver="GeoJSON"))
    ox.save_graphml(G, CARPETA / "calles_lima.graphml")
    (CARPETA / "LEEME_DATOS_SIMULADOS.txt").write_text(
        "Datos INVENTADOS para desarrollo. No usar en el informe ni compartir como reales.\n", encoding="utf-8")
    return len(limites), len(lugares), G.number_of_nodes(), G.number_of_edges()


if __name__ == "__main__":
    print("limites, lugares, nodos, aristas:", generar())
