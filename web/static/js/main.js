let ESTADO = null;
let GEOJSON = null;
let DISTRITOS_ACTUAL = [];

let mapPred = null;
let layerPred = null;
let mapGA = null;
let layerGA = null;
let metricaPred = "d_esperadas";
let capaGA = "patrullas_ga";

let chartEstrategias = null;
let chartTop15 = null;
let chartConvergencia = null;

let mapRiesgo = null;
let marcaRiesgo = null;
let tramoRiesgo = null;
let mapRutas = null;
let capaRuta = null;
let ubigeoRuta = null;
const COLOR_NIVEL_DISTRITO = { bajo: "#fde68a", medio: "#fb923c", alto: "#dc2626" };
const NOMBRE_NIVEL = { bajo: "baja", medio: "media", alto: "alta" };

function colorSecuencial(valor, maxVal, paleta = "azul") {
  const r = maxVal > 0 ? Math.min(1, Math.max(0, valor / maxVal)) : 0;
  if (paleta === "verde") {
    const escala = ["#f0fdf4", "#bbf7d0", "#4ade80", "#16a34a", "#14532d"];
    return escala[Math.min(4, Math.floor(r * 5))];
  }
  if (paleta === "gris") {
    const escala = ["#f8fafc", "#cbd5e1", "#94a3b8", "#475569", "#1e293b"];
    return escala[Math.min(4, Math.floor(r * 5))];
  }
  const escala = ["#eff6ff", "#bfdbfe", "#60a5fa", "#2563eb", "#1e3a8a"];
  return escala[Math.min(4, Math.floor(r * 5))];
}

function colorBrecha(valor) {
  if (valor >= 25) return "#16a34a";
  if (valor >= 8) return "#86efac";
  if (valor > -8) return "#f1f5f9";
  if (valor > -25) return "#fde047";
  return "#dc2626";
}

async function iniciar() {
  const [resResumen, resGeo] = await Promise.all([
    fetch("/api/resumen"),
    fetch("/api/geojson"),
  ]);
  ESTADO = await resResumen.json();
  GEOJSON = await resGeo.json();
  DISTRITOS_ACTUAL = ESTADO.distritos.map((d) => ({ ...d }));

  renderResumen();
  renderTablaPrediccion(ESTADO.distritos);
  llenarSelectorRutas();
  renderTop15(DISTRITOS_ACTUAL);
  renderConvergencia(
    ESTADO.convergencia_inicial.mejor,
    ESTADO.convergencia_inicial.promedio,
    ESTADO.kpis.cobertura_renamu,
    ESTADO.kpis.cobertura_parejo
  );

  configurarEventos();
}

function formatoTitulo(texto) {
  const conectores = new Set(["de", "del", "la", "las", "los", "y"]);
  return texto
    .toLowerCase()
    .split(" ")
    .map((p, i) => (i > 0 && conectores.has(p) ? p : p.charAt(0).toUpperCase() + p.slice(1)))
    .join(" ");
}

