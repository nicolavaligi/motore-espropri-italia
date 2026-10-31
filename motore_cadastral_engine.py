#!/usr/bin/env python3
"""
================================================================================
MOTORE ESPROPRI & ASSERVIMENTI — SUITE INTEGRATA D.P.R. 327/2001
================================================================================
Proprietà intellettuale: Nicola Valigi (Houdinick)
Ambiente: Antigravity (AGY)

Include:
  - Ingestione Visure & Normalizzazione Ditte Comproprietà
  - Buffer Topologici, Sottrazione Geometrica e Test Interclusione Viaria (Art. 33)
  - Computo Soprassuoli Agricoli e Fabbricati (Impianti, Alberi, Pozzi, Fabbricati)
  - Quadro Estimativo di Legge con Maggiorazioni CD/IAP e Cessione Volontaria
  - Esportazione Deliverable: GeoJSON WebGIS, Excel Peritale e Memorie di Opposizione
================================================================================
"""

from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import geopandas as gpd
import pandas as pd
from shapely.geometry import MultiPolygon, Polygon, shape


# ==============================================================================
# PARAMETRI TECNICI ED ECONOMICI ESTIMATIVI
# ==============================================================================
@dataclass
class ParametriEspropri:
    # Valori di mercato terreni (€/mq)
    valore_venale_agricolo_mq: float = 5.00      # Valore effettivo di mercato fondo libero (Corte Cost. 181/2011)
    valore_agricolo_medio_mq: float = 3.20       # Riferimento VAM per indennità aggiuntiva CD/IAP (art. 40 c. 4)
    valore_venale_edificabile_mq: float = 95.00  # Valore venale area edificabile (art. 37)
    saggio_asservimento: float = 0.35            # Saggio deprezzamento fascia di rispetto/sorvolo (30%-50%)
    durata_anni_cantiere: float = 2.0            # Durata cantiere per indennità temporanea (art. 50: 1/12 annuo)

    # Parametri dimensionali buffer metrici
    buffer_esproprio_m: float = 12.0             # Sede permanente opera (metri da asse)
    buffer_asservimento_m: float = 25.0          # Fascia asservimento/rispetto (metri da asse)
    buffer_cantiere_m: float = 8.0               # Occupazione temporanea esterna
    tolleranza_strada_m: float = 1.00            # Snapping topologico viabilità pubblica esistente

    # Costi parametrici soprassuoli e manufatti (€)
    costo_recinzione_ml: float = 65.00           # Recinzione metallica con muretto cls al metro lineare
    costo_albero_frutto: float = 280.00          # Valore complementare pianta da frutto in piena produzione
    costo_albero_olivo_vite: float = 350.00      # Pianta specializzata di pregio
    costo_impianto_irrigazione_mq: float = 1.80  # Impianto a goccia o aspersione su superficie lorda
    costo_fabbricato_rurale_mq: float = 650.00   # Fabbricato rurale/deposito abbattuto (valore di ricostruzione)


# Alias per retrocompatibilità estimativa
ParametriEconomici = ParametriEspropri


@dataclass
class ParametriEconomiciComune:
    valore_venale_agricolo_mq: float            # Valore di mercato effettivo fondo libero
    valore_agricolo_medio_mq: float             # Riferimento per indennità aggiuntiva IAP/CD
    valore_venale_edificabile_mq: float
    saggio_asservimento: float = 0.35           # Percentuale deprezzamento fascia di rispetto/sorvolo
    durata_anni_cantiere: float = 2.0


# ==============================================================================
# 1. INGESTIONE CATASTALE & NORMALIZZAZIONE CROWDED COMPROPRIETÀ
# ==============================================================================
def normalizza_stringa_catasto(valore: Any) -> str:
    """Elimina zeri non significativi, spazi bianchi e caratteri non alfanumerici."""
    if pd.isna(valore):
        return ""
    val_str = str(valore).strip().upper()
    val_str = re.sub(r"^0+", "", val_str)
    return val_str


normalizza_codice = normalizza_stringa_catasto


