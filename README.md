# Motore Espropri Italia — archivio documentale

Applicazione FastAPI e MapLibre per collegare opere, documenti degli enti, righe catastali e geometrie effettive. Il catalogo operativo usa solo opere riscontrate su fonti ufficiali. L'archivio precedente, che mescolava dati dimostrativi e dati privi di provenienza sufficiente, è conservato in `data/quarantine/` ed escluso dall'applicazione.

## Stato dell'acquisizione locale — 1 novembre 2026

- 7 opere/fascicoli riscontrati su fonti ufficiali, con lotti distinti.
- 17 PDF ufficiali archiviati con checksum: i 14 elenchi ditte della Rho–Gallarate disponibili dal portale VIA, due avvisi espropri 2026 di FS Engineering e il piano particellare pubblico di Pavia. I tre documenti aggiuntivi non hanno prodotto righe proprietari tabellari con il parser corrente.
- 832 righe catastali trascritte dalle scansioni, tutte nello stato **`ocr_da_verificare`**. Non rappresentano 832 proprietari unici né un elenco completo certificato.
- 365 pagine conservate nello stato di estrazione; le pagine senza righe riconosciute restano segnalate per controllo. Nessuna indennità o superficie viene inventata a partire da queste scansioni.
- Cinque righe catastali hanno geometria WFS corrente, riferite a tre particelle uniche: Canegrate, foglio 11, mappali 79 e 80; Busto Arsizio, sezione A, foglio 917, mappale 2038 (tre subalterni nel documento). Gli identificativi di tutte e cinque le righe sono stati confrontati con le pagine originali; la particella 79 è stata corretta da 790 con revisione auditata. I nominativi OCR restano da verificare.
- Le geometrie provengono da risposte GML ufficiali conservate con URL, checksum, licenza e data. Il collegamento identifica comune, foglio, sezione quando disponibile e mappale; il catasto corrente può differire dal piano storico. Il resto delle righe non è localizzato e la copertura dell'opera non è certificata.
- L'indice MASE della Rho–Gallarate espone un export XLSX con 1.658 righe di documenti, inclusi piani particellari per più comuni; questi elaborati non sono ancora stati scaricati nei rispettivi fascicoli. Il canale Vercel autorizzato ha consentito i download descritti sopra. Le sandbox temporanee sono state arrestate al termine delle acquisizioni.

Questi dati descrivono il lavoro effettivamente eseguito, non la copertura di tutte le opere del precedente catalogo. Le restanti opere legacy devono essere riscontrate e ricondotte al lotto, al CUP e ai documenti corretti prima di rientrare nel catalogo operativo.

## Avvio

```sh
./run.sh
```

Mappa principale: `http://127.0.0.1:8000/`. Fascicoli, originali e particelle: `http://127.0.0.1:8000/quadro-interferenze`. API: `/docs`.

L'archivio persistente è `data/production/` oppure la directory indicata da `MOTORE_ARCHIVE_ROOT`. SQLite, PDF e trascrizioni sono esclusi da Git. La sola distribuzione del codice non trasferisce l'archivio.

Su un server con disco persistente impostare `MOTORE_ARCHIVE_ROOT` sul volume conservato tra gli aggiornamenti e salvare sia il database SQLite (mediante backup SQLite coerente) sia gli originali. Un filesystem temporaneo serverless non costituisce persistenza per questo archivio. L'entrypoint Vercel preesistente richiede una soluzione di persistenza e accesso riservato prima di essere utilizzato per questo catalogo; non è stato pubblicato alcun archivio personale su hosting.

## Acquisizione da enti

Il manifest `config/fonti_pubbliche.json` elenca pagine specifiche delle opere, host consentiti e limiti di scansione. Contiene fonti RFI/FS Engineering, MIT, MASE, Comune di Vicenza, Regione Emilia-Romagna e concessionario Cispadana. Le fonti generiche sono destinate alla scoperta e richiedono verifica dell'abbinamento prima di acquisire un allegato nel fascicolo.

