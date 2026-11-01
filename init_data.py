"""Inizializza l'archivio di produzione senza generare opere o ditte."""
from production_store import ProductionStore

if __name__ == '__main__':
    store=ProductionStore()
    print(f'Archivio di produzione: {store.export_catalogue()}')
    print('Acquisizione: python collect_public_records.py --manifest config/fonti_pubbliche.json')
