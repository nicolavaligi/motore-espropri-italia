"""Proiezione operativa del catalogo: solo evidenze, conteggi e fonti pubbliche."""
from datetime import datetime, timezone
import re
from urllib.parse import urlsplit

STATES = {'AVANZATA_SENZA_ELENCO', 'ELENCO_PUBBLICATO', 'PRELIMINARE', 'CHIUSA'}
ORIGINS = {'PNRR': 'PNRR', 'LEAD': 'Nuovi lead', 'NOSTRA': 'Opere interne', 'ARCHIVIO': 'Archivio',
           'ARCHIVIO_DOCUMENTALE': 'Archivio documentale'}
LIST_TITLE = re.compile(r'piano\s+particell|elenco.{0,20}ditt|elenco.{0,20}espropriat', re.I)


def public_link(value):
    try:
        p = urlsplit(value or '')
        if p.scheme in {'https', 'http'} and p.hostname and not p.username and not p.password:
            return value
    except ValueError:
        pass
    return None


def count(value):
    try:
        return max(0, int(value)) if value is not None else None
    except (TypeError, ValueError, OverflowError):
        return None


def date_value(value):
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    except (ValueError, TypeError, AttributeError):
        return None


def latest(values):
    dates = [dt for v in values if (dt := date_value(v)) is not None]
    return max(dates).isoformat() if dates else None


def radar_catalogue(opere, archive_status=None):
    status = archive_status or {}
    items, all_refs, acquisition_dates = [], set(), []
    for op in opere:
        docs = [d for d in op.get('documenti', []) if d.get('attivo', 1)]
        sources = [public_link(d.get('fonte_url')) for d in docs]
        sources = sorted({urlsplit(u).hostname for u in sources if u})
        rows = op.get('ditte') or []
        located = [r for r in rows if (r.get('geometry') or {}).get('type') in {'Polygon', 'MultiPolygon'}]
        refs = {r.get('riferimento_catastale') or f"{op['slug']}:{r.get('id', i)}" for i, r in enumerate(located)}
        all_refs.update(refs)
        listed_rows = count(op.get('righe_catastali'))
        archive_rows = count(op.get('righe_catastali_archivio'))
        if listed_rows is None:
            listed_rows = len(rows)
        if archive_rows is None:
            archive_rows = listed_rows
        has_list = any(d.get('tipo') in {'elenco_ditte', 'piano_particellare'} or
                       LIST_TITLE.search(d.get('titolo') or '') or (count(d.get('righe_estratte')) or 0) > 0
                       for d in docs) or listed_rows > 0
        availability = 'ELENCO_DISPONIBILE' if has_list else ('DOCUMENTI_DA_VERIFICARE' if docs else 'DA_ACQUISIRE')
        origin = op.get('origine') or op.get('fonte')
        origin = origin if origin in ORIGINS else 'ARCHIVIO_DOCUMENTALE'
        declared = op.get('stato_procedurale') or op.get('stato_master') or op.get('stato_opera')
        procedural_state = declared if declared in STATES else 'DA_VERIFICARE'
        geo = op.get('geo')
        has_point = bool(geo and op.get('fonte_coordinate') and
                         isinstance(geo.get('lat'), (float, int)) and isinstance(geo.get('lng'), (float, int)) and
                         -90 <= geo['lat'] <= 90 and -180 <= geo['lng'] <= 180)
        dates = [d.get('acquisito_il') for d in docs]
        acquisition_dates.extend(dates)
        items.append(dict(slug=op['slug'], titolo=op.get('titolo'), cup=op.get('cup'),
                          ente=op.get('ente_promotore') or op.get('ente'), regione=op.get('regione'),
                          comune=op.get('comune'), origine=origin, origine_label=ORIGINS[origin],
                          stato_procedurale=procedural_state, disponibilita=availability,
                          documenti=len(docs), righe_catalogo=listed_rows, righe_archivio=archive_rows,
                          particelle_uniche=len(refs), localizzata=bool(located or has_point),
                          tipo_posizione='particelle' if located else ('punto_documentato' if has_point else 'non_disponibile'),
                          fonte_atto_url=public_link(op.get('fonte_atto_url')), host_fonti=sources,
                          ultima_acquisizione_il=latest(dates)))
    attempts = status.get('ultime_acquisizioni') or []
    last_attempt = max((a for a in attempts if date_value(a.get('eseguito_il'))),
                       key=lambda a: date_value(a['eseguito_il']), default=None)
    public = status.get('modalita') == 'catalogo_pubblico_sola_lettura'
    return dict(schema='motore-radar-v1', opere=items,
                riepilogo=dict(opere=len(items), documenti=sum(o['documenti'] for o in items),
                               con_elenco=sum(o['disponibilita'] == 'ELENCO_DISPONIBILE' for o in items),
                               senza_stato=sum(o['stato_procedurale'] == 'DA_VERIFICARE' for o in items),
                               localizzate=sum(o['localizzata'] for o in items), particelle_uniche=len(all_refs),
                               righe_catalogo=sum(o['righe_catalogo'] for o in items),
                               righe_archivio=sum(o['righe_archivio'] for o in items)),
                acquisizioni=dict(modalita='catalogo_pubblico_sola_lettura' if public else 'archivio_documentale',
                                  aggiornato_il=status.get('aggiornato_il'), ultima_acquisizione_il=latest(acquisition_dates),
                                  monitoraggio='non_pubblicato' if public or not attempts else 'tentativi_registrati',
                                  ultimo_tentativo_il=last_attempt.get('eseguito_il') if last_attempt else None,
                                  ultimo_esito=last_attempt.get('stato') if last_attempt else None,
                                  tentativi_considerati=len(attempts),
                                  errori_tentativi=sum(str(a.get('stato', '')).startswith('errore_') for a in attempts)),
                completezza='non_certificata')
