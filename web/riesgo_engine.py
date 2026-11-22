"""Consulta del riesgo por calle para el clic en el mapa.

Lee data/processed/riesgo_calles_web.csv.gz (de src/exportar_riesgo_web.py) y responde,
para un punto (lat, lon), cuál es el tramo de calle más cercano y su riesgo.
Solo usa la biblioteca estándar para que el servidor no necesite numpy ni geopandas.
"""
import csv
import gzip
import math
from array import array
from pathlib import Path

CELDA_GRADOS = 0.0015          # rejilla para buscar rápido (unos 165 m)
M_POR_GRADO_LAT = 110_574.0
M_POR_GRADO_LON = 111_320.0 * math.cos(math.radians(-12.05))  # Lima

# Niveles del riesgo de una calle (RIESGO va de 0 a 1, ver 03_riesgo).
# Cerca del 90 % de las calles de Lima está por debajo de 0,2; solo el 2,6 % pasa de 0,5,
# que es el mismo umbral de «riesgo alto» que usa 05_rutas.
UMBRAL_MEDIO = 0.2
UMBRAL_ALTO = 0.5


def nivel_calle(riesgo: float) -> str:
    if riesgo >= UMBRAL_ALTO:
        return "alto"
    if riesgo >= UMBRAL_MEDIO:
        return "medio"
    return "bajo"


def _dist2_segmento(px, py, ax, ay, bx, by):
    """Distancia al cuadrado de P al segmento AB, en metros (coordenadas ya en metros)."""
    dx, dy = bx - ax, by - ay
    largo2 = dx * dx + dy * dy
    t = 0.0 if largo2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / largo2))
    cx, cy = ax + t * dx - px, ay + t * dy - py
    return cx * cx + cy * cy


