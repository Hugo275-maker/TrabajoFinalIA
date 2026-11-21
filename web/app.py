import csv
import json
import random
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from web.ga_engine import (
    calcular_cobertura_distrito,
    calcular_cotas,
    calcular_fitness,
    reparar,
    simular_ga,
)

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = Path(__file__).resolve().parent
DATA_PROCESSED = BASE_DIR / "data" / "processed"
DATA_OSM = BASE_DIR / "data" / "osm"
OUTPUTS_MAPAS = BASE_DIR / "outputs" / "mapas"

ALPHA_DEFAULT = 0.45

app = FastAPI(title="PatrullaIA — Dashboard de Resultados")
app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")
if OUTPUTS_MAPAS.exists():
    app.mount("/mapas", StaticFiles(directory=str(OUTPUTS_MAPAS)), name="mapas")

templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))


def _leer_csv(ruta: Path) -> list[dict]:
    if not ruta.exists():
        return []
    with open(ruta, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _cargar_mes_anterior(ubigeos_orden: list[str]) -> dict[str, float]:
    ruta_hist = DATA_PROCESSED / "lima_robo_hurto_mensual.csv"
    filas = _leer_csv(ruta_hist)
    if not filas:
        return {}

    ignorar = {
        "UBIGEO", "ANIO", "AÑO", "YEAR", "MES", "MONTH",
        "DIST_HECHO", "DIST_NORM", "DISTRITO", "PERIODO",
        "FECHA", "MODALIDAD", "PARTICION", "SPLIT", "CONJUNTO", "SET",
    }
    columnas = list(filas[0].keys())
    col_conteo = None
    for cand in ["DENUNCIAS", "CANTIDAD", "ROBO_HURTO", "TOTAL", "CONTEO"]:
        if cand in columnas:
            col_conteo = cand
            break
    if not col_conteo:
        for col in columnas:
            if col.upper() not in ignorar:
                try:
                    float(filas[0][col])
                    col_conteo = col
                    break
                except ValueError:
                    continue
    if not col_conteo:
        return {}

    tiene_anio_mes = "ANIO" in columnas and "MES" in columnas
    ult_clave = None
    if tiene_anio_mes:
        claves = [(int(float(r["ANIO"])), int(float(r["MES"]))) for r in filas if r.get("ANIO") and r.get("MES")]
        ult_clave = max(claves) if claves else None

    acum = {u: 0.0 for u in ubigeos_orden}
    for r in filas:
        if ult_clave is not None:
            if (int(float(r["ANIO"])), int(float(r["MES"]))) != ult_clave:
                continue
        u = str(r.get("UBIGEO", "")).strip().zfill(6)
        if u in acum:
            try:
                acum[u] += float(r[col_conteo])
            except ValueError:
                pass
    return acum


def cargar_estado_proyecto() -> dict:
    areas_rows = _leer_csv(DATA_PROCESSED / "areas_distritos.csv")
    pred_rows = _leer_csv(DATA_PROCESSED / "prediccion_distritos.csv")
    ga_rows = _leer_csv(DATA_PROCESSED / "reparto_patrullas.csv")
    ren_rows = _leer_csv(DATA_PROCESSED / "renamu_lima.csv")
    rutas_rows = _leer_csv(DATA_PROCESSED / "rutas_resumen.csv")

    pred_map = {str(r["UBIGEO"]).strip().zfill(6): float(r["D_ESPERADAS"]) for r in pred_rows}
    ga_map = {str(r["UBIGEO"]).strip().zfill(6): int(float(r["PATRULLAS"])) for r in ga_rows}
    ren_map = {str(r["UBIGEO"]).strip().zfill(6): int(float(r["PATRULLAS_RENAMU"])) for r in ren_rows}

    areas_orden = sorted(areas_rows, key=lambda r: str(r["UBIGEO"]).strip().zfill(6))
    ubigeos = [str(r["UBIGEO"]).strip().zfill(6) for r in areas_orden]
    mes_ant_map = _cargar_mes_anterior(ubigeos)

    distritos = []
    for r in areas_orden:
        u = str(r["UBIGEO"]).strip().zfill(6)
        area = float(r["AREA_KM2"])
        d_esp = pred_map.get(u, 0.0)
        d_ant = mes_ant_map.get(u, d_esp) if mes_ant_map.get(u, 0.0) > 0 else d_esp
        p_ga = ga_map.get(u, 1)
        p_ren = ren_map.get(u, 1)
        cob_ga = calcular_cobertura_distrito(p_ga, area, ALPHA_DEFAULT) * 100.0
        cob_ren = calcular_cobertura_distrito(p_ren, area, ALPHA_DEFAULT) * 100.0

        distritos.append({
            "ubigeo": u,
            "distrito": str(r["DIST_NORM"]).strip(),
            "area_km2": round(area, 2),
            "d_esperadas": round(d_esp, 2),
            "d_mes_anterior": round(d_ant, 2),
            "densidad": round(d_esp / area, 2) if area > 0 else 0.0,
            "patrullas_ga": p_ga,
            "patrullas_renamu": p_ren,
            "brecha": p_ga - p_ren,
            "cobertura_ga": round(cob_ga, 2),
            "cobertura_renamu": round(cob_ren, 2),
        })

    # Reemplaza estas 2 líneas donde armas areas_vec:
    areas_vec = [float(r["AREA_KM2"]) for r in areas_orden]
    d_esp_vec = [d["d_esperadas"] for d in distritos]
    d_ant_vec = [d["d_mes_anterior"] for d in distritos]
    x_ga = [d["patrullas_ga"] for d in distritos]
    x_ren = [d["patrullas_renamu"] for d in distritos]
    flota_total = sum(x_ren)

    rng_base = random.Random(42)
    p_min, p_max = calcular_cotas(areas_vec, flota_total)
    x_parejo = reparar([flota_total / len(distritos)] * len(distritos), flota_total, p_min, p_max, rng_base)
    suma_ant = sum(d_ant_vec) or 1.0
    x_prop_ant = reparar([(v / suma_ant) * flota_total for v in d_ant_vec], flota_total, p_min, p_max, rng_base)

    fit_parejo = round(calcular_fitness(x_parejo, d_esp_vec, areas_vec, ALPHA_DEFAULT), 2)
    fit_prop_ant = round(calcular_fitness(x_prop_ant, d_esp_vec, areas_vec, ALPHA_DEFAULT), 2)
    fit_renamu = round(calcular_fitness(x_ren, d_esp_vec, areas_vec, ALPHA_DEFAULT), 2)
    fit_ga = round(calcular_fitness(x_ga, d_esp_vec, areas_vec, ALPHA_DEFAULT), 2)

    # Procesar resumen de rutas piloto (Cercado 150101 y SJL 150132)
    rutas_piloto = []
    for rr in rutas_rows:
        col_pct = next((k for k in rr.keys() if "0,5" in k or "0.5" in k or "%" in k), None)
        u_r = str(rr.get("UBIGEO", "")).strip().zfill(6)
        rutas_piloto.append({
            "ubigeo": u_r,
            "distrito": "Cercado de Lima" if u_r == "150101" else ("San Juan de Lurigancho" if u_r == "150132" else u_r),
            "beta": float(rr.get("beta", 0)),
            "km": round(float(rr.get("km", 0)), 3),
            "riesgo_medio": round(float(rr.get("riesgo_medio", 0)), 3),
            "pct_riesgo_alto": round(float(rr.get(col_pct, 0)), 2) if col_pct else 0.0,
            "segundos": round(float(rr.get("segundos", 0)), 4),
        })

    # Curva base de referencia para mostrar al abrir la pestaña GA
    sim_base = simular_ga(areas_vec, d_esp_vec, flota_total, ALPHA_DEFAULT, individuos=80, epochs=120, seed=42)

    geojson_data = {}
    ruta_geo = DATA_OSM / "limites_distritos.geojson"
    if ruta_geo.exists():
        with open(ruta_geo, "r", encoding="utf-8") as f:
            geojson_data = json.load(f)

    return {
        "kpis": {
            "total_distritos": len(distritos),
            "denuncias_esperadas_total": round(sum(d_esp_vec), 1),
            "flota_total": flota_total,
            "cobertura_parejo": fit_parejo,
            "cobertura_prop_ant": fit_prop_ant,
            "cobertura_renamu": fit_renamu,
            "cobertura_ga": fit_ga,
            "ganancia_vs_renamu": round(fit_ga - fit_renamu, 2),
            "alpha": ALPHA_DEFAULT,
        },
        "estrategias": [
            {"nombre": "Reparto Uniforme (P/43)", "cobertura": fit_parejo, "tipo": "base"},
            {"nombre": "Realidad Municipal (RENAMU 2026)", "cobertura": fit_renamu, "tipo": "renamu"},
            {"nombre": "Proporcional Mes Anterior", "cobertura": fit_prop_ant, "tipo": "base"},
            {"nombre": "Algoritmo Genético (PatrullaIA)", "cobertura": fit_ga, "tipo": "optimo"},
        ],
        "distritos": distritos,
        "rutas_piloto": rutas_piloto,
        "mapas_disponibles": {
            "150101": (OUTPUTS_MAPAS / "ruta_150101.html").exists(),
            "150132": (OUTPUTS_MAPAS / "ruta_150132.html").exists(),
        },
        "convergencia_inicial": {
            "mejor": sim_base["historial_mejor"],
            "promedio": sim_base["historial_promedio"],
        },
        "geojson": geojson_data,
    }


ESTADO = cargar_estado_proyecto()


class SimuladorRequest(BaseModel):
    flota: int = Field(default=1187, ge=100, le=3000)
    alpha: float = Field(default=0.45, ge=0.1, le=2.0)
    epochs: int = Field(default=100, ge=20, le=250)

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(WEB_DIR / "static" / "images" / "favicon.png")

@app.get("/", response_class=HTMLResponse)
async def inicio(request: Request):
    return HTMLResponse((WEB_DIR / "templates" / "index.html").read_text(encoding="utf-8"))


@app.get("/api/resumen")
async def api_resumen():
    return JSONResponse({
        "kpis": ESTADO["kpis"],
        "estrategias": ESTADO["estrategias"],
        "distritos": ESTADO["distritos"],
        "rutas_piloto": ESTADO["rutas_piloto"],
        "mapas_disponibles": ESTADO["mapas_disponibles"],
        "convergencia_inicial": ESTADO["convergencia_inicial"],
    })


@app.get("/api/geojson")
async def api_geojson():
    return JSONResponse(ESTADO["geojson"])


@app.post("/api/simular-ga")
async def api_simular_ga(params: SimuladorRequest):
    distritos = ESTADO["distritos"]
    areas_vec = [d["area_km2"] for d in distritos]
    d_esp_vec = [d["d_esperadas"] for d in distritos]
    x_ren = [d["patrullas_renamu"] for d in distritos]

    res = simular_ga(
        areas=areas_vec,
        d_esp=d_esp_vec,
        meta=params.flota,
        alpha=params.alpha,
        individuos=80,
        epochs=params.epochs,
        seed=42,
    )

    rng_b = random.Random(42)
    p_min, p_max = calcular_cotas(areas_vec, params.flota)
    x_parejo = reparar([params.flota / len(distritos)] * len(distritos), params.flota, p_min, p_max, rng_b)
    # Escalar RENAMU proporcionalmente a la nueva flota para comparar equitativamente
    suma_ren = sum(x_ren) or 1
    x_ren_esc = reparar([(v / suma_ren) * params.flota for v in x_ren], params.flota, p_min, p_max, rng_b)

    fit_parejo = round(calcular_fitness(x_parejo, d_esp_vec, areas_vec, params.alpha), 2)
    fit_ren = round(calcular_fitness(x_ren_esc, d_esp_vec, areas_vec, params.alpha), 2)

    detalle = []
    for i, d in enumerate(distritos):
        p_new = res["patrullas"][i]
        cob_new = calcular_cobertura_distrito(p_new, d["area_km2"], params.alpha) * 100.0
        detalle.append({
            "ubigeo": d["ubigeo"],
            "distrito": d["distrito"],
            "patrullas_ga": p_new,
            "patrullas_renamu": x_ren_esc[i],
            "brecha": p_new - x_ren_esc[i],
            "cobertura_ga": round(cob_new, 2),
        })

    return JSONResponse({
        "flota": params.flota,
        "alpha": params.alpha,
        "epochs": params.epochs,
        "fitness_ga": res["fitness"],
        "fitness_parejo": fit_parejo,
        "fitness_renamu": fit_ren,
        "ganancia_vs_renamu": round(res["fitness"] - fit_ren, 2),
        "historial_mejor": res["historial_mejor"],
        "historial_promedio": res["historial_promedio"],
        "detalle": detalle,
    })