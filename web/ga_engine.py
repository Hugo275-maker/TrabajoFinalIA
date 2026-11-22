import math
import random


def calcular_cobertura_distrito(p_i: float, area_i: float, alpha: float) -> float:
    if area_i <= 0:
        return 0.0
    return 1.0 - math.exp(-alpha * (p_i / area_i))


def calcular_fitness(cromosoma: list[int], d_esp: list[float], areas: list[float], alpha: float) -> float:
    numerador = 0.0
    denominador = 0.0
    for i in range(len(cromosoma)):
        cob_i = calcular_cobertura_distrito(cromosoma[i], areas[i], alpha)
        numerador += d_esp[i] * cob_i
        denominador += d_esp[i]
    return (numerador / denominador) * 100.0 if denominador > 0 else 0.0


def calcular_cotas(areas: list[float], meta: int) -> tuple[list[int], list[int]]:
    n = len(areas)
    suma_areas = sum(areas) or 1.0
    p_min = [1 if meta >= n else 0 for _ in range(n)]
    p_max = []
    for i in range(n):
        max_i = int(meta * (0.15 + (areas[i] / suma_areas)))
        p_max.append(max(p_min[i] + 5, max_i))
    return p_min, p_max


def reparar(cromosoma: list[float], meta: int, p_min: list[int], p_max: list[int], rng: random.Random) -> list[int]:
    n = len(cromosoma)
    vec = []
    for i in range(n):
        val = int(round(cromosoma[i]))
        if val < p_min[i]:
            val = p_min[i]
        elif val > p_max[i]:
            val = p_max[i]
        vec.append(val)

    suma = sum(vec)
    pasos = 0
    limite_pasos = max(10000, meta * 20)
    while suma != meta and pasos < limite_pasos:
        idx = rng.randrange(n)
        if suma < meta:
            if vec[idx] < p_max[idx]:
                vec[idx] += 1
                suma += 1
        else:
            if vec[idx] > p_min[idx]:
                vec[idx] -= 1
                suma -= 1
        pasos += 1
    return vec


def simular_ga(
    areas: list[float],
    d_esp: list[float],
    meta: int,
    alpha: float = 0.45,
    individuos: int = 80,
    epochs: int = 120,
    seed: int = 42,
) -> dict:
    rng = random.Random(seed)
    n = len(areas)
    p_min, p_max = calcular_cotas(areas, meta)

    poblacion = []
    # Semilla 1: reparto uniforme
    poblacion.append(reparar([meta / n] * n, meta, p_min, p_max, rng))
    # Semilla 2: reparto proporcional a denuncias esperadas
    suma_d = sum(d_esp) or 1.0
    poblacion.append(reparar([(d / suma_d) * meta for d in d_esp], meta, p_min, p_max, rng))

    while len(poblacion) < individuos:
        azar = [rng.randint(1, max(10, int(meta / n * 2))) for _ in range(n)]
        poblacion.append(reparar(azar, meta, p_min, p_max, rng))

    hist_mejor = []
    hist_prom = []

    for _ in range(epochs):
        fits = [calcular_fitness(ind, d_esp, areas, alpha) for ind in poblacion]
        orden = sorted(range(individuos), key=lambda idx: fits[idx], reverse=True)
        hist_mejor.append(round(fits[orden[0]], 2))
        hist_prom.append(round(sum(fits) / individuos, 2))

        # Elitismo: pasan los 2 mejores individuos sin cambios
        nueva = [poblacion[orden[0]][:], poblacion[orden[1]][:]]

        while len(nueva) < individuos:
            c1 = rng.sample(range(individuos), 3)
            p1 = poblacion[max(c1, key=lambda idx: fits[idx])]
            c2 = rng.sample(range(individuos), 3)
            p2 = poblacion[max(c2, key=lambda idx: fits[idx])]

            h1, h2 = [], []
            for i in range(n):
                if rng.getrandbits(1):
                    h1.append(p1[i])
                    h2.append(p2[i])
                else:
                    h1.append(p2[i])
                    h2.append(p1[i])

            h1 = reparar(h1, meta, p_min, p_max, rng)
            h2 = reparar(h2, meta, p_min, p_max, rng)

            for h in (h1, h2):
                if rng.random() < 0.45:
                    i = rng.randrange(n)
                    j = rng.randrange(n)
                    if i != j and h[i] > p_min[i] and h[j] < p_max[j]:
                        h[i] -= 1
                        h[j] += 1
                if len(nueva) < individuos:
                    nueva.append(h)

        poblacion = nueva

    fits_fin = [calcular_fitness(ind, d_esp, areas, alpha) for ind in poblacion]
    best_idx = max(range(individuos), key=lambda idx: fits_fin[idx])
    mejor_x = poblacion[best_idx]

    return {
        "patrullas": mejor_x,
        "fitness": round(fits_fin[best_idx], 2),
        "historial_mejor": hist_mejor,
        "historial_promedio": hist_prom,
    }