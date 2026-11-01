/* Navigazione cartografica: nessuna dipendenza aggiuntiva. */
let mapSearchTimer;
let mapViewportFrame;
const mapOperaSuiteCache = new WeakMap();

function validMapCoordinates(opera) {
  const geo = opera?.geo;
  return geo && geo.lat !== null && geo.lng !== null && geo.lat !== '' && geo.lng !== '' &&
    Number.isFinite(Number(geo.lat)) && Number.isFinite(Number(geo.lng)) &&
    Math.abs(Number(geo.lat)) <= 90 && Math.abs(Number(geo.lng)) <= 180;
}

function normalizeMapSearch(value) {
  return String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('it').trim();
}

function scheduleMapSearch() {
  clearTimeout(mapSearchTimer);
  mapSearchTimer = setTimeout(applyFilters, 160);
}

function mapAnimationDuration(duration) {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : duration;
}

function mapCameraPadding() {
  const mobile = window.innerWidth < 768;
  const sidebar = document.getElementById('floating-sidebar');
  return {
    top: mobile ? 100 : 80,
    right: mobile ? 32 : 250,
    bottom: mobile ? 80 : 70,
    left: !mobile && state.sidebarOpen ? Math.min(sidebar.offsetWidth + 36, window.innerWidth * 0.45) : 40
  };
}

function fitMapResults() {
  const points = (state.filteredOpere || state.opere).filter(validMapCoordinates);
  if (!state.map || !points.length) return;
  const bounds = new maplibregl.LngLatBounds();
  points.forEach(op => bounds.extend([Number(op.geo.lng), Number(op.geo.lat)]));
  state.map.fitBounds(bounds, {padding: mapCameraPadding(), maxZoom: 13, pitch: 0, bearing: 0,
    duration: mapAnimationDuration(650)});
}

function syncMapWorkspaceLayout() {
  const workspace = document.getElementById('map-workspace');
  const sidebar = document.getElementById('floating-sidebar');
  workspace.style.setProperty('--sidebar-offset', state.sidebarOpen && window.innerWidth >= 768 ? `${sidebar.offsetWidth + 28}px` : '16px');
}

function updateMapViewportStatus() {
  if (!state.map) return;
  const pool = state.filteredOpere || state.opere;
  const bounds = state.map.getBounds();
  const valid = pool.filter(validMapCoordinates);
  const visible = valid.filter(op => bounds.contains([Number(op.geo.lng), Number(op.geo.lat)])).length;
  document.getElementById('stat-in-vista').textContent = visible;
  document.getElementById('map-view-status').textContent = `${visible} in vista · ${pool.length} opere filtrate${pool.length !== valid.length ? ` · ${pool.length - valid.length} senza coordinate` : ''}`;
  document.getElementById('btn-fit-results').disabled = valid.length === 0;
  const zoom = state.map.getZoom();
  document.getElementById('gis-map').dataset.detail = zoom >= 10 ? 'local' : 'overview';
  const button = document.getElementById('btn-toggle-pitch');
  const pitched = state.map.getPitch() > 15;
  button.setAttribute('aria-pressed', String(pitched));
  button.textContent = pitched ? 'Vista 2D' : 'Vista 3D';
}

function scheduleMapViewportStatus() {
  if (mapViewportFrame) return;
  mapViewportFrame = requestAnimationFrame(() => {
    mapViewportFrame = null;
    updateMapViewportStatus();
  });
}

function getMapOperaSuite(opera) {
  if (!mapOperaSuiteCache.has(opera)) {
    mapOperaSuiteCache.set(opera, window.TracciatoSuite.generaSuiteGeoJsonPerOpera(opera));
  }
  return mapOperaSuiteCache.get(opera);
}

