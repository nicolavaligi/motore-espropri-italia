"""
Script di generazione e standardizzazione dati conforme al Dossier Architetturale.
Schema conforme a:
- D.P.R. 327/2001 (artt. 9-24, 37, 40, 45)
- Checklist Maturità 1-7
- JSON Schema OperaEsproprio & ParticellaDitta
"""

import json
import random
import sqlite3
import uuid
from pathlib import Path

# Definizione Mapping Fasi Procedurali & Maturità Step (Scala 1 -> 7)
FASE_MAPPING = {
    1: {"fase": "VINCOLO_PREORDINATO", "stato_legacy": "PRELIMINARE", "label": "Apposizione vincolo preordinato (artt. 9-10)"},
    2: {"fase": "VINCOLO_PREORDINATO", "stato_legacy": "PRELIMINARE", "label": "Comunicazione avvio procedimento ex L. 241/90 (art. 11)"},
    3: {"fase": "DICHIARAZIONE_PU", "stato_legacy": "AVANZATA_SENZA_ELENCO", "label": "Approvazione PFTE/PD con dichiarazione PU (art. 12)"},
    4: {"fase": "DEPOSITO_PIANO_PARTICELLARE", "stato_legacy": "ELENCO_PUBBLICATO", "label": "Deposito piano particellare ditte ed elenco beni (art. 16)"},
    5: {"fase": "DETERMINA_INDENNITA_PROVVISORIA", "stato_legacy": "ELENCO_PUBBLICATO", "label": "Notifica indennità provvisoria di esproprio (art. 20)"},
    6: {"fase": "DETERMINA_INDENNITA_PROVVISORIA", "stato_legacy": "ELENCO_PUBBLICATO", "label": "Nomina Collegio Peritale / Terna arbitrale (art. 21)"},
    7: {"fase": "DECRETO_ESPROPRIO", "stato_legacy": "CHIUSA", "label": "Emissione ed esecuzione Decreto di Esproprio (artt. 23-24)"}
}