def arricchisci_catasto_con_visure(
    gdf_catasto: gpd.GeoDataFrame,
    visure_path: Optional[str] = None,
    col_comune: str = "COMUNE",
    col_foglio: str = "FOGLIO",
    col_mappale: str = "NUMERO"
) -> gpd.GeoDataFrame:
    """Effettua il join relazionale tra i poligoni del catasto e i tabulati ditte Sister/AdE."""
    gdf = gdf_catasto.copy()

    if not visure_path or not Path(visure_path).is_file():
        gdf["INTESTATI_COMPLETI"] = "Ditta da visura non disponibile"
        gdf["NUM_INTESTATI"] = 1
        gdf["QUALIFICA_SOGGETTO"] = "PROPRIETARIO_NON_COLTIVATORE"
        gdf["DESTINAZIONE_URB"] = gdf.get("DESTINAZIONE_URB", "Agricola")
        gdf["ALBERI_PREGIO_QTA"] = 0
        gdf["RECINZIONE_ML"] = 0.0
        gdf["IMPIANTO_IRRIGUO"] = False
        return gdf

    if visure_path.endswith((".xlsx", ".xls")):
        df_visure = pd.read_excel(visure_path)
    else:
        df_visure = pd.read_csv(visure_path, sep=None, engine="python")

    # Creazione chiave univoca di join
    gdf["_key_join"] = (
        gdf[col_comune].apply(normalizza_stringa_catasto) + "_" +
        gdf[col_foglio].apply(normalizza_stringa_catasto) + "_" +
        gdf[col_mappale].apply(normalizza_stringa_catasto)
    )

    df_visure["_key_join"] = (
        df_visure["COMUNE"].apply(normalizza_stringa_catasto) + "_" +
        df_visure["FOGLIO"].apply(normalizza_stringa_catasto) + "_" +
        df_visure["MAPPALE"].apply(normalizza_stringa_catasto)
    )

    # Aggregazione comproprietari
    def _aggrega_ditta(sub_df):
        ditte = []
        for _, r in sub_df.iterrows():
            q = f" ({r.get('QUOTA', '1/1')})" if pd.notna(r.get("QUOTA")) else ""
            cf = f" [CF: {r.get('CODICE_FISCALE', '')}]" if pd.notna(r.get("CODICE_FISCALE")) else ""
            ditte.append(f"{r.get('INTESTATO', 'N.D.')}{q}{cf}")

        primo = sub_df.iloc[0].to_dict()
        prima_serie = pd.Series(primo)
        prima_serie["INTESTATI_COMPLETI"] = " | ".join(ditte)
        prima_serie["NUM_INTESTATI"] = len(ditte)
        return prima_serie

    df_agg = df_visure.groupby("_key_join", group_keys=False).apply(_aggrega_ditta)

    campi_join = [
        "_key_join", "INTESTATI_COMPLETI", "NUM_INTESTATI", "QUALITA",
        "CLASSE", "QUALIFICA_SOGGETTO", "DESTINAZIONE_URB",
        "ALBERI_PREGIO_QTA", "RECINZIONE_ML", "IMPIANTO_IRRIGUO"
    ]
    campi_presenti = [c for c in campi_join if c in df_agg.columns]

    gdf_out = gdf.merge(df_agg[campi_presenti], on="_key_join", how="left")
    gdf_out["INTESTATI_COMPLETI"] = gdf_out["INTESTATI_COMPLETI"].fillna("Dati non censiti")
    gdf_out["QUALIFICA_SOGGETTO"] = gdf_out["QUALIFICA_SOGGETTO"].fillna("PROPRIETARIO_NON_COLTIVATORE")
    gdf_out["DESTINAZIONE_URB"] = gdf_out["DESTINAZIONE_URB"].fillna("Agricola")
    gdf_out["ALBERI_PREGIO_QTA"] = gdf_out.get("ALBERI_PREGIO_QTA", 0).fillna(0).astype(int)
    gdf_out["RECINZIONE_ML"] = gdf_out.get("RECINZIONE_ML", 0.0).fillna(0.0).astype(float)
    gdf_out["IMPIANTO_IRRIGUO"] = gdf_out.get("IMPIANTO_IRRIGUO", False).fillna(False).astype(bool)
    gdf_out.drop(columns=["_key_join"], inplace=True)

    return gdf_out


carica_e_associa_censuario = arricchisci_catasto_con_visure


