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

// ============================================================================
// Inicialización
// ============================================================================

async function init() {
  try {
    await cargar_dimensiones();
    await actualizar_kpis();
    await actualizar_serie_tiempo();
    await actualizar_mapa();
    await actualizar_rankings();
    await actualizar_completitud();
    setup_event_listeners();
  } catch (e) {
    console.error('Error en inicialización:', e);
  }
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
      actualizar_ui();
    });
  });

  // Fechas
  const hoy = new Date();
  const hace_30_dias = new Date(hoy.getTime() - 30 * 24 * 60 * 60 * 1000);
  document.getElementById('fecha-inicio').valueAsDate = hace_30_dias;
  document.getElementById('fecha-fin').valueAsDate = hoy;

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

  // Re-render en caso de que sea lazy
  if (tab === 'mapa' && map === null) actualizar_mapa();
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

async function actualizar_kpis() {
  const params = new URLSearchParams();
  if (state.contaminante) params.append('contaminante', state.contaminante);
  if (state.alcaldia_id) params.append('alcaldia_id', state.alcaldia_id);
  if (state.fecha_inicio) params.append('fecha_inicio', state.fecha_inicio);
  if (state.fecha_fin) params.append('fecha_fin', state.fecha_fin);

  const data = await fetch(`${API_URL}/api/kpis?${params}`).then(r => r.json());

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
      <div class="kpi-value">${(data.total_mediciones / 1e6).toFixed(1)}M</div>
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
  }

  const params = new URLSearchParams();
  params.append('contaminante', state.contaminante);
  if (state.fecha_fin) params.append('fecha', state.fecha_fin);

  const data = await fetch(`${API_URL}/api/mapa-estaciones?${params}`).then(r => r.json());

  // Limpiar marcadores previos
  map.eachLayer(layer => {
    if (layer instanceof L.Marker) map.removeLayer(layer);
  });

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
    }).bindPopup(popup).addTo(map);
  });
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
