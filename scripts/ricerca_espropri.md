# Verifica della ricerca di opere con espropri

Genera un piano di ricerca con link apribili per territorio e tipo di atto. I domini provengono dal manifest locale del motore, quando disponibile. Aggiungi i domini di Comuni, BUR e altri enti di interesse con `--dominio`, ripetibile come `--territorio`.

```sh
python3 scripts/verifica_ricerca_espropri.py \
  --territorio Lombardia --territorio Lecco \
  --dominio regione.lombardia.it --dal 2026-09-01 \
  --output ricerche.json
```

Apri i link `url_ricerca` e raccogli gli atti pertinenti in un CSV UTF-8. Il filtro temporale del motore di ricerca serve per orientarsi. Usa la data indicata sull'atto o sulla pagina di pubblicazione per compilare il campo `data`. Lascia vuoti i dati assenti. Il CSV richiede tutte le intestazioni e accetta titoli con virgole racchiusi tra virgolette.

```csv
titolo,url,data,territorio,cup,lotto
"Avviso di avvio del procedimento espropriativo, lotto 2",https://example.org/atto/123,2026-10-15,Lecco,,2
```

```sh
python3 scripts/verifica_ricerca_espropri.py \
  --territorio Lecco --dominio regione.lombardia.it --dal 2026-09-01 \
  --risultati risultati.csv --output priorita.json
```

Controlla per prime le segnalazioni `da_verificare`. Il punteggio combina il tipo di atto suggerito dal titolo, il dominio, la data e la presenza di CUP e lotto. La data mancante resta visibile. Le fonti già censite conservano il collegamento ai fascicoli noti. Il riepilogo conta anche duplicati, righe scartate e segnalazioni fuori periodo.

Prima di valutare un incarico, apri l'atto e verifica ente, opera, lotto, fase e termine eventualmente indicato. Una pagina di raccolta può contenere atti diversi. Lo script lavora su riferimenti documentali e metadati dell'opera. Per rendere disponibile la consulenza puoi usare una pagina informativa o iniziative locali a cui gli interessati possano aderire.