function renderResumen() {
  const k = ESTADO.kpis;
  document.getElementById("kpi-denuncias").textContent = k.denuncias_esperadas_total.toLocaleString("es-PE");
  document.getElementById("kpi-flota").textContent = k.flota_total.toLocaleString("es-PE");
  document.getElementById("kpi-renamu").textContent = `${k.cobertura_renamu.toFixed(2)} %`;
  document.getElementById("kpi-ga").textContent = `${k.cobertura_ga.toFixed(2)} %`;
  const signo = k.ganancia_vs_renamu >= 0 ? "+" : "";
  document.getElementById("kpi-ganancia").textContent = `${signo}${k.ganancia_vs_renamu.toFixed(2)} pp frente a RENAMU 2026`;

  const ordenBrecha = [...ESTADO.distritos].sort((a, b) => b.brecha - a.brecha);
  const masReforzados = ordenBrecha
    .slice(0, 3)
    .map((d) => `<strong>${formatoTitulo(d.distrito)}</strong> (+${d.brecha})`)
    .join(", ");
  const masExcedentes = ordenBrecha
    .slice(-2)
    .reverse()
    .map((d) => `<strong>${formatoTitulo(d.distrito)}</strong> (${d.brecha})`)
    .join(" y ");

  document.getElementById("lista-hallazgos").innerHTML = `
    <li><strong>Mayor cobertura sin inversión en flota:</strong> con las mismas <strong>${k.flota_total.toLocaleString("es-PE")}</strong> patrullas operativas de RENAMU 2026, el Algoritmo Genético eleva la cobertura provincial de <strong>${k.cobertura_renamu.toFixed(2)} %</strong> a <strong>${k.cobertura_ga.toFixed(2)} %</strong> (<strong>${signo}${k.ganancia_vs_renamu.toFixed(2)} pp</strong>).</li>
    <li><strong>Focos críticos reforzados:</strong> ${masReforzados} reciben el mayor incremento de unidades debido a su alta densidad de robos y hurtos por km².</li>
    <li><strong>Reasignación de excedentes:</strong> se redistribuyen unidades desde distritos con menor cobertura marginal como ${masExcedentes}, manteniendo siempre el mínimo operativo en los 43 distritos.</li>
    <li><strong>Enrutamiento táctico (A*):</strong> los <strong>${ESTADO.distritos_con_ruta.length}</strong> distritos de peligrosidad media y alta tienen una ruta desde su comisaría que prioriza calles con índice de riesgo &gt; 0.5 con un alargamiento mínimo del recorrido.</li>
  `;

  const etiquetasBarrasPlugin = {
    id: "etiquetasBarrasResumen",
    afterDatasetsDraw(chart) {
      const { ctx } = chart;
      const meta = chart.getDatasetMeta(0);
      ctx.save();
      ctx.font = "700 12px -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
      ctx.textBaseline = "middle";
      meta.data.forEach((bar, i) => {
        const val = chart.data.datasets[0].data[i];
        const esOptimo = ESTADO.estrategias[i].tipo === "optimo";
        ctx.fillStyle = esOptimo ? "#059669" : "#334155";
        ctx.fillText(`${val.toFixed(2)} %`, bar.x + 8, bar.y);
      });
      ctx.restore();
    },
  };

  const ctx = document.getElementById("chart-estrategias");
  if (chartEstrategias) chartEstrategias.destroy();
  chartEstrategias = new Chart(ctx, {
    type: "bar",
    data: {
      labels: ESTADO.estrategias.map((e) => e.nombre),
      datasets: [{
        label: "Cobertura esperada F(x) (%)",
        data: ESTADO.estrategias.map((e) => e.cobertura),
        backgroundColor: ESTADO.estrategias.map((e) =>
          e.tipo === "optimo" ? "#059669" : e.tipo === "renamu" ? "#1e3a8a" : "#94a3b8"
        ),
        borderRadius: 6,
        barThickness: 26,
      }],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      layout: { padding: { right: 56 } },
      plugins: { legend: { display: false } },
      scales: {
        x: {
          min: 0,
          max: 75,
          ticks: { stepSize: 15, callback: (v) => `${v}%`, color: "#64748b", font: { size: 11 } },
          grid: { color: "#f1f5f9" },
        },
        y: {
          grid: { display: false },
          ticks: { color: "#0f172a", font: { size: 11.5, weight: "500" } },
        },
      },
    },
    plugins: [etiquetasBarrasPlugin],
  });
}

function renderTablaPrediccion(lista) {
  const tbody = document.getElementById("tbody-prediccion");
  const ordenada = [...lista].sort((a, b) => b.d_esperadas - a.d_esperadas);
  tbody.innerHTML = ordenada.map((d) => `
    <tr>
      <td><strong>${d.distrito}</strong><br><span class="muted">${d.ubigeo}</span></td>
      <td class="num">${d.area_km2.toFixed(2)}</td>
      <td class="num"><strong>${d.d_esperadas.toFixed(1)}</strong></td>
      <td class="num">${d.densidad.toFixed(2)}</td>
    </tr>
  `).join("");
}

function initMapaPrediccion() {
  if (!mapPred) {
    // zoomControl: false para reubicarlo abajo a la derecha
    mapPred = L.map("map-prediccion", { zoomControl: false }).setView([-12.05, -77.02], 10);
    
    // Cambiado a OpenStreetMap estándar para evitar marcas de API KEY de CartoDB
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap colaboradores",
    }).addTo(mapPred);
    
    L.control.zoom({ position: "bottomright" }).addTo(mapPred);
  }
  actualizarMapaPrediccion();
  setTimeout(() => mapPred.invalidateSize(), 150);
}

function actualizarMapaPrediccion() {
  if (!mapPred || !GEOJSON) return;
  if (layerPred) mapPred.removeLayer(layerPred);

  const porUbigeo = Object.fromEntries(ESTADO.distritos.map((d) => [d.ubigeo, d]));
  const maxVal = Math.max(...ESTADO.distritos.map((d) => d[metricaPred]));

  layerPred = L.geoJSON(GEOJSON, {
    style: (feat) => {
      const u = String(feat.properties.UBIGEO || "").padStart(6, "0");
      const info = porUbigeo[u];
      const val = info ? info[metricaPred] : 0;
      return {
        fillColor: colorSecuencial(val, maxVal, "azul"),
        weight: 1.2,
        color: "#475569",
        fillOpacity: 0.65,
      };
    },
    onEachFeature: (feat, layer) => {
      const u = String(feat.properties.UBIGEO || "").padStart(6, "0");
      const d = porUbigeo[u];
      if (d) {
        layer.bindTooltip(
          `<strong>${d.distrito}</strong> (${u})<br>Denuncias esp.: <strong>${d.d_esperadas}</strong><br>Área: ${d.area_km2} km² · Densidad: ${d.densidad}/km²`,
          { sticky: true }
        );
      }
    },
  }).addTo(mapPred);
}

