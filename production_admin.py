"""Revisione locale delle trascrizioni dopo confronto con la pagina originale.

python production_admin.py review --row ID --fields correzione.json --operator NOME
Il JSON contiene solo i campi letti dal documento. Le versioni restano nell'audit.
"""
import argparse
import json
from pathlib import Path
from production_store import ProductionStore

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['review'])
    parser.add_argument('--row',required=True);parser.add_argument('--fields',required=True);parser.add_argument('--operator',required=True)
    parser.add_argument('--scope',choices=['completa','identificativi'],default='completa')
    args=parser.parse_args()
    ProductionStore().review_row(args.row,json.loads(Path(args.fields).read_text()),args.operator,args.scope)
    print('Revisione registrata con riferimento immutato a documento e pagina.')
