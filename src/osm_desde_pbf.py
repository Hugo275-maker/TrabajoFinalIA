"""Extrae calles y lugares de Lima del archivo de Perú de Geofabrik, sin usar ninguna API.

Entrada: data/osm/fuente/peru-latest.osm.pbf (https://download.geofabrik.de/south-america/peru.html)
         data/osm/limites_distritos.geojson
Salidas: data/osm/calles_lima.graphml.gz (comprimido para caber en GitHub) y data/osm/lugares.geojson

Las calles usan el mismo filtro "drive" que osmnx aplica en Overpass y se recortan igual
que graph_from_polygon (margen de 500 m, simplificación y recorte final al contorno).
Uso (desde la raíz): .venv\\Scripts\\python.exe src\\osm_desde_pbf.py
"""
import gzip
import re
import shutil
import time
from xml.sax.saxutils import quoteattr

import geopandas as gpd
import osmium
import osmnx as ox
from shapely.geometry import Point

from fuente_osm import CRS_METROS, RAIZ

OSM = RAIZ / "data" / "osm"
PBF = OSM / "fuente" / "peru-latest.osm.pbf"
XML_TEMPORAL = OSM / "fuente" / "lima_drive.osm"

# Filtro "drive" de osmnx 2.x (osmnx._overpass._get_network_filter("drive")) más su ["access"!~"private"]
EXCLUIR = {
    "highway": r"abandoned|bridleway|bus_guideway|construction|corridor|cycleway|elevator|escalator|footway|no|path"
               r"|pedestrian|planned|platform|proposed|raceway|razed|rest_area|service|services|steps|track",
    "area": r"yes",
    "access": r"private",
    "motor_vehicle": r"no",
    "motorcar": r"no",
    "service": r"alley|driveway|emergency_access|parking|parking_aisle|private",
}
AMENITY_LUGARES = {"bar", "pub", "nightclub", "marketplace", "bank", "atm", "police"}
TAGS_CALLE = ["highway", "oneway", "lit", "name", "ref", "lanes", "maxspeed", "junction",
              "access", "service", "bridge", "tunnel", "width", "est_width"]


def es_calle_drive(tags):
    if "highway" not in tags:
        return False
    return not any(clave in tags and re.search(patron, tags[clave]) for clave, patron in EXCLUIR.items())


def es_lugar(tags):
    return tags.get("amenity") in AMENITY_LUGARES or tags.get("highway") == "bus_stop"


def dentro(lon, lat, caja):
    return caja[0] <= lon <= caja[2] and caja[1] <= lat <= caja[3]


def leer_pbf(caja):
    """Una sola pasada: calles drive que tocan la caja de Lima y lugares de la Tabla 3."""
    nodos, calles, lugares = {}, [], []
    filtro = osmium.filter.KeyFilter("highway", "amenity")
    for obj in osmium.FileProcessor(str(PBF)).with_locations().with_filter(filtro):
        tags = dict(obj.tags)
        if obj.is_node():
            if es_lugar(tags) and obj.location.valid() and dentro(obj.location.lon, obj.location.lat, caja):
                lugares.append({"element": "node", "id": obj.id, **_tags_lugar(tags),
                                "geometry": Point(obj.location.lon, obj.location.lat)})
        elif obj.is_way():
            puntos = [(n.ref, n.lon, n.lat) for n in obj.nodes if n.location.valid()]
            if len(puntos) < 2 or not any(dentro(lon, lat, caja) for _, lon, lat in puntos):
                continue
            if es_calle_drive(tags):
                for ref, lon, lat in puntos:
                    nodos[ref] = (lon, lat)
                calles.append((obj.id, [p[0] for p in puntos], {k: tags[k] for k in TAGS_CALLE if k in tags}))
            if es_lugar(tags):
                lon = sum(p[1] for p in puntos) / len(puntos)
                lat = sum(p[2] for p in puntos) / len(puntos)
                lugares.append({"element": "way", "id": obj.id, **_tags_lugar(tags), "geometry": Point(lon, lat)})
    return nodos, calles, lugares


def _tags_lugar(tags):
    return {"amenity": tags.get("amenity"), "highway": tags.get("highway"), "name": tags.get("name")}


def escribir_xml(nodos, calles):
    with open(XML_TEMPORAL, "w", encoding="utf-8") as f:
        f.write("<?xml version='1.0' encoding='UTF-8'?>\n<osm version=\"0.6\">\n")
        for ref, (lon, lat) in nodos.items():
            f.write(f'<node id="{ref}" lat="{lat:.7f}" lon="{lon:.7f}"/>\n')
        for way_id, refs, tags in calles:
            f.write(f'<way id="{way_id}">')
            f.write("".join(f'<nd ref="{r}"/>' for r in refs))
            f.write("".join(f"<tag k={quoteattr(k)} v={quoteattr(v)}/>" for k, v in tags.items()))
            f.write("</way>\n")
        f.write("</osm>\n")


def main():
    t0 = time.time()
    limites = gpd.read_file(OSM / "limites_distritos.geojson")
    contorno = limites.union_all()
    contorno_m = gpd.GeoSeries([contorno], crs="EPSG:4326").to_crs(CRS_METROS)
    margen = contorno_m.buffer(500).to_crs("EPSG:4326").iloc[0]
    caja = tuple(margen.bounds)

    nodos, calles, lugares = leer_pbf(caja)
    print(f"PBF leído en {time.time() - t0:.0f} s: {len(calles)} calles, {len(nodos)} nodos, {len(lugares)} lugares", flush=True)

    escribir_xml(nodos, calles)
    ox.settings.useful_tags_way = list(dict.fromkeys(list(ox.settings.useful_tags_way) + ["lit"]))
    G = ox.graph_from_xml(XML_TEMPORAL, simplify=False, retain_all=True)
    G = ox.truncate.truncate_graph_polygon(G, margen, truncate_by_edge=True)
    G = ox.simplify_graph(G)
    G = ox.truncate.truncate_graph_polygon(G, contorno, truncate_by_edge=True)
    graphml = OSM / "calles_lima.graphml"
    ox.save_graphml(G, graphml)
    with open(graphml, "rb") as f, gzip.open(OSM / "calles_lima.graphml.gz", "wb", compresslevel=9) as g:
        shutil.copyfileobj(f, g)
    graphml.unlink()
    XML_TEMPORAL.unlink()

    lug = gpd.GeoDataFrame(lugares, crs="EPSG:4326")
    lug = lug[lug.within(margen)]
    lug.to_file(OSM / "lugares.geojson", driver="GeoJSON")
    print(f"Listo en {time.time() - t0:.0f} s: grafo {G.number_of_nodes()} nodos / {G.number_of_edges()} aristas; "
          f"{len(lug)} lugares", flush=True)


if __name__ == "__main__":
    main()
