/* Funzioni condivise dal radar; nessun dato dimostrativo o geocodifica implicita. */
(function(root) {
  const labels = {DA_VERIFICARE:'Fase da verificare', AVANZATA_SENZA_ELENCO:'Avanzata · elenco atteso',
    ELENCO_PUBBLICATO:'Elenco pubblicato', PRELIMINARE:'Preliminare', CHIUSA:'Chiusa'};
  const availability = {ELENCO_DISPONIBILE:'Elenco disponibile', DOCUMENTI_DA_VERIFICARE:'Documenti da verificare', DA_ACQUISIRE:'Documenti da acquisire'};
  function normalize(value) {return String(value ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase('it').trim();}
  function filter(items, f={}) {
    const q=normalize(f.q);
    return items.filter(o => (!f.origin || o.origine===f.origin) && (!f.region || o.regione===f.region) &&
      (!f.phase || o.stato_procedurale===f.phase) && (!f.availability || o.disponibilita===f.availability) &&
      (!f.location || (f.location==='located' ? o.localizzata : !o.localizzata)) &&
      (!q || normalize([o.titolo,o.slug,o.cup,o.ente,o.comune,o.regione].join(' ')).includes(q)));
  }
  function markerAnchor(op) {
    const geo=op?.geo;
    if (geo && geo.lat!==null && geo.lng!==null && geo.lat!=='' && geo.lng!=='' &&
        Number.isFinite(Number(geo.lat)) && Number.isFinite(Number(geo.lng)) && Math.abs(Number(geo.lat))<=90 && Math.abs(Number(geo.lng))<=180)
      return {coordinates:[Number(geo.lng),Number(geo.lat)], type:'punto_documentato'};
    let point=null;
    function visit(c) {
      if (point || !Array.isArray(c)) return;
      if (typeof c[0]==='number') {
        if(Number.isFinite(c[0]) && Number.isFinite(c[1]) && Math.abs(c[0])<=180 && Math.abs(c[1])<=90)point=c.slice(0,2);
      } else c.forEach(visit);
    }
    for(const row of op?.ditte || []) {
      const g=row.geometry || row.geojson?.geometry;
      if(['Polygon','MultiPolygon'].includes(g?.type))visit(g.coordinates);
      if(point)break;
    }
    return point ? {coordinates:point,type:'particelle'} : null;
  }
  function csv(items) {
    const fields=[['titolo','Opera'],['cup','CUP'],['ente','Ente'],['regione','Regione'],['comune','Comune'],
      ['origine_label','Origine'],['stato_procedurale','Fase dichiarata'],['disponibilita','Disponibilità documenti'],
      ['documenti','Documenti'],['righe_catalogo','Righe nel catalogo'],['righe_archivio','Righe in archivio'],
      ['particelle_uniche','Particelle localizzate distinte'],['ultima_acquisizione_il','Acquisito il'],['fonte_atto_url','Fonte']];
    const cell=value=>'"'+String(value ?? '').replace(/^[=+@\-\t\r]/, "'$&").replace(/"/g,'""')+'"';
    return '\ufeff'+[fields.map(([,label])=>cell(label)).join(';'),...items.map(o=>fields.map(([key])=>cell(o[key])).join(';'))].join('\r\n');
  }
  const api={labels,availability,normalize,filter,markerAnchor,csv};
  root.RadarModel=api;
  if(typeof module!=='undefined' && module.exports)module.exports=api;
})(globalThis);
