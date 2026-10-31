#!/usr/bin/env python3
"""
MOTORE ESPROPRI & ASSERVIMENTI — D.P.R. 327/2001
Modulo Integrato di Intelligence Territoriale & Quadro Estimativo Analitico

Proprietà intellettuale: Nicola Valigi (Houdinick)
Ambiente: Antigravity (AGY)

Funzionalità:
  1. Ingestione Visure & Join Censuario Ditte (Normalizzazione chiavi e aggregazione comproprietà)
  2. Analisi Topologica di Interclusione e Accessibilità Stradale dei Relitti (Art. 33)
  3. Calcolo Estimativo Completo con Maggiorazioni Coltivatore Diretto / IAP (Artt. 37, 40, 45, 50)
  4. Intersezione Topologica e Calcolo Quote di Occupazione (Esproprio, Asservimento, Cantiere)
  5. Esportazione GeoJSON per WebGIS e Tabellare Excel per Relazione Tecnica
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import geopandas as gpd
from shapely.geometry import MultiPolygon, Polygon, shape


# ==============================================================================
# PARAMETRI ECONOMICI ED ESTIMATIVI COMUNALI
# ==============================================================================
@dataclass
class ParametriEconomici:
    valore_venale_agricolo_mq: float = 5.00     # Mercato effettivo fondo libero (art. 40 - Sent. 181/2011)
    valore_agricolo_medio_mq: float = 3.20      # VAM di riferimento per indennità aggiuntiva IAP/CD
    valore_venale_edificabile_mq: float = 90.00 # Valore venale area fabbricabile (art. 37)
    saggio_asservimento: float = 0.35           # Deprezzamento fascia di rispetto/servitù (30%-50%)
    durata_anni_cantiere: float = 2.0           # Durata prevista cantiere (art. 50: 1/12 annuo)
    buffer_esproprio_m: float = 12.0            # Sede permanente opera (metri da asse)
    buffer_asservimento_m: float = 25.0         # Fascia rispetto/asservimento (metri da asse)
    buffer_cantiere_m: float = 8.0              # Fascia occupazione temporanea aggiuntiva
    tolleranza_strada_m: float = 0.50           # Snapping geometrico viabilità esistente


@dataclass
class ParametriEconomiciComune:
    valore_venale_agricolo_mq: float            # Valore di mercato effettivo fondo libero
    valore_agricolo_medio_mq: float             # Riferimento per indennità aggiuntiva IAP/CD
    valore_venale_edificabile_mq: float
    saggio_asservimento: float = 0.35           # Percentuale deprezzamento fascia di rispetto/sorvolo
    durata_anni_cantiere: float = 2.0


# ==============================================================================
# 1. NORMALIZZAZIONE & INGESTIONE VISURE CATASTALI
# ==============================================================================
def normalizza_codice(valore: Any) -> str:
    """Rimuove zeri iniziali, spazi e caratteri spuri per match deterministico."""
    if pd.isna(valore):
        return ""
    val_str = str(valore).strip().upper()
    val_str = re.sub(r"^0+", "", val_str)
    return val_str


def carica_e_associa_censuario(
    gdf_particellare: gpd.GeoDataFrame,
    visure_path: Optional[str] = None,
    col_comune_gis: str = "COMUNE",
    col_foglio_gis: str = "FOGLIO",
    col_mappale_gis: str = "NUMERO"
) -> gpd.GeoDataFrame:
    """
    Esegue il join tra il layer cartografico e l'estratto tavolare delle ditte intestate,
    qualità colturale, classe, superficie catastale nominale e redditi dominicali/agrari.
    """
    gdf = gdf_particellare.copy()

    # Se non c'è file visure, predispone attributi standard
    if not visure_path or not Path(visure_path).is_file():
        gdf["INTESTATI_COMPLETI"] = "Dati ditta non censiti / In attesa di visura"
        gdf["NUM_INTESTATI"] = 1
        gdf["QUALIFICA_SOGGETTO"] = "PROPRIETARIO_NON_COLTIVATORE"
        gdf["DESTINAZIONE_URB"] = gdf.get("DESTINAZIONE_URB", "Agricola")
        return gdf

    # 1. Caricamento dati visure (supporta CSV o XLSX)
    if visure_path.endswith((".xlsx", ".xls")):
        df_visure = pd.read_excel(visure_path)
    else:
        df_visure = pd.read_csv(visure_path, sep=None, engine="python")

    # 2. Generazione chiavi normalizzate per il join
    gdf["_key_join"] = (
        gdf[col_comune_gis].apply(normalizza_codice) + "_" +
        gdf[col_foglio_gis].apply(normalizza_codice) + "_" +
        gdf[col_mappale_gis].apply(normalizza_codice)
    )

    df_visure["_key_join"] = (
        df_visure["COMUNE"].apply(normalizza_codice) + "_" +
        df_visure["FOGLIO"].apply(normalizza_codice) + "_" +
        df_visure["MAPPALE"].apply(normalizza_codice)
    )

    # 3. Aggregazione intestati nel caso di comproprietà multiple sullo stesso mappale
    def aggrega_ditte(gruppo):
        ditte_lista = []
        for _, row in gruppo.iterrows():
            quota = f" ({row.get('QUOTA', '1/1')})" if pd.notna(row.get("QUOTA")) else ""
            cf = f" - CF: {row.get('CODICE_FISCALE', '')}" if pd.notna(row.get("CODICE_FISCALE")) else ""
            ditte_lista.append(f"{row.get('INTESTATO', 'N.D.')}{quota}{cf}")

        prima_riga = gruppo.iloc[0].to_dict()
        prima_riga["INTESTATI_COMPLETI"] = " | ".join(ditte_lista)
        prima_riga["NUM_INTESTATI"] = len(ditte_lista)
        return pd.Series(prima_riga)

    df_visure_agg = df_visure.groupby("_key_join", group_keys=False).apply(aggrega_ditte)

    # 4. Join con il layer geografico
    campi_merge = [
        c for c in [
            "_key_join", "INTESTATI_COMPLETI", "NUM_INTESTATI", "QUALITA",
            "CLASSE", "REDDITO_DOMINICALE", "REDDITO_AGRARIO",
            "QUALIFICA_SOGGETTO", "DESTINAZIONE_URB"
        ] if c in df_visure_agg.columns
    ]

    gdf_join = gdf.merge(df_visure_agg[campi_merge], on="_key_join", how="left")
    gdf_join["INTESTATI_COMPLETI"] = gdf_join["INTESTATI_COMPLETI"].fillna("Dati ditta non censiti / In attesa di visura")
    gdf_join["QUALIFICA_SOGGETTO"] = gdf_join["QUALIFICA_SOGGETTO"].fillna("PROPRIETARIO_NON_COLTIVATORE")
    gdf_join["DESTINAZIONE_URB"] = gdf_join.get("DESTINAZIONE_URB", "Agricola").fillna("Agricola")
    gdf_join.drop(columns=["_key_join"], inplace=True)

    return gdf_join


# ==============================================================================
# 2. CALCOLO INTERFERENZE TOPOLOGICHE E ACCESSIBILITÀ STRADALE (ART. 33)
# ==============================================================================
def analizza_interferenze_e_interclusione(
    gdf_particelle: gpd.GeoDataFrame,
    gdf_tracciato: gpd.GeoDataFrame,
    gdf_strade: Optional[gpd.GeoDataFrame] = None,
    params: Optional[ParametriEconomici] = None,
    target_crs: str = "EPSG:32632"
) -> gpd.GeoDataFrame:
    """Esegue buffering metrico, sottrazione spaziale e test di contatto viario."""
    if params is None:
        params = ParametriEconomici()

    catasto_m = gdf_particelle.to_crs(target_crs)
    tracciato_m = gdf_tracciato.to_crs(target_crs)

    # Preparazione rete stradale se fornita
    rete_stradale_geom = None
    if gdf_strade is not None and not gdf_strade.empty:
        rete_stradale_geom = gdf_strade.to_crs(target_crs).unary_union.buffer(params.tolleranza_strada_m)

    # Generazione fasce d'ingombro
    geom_asse = tracciato_m.unary_union
    geom_esp = geom_asse.buffer(params.buffer_esproprio_m)
    geom_ass_tot = geom_asse.buffer(params.buffer_asservimento_m)
    geom_ass = geom_ass_tot.difference(geom_esp)
    geom_cant_tot = geom_asse.buffer(params.buffer_asservimento_m + params.buffer_cantiere_m)
    geom_cant = geom_cant_tot.difference(geom_ass_tot)

    record_elaborati = []

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

        # Rilevamento relitto critico dimensionale (< 450 mq o > 75% espropriato)
        relitto_critico = (0 < area_res < 450.0) or (0 < area_res and pct_esp > 75.0)

        # Analisi topologica dei frammenti residui e verifica sbocco su strada
        is_intercluso = False
        frammenti_info = []

        if area_esp > 0:
            residuo_geom = geom_part.difference(geom_esp)
            lista_spezzoni = []
            if isinstance(residuo_geom, Polygon):
                if not residuo_geom.is_empty and residuo_geom.area > 1.0:
                    lista_spezzoni.append(residuo_geom)
            elif isinstance(residuo_geom, MultiPolygon):
                lista_spezzoni = [p for p in residuo_geom.geoms if not p.is_empty and p.area > 1.0]

            for idx, spezzone in enumerate(lista_spezzoni):
                ha_strada = True
                if rete_stradale_geom is not None:
                    ha_strada = spezzone.intersects(rete_stradale_geom)

                if not ha_strada:
                    is_intercluso = True

                frammenti_info.append({
                    "spezzone_id": idx + 1,
                    "superficie_mq": round(spezzone.area, 1),
                    "accesso_stradale": ha_strada
                })

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
            "num_spezzoni_residui": len(frammenti_info) if frammenti_info else 1,
            "has_progetto": True
        })
        record_elaborati.append(dati)

    if not record_elaborati:
        return gpd.GeoDataFrame(columns=catasto_m.columns, crs=target_crs)

    return gpd.GeoDataFrame(record_elaborati, crs=target_crs)


# Alias per compatibilità con entrambe le nomenclature
analizza_accessibilita_e_interclusione = analizza_interferenze_e_interclusione


# ==============================================================================
# 3. INTERSEZIONE TOPOLOGICA & CALCOLO ESTIMATIVO DI DETTAGLIO
# ==============================================================================
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
    """
    Esegue l'intersezione topologica e il calcolo estimativo di dettaglio 
    per ogni particella interferita dal tracciato di progetto.
    """
    gdf_tracciato = gpd.read_file(tracciato_path).to_crs(target_crs)
    gdf_catasto = gpd.read_file(catasto_path).to_crs(target_crs)

    gdf_fabbricati = None
    if fabbricati_path and Path(fabbricati_path).is_file():
        gdf_fabbricati = gpd.read_file(fabbricati_path).to_crs(target_crs)

    # 1. Calcolo geometrie unificate di ingombro
    geom_tracciato_union = gdf_tracciato.unary_union
    geom_esproprio = geom_tracciato_union.buffer(buffer_esproprio_m)

    # Asservimento al netto della sede dell'opera espropriata
    geom_asservimento_totale = geom_tracciato_union.buffer(buffer_asservimento_m)
    geom_asservimento = geom_asservimento_totale.difference(geom_esproprio)

    # Cantiere / occupazione temporanea esterna
    geom_cantiere_totale = geom_tracciato_union.buffer(buffer_asservimento_m + buffer_cantiere_m)
    geom_cantiere = geom_cantiere_totale.difference(geom_asservimento_totale)

    record_particelle = []

    # 2. Iterazione particellare
    for _, part in gdf_catasto.iterrows():
        geom_part = part.geometry

        # Filtro rapido di intersezione
        if not geom_part.intersects(geom_cantiere_totale):
            continue

        sup_totale = float(geom_part.area)

        # Intersezioni geometriche
        geom_int_esp = geom_part.intersection(geom_esproprio)
        geom_int_ass = geom_part.intersection(geom_asservimento)
        geom_int_cant = geom_part.intersection(geom_cantiere)

        area_esp = float(geom_int_esp.area) if not geom_int_esp.is_empty else 0.0
        area_ass = float(geom_int_ass.area) if not geom_int_ass.is_empty else 0.0
        area_cant = float(geom_int_cant.area) if not geom_int_cant.is_empty else 0.0
        area_res = max(0.0, sup_totale - area_esp)

        if (area_esp + area_ass + area_cant) == 0:
            continue

        pct_esproprio = (area_esp / sup_totale) * 100.0 if sup_totale > 0 else 0.0

        # Rilevamento criticità art. 33 DPR 327/2001 (Relitto non utilizzabile o frammentazione)
        is_relitto = False
        motivo_relitto = "Nessuno"
        if 0 < area_res < 450.0:
            is_relitto = True
            motivo_relitto = "Superficie residua < 450 mq (soglia minima lavorabilità)"
        elif 0 < area_res and (pct_esproprio > 75.0):
            is_relitto = True
            motivo_relitto = "Esproprio > 75% della superficie totale catastale"

        # Verifica impatto su fabbricati o manufatti censiti
        has_fabbricato = False
        num_fabbricati = 0
        if gdf_fabbricati is not None:
            fabbricati_intersecati = gdf_fabbricati[gdf_fabbricati.intersects(geom_part)]
            if not fabbricati_intersecati.empty:
                interferenza_fabb = fabbricati_intersecati.intersects(geom_esproprio | geom_asservimento)
                if interferenza_fabb.any():
                    has_fabbricato = True
                    num_fabbricati = int(interferenza_fabb.sum())

        # Classificazione urbanistica (default agricola se non specificata)
        destinazione = str(part.get("DESTINAZIONE_URB", "Agricola")).strip().capitalize()
        v_unitario = valore_edificabile_mq if destinazione == "Edificabile" else valore_agricolo_medio_mq

        # 3. Conteggio Estimativo Indennitario (D.P.R. 327/2001)
        indennita_esp = area_esp * v_unitario
        saggio_asservimento = 0.35
        indennita_ass = area_ass * (v_unitario * saggio_asservimento)
        indennita_cant = (area_cant * v_unitario) * (1.0 / 12.0) * 2.0
        totale_indennita = indennita_esp + indennita_ass + indennita_cant

        record_particelle.append({
            "comune": part.get("COMUNE", "N.D."),
            "foglio": str(part.get("FOGLIO", "")),
            "mappale": str(part.get("NUMERO", part.get("MAPPALE", ""))),
            "destinazione": destinazione,
            "sup_totale_mq": round(sup_totale, 1),
            "sup_esproprio_mq": round(area_esp, 1),
            "pct_esproprio": round(pct_esproprio, 1),
            "sup_asservimento_mq": round(area_ass, 1),
            "sup_cantiere_mq": round(area_cant, 1),
            "sup_residua_mq": round(area_res, 1),
            "relitto_critico": is_relitto,
            "motivo_relitto": motivo_relitto,
            "has_fabbricato": has_fabbricato,
            "num_fabbricati": num_fabbricati,
            "indennita_esp_eur": round(indennita_esp, 2),
            "indennita_ass_eur": round(indennita_ass, 2),
            "indennita_cant_eur": round(indennita_cant, 2),
            "totale_indennita_eur": round(totale_indennita, 2),
            "has_progetto": True,
            "geometry": geom_part
        })

    gdf_risultato = gpd.GeoDataFrame(record_particelle, crs=target_crs)
    return gdf_risultato.to_crs(epsg=4326)


# ==============================================================================
# 4. MOTORE ESTIMATIVO INDENNITARIO ANALITICO CON MAGGIORAZIONI CD / IAP
# ==============================================================================
def calcola_quadro_indennitario_analitico(
    row: Dict[str, Any],
    parametri: Any,
    opzione_cessione_volontaria: bool = True
) -> Dict[str, Any]:
    """
    Calcola le singole componenti indennitarie nel rispetto degli artt. 33, 37, 40, 45 e 50 D.P.R. 327/2001.
    """
    destinazione = str(row.get("destinazione", row.get("DESTINAZIONE_URB", "Agricola"))).strip().capitalize()
    qualifica = str(row.get("QUALIFICA_SOGGETTO", "PROPRIETARIO_NON_COLTIVATORE")).strip().upper()

    sup_esp = float(row.get("sup_esproprio_mq", 0.0))
    sup_ass = float(row.get("sup_asservimento_mq", 0.0))
    sup_cant = float(row.get("sup_cantiere_mq", 0.0))
    sup_res = float(row.get("sup_residua_mq", 0.0))
    is_intercluso = bool(row.get("relitto_intercluso_art33", False))

    indennita_base_esproprio = 0.0
    indennita_aggiuntiva_iap_cd = 0.0
    indennita_asservimento = 0.0
    indennita_cantiere = 0.0
    indennita_deprezzamento_relitto = 0.0

    # 1. Stima Indennità di Esproprio Principale
    if destinazione == "Edificabile":
        valore_unitario = getattr(parametri, "valore_venale_edificabile_mq", 90.0)
        indennita_base_esproprio = sup_esp * valore_unitario
        if opzione_cessione_volontaria:
            indennita_base_esproprio *= 1.10
    else:
        valore_unitario = getattr(parametri, "valore_venale_agricolo_mq", 5.0)
        indennita_base_esproprio = sup_esp * valore_unitario

        # Maggiorazioni Coltivatore Diretto / IAP (Art. 40 c. 4 e Art. 45 c. 2 lett. d)
        vam = getattr(parametri, "valore_agricolo_medio_mq", 3.20)
        if "IAP" in qualifica or "COLTIVATORE" in qualifica:
            if opzione_cessione_volontaria:
                indennita_aggiuntiva_iap_cd = (sup_esp * valore_unitario) * 2.0
            else:
                indennita_aggiuntiva_iap_cd = sup_esp * vam
        elif "FITTA" in qualifica:
            indennita_aggiuntiva_iap_cd = sup_esp * vam

    # 2. Indennità di Asservimento
    saggio = getattr(parametri, "saggio_asservimento", 0.35)
    indennita_asservimento = sup_ass * (valore_unitario * saggio)

    # 3. Indennità di Cantiere (Art. 50 D.P.R. 327/2001)
    durata = getattr(parametri, "durata_anni_cantiere", 2.0)
    indennita_cantiere = (sup_cant * valore_unitario) * (1.0 / 12.0) * durata

    # 4. Deprezzamento Relitto o Riacquisto per Interclusione (Art. 33)
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
            "azione_consigliata": row.get("azione_consigliata", "Liquidazione standard")
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


def calcola_indennita_dpr327(
    gdf_interferenze: gpd.GeoDataFrame,
    params: Optional[ParametriEconomici] = None,
    cessione_volontaria: bool = True
) -> pd.DataFrame:
    """Calcola le voci indennitarie conformemente agli artt. 33, 37, 40, 45 e 50."""
    if params is None:
        params = ParametriEconomici()

    righe = []
    for _, r in gdf_interferenze.iterrows():
        stima = calcola_quadro_indennitario_analitico(r.to_dict(), params, cessione_volontaria)
        righe.append({
            "COMUNE": stima["comune"],
            "FOGLIO": stima["foglio"],
            "MAPPALE": stima["mappale"],
            "INTESTATI": stima["intestati"],
            "QUALIFICA": stima["qualifica"],
            "DESTINAZIONE": stima["destinazione"],
            "SUP_TOT_MQ": stima["superfici"]["totale_mq"],
            "SUP_ESP_MQ": stima["superfici"]["esproprio_mq"],
            "SUP_ASS_MQ": stima["superfici"]["asservimento_mq"],
            "SUP_CANT_MQ": stima["superfici"]["cantiere_mq"],
            "SUP_RES_MQ": stima["superfici"]["residuo_mq"],
            "INTERCLUSO_ART33": stima["criticita"]["interclusione"],
            "RELITTO_CRITICO": stima["criticita"]["relitto_critico"],
            "IND_ESPROPRIO_BASE_EUR": stima["indennita"]["esproprio_base_eur"],
            "IND_AGGIUNTIVA_CD_IAP_EUR": stima["indennita"]["aggiuntiva_cd_iap_eur"],
            "IND_ASSERVIMENTO_EUR": stima["indennita"]["asservimento_eur"],
            "IND_CANTIERE_ART50_EUR": stima["indennita"]["cantiere_art50_eur"],
            "DANNO_RELITTO_ART33_EUR": stima["indennita"]["danno_relitto_art33_eur"],
            "TOTALE_INDENNITA_EUR": stima["indennita"]["totale_liquidabile_eur"],
            "AZIONE_CONSIGLIATA": stima["criticita"]["azione_consigliata"]
        })
    return pd.DataFrame(righe)


# ==============================================================================
# 5. PIPELINE DI ESECUZIONE & CLI ENTRYPOINT
# ==============================================================================
def esegui_pipeline(
    tracciato_path: str,
    catasto_path: str,
    strade_path: Optional[str] = None,
    visure_path: Optional[str] = None,
    output_dir: str = "output_espropri",
    params: Optional[ParametriEconomici] = None,
    target_crs: str = "EPSG:32632"
):
    """Coordina l'esecuzione sequenziale e produce i deliverable peritali e GIS."""
    if params is None:
        params = ParametriEconomici()

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    print(f"[*] Caricamento vettoriali geografici in sistema metrico {target_crs}...")
    gdf_tracciato = gpd.read_file(tracciato_path)
    gdf_catasto = gpd.read_file(catasto_path)
    gdf_strade = gpd.read_file(strade_path) if strade_path and Path(strade_path).is_file() else None

    # Step 1: Join Ditte Censuarie
    print("[*] Esecuzione join ditte e aggregazione comproprietari da visura...")
    gdf_censuario = carica_e_associa_censuario(gdf_catasto, visure_path)

    # Step 2: Analisi Spaziale e Interclusione
    print("[*] Buffering opera, clip particellare e test topologico accessibilità viaria...")
    gdf_interferenze = analizza_interferenze_e_interclusione(
        gdf_censuario, gdf_tracciato, gdf_strade, params, target_crs=target_crs
    )

    if gdf_interferenze.empty:
        print("[!] Nessuna particella interferita dal tracciato con i buffer impostati.")
        return

    # Step 3: Calcolo Estimativo Analitico D.P.R. 327/2001
    print("[*] Calcolo indennità provvisorie, cessione volontaria e maggiorazioni CD/IAP...")
    df_stime = calcola_indennita_dpr327(gdf_interferenze, params, cessione_volontaria=True)

    # Step 4: Esportazione Deliverable
    geojson_out = out_path / "piano_particellare_espropri.geojson"
    excel_out = out_path / "quadro_economico_perizia_espropri.xlsx"

    print(f"[*] Esportazione layer WebGIS in EPSG:4326: {geojson_out}")
    gdf_interferenze.to_crs(epsg=4326).to_file(geojson_out, driver="GeoJSON")

    print(f"[*] Esportazione perizia tabellare Excel: {excel_out}")
    with pd.ExcelWriter(excel_out, engine="openpyxl") as writer:
        df_stime.to_excel(writer, sheet_name="Piano Particellare", index=False)

        df_riepilogo = df_stime.groupby("INTESTATI", as_index=False).agg({
            "SUP_ESP_MQ": "sum",
            "SUP_ASS_MQ": "sum",
            "SUP_CANT_MQ": "sum",
            "TOTALE_INDENNITA_EUR": "sum"
        }).rename(columns={"TOTALE_INDENNITA_EUR": "TOTALE_LIQUIDABILE_EUR"})
        df_riepilogo.to_excel(writer, sheet_name="Riepilogo Liquidazione Ditte", index=False)

    print("\n[+] Elaborazione completata con successo.")
    print(f"    - Particelle impattate: {len(df_stime)}")
    print(f"    - Totale Indennità Provvisorie Stimate: € {df_stime['TOTALE_INDENNITA_EUR'].sum():,.2f}")
    print(f"    - Relitti con allarme interclusione: {int(df_stime['INTERCLUSO_ART33'].sum())}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Motore Espropri & Asservimenti D.P.R. 327/2001")
    parser.add_argument("--tracciato", required=True, help="Path GeoJSON/SHP del tracciato asse opera")
    parser.add_argument("--catasto", required=True, help="Path GeoJSON/SHP/GPKG delle particelle catastali")
    parser.add_argument("--strade", default=None, help="Path GeoJSON/SHP della rete viaria pubblica esistente")
    parser.add_argument("--visure", default=None, help="Path CSV/Excel delle visure censuarie ditte")
    parser.add_argument("--outdir", default="output_espropri", help="Cartella di output per GeoJSON e Excel")
    parser.add_argument("--crs", default="EPSG:32632", help="Sistema proiettato metrico locale (es. EPSG:32632 o EPSG:6708)")

    args = parser.parse_args()
    esegui_pipeline(
        tracciato_path=args.tracciato,
        catasto_path=args.catasto,
        strade_path=args.strade,
        visure_path=args.visure,
        output_dir=args.outdir,
        target_crs=args.crs
    )
