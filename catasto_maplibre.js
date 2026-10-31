/**
 * catasto_maplibre.js - Integrazione WMS AdE per MapLibre GL
 */

export function addCatastoWmsLayer(map) {
  // URL BBOX template compatibile con MapLibre GL
  const wmsUrl =
    'https://wms.cartografia.agenziaentrate.gov.it/inspire/wms/ows?' +
    'SERVICE=WMS&REQUEST=GetMap&LAYERS=CP.CadastralParcel,CP.CadastralZoning,BU.Building' +
    '&STYLES=&FORMAT=image/png&TRANSPARENT=TRUE&VERSION=1.3.0' +
    '&WIDTH=256&HEIGHT=256&CRS=EPSG:3857' +
    '&BBOX={bbox-epsg-3857}';

  if (!map.getSource('catasto-ade-source')) {
    map.addSource('catasto-ade-source', {
      type: 'raster',
      tiles: [wmsUrl],
      tileSize: 256,
      minzoom: 15,
      maxzoom: 22,
      attribution: '© Agenzia delle Entrate - Dati Catastali'
    });

    map.addLayer({
      id: 'catasto-ade-layer',
      type: 'raster',
      source: 'catasto-ade-source',
      layout: {
        visibility: 'none' // Nascosto di default, attivabile via switch
      },
      paint: {
        'raster-opacity': 0.85,
        'raster-fade-duration': 150
      }
    });
  }
}

// Funzione helper per commutare visibilità e opacità
export function setCatastoVisibility(map, visible) {
  if (map.getLayer('catasto-ade-layer')) {
    map.setLayoutProperty(
      'catasto-ade-layer',
      'visibility',
      visible ? 'visible' : 'none'
    );
  }
}

export function setCatastoOpacity(map, opacityValue) {
  if (map.getLayer('catasto-ade-layer')) {
    map.setPaintProperty('catasto-ade-layer', 'raster-opacity', opacityValue);
  }
}
