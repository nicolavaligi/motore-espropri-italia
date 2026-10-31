import json
import sqlite3
from pathlib import Path

BASE_OPERE = [
  {
    "slug": "SIMICO-MICO-2026-VALTELLINA-SS38",
    "cup": "B39H21000120001",
    "titolo": "S.S. 38 Variante di Tirano e Nodo di Bormio - Adeguamento e svincoli Olimpiadi 2026",
    "ente": "SIMICO S.p.A. / ANAS Lombardia",
    "regione": "Lombardia",
    "provincia": "SO",
    "comune": "Tirano, Villa di Tirano",
    "importo_eur": 184500000,
    "data_pubblicazione": "2026-10-18",
    "stato_opera": "AVANZATA_SENZA_ELENCO",
    "maturity_score": 5,
    "maturity_signals": {
      "conferenza_servizi_chiusa": True,
      "progetto_def_esec_approvato": True,
      "pubblica_utilita_emessa": True,
      "cup_attivo_finanziamento": True,
      "avviso_art11_dpr327": True,
      "vincolo_preordinato_pgt": False,
      "bando_aggiudicazione_anac": False
    },
    "azione": {
      "verbo": "Pre-acquisizione proprietari su deposito provvisorio",
      "priorita": "alta",
      "giorni_residui": 18,
      "elenco_non_pubblico": True,
      "deposito_presso": "Ufficio Espropri SIMICO - Sede operativa Sondrio, previo appuntamento pec@simico.it"
    },
    "geo": { "lat": 46.2155, "lng": 10.1742 },
    "fonte_url": "https://simico.it/atti-pubblicati-espropri-2026",
    "ditte": []
  },
  {
    "slug": "RFI-TAV-VR-PD-SUB-TRATTA-VICENZA",
    "cup": "F81B18000450009",
    "titolo": "Linea AV/AC Verona-Padova: Tratta 2° Lotto Costruttivo attraversamento Vicenza e opere connesse",
    "ente": "RFI / Italferr S.p.A.",
    "regione": "Veneto",
    "provincia": "VI",
    "comune": "Vicenza, Altavilla Vicentina",
    "importo_eur": 890000000,
    "data_pubblicazione": "2026-10-12",
    "stato_opera": "ELENCO_PUBBLICATO",
    "maturity_score": 6,
    "maturity_signals": {
      "conferenza_servizi_chiusa": True,
      "progetto_def_esec_approvato": True,
      "pubblica_utilita_emessa": True,
      "cup_attivo_finanziamento": True,
      "avviso_art11_dpr327": True,
      "vincolo_preordinato_pgt": True,
      "bando_aggiudicazione_anac": False
    },
    "azione": {
      "verbo": "Opposizione stima provvisoria e perizie tecniche concordate",
      "priorita": "alta",
      "giorni_residui": 24,
      "elenco_non_pubblico": False
    },
    "geo": { "lat": 45.5455, "lng": 11.5354 },
    "fonte_url": "https://www.rfi.it/it/progetti-e-interventi/espropri.html",
    "ditte": [
      { "intestatario": "Zanella S.r.l. Costruzioni", "comune": "Vicenza", "foglio": "34", "mappali": "128, 129 sub 2", "sup_mq": 4850, "indennita": 145000, "delta": True },
      { "intestatario": "Rossi Mario & Rossi Giuseppe", "comune": "Vicenza", "foglio": "34", "mappali": "140", "sup_mq": 1200, "indennita": 34000, "delta": False },
      { "intestatario": "Agricola Berica di Benetti F.lli", "comune": "Altavilla Vic.", "foglio": "12", "mappali": "88, 91, 95", "sup_mq": 18400, "indennita": 198000, "delta": True },
      { "intestatario": "Immobiliare San Felice S.a.s.", "comune": "Vicenza", "foglio": "35", "mappali": "210, 212", "sup_mq": 3100, "indennita": 89000, "delta": False }
    ]
  },
  {
    "slug": "AUTOVIE-A4-TERZA-CORSIA-SAN-DONA-PORTOGRUARO",
    "cup": "C21B20000150003",
    "titolo": "Autostrada A4 Venezia-Trieste: Realizzazione Terza Corsia tratta San Donà - Portogruaro",
    "ente": "Autostrade Alto Adriatico S.p.A.",
    "regione": "Veneto",
    "provincia": "VE",
    "comune": "San Donà di Piave, Cessalto, Portogruaro",
    "importo_eur": 420000000,
    "data_pubblicazione": "2026-09-28",
    "stato_opera": "AVANZATA_SENZA_ELENCO",
    "maturity_score": 4,
    "maturity_signals": {
      "conferenza_servizi_chiusa": True,
      "progetto_def_esec_approvato": True,
      "pubblica_utilita_emessa": True,
      "cup_attivo_finanziamento": True,
      "avviso_art11_dpr327": False,
      "vincolo_preordinato_pgt": False,
      "bando_aggiudicazione_anac": False
    },
    "azione": {
      "verbo": "Target pre-acquisizione: monitorare pubblicazione piano particellare",
      "priorita": "alta",
      "giorni_residui": None,
      "elenco_non_pubblico": True,
      "deposito_presso": "Ufficio del Commissario Delegato A4 c/o Palmanova"
    },
    "geo": { "lat": 45.6322, "lng": 12.5644 },
    "fonte_url": "https://www.autostradealtoadriatico.it/espropri",
    "ditte": []
  },
  {
    "slug": "ANAS-LOMBARDIA-VARIANTE-PALADINA-SEDRINA-SS470",
    "cup": "E81B23000670002",
    "titolo": "S.S. 470 della Valle Brembana: Variante di Paladina e sistemazione viabilità all'incrocio di Almè",
    "ente": "ANAS Lombardia / Provincia di Bergamo",
    "regione": "Lombardia",
    "provincia": "BG",
    "comune": "Paladina, Almè, Villa d'Almè",
    "importo_eur": 65000000,
    "data_pubblicazione": "2026-10-25",
    "stato_opera": "AVANZATA_SENZA_ELENCO",
    "maturity_score": 4,
    "maturity_signals": {
      "conferenza_servizi_chiusa": True,
      "progetto_def_esec_approvato": True,
      "pubblica_utilita_emessa": False,
      "cup_attivo_finanziamento": True,
      "avviso_art11_dpr327": True,
      "vincolo_preordinato_pgt": False,
      "bando_aggiudicazione_anac": False
    },
    "azione": {
      "verbo": "Ingaggio preventivo proprietari terreni adiacenti sedime",
      "priorita": "alta",
      "giorni_residui": 28,
      "elenco_non_pubblico": True,
      "deposito_presso": "Uff. Tecnico Comune di Paladina e sede ANAS Milano Via Filzi"
    },
    "geo": { "lat": 45.7289, "lng": 9.6133 },
    "fonte_url": "https://stradeanas.it/it/lombardia-espropri-paladina",
    "ditte": []
  },
  {
    "slug": "EMILIA-CISPADANA-AUTOSTRADA-REGIONALE",
    "cup": "D41B19000220007",
    "titolo": "Autostrada Regionale Cispadana: Collegamento casello A22 Rolo-Reggiolo con A13 Ferrara Sud",
    "ente": "Autostrada del Brennero / ARC S.p.A.",
    "regione": "Emilia-Romagna",
    "provincia": "RE",
    "comune": "Guastalla, Rolo, Cento, Mirandola",
    "importo_eur": 1300000000,
    "data_pubblicazione": "2026-08-14",
    "stato_opera": "ELENCO_PUBBLICATO",
    "maturity_score": 6,
    "maturity_signals": {
      "conferenza_servizi_chiusa": True,
      "progetto_def_esec_approvato": True,
      "pubblica_utilita_emessa": True,
      "cup_attivo_finanziamento": True,
      "avviso_art11_dpr327": True,
      "vincolo_preordinato_pgt": True,
      "bando_aggiudicazione_anac": False
    },
    "azione": {
      "verbo": "Perizie espropriative stima VAM / Valore di Mercato",
      "priorita": "media",
      "giorni_residui": 0,
      "elenco_non_pubblico": False
    },
    "geo": { "lat": 44.8872, "lng": 11.0667 },
    "fonte_url": "https://bur.regione.emilia-romagna.it",
    "ditte": [
      { "intestatario": "Società Agricola Mirandolese S.s.", "comune": "Mirandola", "foglio": "45", "mappali": "12, 14, 15", "sup_mq": 32400, "indennita": 310000, "delta": True },
      { "intestatario": "Golinelli Sergio & Andrea", "comune": "Cento", "foglio": "18", "mappali": "202, 204", "sup_mq": 8700, "indennita": 74000, "delta": False },
      { "intestatario": "Manifattura Tessile Emiliana S.p.A.", "comune": "Reggiolo", "foglio": "9", "mappali": "55", "sup_mq": 4100, "indennita": 165000, "delta": True }
    ]
  },
  {
    "slug": "PIEMONTE-TANGENZIALE-EST-TORINO-CONCESSIONE",
    "cup": "G11B22000550001",
    "titolo": "Tangenziale Est di Torino: Connessione tra A4 Torino-Milano e A21 Torino-Piacenza",
    "ente": "Regione Piemonte / Città Metropolitana Torino",
    "regione": "Piemonte",
    "provincia": "TO",
    "comune": "Chivasso, San Mauro Torinese, Moncalieri",
    "importo_eur": 780000000,
    "data_pubblicazione": "2026-09-02",
    "stato_opera": "PRELIMINARE",
    "maturity_score": 2,
    "maturity_signals": {
      "conferenza_servizi_chiusa": False,
      "progetto_def_esec_approvato": False,
      "pubblica_utilita_emessa": False,
      "cup_attivo_finanziamento": True,
      "avviso_art11_dpr327": True,
      "vincolo_preordinato_pgt": False,
      "bando_aggiudicazione_anac": False
    },
    "azione": {
      "verbo": "Watchlist - In attesa di conclusione Conferenza Servizi",
      "priorita": "bassa",
      "giorni_residui": None,
      "elenco_non_pubblico": False
    },
    "geo": { "lat": 45.1033, "lng": 7.7850 },
    "fonte_url": "https://www.regione.piemonte.it/bandi",
    "ditte": []
  },
  {
    "slug": "LIGURIA-NODODE-GENOVA-POTENZIAMENTO-VOLTRI-BRIGNOLE",
    "cup": "J31B15000210008",
    "titolo": "Potenziamento infrastrutturale nodo ferroviario di Genova: Tratta Voltri - Sampierdarena - Brignole",
    "ente": "RFI S.p.A. / Italferr",
    "regione": "Liguria",
    "provincia": "GE",
    "comune": "Genova",
    "importo_eur": 540000000,
    "data_pubblicazione": "2026-07-21",
    "stato_opera": "CHIUSA",
    "maturity_score": 7,
    "maturity_signals": {
      "conferenza_servizi_chiusa": True,
      "progetto_def_esec_approvato": True,
      "pubblica_utilita_emessa": True,
      "cup_attivo_finanziamento": True,
      "avviso_art11_dpr327": True,
      "vincolo_preordinato_pgt": True,
      "bando_aggiudicazione_anac": True
    },
    "azione": {
      "verbo": "Assistenza per svincolo indennità depositate presso Cassa Depositi e Prestiti",
      "priorita": "media",
      "giorni_residui": 0,
      "elenco_non_pubblico": False
    },
    "geo": { "lat": 44.4142, "lng": 8.9132 },
    "fonte_url": "https://www.commissari.mit.gov.it/nodo-genova",
    "ditte": []
  }
]

