# 🏛 Motore Espropri Italia — Dossier Architetturale & Specifiche di Sistema

> **Documento Tecnico Operativo (ADR & Blueprint)**  
> **Autore:** Nicola Valigi (Houdinick)  
> **Ambiente di Esecuzione:** `~/motore-espropri-italia`  
> **Framework:** FastAPI / Python 3.12+ (uv) + Leaflet GIS Fullscreen Engine  
> **Quadro Giuridico:** D.P.R. 8 giugno 2001, n. 327 e s.m.i.

---

## 1. Architettura di Sistema & Componenti

Il sistema è strutturato come un'applicazione a compartimento stagno, modulata per elaborare e geolocalizzare flussi eterogenei provenienti da avvisi d'esproprio, BUR, albi pretori e banche dati CUP/MIMS.

```
                      ┌───────────────────────────────────────┐
                      │   FONTI DATI PROCEDURALI (BUR / CUP)   │
                      └──────────────────┬────────────────────┘
                                         │
                                         ▼
                      ┌───────────────────────────────────────┐
                      │    espropri-intelligence-db (JSON)    │
                      │    - Blueprint opere (17 Regioni)     │
                      │    - Piani particellari (es. Dervio)  │
                      └──────────────────┬────────────────────┘
                                         │
                                         ▼
                      ┌───────────────────────────────────────┐
                      │        BACKEND FASTAPI (server.py)    │
                      │        - Endpoint REST /api/opere     │
                      │        - Motore calcolo D.P.R. 327    │
                      │        - Static File & Map Serving    │
                      └──────────────────┬────────────────────┘
                                         │
                                         ▼
                      ┌───────────────────────────────────────┐
                      │       FRONTEND GIS FULLSCREEN (JS)    │
                      │       - ESRI Canvas HD (3 Basemap)    │
                      │       - Marker Flyout (4 Tab)         │
                      │       - Toolbar & Telemetria Live     │
                      └───────────────────────────────────────┘
```

---

## 2. Blueprint Dati JSON (`opere.json`)