# ==============================================================================
# 2. ANALISI TOPOLOGICA: FASCE D'INGOMBRO, RESIDUI & INTERCLUSIONE STRADALE (ART. 33)
# ==============================================================================
def elabora_interferenze_spaziali(
    gdf_catasto: gpd.GeoDataFrame,
    gdf_tracciato: gpd.GeoDataFrame,
    gdf_strade: Optional[gpd.GeoDataFrame] = None,
    gdf_fabbricati: Optional[gpd.GeoDataFrame] = None,
    params: Optional[ParametriEspropri] = None,
    target_crs: str = "EPSG:32632"
) -> gpd.GeoDataFrame:
    """Interseca le fasce di progetto con il particellare e analizza l'accessibilità viaria."""
    if params is None:
        params = ParametriEspropri()

    catasto_m = gdf_catasto.to_crs(target_crs)
    tracciato_m = gdf_tracciato.to_crs(target_crs)

    strade_geom = None
    if gdf_strade is not None and not gdf_strade.empty:
        try:
            strade_union = gdf_strade.to_crs(target_crs).union_all()
        except AttributeError:
            strade_union = gdf_strade.to_crs(target_crs).unary_union
        strade_geom = strade_union.buffer(params.tolleranza_strada_m)

    fabbricati_m = None
    if gdf_fabbricati is not None and not gdf_fabbricati.empty:
        fabbricati_m = gdf_fabbricati.to_crs(target_crs)

    # Geometrie fasce di progetto
    try:
        asse_union = tracciato_m.union_all()
    except AttributeError:
        asse_union = tracciato_m.unary_union

    geom_esp = asse_union.buffer(params.buffer_esproprio_m)
    geom_ass_tot = asse_union.buffer(params.buffer_asservimento_m)
    geom_ass = geom_ass_tot.difference(geom_esp)
    geom_cant_tot = asse_union.buffer(params.buffer_asservimento_m + params.buffer_cantiere_m)
    geom_cant = geom_cant_tot.difference(geom_ass_tot)

    risultati = []

    for _, row in catasto_m.iterrows():
        geom_part = row.geometry
        if not geom_part.intersects(geom_cant_tot):
            continue

        sup_tot = float(geom_part.area)
        int_esp = geom_part.intersection(geom_esp)
        int_ass = geom_part.intersection(geom_ass)
        int_cant = geom_part.intersection(geom_cant)

        area_esp = float(int_esp.area) if not int_esp.is_empty else 0.0
        area_ass = float(int_ass.area) if not int_ass.is_empty else 0.0
        area_cant = float(int_cant.area) if not int_cant.is_empty else 0.0
        area_res = max(0.0, sup_tot - area_esp)

        if (area_esp + area_ass + area_cant) == 0:
            continue

        pct_esp = (area_esp / sup_tot) * 100.0 if sup_tot > 0 else 0.0

        # Riconoscimento relitto critico dimensionale
        relitto_critico = (0 < area_res < 450.0) or (0 < area_res and pct_esp > 75.0)

        # Analisi interclusione e spezzoni
        is_intercluso = False
        num_spezzoni = 1

        if area_esp > 0:
            residuo_geom = geom_part.difference(geom_esp)
            frammenti: List[Polygon] = []
            if isinstance(residuo_geom, Polygon):
                if not residuo_geom.is_empty and residuo_geom.area > 1.0:
                    frammenti.append(residuo_geom)
            elif isinstance(residuo_geom, MultiPolygon):
                frammenti = [p for p in residuo_geom.geoms if not p.is_empty and p.area > 1.0]

            num_spezzoni = len(frammenti)
            if strade_geom is not None and frammenti:
                for f in frammenti:
                    if not f.intersects(strade_geom):
                        is_intercluso = True
                        break

        # Verifica collisione fabbricati censiti
        sup_fabbricati_abbattuti = 0.0
        if fabbricati_m is not None:
            fabb_intersecati = fabbricati_m[fabbricati_m.intersects(int_esp)]
            if not fabb_intersecati.empty:
                sup_fabbricati_abbattuti = float(fabb_intersecati.intersection(int_esp).area.sum())

        dati = row.to_dict()
        dati.update({
            "sup_totale_mq": round(sup_tot, 1),
            "sup_esproprio_mq": round(area_esp, 1),
            "pct_esproprio": round(pct_esp, 1),
            "sup_asservimento_mq": round(area_ass, 1),
            "sup_cantiere_mq": round(area_cant, 1),
            "sup_residua_mq": round(area_res, 1),
            "relitto_critico": relitto_critico,
            "relitto_intercluso_art33": is_intercluso,
            "num_spezzoni_residui": num_spezzoni,
            "sup_fabbricati_abbattuti_mq": round(sup_fabbricati_abbattuti, 1),
            "has_progetto": True
        })
        risultati.append(dati)

    if not risultati:
        return gpd.GeoDataFrame(columns=catasto_m.columns, crs=target_crs)

    return gpd.GeoDataFrame(risultati, crs=target_crs)


analizza_interferenze_e_interclusione = elabora_interferenze_spaziali
analizza_accessibilita_e_interclusione = elabora_interferenze_spaziali


