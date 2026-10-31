/**
 * markers.js - Generatore Marker Vettoriali e Poligoni per Motore Espropri
 */

export function createOperaMarker(opera, clickCallback) {
  // 1. Determina la classe di stato procedurale
  let statusClass = 'status-pda';
  let badgeLabel = opera.sigla || opera.cup || opera.titolo?.slice(0, 15) || 'OPERA';

  if (opera.giorni_residui !== undefined && opera.giorni_residui <= 15 && opera.giorni_residui >= 0) {
    statusClass = 'status-urgente'; // Termini perentori < 15 gg
  } else if (opera.stato_codice === 'DECRETO' || opera.stato_opera === 'CHIUSA') {
    statusClass = 'status-decreto';
  } else if (opera.stato_codice === 'DPU' || opera.fase_procedurale === 'DICHIARAZIONE_PU') {
    statusClass = 'status-dpu';
  }

  // 2. Crea l'HTML del pin con LED + contatore ditte/mq
  const particelle = opera.particellare || opera.particelle || opera.ditte || [];
  const particelleCount = particelle.length;
  const countHtml = particelleCount > 0 
    ? `<span style="color:#94a3b8; font-size:10px; margin-left:2px;">(${particelleCount})</span>` 
    : '';

  const isUrgent = statusClass === 'status-urgente';
  const pulseHtml = isUrgent ? '<div class="pulse-ring"></div>' : '';

  const markerHtml = `
    <div class="custom-pin-container ${statusClass}">
      ${pulseHtml}
      <div class="pin-badge">
        <span class="pin-led"></span>
        <span style="max-width:130px; overflow:hidden; text-overflow:ellipsis;">${badgeLabel}</span>
        ${countHtml}
      </div>
    </div>
  `;

  // 3. Istanzia DivIcon Leaflet
  const customIcon = L.divIcon({
    html: markerHtml,
    className: '', // Disabilita stili di default di Leaflet
    iconSize: [120, 30],
    iconAnchor: [15, 15] // Centrato sul punto LED
  });

  const lat = opera.lat || opera.coordinate?.lat || opera.geo?.lat;
  const lng = opera.lng || opera.coordinate?.lng || opera.geo?.lng;
  if (!lat || !lng) return null;

  const marker = L.marker([lat, lng], { icon: customIcon });

  if (clickCallback) {
    marker.on('click', () => clickCallback(opera));
  }

  return marker;
}

// 4. Stili vettoriali per GeoJSON particellare (intersezioni e fasce)
export function getParticellaStyle(feature) {
  const tipo = feature.properties ? feature.properties.tipo_occupazione : 'esproprio';

  switch (tipo) {
    case 'asservimento':
      return { className: 'poly-fascia-asservimento' };
    case 'occupazione_temporanea':
      return { className: 'poly-occupazione-temporanea' };
    case 'esproprio':
    default:
      return { className: 'poly-particella-esproprio' };
  }
}

// Applicazione del layer particellare di un'opera selezionata
export function renderPianoParticellareLayer(map, geojsonData, onParticellaClick) {
  if (window.currentParticelleLayer) {
    map.removeLayer(window.currentParticelleLayer);
  }

  window.currentParticelleLayer = L.geoJSON(geojsonData, {
    style: getParticellaStyle,
    onEachFeature: (feature, layer) => {
      const p = feature.properties;
      
      // Tooltip informativo al passaggio mouse
      layer.bindTooltip(`
        <div style="font-size:11px; font-family:sans-serif; line-height:1.4;">
          <strong>Fg. ${p.foglio} - Map. ${p.mappale}</strong><br/>
          Ditta: ${p.intestatario || 'N.D.'}<br/>
          Sup. Esproprio: <b>${p.superficie_occupata || p.superfici_mq?.esproprio || 0} mq</b>
        </div>
      `, { sticky: true, opacity: 0.95 });

      // Click: apre il calcolatore o focalizza la ditta
      if (onParticellaClick) {
        layer.on('click', () => onParticellaClick(p));
      }
    }
  }).addTo(map);
}
