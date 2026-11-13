"""Descarga los límites reales de los 43 distritos desde Nominatim y calcula sus áreas.

Solo escribe los archivos si los 43 polígonos pasan las validaciones.
Salidas: data/osm/limites_distritos.geojson y data/processed/areas_distritos.csv
Uso (desde la raíz): .venv\\Scripts\\python.exe src\\descargar_limites.py
"""
import geopandas as gpd
import osmnx as ox
import pandas as pd

from fuente_osm import CRS_METROS, RAIZ

ox.settings.use_cache = True
ox.settings.cache_folder = RAIZ / "data" / "osm" / "_cache"

CONSULTA_PROVINCIA = "Province of Lima, Lima Metropolitan Area, Lima, Peru"
AREA_MAX_KM2 = 450        # el distrito más grande de la provincia ronda los 350 km²
PROVINCIA_REF_KM2 = 2672  # superficie aproximada de la provincia de Lima
TOLERANCIA_SUMA = 0.10
SOLAPE_MAX_KM2 = 2


ALIAS = {"Lima": ["Cercado de Lima", "Lima"],
         "Lurigancho - Chosica": ["Lurigancho", "Lurigancho-Chosica", "Chosica"]}
RESULTADOS_POR_CONSULTA = 3


def plantillas(nombre):
    consultas = []
    for n in ALIAS.get(nombre, [nombre]):
        consultas += [f"Distrito de {n}, Provincia de Lima, Perú",
                      f"{n}, Provincia de Lima, Perú",
                      f"{n}, Lima, Perú"]
    return consultas


def motivo_rechazo(fila, geom_m, provincia_m):
    area = geom_m.area / 1e6
    if fila["class"] != "boundary" or fila["type"] != "administrative":
        return f"es {fila['class']}/{fila['type']}"
    if geom_m.geom_type not in ("Polygon", "MultiPolygon"):
        return "no es polígono"
    if area > AREA_MAX_KM2:
        return f"área {area:.0f} km²"
    if not provincia_m.buffer(1000).contains(geom_m.representative_point()):
        return "fuera de la provincia"
    return None


def buscar(nombre, provincia_m):
    """Devuelve la primera respuesta válida y deja registro de lo rechazado."""
    rechazos = []
    for consulta in plantillas(nombre.title()):
        for k in range(1, RESULTADOS_POR_CONSULTA + 1):
            try:
                res = ox.geocode_to_gdf(consulta, which_result=k)
            except Exception as error:
                rechazos.append(f"{consulta} #{k}: {type(error).__name__}")
                break  # no hay más resultados para esta consulta
            motivo = motivo_rechazo(res.iloc[0], res.to_crs(CRS_METROS).geometry.iloc[0], provincia_m)
            if motivo is None:
                return res.iloc[0], consulta, rechazos
            rechazos.append(f"{consulta} #{k}: {motivo}")
    return None, None, rechazos


def main():
    ubigeo = pd.read_csv(RAIZ / "data" / "processed" / "ubigeo_lima.csv", dtype={"UBIGEO": str})
    provincia = ox.geocode_to_gdf(CONSULTA_PROVINCIA)
    provincia_m = provincia.to_crs(CRS_METROS).geometry.iloc[0]
    print(f"Provincia OSM: {provincia_m.area / 1e6:.0f} km²")

    filas, fallos = [], []
    for _, d in ubigeo.iterrows():
        res, consulta, rechazos = buscar(d["DIST_HECHO"], provincia_m)
        if res is None:
            fallos.append((d["UBIGEO"], d["DIST_HECHO"], rechazos))
            print("FALLA", d["UBIGEO"], d["DIST_HECHO"], rechazos)
            continue
        filas.append({"UBIGEO": d["UBIGEO"], "DIST_NORM": d["DIST_NORM"], "OSM_ID": f"{res['osm_type']}/{res['osm_id']}",
                      "DISPLAY_NAME": res["display_name"], "CONSULTA": consulta, "geometry": res.geometry})
    if fallos:
        raise SystemExit(f"{len(fallos)} distritos sin polígono válido. No se guardó nada.")

    limites = gpd.GeoDataFrame(filas, crs="EPSG:4326")
    m = limites.to_crs(CRS_METROS)
    limites["AREA_KM2"] = m.area / 1e6

    problemas = []
    if limites["OSM_ID"].duplicated().any():
        problemas.append(f"polígonos repetidos: {limites.loc[limites['OSM_ID'].duplicated(keep=False), 'DIST_NORM'].tolist()}")
    pares = gpd.sjoin(m, m, predicate="intersects")
    pares = pares[pares.index < pares["index_right"]]
    for i, j in zip(pares.index, pares["index_right"]):
        solape = m.geometry[i].intersection(m.geometry[j]).area / 1e6
        if solape > SOLAPE_MAX_KM2:
            problemas.append(f"solape {limites.DIST_NORM[i]} / {limites.DIST_NORM[j]}: {solape:.1f} km²")
    suma = limites["AREA_KM2"].sum()
    if abs(suma - PROVINCIA_REF_KM2) / PROVINCIA_REF_KM2 > TOLERANCIA_SUMA:
        problemas.append(f"suma de áreas {suma:.0f} km², referencia {PROVINCIA_REF_KM2}")

    print(limites[["UBIGEO", "DIST_NORM", "AREA_KM2", "OSM_ID", "DISPLAY_NAME"]].round(2).to_string())
    print(f"Suma: {suma:.1f} km²")
    if problemas:
        print("PROBLEMAS:", *problemas, sep="\n  ")
        raise SystemExit("Validación fallida. No se guardó nada.")

    limites.drop(columns="AREA_KM2").to_file(RAIZ / "data" / "osm" / "limites_distritos.geojson", driver="GeoJSON")
    limites[["UBIGEO", "DIST_NORM", "AREA_KM2"]].sort_values("UBIGEO").to_csv(
        RAIZ / "data" / "processed" / "areas_distritos.csv", index=False)
    print("Guardados los límites y data/processed/areas_distritos.csv")


if __name__ == "__main__":
    main()
