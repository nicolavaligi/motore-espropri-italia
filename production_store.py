"""Archivio documentale di produzione. SQLite e PDF locali, mai dati sintetici."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from urllib.parse import urlsplit

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_ROOT = Path(os.environ.get('MOTORE_ARCHIVE_ROOT') or (BASE_DIR / 'data' / 'production')).expanduser().resolve()


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def public_url(url):
    parts = urlsplit(url)
    if parts.scheme not in {'https', 'http'} or not parts.hostname or parts.username or parts.password:
        raise ValueError('Richiesto URL pubblico HTTP(S) senza credenziali')
    return url


class ProductionStore:
    def __init__(self, root=None):
        self.root = Path(root or DEFAULT_ROOT)
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = self.root / 'archivio.sqlite3'
        with self.connect() as con:
            con.executescript('''
                CREATE TABLE IF NOT EXISTS opere (
                    slug TEXT PRIMARY KEY, metadata TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS documenti (
                    id TEXT PRIMARY KEY, opera_slug TEXT NOT NULL REFERENCES opere(slug),
                    sha256 TEXT NOT NULL, fonte_url TEXT NOT NULL, pagina_fonte TEXT NOT NULL,
                    titolo TEXT NOT NULL, filename TEXT NOT NULL, byte_size INTEGER NOT NULL,
                    acquisito_il TEXT NOT NULL, modalita TEXT NOT NULL, parser TEXT,
                    stato TEXT NOT NULL DEFAULT 'archiviato', totale_pagine INTEGER, tipo TEXT NOT NULL DEFAULT 'documento', attivo INTEGER NOT NULL DEFAULT 1,
                    UNIQUE(opera_slug, sha256, fonte_url));
                CREATE TABLE IF NOT EXISTS righe (
                    id TEXT PRIMARY KEY, documento_id TEXT NOT NULL REFERENCES documenti(id),
                    pagina INTEGER NOT NULL CHECK(pagina>0), indice INTEGER NOT NULL,
                    payload TEXT NOT NULL, stato TEXT NOT NULL,
                    UNIQUE(documento_id, pagina, indice));
                CREATE TABLE IF NOT EXISTS pagine (
                    documento_id TEXT NOT NULL REFERENCES documenti(id),
                    pagina INTEGER NOT NULL, stato TEXT NOT NULL, nota TEXT,
                    PRIMARY KEY(documento_id,pagina));
                CREATE TABLE IF NOT EXISTS tentativi (
                    id INTEGER PRIMARY KEY, opera_slug TEXT, url TEXT NOT NULL,
                    eseguito_il TEXT NOT NULL, stato TEXT NOT NULL, dettaglio TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS revisioni (
                    id INTEGER PRIMARY KEY, riga_id TEXT NOT NULL REFERENCES righe(id),
                    verificato_il TEXT NOT NULL, operatore TEXT NOT NULL,
                    precedente TEXT NOT NULL, successivo TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS idx_documenti_opera ON documenti(opera_slug);
                CREATE INDEX IF NOT EXISTS idx_righe_documento ON righe(documento_id,pagina);
            ''')
            if 'tipo' not in {r[1] for r in con.execute('PRAGMA table_info(documenti)')}:
                con.execute("ALTER TABLE documenti ADD COLUMN tipo TEXT NOT NULL DEFAULT 'documento'")
            if 'attivo' not in {r[1] for r in con.execute('PRAGMA table_info(documenti)')}:
                con.execute("ALTER TABLE documenti ADD COLUMN attivo INTEGER NOT NULL DEFAULT 1")

    @contextmanager
    def connect(self):
        con = sqlite3.connect(self.db, timeout=30)
        con.row_factory = sqlite3.Row
        con.execute('PRAGMA foreign_keys=ON')
        con.execute('PRAGMA journal_mode=WAL')
        try:
            with con:
                yield con
        finally:
            con.close()

    def register_opera(self, opera):
        slug = opera['slug']
        if not slug or not opera.get('titolo'):
            raise ValueError('Opera priva di identificativo o titolo')
        public_url(opera['fonte_atto_url'])
        if opera.get('tipo_dati') != 'documentale':
            raise ValueError('Il catalogo accetta solo opere documentate')
        if opera.get('coordinate') and not opera.get('fonte_coordinate'):
            raise ValueError('Coordinate prive di fonte: localizzazione non accettata')
        if opera.get('tracciato_geojson') and not opera.get('fonte_tracciato_url'):
            raise ValueError('Tracciato privo di documento di provenienza')
        # Elenchi e dati geospaziali devono passare dai rispettivi importatori.
        meta = {k:v for k,v in opera.items() if k not in {'ditte', 'particellare', 'particelle'}}
        with self.connect() as con:
            previous = con.execute('SELECT metadata FROM opere WHERE slug=?', (slug,)).fetchone()
            if previous:
                existing = json.loads(previous['metadata'])
                # La scansione di una pagina non cancella localizzazioni già documentate.
                for key in ('coordinate','fonte_coordinate','tracciato_geojson','fonte_tracciato_url'):
                    if not meta.get(key) and existing.get(key):meta[key]=existing[key]
            con.execute('INSERT INTO opere VALUES (?,?,?) ON CONFLICT(slug) DO UPDATE SET metadata=excluded.metadata,updated_at=excluded.updated_at',
                        (slug, json.dumps(meta, ensure_ascii=False, allow_nan=False), utcnow()))

    def archive_pdf(self, slug, content, source_url, source_page, title, mode='download_http', kind='documento'):
        public_url(source_url)
        public_url(source_page)
        if not content.lstrip().startswith(b'%PDF-'):
            raise ValueError('Il contenuto acquisito non è un PDF')
        sha = hashlib.sha256(content).hexdigest()
        identifier = hashlib.sha256(f'{slug}\0{sha}'.encode()).hexdigest()[:32]
        folder = self.root / 'documenti'
        folder.mkdir(exist_ok=True)
        filename = f'{sha}.pdf'
        path = folder / filename
        if not path.exists():
            temporary = folder / f'{sha}.{os.getpid()}.tmp'
            try:
                with temporary.open('xb') as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
        elif hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            raise ValueError('Checksum dell’archivio incoerente')
        with self.connect() as con:
            con.execute('UPDATE documenti SET attivo=0 WHERE opera_slug=? AND fonte_url=? AND id!=?', (slug,source_url,identifier))
            con.execute('''INSERT OR IGNORE INTO documenti
                (id,opera_slug,sha256,fonte_url,pagina_fonte,titolo,filename,byte_size,acquisito_il,modalita,tipo)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                (identifier, slug, sha, source_url, source_page, title, filename, len(content), utcnow(), mode, kind))
            con.execute('UPDATE documenti SET attivo=1 WHERE id=?',(identifier,))
        return identifier

    def save_extraction(self, doc_id, pages, total_pages, parser):
        """Una riestrazione sostituisce transazionalmente le righe del documento."""
        with self.connect() as con:
            if not con.execute('SELECT 1 FROM documenti WHERE id=?', (doc_id,)).fetchone():
                raise ValueError('Documento non archiviato')
            previous = {r['id']:dict(r) for r in con.execute('SELECT * FROM righe WHERE documento_id=?',(doc_id,))}
            # Le righe verificate hanno un audit: un nuovo parser non può eliminarle.
            # Keep every row that has an audit trail, including identifier-only
            # reviews; parser re-runs must never erase a human correction.
            reviewed = {r['riga_id'] for r in con.execute("SELECT riga_id FROM revisioni WHERE riga_id IN (SELECT id FROM righe WHERE documento_id=?)",(doc_id,))}
            con.execute("DELETE FROM righe WHERE documento_id=? AND id NOT IN (SELECT riga_id FROM revisioni)", (doc_id,))
            con.execute('DELETE FROM pagine WHERE documento_id=?', (doc_id,))
            for page in pages:
                number = int(page['pagina'])
                if not 1 <= number <= total_pages:
                    raise ValueError('Pagina fuori dal documento')
                rows = page.get('righe', [])
                status = page.get('stato') or ('estratta' if rows else 'da_verificare')
                con.execute('INSERT INTO pagine VALUES (?,?,?,?)', (doc_id, number, status, page.get('nota')))
                for index, record in enumerate(rows, 1):
                    if not record.get('foglio') or not record.get('mappale'):
                        raise ValueError('Riga priva di foglio o mappale: conservare nelle evidenze, non tra le particelle')
                    record = dict(record, stato_geometria='non_localizzata')
                    record.pop('geometry',None)
                    identifier = hashlib.sha256(f'{doc_id}:{number}:{index}'.encode()).hexdigest()[:32]
                    if identifier in reviewed:continue
                    old = previous.get(identifier)
                    if old:
                        old_payload = json.loads(old['payload'])
                        if all(old_payload.get(k)==record.get(k) for k in ('comune','foglio','mappale','sub')):
                            for key in ('geometry','stato_geometria','riferimento_catastale','fonte_geometria','fonte_geometria_sha256','geometria_acquisita_il','crs_sorgente','crs_geometry','licenza_geometria','match_geometria','sezione_catastale_geometria'):
                                if key in old_payload:record[key]=old_payload[key]
                    con.execute('INSERT INTO righe VALUES (?,?,?,?,?,?)',
                                (identifier, doc_id, number, index, json.dumps(record, ensure_ascii=False, allow_nan=False),
                                 record.get('stato_estrazione', 'estratta_da_testo')))
            con.execute('UPDATE documenti SET stato=?,totale_pagine=?,parser=? WHERE id=?',
                        ('estrazione_parziale', total_pages, parser, doc_id))

    def log_attempt(self, slug, url, status, detail):
        with self.connect() as con:
            con.execute('INSERT INTO tentativi(opera_slug,url,eseguito_il,stato,dettaglio) VALUES (?,?,?,?,?)',
                        (slug, url, utcnow(), status, str(detail)[:2000]))

    def document(self, identifier):
        with self.connect() as con:
            row = con.execute('SELECT * FROM documenti WHERE id=?', (identifier,)).fetchone()
        return dict(row) if row else None

    def documents(self, slug):
        with self.connect() as con:
            return [dict(r) for r in con.execute('''SELECT d.*,COUNT(r.id) AS righe_estratte
                FROM documenti d LEFT JOIN righe r ON r.documento_id=d.id
                WHERE d.opera_slug=? GROUP BY d.id ORDER BY d.titolo''', (slug,))]

    def rows(self, slug):
        with self.connect() as con:
            data = con.execute('''SELECT r.*,d.fonte_url,d.titolo,d.sha256 FROM righe r
                JOIN documenti d ON d.id=r.documento_id WHERE d.opera_slug=? AND d.attivo=1 ORDER BY d.titolo,r.pagina,r.indice''', (slug,)).fetchall()
        result = []
        for r in data:
            payload = json.loads(r['payload'])
            payload.update(id=r['id'], documento_id=r['documento_id'], fonte_pagina=r['pagina'],
                           fonte_url=r['fonte_url'], fonte_sha256=r['sha256'],
                           documento_url=f"/api/documenti/{r['documento_id']}/file#page={r['pagina']}", stato_estrazione=r['stato'])
            result.append(payload)
        return result

    def catalogue(self):
        with self.connect() as con:
            opere = [json.loads(r['metadata']) for r in con.execute('SELECT metadata FROM opere ORDER BY slug')]
        for op in opere:
            rows = self.rows(op['slug'])
            docs = self.documents(op['slug'])
            op.update(documenti=[{k:v for k,v in d.items() if k != 'filename'} | {'archivio_url':f"/api/documenti/{d['id']}/file"} for d in docs],
                      particellare_url=f"/api/opere/{op['slug']}/particelle", ditte=[self.legacy_row(r) for r in rows], has_pda=bool(rows) or any(d['tipo']=='elenco_ditte' and d['attivo'] for d in docs),
                      completezza_catastale='non_certificata',
                      righe_catastali=len(rows), particelle_localizzate=sum(bool(r.get('geometry')) for r in rows),
                      stato_opera='DOCUMENTI_ARCHIVIATI' if docs else 'DOCUMENTI_DA_ACQUISIRE',
                      ente=op.get('ente_promotore'), geo=op.get('coordinate'), importo_eur=op.get('importo_lavori_eur'))
        return opere

    @staticmethod
    def legacy_row(row):
        sup = row.get('superfici_mq') or {}
        keys = ('id', 'intestatario', 'comune', 'foglio', 'mappale', 'sub', 'geometry', 'stato_estrazione',
                'stato_identificativi', 'stato_geometria', 'riferimento_catastale','fonte_geometria',
                'fonte_geometria_sha256','documento_url', 'documento_id', 'fonte_pagina', 'fonte_url', 'fonte_sha256')
        out = {k:row.get(k) for k in keys}
        return dict(out, mappali=row['mappale'], sup_mq=sup.get('esproprio'),
                    sup_esproprio_mq=sup.get('esproprio'), sup_asservimento_mq=sup.get('asservimento'),
                    indennita=None, delta=False)

    def export_catalogue(self):
        path = self.root / 'opere.json'
        tmp = self.root / f'opere.{os.getpid()}.tmp'
        try:
            tmp.write_text(json.dumps(self.catalogue(), ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
            os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)
        return path

    def status(self):
        with self.connect() as con:
            counts = {table:con.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
                      for table in ('opere', 'documenti', 'righe', 'pagine')}
            attempts = [dict(r) for r in con.execute('SELECT * FROM tentativi ORDER BY id DESC LIMIT 100')]
            pages = [dict(r) for r in con.execute('SELECT stato,COUNT(*) AS totale FROM pagine GROUP BY stato')]
        return dict(counts, ultime_acquisizioni=attempts, esiti_pagine=pages, completezza='non_certificata')

    def review_row(self, identifier, fields, operator, scope='completa'):
        allowed = {'comune','foglio','mappale','sub','intestatario','codice_fiscale','quota','diritto','superfici_mq'}
        identifiers = {'comune','foglio','mappale','sub'}
        if scope not in {'completa','identificativi'} or not fields or set(fields)-allowed or (scope=='identificativi' and set(fields)-identifiers) or not operator.strip():
            raise ValueError('Campi di revisione o operatore non validi')
        with self.connect() as con:
            row=con.execute('SELECT * FROM righe WHERE id=?',(identifier,)).fetchone()
            if not row:raise ValueError('Riga non presente')
            before=json.loads(row['payload']);after=dict(before,**fields)
            required = ('comune','foglio','mappale') if scope=='identificativi' else ('comune','foglio','mappale','intestatario')
            for key in required:
                if not str(after.get(key) or '').strip():raise ValueError(f'Campo obbligatorio: {key}')
            if any(before.get(k)!=after.get(k) for k in ('comune','foglio','mappale','sub')):
                for key in list(after):
                    if key in {'geometry','riferimento_catastale','crs_sorgente','crs_geometry','licenza_geometria','geometria_acquisita_il','match_geometria','sezione_catastale_geometria'} or key.startswith('fonte_geometria'):
                        after.pop(key,None)
                after['stato_geometria']='non_localizzata'
            if scope=='completa':
                after['stato_estrazione']='verificata_su_documento'
            else:
                after['stato_identificativi']='verificati_su_documento'
            encoded=json.dumps(after,ensure_ascii=False,allow_nan=False)
            con.execute('INSERT INTO revisioni(riga_id,verificato_il,operatore,precedente,successivo) VALUES (?,?,?,?,?)',
                        (identifier,utcnow(),operator,json.dumps(before,ensure_ascii=False),encoded))
            status='verificata_su_documento' if scope=='completa' else row['stato']
            con.execute("UPDATE righe SET payload=?,stato=? WHERE id=?",(encoded,status,identifier))
        self.export_catalogue()
