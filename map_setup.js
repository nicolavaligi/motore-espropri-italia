/**
 * map_setup.js - Setup Cartografia Italia HD per Motore Espropri
 */

// Bounding Box e Centro Ottimale per l'Italia (interezza penisola + isole)
export const ITALY_CENTER = [42.1, 12.8];
export const ITALY_BOUNDS = [
  [35.4, 6.6],  // Sud-Ovest (Lampedusa / Canale di Sicilia)
  [47.3, 18.6]   // Nord-Est (Alpi Giulie / Friuli)
];

export function initMap(containerId = 'gis-map') {
  const map = L.map(containerId, {
    center: ITALY_CENTER,
    zoom: 6,
    minZoom: 5,
    maxZoom: 20,
    maxBounds: [[34.0, 5.0], [48.5, 20.5]], // Impedisce di navigare fuori dall'Italia
    zoomControl: false // Riposizionabile
  });

  // Riposiziona zoom in alto a destra
  L.control.zoom({ position: 'topright' }).addTo(map);

  // --- DEFINIZIONE LAYER BASEMAP ---

  // 1. CHIARA TECNICA (Ultra leggibile, zero rumore)
  const layerLightBase = L.tileLayer('https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png', {
    subdomains: 'abcd',
    maxZoom: 20,
    attribution: '© CARTO, © OpenStreetMap'
  });
  const layerLightLabels = L.tileLayer('https://{s}.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}{r}.png', {
    subdomains: 'abcd',
    maxZoom: 20,
    zIndex: 600 // Sempre sopra le particelle
  });
  const basemapLight = L.layerGroup([layerLightBase, layerLightLabels]);

  // 2. DARK SLATE PRO (Alto contrasto, stile intelligence)
  const layerDarkBase = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
    maxZoom: 19,
    attribution: '© ESRI ArcGIS'
  });
  const layerDarkLabels = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}', {
    maxZoom: 19,
    zIndex: 600
  });
  const basemapDark = L.layerGroup([layerDarkBase, layerDarkLabels]);

  // 3. SATELLITE HD IBRIDO (Foto aerea ad alta nitidezza + toponimi puliti)
  const layerSatellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    maxZoom: 19,
    attribution: '© ESRI World Imagery'
  });
  const layerSatLabels = L.tileLayer('https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}', {
    maxZoom: 19,
    zIndex: 600
  });
  const basemapSatellite = L.layerGroup([layerSatellite, layerSatLabels]);

  // Imposta Dark di default con filtro CSS
  basemapDark.addTo(map);
  const tilePane = map.getPane('tilePane');
  if (tilePane) {
    tilePane.classList.add('basemap-dark');
  }

  // --- GESTORE CAMBIO BASEMAP ---
  window.switchBasemap = function(mode) {
    if (tilePane) {
      tilePane.classList.remove('basemap-light', 'basemap-dark', 'basemap-satellite');
    }
    map.removeLayer(basemapLight);
    map.removeLayer(basemapDark);
    map.removeLayer(basemapSatellite);

    if (mode === 'light') {
      basemapLight.addTo(map);
      if (tilePane) tilePane.classList.add('basemap-light');
    } else if (mode === 'satellite') {
      basemapSatellite.addTo(map);
      if (tilePane) tilePane.classList.add('basemap-satellite');
    } else {
      basemapDark.addTo(map);
      if (tilePane) tilePane.classList.add('basemap-dark');
    }

    // Aggiorna classi bottoni
    document.querySelectorAll('.btn-basemap').forEach(b => b.classList.remove('active'));
    const btn = document.getElementById(`btn-basemap-${mode}`);
    if (btn) btn.classList.add('active');
  };

  // --- CARICAMENTO CONFINI REGIONALI ISTAT ---
  caricaConfiniRegionali(map);

  return map;
}

// Layer vettoriale dei confini regionali per dare struttura geometrica chiara all'Italia
export async function caricaConfiniRegionali(map) {
  try {
    const res = await fetch('https://raw.githubusercontent.com/openpolis/geojson-italy/master/geojson/limits_IT_regions.geojson');
    if (!res.ok) return;
    const geojsonData = await res.json();

    L.geoJSON(geojsonData, {
      style: {
        className: 'regioni-border-layer'
      },
      onEachFeature: (feature, layer) => {
        if (feature.properties && feature.properties.reg_name) {
          layer.bindTooltip(feature.properties.reg_name.toUpperCase(), {
            sticky: true,
            className: 'tooltip-regione-istat'
          });
        }
      }
    }).addTo(map);
  } catch (err) {
    console.warn("Impossibile caricare i confini regionali ISTAT:", err);
  }
}