# ==============================================================================
# 3. COMPUTO ESTIMATIVO DETTAGLIATO: FONDI, SOPRASSUOLI & MAGGIORAZIONI
# ==============================================================================
def calcola_stime_espropriative(
    gdf_interferenze: gpd.GeoDataFrame,
    params: Optional[ParametriEspropri] = None,
    cessione_volontaria: bool = True
) -> pd.DataFrame:
    """Quantifica analiticamente tutte le spettanze indennitarie e formula le memorie difensive."""
    if params is None:
        params = ParametriEspropri()

    dossier = []

    for _, r in gdf_interferenze.iterrows():
        dest = str(r.get("DESTINAZIONE_URB", r.get("destinazione", "Agricola"))).strip().capitalize()
        qual = str(r.get("QUALIFICA_SOGGETTO", "PROPRIETARIO_NON_COLTIVATORE")).strip().upper()

        sup_esp = float(r.get("sup_esproprio_mq", 0.0))
        sup_ass = float(r.get("sup_asservimento_mq", 0.0))
        sup_cant = float(r.get("sup_cantiere_mq", 0.0))
        sup_res = float(r.get("sup_residua_mq", 0.0))
        is_intercluso = bool(r.get("relitto_intercluso_art33", False))
        is_relitto = bool(r.get("relitto_critico", False))

        # 1. Indennità Base Esproprio
        if dest == "Edificabile":
            v_unit = params.valore_venale_edificabile_mq
            ind_base = sup_esp * v_unit
            if cessione_volontaria:
                ind_base *= 1.10  # Maggiorazione 10% art. 45 c. 2 lett. a
        else:
            v_unit = params.valore_venale_agricolo_mq
            ind_base = sup_esp * v_unit

        # 2. Maggiorazione Coltivatore Diretto / IAP
        ind_cd_iap = 0.0
        if any(k in qual for k in ["IAP", "COLTIVATORE"]):
            if cessione_volontaria and dest != "Edificabile":
                # Triplo del valore agricolo effettivo ex art. 45 c. 2 lett. d
                ind_cd_iap = (sup_esp * v_unit) * 2.0
            else:
                # Indennità aggiuntiva ordinaria pari al VAM ex art. 40 c. 4
                ind_cd_iap = sup_esp * params.valore_agricolo_medio_mq
        elif "FITTA" in qual:
            ind_cd_iap = sup_esp * params.valore_agricolo_medio_mq

        # 3. Asservimento (deprezzamento fascia servitù/rispetto)
        ind_ass = sup_ass * (v_unit * params.saggio_asservimento)

        # 4. Occupazione Temporanea Cantiere (Art. 50: 1/12 annuo)
        ind_cant = (sup_cant * v_unit) * (1.0 / 12.0) * params.durata_anni_cantiere

        # 5. Soprassuoli, Manufatti e Fabbricati Rurali
        qta_alberi = int(r.get("ALBERI_PREGIO_QTA", 0))
        ml_recinto = float(r.get("RECINZIONE_ML", 0.0))
        has_irriguo = bool(r.get("IMPIANTO_IRRIGUO", False))
        sup_fabb = float(r.get("sup_fabbricati_abbattuti_mq", 0.0))

        ind_soprassuoli = (
            (qta_alberi * params.costo_albero_olivo_vite) +
            (ml_recinto * params.costo_recinzione_ml) +
            ((sup_esp * params.costo_impianto_irrigazione_mq) if has_irriguo else 0.0) +
            (sup_fabb * params.costo_fabbricato_rurale_mq)
        )

        # 6. Danno Relitto / Interclusione (Art. 33)
        ind_relitto = 0.0
        if is_intercluso:
            ind_relitto = sup_res * v_unit
            motivo_azione = "Interclusione assoluta della porzione residua priva di viabilità (art. 33 c. 2)."
            azione = "Istanza di esproprio totale con liquidazione integrale del relitto."
        elif is_relitto:
            ind_relitto = sup_res * (v_unit * 0.50)
            motivo_azione = "Relitto di consistenza antieconomica inferiore al minimo colturale o con taglio > 75%."
            azione = "Richiesta deprezzamento del 50% su area residua o accorpamento all'esproprio."
        else:
            motivo_azione = "Opera regolare senza relitti critici individuati."
            azione = "Accettazione con riserva o cessione volontaria con indennità concordata."

        totale = ind_base + ind_cd_iap + ind_ass + ind_cant + ind_soprassuoli + ind_relitto

        dossier.append({
            "COMUNE": r.get("COMUNE", r.get("comune", "N.D.")),
            "FOGLIO": str(r.get("FOGLIO", r.get("foglio", ""))),
            "MAPPALE": str(r.get("NUMERO", r.get("MAPPALE", r.get("mappale", "")))),
            "INTESTATI": r.get("INTESTATI_COMPLETI", r.get("intestatario", "N.D.")),
            "QUALIFICA": qual,
            "DESTINAZIONE": dest,
            "SUP_TOT_MQ": r.get("sup_totale_mq", 0.0),
            "SUP_ESP_MQ": sup_esp,
            "PCT_ESP": r.get("pct_esproprio", 0.0),
            "SUP_ASS_MQ": sup_ass,
            "SUP_CANT_MQ": sup_cant,
            "SUP_RES_MQ": sup_res,
            "INTERCLUSO_ART33": is_intercluso,
            "RELITTO_CRITICO": is_relitto,
            "IND_ESPROPRIO_BASE": round(ind_base, 2),
            "IND_AGGIUNTIVA_CD_IAP": round(ind_cd_iap, 2),
            "IND_ASSERVIMENTO": round(ind_ass, 2),
            "IND_CANTIERE_ART50": round(ind_cant, 2),
            "IND_SOPRASSUOLI_MANUFATTI": round(ind_soprassuoli, 2),
            "DANNO_RELITTO_ART33": round(ind_relitto, 2),
            "TOTALE_INDENNITA_STIMATA": round(totale, 2),
            "MOTIVAZIONE_TECNICA": motivo_azione,
            "AZIONE_CONSIGLIATA": azione
        })

    return pd.DataFrame(dossier)


