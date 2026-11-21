"""Genera interfaz/index.html a partir de los resultados del proyecto.

Uso (desde la raíz del repositorio, con el entorno activado):
    python src/exportar_interfaz.py

No entrena nada: lee data/processed/, data/osm/ y vuelve a ejecutar las funciones
de notebooks/05_rutas.ipynb (A*, BFS y orden de visita) para obtener el trazado de
cada ruta. El resultado es un solo archivo HTML que se abre con doble clic.

Si existe notebooks/04_ga.ipynb, se vuelven a ejecutar sus celdas de cálculo (sin la
instalación de paquetes, las figuras ni la escritura de archivos) para obtener el reparto
del algoritmo genético, las tres líneas base y la curva de convergencia. Se comprueba que
el reparto sea el mismo de data/processed/reparto_patrullas.csv.
"""
import json
import os
import sys
from pathlib import Path

import nbformat
import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
PROC = RAIZ / "data" / "processed"
INTERFAZ = RAIZ / "interfaz"

# ---------------------------------------------------------------------------
# Cifras que solo están en la salida de los notebooks (no en un CSV).
# Si se vuelve a ejecutar 02_prediccion o 03_riesgo, actualizar aquí.
# ---------------------------------------------------------------------------
METRICAS_PREDICCION = {  # 02_prediccion, sección 8
    "modelos": ["Ingenuo", "Perceptrón", "MLP [8]"],
    "validacion": {"MAE": [24.34, 25.10, 25.97], "RMSE": [38.75, 38.27, 39.65], "MAPE": [21.19, 42.87, 33.68]},
    "prueba": {"MAE": [24.82, 24.96, 27.36], "RMSE": [38.08, 38.37, 41.28], "MAPE": [23.63, 31.47, 40.62]},
}
PESOS_RIESGO = [  # 03_riesgo, sección 4 (peso por lugar a menos de 100 m)
    {"factor": "Bancos y cajeros", "peso": 0.240281},
    {"factor": "Mercados", "peso": 0.176959},
    {"factor": "Paraderos", "peso": 0.044922},
    {"factor": "Cualquier calle (base)", "peso": 0.001458},
    {"factor": "Bares y discotecas", "peso": 0.0},
    {"factor": "Cerca de la policía", "peso": 0.0},
]
VALIDACION_RIESGO = {  # 03_riesgo, sección 5 (dejando un distrito fuera)
    "base": {"MAE": 132.11, "MAPE": 159.79, "R2": 0.19},
    "completo": {"MAE": 76.54, "MAPE": 45.87, "R2": 0.63},
}


def titulo(nombre):
    menores = {"DE", "DEL", "LA", "EL", "LOS"}
    partes = [p.capitalize() if p not in menores or i == 0 else p.lower() for i, p in enumerate(nombre.split())]
    return " ".join(partes).replace(" - ", " – ")


def anillos(geom, tolerancia=0.0006):
    """Polígono simplificado como lista de anillos [[lon, lat], ...] con 4 decimales."""
    geom = geom.simplify(tolerancia, preserve_topology=True)
    poligonos = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
    return [[[round(x, 4), round(y, 4)] for x, y in p.exterior.coords] for p in poligonos]


def ejecutar_rutas():
    """Ejecuta las celdas de cálculo de 05_rutas (sin figuras ni escritura de archivos)."""
    os.environ.setdefault("PATRULLA_OSM", "local")
    os.chdir(RAIZ / "notebooks")
    nb = nbformat.read("05_rutas.ipynb", 4)
    entorno = {"__name__": "rutas"}
    for celda in nb.cells:
        if celda.cell_type != "code":
            continue
        codigo = celda.source
        if "folium.Map" in codigo:  # de la celda de mapas solo interesa la función coordenadas
            codigo = codigo.split("\nfor u in PILOTOS")[0]
        if "plt.subplots" in codigo:
            continue
        codigo = "\n".join(l for l in codigo.splitlines() if ".to_csv(" not in l)
        exec(compile(codigo, "05_rutas", "exec"), entorno)
    os.chdir(RAIZ)
    return entorno


