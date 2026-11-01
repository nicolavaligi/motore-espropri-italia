"""Catalogo cartografico pubblico, immutabile: nessun accesso al database privato."""
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path

PUBLIC_CATALOGUE_PATH = Path(__file__).parent / 'data' / 'public' / 'catalogue.json'


class PublishedArchive:
    def __init__(self, path=PUBLIC_CATALOGUE_PATH):
        self.path = Path(path)
        self.data = _read_snapshot(str(self.path), self.path.stat().st_mtime_ns)

    def catalogue(self):
        return deepcopy(self.data['opere'])

    def rows(self, slug):
        return deepcopy(self.data['particelle'].get(slug, []))

    def documents(self, slug):
        return next((op['documenti'] for op in self.catalogue() if op['slug'] == slug), [])

    def document(self, identifier):
        return next((d for op in self.catalogue() for d in op['documenti'] if d['id'] == identifier), None)

    def status(self):
        meta = self.data['metadata']
        return dict(opere=len(self.data['opere']), documenti=sum(len(o['documenti']) for o in self.data['opere']),
                    righe=sum(len(rows) for rows in self.data['particelle'].values()), pagine=None,
                    particelle_uniche=meta['particelle_uniche'], ultime_acquisizioni=[], esiti_pagine=[],
                    completezza='non_certificata', modalita='catalogo_pubblico_sola_lettura',
                    aggiornato_il=meta['esportato_il'], originali_locali_pubblicati=False,
                    nota='Catalogo pubblico di fonti e geometrie documentate. Originali disponibili presso gli enti; nominativi e archivio locale non pubblicati.')


@lru_cache(maxsize=2)
def _read_snapshot(path, modified):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if data.get('schema') != 'motore-espropri-catalogo-pubblico-v1':
        raise ValueError('Schema del catalogo pubblico non valido')
    if not isinstance(data.get('opere'), list) or not isinstance(data.get('particelle'), dict):
        raise ValueError('Catalogo pubblico non valido')
    return data
