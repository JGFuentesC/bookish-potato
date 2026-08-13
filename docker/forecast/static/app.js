"use strict";

// La API se sirve en el mismo origen que este frontend (FastAPI -> /static).
// Usamos rutas relativas SIEMPRE. Fallback comentado por si se abre desde otro puerto:
// const BASE_API = ""; // mismo origen
// const BASE_API = "http://127.0.0.1:8090"; // solo como fallback manual, mantener vacío en producción
const BASE_API = "";

const estado = {
  sim: "AAPL",
  lista: "",          // SP500 | NASDAQ | AMEX | "" (vacío = todas)
  sector: "",         // sector seleccionado o ""
  desde: "",
  hasta: "",
  enCarga: false,
  cargaToken: 0,
};

// Ventana de observación por defecto (días naturales) para que el forecast
// de 10 días sea claramente visible al final del gráfico. El usuario la puede
// ampliar desde los inputs de fecha.
const DIAS_OBSERVACION = 180;

const mapaSimbolos = new Map(); // simbolo -> {simbolo, nombre, sector, listas}
let ultimaFecha = null;          // último día hábil conocido (de la historia)

const $ = (id) => document.getElementById(id);

/* ------------------------------------------------------------------ */
/*  Utilidades                                                         */
/* ------------------------------------------------------------------ */

// Token de API inyectado en el HTML en tiempo de servido (nunca en la
// imagen). Vacío en dev local / sin protección.
const _API_TOKEN = (typeof window !== "undefined" && window.__API_TOKEN__) || "";

function _conAuth(opciones = {}) {
  if (!_API_TOKEN) return opciones;
  const headers = Object.assign({}, opciones.headers);
  headers["Authorization"] = "Bearer " + _API_TOKEN;
  return Object.assign({}, opciones, { headers });
}

