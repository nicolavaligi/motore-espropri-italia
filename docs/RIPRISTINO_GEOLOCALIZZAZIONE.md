# Ripristino cartografia e catalogo pubblico — 1 novembre 2026

Il rilascio precedente non includeva un archivio persistente: `/api/opere` rispondeva 503. Lo sfondo CARTO mostrava inoltre tessere con richiesta di API key. La correzione distribuisce un catalogo pubblico di sola lettura e usa lo sfondo stradale Esri già utilizzato nel quadro interferenze.

## Dati effettivamente ripristinati

7 schede di opere con fonte ufficiale, 17 riferimenti a documenti e 5 righe catastali localizzate e riscontrate sugli atti, corrispondenti a 3 particelle distinte della Rho–Gallarate (Canegrate e Busto Arsizio). Le altre opere restano consultabili senza pin quando non hanno coordinate documentate. Non è stato ripristinato il vecchio dataset dimostrativo.

`data/public/catalogue.json` contiene una proiezione esplicita dei soli campi pubblicabili: metadati delle fonti, riferimenti e geometrie con CRS, licenza, URL e checksum. Nessun nominativo, codice fiscale, cella OCR, database o PDF locale è incluso. Le superfici e le indennità non verificate rimangono null. Le geometrie sono del catasto acquisito, non l’ingombro dell’opera né una prova di titolarità o del regime di occupazione.

## Aggiornamento ripetibile

```sh
python tools/export_public_catalogue.py data/production data/public/catalogue.json
```

L’esportatore apre SQLite in sola lettura e usa una transazione coerente. Prima di pubblicare richiede identificativi verificati sul documento, geometrie poligonali WGS84 valide, fonte, checksum e licenza. I campi sono selezionati tramite allowlist; i dati personali non vengono esportati. Il catalogo è una fotografia datata: non sostituisce uno storage persistente per importazioni o revisioni online.

In assenza dell’archivio locale e di un percorso esplicito `MOTORE_ARCHIVE_ROOT`, le API di catalogo, riferimenti catastali e stato leggono la stessa fotografia inclusa nel rilascio. Gli originali vengono aperti tramite redirect al sito dell’ente. `MOTORE_PUBLIC_CATALOGUE_ONLY=1` consente di verificare questo percorso anche su una macchina che dispone dell’archivio privato. Un percorso di archivio configurato ma mancante continua a essere segnalato come errore, senza mascherarlo con dati meno recenti.

## Correzioni cartografiche

Il builder Python di Vercel esclude per impostazione predefinita `**/public/**`, anche se la directory è annidata sotto `data/`. `vercel.json` include quindi esplicitamente `data/public/catalogue.json` nella funzione `server.py`. Il controllo dopo il deploy deve verificare le API online, non soltanto il successo della build.

- Inquadramento iniziale, “Inquadra risultati” e filtro dell’area visibile considerano i poligoni reali anche senza pin.
- L’apertura delle particelle non richiede un asse di progetto.
- I subalterni con lo stesso riferimento catastale non duplicano il poligono visualizzato.
- Le opere senza geometrie aprono scheda e fonti. Nessuna coordinate viene ricavata dal centro comunale.
- I popup dichiarano quando nominativo, superficie e regime di occupazione non sono pubblicati o non verificati.
