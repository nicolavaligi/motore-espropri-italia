#!/usr/bin/env python3
"""Esporta solo fonti pubbliche e geometrie riscontrate, mai nominativi o originali."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlsplit

from shapely import get_coordinates
from shapely.geometry import shape

OPERA_FIELDS = ('slug', 'titolo', 'ente_promotore', 'regione', 'provincia', 'comune', 'cup', 'tipo_dati',
                'fonte_atto_url', 'stato_verifica')
DOC_FIELDS = ('id', 'titolo', 'fonte_url', 'pagina_fonte', 'sha256', 'acquisito_il', 'tipo', 'attivo',
              'totale_pagine', 'stato', 'righe_estratte')
ROW_FIELDS = ('comune', 'foglio', 'mappale', 'sub', 'sezione', 'geometry', 'riferimento_catastale',
              'stato_identificativi', 'stato_geometria', 'fonte_geometria', 'fonte_geometria_sha256',
              'geometria_acquisita_il', 'crs_sorgente', 'crs_geometry', 'licenza_geometria',
              'sezione_catastale_geometria', 'match_geometria')


def public_url(value):
    parts = urlsplit(value or '')
    if parts.scheme not in {'http', 'https'} or not parts.hostname or parts.username or parts.password:
        raise ValueError('Fonte pubblica non valida')
    return value


def export_public_catalogue(archive_root, destination):
    database = Path(archive_root).resolve() / 'archivio.sqlite3'
    con = sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)
    con.row_factory = sqlite3.Row
    try:
        # Una transazione di sola lettura mantiene coerenti metadati e righe.
        con.execute('BEGIN')
        opere, particelle = [], {}
        for record in con.execute('SELECT slug,metadata FROM opere ORDER BY slug'):
            original = json.loads(record['metadata'])
            if original.get('tipo_dati') != 'documentale':
                continue
            public_url(original.get('fonte_atto_url'))
            op = {key: original.get(key) for key in OPERA_FIELDS}
            docs = []
            for doc in con.execute('''SELECT d.*,COUNT(r.id) AS righe_estratte FROM documenti d
                LEFT JOIN righe r ON r.documento_id=d.id WHERE d.opera_slug=? AND d.attivo=1
                GROUP BY d.id ORDER BY d.titolo,d.id''', (record['slug'],)):
                public_url(doc['fonte_url'])
                item = {key: doc[key] for key in DOC_FIELDS}
                item.update(disponibilita='presso_ente', archivio_url=f"/api/documenti/{doc['id']}/file",
                            righe_pubblicate=0)
                docs.append(item)
            rows = []
            total_rows = 0
            for row in con.execute('''SELECT r.*,d.fonte_url,d.sha256 FROM righe r JOIN documenti d
                ON d.id=r.documento_id WHERE d.opera_slug=? AND d.attivo=1
                ORDER BY r.documento_id,r.pagina,r.indice''', (record['slug'],)):
                total_rows += 1
                payload = json.loads(row['payload'])
                if not payload.get('geometry'):
                    continue
                # Pubblicare solo abbinamenti controllati con evidenza e licenza.
                if payload.get('stato_identificativi') != 'verificati_su_documento':
                    continue
                public_url(payload.get('fonte_geometria'))
                if not re.fullmatch(r'[a-f0-9]{64}', payload.get('fonte_geometria_sha256', '')) or not payload.get('licenza_geometria'):
                    raise ValueError('Geometria priva di checksum o licenza')
                geom = shape(payload['geometry'])
                if payload.get('crs_geometry') != 'EPSG:4326' or geom.geom_type not in {'Polygon', 'MultiPolygon'} or not geom.is_valid or geom.is_empty:
                    raise ValueError('Geometria non valida per la pubblicazione WGS84')
                if not all(math.isfinite(float(v)) for p in get_coordinates(geom) for v in p):
                    raise ValueError('Coordinate non finite')
                minx, miny, maxx, maxy = geom.bounds
                if not (-180 <= minx <= maxx <= 180 and -90 <= miny <= maxy <= 90):
                    raise ValueError('Coordinate fuori WGS84')
                item = {key: payload.get(key) for key in ROW_FIELDS}
                item.update(id=row['id'], documento_id=row['documento_id'], fonte_pagina=row['pagina'],
                            fonte_url=row['fonte_url'], fonte_sha256=row['sha256'], intestatario=None,
                            stato_estrazione='intestazione_non_pubblicata',
                            documento_url=f"/api/documenti/{row['documento_id']}/file#page={row['pagina']}")
                rows.append(item)
            for doc in docs:
                doc['righe_pubblicate'] = sum(r['documento_id'] == doc['id'] for r in rows)
            ditte = [dict(row, mappali=row['mappale'], sup_mq=None, sup_esproprio_mq=None,
                          sup_asservimento_mq=None, indennita=None, delta=False) for row in rows]
            references = {row['riferimento_catastale'] for row in rows}
            op.update(documenti=docs, ditte=ditte, geo=None, ente=op.get('ente_promotore'),
                      tipo_dati='documentale', importo_eur=None,
                      stato_opera='DOCUMENTI_ARCHIVIATI' if docs else 'DOCUMENTI_DA_ACQUISIRE',
                      particellare_url=f"/api/opere/{op['slug']}/particelle", has_pda=any(d['tipo']=='elenco_ditte' for d in docs),
                      righe_catastali=len(rows), righe_catastali_archivio=total_rows,
                      particelle_localizzate=len(rows), particelle_uniche=len(references),
                      completezza_catastale='non_certificata', modalita_archivio='catalogo_pubblico_sola_lettura')
            # Coordinate preesistenti ammesse soltanto se accompagnate da fonte.
            coordinates = original.get('coordinate')
            if coordinates and original.get('fonte_coordinate'):
                public_url(original['fonte_coordinate'])
                x, y = coordinates.get('lng'), coordinates.get('lat')
                if isinstance(x, (int, float)) and isinstance(y, (int, float)) and math.isfinite(x) and math.isfinite(y) and -180<=x<=180 and -90<=y<=90:
                    op.update(geo=coordinates, fonte_coordinate=original['fonte_coordinate'])
            opere.append(op)
            particelle[op['slug']] = rows
        all_rows = [r for rows in particelle.values() for r in rows]
        result = dict(schema='motore-espropri-catalogo-pubblico-v1', opere=opere, particelle=particelle,
                      metadata=dict(esportato_il=datetime.now(timezone.utc).isoformat(),
                                    modalita='catalogo_pubblico_sola_lettura',
                                    particelle_uniche=len({r['riferimento_catastale'] for r in all_rows}),
                                    righe_pubblicate=len(all_rows),
                                    nota='Sole fonti pubbliche e geometrie catastali riscontrate. Nessun nominativo, database o PDF locale. Copertura parziale.'))
        content = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content + '\n', encoding='utf-8')
        return {'opere': len(opere), 'righe_pubblicate': len(all_rows), 'particelle_uniche': result['metadata']['particelle_uniche'],
                'sha256': hashlib.sha256((content + '\n').encode()).hexdigest()}
    finally:
        con.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive_root')
    parser.add_argument('destination')
    args = parser.parse_args()
    print(json.dumps(export_public_catalogue(args.archive_root, args.destination)))
