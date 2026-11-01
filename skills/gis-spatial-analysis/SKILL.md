---
name: gis-spatial-analysis
description: Realizza analisi GIS riproducibili su raster e vettori, trasformazioni CRS, overlay, PostGIS e cartografia. Usa quando correttezza spaziale e qualità dei dati influenzano il risultato.
---

# GIS e analisi spaziale avanzata

## Diagnosi iniziale

Inventaria layer, schema, identificatori, geometrie, estensione, risoluzione, NoData, CRS, datum, unità, licenza, epoca e provenienza. Leggi metadati e campioni senza caricare inutilmente tutto il dataset. Ricava dal quesito la scala, gli attributi necessari e la tolleranza accettabile.

Preferisci lo stack già usato: QGIS Processing per procedure di progetto, GDAL per raster/conversioni, GeoPandas/Shapely per vettori in memoria adeguati alle risorse, PostGIS per dataset condivisi o estesi. Registra versioni e verifica la disponibilità delle funzioni prima di scrivere workflow.

## Invarianti spaziali

- Distingui assegnazione del CRS e trasformazione. Non imporre EPSG:4326 a dati ignoti; controlla ordine degli assi nei protocolli e ordine XY nelle librerie. Per aree e distanze seleziona un CRS proiettato appropriato o calcoli geodetici motivati. Web Mercator non è una scelta metrica generale.
- Verifica operazione geodetica, area d'uso, accuratezza dichiarata e griglie disponibili; segnala fallback approssimati. Mantieni datum verticale e orizzontale distinti. Non sommare quote ellissoidiche e ortometriche senza trasformazione documentata.
- Controlla validità, geometrie vuote, duplicati e tipi prima degli overlay. Ripara su copie e misura variazioni di area, numero componenti e tipo; una riparazione può produrre multipart o collection. Non eliminare sliver con soglie arbitrarie.
- Prima degli spatial join dichiara predicato e cardinalità: intersects include contatti di bordo; within può escluderli. Per join molti-a-molti conserva una tabella relazionale o definisci aggregazione; non duplicare quantità in modo accidentale.
- Per mosaici e raster algebra allinea CRS, origine, risoluzione, estensione e NoData. Usa nearest per categorie; per dati continui motiva bilinear, cubic o aggregazione. Non trasformare NoData in zero e non assumere che ricampionare conservi somme o volumi.
- Per prestazioni usa filtri spaziali precoci, indici, blocchi e query set-based. In PostGIS ispeziona il piano quando la query è lenta; evita trasformazioni per riga non indicizzabili senza ragione. Per SQL parametrizza i valori e tratta separatamente gli identificatori.
- Per statistiche territoriali verifica denominatore, aree effettivamente coperte, pesi e campionamento. Valuta effetti della zonizzazione, autocorrelazione e disallineamento temporale quando influenzano l'inferenza.

## Risultati verificabili

Controlla conteggi prima/dopo, feature senza corrispondenza, bilancio delle aree o somme dove applicabile, campioni di bordo e confronti con casi di risultato noto. Distingui validità geometrica 2D da correttezza topologica o 3D. Riporta unità e cifre significative coerenti con l'accuratezza sorgente.

Consegna gli output richiesti e il workflow ripetibile; preferisci GeoPackage per scambi vettoriali locali con schema ricco e COG per raster distribuiti quando appropriato. Se richiesto Shapefile, gestisci esplicitamente limiti di campi, codifica e file accessori. Le mappe devono riportare legenda, unità, CRS, epoca e fonti utili alla loro interpretazione.

Documentazione da consultare per implementazione: [PROJ](https://proj.org/en/stable/operations/index.html), [gdalwarp](https://gdal.org/en/stable/programs/gdalwarp.html), [ST_IsValid](https://postgis.net/docs/ST_IsValid.html), [ST_MakeValid](https://postgis.net/docs/ST_MakeValid.html).