def ejecutar_ga():
    """Ejecuta las celdas de cálculo de 04_ga y devuelve los repartos, su cobertura y la convergencia."""
    os.chdir(RAIZ / "notebooks")
    nb = nbformat.read("04_ga.ipynb", 4)
    e = {"__name__": "ga"}
    for celda in nb.cells:
        codigo = celda.source
        if celda.cell_type != "code" or codigo.lstrip().startswith(("%", "!")) or "plt." in codigo:
            continue
        codigo = "\n".join(l for l in codigo.splitlines() if ".to_csv(" not in l)
        exec(compile(codigo, "04_ga", "exec"), e)
    os.chdir(RAIZ)

    guardado = pd.read_csv(PROC / "reparto_patrullas.csv", dtype={"UBIGEO": str})
    assert guardado["UBIGEO"].tolist() == e["ubigeos"] and guardado["PATRULLAS"].tolist() == list(e["x_optimo"]), \
        "04_ga no reproduce reparto_patrullas.csv: vuelve a ejecutar el notebook"

    # Comprobación: la función de aptitud es una suma de términos cóncavos, así que el reparto
    # voraz (sumar cada patrulla donde más cobertura agrega) da el óptimo exacto.
    areas, d, alpha, meta = np.array(e["areas"]), np.array(e["d_esperadas"]), e["alpha"], e["meta"]
    p_min, p_max = np.array(e["p_min"]), np.array(e["p_max"])
    p = p_min.copy()
    for _ in range(meta - p.sum()):
        ganancia = d * (np.exp(-alpha * p / areas) - np.exp(-alpha * (p + 1) / areas))
        ganancia[p >= p_max] = -1
        p[np.argmax(ganancia)] += 1
    optimo = e["calcular_fitness"](p.tolist(), e["d_esperadas"], e["areas"], alpha)

    vector = lambda x: dict(zip(e["ubigeos"], [int(v) for v in x]))
    return {
        "n": int(meta),
        "alpha": alpha,
        "metodos": {"parejo": vector(e["x_parejo"]), "proporcional": vector(e["x_prop_ant"]),
                    "renamu": vector(e["x_renamu"]), "ga": vector(e["x_optimo"])},
        "cobertura": {"parejo": round(e["fit_parejo"], 2), "proporcional": round(e["fit_prop_ant"], 2),
                      "renamu": round(e["fit_renamu"], 2), "ga": round(e["fit_optimo"], 2), "optimo": round(optimo, 2)},
        "convergencia": {"mejor": [round(v, 3) for v in e["hist_mejor"]], "promedio": [round(v, 3) for v in e["hist_prom"]]},
    }


def exportar_piloto(e, ubigeo):
    g, _ = e["grafos"][ubigeo]
    nombre, salida, nodos_p = e["paradas"][ubigeo]
    xs = np.array([d["x"] for _, d in g.nodes(data=True)])
    ys = np.array([d["y"] for _, d in g.nodes(data=True)])
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    q = lambda x, y: (int(round((x - x0) / (x1 - x0) * 10000)), int(round((y - y0) / (y1 - y0) * 10000)))

    # Calles: un segmento por par de esquinas, con su riesgo (0 a 100)
    vistos, calles = set(), []
    for a, b, d in g.edges(data=True):
        par = frozenset((a, b))
        if par in vistos or a == b:
            continue
        vistos.add(par)
        calles += [*q(g.nodes[a]["x"], g.nodes[a]["y"]), *q(g.nodes[b]["x"], g.nodes[b]["y"]), int(round(d["riesgo"] * 100))]

    rutas = {}
    for beta in e["BETAS_COMPARAR"]:
        ruta, secuencia = e["rutas"][ubigeo, beta]
        xy = e["coordenadas"](g, ruta, beta)
        plano = []
        for x, y in xy:
            plano += q(x, y)
        fila = e["resumen"][(e["resumen"]["UBIGEO"] == ubigeo) & (e["resumen"]["beta"] == beta)].iloc[0]
        rutas[f"{beta:g}"] = {
            "xy": plano,
            "orden": [nodos_p.index(n) + 1 for n in secuencia[1:-1]],
            "km": round(float(fila["km"]), 2),
            "riesgo_medio": round(float(fila["riesgo_medio"]), 3),
            "pct_alto": round(float(fila["% km en calles de riesgo > 0,5"]), 1),
        }

    comp = e["comparacion"].loc[ubigeo]
    algoritmos = [{"nombre": n, "nodos": int(f["nodos revisados"]), "km": round(f["metros"] / 1000, 2)} for n, f in comp.iterrows()]
    p = e["puntos"][e["puntos"]["UBIGEO"] == ubigeo].sort_values("ORDEN")
    return {
        "bbox": [x0, y0, x1, y1],
        "esquinas": g.number_of_nodes(),
        "tramos": len(vistos),
        "calles": calles,
        "comisaria": {"nombre": nombre, "xy": q(g.nodes[salida]["x"], g.nodes[salida]["y"])},
        "puntos": [{"n": int(o), "xy": q(g.nodes[n]["x"], g.nodes[n]["y"]), "riesgo": float(r)}
                   for o, n, r in zip(p["ORDEN"], nodos_p, p["RIESGO_CRUDO"])],
        "rutas": rutas,
        "algoritmos": algoritmos,
    }


