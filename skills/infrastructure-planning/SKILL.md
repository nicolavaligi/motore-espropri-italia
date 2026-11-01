---
name: infrastructure-planning
description: Confronta alternative infrastrutturali con analisi GIS di corridoi, interferenze, particelle, accessibilità e movimenti terra. Usa per fattibilità e supporto alla pianificazione con assunzioni e incertezze esplicite.
---

# Pianificazione infrastrutturale avanzata

## Decisione e base dati

Identifica infrastruttura, fase progettuale, area, alternative, obiettivi, criteri tecnici e dati disponibili. Distingui requisiti vincolanti, preferenze e ipotesi. Definisci accuratezza e scala adeguate alla decisione; dati di screening non giustificano dettagli esecutivi.

Inventaria rilievi, DTM, reti esistenti, particelle, uso del suolo, vincoli e studi tematici con fonte ed epoca. Per obblighi normativi, fasce o procedure espropriative richiesti consulta fonti ufficiali aggiornate e cita giurisdizione e data; se non verificati trattali come parametri da confermare. Non ricavare titolarità o confini legali definitivi da una semplice sovrapposizione cartografica.

## Analisi delle alternative

- Porta le fonti in riferimenti compatibili, conserva ID e provenienza. Controlla disallineamenti prima di classificare interferenze o particelle coinvolte. Usa la skill GIS se disponibile per overlay e QA geometrico.
- Separa maschere di esclusione da superfici di costo; vincoli invalicabili non sono semplicemente pesi alti. Dichiara risoluzione, normalizzazione, direzione dei criteri e pesi. Non contare due volte criteri fortemente correlati.
- Per least-cost path considera effetti della griglia e anisotropia quando pendenza/direzione influenzano il costo. Un percorso raster non costituisce un tracciato conforme: verifica raggi, pendenze, attraversamenti, profilo e costruibilità nella fase adeguata.
- Confronta alternative sulla stessa copertura e base temporale: lunghezza, pendenze, attraversamenti, interferenze, impatti, accessi, suolo e costi documentati. Mantieni disponibili i valori originari accanto ai punteggi aggregati.
- Per analisi multicriterio misura sensibilità a pesi, soglie, risoluzione e dati incerti. Riporta quando cambia la graduatoria; non presentare il punteggio massimo come scelta oggettiva unica.
- Per reti usa topologia con nodi, direzioni, restrizioni e impedenza. Valuta disconnessioni e attraversamenti a livelli diversi; intersezioni geometriche non implicano connessioni reali.

## Quantità, particelle e incertezza

Per movimenti terra allinea DTM e superficie di progetto per CRS XYZ, griglia, area e NoData. Definisci delta = z_progetto - z_terreno: volume riporto = somma(max(delta,0) * area_cella), scavo = somma(max(-delta,0) * area_cella) per celle valide. Specifica trattamento di celle parziali e bordo. Questi sono volumi geometrici; coefficienti di rigonfiamento, compattazione, terreno vegetale e materiali inadatti richiedono dati distinti.

Per interferenze e piani particellari mantieni separati occupazione permanente, temporanea e servitù. Usa chiavi amministrative complete, non il solo numero di particella. Aggrega per chiave senza duplicare aree sovrapposte dello stesso regime; conserva relazione con la geometria sorgente e segnala sovrapposizioni tra regimi. Controlla unità, somma superfici, sliver e limiti della cartografia. Se estrai dati da PDF/OCR conserva pagina, testo originale e incertezza; non inventare campi illeggibili o dedurre unità non espresse.

Per stime economiche riporta quantità, prezzo unitario, fonte, data, valuta e voci escluse. Evita precisione superiore ai dati disponibili. Propaga l'incertezza con scenari o metodi motivati, indicando dipendenze tra errori e parametri.

Consegna matrice delle alternative, layer di tracciati/corridoi e interferenze, tabelle riconciliabili alle geometrie, workflow e relazione su ipotesi, lacune e sensibilità. Distingui analisi completate da verifiche progettuali o amministrative ancora necessarie.
