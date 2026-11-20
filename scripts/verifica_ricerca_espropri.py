#!/usr/bin/env python3
"""Genera ricerche e classifica segnalazioni documentali di opere con espropri."""

import argparse
import csv
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
SIGNALS = (
    ("avviso di avvio", r"avviso.{0,40}avvio|avvio del procedimento", 5),
    ("deposito del piano", r"deposito.{0,45}particellar", 5),
    ("vincolo espropriativo", r"vincolo.{0,30}(?:espropri|esproprio)", 4),
    ("pubblica utilità", r"dichiarazione.{0,30}pubblica utilità", 4),
    ("piano particellare", r"pian[oi] particellar", 3),
    ("decreto di esproprio", r"decret[oi].{0,20}espropr", 2),
    ("indennità", r"indennità.{0,25}(?:espropr|provvisori)", 2),
)
QUERY_TERMS = (
    ('"avvio del procedimento" "esproprio"', "avviso"),
    ('"piano particellare" "deposito"', "elaborato"),
    ('"vincolo preordinato all’esproprio"', "vincolo"),
    ('"dichiarazione di pubblica utilità" "esproprio"', "atto"),
    ('"decreto di esproprio"', "decreto"),
)


def public_url(value):
    parts = urlsplit(value.strip())
    if parts.scheme not in {"https", "http"} or not parts.hostname or parts.username is not None:
        raise ValueError("URL HTTP(S) pubblico richiesto")
    query = sorted((key, val) for key, val in parse_qsl(parts.query, keep_blank_values=True)
                   if not key.lower().startswith("utm_") and key.lower() not in {"fbclid", "gclid"})
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path or "/", urlencode(query), ""))


def domain(value):
    if not re.fullmatch(r"(?:[a-z0-9-]+\.)+[a-z0-9-]+", value.lower()):
        raise ValueError(f"Dominio non valido: {value}")
    return value.lower()


def read_manifest(path):
    if path is None:
        return []
    return json.loads(path.read_text(encoding="utf-8"))["sources"]


def build_queries(territories, domains, since):
    for territory in territories:
        territory = territory.replace('"', " ")
        for terms, category in QUERY_TERMS:
            base = f'{terms} "{territory}" after:{since.isoformat()}'
            for host in ["", *sorted(domains)]:
                query = f"site:{host} {base}" if host else base
                yield {
                    "territorio": territory,
                    "famiglia": category,
                    "dominio": host,
                    "query": query,
                    "url_ricerca": "https://www.google.com/search?" + urlencode({"q": query}),
                }