async function fetchJSON(url, opciones = {}) {
  const res = await fetch(url, _conAuth(opciones));
  if (!res.ok) {
    let detalle = `HTTP ${res.status}`;
    try {
      const texto = await res.text();
      if (texto && texto.trim()) detalle = texto.trim().slice(0, 300);
    } catch (_) { /* sin cuerpo legible */ }
    const err = new Error(detalle);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

const escribe = (num, decimales = 2) => {
  if (num === null || num === undefined || Number.isNaN(num)) return "--";
  return Number(num).toLocaleString("en-US", {
    minimumFractionDigits: 0,
    maximumFractionDigits: decimales,
  });
};

function aISO(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${dd}`;
}

const formatearFecha = (iso) => {
  if (!iso) return "--";
  const [y, m, d] = iso.split("-").map(Number);
  return new Intl.DateTimeFormat("es-ES", {
    day: "2-digit",
    month: "short",
    year: y !== new Date().getFullYear() ? "numeric" : undefined,
  }).format(new Date(y, m - 1, d));
};

function siguienteDiaHabil(d) {
  const x = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  do { x.setDate(x.getDate() + 1); } while (x.getDay() === 0 || x.getDay() === 6);
  return x;
}

function scaleLineal(dominio, rango) {
  const [d0, d1] = dominio;
  const [r0, r1] = rango;
  const pendiente = (r1 - r0) / (d1 - d0 || 1);
  return (v) => r0 + (v - d0) * pendiente;
}

function ticksLimpios(min, max, n = 5) {
  const span = (max - min) || 1;
  const paso = Math.pow(10, Math.floor(Math.log10(span / n)));
  const err = span / n / paso;
  const mult = err >= 7.5 ? 10 : err >= 3.5 ? 5 : err >= 1.5 ? 2 : 1;
  const s = paso * mult;
  const out = [];
  for (let v = Math.ceil(min / s) * s; v <= max + 1e-9; v += s) out.push(v);
  return out;
}

/* ------------------------------------------------------------------ */
/*  Datalist de tickers + filtros                                      */
/* ------------------------------------------------------------------ */

function poblarDatalist(items) {
  const dl = $("lista-tickers");
  dl.replaceChildren();
  for (const t of items) {
    const op = document.createElement("option");
    op.value = t.simbolo;
    const etiqueta = t.nombre ? `${t.nombre}${t.sector ? ` (${t.sector})` : ""}` : t.simbolo;
    op.label = etiqueta;
    dl.appendChild(op);
    mapaSimbolos.set(t.simbolo, t);
  }
}

function poblarSectores(items) {
  const select = $("select-sector");
  const actual = estado.sector;
  const sectores = [...new Set(items.map((t) => (t.sector || "").trim()).filter(Boolean))]
    .sort((a, b) => a.localeCompare(b));
  select.replaceChildren();
  const vacio = document.createElement("option");
  vacio.value = "";
  vacio.textContent = "Todos los sectores";
  select.appendChild(vacio);
  for (const s of sectores) {
    const op = document.createElement("option");
    op.value = s;
    op.textContent = s;
    select.appendChild(op);
  }
  estado.sector = sectores.includes(actual) ? actual : "";
  select.value = estado.sector;
}

function urlTickers() {
  const q = $("input-ticker").value.trim();
  const p = new URLSearchParams();
  if (q.length > 0) p.set("q", q);
  if (estado.lista) p.set("lista", estado.lista);
  if (estado.sector) p.set("sector", estado.sector);
  const qs = p.toString();
  return `${BASE_API}/api/v1/tickers${qs ? `?${qs}` : ""}`;
}

async function refrescarTickers() {
  const items = await fetchJSON(urlTickers());
  poblarDatalist(items);
}

/* ------------------------------------------------------------------ */
/*  Carga de datos                                                     */
/* ------------------------------------------------------------------ */

function urlHistoria(sim) {
  // Asegura que el input "Desde" refleje la ventana activa (default o la del
  // usuario) antes de construir la URL, así UI y petición siempre coinciden.
  sincronizarVentanaUI();
  const p = new URLSearchParams();
  const desde = estado.desde || $("desde").value;
  if (desde) p.set("desde", desde);
  if (estado.hasta) p.set("hasta", estado.hasta);
  const qs = p.toString();
  return `${BASE_API}/api/v1/ticker/${encodeURIComponent(sim)}/history${qs ? `?${qs}` : ""}`;
}

// Restringe el default a la ventana de observación (últimos DIAS_OBSERVACION
// días naturales) para que el forecast de 10 días sea visible al final del eje.
// Siempre se basa en hoy: ventana estable y coincidente entre URL e input.
function ventanaPorDefectoDesde() {
  return aISO(new Date(Date.now() - DIAS_OBSERVACION * 86400000));
}

// Sincroniza el input "Desde" para que la UI refleje la ventana activa,
// pero solo si el usuario aún no fijó una fecha propia.
function sincronizarVentanaUI() {
  if (!estado.desde) {
    $("desde").value = ventanaPorDefectoDesde();
  }
}

async function cargarTicker(sim, soloHistoria = false) {
  estado.sim = sim;
  estado.enCarga = true;
  const token = ++estado.cargaToken;
  mostrarCarga(true);
  ocultarBanner();

  const meta = mapaSimbolos.get(sim);
  $("titulo-ticker").textContent = sim.toUpperCase();
  $("subtitulo-ticker").textContent = meta && meta.nombre
    ? `${meta.nombre} · ${meta.sector || "sin sector"}`
    : "Cargando metadatos…";
  $("prob-simbolo").textContent = sim.toUpperCase();

  const tareas = [fetchJSON(urlHistoria(sim))];
  if (!soloHistoria) tareas.push(fetchJSON(`${BASE_API}/api/v1/ticker/${encodeURIComponent(sim)}/forecast`));
  const [hist, fc] = await Promise.allSettled(tareas);
  if (token !== estado.cargaToken) return; // respuesta obsoleta

  if (hist.status === "fulfilled" && Array.isArray(hist.value) && hist.value.length) {
    ultimaFecha = hist.value[hist.value.length - 1].fecha;
    if (ultimaFecha) {
      $("hasta").max = ultimaFecha;
      $("desde").max = ultimaFecha;
    }
    const fcDato = fc && fc.status === "fulfilled" ? fc.value : null;
    const incluyeFin = !estado.hasta || (ultimaFecha && estado.hasta >= ultimaFecha);
    dibujar(hist.value, fcDato || (soloHistoria && incluyeFin ? ultimoForecast : null));
  } else {
    const fallo = hist.status === "rejected" ? hist.reason : new Error("Sin datos de historia");
    mostrarError(`No se pudo obtener la historia de ${sim.toUpperCase()}: ${fallo.message}`);
    limpiarGrafico();
  }

  if (fc && fc.status === "fulfilled" && fc.value) {
    pintarProbabilidad(fc.value);
  } else if (fc && fc.status === "rejected") {
    const fallo = fc.reason;
    pintarErrorForecast(sim, fallo);
    if (hist.status === "rejected" && !(estado.desde || estado.hasta)) {
      mostrarError(`Falló la conexión con la API (${fallo.message}). Verificá que FastAPI esté en :8090.`);
    }
  }

  estado.enCarga = false;
  mostrarCarga(false);
}

/* ------------------------------------------------------------------ */
/*  Estados: carga / error / probabilidad                              */
/* ------------------------------------------------------------------ */

function mostrarCarga(activo) {
  $("estado-carga").hidden = !activo;
  const ph = $("placeholder-grafico");
  ph.hidden = !activo;
  if (activo) {
    ph.querySelector(".spinner").hidden = false;
    ph.querySelector("p").textContent = "Descargando precios y forecast…";
  }
}

function mostrarError(mensaje) {
  const b = $("banner-error");
  b.textContent = b.hidden ? mensaje : `${b.textContent}\n${mensaje}`;
  b.hidden = false;
}

function ocultarBanner() { $("banner-error").hidden = true; }

function pintarProbabilidad(fc) {
  const fuerte = Math.max(0, Math.min(1, Number(fc.prob_mov_fuerte) || 0));
  const calma = Math.max(0, Math.min(1, Number(fc.prob_calma) || 0));
  const pFuerte = Math.round(fuerte * 100);
  const pCalma = Math.round(calma * 100);

  $("barra-fuerte").style.width = `${pFuerte}%`;
  $("barra-calma").style.width = `${pCalma}%`;
  $("prob-fuerte").textContent = `${pFuerte}%`;
  $("prob-calma").textContent = `${pCalma}%`;

  $("dato-precio").textContent = fc.precio_actual != null ? `$${escribe(fc.precio_actual)}` : "--";
  $("dato-fecha").textContent = formatearFecha(fc.fecha_asof);
  $("dato-modelo").textContent = fc.modelo || "--";
  $("badge-modelo").textContent = fc.modelo ? `modelo: ${fc.modelo}` : "";
  $("badge-modelo").hidden = !fc.modelo;

  const nota = $("nota-modelo");
  const umbral = Number(fc.umbral_movimiento);
  if (umbral) {
    nota.textContent = `Movimiento fuerte = variación > ${Math.round(umbral * 100)}% a 21 días hábiles.`;
    nota.hidden = false;
  } else {
    nota.hidden = true;
  }
}

function pintarErrorForecast(sim, err) {
  $("barra-fuerte").style.width = "0%";
  $("barra-calma").style.width = "0%";
  $("prob-fuerte").textContent = "--";
  $("prob-calma").textContent = "--";
  $("dato-precio").textContent = "--";
  $("dato-fecha").textContent = "--";
  $("dato-modelo").textContent = "--";
  $("badge-modelo").hidden = true;

  const nota = $("nota-modelo");
  if (err.status === 503) {
    nota.textContent = `Modelo no entrenado para ${sim.toUpperCase()} (503). La historia se muestra igual.`;
  } else {
    nota.textContent = `No se pudo generar el forecast: ${err.message}`;
  }
  nota.hidden = false;
}

function limpiarGrafico() {
  const svg = $("grafico-svg");
  svg.replaceChildren();
  const ph = $("placeholder-grafico");
  ph.querySelector(".spinner").hidden = true;
  ph.querySelector("p").textContent = "No hay datos de historia para este rango.";
  ph.hidden = false;
}

/* ------------------------------------------------------------------ */
/*  Gráfico SVG                                                        */
/* ------------------------------------------------------------------ */

const SVG_NS = "http://www.w3.org/2000/svg";
const MARGEN = { sup: 16, der: 18, inf: 32, izq: 60 };

let ultimaHistoria = null;
let ultimoForecast = null;
const COLORES = {
  azul: "#3b82f6",
  naranja: "#f59e0b",
  naranjaBanda: "rgba(245, 158, 11, 0.16)",
  rejilla: "rgba(139, 147, 167, 0.10)",
  eje: "#8b93a7",
  area: "rgba(59, 130, 246, 0.12)",
  areaPico: "rgba(59, 130, 246, 0.03)",
};

let ptsTooltip = [];

function el(nombre, attrs = {}) {
  const n = document.createElementNS(SVG_NS, nombre);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  return n;
}

function rutaSuave(pts) {
  if (pts.length < 3) return "M" + pts.map((p) => `${p[0]},${p[1]}`).join(" L");
  let d = `M${pts[0][0]},${pts[0][1]}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[Math.max(0, i - 1)];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[Math.min(pts.length - 1, i + 2)];
    const c1x = p1[0] + (p2[0] - p0[0]) / 6;
    const c1y = p1[1] + (p2[1] - p0[1]) / 6;
    const c2x = p2[0] - (p3[0] - p1[0]) / 6;
    const c2y = p2[1] - (p3[1] - p1[1]) / 6;
    d += ` C${c1x},${c1y} ${c2x},${c2y} ${p2[0]},${p2[1]}`;
  }
  return d;
}

function diasFuturos(desdeISO, cantidad) {
  const base = siguienteDiaHabil(new Date(desdeISO.slice(0, 4), desdeISO.slice(5, 7) - 1, desdeISO.slice(8, 10)));
  const out = [];
  let d = base;
  for (let i = 0; i < cantidad; i++) {
    out.push(aISO(d));
    d = siguienteDiaHabil(d);
  }
  return out;
}

function dibujar(hist, fc) {
  ultimaHistoria = hist;
  ultimoForecast = fc;

  const cont = $("grafico");
  const svg = $("grafico-svg");
  svg.replaceChildren();
  ptsTooltip = [];
  $("placeholder-grafico").hidden = true;
  $("tooltip").hidden = true;

  const ancho = cont.clientWidth || 600;
  const alto = cont.clientHeight || 430;
  const iw = ancho - MARGEN.izq - MARGEN.der;
  const ih = alto - MARGEN.sup - MARGEN.inf;

  const nHist = hist.length;
  const diasFc = fc && Array.isArray(fc.forecast) ? fc.forecast : null;
  const nFc = diasFc ? diasFc.length : 0;
  const nBase = nHist;                       // primer índice del forecast
  const nTotal = nBase + nFc;                // dominio X = [0, nTotal-1]

  const fechas = hist.map((h) => h.fecha).concat(diasFc ? diasFuturos(hist[nHist - 1].fecha, nFc) : []);

  // Y: dominio sobre historia + banda del forecast
  let yMin = Infinity, yMax = -Infinity;
  for (const h of hist) {
    yMin = Math.min(yMin, h.close);
    yMax = Math.max(yMax, h.close);
  }
  if (diasFc) {
    for (const f of diasFc) {
      if (f.q10 < yMin) yMin = f.q10;
      if (f.q90 > yMax) yMax = f.q90;
    }
  }
  if (yMin === Infinity) { yMin = 0; yMax = 1; }
  const pad = (yMax - yMin) * 0.06 || 1;
  yMin -= pad; yMax += pad;
  const y = scaleLineal([yMin, yMax], [ih, 0]);
  const px = (i) => MARGEN.izq + (i / Math.max(1, nTotal - 1)) * iw;

  const defs = el("defs");
  const grad = el("linearGradient", { id: "grad-area", x1: "0", y1: "0", x2: "0", y2: "1" });
  grad.appendChild(el("stop", { offset: "0%", "stop-color": "#3b82f6", "stop-opacity": "0.16" }));
  grad.appendChild(el("stop", { offset: "100%", "stop-color": "#3b82f6", "stop-opacity": "0" }));
  defs.appendChild(grad);
  svg.appendChild(defs);

  // ---------- Grid Y + etiquetas ----------
  const ticksY = ticksLimpios(yMin, yMax, 5);
  for (const t of ticksY) {
    const yy = MARGEN.sup + y(t) + 0.5;
    svg.appendChild(el("line", {
      x1: MARGEN.izq, y1: yy, x2: ancho - MARGEN.der, y2: yy,
      stroke: COLORES.rejilla, "stroke-width": 1,
    }));
    const tL = el("text", {
      x: MARGEN.izq - 9, y: yy + 4,
      "text-anchor": "end", "font-size": 11, fill: COLORES.eje,
    });
    tL.textContent = escribe(t, Math.abs(t) < 10 ? 2 : 0);
    svg.appendChild(tL);
  }

  // ---------- Grid X + etiquetas ----------
  const pasoX = Math.max(2, Math.ceil(nTotal / Math.max(2, Math.floor(iw / 95))));
  const ticksX = [];
  for (let i = 0; i < nTotal; i += pasoX) ticksX.push(i);
  if (ticksX[ticksX.length - 1] !== nTotal - 1) ticksX.push(nTotal - 1);
  for (const i of ticksX) {
    const xx = px(i);
    svg.appendChild(el("line", {
      x1: xx, y1: MARGEN.sup, x2: xx, y2: alto - MARGEN.inf,
      stroke: COLORES.rejilla, "stroke-width": 1,
    }));
    const tL = el("text", {
      x: xx, y: alto - MARGEN.inf + 18,
      "text-anchor": "middle", "font-size": 11, fill: COLORES.eje,
    });
    tL.textContent = formatearFecha(fechas[i] || fechas[fechas.length - 1]);
    svg.appendChild(tL);
  }

  // Separador historia/forecast
  if (nFc > 0 && nHist > 0) {
    const xb = (px(nBase - 1) + px(nBase)) / 2;
    svg.appendChild(el("line", {
      x1: xb, y1: MARGEN.sup, x2: xb, y2: alto - MARGEN.inf,
      stroke: COLORES.naranja, "stroke-width": 1, "stroke-dasharray": "3 4", opacity: 0.55,
    }));
    const lbl = el("text", {
      x: xb + 7, y: MARGEN.sup + 12,
      "font-size": 10, fill: COLORES.naranja, "font-weight": 600,
    });
    lbl.textContent = "forecast";
    svg.appendChild(lbl);
  }

  // ---------- Serie histórica: área + línea ----------
  const pts = hist.map((h, i) => [px(i), MARGEN.sup + y(h.close)]);
  const base = alto - MARGEN.inf;
  const area = `M${pts[0][0]},${base} L${pts[0][0]},${pts[0][1]} ` +
    rutaSuave(pts).slice(1) + ` L${pts[pts.length - 1][0]},${base} Z`;
  svg.appendChild(el("path", { d: area, fill: "url(#grad-area)" }));

  svg.appendChild(el("path", {
    d: rutaSuave(pts), fill: "none", stroke: COLORES.azul,
    "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round",
  }));

  // ---------- Forecast: banda Q10-Q90 + línea Q50 ----------
  if (diasFc && nFc > 0) {
    const q10 = diasFc.map((f, k) => [px(nBase + k), MARGEN.sup + y(f.q10)]);
    const q90 = diasFc.map((f, k) => [px(nBase + k), MARGEN.sup + y(f.q90)]);

    let banda = `M${q10[0][0]},${q10[0][1]}`;
    for (let k = 1; k < nFc; k++) banda += ` L${q10[k][0]},${q10[k][1]}`;
    for (let k = nFc - 1; k >= 0; k--) banda += ` L${q90[k][0]},${q90[k][1]}`;
    banda += " Z";
    svg.appendChild(el("path", { d: banda, fill: COLORES.naranjaBanda }));

    const q50 = diasFc.map((f, k) => [px(nBase + k), MARGEN.sup + y(f.q50)]);
    const desde = pts[pts.length - 1];
    const lineaFc = `M${desde[0]},${desde[1]}` + q50.map((p) => ` L${p[0]},${p[1]}`).join("");
    svg.appendChild(el("path", {
      d: lineaFc, fill: "none", stroke: COLORES.naranja,
      "stroke-width": 2, "stroke-dasharray": "5 4", "stroke-linecap": "round",
    }));
  }

  // ---------- Tooltip (punto más cercano) ----------
  pts.forEach((p, i) => ptsTooltip.push({
    x: p[0], y: p[1], fecha: fechas[i], tipo: "hist", valor: hist[i].close,
  }));
  if (diasFc) {
    diasFc.forEach((f, k) => {
      const x = px(nBase + k);
      ptsTooltip.push({
        x, y: MARGEN.sup + y(f.q50), fecha: fechas[nBase + k],
        tipo: "fc", q50: f.q50, q10: f.q10, q90: f.q90,
      });
    });
  }
}

function moverTooltip(evt) {
  const cont = $("grafico");
  const tip = $("tooltip");
  const rect = cont.getBoundingClientRect();
  const mx = evt.clientX - rect.left;
  const my = evt.clientY - rect.top;

  let mejor = null, mejorDist = Infinity;
  for (const p of ptsTooltip) {
    const d = Math.hypot(p.x - mx, p.y - my);
    if (d < mejorDist) { mejorDist = d; mejor = p; }
  }
  if (!mejor) return;

  const piezas = [];

  if (mejor.tipo === "fc") {
    const tag = document.createElement("span");
    tag.className = "tt-tag";
    tag.textContent = "forecast";
    piezas.push(tag);
  }

  const fecha = document.createElement("span");
  fecha.className = "tt-fecha";
  fecha.textContent = formatearFecha(mejor.fecha);
  piezas.push(fecha);

  if (mejor.tipo === "fc") {
    const valor = document.createElement("div");
    valor.className = "tt-valor";
    valor.appendChild(document.createTextNode(escribe(mejor.q50) + " "));
    const q = document.createElement("span");
    q.style.color = "#9aa3b6";
    q.textContent = "q50";
    valor.appendChild(q);
    piezas.push(valor);

    const banda = document.createElement("div");
    banda.style.color = "#9aa3b6";
    banda.appendChild(document.createTextNode(`q10 ${escribe(mejor.q10)} · q90 ${escribe(mejor.q90)}`));
    piezas.push(banda);
  } else {
    const valor = document.createElement("div");
    valor.className = "tt-valor";
    valor.textContent = `$${escribe(mejor.valor)}`;
    piezas.push(valor);
  }

  tip.replaceChildren(...piezas);
  tip.style.left = `${Math.min(Math.max(mejor.x, 40), rect.width - 20)}px`;
  tip.style.top = `${Math.max(8, Math.min(mejor.y, rect.height - 12))}px`;
  tip.hidden = false;
}

/* ------------------------------------------------------------------ */
/*  Eventos de UI                                                      */
/* ------------------------------------------------------------------ */

let timerDatalist = null;

function onInputTicker() {
  clearTimeout(timerDatalist);
  const v = $("input-ticker").value.trim();
  const vMayus = v.toUpperCase();

  // El usuario puede haber elegido un símbolo del datalist: si coincide con
  // uno válido, disparamos la carga.
  if (v && mapaSimbolos.has(vMayus)) {
    cargarTicker(vMayus);
    return;
  }

  timerDatalist = setTimeout(async () => {
    try {
      if (v.length === 0) {
        // Al vaciarse el input, recargamos el listado base (filtros activos).
        const items = await fetchJSON(urlTickers());
        poblarDatalist(items);
      } else if (v.length >= 2) {
        await refrescarTickers();
      }
    } catch (err) {
      mostrarError(`No se pudo acotar el listado de tickers: ${err.message}`);
    }
  }, 150);
}

function onCambioTicker() {
  const v = $("input-ticker").value.trim();
  const vMayus = v.toUpperCase();
  if (v && mapaSimbolos.has(vMayus)) {
    $("input-ticker").value = vMayus;
    cargarTicker(vMayus);
  }
}

function initChips() {
  $("grupo-chips").addEventListener("click", (evt) => {
    const chip = evt.target.closest(".chip");
    if (!chip) return;
    const lista = chip.dataset.lista;
    const activa = chip.classList.contains("activo");
    document.querySelectorAll(".chip").forEach((c) => c.classList.remove("activo"));
    if (!activa) {
      chip.classList.add("activo");
      estado.lista = lista;
    } else {
      estado.lista = "";
    }
    refrescarTickers().catch((err) => mostrarError(`Filtro de lista: ${err.message}`));
  });
}

function init() {
  initChips();

  $("input-ticker").addEventListener("input", onInputTicker);
  $("input-ticker").addEventListener("change", onCambioTicker);

  $("select-sector").addEventListener("change", (evt) => {
    estado.sector = evt.target.value;
    refrescarTickers().catch((err) => mostrarError(`Filtro de sector: ${err.message}`));
  });

  $("desde").addEventListener("change", (evt) => {
    estado.desde = evt.target.value;
    cargarTicker(estado.sim, true);
  });
  $("hasta").addEventListener("change", (evt) => {
    estado.hasta = evt.target.value;
    cargarTicker(estado.sim, true);
  });

  const cont = $("grafico");
  cont.addEventListener("mousemove", moverTooltip);
  cont.addEventListener("mouseleave", () => { $("tooltip").hidden = true; });

  const ro = new ResizeObserver(() => {
    if (ultimaHistoria) dibujar(ultimaHistoria, ultimoForecast);
  });
  ro.observe(cont);
}

/* ------------------------------------------------------------------ */
/*  Arranque                                                           */
/* ------------------------------------------------------------------ */

(async function main() {
  try {
    // Listado inicial (hasta 200) para el datalist + derivar sectores.
    const items = await fetchJSON(`${BASE_API}/api/v1/tickers`);
    poblarDatalist(items);
    poblarSectores(items);
  } catch (err) {
    mostrarError(`No se pudo cargar el catálogo de tickers: ${err.message}. La demo carga igual con AAPL.`);
  }

  init();
  // Mostrar la ventana de observación por defecto antes de la primera carga,
  // para que URL del histograma y el input "Desde" coincidan desde el inicio.
  sincronizarVentanaUI();
  cargarTicker("AAPL");
})();