RAW_OPERE = [
    {
        "slug": "SIMICO-MICO-2026-VALTELLINA-SS38",
        "cup": "B39H21000120001",
        "titolo": "S.S. 38 Variante di Tirano e Nodo di Bormio - Adeguamento e svincoli Olimpiadi 2026",
        "ente_promotore": "SIMICO S.p.A. / ANAS",
        "rup": "Ing. Marco Rossi",
        "regione": "Lombardia",
        "provincia": "SO",
        "comune": "Tirano, Villa di Tirano",
        "importo_lavori_eur": 184500000,
        "data_pubblicazione": "2026-10-18",
        "scadenza_osservazioni": "2026-11-17",
        "maturita_step": 3,
        "has_pda": False,
        "fonte_atto_url": "https://simico.it/atti-pubblicati-espropri-2026",
        "coordinate": {"lat": 46.2155, "lng": 10.1742},
        "nostra_opera": True,
        "settimana_corrente": True,
        "particellare": []
    },
    {
        "slug": "RFI-TAV-VR-PD-SUB-TRATTA-VICENZA",
        "cup": "F81B18000450009",
        "titolo": "Linea AV/AC Verona-Padova: Tratta 2° Lotto Costruttivo attraversamento Vicenza e opere connesse",
        "ente_promotore": "RFI / Italferr S.p.A.",
        "rup": "Ing. Roberto Bianchi",
        "regione": "Veneto",
        "provincia": "VI",
        "comune": "Vicenza, Altavilla Vicentina",
        "importo_lavori_eur": 890000000,
        "data_pubblicazione": "2026-10-12",
        "scadenza_osservazioni": "2026-11-11",
        "maturita_step": 5,
        "has_pda": True,
        "fonte_atto_url": "https://www.rfi.it/it/progetti-e-interventi/espropri.html",
        "coordinate": {"lat": 45.5455, "lng": 11.5354},
        "nostra_opera": True,
        "settimana_corrente": True,
        "particellare": [
            {
                "intestatario": "Zanella S.r.l. Costruzioni",
                "codice_fiscale": "03819280241",
                "foglio": "34",
                "mappale": "128, 129",
                "subalterno": "2",
                "superficie_totale_mq": 8500,
                "superficie_esproprio_mq": 4850,
                "qualita_coltura": "Area di cantiere / Produttiva",
                "destinazione_urbanistica": "EDIFICABILE",
                "indennita_proposta_eur": 145000
            },
            {
                "intestatario": "Rossi Mario & Rossi Giuseppe",
                "codice_fiscale": "RSSMRA62A15L840B",
                "foglio": "34",
                "mappale": "140",
                "subalterno": "",
                "superficie_totale_mq": 3200,
                "superficie_esproprio_mq": 1200,
                "qualita_coltura": "Seminativo irriguo classe 1",
                "destinazione_urbanistica": "AGRICOLA",
                "indennita_proposta_eur": 34000
            },
            {
                "intestatario": "Agricola Berica di Benetti F.lli",
                "codice_fiscale": "01948270249",
                "foglio": "12",
                "mappale": "88, 91, 95",
                "subalterno": "",
                "superficie_totale_mq": 35000,
                "superficie_esproprio_mq": 18400,
                "qualita_coltura": "Vigneto DOC Colli Berici",
                "destinazione_urbanistica": "AGRICOLA",
                "indennita_proposta_eur": 198000
            },
            {
                "intestatario": "Immobiliare San Felice S.a.s.",
                "codice_fiscale": "02281900244",
                "foglio": "35",
                "mappale": "210, 212",
                "subalterno": "",
                "superficie_totale_mq": 5600,
                "superficie_esproprio_mq": 3100,
                "qualita_coltura": "Incolto sterile",
                "destinazione_urbanistica": "EDIFICABILE",
                "indennita_proposta_eur": 89000
            }
        ]
    },
    {
        "slug": "REGIONE-LOMBARDIA-DERVIO-IDRAULICA-LC",
        "cup": "C12C24000100002",
        "titolo": "Interventi di mitigazione idraulica e viabilità di accesso — Comune di Dervio (LC)",
        "ente_promotore": "Regione Lombardia / Comune di Dervio",
        "rup": "Arch. Luca Fontana",
        "regione": "Lombardia",
        "provincia": "LC",
        "comune": "Dervio",
        "importo_lavori_eur": 4800000,
        "data_pubblicazione": "2026-10-29",
        "scadenza_osservazioni": "2026-11-28",
        "maturita_step": 4,
        "has_pda": True,
        "fonte_atto_url": "https://www.comune.dervio.lc.it",
        "coordinate": {"lat": 46.0772, "lng": 9.3061},
        "nostra_opera": True,
        "settimana_corrente": True,
        "particellare": []
    },
    {
        "slug": "AUTOVIE-A4-TERZA-CORSIA-SAN-DONA-PORTOGRUARO",
        "cup": "C21B20000150003",
        "titolo": "Autostrada A4 Venezia-Trieste: Realizzazione Terza Corsia tratta San Donà - Portogruaro",
        "ente_promotore": "Autostrade Alto Adriatico S.p.A.",
        "rup": "Ing. Paolo Barbieri",
        "regione": "Veneto",
        "provincia": "VE",
        "comune": "San Donà di Piave, Cessalto, Portogruaro",
        "importo_lavori_eur": 420000000,
        "data_pubblicazione": "2026-09-28",
        "scadenza_osservazioni": "2026-11-15",
        "maturita_step": 3,
        "has_pda": False,
        "fonte_atto_url": "https://www.autostradealtoadriatico.it/espropri",
        "coordinate": {"lat": 45.6322, "lng": 12.5644},
        "nostra_opera": True,
        "settimana_corrente": False,
        "particellare": []
    },
    {
        "slug": "ANAS-LOMBARDIA-VARIANTE-PALADINA-SEDRINA-SS470",
        "cup": "E81B23000670002",
        "titolo": "S.S. 470 della Valle Brembana: Variante di Paladina e sistemazione viabilità all'incrocio di Almè",
        "ente_promotore": "ANAS Lombardia / Provincia di Bergamo",
        "rup": "Ing. Andrea Vitali",
        "regione": "Lombardia",
        "provincia": "BG",
        "comune": "Paladina, Almè, Villa d'Almè",
        "importo_lavori_eur": 65000000,
        "data_pubblicazione": "2026-10-25",
        "scadenza_osservazioni": "2026-11-24",
        "maturita_step": 3,
        "has_pda": False,
        "fonte_atto_url": "https://stradeanas.it/it/lombardia-espropri-paladina",
        "coordinate": {"lat": 45.7289, "lng": 9.6133},
        "nostra_opera": True,
        "settimana_corrente": True,
        "particellare": []
    },
    {
        "slug": "EMILIA-CISPADANA-AUTOSTRADA-REGIONALE",
        "cup": "D41B19000220007",
        "titolo": "Autostrada Regionale Cispadana: Collegamento casello A22 Rolo-Reggiolo con A13 Ferrara Sud",
        "ente_promotore": "Autostrada del Brennero / ARC S.p.A.",
        "rup": "Ing. Giancarlo Testi",
        "regione": "Emilia-Romagna",
        "provincia": "RE",
        "comune": "Guastalla, Rolo, Cento, Mirandola",
        "importo_lavori_eur": 1300000000,
        "data_pubblicazione": "2026-08-14",
        "scadenza_osservazioni": "2026-10-15",
        "maturita_step": 5,
        "has_pda": True,
        "fonte_atto_url": "https://bur.regione.emilia-romagna.it",
        "coordinate": {"lat": 44.8872, "lng": 11.0667},
        "nostra_opera": True,
        "settimana_corrente": False,
        "particellare": [
            {
                "intestatario": "Società Agricola Mirandolese S.s.",
                "codice_fiscale": "01827360362",
                "foglio": "45",
                "mappale": "12, 14, 15",
                "subalterno": "",
                "superficie_totale_mq": 52000,
                "superficie_esproprio_mq": 32400,
                "qualita_coltura": "Seminativo irriguo / Frutteto",
                "destinazione_urbanistica": "AGRICOLA",
                "indennita_proposta_eur": 310000
            },
            {
                "intestatario": "Golinelli Sergio & Andrea",
                "codice_fiscale": "GLNSRG58C12C469X",
                "foglio": "18",
                "mappale": "202, 204",
                "subalterno": "",
                "superficie_totale_mq": 14000,
                "superficie_esproprio_mq": 8700,
                "qualita_coltura": "Seminativo",
                "destinazione_urbanistica": "AGRICOLA",
                "indennita_proposta_eur": 74000
            },
            {
                "intestatario": "Manifattura Tessile Emiliana S.p.A.",
                "codice_fiscale": "00918230351",
                "foglio": "9",
                "mappale": "55",
                "subalterno": "1",
                "superficie_totale_mq": 6200,
                "superficie_esproprio_mq": 4100,
                "qualita_coltura": "Area industriale D1",
                "destinazione_urbanistica": "EDIFICABILE",
                "indennita_proposta_eur": 165000
            }
        ]
    },
    {
        "slug": "PIEMONTE-TANGENZIALE-EST-TORINO-CONCESSIONE",
        "cup": "G11B22000550001",
        "titolo": "Tangenziale Est di Torino: Connessione tra A4 Torino-Milano e A21 Torino-Piacenza",
        "ente_promotore": "Regione Piemonte / Città Metropolitana Torino",
        "rup": "Ing. Daniele Sanna",
        "regione": "Piemonte",
        "provincia": "TO",
        "comune": "Chivasso, San Mauro Torinese, Moncalieri",
        "importo_lavori_eur": 780000000,
        "data_pubblicazione": "2026-09-02",
        "scadenza_osservazioni": "2026-12-01",
        "maturita_step": 2,
        "has_pda": False,
        "fonte_atto_url": "https://www.regione.piemonte.it/bandi",
        "coordinate": {"lat": 45.1033, "lng": 7.7850},
        "nostra_opera": False,
        "settimana_corrente": False,
        "particellare": []
    },
    {
        "slug": "LIGURIA-NODODE-GENOVA-POTENZIAMENTO-VOLTRI-BRIGNOLE",
        "cup": "J31B15000210008",
        "titolo": "Potenziamento infrastrutturale nodo ferroviario di Genova: Tratta Voltri - Sampierdarena - Brignole",
        "ente_promotore": "RFI S.p.A. / Italferr",
        "rup": "Ing. Massimo Serra",
        "regione": "Liguria",
        "provincia": "GE",
        "comune": "Genova",
        "importo_lavori_eur": 540000000,
        "data_pubblicazione": "2026-07-21",
        "scadenza_osservazioni": "2026-08-30",
        "maturita_step": 7,
        "has_pda": False,
        "fonte_atto_url": "https://www.commissari.mit.gov.it/nodo-genova",
        "coordinate": {"lat": 44.4142, "lng": 8.9132},
        "nostra_opera": False,
        "settimana_corrente": False,
        "particellare": []
    }
]

