// API OLAP Dashboard
// Consume endpoints /api/* para poblar dashboard con datos en tiempo real

const API_URL = window.location.origin;
let state = {
  contaminante: 'PM25',
  alcaldia_id: null,
  estacion: null,
  fecha_inicio: null,
  fecha_fin: null,
  granularidad: 'dia',
};

let map = null;
let capa_estaciones = null;
let rango_datos = null;  // { fecha_min, fecha_max } del cubo

// Ventana por defecto según granularidad: 30 días de datos horarios/diarios se
// ven bien, pero en vista mensual serían un único punto.
const DIAS_POR_GRANULARIDAD = { hora: 7, dia: 30, mes: 730 };

// ============================================================================
// Inicialización
// ============================================================================

async function init() {
  try {
    await fijar_rango_inicial();
  } catch (e) {
    console.warn('Rango de fechas no disponible, se usan los defaults de la API:', e);
  }

  try {
    await cargar_dimensiones();
  } catch (e) {
    console.error('Error cargando dimensiones:', e);
  }

  try {
    await actualizar_kpis();
  } catch (e) {
    console.warn('KPIs no disponibles:', e);
  }

  try {
    await actualizar_serie_tiempo();
  } catch (e) {
    console.warn('Serie tiempo no disponible:', e);
  }

  try {
    await actualizar_mapa();
  } catch (e) {
    console.warn('Mapa no disponible:', e);
  }

  try {
    await actualizar_rankings();
  } catch (e) {
    console.warn('Rankings no disponibles:', e);
  }

  try {
    await actualizar_completitud();
  } catch (e) {
    console.warn('Completitud no disponible:', e);
  }

  setup_event_listeners();
}

// Fija fechas explícitas desde el rango real de datos (terminan en 2025-12-31).
// Sin esto, cada endpoint resolvía su propio default: los KPIs miraban 12 meses,
// la serie 30 días, y los inputs mostraban fechas de hoy que no correspondían
// a nada de lo graficado.
async function fijar_rango_inicial() {
  rango_datos = await fetch(`${API_URL}/api/rango-fechas`).then(r => r.json());

  ['fecha-inicio', 'fecha-fin'].forEach(id => {
    document.getElementById(id).min = rango_datos.fecha_min;
    document.getElementById(id).max = rango_datos.fecha_max;
  });

  aplicar_ventana_por_granularidad();
}

// Reencuadra el período al cambiar de granularidad, tomando como fin la última
// fecha con datos.
function aplicar_ventana_por_granularidad() {
  if (!rango_datos) return;

  const dias = DIAS_POR_GRANULARIDAD[state.granularidad] ?? 30;
  const fecha_fin = new Date(`${rango_datos.fecha_max}T00:00:00`);
  const fecha_inicio = new Date(fecha_fin.getTime() - dias * 24 * 60 * 60 * 1000);
  const limite_min = new Date(`${rango_datos.fecha_min}T00:00:00`);

  state.fecha_fin = rango_datos.fecha_max;
  state.fecha_inicio = (fecha_inicio < limite_min ? limite_min : fecha_inicio)
    .toISOString().slice(0, 10);

  document.getElementById('fecha-inicio').value = state.fecha_inicio;
  document.getElementById('fecha-fin').value = state.fecha_fin;
}

// ============================================================================
// Cargar Dimensiones
// ============================================================================

async function cargar_dimensiones() {
  // Contaminantes (pills)
  const contaminantes = await fetch(`${API_URL}/api/dimensiones/contaminantes`).then(r => r.json());
  const pills_container = document.getElementById('contaminant-pills');
  contaminantes.items.forEach(c => {
    const pill = document.createElement('button');
    pill.className = 'pill';
    pill.textContent = c.codigo;
    pill.dataset.codigo = c.codigo;
    if (c.codigo === state.contaminante) pill.classList.add('active');
    pill.addEventListener('click', () => cambiar_contaminante(c.codigo));
    pills_container.appendChild(pill);
  });

  // Alcaldías (select)
  const alcaldias = await fetch(`${API_URL}/api/dimensiones/alcaldias`).then(r => r.json());
  const alcaldia_select = document.getElementById('alcaldia-select');
  alcaldias.items.forEach(a => {
    const option = document.createElement('option');
    option.value = a.alcaldia_id;
    option.textContent = a.nombre_alcaldia;
    alcaldia_select.appendChild(option);
  });
  alcaldia_select.addEventListener('change', (e) => {
    state.alcaldia_id = e.target.value ? parseInt(e.target.value) : null;
    actualizar_estaciones();
  });

  // Estaciones (select, poblado dinámicamente)
  actualizar_estaciones();
}