calcola_indennita_dpr327 = calcola_stime_espropriative


def calcola_quadro_indennitario_analitico(
    row: Dict[str, Any],
    parametri: Any,
    opzione_cessione_volontaria: bool = True
) -> Dict[str, Any]:
    """Helper di calcolo estimativo per singola riga di dizionario."""
    destinazione = str(row.get("destinazione", row.get("DESTINAZIONE_URB", "Agricola"))).strip().capitalize()
    qualifica = str(row.get("QUALIFICA_SOGGETTO", "PROPRIETARIO_NON_COLTIVATORE")).strip().upper()

    sup_esp = float(row.get("sup_esproprio_mq", 0.0))
    sup_ass = float(row.get("sup_asservimento_mq", 0.0))
    sup_cant = float(row.get("sup_cantiere_mq", 0.0))
    sup_res = float(row.get("sup_residua_mq", 0.0))
    is_intercluso = bool(row.get("relitto_intercluso_art33", False))

    indennita_base_esproprio = 0.0
    indennita_aggiuntiva_iap_cd = 0.0

    if destinazione == "Edificabile":
        valore_unitario = getattr(parametri, "valore_venale_edificabile_mq", 95.0)
        indennita_base_esproprio = sup_esp * valore_unitario
        if opzione_cessione_volontaria:
            indennita_base_esproprio *= 1.10
    else:
        valore_unitario = getattr(parametri, "valore_venale_agricolo_mq", 5.0)
        indennita_base_esproprio = sup_esp * valore_unitario
        vam = getattr(parametri, "valore_agricolo_medio_mq", 3.20)
        if "IAP" in qualifica or "COLTIVATORE" in qualifica:
            if opzione_cessione_volontaria:
                indennita_aggiuntiva_iap_cd = (sup_esp * valore_unitario) * 2.0
            else:
                indennita_aggiuntiva_iap_cd = sup_esp * vam
        elif "FITTA" in qualifica:
            indennita_aggiuntiva_iap_cd = sup_esp * vam

    saggio = getattr(parametri, "saggio_asservimento", 0.35)
    indennita_asservimento = sup_ass * (valore_unitario * saggio)

    durata = getattr(parametri, "durata_anni_cantiere", 2.0)
    indennita_cantiere = (sup_cant * valore_unitario) * (1.0 / 12.0) * durata

    indennita_deprezzamento_relitto = 0.0
    if is_intercluso:
        indennita_deprezzamento_relitto = sup_res * valore_unitario
    elif row.get("relitto_critico", False):
        indennita_deprezzamento_relitto = sup_res * (valore_unitario * 0.50)

    totale_complessivo = (
        indennita_base_esproprio +
        indennita_aggiuntiva_iap_cd +
        indennita_asservimento +
        indennita_cantiere +
        indennita_deprezzamento_relitto
    )

    return {
        "comune": row.get("comune", row.get("COMUNE", "N.D.")),
        "foglio": row.get("foglio", row.get("FOGLIO", "")),
        "mappale": row.get("mappale", row.get("NUMERO", row.get("MAPPALE", ""))),
        "intestati": row.get("INTESTATI_COMPLETI", row.get("intestatario", "N.D.")),
        "qualifica": qualifica,
        "destinazione": destinazione,
        "superfici": {
            "totale_mq": sup_esp + sup_res,
            "esproprio_mq": sup_esp,
            "asservimento_mq": sup_ass,
            "cantiere_mq": sup_cant,
            "residuo_mq": sup_res
        },
        "criticita": {
            "interclusione": is_intercluso,
            "relitto_critico": row.get("relitto_critico", False),
            "azione_consigliata": "Opposizione per relitto" if row.get("relitto_critico") else "Liquidazione standard"
        },
        "indennita": {
            "esproprio_base_eur": round(indennita_base_esproprio, 2),
            "aggiuntiva_cd_iap_eur": round(indennita_aggiuntiva_iap_cd, 2),
            "asservimento_eur": round(indennita_asservimento, 2),
            "cantiere_art50_eur": round(indennita_cantiere, 2),
            "danno_relitto_art33_eur": round(indennita_deprezzamento_relitto, 2),
            "totale_liquidabile_eur": round(totale_complessivo, 2)
        }
    }