function initMapaGA() {
  if (!mapGA) {
    mapGA = L.map("map-ga", { zoomControl: false }).setView([-12.05, -77.02], 10);
    
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap colaboradores",
    }).addTo(mapGA);
    
    L.control.zoom({ position: "bottomright" }).addTo(mapGA);
  }
  actualizarMapaGA();
  setTimeout(() => mapGA.invalidateSize(), 150);
}

function actualizarMapaGA() {
  if (!mapGA || !GEOJSON) return;
  if (layerGA) mapGA.removeLayer(layerGA);

  const porUbigeo = Object.fromEntries(DISTRITOS_ACTUAL.map((d) => [d.ubigeo, d]));
  const maxVal = Math.max(...DISTRITOS_ACTUAL.map((d) => d[capaGA] || 0));

  layerGA = L.geoJSON(GEOJSON, {
    style: (feat) => {
      const u = String(feat.properties.UBIGEO || "").padStart(6, "0");
      const info = porUbigeo[u];
      const val = info ? info[capaGA] : 0;
      let fill = "#f1f5f9";
      if (capaGA === "brecha") fill = colorBrecha(val);
      else if (capaGA === "patrullas_ga") fill = colorSecuencial(val, maxVal, "verde");
      else fill = colorSecuencial(val, maxVal, "gris");
      return { fillColor: fill, weight: 1.2, color: "#475569", fillOpacity: 0.72 };
    },
    onEachFeature: (feat, layer) => {
      const u = String(feat.properties.UBIGEO || "").padStart(6, "0");
      const d = porUbigeo[u];
      if (d) {
        const signo = d.brecha > 0 ? `+${d.brecha}` : `${d.brecha}`;
        layer.bindTooltip(
          `<strong>${d.distrito}</strong><br>GA Óptimo: <strong>${d.patrullas_ga}</strong> patrullas<br>RENAMU: ${d.patrullas_renamu} · Brecha: <strong>${signo}</strong><br>Cobertura GA: ${d.cobertura_ga}%`,
          { sticky: true }
        );
      }
    },
  }).addTo(mapGA);
}

function renderTop15(lista) {
  const top15 = [...lista].sort((a, b) => b.patrullas_ga - a.patrullas_ga).slice(0, 15).reverse();
  const ctx = document.getElementById("chart-top15");
  if (chartTop15) chartTop15.destroy();
  chartTop15 = new Chart(ctx, {
    type: "bar",
    data: {
      labels: top15.map((d) => d.distrito),
      datasets: [
        { label: "Algoritmo Genético (Óptimo)", data: top15.map((d) => d.patrullas_ga), backgroundColor: "#14532d", borderRadius: 3, barPercentage: 0.8 },
        { label: "Uso Real RENAMU", data: top15.map((d) => d.patrullas_renamu), backgroundColor: "#94a3b8", borderRadius: 3, barPercentage: 0.8 },
      ],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "bottom", labels: { boxWidth: 12, font: { size: 10 } } }
      },
      scales: {
        x: { grid: { color: "#e2e8f0" }, ticks: { font: { size: 9.5 } } },
        y: { grid: { display: false }, ticks: { font: { size: 9.5 } } },
      },
    },
  });
}

