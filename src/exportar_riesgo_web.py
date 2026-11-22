"""Prepara el riesgo por calle para la web (clic en el mapa).

Junta data/processed/riesgo_calles.csv (de 03_riesgo) con la forma y el nombre de cada
tramo del grafo de OSM y guarda data/processed/riesgo_calles_web.csv.gz, que la web
lee sin necesitar osmnx, geopandas ni pandas.

Uso, desde la raíz del proyecto y después de ejecutar 03_riesgo:
    python src/exportar_riesgo_web.py
"""
import csv
import gzip

import pandas as pd

import fuente_osm as fuente

PROCESADOS = fuente.RAIZ / "data" / "processed"
SALIDA = PROCESADOS / "riesgo_calles_web.csv.gz"
TOLERANCIA_M = 3  # se simplifica la forma de cada tramo para que el archivo pese menos


def nombre(valor):
    if isinstance(valor, list):
        return " / ".join(dict.fromkeys(str(v) for v in valor))
    return "" if pd.isna(valor) else str(valor)


def main():
    assert not fuente.es_mock(), "La web solo usa datos reales"
    G = fuente.cargar_calles()
    Gu = fuente.ox.convert.to_undirected(G)  # el mismo grafo sin dirección que usa 03_riesgo
    tramos = fuente.ox.graph_to_gdfs(Gu, nodes=False)
    tramos = tramos[["name", "highway", "geometry"]].reset_index()

    riesgo = pd.read_csv(PROCESADOS / "riesgo_calles.csv", dtype={"UBIGEO": str})
    datos = riesgo.merge(tramos, on=["u", "v", "key"], how="left", validate="one_to_one")
    faltan = datos["geometry"].isna().sum()
    assert faltan == 0, f"{faltan} tramos de riesgo_calles.csv no están en el grafo"

    forma = fuente.gpd.GeoSeries(datos["geometry"], crs="EPSG:4326").to_crs(fuente.CRS_METROS)
    forma = forma.simplify(TOLERANCIA_M).to_crs("EPSG:4326")

    with gzip.open(SALIDA, "wt", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["UBIGEO", "RIESGO", "NOMBRE", "TIPO", "PARADEROS", "MERCADOS",
                    "BANCOS_CAJEROS", "BARES", "CERCA_POLICIA", "COORDS"])
        for fila, geom in zip(datos.itertuples(index=False), forma):
            coords = ";".join(f"{x:.5f},{y:.5f}" for x, y in geom.coords)
            w.writerow([fila.UBIGEO, f"{fila.RIESGO:.3f}", nombre(fila.name), nombre(fila.highway),
                        fila.paraderos, fila.mercados, fila.bancos_cajeros, fila.bares,
                        f"{fila.cerca_policia:.2f}", coords])
    print(f"Guardado {SALIDA.name}: {len(datos):,} tramos, {SALIDA.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