def elabora_piano_particellare_espropri(
    tracciato_path: str,
    catasto_path: str,
    fabbricati_path: Optional[str] = None,
    buffer_esproprio_m: float = 12.0,
    buffer_asservimento_m: float = 25.0,
    buffer_cantiere_m: float = 8.0,
    valore_agricolo_medio_mq: float = 4.50,
    valore_edificabile_mq: float = 85.00,
    target_crs: str = "EPSG:32632"
) -> gpd.GeoDataFrame:
    """Wrapper di alto livello per elaborazione del piano particellare con fabbricati."""
    params = ParametriEspropri(
        buffer_esproprio_m=buffer_esproprio_m,
        buffer_asservimento_m=buffer_asservimento_m,
        buffer_cantiere_m=buffer_cantiere_m,
        valore_agricolo_medio_mq=valore_agricolo_medio_mq,
        valore_venale_edificabile_mq=valore_edificabile_mq
    )
    gdf_tracciato = gpd.read_file(tracciato_path)
    gdf_catasto = gpd.read_file(catasto_path)
    gdf_fabb = gpd.read_file(fabbricati_path) if fabbricati_path and Path(fabbricati_path).is_file() else None

    gdf_interf = elabora_interferenze_spaziali(
        gdf_catasto, gdf_tracciato, gdf_fabbricati=gdf_fabb, params=params, target_crs=target_crs
    )
    return gdf_interf.to_crs(epsg=4326)