# Estrazione particelle reali Dervio da SQLite se presente
db_path = Path("/Users/houdinick/MyIP_Vault/02_Blueprints/espropri-intelligence-db/espropri_radar.db")
if db_path.exists():
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT comune_nome, foglio, numero_particella, subalterno, ditta_intestataria, 
               codice_fiscale_ditta, qualita_catastale, tipo_intervento,
               superficie_occupata_mq, superficie_totale_particella_mq, indennita_provvisoria_stimata
        FROM particelle_esproprio
    """)
    rows = cur.fetchall()
    ditte_dervio = []
    for r in rows:
        comune, foglio, part, sub, ditta, cf, qualita, tipo, sup_occ, sup_tot, ind = r
        ditta_clean = ditta.split(' nato')[0].split(' con sede')[0].strip() if ditta else "Proprietario Privato"
        ind_val = round(float(ind), 2) if ind else 0
        dest = "EDIFICABILE" if "fabbric" in (qualita or "").lower() or (ind_val > 20000) else "AGRICOLA"
        ditte_dervio.append({
            "intestatario": ditta_clean[:50],
            "codice_fiscale": cf or "ND",
            "foglio": str(foglio),
            "mappale": str(part),
            "subalterno": str(sub or ""),
            "superficie_totale_mq": float(sup_tot or sup_occ or 0),
            "superficie_esproprio_mq": float(sup_occ or 0),
            "qualita_coltura": qualita or "Seminativo / Residenziale",
            "destinazione_urbanistica": dest,
            "indennita_proposta_eur": float(ind_val)
        })
    conn.close()
    RAW_OPERE[2]["particellare"] = ditte_dervio

# Dataset nazionale complementare
INFRA_NATIONAL = [
    ("TOSCANA-FI-PI-LI-TERZA-CORSIA-EMPOLI", "D51B22000880001", "Strada Grande Comunicazione FI-PI-LI: Terza corsia dinamica e svincolo Empoli Est", "Regione Toscana / Città Metro Firenze", "Toscana", "FI", "Empoli, Montelupo Fiorentino", 92000000, 43.7180, 10.9480, 3, False),
    ("TOSCANA-RFI-RADDOPPIO-PISTOIA-LUCCA", "F71B17000320009", "Potenziamento e raddoppio linea ferroviaria Pistoia - Lucca: Tratta Montecatini - Pescia", "RFI / Italferr", "Toscana", "PT", "Montecatini Terme, Pescia", 240000000, 43.8820, 10.7730, 4, True),
    ("MARCHE-ANAS-SS16-VARIANTE-FALCONARA-ANCONA", "E31B20000410002", "S.S. 16 Adriatica: Variante all'abitato di Falconara e collegamento Porto di Ancona", "ANAS Marche", "Marche", "AN", "Falconara Marittima, Ancona", 145000000, 43.6280, 13.4020, 3, False),
    ("MARCHE-RFI-BYPASS-FERROVIARIO-PESARO", "F11B21000910004", "Linea Ferroviaria Adriatica: Bypass di arretramento Pesaro e nuovo tracciato AV", "RFI S.p.A.", "Marche", "PU", "Pesaro, Fano", 620000000, 43.9100, 12.9130, 1, False),
    ("UMBRIA-ANAS-E45-RISANAMENTO-TERNI-ORTE", "B81B19000110003", "Itinerario E45 Orte-Ravenna: Adeguamento svincoli e complanari nodo di Terni", "ANAS Umbria", "Umbria", "TR", "Terni, Narni", 78000000, 42.5640, 12.6410, 3, False),
    ("LAZIO-AUTOSTRADA-ROMA-LATINA-TRATTA-A", "C81B16000250005", "Corridoio Intermodale Roma - Latina: Tratta autostradale Tor de' Cenci - Latina Borgo Piave", "Autostrade del Lazio / MIT", "Lazio", "LT", "Pomezia, Aprilia, Latina", 1250000000, 41.5830, 12.8330, 3, False),
    ("LAZIO-RFI-CHIUSURA-ANELLO-ROMA-VIGNA-CLARA", "F81B23000770001", "Chiusura Anello Ferroviario di Roma: Tratta Vigna Clara - Tor di Quinto - Salaria", "RFI / Italferr", "Lazio", "RM", "Roma", 380000000, 41.9420, 12.4910, 4, True),
    ("CAMPANIA-RFI-AV-NAPOLI-BARI-LOTTO-IRPINIA", "F21B19000150008", "Nuova Linea AV/AC Napoli-Bari: Tratta Apice - Hirpinia e Stazione Hirpinia", "RFI / Italferr", "Campania", "AV", "Ariano Irpino, Grottaminarda", 650000000, 41.1180, 15.0830, 5, True),
    ("CAMPANIA-ANAS-SS268-RADDOPPIO-VESUVIANA", "E41B21000300002", "S.S. 268 del Vesuvio: Adeguamento a 4 corsie e raccordi autostradali A30", "ANAS Campania", "Campania", "NA", "Somma Vesuviana, Ottaviano, Palma C.", 115000000, 40.8520, 14.4710, 3, False),
    ("PUGLIA-ANAS-SS16-TRATTA-BARI-MOLA", "E91B22000390004", "S.S. 16 Variante di Bari: Sistemazione nodi complanari e svincoli Torre a Mare - Mola", "ANAS Puglia", "Puglia", "BA", "Bari, Mola di Bari", 85000000, 41.0610, 17.0210, 3, False),
    ("PUGLIA-TERNA-CORRIDOIO-ADRIATICO-HVDC", "G41B21000190007", "Elettrodotto sottomarino HVDC Adriatico: Stazione di conversione e cavidotto Galatina", "Terna Rete Italia", "Puglia", "LE", "Galatina, Soleto", 410000000, 40.1740, 18.1680, 4, True),
    ("ABRUZZO-RFI-VELOCIZZAZIONE-ROMA-PESCARA", "F31B22000820001", "Velocizzazione ferrovia Roma-Pescara: Raddoppio tratta Interporto d'Abruzzo - Manoppello", "RFI S.p.A.", "Abruzzo", "PE", "Manoppello, Scafa, Chieti", 320000000, 42.3480, 14.0620, 3, False),
    ("FVG-RFI-POTENZIAMENTO-TRIESTE-DIVACCIA", "F51B20000340003", "Nodo di Trieste: Potenziamento linea di cintura e collegamento scalo Campo Marzio", "RFI / Italferr", "Friuli-Venezia Giulia", "TS", "Trieste, San Dorligo della Valle", 195000000, 45.6290, 13.8010, 4, True),
    ("TRENTINO-RFI-CIRCONVALLAZIONE-TRENTO", "F61B21000630006", "Circonvallazione ferroviaria di Trento (Galleria di Trento): Accesso sud Tunnel del Brennero", "RFI S.p.A.", "Trentino-Alto Adige", "TN", "Trento", 970000000, 46.0670, 11.1210, 5, True),
    ("ALTO-ADIGE-VARIANTE-VAL-PUSTERIA-SS49", "E51B22000120004", "S.S. 49 della Val Pusteria: Circonvallazione di Perca e centro mobilità", "Provincia Autonoma Bolzano", "Trentino-Alto Adige", "BZ", "Perca, Brunico", 138000000, 46.7920, 11.9810, 3, False),
    ("SICILIA-RFI-RADDOPPIO-PALERMO-CATANIA-LOTTO-DITTAINO", "F41B19000550001", "Itinerario ferroviario Palermo - Catania - Messina: Tratta Dittaino - Enna Nuova", "RFI / Italferr", "Sicilia", "EN", "Enna, Assoro", 820000000, 37.5850, 14.3670, 5, True),
    ("SICILIA-ANAS-RAGUSA-CATANIA-LOTTO-1", "E11B18000400002", "Raddoppio S.S. 514 di Chiaramonte e S.S. 194 Ragusana: Tratta Ragusa - Vizzini", "ANAS Sicilia", "Sicilia", "RG", "Ragusa, Chiaramonte Gulfi", 490000000, 36.9850, 14.6850, 3, False),
    ("CALABRIA-ANAS-SS106-JONICA-CROTONE-SIBARI", "E61B22000980003", "Nuova S.S. 106 Jonica a 4 corsie: Tratta Crotone Nord - Mandatoriccio", "ANAS Calabria", "Calabria", "KR", "Crotone, Cirò Marina", 730000000, 39.2210, 17.1080, 3, False),
    ("SARDEGNA-ANAS-SS131-ADEGUAMENTO-BONORVA-SASSARI", "E71B21000440002", "S.S. 131 Carlo Felice: Risoluzione nodi critici ed eliminazione incroci a raso", "ANAS Sardegna", "Sardegna", "SS", "Bonorva, Sassari", 160000000, 40.5280, 8.7610, 3, False),
    ("BASILICATA-FERROVIA-MATERA-FERRANDINA", "F91B19000720005", "Completamento collegamento ferroviario Ferrandina Scalo - Matera La Martella", "RFI / Italferr", "Basilicata", "MT", "Matera, Ferrandina", 365000000, 40.6420, 16.5410, 4, True),
    ("MOLISE-ANAS-FONDO-VALLE-BIFERNO-SS647", "E21B20000180001", "S.S. 647 Fondo Valle del Biferno: Messa in sicurezza e viadotti viabilità Liscione", "ANAS Molise", "Molise", "CB", "Guardialfiera, Larino", 72000000, 41.8020, 14.8110, 2, False),
    ("PIEMONTE-RFI-RADDOPPIO-PIOSSASCO-ORBASSANO", "F11B23000210002", "Linea SFM 5 Torino: Nodo di interscambio e raddoppio scalo Orbassano", "RFI / Regione Piemonte", "Piemonte", "TO", "Orbassano, Rivalta di Torino", 110000000, 45.0080, 7.5380, 3, False),
    ("LOMBARDIA-PEDEMONTANA-TRATTA-B2-CESANO-DESIO", "C11B09000010008", "Autostrada Pedemontana Lombarda: Tratta B2 da Lentate sul Seveso a Cesano Maderno", "Autostrada Pedemontana Lombarda S.p.A.", "Lombardia", "MB", "Cesano Maderno, Seveso, Desio", 680000000, 45.6290, 9.1550, 3, False),
    ("LOMBARDIA-RFI-QUADRUPICAMENTO-MILANO-PAVIA", "F21B22000640003", "Quadruplicamento linea Milano Rogoredo - Pavia: Tratta Pieve Emanuele - Certosa", "RFI S.p.A.", "Lombardia", "PV", "Pieve Emanuele, Locate Triulzi, Certosa di Pavia", 520000000, 45.3120, 9.1510, 4, True),
    ("VENETO-ANAS-SS51-ALEMAGNA-VARIANTE-CORTINA", "E81B21000190001", "S.S. 51 di Alemagna: Circonvallazione e gallerie per Cortina d'Ampezzo", "SIMICO / ANAS Veneto", "Veneto", "BL", "Cortina d'Ampezzo, San Vito di Cadore", 260000000, 46.5380, 12.1380, 3, False),
    ("EMILIA-RFI-PONTREMOLESE-RADDOPPIO-FORNOVO", "F51B18000770004", "Linea Ferroviaria Pontremolese: Raddoppio tratta Fornovo di Taro - Osteriazza", "RFI / Italferr", "Emilia-Romagna", "PR", "Fornovo di Taro, Solignano", 430000000, 44.6890, 10.0980, 3, False),
    ("EMILIA-SNAM-METANODOTTO-RAVENNA-MINERBIO", "S11B23000450009", "Metanodotto dorsale adriatica DN 1200: Tratta Ravenna Hub FSRU - Stoccaggio Minerbio", "Snam Rete Gas S.p.A.", "Emilia-Romagna", "BO", "Ravenna, Alfonsine, Minerbio", 310000000, 44.5240, 11.7820, 4, True),
    ("LIGURIA-TERNA-TYRRHENIAN-LAB-SAVONA", "G91B22000330005", "Collegamento sottomarino ad altissima tensione Tyrrhenian Link: Approdo e stazione Vado", "Terna Rete Italia", "Liguria", "SV", "Vado Ligure, Quiliano", 380000000, 44.2750, 8.4310, 3, False)
]

for item in INFRA_NATIONAL:
    slug, cup, titolo, ente, regione, prov, comune, importo, lat, lng, step, has_pda = item
    
    particellare_mock = []
    if has_pda:
        cognomi = ["Ferrari", "Russo", "Bianchi", "Colombo", "Esposito", "Romano", "Galli", "Costa", "Fontana", "Marino"]
        aziende = ["Costruzioni Generali S.r.l.", "Agricola Padana S.s.", "Immobiliare Veneta S.p.A.", "Logistica Adriatica S.r.l.", "Fondo Sviluppo Nord"]
        for j in range(random.randint(6, 16)):
            is_company = random.random() > 0.65
            nome_ditta = f"{random.choice(aziende)} {j+1}" if is_company else f"{random.choice(cognomi)} {random.choice(['Mario', 'Giuseppe', 'Luigi', 'Anna', 'Giovanni', 'Carla'])}"
            sup_lot = random.randint(300, 24000)
            dest = "EDIFICABILE" if random.random() > 0.7 else "AGRICOLA"
            stima_eur = int(sup_lot * (random.uniform(50, 140) if dest == "EDIFICABILE" else random.uniform(8, 35)))
            particellare_mock.append({
                "intestatario": nome_ditta,
                "codice_fiscale": f"IT{random.randint(10000000000, 99999999999)}" if is_company else f"{random.choice(cognomi)[:3].upper()}{random.randint(10, 99)}A01H501Z",
                "foglio": str(random.randint(4, 55)),
                "mappale": f"{random.randint(10, 450)}, {random.randint(451, 890)}",
                "subalterno": str(random.randint(1, 10)) if random.random() > 0.5 else "",
                "superficie_totale_mq": float(sup_lot + random.randint(50, 5000)),
                "superficie_esproprio_mq": float(sup_lot),
                "qualita_coltura": "Area industriale" if dest == "EDIFICABILE" else "Seminativo irriguo classe 1",
                "destinazione_urbanistica": dest,
                "indennita_proposta_eur": float(stima_eur)
            })

    op_obj = {
        "slug": slug,
        "cup": cup,
        "titolo": titolo,
        "ente_promotore": ente,
        "rup": f"Ing. Tecnico RUP ({ente.split('/')[0].strip()})",
        "regione": regione,
        "provincia": prov,
        "comune": comune,
        "importo_lavori_eur": importo,
        "data_pubblicazione": f"2026-10-{random.randint(10, 30):02d}",
        "scadenza_osservazioni": f"2026-11-{random.randint(15, 30):02d}",
        "maturita_step": step,
        "has_pda": has_pda,
        "fonte_atto_url": "https://stradeanas.it/espropri" if "ANAS" in ente else "https://www.rfi.it/espropri",
        "coordinate": {"lat": lat, "lng": lng},
        "nostra_opera": True,
        "settimana_corrente": random.random() > 0.45,
        "particellare": particellare_mock
    }
    RAW_OPERE.append(op_obj)

# Uniformazione con schema JSON e alias backward-compatible
STANDARDIZED_OPERE = []
for op in RAW_OPERE:
    step = op.get("maturita_step", 3)
    fase_info = FASE_MAPPING.get(step, FASE_MAPPING[3])
    
    # Costruzione ditte legacy per compatibilità frontend
    ditte_legacy = []
    for p in op.get("particellare", []):
        ind_eur = p.get("indennita_proposta_eur", 0)
        ditte_legacy.append({
            "intestatario": p.get("intestatario"),
            "comune": op.get("comune").split(",")[0].strip(),
            "foglio": p.get("foglio"),
            "mappali": p.get("mappale"),
            "sup_mq": int(p.get("superficie_esproprio_mq", 0)),
            "indennita": int(ind_eur),
            "delta": ind_eur > 15000,
            "destinazione": p.get("destinazione_urbanistica")
        })

    # Standard Record Conforme al Dossier
    record = {
        "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, op["slug"])).replace("-", ""),
        "slug": op["slug"],
        "titolo": op["titolo"],
        "cup": op.get("cup"),
        "ente_promotore": op.get("ente_promotore"),
        "rup": op.get("rup", "Non comunicato"),
        "regione": op.get("regione"),
        "provincia": op.get("provincia", "ND"),
        "comune": op.get("comune"),
        "coordinate": op["coordinate"],
        "importo_lavori_eur": float(op["importo_lavori_eur"]),
        "data_pubblicazione": op["data_pubblicazione"],
        "scadenza_osservazioni": op.get("scadenza_osservazioni", "2026-11-30"),
        "fase_procedurale": fase_info["fase"],
        "maturita_step": step,
        "has_pda": bool(op.get("has_pda", len(op.get("particellare", [])) > 0)),
        "fonte_atto_url": op.get("fonte_atto_url", ""),
        "particellare": op.get("particellare", []),
        
        # Campi Alias & Legacy per compatibilità istantanea UI
        "geo": op["coordinate"],
        "ente": op.get("ente_promotore"),
        "importo_eur": float(op["importo_lavori_eur"]),
        "stato_opera": fase_info["stato_legacy"],
        "nostra_opera": op.get("nostra_opera", True),
        "settimana_corrente": op.get("settimana_corrente", False),
        "maturity_score": step,
        "ditte": ditte_legacy,
        "azione": {
            "verbo": "Target pre-acquisizione proprietari prima della notifica formale" if step <= 3 else ("Opposizione stima provvisoria e perizia giurata D.P.R. 327" if step in [4, 5] else "Assistenza svincolo somme depositate CDP"),
            "priorita": "alta" if step in [3, 4] else ("media" if step == 5 else "bassa"),
            "giorni_residui": random.randint(8, 29) if step in [3, 4, 5] else None,
            "elenco_non_pubblico": step == 3,
            "deposito_presso": f"Ufficio Espropri {op.get('ente_promotore').split('/')[0].strip()} c/o Albo Pretorio"
        },
        "maturity_signals": {
            "conferenza_servizi_chiusa": step >= 3,
            "progetto_def_esec_approvato": step >= 3,
            "pubblica_utilita_emessa": step >= 3,
            "cup_attivo_finanziamento": True,
            "avviso_art11_dpr327": step >= 2,
            "vincolo_preordinato_pgt": step >= 4,
            "bando_aggiudicazione_anac": step >= 7
        }
    }
    STANDARDIZED_OPERE.append(record)

out_file = Path("/Users/houdinick/motore-espropri-italia/data/opere.json")
out_file.write_text(json.dumps(STANDARDIZED_OPERE, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Standardizzate {len(STANDARDIZED_OPERE)} opere con schema Dossier Architetturale.")