def read_candidates(path, known, domains, today, since):
    candidates = {}
    rejected = []
    duplicates = 0
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"titolo", "url", "data", "territorio", "cup", "lotto"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("Il CSV richiede le colonne titolo,url,data,territorio,cup,lotto")
        for row in reader:
            try:
                if None in row or any(row[key] is None for key in required):
                    raise ValueError("Numero di colonne non valido")
                url = public_url(row["url"])
                raw_date = row["data"].strip()
                published = date.fromisoformat(raw_date) if raw_date else None
                if published and published > today:
                    raise ValueError("Data di pubblicazione futura")
                title = row["titolo"].strip()
                if not title:
                    raise ValueError("Titolo mancante")
            except (ValueError, UnicodeError) as exc:
                rejected.append({"riga": reader.line_num, "errore": str(exc)})
                continue

            host = urlsplit(url).hostname
            official = any(host == item or host.endswith("." + item) for item in domains)
            signals = [(label, points) for label, pattern, points in SIGNALS
                       if re.search(pattern, title, re.IGNORECASE)]
            status = "da_verificare"
            if published and published < since:
                status = "fuori_periodo"
            elif url in known and not (row["cup"].strip() or row["lotto"].strip()):
                status = "fonte_gia_censita"
            elif not signals:
                status = "nessun_indizio_nel_titolo"

            cup, lot = row["cup"].strip().upper(), row["lotto"].strip()
            score = (max((points for _, points in signals), default=0)
                     + (3 if official else 0) + (2 if published and published >= since else 0)
                     + bool(cup) + bool(lot))
            record = {
                "titolo": title, "url": url, "data": raw_date,
                "territorio": row["territorio"].strip(), "cup": cup, "lotto": lot,
                "dominio_censito": official, "stato": status, "priorita": score,
                "indizi": [label for label, _ in signals],
                "opere_fonte_censita": sorted(known.get(url, [])), "riga_csv": reader.line_num,
            }
            # Un CUP può comprendere più lotti. Gli atti distinti restano consultabili.
            key = (url, cup, lot.casefold())
            previous = candidates.get(key)
            if previous:
                duplicates += 1
            if previous is None or (status == "da_verificare", score) > (
                previous["stato"] == "da_verificare", previous["priorita"]
            ):
                candidates[key] = record
    return sorted(candidates.values(), key=lambda item: (
        item["stato"] != "da_verificare", -item["priorita"], item["url"], item["riga_csv"]
    )), rejected, duplicates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--territorio", action="append", required=True, help="Comune, provincia o regione. Ripetibile.")
    parser.add_argument("--dominio", action="append", default=[], help="Dominio di ente aggiuntivo. Ripetibile.")
    parser.add_argument("--dal", type=date.fromisoformat, help="Prima data di interesse, AAAA-MM-GG.")
    manifests = parser.add_mutually_exclusive_group()
    manifests.add_argument("--manifest", type=Path, default=ROOT / "config/fonti_pubbliche.json")
    manifests.add_argument("--senza-manifest", action="store_true")
    parser.add_argument("--risultati", type=Path, help="CSV UTF-8 con segnalazioni da classificare.")
    parser.add_argument("--output", type=Path, help="Report JSON. Se omesso, scrive su stdout.")
    args = parser.parse_args()
    today = date.today()
    since = args.dal or today.replace(day=1, month=1)
    if since > today:
        parser.error("--dal deve essere una data già trascorsa oppure oggi")
    if any(not territory.strip() for territory in args.territorio):
        parser.error("--territorio richiede un valore non vuoto")
    try:
        manifest_path = None if args.senza_manifest else args.manifest
        if manifest_path and not manifest_path.is_file():
            if manifest_path != ROOT / "config/fonti_pubbliche.json":
                raise ValueError(f"Manifest assente: {manifest_path}")
            manifest_path = None
        sources = read_manifest(manifest_path)
        domains = {domain(value.strip()) for value in args.dominio}
        domains.update(domain(host) for source in sources for host in source["allowed_hosts"])
        known = {}
        for source in sources:
            opera = source["opera"]
            for url in [*source["pages"], opera.get("fonte_atto_url")]:
                if url:
                    known.setdefault(public_url(url), set()).add(opera["slug"])
        results, rejected, duplicates = (
            read_candidates(args.risultati, known, domains, today, since)
            if args.risultati else ([], [], 0)
        )
        report = {
            "dal": since.isoformat(),
            "manifest": str(manifest_path) if manifest_path else None,
            "domini_censiti": sorted(domains),
            "url_censiti": len(known),
            "ricerche": list(build_queries(dict.fromkeys(t.strip() for t in args.territorio), domains, since)),
            "riepilogo": {
                status: sum(item["stato"] == status for item in results)
                for status in ("da_verificare", "fonte_gia_censita", "fuori_periodo", "nessun_indizio_nel_titolo")
            } | {"righe_duplicate": duplicates, "righe_scartate": len(rejected)},
            "segnalazioni": results,
            "scarti_csv": rejected,
        }
        output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            if any(args.output.resolve() == path.resolve() for path in (manifest_path, args.risultati) if path):
                raise ValueError("--output coincide con un file di input")
            args.output.write_text(output, encoding="utf-8")
        else:
            print(output, end="")
    except (OSError, ValueError, KeyError, TypeError, csv.Error) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