# ==============================================================================
# 4. GENERAZIONE MEMORIE TECNICHE E PERIZIE MONOGRAFICHE (MARKDOWN / HTML)
# ==============================================================================
def genera_memorie_tecniche(df_stime: pd.DataFrame, out_dir: Path):
    """Compila le relazioni peritali e le osservazioni al piano particellare per ogni ditta."""
    memorie_dir = out_dir / "memorie_osservazione"
    memorie_dir.mkdir(parents=True, exist_ok=True)

    for _, r in df_stime.iterrows():
        mappale_clean = re.sub(r'[^A-Za-z0-9_]', '_', f"{r['COMUNE']}_F{r['FOGLIO']}_M{r['MAPPALE']}")
        filepath = memorie_dir / f"Osservazione_{mappale_clean}.md"

        contenuto = f"""# MEMORIA TECNICO-ESTIMATIVA E OSSERVAZIONI AL PIANO PARTICELLARE
**Ai sensi e per gli effetti degli artt. 16, 21 e 33 del D.P.R. 8 giugno 2001, n. 327**

---

### 1. DATI IDENTIFICATIVI DEL COMPENDIO
- **Comune Censuario:** {r['COMUNE']}
- **Foglio:** {r['FOGLIO']} | **Mappale:** {r['MAPPALE']}
- **Ditta Intestata:** {r['INTESTATI']}
- **Qualifica Soggettiva:** {r['QUALIFICA']}
- **Destinazione Urbanistica Vigente:** {r['DESTINAZIONE']}

---

### 2. CONSISTENZA DELLE SUPERFICI INTERFERITE
- **Superficie Catastale Totale:** {r['SUP_TOT_MQ']:,.1f} mq
- **Superficie in Esproprio Permanente (Sede Opera):** {r['SUP_ESP_MQ']:,.1f} mq ({r['PCT_ESP']}%)
- **Superficie in Asservimento / Rispetto:** {r['SUP_ASS_MQ']:,.1f} mq
- **Superficie in Occupazione Temporanea (Cantiere):** {r['SUP_CANT_MQ']:,.1f} mq
- **Superficie Residua Libera:** {r['SUP_RES_MQ']:,.1f} mq

---

### 3. CRITICITÀ TOPOLOGICHE E FONDIARE (ART. 33 D.P.R. 327/2001)
- **Stato Interclusione Stradale:** {'ATTENZIONE: PARTICELLA INTERCLUSA (Priva di sbocco su viabilità pubblica)' if r['INTERCLUSO_ART33'] else 'Accesso stradale verificato'}
- **Frazionamento Antieconomico (Relitto):** {'SÌ (Area residua inferiore a 450 mq o > 75% espropriato)' if r['RELITTO_CRITICO'] else 'No'}
- **Diagnosi Peritale:** {r['MOTIVAZIONE_TECNICA']}
- **Richiesta Formale:** {r['AZIONE_CONSIGLIATA']}

---

### 4. QUADRO ESTIMATIVO DELLE SPETTANZE INDENNITARIE
| Voce di Computo | Riferimento di Legge | Indennizzo Stimato (€) |
| :--- | :--- | :--- |
| **Indennità Espropriativa Base** | Artt. 37 / 40 D.P.R. 327/2001 | € {r['IND_ESPROPRIO_BASE']:,.2f} |
| **Maggiorazione Spettante CD / IAP** | Artt. 40 c. 4 / 45 c. 2 lett. d | € {r['IND_AGGIUNTIVA_CD_IAP']:,.2f} |
| **Indennità di Asservimento (Rispetto/Sorvolo)** | Deprezzamento fascia servitù | € {r['IND_ASSERVIMENTO']:,.2f} |
| **Occupazione Temporanea di Cantiere** | Art. 50 (1/12 annuo per durata lavori) | € {r['IND_CANTIERE_ART50']:,.2f} |
| **Soprassuoli, Manufatti e Fabbricati** | Ricostruzione e valore complementare | € {r['IND_SOPRASSUOLI_MANUFATTI']:,.2f} |
| **Deprezzamento o Riacquisto Relitto** | Art. 33 D.P.R. 327/2001 | € {r['DANNO_RELITTO_ART33']:,.2f} |
| **TOTALE INDENNITÀ PROVVISORIA DETERMINATA** | | **€ {r['TOTALE_INDENNITA_STIMATA']:,.2f}** |

---

### 5. CONCLUSIONI E FORMALIZZAZIONE RISERVE
Si formula formale opposizione all'indennità provvisoria qualora non comprensiva dei soprassuoli accertati e del ristoro del relitto immobiliare residuo ai sensi dell'art. 33 del Testo Unico Espropri. Si richiede l'attivazione della commissione arbitrale peritale ex art. 21 D.P.R. 327/2001 in caso di disaccordo con l'Ente Espropriante.

*Data perizia: 31 Ottobre 2026*  
*Il Tecnico Incaricato: Nicola Valigi (Houdinick)*
"""
        filepath.write_text(contenuto, encoding="utf-8")