```sh
uv run --frozen python collect_public_records.py --manifest config/fonti_pubbliche.json
uv run --frozen python collect_public_records.py --opera EMILIA-CISPADANA-AUTOSTRADA-REGIONALE
```

Il raccoglitore verifica host e redirect, limita dimensione e numero di richieste, conserva gli originali con SHA256 e registra errori, pagine non interpretate e limiti raggiunti. Gli errori non equivalgono ad assenza di elenchi. Un errore di acquisizione produce exit code 2. Il job settimanale si interrompe se l'acquisizione fallisce; l'invio email preesistente non è stato eseguito durante la revisione.

I PDF testuali vengono letti con `pdfplumber`. Per scansioni con griglia RFI riconosciuta, il raccoglitore attiva l'adattatore OCR. Layout non supportati rimangono archiviati e segnalati; non viene dichiarata un'estrazione completa. Il formato attualmente acquisito automaticamente è PDF; allegati ZIP, fogli elettronici e portali con interfacce dinamiche richiedono connettori dedicati.

## OCR e revisione

Per gli elenchi RFI già archiviati:

```sh
uv run --frozen python ocr_public_records.py --opera RFI-RHO-GALLARATE-PROGETTO-DEFINITIVO-2013 --workers 4
```

Richiede `pdftoppm` (Poppler) e Tesseract con lingua italiana. La cache è distinta per checksum del PDF e pagina, quindi non viene riutilizzata per revisioni differenti.

Ogni riga conserva documento, pagina PDF, checksum, URL originale e celle OCR. Non viene convertita automaticamente in una ditta verificata. Per registrare una correzione dopo confronto con l'originale:

```sh
uv run --frozen python production_admin.py review --row ID_RIGA --fields correzione.json --operator NOME_OPERATORE
```

`correzione.json` contiene esclusivamente i campi letti dal documento, come `comune`, `foglio`, `mappale`, `sub`, `intestatario`, `codice_fiscale`, `quota`, `diritto`, `superfici_mq`. L'audit conserva versione precedente, nuova versione e operatore. Una successiva riestrazione non sovrascrive le righe verificate. Cambiare l'identificativo catastale invalida la precedente geometria.

Per correggere solo comune/foglio/mappale/sub dopo confronto con l'atto, usare `--scope identificativi`: la revisione conserva l'audit ma lascia nominativi e trascrizione OCR nello stato da verificare. Le correzioni parziali con audit sono protette anche dalle riestrazioni successive.

## Ubicazione reale

```sh
uv run --frozen python cadastral_locator.py --opera RFI-RHO-GALLARATE-PROGETTO-DEFINITIVO-2013 --reference-dir data/production/reference
```

Il localizzatore risolve il comune, cerca il foglio e interroga il WFS catastale per bounding box ridotti. Abbina il riferimento catastale completo; identificativi ambigui, assenza di corrispondenza ed errori di servizio rimangono espliciti. La geometria conserva gli anelli interni, viene trasformata in WGS84 e mantiene URL, risposta GML, checksum e data di acquisizione. I centri comunali servono alla ricerca del foglio e non vengono mostrati come posizione delle ditte.

Il catasto attuale può differire da quello del progetto per frazionamenti, sezioni e revisioni. Le trascrizioni OCR vanno verificate prima di considerare concluso l'abbinamento; non basta che un numero esista oggi nel servizio. L'aggancio alle tavole catastali di progetto, ai frazionamenti storici e ai catasti delle Province autonome richiede fonti/adattatori specifici.

## Consultazione e API

- `/api/opere`: catalogo operativo; `/api/archivio/stato`: acquisizioni, errori e stato pagine.
- `/api/opere/{slug}/documenti`: originali collegati all'opera, comprese revisioni storiche.
- `/api/opere/{slug}/particelle`: righe con provenienza e stato di lettura.
- `/api/opere/{slug}/particelle.geojson`: solo geometrie effettivamente acquisite, con conteggio delle righe non localizzate.
- `/api/documenti/{id}/file#page=N`: apertura della pagina originale archiviata.

