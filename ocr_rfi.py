"""Lettura OCR delle griglie RFI scansionate, con conservazione della pagina.

Adattatore derivato dall'estrattore locale Rho–Gallarate. Nessuna geometria
è ricavata dalla posizione delle celle. Richiede pdftoppm e Tesseract (ita).
"""
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

ELENCHI = {  # documento VIA -> comune
    "95255": "Rho", "95273": "Rho", "95286": "Rho", "95274": "Pregnana Milanese", "95287": "Pregnana Milanese",
    "95275": "Vanzago", "95288": "Vanzago", "95276": "Pogliano Milanese", "95277": "Nerviano",
    "95278": "Parabiago", "95279": "Canegrate", "95280": "Legnano", "95281": "Castellanza", "95282": "Busto Arsizio",
}
COLONNE = ["n_piano", "foglio", "mappale", "sub", "qualita", "classe", "cat", "ha", "are", "ca", "consistenza",
           "mq_esproprio_sede", "mq_esproprio_deviazioni", "mq_reliquati", "mq_servitu_elettrodotto",
           "mq_esproprio_riqualificazione"]
SCURO = 160
NUMERICHE = {"n_piano", "foglio", "mappale", "sub", "classe", "ha", "are", "ca", "mq_esproprio_sede",
             "mq_esproprio_deviazioni", "mq_reliquati", "mq_servitu_elettrodotto", "mq_esproprio_riqualificazione"}


def pulisci(col: str, val: str) -> str:
    """Corregge gli errori OCR tipici: bordi di cella letti come ] | l, lo zero letto come o/ol/of."""
    val = val.strip()
    if col in NUMERICHE:
        for tok in val.split():
            cifre = re.sub(r"\D", "", tok)
            if cifre:
                return cifre
        if any(re.fullmatch(r"[oO0QDcC]+[lf|\]]?", re.sub(r"[^\w|\]]", "", t)) for t in val.split()):
            return "0"
        return ""
    if col == "cat":
        m = re.search(r"([A-FTa-ft])\s*[/|]?\s*(\d{1,2})\b", val)
        return f"{m.group(1).upper()}/{m.group(2)}" if m else val
    return re.sub(r"^[\[\]|{}_ ]+|[\[\]|{}_ ]+$", "", val)