# Aggiungiamo anche Dervio dal DB locale espropri_radar.db
db_path = Path("/Users/houdinick/MyIP_Vault/02_Blueprints/espropri-intelligence-db/espropri_radar.db")
if db_path.exists():
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT comune_nome, foglio, numero_particella, ditta_intestataria, 
               superficie_occupata_mq, indennita_provvisoria_stimata
        FROM particelle_esproprio
        LIMIT 30
    """)
    rows = cur.fetchall()
    ditte_dervio = []
    tot_indennita = 0
    for r in rows:
        comune, foglio, part, ditta, sup, ind = r
        ditta_clean = ditta.split(' nato')[0].split(' con sede')[0].strip() if ditta else "Proprietario Privato"
        ind_val = round(float(ind), 2) if ind else 0
        tot_indennita += ind_val
        ditte_dervio.append({
            "intestatario": ditta_clean[:45],
            "comune": comune.title() if comune else "Dervio",
            "foglio": str(foglio),
            "mappali": str(part),
            "sup_mq": int(sup) if sup else 0,
            "indennita": int(ind_val),
            "delta": ind_val > 5000
        })
    conn.close()

    dervio_opera = {
        "slug": "REGIONE-LOMBARDIA-DERVIO-IDRAULICA-LC",
        "cup": "C12C24000100002",
        "titolo": "Interventi di mitigazione idraulica e viabilità di accesso — Comune di Dervio (LC)",
        "ente": "Regione Lombardia / Comune di Dervio",
        "regione": "Lombardia",
        "provincia": "LC",
        "comune": "Dervio",
        "importo_eur": 4800000,
        "data_pubblicazione": "2026-10-29",
        "stato_opera": "ELENCO_PUBBLICATO",
        "maturity_score": 6,
        "maturity_signals": {
            "conferenza_servizi_chiusa": True,
            "progetto_def_esec_approvato": True,
            "pubblica_utilita_emessa": True,
            "cup_attivo_finanziamento": True,
            "avviso_art11_dpr327": True,
            "vincolo_preordinato_pgt": True,
            "bando_aggiudicazione_anac": False
        },
        "azione": {
            "verbo": "Assistenza tecnica stima provvisoria e perizie D.P.R. 327/2001",
            "priorita": "alta",
            "giorni_residui": 29,
            "elenco_non_pubblico": False
        },
        "geo": { "lat": 46.0772, "lng": 9.3061 },
        "fonte_url": "https://www.comune.dervio.lc.it",
        "ditte": ditte_dervio
    }
    BASE_OPERE.insert(1, dervio_opera)

out_file = Path("/Users/houdinick/motore-espropri-italia/data/opere.json")
out_file.write_text(json.dumps(BASE_OPERE, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Salvato con successo {len(BASE_OPERE)} opere in {out_file}")
