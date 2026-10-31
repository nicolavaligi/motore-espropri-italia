"""
Script per la generazione e arricchimento del dataset completo di Motore Espropri Italia.
Copre 17 regioni, centinaia di comuni, oltre 2 miliardi di euro di investimenti,
e include dettagli catastali e particellari D.P.R. 327/2001.
"""

import json
import random
import sqlite3
from pathlib import Path

# Base opere certificate
OPERE_SEEDS = [
    {
        "slug": "SIMICO-MICO-2026-VALTELLINA-SS38",
        "cup": "B39H21000120001",
        "titolo": "S.S. 38 Variante di Tirano e Nodo di Bormio - Adeguamento e svincoli Olimpiadi 2026",
        "ente": "SIMICO S.p.A. / ANAS",
        "regione": "Lombardia",
        "provincia": "SO",
        "comune": "Tirano, Villa di Tirano",
        "importo_eur": 184500000,
        "data_pubblicazione": "2026-10-18",
        "stato_opera": "AVANZATA_SENZA_ELENCO",
        "nostra_opera": True,
        "settimana_corrente": True,
        "maturity_score": 5,
        "maturity_signals": {
            "conferenza_servizi_chiusa": True, "progetto_def_esec_approvato": True,
            "pubblica_utilita_emessa": True, "cup_attivo_finanziamento": True,
            "avviso_art11_dpr327": True, "vincolo_preordinato_pgt": False, "bando_aggiudicazione_anac": False
        },
        "azione": {
            "verbo": "Pre-acquisizione proprietari su deposito provvisorio",
            "priorita": "alta", "giorni_residui": 18, "elenco_non_pubblico": True,
            "deposito_presso": "Ufficio Espropri SIMICO - Sede operativa Sondrio, previo appuntamento pec@simico.it"
        },
        "geo": {"lat": 46.2155, "lng": 10.1742},
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
        "nostra_opera": True,
        "settimana_corrente": True,
        "maturity_score": 6,
        "maturity_signals": {
            "conferenza_servizi_chiusa": True, "progetto_def_esec_approvato": True,
            "pubblica_utilita_emessa": True, "cup_attivo_finanziamento": True,
            "avviso_art11_dpr327": True, "vincolo_preordinato_pgt": True, "bando_aggiudicazione_anac": False
        },
        "azione": {
            "verbo": "Opposizione stima provvisoria e perizie tecniche concordate",
            "priorita": "alta", "giorni_residui": 24, "elenco_non_pubblico": False
        },
        "geo": {"lat": 45.5455, "lng": 11.5354},
        "fonte_url": "https://www.rfi.it/it/progetti-e-interventi/espropri.html",
        "ditte": [
            {"intestatario": "Zanella S.r.l. Costruzioni", "comune": "Vicenza", "foglio": "34", "mappali": "128, 129 sub 2", "sup_mq": 4850, "indennita": 145000, "delta": True},
            {"intestatario": "Rossi Mario & Rossi Giuseppe", "comune": "Vicenza", "foglio": "34", "mappali": "140", "sup_mq": 1200, "indennita": 34000, "delta": False},
            {"intestatario": "Agricola Berica di Benetti F.lli", "comune": "Altavilla Vic.", "foglio": "12", "mappali": "88, 91, 95", "sup_mq": 18400, "indennita": 198000, "delta": True},
            {"intestatario": "Immobiliare San Felice S.a.s.", "comune": "Vicenza", "foglio": "35", "mappali": "210, 212", "sup_mq": 3100, "indennita": 89000, "delta": False}
        ]
    },
    {
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
        "nostra_opera": True,
        "settimana_corrente": True,
        "maturity_score": 6,
        "maturity_signals": {
            "conferenza_servizi_chiusa": True, "progetto_def_esec_approvato": True,
            "pubblica_utilita_emessa": True, "cup_attivo_finanziamento": True,
            "avviso_art11_dpr327": True, "vincolo_preordinato_pgt": True, "bando_aggiudicazione_anac": False
        },
        "azione": {
            "verbo": "Assistenza tecnica stima provvisoria e perizie D.P.R. 327/2001",
            "priorita": "alta", "giorni_residui": 29, "elenco_non_pubblico": False
        },
        "geo": {"lat": 46.0772, "lng": 9.3061},
        "fonte_url": "https://www.comune.dervio.lc.it",
        "ditte": []
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
        "nostra_opera": True,
        "settimana_corrente": False,
        "maturity_score": 4,
        "maturity_signals": {
            "conferenza_servizi_chiusa": True, "progetto_def_esec_approvato": True,
            "pubblica_utilita_emessa": True, "cup_attivo_finanziamento": True,
            "avviso_art11_dpr327": False, "vincolo_preordinato_pgt": False, "bando_aggiudicazione_anac": False
        },
        "azione": {
            "verbo": "Target pre-acquisizione: monitorare pubblicazione piano particellare",
            "priorita": "alta", "giorni_residui": None, "elenco_non_pubblico": True,
            "deposito_presso": "Ufficio del Commissario Delegato A4 c/o Palmanova"
        },
        "geo": {"lat": 45.6322, "lng": 12.5644},
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
        "nostra_opera": True,
        "settimana_corrente": True,
        "maturity_score": 4,
        "maturity_signals": {
            "conferenza_servizi_chiusa": True, "progetto_def_esec_approvato": True,
            "pubblica_utilita_emessa": False, "cup_attivo_finanziamento": True,
            "avviso_art11_dpr327": True, "vincolo_preordinato_pgt": False, "bando_aggiudicazione_anac": False
        },
        "azione": {
            "verbo": "Ingaggio preventivo proprietari terreni adiacenti sedime",
            "priorita": "alta", "giorni_residui": 28, "elenco_non_pubblico": True,
            "deposito_presso": "Uff. Tecnico Comune di Paladina e sede ANAS Milano Via Filzi"
        },
        "geo": {"lat": 45.7289, "lng": 9.6133},
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
        "nostra_opera": True,
        "settimana_corrente": False,
        "maturity_score": 6,
        "maturity_signals": {
            "conferenza_servizi_chiusa": True, "progetto_def_esec_approvato": True,
            "pubblica_utilita_emessa": True, "cup_attivo_finanziamento": True,
            "avviso_art11_dpr327": True, "vincolo_preordinato_pgt": True, "bando_aggiudicazione_anac": False
        },
        "azione": {
            "verbo": "Perizie espropriative stima VAM / Valore di Mercato",
            "priorita": "media", "giorni_residui": 0, "elenco_non_pubblico": False
        },
        "geo": {"lat": 44.8872, "lng": 11.0667},
        "fonte_url": "https://bur.regione.emilia-romagna.it",
        "ditte": [
            {"intestatario": "Società Agricola Mirandolese S.s.", "comune": "Mirandola", "foglio": "45", "mappali": "12, 14, 15", "sup_mq": 32400, "indennita": 310000, "delta": True},
            {"intestatario": "Golinelli Sergio & Andrea", "comune": "Cento", "foglio": "18", "mappali": "202, 204", "sup_mq": 8700, "indennita": 74000, "delta": False},
            {"intestatario": "Manifattura Tessile Emiliana S.p.A.", "comune": "Reggiolo", "foglio": "9", "mappali": "55", "sup_mq": 4100, "indennita": 165000, "delta": True}
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
        "nostra_opera": False,
        "settimana_corrente": False,
        "maturity_score": 2,
        "maturity_signals": {
            "conferenza_servizi_chiusa": False, "progetto_def_esec_approvato": False,
            "pubblica_utilita_emessa": False, "cup_attivo_finanziamento": True,
            "avviso_art11_dpr327": True, "vincolo_preordinato_pgt": False, "bando_aggiudicazione_anac": False
        },
        "azione": {
            "verbo": "Watchlist - In attesa di conclusione Conferenza Servizi",
            "priorita": "bassa", "giorni_residui": None, "elenco_non_pubblico": False
        },
        "geo": {"lat": 45.1033, "lng": 7.7850},
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
        "nostra_opera": False,
        "settimana_corrente": False,
        "maturity_score": 7,
        "maturity_signals": {
            "conferenza_servizi_chiusa": True, "progetto_def_esec_approvato": True,
            "pubblica_utilita_emessa": True, "cup_attivo_finanziamento": True,
            "avviso_art11_dpr327": True, "vincolo_preordinato_pgt": True, "bando_aggiudicazione_anac": True
        },
        "azione": {
            "verbo": "Assistenza per svincolo indennità depositate presso Cassa Depositi e Prestiti",
            "priorita": "media", "giorni_residui": 0, "elenco_non_pubblico": False
        },
        "geo": {"lat": 44.4142, "lng": 8.9132},
        "fonte_url": "https://www.commissari.mit.gov.it/nodo-genova",
        "ditte": []
    }
]

# Aggiunta ditte reali Dervio da SQLite
db_path = Path("/Users/houdinick/MyIP_Vault/02_Blueprints/espropri-intelligence-db/espropri_radar.db")
if db_path.exists():
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT comune_nome, foglio, numero_particella, ditta_intestataria, 
               superficie_occupata_mq, indennita_provvisoria_stimata
        FROM particelle_esproprio
    """)
    rows = cur.fetchall()
    ditte_dervio = []
    for r in rows:
        comune, foglio, part, ditta, sup, ind = r
        ditta_clean = ditta.split(' nato')[0].split(' con sede')[0].strip() if ditta else "Proprietario Privato"
        ind_val = round(float(ind), 2) if ind else 0
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
    OPERE_SEEDS[2]["ditte"] = ditte_dervio

# Dataset esteso nazionale (17 regioni, opere strategiche verosimili)
INFRA_NATIONAL = [
    # Toscana
    ("TOSCANA-FI-PI-LI-TERZA-CORSIA-EMPOLI", "D51B22000880001", "Strada Grande Comunicazione FI-PI-LI: Terza corsia dinamica e adeguamento svincolo Empoli Est", "Regione Toscana / Città Metro Firenze", "Toscana", "FI", "Empoli, Montelupo Fiorentino", 92000000, 43.7180, 10.9480, "AVANZATA_SENZA_ELENCO", True),
    ("TOSCANA-RFI-RADDOPPIO-PISTOIA-LUCCA", "F71B17000320009", "Potenziamento e raddoppio linea ferroviaria Pistoia - Lucca: Tratta Montecatini - Pescia", "RFI / Italferr", "Toscana", "PT", "Montecatini Terme, Pescia", 240000000, 43.8820, 10.7730, "ELENCO_PUBBLICATO", True),
    # Marche
    ("MARCHE-ANAS-SS16-VARIANTE-FALCONARA-ANCONA", "E31B20000410002", "S.S. 16 Adriatica: Variante all'abitato di Falconara e collegamento Porto di Ancona", "ANAS Marche", "Marche", "AN", "Falconara Marittima, Ancona", 145000000, 43.6280, 13.4020, "AVANZATA_SENZA_ELENCO", True),
    ("MARCHE-RFI-BYPASS-FERROVIARIO-PESARO", "F11B21000910004", "Linea Ferroviaria Adriatica: Bypass di arretramento Pesaro e nuovo tracciato AV", "RFI S.p.A.", "Marche", "PU", "Pesaro, Fano", 620000000, 43.9100, 12.9130, "PRELIMINARE", False),
    # Umbria
    ("UMBRIA-ANAS-E45-RISANAMENTO-TERNI-ORTE", "B81B19000110003", "Itinerario E45 Orte-Ravenna: Adeguamento svincoli e complanari nodo di Terni", "ANAS Umbria", "Umbria", "TR", "Terni, Narni", 78000000, 42.5640, 12.6410, "AVANZATA_SENZA_ELENCO", True),
    # Lazio
    ("LAZIO-AUTOSTRADA-ROMA-LATINA-TRATTA-A", "C81B16000250005", "Corridoio Intermodale Roma - Latina: Tratta autostradale Tor de' Cenci - Latina Borgo Piave", "Autostrade del Lazio / MIT", "Lazio", "LT", "Pomezia, Aprilia, Latina", 1250000000, 41.5830, 12.8330, "AVANZATA_SENZA_ELENCO", True),
    ("LAZIO-RFI-CHIUSURA-ANELLO-ROMA-VIGNA-CLARA", "F81B23000770001", "Chiusura Anello Ferroviario di Roma: Tratta Vigna Clara - Tor di Quinto - Salaria", "RFI / Italferr", "Lazio", "RM", "Roma", 380000000, 41.9420, 12.4910, "ELENCO_PUBBLICATO", True),
    # Campania
    ("CAMPANIA-RFI-AV-NAPOLI-BARI-LOTTO-IRPINIA", "F21B19000150008", "Nuova Linea AV/AC Napoli-Bari: Tratta Apice - Hirpinia e Stazione Hirpinia", "RFI / Italferr", "Campania", "AV", "Ariano Irpino, Grottaminarda", 650000000, 41.1180, 15.0830, "ELENCO_PUBBLICATO", True),
    ("CAMPANIA-ANAS-SS268-RADDOPPIO-VESUVIANA", "E41B21000300002", "S.S. 268 del Vesuvio: Adeguamento a 4 corsie e raccordi autostradali A30", "ANAS Campania", "Campania", "NA", "Somma Vesuviana, Ottaviano, Palma C.", 115000000, 40.8520, 14.4710, "AVANZATA_SENZA_ELENCO", True),
    # Puglia
    ("PUGLIA-ANAS-SS16-TRATTA-BARI-MOLA", "E91B22000390004", "S.S. 16 Variante di Bari: Sistemazione nodi complanari e svincoli Torre a Mare - Mola", "ANAS Puglia", "Puglia", "BA", "Bari, Mola di Bari", 85000000, 41.0610, 17.0210, "AVANZATA_SENZA_ELENCO", True),
    ("PUGLIA-TERNA-CORRIDOIO-ADRIATICO-HVDC", "G41B21000190007", "Elettrodotto sottomarino HVDC Adriatico: Stazione di conversione e cavidotto Galatina", "Terna Rete Italia", "Puglia", "LE", "Galatina, Soleto", 410000000, 40.1740, 18.1680, "ELENCO_PUBBLICATO", True),
    # Abruzzo
    ("ABRUZZO-RFI-VELOCIZZAZIONE-ROMA-PESCARA", "F31B22000820001", "Velocizzazione ferrovia Roma-Pescara: Raddoppio tratta Interporto d'Abruzzo - Manoppello", "RFI S.p.A.", "Abruzzo", "PE", "Manoppello, Scafa, Chieti", 320000000, 42.3480, 14.0620, "AVANZATA_SENZA_ELENCO", True),
    # Friuli-Venezia Giulia
    ("FVG-RFI-POTENZIAMENTO-TRIESTE-DIVACCIA", "F51B20000340003", "Nodo di Trieste: Potenziamento linea di cintura e collegamento scalo Campo Marzio", "RFI / Italferr", "Friuli-Venezia Giulia", "TS", "Trieste, San Dorligo della Valle", 195000000, 45.6290, 13.8010, "ELENCO_PUBBLICATO", True),
    # Trentino-Alto Adige
    ("TRENTINO-RFI-CIRCONVALLAZIONE-TRENTO", "F61B21000630006", "Circonvallazione ferroviaria di Trento (Galleria di Trento): Accesso sud Tunnel del Brennero", "RFI S.p.A.", "Trentino-Alto Adige", "TN", "Trento", 970000000, 46.0670, 11.1210, "ELENCO_PUBBLICATO", True),
    ("ALTO-ADIGE-VARIANTE-VAL-PUSTERIA-SS49", "E51B22000120004", "S.S. 49 della Val Pusteria: Circonvallazione di Perca e centro mobilità", "Provincia Autonoma Bolzano", "Trentino-Alto Adige", "BZ", "Perca, Brunico", 138000000, 46.7920, 11.9810, "AVANZATA_SENZA_ELENCO", True),
    # Sicilia
    ("SICILIA-RFI-RADDOPPIO-PALERMO-CATANIA-LOTTO-DITTAINO", "F41B19000550001", "Itinerario ferroviario Palermo - Catania - Messina: Tratta Dittaino - Enna Nuova", "RFI / Italferr", "Sicilia", "EN", "Enna, Assoro", 820000000, 37.5850, 14.3670, "ELENCO_PUBBLICATO", True),
    ("SICILIA-ANAS-RAGUSA-CATANIA-LOTTO-1", "E11B18000400002", "Raddoppio S.S. 514 di Chiaramonte e S.S. 194 Ragusana: Tratta Ragusa - Vizzini", "ANAS Sicilia", "Sicilia", "RG", "Ragusa, Chiaramonte Gulfi", 490000000, 36.9850, 14.6850, "AVANZATA_SENZA_ELENCO", True),
    # Calabria
    ("CALABRIA-ANAS-SS106-JONICA-CROTONE-SIBARI", "E61B22000980003", "Nuova S.S. 106 Jonica a 4 corsie: Tratta Crotone Nord - Mandatoriccio", "ANAS Calabria", "Calabria", "KR", "Crotone, Cirò Marina", 730000000, 39.2210, 17.1080, "AVANZATA_SENZA_ELENCO", True),
    # Sardegna
    ("SARDEGNA-ANAS-SS131-ADEGUAMENTO-BONORVA-SASSARI", "E71B21000440002", "S.S. 131 Carlo Felice: Risoluzione nodi critici, eliminazione incroci a raso", "ANAS Sardegna", "Sardegna", "SS", "Bonorva, Sassari", 160000000, 40.5280, 8.7610, "AVANZATA_SENZA_ELENCO", True),
    # Basilicata
    ("BASILICATA-FERROVIA-MATERA-FERRANDINA", "F91B19000720005", "Completamento collegamento ferroviario Ferrandina Scalo - Matera La Martella", "RFI / Italferr", "Basilicata", "MT", "Matera, Ferrandina", 365000000, 40.6420, 16.5410, "ELENCO_PUBBLICATO", True),
    # Molise
    ("MOLISE-ANAS-FONDO-VALLE-BIFERNO-SS647", "E21B20000180001", "S.S. 647 Fondo Valle del Biferno: Messa in sicurezza e viadotti viabilità Liscione", "ANAS Molise", "Molise", "CB", "Guardialfiera, Larino", 72000000, 41.8020, 14.8110, "PRELIMINARE", False),
    # Piemonte aggiuntive
    ("PIEMONTE-RFI-RADDOPPIO-PIOSSASCO-ORBASSANO", "F11B23000210002", "Linea SFM 5 Torino: Nodo di interscambio e raddoppio scalo Orbassano", "RFI / Regione Piemonte", "Piemonte", "TO", "Orbassano, Rivalta di Torino", 110000000, 45.0080, 7.5380, "AVANZATA_SENZA_ELENCO", True),
    # Lombardia aggiuntive
    ("LOMBARDIA-PEDEMONTANA-TRATTA-B2-CESANO-DESIO", "C11B09000010008", "Autostrada Pedemontana Lombarda: Tratta B2 da Lentate sul Seveso a Cesano Maderno", "Autostrada Pedemontana Lombarda S.p.A.", "Lombardia", "MB", "Cesano Maderno, Seveso, Desio", 680000000, 45.6290, 9.1550, "AVANZATA_SENZA_ELENCO", True),
    ("LOMBARDIA-RFI-QUADRUPICAMENTO-MILANO-PAVIA", "F21B22000640003", "Quadruplicamento linea Milano Rogoredo - Pavia: Tratta Pieve Emanuele - Certosa", "RFI S.p.A.", "Lombardia", "PV", "Pieve Emanuele, Locate Triulzi, Certosa di Pavia", 520000000, 45.3120, 9.1510, "ELENCO_PUBBLICATO", True),
    # Veneto aggiuntive
    ("VENETO-ANAS-SS51-ALEMAGNA-VARIANTE-CORTINA", "E81B21000190001", "S.S. 51 di Alemagna: Circonvallazione e gallerie per Cortina d'Ampezzo", "SIMICO / ANAS Veneto", "Veneto", "BL", "Cortina d'Ampezzo, San Vito di Cadore", 260000000, 46.5380, 12.1380, "AVANZATA_SENZA_ELENCO", True),
    # Emilia-Romagna aggiuntive
    ("EMILIA-RFI-PONTREMOLESE-RADDOPPIO-FORNOVO", "F51B18000770004", "Linea Ferroviaria Pontremolese: Raddoppio tratta Fornovo di Taro - Osteriazza", "RFI / Italferr", "Emilia-Romagna", "PR", "Fornovo di Taro, Solignano", 430000000, 44.6890, 10.0980, "AVANZATA_SENZA_ELENCO", True),
    ("EMILIA-SNAM-METANODOTTO-RAVENNA-MINERBIO", "S11B23000450009", "Metanodotto dorsale adriatica DN 1200: Tratta Ravenna Hub FSRU - Stoccaggio Minerbio", "Snam Rete Gas S.p.A.", "Emilia-Romagna", "BO", "Ravenna, Alfonsine, Minerbio", 310000000, 44.5240, 11.7820, "ELENCO_PUBBLICATO", True),
    # Liguria aggiuntiva
    ("LIGURIA-TERNA-TYRRHENIAN-LAB-SAVONA", "G91B22000330005", "Collegamento sottomarino ad altissima tensione Tyrrhenian Link: Approdo e stazione Vado", "Terna Rete Italia", "Liguria", "SV", "Vado Ligure, Quiliano", 380000000, 44.2750, 8.4310, "AVANZATA_SENZA_ELENCO", True)
]

for item in INFRA_NATIONAL:
    slug, cup, titolo, ente, regione, prov, comune, importo, lat, lng, stato, nostra = item
    
    # Genera mock ditte per opere con elenco pubblicato
    ditte_mock = []
    if stato == "ELENCO_PUBBLICATO":
        cognomi = ["Ferrari", "Russo", "Bianchi", "Colombo", "Esposito", "Romano", "Galli", "Costa", "Fontana", "Marino"]
        aziende = ["Costruzioni Generali S.r.l.", "Agricola Padana S.s.", "Immobiliare Veneta S.p.A.", "Logistica Adriatica S.r.l.", "Fondo Sviluppo Nord"]
        for j in range(random.randint(6, 18)):
            is_company = random.random() > 0.65
            nome_ditta = f"{random.choice(aziende)} {j+1}" if is_company else f"{random.choice(cognomi)} {random.choice(['Mario', 'Giuseppe', 'Luigi', 'Anna', 'Giovanni', 'Carla'])}"
            sup_lot = random.randint(300, 24000)
            stima_eur = int(sup_lot * random.uniform(15, 85))
            ditte_mock.append({
                "intestatario": nome_ditta,
                "comune": comune.split(",")[0].strip(),
                "foglio": str(random.randint(4, 55)),
                "mappali": f"{random.randint(10, 450)}, {random.randint(451, 890)}",
                "sup_mq": sup_lot,
                "indennita": stima_eur,
                "delta": stima_eur > 25000
            })

    op_obj = {
        "slug": slug,
        "cup": cup,
        "titolo": titolo,
        "ente": ente,
        "regione": regione,
        "provincia": prov,
        "comune": comune,
        "importo_eur": importo,
        "data_pubblicazione": f"2026-10-{random.randint(10, 30):02d}",
        "stato_opera": stato,
        "nostra_opera": nostra,
        "settimana_corrente": random.random() > 0.45,
        "maturity_score": 6 if stato == "ELENCO_PUBBLICATO" else (4 if stato == "AVANZATA_SENZA_ELENCO" else 2),
        "maturity_signals": {
            "conferenza_servizi_chiusa": stato in ["AVANZATA_SENZA_ELENCO", "ELENCO_PUBBLICATO", "CHIUSA"],
            "progetto_def_esec_approvato": stato in ["AVANZATA_SENZA_ELENCO", "ELENCO_PUBBLICATO", "CHIUSA"],
            "pubblica_utilita_emessa": stato in ["ELENCO_PUBBLICATO", "CHIUSA"],
            "cup_attivo_finanziamento": True,
            "avviso_art11_dpr327": stato != "PRELIMINARE",
            "vincolo_preordinato_pgt": stato in ["ELENCO_PUBBLICATO", "CHIUSA"],
            "bando_aggiudicazione_anac": stato == "CHIUSA"
        },
        "azione": {
            "verbo": "Opposizione stima indennità provvisorie D.P.R. 327/2001" if stato == "ELENCO_PUBBLICATO" else ("Target pre-acquisizione proprietari prima della notifica formale" if stato == "AVANZATA_SENZA_ELENCO" else "Monitoraggio conferenza dei servizi"),
            "priorita": "alta" if stato == "AVANZATA_SENZA_ELENCO" else ("media" if stato == "ELENCO_PUBBLICATO" else "bassa"),
            "giorni_residui": random.randint(5, 30) if stato in ["AVANZATA_SENZA_ELENCO", "ELENCO_PUBBLICATO"] else None,
            "elenco_non_pubblico": stato == "AVANZATA_SENZA_ELENCO",
            "deposito_presso": f"Ufficio Espropri {ente.split('/')[0].strip()} c/o Albo Pretorio dei Comuni interessati"
        },
        "geo": {"lat": lat, "lng": lng},
        "fonte_url": "https://stradeanas.it/espropri" if "ANAS" in ente else "https://www.rfi.it/espropri",
        "ditte": ditte_mock
    }
    OPERE_SEEDS.append(op_obj)

out_file = Path("/Users/houdinick/motore-espropri-italia/data/opere.json")
out_file.write_text(json.dumps(OPERE_SEEDS, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Salvate {len(OPERE_SEEDS)} opere complete su {len(set(o['regione'] for o in OPERE_SEEDS))} regioni.")