Tutte le istanze mappate nel motore seguono lo schema unificato riportato di seguito.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "OperaEsproprio",
  "type": "object",
  "required": [
    "id",
    "slug",
    "titolo",
    "cup",
    "ente_promotore",
    "regione",
    "comune",
    "coordinate",
    "importo_lavori_eur",
    "data_pubblicazione",
    "scadenza_osservazioni",
    "fase_procedurale",
    "maturita_step",
    "particellare"
  ],
  "properties": {
    "id": { "type": "string" },
    "slug": { "type": "string" },
    "titolo": { "type": "string" },
    "cup": { "type": "string" },
    "ente_promotore": { "type": "string" },
    "rup": { "type": "string" },
    "regione": { "type": "string" },
    "comune": { "type": "string" },
    "coordinate": {
      "type": "object",
      "properties": {
        "lat": { "type": "number" },
        "lng": { "type": "number" }
      },
      "required": ["lat", "lng"]
    },
    "importo_lavori_eur": { "type": "number" },
    "data_pubblicazione": { "type": "string", "format": "date" },
    "scadenza_osservazioni": { "type": "string", "format": "date" },
    "fase_procedurale": {
      "type": "string",
      "enum": [
        "VINCOLO_PREORDINATO",
        "DICHIARAZIONE_PU",
        "DEPOSITO_PIANO_PARTICELLARE",
        "DETERMINA_INDENNITA_PROVVISORIA",
        "DECRETO_ESPROPRIO"
      ]
    },
    "maturita_step": {
      "type": "integer",
      "minimum": 1,
      "maximum": 7,
      "description": "Livello checklist procedurale D.P.R. 327/2001"
    },
    "has_pda": { "type": "boolean" },
    "fonte_atto_url": { "type": "string" },
    "particellare": {
      "type": "array",
      "items": {
        "$ref": "#/definitions/ParticellaDitta"
      }
    }
  },
  "definitions": {
    "ParticellaDitta": {
      "type": "object",
      "required": ["intestatario", "foglio", "mappale", "superficie_esproprio_mq", "qualita_coltura"],
      "properties": {
        "intestatario": { "type": "string" },
        "codice_fiscale": { "type": "string" },
        "foglio": { "type": "string" },
        "mappale": { "type": "string" },
        "subalterno": { "type": "string" },
        "superficie_totale_mq": { "type": "number" },
        "superficie_esproprio_mq": { "type": "number" },
        "qualita_coltura": { "type": "string" },
        "destinazione_urbanistica": { "type": "string", "enum": ["AGRICOLA", "EDIFICABILE", "BOSCO", "INCOLTO"] },
        "indennita_proposta_eur": { "type": "number" }
      }
    }
  }
}
```

---

## 3. Checklist di Maturità Procedurale (Scala $1 \to 7$)

Ogni opera viene tracciata su un percorso a 7 stadi sequenziali per calcolare il coefficiente di maturità visualizzato sul pin cartografico:

| Step | Fase Procedurale D.P.R. 327/2001 | Base Giuridica | Finestra di Intervento |
| :---: | :--- | :--- | :--- |
| **1/7** | Apposizione del vincolo preordinato all'esproprio | Artt. 9–10 | Osservazioni a varianti PRG/PUC (30 gg) |
| **2/7** | Comunicazione avvio procedimento ex L. 241/90 | Art. 11, c. 2 | Verifica titolarità catastale e ditte omesse |
| **3/7** | Approvazione PFTE / Progetto Definitivo con dichiarazione PU | Art. 12 | Verifica termini decadenziali (5 anni vincolo) |
| **4/7** | Deposito piano particellare ditte ed elenco beni | Art. 16 | **Target Principale (PdA):** 30 gg per osservazioni |
| **5/7** | Notifica indennità provvisoria di esproprio | Art. 20 | 30 gg per accettazione o rifiuto motivato |
| **6/7** | Nomina Collegio Peritale / Richiesta terna arbitrale | Art. 21 | Procedura perizia di stima collegiale |
| **7/7** | Emissione ed esecuzione Decreto di Esproprio | Artt. 23–24 | Immissione in possesso e ricorso Corte d'Appello |

---

## 4. Algoritmo di Stima Peritale Integrato

Il motore integra le formule di calcolo indennitario conformi al diritto vivente e alle sentenze della Corte Costituzionale.

### A. Aree Edificabili (Post Corte Cost. n. 348/2007)
Il valore base non è più dimezzato (ex art. 5-bis L. 359/1992), ma coincide con il **valore venale pieno di mercato**:

$$I_e = V_v$$

In caso di cessione volontaria (art. 45, c. 2, lett. a):
$$I_{e,\text{cessione}} = V_v \cdot 1{,}10$$

### B. Aree Agricole o Non Edificabili (Post Corte Cost. n. 181/2011)
Eliminati i Valori Agricoli Medi (VAM) tabellari: l'indennità deve riflettere il valore venale effettivo dell'area agricola in base alle colture praticate, soprassuoli e frutti pendenti:

$$I_a = V_a + S_p$$

*Dove $V_a$ è il valore del fondo e $S_p$ è il valore di manufatti, impianti irrigui o soprassuoli arborei.*

### C. Maggiorazioni per Coltivatore Diretto / IAP (Art. 40, c. 4)
Se il proprietario espropriando coltiva direttamente il fondo:

$$I_{\text{totale}} = I_a + V_{\text{VAM}}$$

*(Viene corrisposta una ulteriore indennità pari al valore agricolo medio corrispondente al tipo di coltura effettivamente praticata).*

### D. Cessione Volontaria per Aree Agricole (Art. 45, c. 2, lett. c)
Se il proprietario non coltivatore accetta la cessione bonaria:
$$I_{a,\text{cessione}} = I_a \cdot 1{,}50$$

Se coltivatore diretto o IAP:
$$I_{a,\text{coltivatore}} = I_a \cdot 3{,}00$$

---

## 5. Specifiche Interfaccia GIS & Basemap ESRI HD

Per prevenire blocchi API e watermark, l'engine frontend adotta endpoint ESRI ArcGIS Canvas HD:

1. **Dark GIS (Default):**
   * Tile URL Base: `https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}`
   * Tile URL Labels: `https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}`
   * Massima leggibilità per overlay geometrici particellari e marker ad alta frequenza.

2. **Strade HD:**
   * Tile URL: `https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}`
   * Layer analitico per individuare accessi carrabili, interruzioni stradali e recinzioni espropriande.

3. **OpenStreetMap Standard:**
   * Tile URL: `https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png`
   * Riscontro toponomastico e catastale aperto.

---

## 6. Playbook Operativo d'Ingaggio (Lead Generation Pre-Decreto)

```
[AVVISO BUR/ALBO] ──> Ingestione CUP & Particellare
                              │
                              ▼
[MATCHING DATA]   ──> Filtro "PdA" + Countdown Scadenza (<30 gg)
                              │
                              ▼
[AUDIT TECNICO]   ──> Calcolo differenziale:
                      Δ = (Stima Peritale Reale) - (Indennità Proposta Ente)
                              │
                              ▼
[PROPOSTA DITTA]  ──> Notifica all'espropriando con perizia preliminare
                      e schema di osservazione tecnica ex Art. 16 DPR 327
```

Il valore aggiunto del motore consiste nell'intercettare l'espropriando allo **Step 4/7**, prima che l'indennità provvisoria diventi definitiva per decorrenza termini, garantendo il recupero del delta tra offerta tabellare dell'Ente e reale valore venale di mercato.