function initializeMapWorkspace() {
  const map = state.map;
  syncMapWorkspaceLayout();
  map.addControl(new maplibregl.ScaleControl({maxWidth: 120, unit: 'metric'}), 'bottom-left');
  map.on('moveend', () => {
    if (document.getElementById('filter-in-view').checked) applyFilters();
    else scheduleMapViewportStatus();
  });
  map.on('mousemove', event => {
    const node = document.getElementById('map-coordinate-status');
    node.textContent = `${event.lngLat.lat.toFixed(5)}° N · ${event.lngLat.lng.toFixed(5)}° E`;
  });
  map.on('error', event => {
    // Un errore di tile non impedisce di usare opere e filtri.
    if (event.error?.message) console.warn('Cartografia:', event.error.message);
  });
  window.addEventListener('resize', () => { syncMapWorkspaceLayout(); map.resize(); });
  document.addEventListener('keydown', event => {
    if (event.key === '/' && !event.target.closest('input, textarea, select, [contenteditable]')) {
      event.preventDefault();
      if (!state.sidebarOpen) toggleSidebar();
      document.getElementById('filter-search').focus();
    }
  });
  document.querySelectorAll('.map-layer-panel button').forEach(button => { button.type = 'button'; });
}

function countMapIntestatari(rows) {
  return new Set((rows || []).map(row => normalizeMapSearch(row.intestatario)).filter(Boolean)).size;
}

function escapeMapHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function safeArchiveLink(value) {
  return /^\/api\/documenti\/[a-f0-9]{32}\/file(?:#page=\d+)?$/.test(value) ? value : '#';
}
function safeSourceLink(value) {
  try { const url=new URL(value);return ['https:','http:'].includes(url.protocol) ? escapeMapHtml(url.href) : '#'; }
  catch {return '#';}
}
function renderOperaDocuments(opera) {
  let panel=document.getElementById('opera-documents');
  if (!panel) {
    panel=document.createElement('div');panel.id='opera-documents';
    panel.className='p-4 border-b border-slate-700 text-xs space-y-2';
    panel.style.maxHeight='160px';panel.style.overflowY='auto';
    document.getElementById('modal-ditte-subtitle').parentElement.appendChild(panel);
  }
  panel.innerHTML=`<a href="${safeSourceLink(opera.fonte_atto_url)}" target="_blank" rel="noopener" class="text-sky-300 underline">Pagina ufficiale dell’opera</a>
    <p class="text-slate-400">${opera.righe_catastali || 0} righe estratte · ${opera.particelle_localizzate || 0} localizzate. Copertura completa non certificata.</p>`+
    (opera.documenti || []).map(doc=>`<div><a class="text-sky-300 underline" href="/api/documenti/${escapeMapHtml(doc.id)}/file" target="_blank" rel="noopener">${escapeMapHtml(doc.titolo)}</a>
    <span class="text-slate-400"> · ${doc.totale_pagine ?? '?'} pagine · ${doc.righe_estratte} righe</span>
    <a href="${safeSourceLink(doc.fonte_url)}" target="_blank" rel="noopener" class="text-slate-400 underline">Fonte ente</a></div>`).join('');
}
function buildDocumentedOperaPopup(opera) {
  return `<div style="padding:20px;font-size:12px;line-height:1.7"><span style="color:#7dd3fc">ARCHIVIO DOCUMENTALE</span>
    <h3 style="font-size:15px;font-weight:700;margin:8px 0">${escapeMapHtml(opera.titolo)}</h3>
    <p>${escapeMapHtml(opera.ente_promotore || '')}</p>
    <p>${opera.documenti?.length || 0} documenti · ${opera.righe_catastali || 0} righe estratte · ${opera.particelle_localizzate || 0} localizzate</p>
    <p style="color:#fbbf24">Il pin indica la posizione registrata dell'opera: non identifica né sostituisce la geometria delle singole particelle.</p>
    <p style="color:#fbbf24">Copertura non certificata. Le trascrizioni OCR richiedono verifica sull’originale.</p>
    <a href="/quadro-interferenze?opera=${encodeURIComponent(opera.slug)}" style="color:#7dd3fc;text-decoration:underline">Apri documenti, ditte e mappa →</a></div>`;
}
