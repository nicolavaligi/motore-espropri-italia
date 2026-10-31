/**
 * particella_bridge.js - Connessione Geometria/Tabella -> Stima Delta DPR 327/2001
 */

/**
 * Normalizza e precarica i dati catastali nel form della modale
 * @param {Object} p - Oggetto particella catastale
 * @param {Object} contestoOpera - Metadati dell'opera (titolo opera, ente promotore, ecc.)
 */
export function innescaCalcoloDaParticella(p, contestoOpera = {}) {
  const modal = document.getElementById('modal-stima');
  if (!modal) return;

  // 1. Estrazione e sanitizzazione delle superfici
  const supEsproprio = parseFloat(p.superficie_occupata || p.superfici_mq?.esproprio || p.sup_mq || 0);
  const supAsservimento = parseFloat(p.superfici_mq?.asservimento || 0);
  const supTotaleMq = supEsproprio > 0 ? supEsproprio : (supAsservimento > 0 ? supAsservimento : 1000);

  // 2. Determinazione tipologia d'intervento automatica
  const inpIntervento = document.getElementById('inp-intervento');
  if (inpIntervento) {
    if (supAsservimento > 0 && supEsproprio === 0) {
      inpIntervento.value = 'asservimento';
    } else if (p.esproprio_parziale) {
      inpIntervento.value = 'esproprio_parziale';
    } else {
      inpIntervento.value = 'esproprio_totale';
    }
  }

  // 3. Compilazione dei campi form
  const setVal = (id, val) => {
    const el = document.getElementById(id);
    if (el && val !== undefined && val !== null) el.value = val;
  };

  setVal('inp-superficie', supTotaleMq);
  
  // Offerta Ente: se presente nel piano ditte, altrimenti valore tabellare prudenziale
  const offertaEnte = p.offerta_proposta_mq || p.indennita_unitaria || 4.50;
  setVal('inp-offerta-ente', offertaEnte);

  // Valore Venale di Mercato stimato per la zona (es. da quotazioni OMI regionali)
  const stimaMercatoZona = p.valore_mercato_stimato_mq || (offertaEnte * 3.5);
  setVal('inp-valore-mercato', Math.round(stimaMercatoZona * 10) / 10);

  // Soprassuoli noti e coltivatore diretto
  setVal('inp-soprassuoli', p.indennita_soprassuoli || 0);
  
  const chkCd = document.getElementById('chk-coltivatore-diretto');
  if (chkCd) {
    // Se la ditta è indicata come IAP/CD o persona fisica agricola
    chkCd.checked = Boolean(p.is_coltivatore_diretto || p.qualifica_professionale === 'CD');
  }

  // 4. Aggiorna l'header della modale con i riferimenti catastali esatti
  const subtitleEl = modal.querySelector('.modal-stima-header .subtitle');
  if (subtitleEl) {
    subtitleEl.innerHTML = `
      <b>Fg. ${p.foglio || '-'} Mapp. ${p.mappale || '-'}</b> 
      • Ditta: <i>${p.intestatario || 'Ditta non censita'}</i> 
      • Opera: ${contestoOpera.sigla || contestoOpera.cup || 'Infrastruttura'}
    `;
  }

  // 5. Apertura modale ed esecuzione calcolo immediato
  modal.style.display = 'flex';
  
  // Esegue il calcolo
  const btnCalcola = document.getElementById('btn-calcola-delta');
  if (btnCalcola) {
    btnCalcola.click();
  } else if (window.eseguiCalcoloDelta) {
    window.eseguiCalcoloDelta();
  }
}

/**
 * Rendering della tabella ditte all'interno del Tab 3
 */
export function generaTabellaDitteHtml(particelleList, operaData) {
  if (!particelleList || particelleList.length === 0) {
    return `<div class="empty-state" style="padding:16px; text-align:center; color:#94a3b8; font-size:11px;">Nessun piano particellare ditte depositato per quest'opera.</div>`;
  }

  let rows = particelleList.map((p, idx) => `
    <tr style="border-bottom:1px solid #1e293b;">
      <td style="padding:5px 6px; color:#38bdf8;"><b>Fg. ${p.foglio}</b></td>
      <td style="padding:5px 6px; color:#e2e8f0;"><b>Mapp. ${p.mappale}</b></td>
      <td style="padding:5px 6px; color:#f8fafc; max-width:140px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${p.intestatario || 'Ditta N.D.'}</td>
      <td style="padding:5px 6px; text-align:right; font-weight:600; color:#94a3b8;">${p.superficie_occupata || p.superfici_mq?.esproprio || p.sup_mq || 0} mq</td>
      <td style="padding:5px 6px; text-align:center;">
        <button 
          class="btn-row-stima" 
          onclick='window.innescaCalcoloParticellaByIndex(${idx})'
          style="background:#0284c7; color:#fff; border:none; padding:3px 7px; border-radius:4px; font-size:10px; font-weight:bold; cursor:pointer;"
          title="Apri calcolo delta indennità per questa particella">
          ⚖ Stima Delta
        </button>
      </td>
    </tr>
  `).join('');

  // Salva l'elenco in memoria per il binding click
  window._currentFlyoutParticelle = particelleList;
  window._currentFlyoutOpera = operaData;

  return `
    <table class="table-ditte-flyout" style="width:100%; font-size:10px; border-collapse:collapse; font-family:'JetBrains Mono',monospace;">
      <thead>
        <tr style="border-bottom:1px solid #334155; color:#94a3b8; background:#111827;">
          <th style="padding:5px 6px; text-align:left;">Foglio</th>
          <th style="padding:5px 6px; text-align:left;">Mappale</th>
          <th style="padding:5px 6px; text-align:left;">Intestatario</th>
          <th style="padding:5px 6px; text-align:right;">Sup.</th>
          <th style="padding:5px 6px; text-align:center;">Azione</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

// Handler globale per scatenare il calcolo dalla tabella
window.innescaCalcoloParticellaByIndex = function(idx) {
  const p = window._currentFlyoutParticelle?.[idx];
  const opera = window._currentFlyoutOpera || {};
  if (p) {
    innescaCalcoloDaParticella(p, opera);
  }
};