def raggruppa(valori, gap=4):
    gruppi, cur = [], []
    for v in valori:
        if cur and v - cur[-1] > gap:
            gruppi.append(sum(cur) // len(cur))
            cur = []
        cur.append(v)
    if cur:
        gruppi.append(sum(cur) // len(cur))
    return gruppi


def tess(img: Image.Image, path: Path, psm: str, tsv: bool = False) -> str:
    img.save(path)
    cmd = ["tesseract", str(path), "-", "-l", "ita", "--psm", psm] + (["tsv"] if tsv else [])
    return subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=True).stdout


def raddrizza(im: Image.Image) -> Image.Image:
    """Corregge l'inclinazione della scansione (fino a ±2°): l'angolo giusto è quello in cui
    le linee orizzontali della tabella diventano più nette (picco della proiezione per righe)."""
    picc = im.resize((im.width // 4, im.height // 4))

    def nitidezza(angolo):
        r = picc.rotate(angolo, fillcolor=255)
        px = r.load()
        return max(sum(1 for x in range(0, r.width, 2) if px[x, y] < SCURO) for y in range(r.height // 3, r.height))

    angoli = [a / 4 for a in range(-8, 9)]
    migliore = max(angoli, key=nitidezza)
    return im.rotate(migliore, fillcolor=255, resample=Image.BICUBIC) if migliore else im


def griglia(im: Image.Image):
    """Linee orizzontali della tabella (header + righe) e verticali (colonne)."""
    W, H = im.size
    px = im.load()
    hs = raggruppa([y for y in range(int(.35 * H), H)
                    if sum(1 for x in range(0, W, 3) if px[x, y] < SCURO) / (W / 3) > .25])
    # righe dati: la sequenza più lunga di linee a passo regolare (35-65 px a 300 dpi)
    migliore, cur = [], [hs[0]] if hs else []
    for y in hs[1:]:
        if 35 <= y - cur[-1] <= 65:
            cur.append(y)
        else:
            cur = [y]
        if len(cur) > len(migliore):
            migliore = list(cur)
    righe = migliore
    if len(righe) < 2:
        return None
    # colonne: linee verticali continue lungo tutta la parte dati (lì HA/A/CA sono separate)
    # tolleranza di 3 px per la leggera inclinazione della scansione
    y0, y1 = righe[0], righe[-1]
    ys = range(y0 + 3, y1 - 3, 2)
    vs = raggruppa([x for x in range(3, W - 3)
                    if sum(1 for y in ys if min(px[x + d, y] for d in (-3, -2, -1, 0, 1, 2, 3)) < SCURO) / len(ys) > .65],
                   gap=8)
    return righe, vs


def leggi_pagina(pdf: Path, pagina: int) -> dict:
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        subprocess.run(["pdftoppm", "-r", "300", "-gray", "-png", "-f", str(pagina), "-l", str(pagina),
                        "-singlefile", str(pdf), str(tmp / "p")], check=True, timeout=90)
        orig = Image.open(tmp / "p.png").convert("L")
        out = {"doc": pdf.stem, "pagina": pagina, "comune": ELENCHI.get(pdf.stem, ""), "righe": []}
        # le scansioni sono ruotate in un verso o nell'altro: vale quello in cui si legge il titolo
        g = None
        for angolo in ((-90, 90) if orig.width < orig.height else (0, 180)):
            im = orig.rotate(angolo, expand=True)
            W, H = im.size
            titolo = tess(im.crop((0, 0, W, int(.24 * H))).resize((W // 2, int(.12 * H))), tmp / "t.png", "6")
            if re.search(r"COMUNE|ORDINE|POTENZIAMENTO|Tratta", titolo, re.I):
                im = raddrizza(im)
                g = griglia(im)
                break
        if not g:
            out["nota"] = "tabella non trovata (copertina o pagina illeggibile)"
            return out
        W, H = im.size
        # il numero d'ordine stampato si legge male: si ricostruisce in sequenza in numera_ditte()
        righe, vs = g
        # ditta catastale: dal titolo alla tabella, a destra dell'etichetta
        ditta = tess(im.crop((int(.12 * W), int(.28 * H), int(.95 * W), max(int(.30 * H) + 10, righe[0] - 420))),
                     tmp / "d.png", "6")
        ditta = re.sub(r"\s+", " ", ditta)
        # via le righe del titolo finite nel ritaglio
        ditta = re.sub(r".*?(Progetto\s+Definitivo|Raccordo\s*Y\W*)\s*", "", ditta, count=1, flags=re.I) \
            if re.search(r"Progetto\s+Definitivo|Raccordo\s*Y", ditta[:200], re.I) else ditta
        ditta = re.sub(r"Ditta\s+catastale\W*", "", ditta, flags=re.I)
        out["ditta"] = re.sub(r"^\W*\w*(?:finitivo|INITVO)\W*", "", ditta, flags=re.I).strip(" |")
        if len(vs) < len(COLONNE) + 1:
            out["nota"] = f"colonne trovate {len(vs) - 1} invece di {len(COLONNE)}: pagina da leggere a mano"
            if len(vs) < 4:
                return out
        px = im.load()
        for ya, yb in zip(righe, righe[1:]):
            # riga vuota: quasi nessun pixel scuro dentro le celle (linee escluse)
            lontano = [x for x in range(vs[0] + 6, vs[-1] - 6, 3) if all(abs(x - v) > 6 for v in vs)]
            inchiostro = sum(1 for y in range(ya + 8, yb - 8, 2) for x in lontano if px[x, y] < SCURO)
            if inchiostro < 60:
                continue
            # le linee di cella si cancellano: un numero allineato a destra non si fonde col bordo
            striscia = im.crop((vs[0], ya + 4, vs[-1], yb - 4))
            for v in vs:
                striscia.paste(255, (max(v - vs[0] - 7, 0), 0, v - vs[0] + 7, striscia.height))
            tsv = tess(striscia, tmp / "r.png", "6", tsv=True)
            celle = [[] for _ in range(len(vs) - 1)]
            for line in tsv.splitlines()[1:]:
                f = line.split("\t")
                if len(f) < 12 or not f[11].strip():
                    continue
                xc = vs[0] + int(f[6]) + int(f[8]) // 2  # centro della parola
                col = next((i for i in range(len(vs) - 1) if vs[i] <= xc < vs[i + 1]), None)
                if col is not None:
                    celle[col].append(f[11].strip("|"))
            testo = " ".join(" ".join(c) for c in celle)
            # righe di servizio: totale, "segue", sottotitoli tipo "Identificazione Catasto Fabbricati"
            if re.search(r"SEGUE", testo, re.I):
                out["segue"] = True
            if re.search(r"TOTALE|SEGUE|Identificazione|Catasto", testo, re.I):
                continue
            if len(celle) < 3 or not re.search(r"\d", " ".join(celle[1] + celle[2])):  # senza foglio/mappale non è una particella
                continue
            riga = {COLONNE[i] if i < len(COLONNE) else f"col{i}": pulisci(COLONNE[i] if i < len(COLONNE) else "",
                                                                            " ".join(c))
                    for i, c in enumerate(celle)}
            riga["da_ricontrollare"] = "sì" if not (riga.get("foglio") and riga.get("mappale")) else ""
            out["righe"].append(riga)
        return out


def intestatari(ditta: str):
    """Spezza la ditta catastale in intestatari: nome, nascita, codice fiscale, diritto/quota."""
    out = []
    for parte in re.split(r";\s*", ditta):
        parte = parte.strip(" .")
        if len(parte) < 4:
            continue
        cf = (re.search(r"\b([A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z])\b", parte)
              or re.search(r"([A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z])", re.sub(r"[\s.]", "", parte))
              or re.search(r"\b(\d{11})\b", re.sub(r"\s", "", parte)))  # persone giuridiche: partita IVA
        quota = re.search(r"\b(Prop(?:r\.?|rieta)?\.?\s*\d+/\d+|Prop\w*\s*\d+/\d+|Usufr\w*\s*\d+/\d+|Nuda\s+\w+\s*\d+/\d+)",
                          parte, re.I)
        nascita = re.search(r"nat[oa]\s+a\s+(.+?)\s+il\s+(\d{1,2}/\d{1,2}/\d{4})", parte, re.I)
        nome = re.split(r"\s+nat[oa]\s+a\s+|\s+con sede in\s+|\s+c\.?f\.?", parte, maxsplit=1, flags=re.I)[0]
        out.append({"intestatario": nome.strip(), "luogo_nascita": nascita.group(1) if nascita else "",
                    "data_nascita": nascita.group(2) if nascita else "", "codice_fiscale": cf.group(1) if cf else "",
                    "quota": quota.group(1) if quota else "", "testo_originale": parte})
    return out