Le nuove versioni di un documento allo stesso URL conservano lo storico e disattivano le righe della revisione precedente. Il catalogo non somma ditte vecchie e nuove come se fossero contemporanee. Gli inserimenti liberi nel vecchio endpoint POST opere sono disabilitati. I JSON statici e il fallback GitHub non possono reintrodurre dati dimostrativi.

La mappa principale mantiene ricerca, pannelli compatti, scala metrica e filtro sull'area visibile. Il CSS delle utility è compilato in `static/workspace.css`, con sorgente e comando di ricompilazione in `styles/workspace.input.css`; non richiede il runtime Tailwind da CDN. Se la libreria cartografica non si carica, i fascicoli restano consultabili. Il quadro documentale offre ricerca e paginazione delle righe, download CSV con fonti e GeoJSON delle sole geometrie disponibili. Le opere senza coordinate aprono comunque il fascicolo. Nessun tracciato sintetico o rettangolo catastale viene disegnato per le opere documentali.

Per la revisione APL, i KMZ utente B2/C sono conservati privatamente in `data/production/apl/source/`, convertiti senza semplificazione in GeoPackage e GeoJSON. Il comando facoltativo **APL B2/C · KMZ utente** carica solo il layer di revisione, non lo collega alle ditte e non lo presenta come asse verificato. API: `/api/apl/tratte/B2.geojson` e `/api/apl/tratte/C.geojson`.

## Verifiche

```sh
uv run --frozen --group dev python -m pytest -q
node --test tests/map_workspace.test.cjs
uv run --frozen python benchmarks/benchmark_engine.py afb36f6
```

Sono coperti idempotenza, checksum, originali serviti dalle API, rollback transazionale, revisione tracciata, versioni dei documenti, errori di rete, limiti di download, redirect, interpretazione GML, ricerca e riuso dei marker. La prova visiva WebGL e la disponibilità dei servizi degli enti richiedono un ambiente che consenta browser e connessioni di rete.

Il motore estimativo resta parametrico: prezzi, maggiorazioni e soglie euristiche non vengono trasformati in fatti catastali o indennità pubblicate. La revisione numerica precedente ha conservato le superfici fino al computo e corretto l'attribuzione CD/IAP ai non coltivatori e il danno sui residui. Il benchmark locale su 20.000 particelle sparse resta riproducibile; non certifica tempi dei servizi remoti né correttezza normativa di ogni ipotesi estimativa.

## Aggiornamento skill geospaziali — 1 novembre 2026

- Nessuna geometria o fascia viene ricostruita dal pin o da larghezze predefinite. Import KML/GeoJSON conserva linee separate, controlla coordinate e richiede fonte.
- `POST /api/catasto/interferenze` richiede `ingombro_geojson`, `particelle_geojson`, `fonte_ingombro_url`, `fonte_catasto_url`. Sono accettati solo poligoni WGS84 RFC 7946 validi; un solo asse riceve 409, senza fallback. Le intersezioni usano UTM locale, unione degli ingombri e indice spaziale. Estensione massima del progetto 6° per asse: limite tecnico provvisorio, non soglia di conformità. Le fonti sono dichiarate, non automaticamente verificate.
- Superfici senza unità dichiarata o con testo ambiguo restano null. Zero è ammesso solo esplicitamente. Le riestrazioni conservano le revisioni umane.
- Calcolatore senza importi precompilati o prezzi dedotti; errore API esplicito, nessun risultato locale sostitutivo.
- Archivio reale escluso dal repository e dal rilascio. Su Vercel senza archivio collegato viene indicata indisponibilità (503), senza riattivare dataset precedenti.

Riferimenti tecnici: [GeoJSON RFC 7946](https://www.rfc-editor.org/rfc/rfc7946), [GeoPandas UTM locale](https://geopandas.org/en/stable/docs/reference/api/geopandas.GeoDataFrame.estimate_utm_crs.html).
