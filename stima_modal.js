/**
 * stima_modal.js - Controller Modale e Calcolatore Delta DPR 327/2001
 */

const API_STIMA_ENDPOINT = "/api/stima/delta-recuperabile";

export function initStimaModal() {
  const modal = document.getElementById("modal-stima");
  const btnOpen = document.getElementById("btn-open-stima");
  const btnClose = document.getElementById("btn-close-stima");
  const btnCalcola = document.getElementById("btn-calcola-delta");
  const form = document.getElementById("form-stima");

  if (!modal || !btnOpen) return;

  // 1. Apertura e Chiusura
  btnOpen.addEventListener("click", () => {
    modal.style.display = "flex";
    eseguiCalcoloDelta();
  });

  if (btnClose) {
    btnClose.addEventListener("click", () => {
      modal.style.display = "none";
    });
  }

  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && modal.style.display === "flex") {
      modal.style.display = "none";
    }
  });

  // Chiusura al click fuori dal perimetro della finestra
  modal.addEventListener("click", (e) => {
    if (e.target === modal) modal.style.display = "none";
  });

  // 2. Event Listeners per Ricalcolo Automatico Reattivo
  if (form) {
    form.querySelectorAll("input, select").forEach((elem) => {
      elem.addEventListener("input", eseguiCalcoloDelta);
      elem.addEventListener("change", eseguiCalcoloDelta);
    });
  }

  if (btnCalcola) {
    btnCalcola.addEventListener("click", eseguiCalcoloDelta);
  }

  // 3. Esecuzione Calcolo via API FastAPI
  async function eseguiCalcoloDelta() {
    const payload = {
      superficie_mq: parseFloat(document.getElementById("inp-superficie")?.value) || 0,
      destinazione: document.getElementById("inp-destinazione")?.value || "agricola",
      intervento: document.getElementById("inp-intervento")?.value || "asservimento",
      offerta_unitaria_ente: parseFloat(document.getElementById("inp-offerta-ente")?.value) || 0,
      valore_venale_mercato_mq: parseFloat(document.getElementById("inp-valore-mercato")?.value) || 0,
      saggio_deprezzamento_asservimento:
        (parseFloat(document.getElementById("inp-deprezzamento-ass")?.value) || 50) / 100,
      deprezzamento_relitto_euro: parseFloat(document.getElementById("inp-danno-relitto")?.value) || 0,
      valore_soprassuoli_euro: parseFloat(document.getElementById("inp-soprassuoli")?.value) || 0,
      frutti_pendenti_euro: parseFloat(document.getElementById("inp-frutti")?.value) || 0,
      is_coltivatore_diretto_o_iap: Boolean(document.getElementById("chk-coltivatore-diretto")?.checked),
      vam_tabellare_mq: parseFloat(document.getElementById("inp-vam")?.value) || 0,
      adesione_cessione_volontaria: Boolean(document.getElementById("chk-cessione-volontaria")?.checked),
      anni_occupazione: 1.0
    };

    try {
      const response = await fetch(API_STIMA_ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!response.ok) throw new Error("Errore nel calcolo del Delta");

      const data = await response.json();
      renderRisultati(data);
    } catch (err) {
      console.warn("Fallback su calcolo locale:", err);
      // Fallback deterministico locale
      renderRisultatiLocale(payload);
    }
  }

  // Formattatore Valuta IT
  const formatEuro = (num) =>
    new Intl.NumberFormat("it-IT", { style: "currency", currency: "EUR" }).format(num);

  function renderRisultati(data) {
    const elDelta = document.getElementById("res-delta-valore");
    const elPerc = document.getElementById("res-delta-percentuale");
    const elTotEnte = document.getElementById("res-tot-ente");
    const elTotPerizia = document.getElementById("res-tot-perizia");
    const elSuolo = document.getElementById("res-dett-suolo");
    const elRelitto = document.getElementById("res-dett-relitto");
    const elSoprassuoli = document.getElementById("res-dett-soprassuoli");
    const elCD = document.getElementById("res-dett-cd");
    const elCessione = document.getElementById("res-dett-cessione");
    const elCompenso = document.getElementById("res-compenso-tecnico");

    if (elDelta) elDelta.innerText = formatEuro(data.delta_recuperabile);
    if (elPerc) elPerc.innerText = `+${data.percentuale_recupero.toFixed(1)}% rispetto all'offerta`;
    if (elTotEnte) elTotEnte.innerText = formatEuro(data.totale_offerta_ente);
    if (elTotPerizia) elTotPerizia.innerText = formatEuro(data.totale_stima_peritale);

    if (elSuolo) elSuolo.innerText = formatEuro(data.dettaglio_calcolo?.indennita_suolo_reale || 0);
    if (elRelitto) elRelitto.innerText = formatEuro(data.dettaglio_calcolo?.deprezzamento_relitto_art33 || 0);
    if (elSoprassuoli) elSoprassuoli.innerText = formatEuro(data.dettaglio_calcolo?.soprassuoli_e_frutti || 0);
    if (elCD) elCD.innerText = formatEuro(data.dettaglio_calcolo?.indennita_aggiuntiva_cd_iap_art40 || 0);
    if (elCessione) elCessione.innerText = formatEuro(data.dettaglio_calcolo?.maggiorazione_cessione_art45 || 0);
    if (elCompenso) elCompenso.innerText = formatEuro(data.base_onorario_tecnico_consigliato || 0);
  }

  function renderRisultatiLocale(p) {
    const offEnte = p.superficie_mq * p.offerta_unitaria_ente;
    let suoloReale = p.superficie_mq * p.valore_venale_mercato_mq;
    if (p.intervento === "asservimento") {
      suoloReale *= p.saggio_deprezzamento_asservimento;
    }
    const relitto = (p.intervento === "esproprio_parziale" || p.intervento === "asservimento") ? p.deprezzamento_relitto_euro : 0;
    const soprassuoli = p.valore_soprassuoli_euro + p.frutti_pendenti_euro;
    let cdVal = 0;
    if (p.is_coltivatore_diretto_o_iap && p.destinazione === "agricola") {
      cdVal = p.vam_tabellare_mq > 0 ? (p.vam_tabellare_mq * p.superficie_mq) : (suoloReale * 0.5);
    }
    let cessione = 0;
    if (p.adesione_cessione_volontaria) {
      cessione = p.destinazione === "agricola" ? (p.is_coltivatore_diretto_o_iap ? suoloReale * 2 : suoloReale * 0.5) : (suoloReale * 0.1);
    }
    const totPerizia = suoloReale + relitto + soprassuoli + cdVal + cessione;
    const delta = Math.max(0, totPerizia - offEnte);
    const perc = offEnte > 0 ? (delta / offEnte * 100) : 100;

    renderRisultati({
      totale_offerta_ente: offEnte,
      totale_stima_peritale: totPerizia,
      delta_recuperabile: delta,
      percentuale_recupero: perc,
      dettaglio_calcolo: {
        indennita_suolo_reale: suoloReale,
        deprezzamento_relitto_art33: relitto,
        soprassuoli_e_frutti: soprassuoli,
        indennita_aggiuntiva_cd_iap_art40: cdVal,
        maggiorazione_cessione_art45: cessione
      },
      base_onorario_tecnico_consigliato: Math.round(delta * 0.10)
    });
  }

  // Esegui primo calcolo se aperto
  eseguiCalcoloDelta();
  window.eseguiCalcoloDelta = eseguiCalcoloDelta;
}
