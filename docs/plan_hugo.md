# Plan de Hugo: OSM, riesgo por calle, A* y BFS

Punto de partida: 9 de noviembre (semana 13). Según la hoja de ruta, OSM (sem. 11) y riesgo (sem. 12) ya deberían estar listos, así que esta semana se juntan tres entregas.

## Estado de OSM (9 de noviembre)

* **Listo:** `data/processed/areas_distritos.csv` y `data/osm/limites_distritos.geojson` son reales (43 distritos, descargados con `src/descargar_limites.py` desde Nominatim).
* **Listo (10 de noviembre):** calles y lugares reales de los 43 distritos, sacados de Geofabrik. Detalle en `docs/revision_osm.md`.
* **Decidido por los datos:** el alumbrado se quita, porque solo 3,7 % (Cercado) y 2,2 % (SJL) de los tramos tienen la etiqueta. Hay que avisar al equipo.
* **Pendiente:** comparar comisarías con la lista de la PNP, y decidir si el factor de riesgo usa solo comisarías o toda presencia policial y de serenazgo.
* **Listo (10 de noviembre): `03_riesgo` con datos reales.** Pesos con gradiente propio (coincide con la solución exacta), validación dejando un distrito fuera: MAPE 46 % frente a 160 % del modelo que solo cuenta calles. Bares y cercanía a la policía quedaron con peso 0. Salidas: `riesgo_calles.csv`, `puntos_criticos.csv` (8 por piloto) y figuras en `outputs/figuras/`.
* **Listo (10 de noviembre): `05_rutas` con datos reales.** A* y BFS propios; A* coincide con `networkx` y la heurística no sobreestima en ningún nodo. Con β = 2 la patrulla pasa más por calles de riesgo alto (SJL: de 33 % a 46 % del recorrido) y alarga la ruta solo 2–3 %. A* revisa 46 % menos nodos que Dijkstra en Cercado y 68 % menos en SJL. Salidas: `outputs/mapas/ruta_*.html`, `outputs/figuras/rutas_pilotos.png`, `data/processed/rutas_resumen.csv`.
* **Siguiente:** confirmar las comisarías de salida con la PNP (Cotabambas en Cercado y Canto Rey en SJL), integración con el equipo e informe.

## Calendario

| Fecha | Trabajo | Listo cuando |
|---|---|---|
| Lun 9 | Instalar Python y dependencias. Probar `osmnx` con un distrito | Se descarga y dibuja un distrito |
| Lun 9 – mar 10 | `01b_osm`: límites, áreas de los 43 y lugares | `areas_distritos.csv` con 43 filas, enviado a Flavia y Deivis |
| Mar 10 | Red de calles de los 43. Revisar `lit` y comisarías en los pilotos | Grafo guardado; decisión sobre el factor de alumbrado |
| Mié 11 | `03_riesgo`: factores por calle y objetivo por distrito | Tabla de 43 distritos × 6 factores |
| Jue 12 | Gradiente propio, normalización y puntos críticos | Curva de pérdida; 5 a 8 puntos por piloto |
| Jue 12 – vie 13 | `05_rutas`: BFS, A*, orden de visita | Ruta completa en un piloto; con β = 0 coincide con `networkx` |
| Sáb 14 | Segundo piloto, comparación, mapas e integración | Mapas en `outputs/mapas/` |
| 16–21 nov | Informe: Investigación 3, Módulo de rutas, Evaluación y ética; erratas de la sección anterior | Secciones cerradas en el .tex |
| 23–28 nov | Diapositivas y demo de rutas | Demo ensayada |

Si el tiempo no alcanza: terminar primero un piloto completo (Cercado de Lima) y dejar San Juan de Lurigancho para después.

## Puntos a resolver

1. **`areas_distritos.csv` es lo más urgente.** La MLP de Flavia usa el área como entrada y el GA de Deivis también la necesita.
2. **Los 43 distritos, no solo los pilotos.** La semana 11 dice descargar los pilotos, pero la calibración de pesos compara contra los 43 UBIGEO. Sin los factores de los 43 no se puede ajustar. Las rutas sí se quedan en los pilotos.
3. **Pocos datos para calibrar: 43 filas y 6 pesos.** Estandarizar factores, mantener los pesos con el signo esperado y validar dejando un distrito fuera.
4. **La suma por distrito crece con su tamaño.** Un distrito con más calles suma más riesgo aunque cada calle no sea peligrosa. Probar qué tanto explica la cantidad de calles por sí sola y comentarlo en Evaluación y ética.
5. **Usar solo meses de entrenamiento (2018–2024) para el objetivo de calibración,** igual que la división temporal del proyecto.
6. **Calles de un sentido.** Usar grafo dirigido y la mayor componente fuertemente conexa; si no, una ruta puede no tener regreso a la comisaría.
7. **Heurística de A*.** Solo es válida si el riesgo está en [0, 1] y las distancias están en metros en ambos lados. Validarlo con un `assert`.
8. **Orden de visita.** Con 5 a 8 puntos, calcular la matriz de costos con A* y probar todas las permutaciones (máximo 8! = 40 320).

## Coordinar con el equipo

* Avisar que la carpeta cambió: `01_datos` ahora está en `notebooks/` y los CSV en `data/`.
* Confirmar los nombres de archivo y columnas del README.
* `data/raw/BD-delitos-denunciados-2025-12.csv` no aparece en la hoja de ruta: preguntar si alguien lo usará.