class IndiceRiesgo:
    def __init__(self, ruta: Path):
        self.disponible = ruta.exists()
        self.ubigeo: list[str] = []
        self.riesgo = array("f")
        self.nombre: list[str] = []
        self.tipo: list[str] = []
        self.factores: list[tuple[int, int, int]] = []
        self.inicio = array("l")     # cada tramo ocupa coords[inicio[i]:inicio[i+1]] (lon, lat alternados)
        self.coords = array("d")
        self.rejilla: dict[tuple[int, int], list[int]] = {}
        self.por_distrito: dict[str, list[int]] = {}
        if self.disponible:
            self._cargar(ruta)

    def _cargar(self, ruta: Path):
        cache_texto: dict[str, str] = {}
        with gzip.open(ruta, "rt", encoding="utf-8", newline="") as f:
            for i, fila in enumerate(csv.DictReader(f)):
                u = fila["UBIGEO"]
                self.ubigeo.append(cache_texto.setdefault(u, u))
                self.riesgo.append(float(fila["RIESGO"]))
                nom, tip = fila["NOMBRE"], fila["TIPO"]
                self.nombre.append(cache_texto.setdefault(nom, nom))
                self.tipo.append(cache_texto.setdefault(tip, tip))
                self.factores.append((int(fila["PARADEROS"]), int(fila["MERCADOS"]), int(fila["BANCOS_CAJEROS"])))
                self.inicio.append(len(self.coords))
                celdas = set()
                for par in fila["COORDS"].split(";"):
                    lon, lat = par.split(",")
                    lon, lat = float(lon), float(lat)
                    self.coords.append(lon)
                    self.coords.append(lat)
                    celdas.add((math.floor(lon / CELDA_GRADOS), math.floor(lat / CELDA_GRADOS)))
                # Un tramo largo puede cruzar celdas sin tener vértices en ellas: se rellena su caja
                cx = [c[0] for c in celdas]
                cy = [c[1] for c in celdas]
                for gx in range(min(cx), max(cx) + 1):
                    for gy in range(min(cy), max(cy) + 1):
                        self.rejilla.setdefault((gx, gy), []).append(i)
                self.por_distrito.setdefault(u, []).append(i)
        self.inicio.append(len(self.coords))

    def __len__(self):
        return len(self.riesgo)

    def _puntos(self, i: int) -> list[tuple[float, float]]:
        a, b = self.inicio[i], self.inicio[i + 1]
        c = self.coords
        return [(c[k], c[k + 1]) for k in range(a, b, 2)]

    def latlon(self, i: int) -> list[list[float]]:
        return [[lat, lon] for lon, lat in self._puntos(i)]

    def mas_cercano(self, lat: float, lon: float, radio_m: float = 150.0):
        """Índice del tramo más cercano a (lat, lon) y su distancia en metros, o None."""
        if not self.disponible:
            return None
        anillos = int(math.ceil(radio_m / (CELDA_GRADOS * M_POR_GRADO_LAT)))
        gx0, gy0 = math.floor(lon / CELDA_GRADOS), math.floor(lat / CELDA_GRADOS)
        candidatos = set()
        for gx in range(gx0 - anillos, gx0 + anillos + 1):
            for gy in range(gy0 - anillos, gy0 + anillos + 1):
                candidatos.update(self.rejilla.get((gx, gy), ()))
        px, py = lon * M_POR_GRADO_LON, lat * M_POR_GRADO_LAT
        mejor, mejor_d2 = None, radio_m * radio_m
        for i in candidatos:
            pts = [(x * M_POR_GRADO_LON, y * M_POR_GRADO_LAT) for x, y in self._puntos(i)]
            for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                d2 = _dist2_segmento(px, py, ax, ay, bx, by)
                if d2 < mejor_d2:
                    mejor, mejor_d2 = i, d2
        if mejor is None:
            return None
        return mejor, math.sqrt(mejor_d2)

    def describir(self, i: int, distancia_m: float) -> dict:
        r = float(self.riesgo[i])
        paraderos, mercados, bancos = self.factores[i]
        return {
            "nombre": self.nombre[i] or "Calle sin nombre en OSM",
            "tipo": self.tipo[i],
            "ubigeo": self.ubigeo[i],
            "riesgo": round(r, 3),
            "nivel": nivel_calle(r),
            "distancia_m": round(distancia_m, 1),
            "paraderos": paraderos,
            "mercados": mercados,
            "bancos_cajeros": bancos,
            "coords": self.latlon(i),
        }

    def tramos_distrito(self, ubigeo: str, minimo: float = UMBRAL_MEDIO) -> list[dict]:
        """Tramos con riesgo medio o alto de un distrito, para pintarlos en el mapa."""
        return [
            {"r": round(float(self.riesgo[i]), 3), "c": self.latlon(i)}
            for i in self.por_distrito.get(ubigeo, [])
            if self.riesgo[i] >= minimo
        ]


# ---------- distrito de un punto (sin shapely) ----------

def _dentro_anillo(lon, lat, anillo):
    dentro = False
    j = len(anillo) - 1
    for i in range(len(anillo)):
        xi, yi = anillo[i][0], anillo[i][1]
        xj, yj = anillo[j][0], anillo[j][1]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            dentro = not dentro
        j = i
    return dentro


def _dentro_poligono(lon, lat, poligono):
    if not _dentro_anillo(lon, lat, poligono[0]):
        return False
    return not any(_dentro_anillo(lon, lat, hueco) for hueco in poligono[1:])


class LocalizadorDistritos:
    def __init__(self, geojson: dict):
        self.items = []
        for feat in geojson.get("features", []):
            geom = feat.get("geometry") or {}
            if geom.get("type") == "Polygon":
                poligonos = [geom["coordinates"]]
            elif geom.get("type") == "MultiPolygon":
                poligonos = geom["coordinates"]
            else:
                continue
            xs = [p[0] for pol in poligonos for p in pol[0]]
            ys = [p[1] for pol in poligonos for p in pol[0]]
            u = str(feat["properties"].get("UBIGEO", "")).zfill(6)
            self.items.append((u, (min(xs), min(ys), max(xs), max(ys)), poligonos))

    def ubigeo(self, lat: float, lon: float):
        for u, (x0, y0, x1, y1), poligonos in self.items:
            if x0 <= lon <= x1 and y0 <= lat <= y1 and any(_dentro_poligono(lon, lat, p) for p in poligonos):
                return u
        return None
