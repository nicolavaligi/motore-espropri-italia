# Radar operativo — 1 novembre 2026

La homepage `/`, `/radar` e `/radar.html` riproducono la struttura visiva del riferimento `opere-radar.netlify.app/radar.html`: intestazione, sette KPI, stato acquisizioni, filtri, mappa e catalogo laterale. Il riferimento è stato analizzato con la skill `reverse-engineering`; l'implementazione usa le API del motore e MapLibre già adottato dal progetto. La mappa con gli strumenti precedenti resta in `/mappa`.

`GET /api/radar` proietta il catalogo attraverso un'allowlist: distingue origine, disponibilità dei documenti e fase procedurale esplicitamente dichiarata. La presenza di un PDF non determina una fase; un elenco non acquisito non equivale ad assenza di elenco presso l'ente. Nessun proprietario, dettaglio di errore o percorso privato viene aggiunto alla proiezione.

I KPI e il CSV usano tutti i risultati filtrati. La lista ha paginazione da 25 elementi. Le date delle acquisizioni sono assolute e derivate dalle evidenze; un catalogo pubblico senza tentativi non viene presentato come monitoraggio live del crawler.

Le frecce azzurre senza punto generale sono ancorate a un vertice già presente nelle geometrie catastali documentate e aprono le relative particelle. Sono controlli di navigazione, non nuove coordinate dell'opera: `geo` resta invariato. Le opere senza punto e senza geometrie rimangono nel catalogo con posizione da acquisire. I subalterni non duplicano le particelle disegnate.

Nessun record del sito di riferimento, dato personale, database o originale locale è stato importato per ricostruire l'interfaccia. Rimane in uso lo snapshot pubblico esistente, con le relative lacune e fonti. Non è stata modificata alcuna cartella Drive.