async function actualizar_estaciones() {
  const estaciones = await fetch(`${API_URL}/api/dimensiones/estaciones`).then(r => r.json());
  const estacion_select = document.getElementById('estacion-select');
  estacion_select.innerHTML = '<option value="">Todas</option>';

  estaciones.items
    .filter(e => !state.alcaldia_id || e.alcaldia_id === state.alcaldia_id)
    .forEach(e => {
      const option = document.createElement('option');
      option.value = e.codigo;
      option.textContent = `${e.codigo} - ${e.nombre_estacion}`;
      estacion_select.appendChild(option);
    });

  estacion_select.addEventListener('change', (e) => {
    state.estacion = e.target.value || null;
    revisar_hora_deshabilitada();
    actualizar_ui();
  });
}

// ============================================================================
// Event Listeners
// ============================================================================

function setup_event_listeners() {
  // Tabs
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', (e) => cambiar_tab(e.target.dataset.tab));
  });

  // Granularidad
  document.querySelectorAll('[data-granularidad]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      state.granularidad = e.target.dataset.granularidad;
      document.querySelectorAll('[data-granularidad]').forEach(b => b.classList.remove('active'));
      e.target.classList.add('active');
      revisar_hora_deshabilitada();
      aplicar_ventana_por_granularidad();
      actualizar_ui();
    });
  });

  // Fechas: no se prellenan con hoy — los datos terminan en 2025-12-31 y el
  // filtro mostraba un rango de 2026 que contradecía lo graficado. Los inputs
  // se sincronizan con el período que resuelve la API (ver actualizar_kpis).
  document.getElementById('fecha-inicio').addEventListener('change', () => {
    state.fecha_inicio = document.getElementById('fecha-inicio').value;
    actualizar_ui();
  });

  document.getElementById('fecha-fin').addEventListener('change', () => {
    state.fecha_fin = document.getElementById('fecha-fin').value;
    actualizar_ui();
  });

  // Reset
  document.getElementById('reset-btn').addEventListener('click', () => {
    state = { contaminante: 'PM25', alcaldia_id: null, estacion: null, granularidad: 'dia' };
    location.reload();
  });
}

function cambiar_contaminante(codigo) {
  state.contaminante = codigo;
  document.querySelectorAll('.pill').forEach(p => {
    p.classList.toggle('active', p.dataset.codigo === codigo);
  });
  actualizar_ui();
}

function cambiar_tab(tab) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelector(`[data-tab="${tab}"]`).classList.add('active');
  document.querySelectorAll('.tab-content').forEach(t => t.style.display = 'none');
  document.getElementById(`tab-${tab}`).style.display = 'block';

  // El mapa se inicializa con #tab-mapa oculto, así que Leaflet mide un
  // contenedor de 0x0 y sólo carga un tile. Hay que recalcular al mostrarlo.
  if (tab === 'mapa') {
    if (map === null) {
      actualizar_mapa();
    } else {
      map.invalidateSize();
      if (capa_estaciones && capa_estaciones.getLayers().length > 0) {
        map.fitBounds(capa_estaciones.getBounds(), { padding: [40, 40] });
      }
    }
  }

  // Plotly dibuja con el ancho por defecto (700px) si el tab está oculto; sin
  // esto la gráfica se ve a media anchura durante los primeros instantes
  if (tab === 'datos' && window.Plotly) {
    Plotly.Plots.resize('chart-completitud');
  }
}

function revisar_hora_deshabilitada() {
  const btn_hora = document.getElementById('btn-hora');
  if (state.granularidad === 'hora' && !state.estacion) {
    btn_hora.disabled = true;
    btn_hora.style.opacity = '0.5';
    btn_hora.title = 'Requiere estación seleccionada';
    state.granularidad = 'dia';
    document.querySelector('[data-granularidad="dia"]').classList.add('active');
    document.querySelector('[data-granularidad="hora"]').classList.remove('active');
  } else {
    btn_hora.disabled = false;
    btn_hora.style.opacity = '1';
    btn_hora.title = '';
  }
}