function renderConvergencia(mejor, promedio, fitRenamu, fitParejo) {
  if (!mejor || mejor.length === 0) return;
  const ctx = document.getElementById("chart-convergencia");
  if (chartConvergencia) chartConvergencia.destroy();

  const etiquetas = mejor.map((_, i) => i + 1);
  const fitFinalGA = mejor[mejor.length - 1];
  const gananciaPP = (fitFinalGA - fitRenamu).toFixed(2);
  const signo = fitFinalGA >= fitRenamu ? "+" : "";

  const todosValores = [...mejor, ...promedio, fitRenamu, fitParejo];
  const yMin = Math.max(0, Math.floor(Math.min(...todosValores) - 2));
  const yMax = Math.min(100, Math.ceil(Math.max(...todosValores) + 3));

  // Plugin propio para dibujar etiquetas directas y la flecha de ganancia (proyector-ready)
  const etiquetasExposicionPlugin = {
    id: "etiquetasExposicion",
    afterDatasetsDraw(chart) {
      const { ctx, chartArea, scales } = chart;
      if (!chartArea || !scales.y) return;

      const xFin = chartArea.right;
      const yGA = scales.y.getPixelForValue(fitFinalGA);
      const yRen = scales.y.getPixelForValue(fitRenamu);
      const yUni = scales.y.getPixelForValue(fitParejo);

      ctx.save();

      // 1. Punto destacado al final de la curva óptima del GA
      ctx.beginPath();
      ctx.arc(xFin, yGA, 5, 0, Math.PI * 2);
      ctx.fillStyle = "#059669";
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = "#ffffff";
      ctx.stroke();

      // 2. Indicador vertical de ganancia entre RENAMU y GA (si hay espacio)
      if (Math.abs(yRen - yGA) > 26) {
        const xFlecha = xFin - 26;
        ctx.strokeStyle = "#059669";
        ctx.lineWidth = 2;
        ctx.setLineDash([]);
        ctx.beginPath();
        ctx.moveTo(xFlecha, yRen - 3);
        ctx.lineTo(xFlecha, yGA + 4);
        ctx.stroke();

        // Punta de flecha superior
        ctx.beginPath();
        ctx.moveTo(xFlecha - 4, yGA + 10);
        ctx.lineTo(xFlecha, yGA + 3);
        ctx.lineTo(xFlecha + 4, yGA + 10);
        ctx.stroke();

        // Etiqueta de ganancia en medio de la flecha
        const yMid = (yGA + yRen) / 2;
        const txtGain = `${signo}${gananciaPP} pp`;
        ctx.font = "700 12px -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
        const w = ctx.measureText(txtGain).width + 12;
        ctx.fillStyle = "#ecfdf5";
        ctx.strokeStyle = "#059669";
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.roundRect(xFlecha - w - 8, yMid - 11, w, 22, 4);
        ctx.fill();
        ctx.stroke();

        ctx.fillStyle = "#065f46";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(txtGain, xFlecha - w / 2 - 8, yMid);
      }

      // 3. Etiquetas fijas a la derecha (con ajuste anti-solapamiento)
      const items = [
        { y: yGA, texto: `GA: ${fitFinalGA.toFixed(2)}%`, bg: "#059669", fg: "#ffffff" },
        { y: yRen, texto: `RENAMU: ${fitRenamu.toFixed(2)}%`, bg: "#b45309", fg: "#ffffff" },
        { y: yUni, texto: `Uniforme: ${fitParejo.toFixed(2)}%`, bg: "#475569", fg: "#ffffff" },
      ].sort((a, b) => a.y - b.y);

      for (let i = 1; i < items.length; i++) {
        if (items[i].y - items[i - 1].y < 24) {
          items[i].y = items[i - 1].y + 24;
        }
      }

      ctx.font = "700 11.5px -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
      ctx.textAlign = "left";
      ctx.textBaseline = "middle";

      items.forEach((it) => {
        const w = ctx.measureText(it.texto).width + 14;
        ctx.fillStyle = it.bg;
        ctx.beginPath();
        ctx.roundRect(xFin + 10, it.y - 11, w, 22, 4);
        ctx.fill();
        ctx.fillStyle = it.fg;
        ctx.fillText(it.texto, xFin + 17, it.y);
      });

      ctx.restore();
    },
  };

  chartConvergencia = new Chart(ctx, {
    type: "line",
    data: {
      labels: etiquetas,
      datasets: [
        {
          label: `Mejor individuo GA (${fitFinalGA.toFixed(2)}%)`,
          data: mejor,
          borderColor: "#059669",
          backgroundColor: "rgba(5, 150, 105, 0.08)",
          fill: false,
          borderWidth: 3.4,
          pointRadius: 0,
          pointHoverRadius: 5,
          tension: 0.15,
        },
        {
          label: "Promedio de la población",
          data: promedio,
          borderColor: "#0a2540",
          backgroundColor: "#0a2540",
          borderDash: [7, 4],
          borderWidth: 2.3,
          pointRadius: 0,
          pointHoverRadius: 4,
          tension: 0.15,
        },
        {
          label: `Realidad RENAMU (${fitRenamu.toFixed(2)}%)`,
          data: etiquetas.map(() => fitRenamu),
          borderColor: "#b45309",
          backgroundColor: "#b45309",
          borderDash: [9, 5],
          borderWidth: 2.5,
          pointRadius: 0,
        },
        {
          label: `Reparto Uniforme (${fitParejo.toFixed(2)}%)`,
          data: etiquetas.map(() => fitParejo),
          borderColor: "#475569",
          backgroundColor: "#475569",
          borderDash: [4, 4],
          borderWidth: 2.1,
          pointRadius: 0,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      layout: {
        padding: { top: 8, right: 145, bottom: 4, left: 4 },
      },
      plugins: {
        legend: {
          position: "top",
          labels: {
            usePointStyle: true,
            pointStyle: "line",
            boxWidth: 26,
            padding: 18,
            color: "#0f172a",
            font: { size: 12, weight: "600" },
          },
        },
        tooltip: {
          callbacks: {
            label: (c) => `${c.dataset.label.split("(")[0].trim()}: ${Number(c.parsed.y).toFixed(2)}%`,
          },
        },
      },
      scales: {
        x: {
          title: {
            display: true,
            text: "Generación (G)",
            color: "#0f172a",
            font: { size: 12.5, weight: "600" },
          },
          grid: { display: false },
          ticks: {
            maxTicksLimit: 12,
            color: "#334155",
            font: { size: 11.5, weight: "500" },
          },
        },
        y: {
          min: yMin,
          max: yMax,
          title: {
            display: true,
            text: "Cobertura Global F(x) (%)",
            color: "#0f172a",
            font: { size: 12.5, weight: "600" },
          },
          grid: { color: "#e2e8f0" },
          ticks: {
            color: "#334155",
            font: { size: 11.5, weight: "500" },
            callback: (v) => `${v}%`,
          },
        },
      },
    },
    plugins: [etiquetasExposicionPlugin],
  });
}

function escaparHtml(texto) {
  return String(texto ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function capaBase(mapa) {
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap colaboradores",
  }).addTo(mapa);
  L.control.zoom({ position: "bottomright" }).addTo(mapa);
}

/* ---------- Riesgo por calle (clic en el mapa) ---------- */

async function consultarRiesgo(lat, lon) {
  const resp = await fetch(`/api/riesgo-punto?lat=${lat.toFixed(6)}&lon=${lon.toFixed(6)}`);
  if (!resp.ok) throw new Error("fuera de Lima");
  return resp.json();
}

function lugaresCercanos(c) {
  const partes = [];
  if (c.paraderos) partes.push(`${c.paraderos} paradero${c.paraderos > 1 ? "s" : ""}`);
  if (c.mercados) partes.push(`${c.mercados} mercado${c.mercados > 1 ? "s" : ""}`);
  if (c.bancos_cajeros) partes.push(`${c.bancos_cajeros} ${c.bancos_cajeros > 1 ? "bancos o cajeros" : "banco o cajero"}`);
  return partes;
}

function veredicto(res) {
  const c = res.calle;
  const d = res.distrito;
  const textoDistrito = d
    ? `${formatoTitulo(d.distrito)} tiene peligrosidad <strong>${NOMBRE_NIVEL[d.nivel] || d.nivel}</strong> (${d.densidad} denuncias esperadas por km² el próximo mes).`
    : "";
  if (!c) {
    return { nivel: d ? d.nivel : "", texto: `No hay calles registradas a menos de 150 m de este punto. ${textoDistrito}` };
  }
  const lugares = lugaresCercanos(c);
  const cerca = lugares.length
    ? `Tiene cerca (a menos de 100 m) ${lugares.join(", ")}.`
    : "No tiene paraderos, mercados ni bancos a menos de 100 m.";
  const frases = {
    alto: "<strong>Calle de riesgo alto.</strong> Está entre el 3 % de calles de Lima con más factores de riesgo: es prioridad para el patrullaje.",
    medio: "<strong>Calle de riesgo medio.</strong> Tiene más factores de riesgo que 9 de cada 10 calles de Lima.",
    bajo: "<strong>Calle de riesgo bajo.</strong> Tiene pocos o ningún factor de riesgo cerca.",
  };
  return { nivel: c.nivel, texto: `${frases[c.nivel]} ${cerca} ${textoDistrito}` };
}

function htmlPanelRiesgo(res) {
  const c = res.calle;
  const d = res.distrito;
  if (!d && !c) return `<p class="muted">Este punto está fuera de Lima Metropolitana.</p>`;
  const v = veredicto(res);
  let html = `<div class="veredicto ${v.nivel}">${v.texto}</div>`;
  if (c) {
    html += `
      <div>
        <div class="fila-dato"><span>Calle</span><strong>${escaparHtml(c.nombre)}</strong></div>
        <div class="fila-dato"><span>Índice de riesgo</span><span><strong>${c.riesgo.toFixed(2)}</strong> / 1 · <span class="nivel ${c.nivel}">${c.nivel}</span></span></div>
        <div class="barra-riesgo" aria-hidden="true"><span class="marca" style="left:${Math.min(100, c.riesgo * 100)}%"></span></div>
        <div class="fila-dato"><span>Paraderos · mercados · bancos (100 m)</span><strong>${c.paraderos} · ${c.mercados} · ${c.bancos_cajeros}</strong></div>
        <div class="fila-dato"><span>Distancia al punto</span><span>${Math.round(c.distancia_m)} m</span></div>
      </div>`;
  }
  if (d) {
    html += `
      <div>
        <div class="fila-dato"><span>Distrito</span><strong>${formatoTitulo(d.distrito)} (${d.ubigeo})</strong></div>
        <div class="fila-dato"><span>Peligrosidad del distrito</span><span class="nivel ${d.nivel}">${NOMBRE_NIVEL[d.nivel] || d.nivel}</span></div>
        <div class="fila-dato"><span>Denuncias esperadas (mes sig.)</span><strong>${d.d_esperadas}</strong></div>
        <div class="fila-dato"><span>Patrullas asignadas por el GA</span><strong>${d.patrullas_ga}</strong></div>
      </div>`;
    if (d.con_ruta) {
      html += `<button class="btn-secondary" type="button" data-ver-ruta="${d.ubigeo}">Ver la ruta de patrullaje de ${formatoTitulo(d.distrito)}</button>`;
    }
  }
  return html;
}

function resaltarTramo(mapa, calle, capaPrevia) {
  if (capaPrevia) mapa.removeLayer(capaPrevia);
  if (!calle) return null;
  const colores = { alto: "#7f1d1d", medio: "#c2410c", bajo: "#15803d" };
  return L.polyline(calle.coords, { color: colores[calle.nivel], weight: 8, opacity: 0.9, interactive: false }).addTo(mapa);
}

function initMapaRiesgo() {
  if (!mapRiesgo) {
    mapRiesgo = L.map("map-riesgo", { zoomControl: false }).setView([-12.06, -77.03], 12);
    capaBase(mapRiesgo);
    const porUbigeo = Object.fromEntries(ESTADO.distritos.map((d) => [d.ubigeo, d]));
    L.geoJSON(GEOJSON, {
      style: (feat) => {
        const d = porUbigeo[String(feat.properties.UBIGEO || "").padStart(6, "0")];
        return { fillColor: COLOR_NIVEL_DISTRITO[d?.nivel] || "#e2e8f0", fillOpacity: 0.28, weight: 1, color: "#475569" };
      },
      onEachFeature: (feat, layer) => {
        const d = porUbigeo[String(feat.properties.UBIGEO || "").padStart(6, "0")];
        if (d) layer.bindTooltip(`<strong>${formatoTitulo(d.distrito)}</strong><br>Peligrosidad ${NOMBRE_NIVEL[d.nivel] || d.nivel}`, { sticky: true });
      },
    }).addTo(mapRiesgo);

    mapRiesgo.on("click", async (e) => {
      const panel = document.getElementById("panel-riesgo");
      panel.innerHTML = `<p class="muted">Buscando la calle más cercana...</p>`;
      if (marcaRiesgo) mapRiesgo.removeLayer(marcaRiesgo);
      marcaRiesgo = L.circleMarker(e.latlng, { radius: 6, color: "#0f172a", weight: 2, fillColor: "#fff", fillOpacity: 1, interactive: false }).addTo(mapRiesgo);
      try {
        const res = await consultarRiesgo(e.latlng.lat, e.latlng.lng);
        tramoRiesgo = resaltarTramo(mapRiesgo, res.calle, tramoRiesgo);
        marcaRiesgo.bringToFront();
        panel.innerHTML = htmlPanelRiesgo(res);
      } catch (err) {
        tramoRiesgo = resaltarTramo(mapRiesgo, null, tramoRiesgo);
        panel.innerHTML = `<p class="muted">Este punto está fuera de Lima Metropolitana.</p>`;
      }
    });

    document.getElementById("panel-riesgo").addEventListener("click", (e) => {
      const btn = e.target.closest("[data-ver-ruta]");
      if (!btn) return;
      document.getElementById("select-ruta").value = btn.dataset.verRuta;
      document.querySelector('.tab-btn[data-tab="rutas"]').click();
    });
  }
  setTimeout(() => mapRiesgo.invalidateSize(), 150);
}

/* ---------- Rutas por distrito ---------- */

function llenarSelectorRutas() {
  const select = document.getElementById("select-ruta");
  const conRuta = new Set(ESTADO.distritos_con_ruta);
  const grupos = [["alto", "Peligrosidad alta"], ["medio", "Peligrosidad media"]];
  select.innerHTML = grupos.map(([nivel, etiqueta]) => {
    const opciones = ESTADO.distritos
      .filter((d) => conRuta.has(d.ubigeo) && d.nivel === nivel)
      .sort((a, b) => a.distrito.localeCompare(b.distrito))
      .map((d) => `<option value="${d.ubigeo}">${formatoTitulo(d.distrito)} (${d.ubigeo})</option>`)
      .join("");
    return opciones ? `<optgroup label="${etiqueta}">${opciones}</optgroup>` : "";
  }).join("");
  if (conRuta.has("150101")) select.value = "150101";
}

function renderTablaRutas(ubigeo, ruta) {
  document.getElementById("tbody-rutas").innerHTML = ruta.resumen.map((r) => `
    <tr>
      <td class="num"><strong>${r.beta.toFixed(1)}</strong></td>
      <td class="num">${r.km.toFixed(3)}</td>
      <td class="num">${r.riesgo_medio.toFixed(3)}</td>
      <td class="num"><strong>${r.pct_riesgo_alto.toFixed(2)}%</strong></td>
      <td class="num">${r.segundos.toFixed(3)}</td>
    </tr>
  `).join("");
  const d = ruta.distrito;
  document.getElementById("info-ruta").innerHTML =
    `<strong>${formatoTitulo(d.distrito)}</strong> · peligrosidad ${NOMBRE_NIVEL[d.nivel] || d.nivel} · sale de <strong>${escaparHtml(ruta.comisaria)}</strong> y visita ${ruta.puntos.length} puntos críticos en el orden numerado.`;
}

async function cargarRuta(ubigeo) {
  ubigeoRuta = ubigeo;
  const [respRuta, respCalles] = await Promise.all([
    fetch(`/api/ruta/${ubigeo}`),
    fetch(`/api/riesgo-distrito/${ubigeo}`),
  ]);
  if (!respRuta.ok || ubigeo !== ubigeoRuta) return;
  const ruta = await respRuta.json();
  const calles = respCalles.ok ? await respCalles.json() : [];

  if (capaRuta) mapRutas.removeLayer(capaRuta);
  capaRuta = L.layerGroup().addTo(mapRutas);
  const lienzo = L.canvas({ padding: 0.3 });
  calles.forEach((t) => {
    L.polyline(t.c, {
      renderer: lienzo,
      color: t.r >= 0.5 ? "#7f1d1d" : "#f59e0b",
      weight: t.r >= 0.5 ? 3 : 2,
      opacity: 0.75,
      interactive: false,
    }).addTo(capaRuta);
  });
  L.polyline(ruta.rutas["0"], { color: "#555555", weight: 4, opacity: 0.8, dashArray: "8" })
    .bindTooltip("Ruta más corta (β = 0)", { sticky: true }).addTo(capaRuta);
  const principal = L.polyline(ruta.rutas["2"], { color: "#d62728", weight: 5, opacity: 0.85 })
    .bindTooltip("Ruta con riesgo (β = 2)", { sticky: true }).addTo(capaRuta);
  ruta.puntos.forEach((p) => {
    L.marker([p.lat, p.lon], {
      icon: L.divIcon({
        className: "",
        html: `<span style="display:flex;align-items:center;justify-content:center;width:20px;height:20px;border-radius:50%;background:#e4572e;border:2px solid #fff;color:#fff;font:700 11px sans-serif;box-shadow:0 1px 3px rgba(0,0,0,.4)">${p.visita}</span>`,
        iconSize: [24, 24],
        iconAnchor: [12, 12],
      }),
    }).bindTooltip(`Punto crítico, visita ${p.visita}<br>Riesgo de la esquina: ${p.riesgo.toFixed(2)}`).addTo(capaRuta);
  });
  L.marker(ruta.salida).bindTooltip(`Salida: ${escaparHtml(ruta.comisaria)}`).addTo(capaRuta);

  mapRutas.fitBounds(principal.getBounds(), { padding: [30, 30] });
  renderTablaRutas(ubigeo, ruta);
}

function initMapaRutas() {
  if (!mapRutas) {
    mapRutas = L.map("map-rutas", { zoomControl: false }).setView([-12.05, -77.03], 13);
    capaBase(mapRutas);
    mapRutas.on("click", async (e) => {
      const popup = L.popup().setLatLng(e.latlng).setContent("Buscando la calle más cercana...").openOn(mapRutas);
      try {
        const res = await consultarRiesgo(e.latlng.lat, e.latlng.lng);
        const c = res.calle;
        popup.setContent(c
          ? `<div class="popup-riesgo"><strong>${escaparHtml(c.nombre)}</strong><br>Riesgo: <strong>${c.riesgo.toFixed(2)}</strong> <span class="nivel ${c.nivel}">${c.nivel}</span><br>Paraderos · mercados · bancos: ${c.paraderos} · ${c.mercados} · ${c.bancos_cajeros}</div>`
          : `<div class="popup-riesgo">No hay calles a menos de 150 m.</div>`);
      } catch (err) {
        popup.setContent(`<div class="popup-riesgo">Fuera de Lima Metropolitana.</div>`);
      }
    });
  }
  setTimeout(() => {
    mapRutas.invalidateSize();
    const u = document.getElementById("select-ruta").value;
    if (u && u !== ubigeoRuta) cargarRuta(u);
  }, 150);
}

function configurarEventos() {
  // Navegación entre pestañas
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      const tab = btn.dataset.tab;
      document.getElementById(`tab-${tab}`).classList.add("active");
      if (tab === "prediccion") initMapaPrediccion();
      if (tab === "asignacion") initMapaGA();
      if (tab === "riesgo") initMapaRiesgo();
      if (tab === "rutas") initMapaRutas();
    });
  });

  // Buscador de distritos
  document.getElementById("buscar-distrito").addEventListener("input", (e) => {
    const q = e.target.value.trim().toLowerCase();
    const filtrados = ESTADO.distritos.filter(
      (d) => d.distrito.toLowerCase().includes(q) || d.ubigeo.includes(q)
    );
    renderTablaPrediccion(filtrados);
  });

  // Toggle mapa predicción
  document.querySelectorAll("#toggle-pred-metric .seg-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#toggle-pred-metric .seg-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      metricaPred = btn.dataset.metric;
      actualizarMapaPrediccion();
    });
  });

  // Toggle mapa GA
  document.querySelectorAll("#toggle-ga-map .seg-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#toggle-ga-map .seg-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      capaGA = btn.dataset.layer;
      actualizarMapaGA();
    });
  });

  // Selector de distrito en rutas
  document.getElementById("select-ruta").addEventListener("change", (e) => {
    if (mapRutas) cargarRuta(e.target.value);
  });

  // Sliders del simulador
  const slFlota = document.getElementById("input-flota");
  const slAlpha = document.getElementById("input-alpha");
  const slEpochs = document.getElementById("input-epochs");
  slFlota.addEventListener("input", () => (document.getElementById("lbl-flota").textContent = slFlota.value));
  slAlpha.addEventListener("input", () => (document.getElementById("lbl-alpha").textContent = Number(slAlpha.value).toFixed(2)));
  slEpochs.addEventListener("input", () => (document.getElementById("lbl-epochs").textContent = slEpochs.value));

  document.getElementById("btn-simular").addEventListener("click", async () => {
    const status = document.getElementById("sim-status");
    const btn = document.getElementById("btn-simular");
    btn.disabled = true;
    status.textContent = "Ejecutando Algoritmo Genético en el servidor...";

    const resp = await fetch("/api/simular-ga", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        flota: Number(slFlota.value),
        alpha: Number(slAlpha.value),
        epochs: Number(slEpochs.value),
      }),
    });
    const sim = await resp.json();

    DISTRITOS_ACTUAL = ESTADO.distritos.map((orig) => {
      const m = sim.detalle.find((x) => x.ubigeo === orig.ubigeo);
      return m ? { ...orig, ...m } : orig;
    });

    actualizarMapaGA();
    renderTop15(DISTRITOS_ACTUAL);
    renderConvergencia(sim.historial_mejor, sim.historial_promedio, sim.fitness_renamu, sim.fitness_parejo);

    const signo = sim.ganancia_vs_renamu >= 0 ? "+" : "";
    status.innerHTML = `Simulación completada (P=${sim.flota}, α=${sim.alpha}, G=${sim.epochs}): <strong>GA = ${sim.fitness_ga}%</strong> vs. RENAMU = ${sim.fitness_renamu}% (<strong>${signo}${sim.ganancia_vs_renamu} pp</strong>).`;
    btn.disabled = false;
  });

  document.getElementById("btn-reset").addEventListener("click", () => {
    slFlota.value = ESTADO.kpis.flota_total;
    slAlpha.value = ESTADO.kpis.alpha;
    slEpochs.value = 120;
    document.getElementById("lbl-flota").textContent = slFlota.value;
    document.getElementById("lbl-alpha").textContent = Number(slAlpha.value).toFixed(2);
    document.getElementById("lbl-epochs").textContent = slEpochs.value;

    DISTRITOS_ACTUAL = ESTADO.distritos.map((d) => ({ ...d }));
    actualizarMapaGA();
    renderTop15(DISTRITOS_ACTUAL);
    renderConvergencia(
      ESTADO.convergencia_inicial.mejor,
      ESTADO.convergencia_inicial.promedio,
      ESTADO.kpis.cobertura_renamu,
      ESTADO.kpis.cobertura_parejo
    );
    document.getElementById("sim-status").innerHTML = "Restaurada la solución oficial de <code>reparto_patrullas.csv</code>.";
  });
}

iniciar();