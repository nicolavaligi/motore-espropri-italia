"""Importazione di originali VIA già acquisiti, con OCR verificabile pagina per pagina.

python import_rfi_archive.py --originals DIR --index via_index.json --ocr DIR
Non attribuisce autenticità all'OCR e non genera valori economici o coordinate.
"""
import argparse
import json
from pathlib import Path
import re

import pdfplumber
from ocr_rfi import ELENCHI
from production_store import ProductionStore

SLUG='RFI-RHO-GALLARATE-PROGETTO-DEFINITIVO-2013'


def normalized_page(page):
    raw_owner=page.get('ditta','').strip()
    # Le etichette di griglia non fanno parte dell'intestazione: il testo originale resta nell'evidenza.
    owner=re.split(r'IDENTIFICAZIONE|TITOLO DELL.OCCUPAZIONE',raw_owner,flags=re.I)[0].strip(' |')
    owner=re.sub(r'^(?:initivo|definitivo|progetto)\s+', '', owner, flags=re.I)
    rows=[]
    for record in page.get('righe',[]):
        if not re.fullmatch(r'\d{1,4}[A-Za-z]?',record.get('foglio','')) or not re.fullmatch(r'\d+[A-Za-z]?',record.get('mappale','')):
            continue
        # OCR conservato come trascrizione da verificare: nessun importo stimato.
        rows.append({'comune':page['comune'], 'foglio':record['foglio'], 'mappale':record['mappale'],
                     'sub':record.get('sub'), 'intestatario':owner or None, 'superfici_mq':{},
                     'numero_piano_ocr':record.get('n_piano'), 'stato_estrazione':'ocr_da_verificare',
                     'raw':{'intestazione':raw_owner,'celle':record}, 'geometry':None})
    if page.get('errore'):
        status='errore_ocr'
    elif rows:
        status='ocr_da_verificare'
    else:
        status='nessuna_riga_riconosciuta'
    return {'pagina':page['pagina'],'righe':rows,'stato':status,
            'nota':page.get('errore') or page.get('nota') or ('Foglio/mappale e nominativi OCR richiedono verifica sull’originale' if rows else 'Pagina senza righe riconosciute: controllo richiesto')}


def import_archive(originals,index,ocr,store=None):
    store=store or ProductionStore()
    titles=json.loads(Path(index).read_text())
    result=[]
    for code,comune in ELENCHI.items():
        path=Path(originals)/f'{code}.pdf'
        if not path.exists():continue
        identifier=store.archive_pdf(SLUG,path.read_bytes(),f'https://va.mite.gov.it/File/Documento/{code}',
                                     'https://va.mite.gov.it/it-IT/Oggetti/Documentazione/1368/1849',
                                     titles[code][0],mode='originale_precedentemente_acquisito',kind='elenco_ditte')
        with pdfplumber.open(path) as pdf:total=len(pdf.pages)
        pages=[]
        for n in range(1,total+1):
            file=Path(ocr)/f'{code}-{n:04}.json'
            if file.exists():pages.append(normalized_page(json.loads(file.read_text())))
            else:pages.append({'pagina':n,'righe':[],'stato':'ocr_necessario','nota':'Pagina non elaborata'})
        store.save_extraction(identifier,pages,total,'rfi-griglia-ocr-v1')
        result.append({'documento':identifier,'comune':comune,'pagine':total,'righe_ocr':sum(len(p['righe']) for p in pages)})
    store.export_catalogue()
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--originals',required=True);parser.add_argument('--index',required=True);parser.add_argument('--ocr',required=True)
    args=parser.parse_args()
    print(json.dumps(import_archive(args.originals,args.index,args.ocr),ensure_ascii=False,indent=2))
