# Revisión de los datos de OpenStreetMap (10 de noviembre de 2026)

## Fuente

* **Calles y lugares:** extracto de Perú de Geofabrik con fecha del 8 de noviembre de 2026 (`data/osm/fuente/peru-latest.osm.pbf`), procesado con `src/osm_desde_pbf.py`. Overpass dejó de aceptar conexiones desde esta PC el 9 de noviembre a las 22:48.
* **Límites y áreas:** Nominatim (`src/descargar_limites.py`).
* **Calles:** filtro `drive` de osmnx (calles por las que puede pasar un auto), recortadas a los 43 distritos.

| Dato | Valor |
|---|---|
| Esquinas (nodos) | 137 896 |
| Tramos (aristas) | 360 845 |
| Lugares en los 43 distritos | 4 921 |

## Comparación con Overpass (10 distritos, 150101 a 150110)

Mismos tramos (±2 por distrito), kilómetros de calle a menos de 1 % (9 890 frente a 9 910 km), mismo porcentaje con alumbrado y lugares iguales o con 1 de diferencia por categoría. Las diferencias se explican por un día de cambios en OSM y por los tramos del borde. **El extracto de Geofabrik equivale a lo que da Overpass.**

## Lugares por categoría

| Categoría | Cantidad |
|---|---|
| Paraderos | 2 173 |
| Bancos y cajeros | 1 236 |
| Mercados | 900 |
| Bares, pubs y discotecas | 316 |
| `amenity=police` | 296 |

Distritos con alguna categoría en 0: Chaclacayo, Cieneguilla, El Agustino, La Molina, Pachacámac, Pucusana, Punta Hermosa, Punta Negra, San Bartolo y Santa María del Mar. Casi todos en 0 bares. **316 bares para toda Lima es muy poco: OSM no los tiene todos.** Va como limitación en Evaluación y ética.

## Alumbrado en los pilotos

| Piloto | Tramos | Con etiqueta `lit` |
|---|---|---|
| 150101 Cercado de Lima | 5 530 | 3,7 % |
| 150132 San Juan de Lurigancho | 37 965 | 2,2 % |

**Muy bajo.** Según la hoja de ruta, se quita el factor de alumbrado. Hay que avisarlo al equipo y explicarlo en el informe.

## Comisarías en los pilotos

`amenity=police` no son solo comisarías: también incluye serenazgo, DIRINCRI, direcciones y oficinas de la PNP.

* **Cercado de Lima:** 26 registros, 13 con "Comisaría" en el nombre.
* **San Juan de Lurigancho:** 24 registros, 12 con "Comisaría" en el nombre (Canto Rey aparece dos veces, la comisaría y la de la familia).

Decisiones pendientes:
1. **Salida de la ruta A\*:** usar solo las que dicen "Comisaría", verificadas contra la lista de la PNP.
2. **Factor de riesgo "cerca de comisaría":** usar solo comisarías o toda presencia policial y de serenazgo. Lo segundo también es razonable, pero hay que decidirlo y explicarlo.

### Cercado de Lima (150101), con "Comisaría" en el nombre

| Nombre en OSM | Lat | Lon |
|---|---|---|
| Comisaría Mirones Bajo | -12.03680 | -77.07556 |
| Comisaría Monserrate | -12.04137 | -77.03925 |
| Comisaría PNP Alfonso Ugarte | -12.05656 | -77.04117 |
| Comisaría PNP Conde de la Vega | -12.03834 | -77.05318 |
| Comisaría PNP Cotabambas | -12.05805 | -77.03415 |
| Comisaría PNP Mirones Alto | -12.05121 | -77.06746 |
| Comisaría PNP Palomino | -12.06011 | -77.07255 |
| Comisaría PNP Petit Thouars | -12.06887 | -77.03534 |
| Comisaría PNP San Andrés | -12.05115 | -77.02356 |
| Comisaría PNP Unidad Vecinal Nº 3 | -12.05140 | -77.08198 |
| Comisaría PNP de la familia Bertha Gonzales Posada Eyzaguirre | -12.05784 | -77.03419 |
| Puesto de auxilio | -12.05871 | -77.00892 |
| (sin nombre) | -12.04414 | -77.05076 |

Otros 13 registros son unidades especializadas o serenazgo (DIRINCRI, DIPROVE, Región Policial Lima, Serenazgo de Lima, etc.).

### San Juan de Lurigancho (150132), con "Comisaría" en el nombre

| Nombre en OSM | Lat | Lon |
|---|---|---|
| Comisaría Caja de Agua | -12.02718 | -77.01504 |
| Comisaría PNP 10 de Octubre | -11.94455 | -76.98841 |
| Comisaría PNP Bayovar | -11.95223 | -76.99168 |
| Comisaría PNP Canto Rey | -11.97541 | -76.99605 |
| Comisaría PNP La Huayrona | -11.99399 | -77.00691 |
| Comisaría PNP San Antonio Jicamarca | -11.92557 | -76.96141 |
| Comisaría PNP San Juan de Lurigancho Mariscal Cáceres | -11.94922 | -76.98084 |
| Comisaría PNP Santa Elizabeth | -11.98406 | -77.01512 |
| Comisaría PNP Zárate | -12.02689 | -77.00132 |
| Comisaría PNP de la familia Canto Rey | -11.97582 | -76.99571 |
| Auxilio Policial Rápido Azcarrunz Alto (Comisaría Zárate) | -12.01305 | -76.99676 |
| Policía Nacional del Perú | -11.98075 | -77.00570 |
| (sin nombre) | -11.99730 | -76.99620 |

Otros 11 registros son módulos de serenazgo, DIVINCRI y puestos de auxilio rápido.

**Pendiente de Hugo:** comparar estas listas con la de comisarías de la PNP.
