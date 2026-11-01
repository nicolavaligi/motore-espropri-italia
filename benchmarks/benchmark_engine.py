"""Confronto riproducibile con una revisione Git; nessun servizio esterno.

Uso: .venv/bin/python benchmarks/benchmark_engine.py [revisione, default HEAD]
"""
import importlib.util
import json
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time

import geopandas as gpd
from shapely.geometry import LineString, box

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import motore_cadastral_engine as nuovo


def misura(fn, ripetizioni=3):
    tempi = []
    for _ in range(ripetizioni):
        start = time.perf_counter()
        risultato = fn()
        tempi.append(time.perf_counter() - start)
    return statistics.median(tempi), risultato


def main():
    revisione = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
    sorgente = subprocess.check_output(["git", "show", f"{revisione}:motore_cadastral_engine.py"], cwd=ROOT)
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "motore_prima.py"
        path.write_bytes(sorgente)
        spec = importlib.util.spec_from_file_location("motore_prima", path)
        prima = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = prima
        spec.loader.exec_module(prima)
        catasto = gpd.GeoDataFrame(geometry=[box(500000+x*100, 5000000+y*100, 500080+x*100, 5000080+y*100)
                                              for y in range(100) for x in range(200)], crs=32632)
        tracciato = gpd.GeoDataFrame(geometry=[LineString([(500040, 4999900), (500040, 5010100)])], crs=32632)
        vecchio_tempo, vecchio = misura(lambda: prima.elabora_interferenze_spaziali(catasto, tracciato))
        nuovo_tempo, risultato = misura(lambda: nuovo.elabora_interferenze_spaziali(catasto, tracciato))
        assert len(vecchio) == len(risultato) == 100
        assert abs(vecchio.sup_esproprio_mq.sum() - risultato.sup_esproprio_mq.sum()) < 0.01
        print(json.dumps({"baseline": revisione, "particelle": len(catasto), "interferite": len(risultato),
                          "ripetizioni": 3, "mediana_prima_s": round(vecchio_tempo, 6),
                          "mediana_dopo_s": round(nuovo_tempo, 6),
                          "accelerazione": round(vecchio_tempo / nuovo_tempo, 2)}, indent=2))


if __name__ == "__main__":
    main()