# ==============================================================================
# 5. PIPELINE GENERALE DI ESECUZIONE
# ==============================================================================
def esegui_motore_integrato(
    tracciato_path: str,
    catasto_path: str,
    strade_path: Optional[str] = None,
    fabbricati_path: Optional[str] = None,
    visure_path: Optional[str] = None,
    outdir: str = "espropri_deliverables",
    crs: str = "EPSG:32632"
):
    """Esegue la pipeline end-to-end e produce tutti i deliverable."""
    params = ParametriEspropri()
    out_dir_path = Path(outdir)
    out_dir_path.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print(" AVVIO MOTORE ESPROPRI & ASSERVIMENTI (D.P.R. 327/2001)")
    print("=" * 80)

    # 1. Caricamento e join visure
    print("[1/5] Caricamento catasto e join con visure ditte intestate...")
    gdf_catasto_raw = gpd.read_file(catasto_path)
    gdf_censuario = arricchisci_catasto_con_visure(gdf_catasto_raw, visure_path)

    # 2. Vettoriali di contesto
    gdf_tracciato = gpd.read_file(tracciato_path)
    gdf_strade = gpd.read_file(strade_path) if strade_path and Path(strade_path).is_file() else None
    gdf_fabbricati = gpd.read_file(fabbricati_path) if fabbricati_path and Path(fabbricati_path).is_file() else None

    # 3. Analisi topologica
    print(f"[2/5] Elaborazione buffer geometrici, frazionamenti e test interclusione viaria ({crs})...")
    gdf_interferenze = elabora_interferenze_spaziali(
        gdf_censuario, gdf_tracciato, gdf_strade, gdf_fabbricati, params, target_crs=crs
    )

    if gdf_interferenze.empty:
        print("[!] Nessuna particella interferita dal tracciato con i buffer definiti.")
        return

    # 4. Computo Estimativo
    print("[3/5] Calcolo analitico indennità base, soprassuoli, danni da relitto e maggiorazioni CD/IAP...")
    df_stime = calcola_stime_espropriative(gdf_interferenze, params, cessione_volontaria=True)

    # 5. Generazione Deliverable
    print("[4/5] Esportazione layer GeoJSON per WebGIS e Quadro Economico Excel multi-scheda...")
    gdf_webgis = gdf_interferenze.merge(
        df_stime[[
            "COMUNE", "FOGLIO", "MAPPALE", "IND_ESPROPRIO_BASE", "IND_AGGIUNTIVA_CD_IAP",
            "IND_ASSERVIMENTO", "IND_CANTIERE_ART50", "IND_SOPRASSUOLI_MANUFATTI",
            "DANNO_RELITTO_ART33", "TOTALE_INDENNITA_STIMATA", "MOTIVAZIONE_TECNICA", "AZIONE_CONSIGLIATA"
        ]],
        left_on=["COMUNE", "FOGLIO", "NUMERO"],
        right_on=["COMUNE", "FOGLIO", "MAPPALE"],
        how="left"
    )

    geojson_path = out_dir_path / "piano_particellare_espropri.geojson"
    gdf_webgis.to_crs(epsg=4326).to_file(geojson_path, driver="GeoJSON")

    excel_path = out_dir_path / "quadro_economico_espropri.xlsx"
    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        df_stime.to_excel(writer, sheet_name="Piano Particellare", index=False)

        # Riepilogo aggregato ditte
        df_ditte = df_stime.groupby("INTESTATI", as_index=False).agg({
            "SUP_ESP_MQ": "sum",
            "SUP_ASS_MQ": "sum",
            "SUP_CANT_MQ": "sum",
            "IND_ESPROPRIO_BASE": "sum",
            "IND_AGGIUNTIVA_CD_IAP": "sum",
            "IND_SOPRASSUOLI_MANUFATTI": "sum",
            "DANNO_RELITTO_ART33": "sum",
            "TOTALE_INDENNITA_STIMATA": "sum"
        }).rename(columns={"TOTALE_INDENNITA_STIMATA": "TOTALE_LIQUIDAZIONE_DITTA"})
        df_ditte.to_excel(writer, sheet_name="Riepilogo per Ditta", index=False)

    print("[5/5] Compilazione automatica delle memorie di opposizione e schede tecniche...")
    genera_memorie_tecniche(df_stime, out_dir_path)

    print("\n" + "=" * 80)
    print(" ELABORAZIONE COMPLETATA")
    print(f"  - Mappali interferiti: {len(df_stime)}")
    print(f"  - Particelle intercluse (art. 33 c. 2): {int(df_stime['INTERCLUSO_ART33'].sum())}")
    print(f"  - Relitti antieconomici: {int(df_stime['RELITTO_CRITICO'].sum())}")
    print(f"  - Totale Monte Indennità Determinato: € {df_stime['TOTALE_INDENNITA_STIMATA'].sum():,.2f}")
    print(f"  - File WebGIS: {geojson_path}")
    print(f"  - File Tabellare: {excel_path}")
    print(f"  - Memorie generate in: {out_dir_path / 'memorie_osservazione'}")
    print("=" * 80)


esegui_pipeline = esegui_motore_integrato


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Motore Integrato Espropri D.P.R. 327/2001")
    parser.add_argument("--tracciato", required=True, help="Path vettoriale tracciato/asse opera")
    parser.add_argument("--catasto", required=True, help="Path vettoriale particelle catastali")
    parser.add_argument("--strade", default=None, help="Path vettoriale rete stradale pubblica (per check interclusione)")
    parser.add_argument("--fabbricati", default=None, help="Path vettoriale sagome fabbricati censiti")
    parser.add_argument("--visure", default=None, help="Path Excel/CSV visure censuarie ditte")
    parser.add_argument("--outdir", default="espropri_deliverables", help="Cartella output per i deliverable")
    parser.add_argument("--crs", default="EPSG:32632", help="Sistema di riferimento proiettato metrico locale")

    args = parser.parse_args()
    esegui_motore_integrato(
        tracciato_path=args.tracciato,
        catasto_path=args.catasto,
        strade_path=args.strade,
        fabbricati_path=args.fabbricati,
        visure_path=args.visure,
        outdir=args.outdir,
        crs=args.crs
    )