// ============================================================================
// Actualizar UI
// ============================================================================

async function actualizar_ui() {
  await actualizar_kpis();
  await actualizar_serie_tiempo();
  await actualizar_mapa();
  await actualizar_rankings();
  await actualizar_completitud();
}

// ============================================================================
// KPIs
// ============================================================================

// Escala la unidad al tamaño del número: dividir siempre entre 1e6 mostraba
// "0.0M" para los 16,368 registros de un mes filtrado por contaminante.
function formatear_conteo(n) {
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}K`;
  return `${n}`;
}

async function actualizar_kpis() {
  const params = new URLSearchParams();
  if (state.contaminante) params.append('contaminante', state.contaminante);
  if (state.alcaldia_id) params.append('alcaldia_id', state.alcaldia_id);
  if (state.fecha_inicio) params.append('fecha_inicio', state.fecha_inicio);
  if (state.fecha_fin) params.append('fecha_fin', state.fecha_fin);

  const data = await fetch(`${API_URL}/api/kpis?${params}`).then(r => r.json());

  // Reflejar en los inputs el período que la API resolvió por defecto
  if (!state.fecha_inicio) document.getElementById('fecha-inicio').value = data.periodo.fecha_inicio;
  if (!state.fecha_fin) document.getElementById('fecha-fin').value = data.periodo.fecha_fin;

  const html = `
    <div class="kpi">
      <div class="kpi-label">Índice Promedio</div>
      <div class="kpi-value">${data.promedio_indice_normalizado.toFixed(1)}</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Completitud</div>
      <div class="kpi-value">${data.pct_completitud.toFixed(1)}%</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Estaciones Activas</div>
      <div class="kpi-value">${data.estaciones_activas}</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Total Mediciones</div>
      <div class="kpi-value">${formatear_conteo(data.total_mediciones)}</div>
    </div>
  `;

  document.getElementById('kpis-container').innerHTML = html;
}

// ============================================================================
// Series de Tiempo
// ============================================================================

async function actualizar_serie_tiempo() {
  const params = new URLSearchParams();
  params.append('contaminante', state.contaminante);
  params.append('granularidad', state.granularidad);
  if (state.estacion) params.append('estacion', state.estacion);
  if (state.alcaldia_id) params.append('alcaldia_id', state.alcaldia_id);
  if (state.fecha_inicio) params.append('fecha_inicio', state.fecha_inicio);
  if (state.fecha_fin) params.append('fecha_fin', state.fecha_fin);

  const data = await fetch(`${API_URL}/api/series-tiempo?${params}`).then(r => r.json());

  const trace_promedio = {
    x: data.puntos.map(p => p.fecha),
    y: data.puntos.map(p => p.valor_promedio || null),
    name: 'Promedio',
    type: 'scatter',
    mode: 'lines',
    line: { color: '#2b6de8', width: 2 },
    fill: 'tozeroy',
    fillcolor: 'rgba(43, 109, 232, 0.1)',
  };

  const layout = {
    title: `${data.contaminante} - ${state.granularidad.toUpperCase()}`,
    xaxis: { title: 'Fecha' },
    yaxis: { title: 'Valor' },
    hovermode: 'x unified',
    margin: { t: 40, r: 40, b: 40, l: 60 },
  };

  Plotly.newPlot('chart-serie-tiempo', [trace_promedio], layout, { responsive: true });
}

// ============================================================================
// Mapa
// ============================================================================

async function actualizar_mapa() {
  if (!map) {
    map = L.map('map-container').setView([19.4, -99.1], 11);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap',
      maxZoom: 19,
    }).addTo(map);
    // featureGroup, no layerGroup: sólo el primero expone getBounds() para fitBounds
    capa_estaciones = L.featureGroup().addTo(map);
  }

  const params = new URLSearchParams();
  params.append('contaminante', state.contaminante);
  if (state.fecha_fin) params.append('fecha', state.fecha_fin);

  const data = await fetch(`${API_URL}/api/mapa-estaciones?${params}`).then(r => r.json());

  // Limpiar marcadores previos (son circleMarker, no Marker: el chequeo
  // instanceof L.Marker no los removía y se acumulaban en cada refresh)
  capa_estaciones.clearLayers();

  // Rango de índices para colorear
  const indices = data.estaciones.map(e => e.indice_normalizado).filter(i => i !== null);
  const min_idx = Math.min(...indices);
  const max_idx = Math.max(...indices);

  data.estaciones.forEach(e => {
    const color_intensity = e.indice_normalizado ? (e.indice_normalizado - min_idx) / (max_idx - min_idx) : 0.5;
    const color = `hsl(220, 60%, ${100 - color_intensity * 40}%)`;

    const popup = `
      <strong>${e.codigo} - ${e.nombre}</strong><br>
      Valor: ${e.valor?.toFixed(2) || 'N/A'}<br>
      Índice: ${e.indice_normalizado?.toFixed(1) || 'N/A'}
    `;

    L.circleMarker([e.latitud, e.longitud], {
      radius: 8,
      fillColor: color,
      color: '#171a21',
      weight: 1,
      opacity: 1,
      fillOpacity: 0.8,
    }).bindPopup(popup).addTo(capa_estaciones);
  });

  // Encuadrar sobre las estaciones: con zoom 11 fijo quedaban apiñadas al centro
  if (data.estaciones.length > 0) {
    map.invalidateSize();
    map.fitBounds(capa_estaciones.getBounds(), { padding: [40, 40] });
  }
}

// ============================================================================
// Rankings
// ============================================================================

async function actualizar_rankings() {
  // Ranking estaciones
  const params_est = new URLSearchParams();
  params_est.append('contaminante', state.contaminante);
  if (state.fecha_inicio) params_est.append('fecha_inicio', state.fecha_inicio);
  if (state.fecha_fin) params_est.append('fecha_fin', state.fecha_fin);

  const ranking_est = await fetch(`${API_URL}/api/ranking/estaciones?${params_est}`).then(r => r.json());
  const tbody_est = document.querySelector('#ranking-estaciones tbody');
  tbody_est.innerHTML = ranking_est.ranking.map(r => `
    <tr>
      <td style="text-align: center;">${r.posicion}</td>
      <td>${r.codigo} - ${r.nombre}</td>
      <td style="text-align: right; font-weight: 600;">${r.indice_normalizado?.toFixed(1) || 'N/A'}</td>
    </tr>
  `).join('');

  // Ranking contaminantes
  const params_cont = new URLSearchParams();
  if (state.estacion) params_cont.append('estacion', state.estacion);
  if (state.alcaldia_id) params_cont.append('alcaldia_id', state.alcaldia_id);
  if (state.fecha_inicio) params_cont.append('fecha_inicio', state.fecha_inicio);
  if (state.fecha_fin) params_cont.append('fecha_fin', state.fecha_fin);

  const ranking_cont = await fetch(`${API_URL}/api/ranking/contaminantes?${params_cont}`).then(r => r.json());
  const tbody_cont = document.querySelector('#ranking-contaminantes tbody');
  tbody_cont.innerHTML = ranking_cont.ranking.map(r => `
    <tr>
      <td style="text-align: center;">${r.posicion}</td>
      <td>${r.codigo} - ${r.nombre}</td>
      <td style="text-align: right; font-weight: 600;">${r.indice_normalizado_promedio?.toFixed(1) || 'N/A'}</td>
    </tr>
  `).join('');
}

// ============================================================================
// Completitud
// ============================================================================

async function actualizar_completitud() {
  const data = await fetch(`${API_URL}/api/completitud?agrupar_por=contaminante`).then(r => r.json());

  const trace = {
    x: data.items.map(i => i.clave),
    y: data.items.map(i => i.pct_completitud),
    type: 'bar',
    marker: { color: '#2b6de8' },
  };

  const layout = {
    title: '% Completitud por Contaminante',
    xaxis: { title: 'Contaminante' },
    yaxis: { title: '% Completo', range: [0, 100] },
    margin: { b: 60, l: 60, t: 40 },
  };

  Plotly.newPlot('chart-completitud', [trace], layout, { responsive: true });
}

// ============================================================================
// Main
// ============================================================================

document.addEventListener('DOMContentLoaded', init);
