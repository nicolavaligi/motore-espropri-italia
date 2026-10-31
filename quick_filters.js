/**
 * quick_filters.js - Gestione Filtri Rapidi & Telemetria Marker
 */

import { createOperaMarker } from './markers.js';

export class EspropriFilterController {
  constructor(map, opereData, markerGroup) {
    this.map = map;
    this.opere = opereData;
    this.markerGroup = markerGroup; // L.layerGroup o L.featureGroup
    this.markerMap = new Map();     // slug -> { opera, marker }
    this.currentFilter = 'all';

    this.initMarkers();
    this.bindToolbarButtons();
    this.updateKpiCounters();
  }

  initMarkers() {
    this.markerGroup.clearLayers();
    this.markerMap.clear();

    this.opere.forEach(opera => {
      const marker = createOperaMarker(opera, (selectedOpera) => {
        if (window.openOperaFlyout) {
          window.openOperaFlyout(selectedOpera);
        } else if (marker.getPopup()) {
          marker.openPopup();
        }
      });
      
      if (marker) {
        this.markerGroup.addLayer(marker);
        this.markerMap.set(opera.slug, { opera, marker });
      }
    });
  }

  bindToolbarButtons() {
    const btnAll = document.getElementById('btn-filter-all');
    const btnPda = document.getElementById('btn-filter-pda');
    const btnWeek = document.getElementById('btn-filter-settimana');

    if (btnAll) {
      btnAll.addEventListener('click', () => this.applyFilter('all', btnAll));
    }
    if (btnPda) {
      btnPda.addEventListener('click', () => this.applyFilter('pda', btnPda));
    }
    if (btnWeek) {
      btnWeek.addEventListener('click', () => this.applyFilter('settimana', btnWeek));
    }
  }

  applyFilter(filterType, activeBtn) {
    this.currentFilter = filterType;

    // Gestione stato attivo visivo sui pulsanti della toolbar
    document.querySelectorAll('.btn-toolbar-filter').forEach(b => b.classList.remove('active'));
    if (activeBtn) activeBtn.classList.add('active');

    let visibleCount = 0;
    const bounds = [];

    this.markerMap.forEach(({ opera, marker }) => {
      let match = true;
      const particelle = opera.particellare || opera.particelle || opera.ditte || [];

      if (filterType === 'pda') {
        // Mostra solo se ha un piano particellare con elenco ditte reale
        match = Boolean(particelle.length > 0 || opera.has_pda);
      } else if (filterType === 'settimana') {
        // Mostra solo se i termini perentori scadono entro 7 giorni
        match = (opera.giorni_residui !== undefined && opera.giorni_residui <= 7 && opera.giorni_residui >= 0) || Boolean(opera.settimana_corrente);
      }

      if (match) {
        if (!this.markerGroup.hasLayer(marker)) {
          this.markerGroup.addLayer(marker);
        }
        bounds.push(marker.getLatLng());
        visibleCount++;
      } else {
        if (this.markerGroup.hasLayer(marker)) {
          this.markerGroup.removeLayer(marker);
        }
      }
    });

    // Auto-fit vista della mappa sulle opere filtrate (se presenti)
    if (bounds.length > 0) {
      this.map.flyToBounds(bounds, { padding: [50, 50], maxZoom: 12, duration: 0.8 });
    }

    this.updateKpiCounters(visibleCount);
  }

  updateKpiCounters(customVisibleCount = null) {
    const totalCount = this.opere.length;
    const pdaCount = this.opere.filter(o => (o.particellare && o.particellare.length > 0) || (o.ditte && o.ditte.length > 0) || o.has_pda).length;
    const weekCount = this.opere.filter(o => (o.giorni_residui !== undefined && o.giorni_residui <= 7 && o.giorni_residui >= 0) || o.settimana_corrente).length;
    const visible = customVisibleCount !== null ? customVisibleCount : totalCount;

    // Aggiornamento telemetria DOM
    const elTot = document.getElementById('kpi-tot-opere');
    const elInVista = document.getElementById('kpi-in-vista');
    const elPda = document.getElementById('kpi-pda');
    const elWeek = document.getElementById('kpi-scadenza-settimana');

    if (elTot) elTot.innerText = totalCount;
    if (elInVista) elInVista.innerText = visible;
    if (elPda) elPda.innerText = pdaCount;
    if (elWeek) elWeek.innerText = weekCount;
  }
}