def main():
    sys.path.insert(0, str(RAIZ / "src"))
    import fuente_osm as fuente

    mensual = pd.read_csv(PROC / "lima_robo_hurto_mensual.csv", dtype={"UBIGEO": str})
    pred = pd.read_csv(PROC / "prediccion_distritos.csv", dtype={"UBIGEO": str}).set_index("UBIGEO")
    areas = pd.read_csv(PROC / "areas_distritos.csv", dtype={"UBIGEO": str}).set_index("UBIGEO")
    limites = fuente.cargar_limites().set_index("UBIGEO")
    riesgo = pd.read_csv(PROC / "riesgo_calles.csv", dtype={"UBIGEO": str}, usecols=["UBIGEO", "RIESGO"])
    riesgo_medio = riesgo.groupby("UBIGEO")["RIESGO"].mean()

    meses = sorted(mensual["FECHA"].unique())
    distritos = []
    for ubigeo, grupo in mensual.sort_values("FECHA").groupby("UBIGEO"):
        distritos.append({
            "ubigeo": ubigeo,
            "nombre": titulo(grupo["DIST_HECHO"].iloc[0]),
            "area": round(float(areas.loc[ubigeo, "AREA_KM2"]), 1),
            "serie": grupo["TOTAL"].astype(int).tolist(),
            "pred": round(float(pred.loc[ubigeo, "D_ESPERADAS"]), 1),
            "riesgo_medio": round(float(riesgo_medio.get(ubigeo, 0)), 3),
            "forma": anillos(limites.loc[ubigeo, "geometry"]),
        })
    assert len(distritos) == 43 and all(len(d["serie"]) == len(meses) for d in distritos)

    reparto = ejecutar_ga() if (RAIZ / "notebooks" / "04_ga.ipynb").exists() else None

    e = ejecutar_rutas()
    datos = {
        "generado": pd.Timestamp.now().strftime("%Y-%m-%d"),
        "meses": [m[:7] for m in meses],
        "mes_prediccion": "2026-08",
        "distritos": distritos,
        "metricas": METRICAS_PREDICCION,
        "pesos": PESOS_RIESGO,
        "validacion_riesgo": VALIDACION_RIESGO,
        "betas": [f"{b:g}" for b in e["BETAS_COMPARAR"]],
        "pilotos": {u: exportar_piloto(e, u) for u in e["PILOTOS"]},
        "reparto": reparto,
    }

    plantilla = (INTERFAZ / "plantilla.html").read_text(encoding="utf-8")
    assert "/*__DATOS__*/null" in plantilla
    salida = plantilla.replace("/*__DATOS__*/null", json.dumps(datos, ensure_ascii=False, separators=(",", ":")))
    (INTERFAZ / "index.html").write_text(salida, encoding="utf-8")
    print(f"Listo: interfaz/index.html ({len(salida) / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()