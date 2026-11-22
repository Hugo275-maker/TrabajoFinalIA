/* Patrullero que recorre la ruta A* en la pestaña "Rutas de Patrullaje".
   main.js lo llama al cargar cada ruta: Patrullero.recorrer(mapa, capa, lineaRuta, puntos). */
const Patrullero = (() => {
  const DURACION_MS = 12000;
  const sinMovimiento = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let anim = 0, ultimo = null, control = null, marcador = null;

  const num = (v, dec = 1) => Number(v).toLocaleString("es-PE", { minimumFractionDigits: dec, maximumFractionDigits: dec });

  const icono = L.divIcon({
    className: "pt-patrullero", iconSize: [56, 56], iconAnchor: [28, 28],
    html: `<div class="pt-carro"><span class="pt-halo"></span>
      <svg viewBox="-24 -12 48 24" width="46" height="23" aria-hidden="true">
        <rect x="-21" y="-9" width="44" height="21" rx="6" fill="rgba(10,37,64,.25)"/>
        <rect x="-23" y="-10.5" width="5" height="3" fill="#0f172a"/><rect x="11" y="-10.5" width="5" height="3" fill="#0f172a"/>
        <rect x="-23" y="7.5" width="5" height="3" fill="#0f172a"/><rect x="11" y="7.5" width="5" height="3" fill="#0f172a"/>
        <rect x="-22" y="-9" width="44" height="18" rx="5.5" fill="#fbfdff" stroke="#0a2540" stroke-width="1.6"/>
        <rect x="-20" y="-7.6" width="40" height="2.6" fill="#0f6b3a"/><rect x="-20" y="5" width="40" height="2.6" fill="#0f6b3a"/>
        <rect x="5" y="-5" width="8" height="10" rx="1.6" fill="#0a2540"/>
        <rect x="-16" y="-5" width="5" height="10" rx="1.4" fill="#0a2540"/>
        <rect class="pt-luz-roja" x="-5" y="-4.6" width="4.5" height="4.6" rx="1"/>
        <rect class="pt-luz-azul" x="-5" y="0" width="4.5" height="4.6" rx="1"/>
        <rect x="20" y="-7" width="2" height="3" fill="#fde68a"/><rect x="20" y="4" width="2" height="3" fill="#fde68a"/>
      </svg></div>`,
  });

  function controles(mapa) {
    if (control) return;
    marcador = L.DomUtil.create("div", "pt-marcador", mapa.getContainer());
    marcador.hidden = true;
    control = L.control({ position: "topright" });
    control.onAdd = () => {
      const b = L.DomUtil.create("button", "pt-boton");
      b.type = "button";
      b.textContent = "Recorrer otra vez";
      L.DomEvent.disableClickPropagation(b);
      L.DomEvent.on(b, "click", () => ultimo && recorrer(...ultimo));
      return b;
    };
    control.addTo(mapa);
  }

  function detener() {
    cancelAnimationFrame(anim);
    if (marcador) marcador.hidden = true;
  }

  function recorrer(mapa, capa, linea, puntos) {
    detener();
    controles(mapa);
    ultimo = [mapa, capa, linea, puntos];
    const pts = (linea._rutaCompleta || (linea._rutaCompleta = linea.getLatLngs().slice()));
    if (pts.length < 2) return;
    capa.eachLayer((l) => l._esPatrullero && capa.removeLayer(l));

    // distancia recorrida al pasar por cada punto crítico, en el orden de visita
    const acum = [0];
    for (let i = 1; i < pts.length; i++) acum.push(acum[i - 1] + pts[i - 1].distanceTo(pts[i]));
    const total = acum[acum.length - 1];
    const orden = [...puntos].sort((a, b) => a.visita - b.visita);
    const llegada = new Map();
    let desde = 0;
    orden.forEach((p) => {
      const ll = L.latLng(p.lat, p.lon);
      let mejor = desde, dMin = Infinity;
      for (let i = desde; i < pts.length; i++) {
        const d = ll.distanceTo(pts[i]);
        if (d < dMin) { dMin = d; mejor = i; }
        if (dMin < 1 && d > 80) break;
      }
      llegada.set(p, acum[mejor]);
      desde = mejor;
    });
    const visitados = new Set();

    const carro = L.marker(pts[0], { icon: icono, interactive: false, keyboard: false, zIndexOffset: 1000 }).addTo(capa);
    carro._esPatrullero = true;

    function pintar(progreso) {
      const meta = total * progreso;
      let i = 1;
      while (i < pts.length && acum[i] <= meta) i++;
      const tramo = pts.slice(0, i);
      if (i < pts.length) {
        const f = (meta - acum[i - 1]) / (acum[i] - acum[i - 1] || 1);
        tramo.push(L.latLng(pts[i - 1].lat + (pts[i].lat - pts[i - 1].lat) * f, pts[i - 1].lng + (pts[i].lng - pts[i - 1].lng) * f));
      }
      linea.setLatLngs(tramo);
      const fin = tramo[tramo.length - 1];
      carro.setLatLng(fin);
      const a = mapa.latLngToLayerPoint(pts[Math.max(0, i - 1)]), b = mapa.latLngToLayerPoint(pts[Math.min(i, pts.length - 1)]);
      const el = carro.getElement();
      if (el) {
        if (a.distanceTo(b) > 0.01) el.firstChild.style.transform = `rotate(${Math.atan2(b.y - a.y, b.x - a.x) * 180 / Math.PI}deg)`;
        el.classList.toggle("en-marcha", progreso < 1);
      }
      orden.forEach((p) => {
        if (visitados.has(p) || meta < llegada.get(p)) return;
        visitados.add(p);
        if (progreso < 1) {
          const pulso = L.marker([p.lat, p.lon], {
            icon: L.divIcon({ className: "", iconSize: [24, 24], iconAnchor: [12, 12], html: '<span class="pt-pulso"></span>' }),
            interactive: false, keyboard: false,
          }).addTo(capa);
          pulso._esPatrullero = true;
          setTimeout(() => capa.removeLayer(pulso), 1000);
        }
      });
      const km = total / 1000;
      marcador.innerHTML = `<b>${num(km * progreso)}</b> de ${num(km)} km <span></span><b>${visitados.size}</b> de ${orden.length} puntos visitados`;
      marcador.hidden = progreso >= 1;
      if (progreso >= 1) capa.removeLayer(carro);
    }

    if (sinMovimiento) return pintar(1);
    const inicio = performance.now();
    const paso = (t) => {
      const f = Math.min(1, (t - inicio) / DURACION_MS);
      pintar(f);
      if (f < 1) anim = requestAnimationFrame(paso);
    };
    anim = requestAnimationFrame(paso);
  }

  return { recorrer, detener };
})();
