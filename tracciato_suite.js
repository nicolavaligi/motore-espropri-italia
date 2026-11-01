/* Importazione di geometrie reali. Nessuna ricostruzione o fascia automatica. */
(function(root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.TracciatoSuite = factory();
})(typeof self !== 'undefined' ? self : this, function() {
  function distanzaMetriWgs84(a,b) {
    const rad=Math.PI/180, dlat=(b[1]-a[1])*rad, dlon=(b[0]-a[0])*rad;
    const h=Math.sin(dlat/2)**2+Math.cos(a[1]*rad)*Math.cos(b[1]*rad)*Math.sin(dlon/2)**2;
    return 6371008.8*2*Math.asin(Math.sqrt(Math.min(1,Math.max(0,h))));
  }
  function linee(feature) {
    return feature.geometry.type === 'LineString' ? [feature.geometry.coordinates] : feature.geometry.coordinates;
  }
  function coordinateTracciato(feature) { return linee(feature).flat(); }
  function lunghezzaTracciato(feature) {
    return linee(feature).reduce((total,line)=>total+line.slice(1).reduce((n,p,i)=>n+distanzaMetriWgs84(line[i],p),0),0);
  }
  function valida(feature) {
    if (!feature?.geometry || !['LineString','MultiLineString'].includes(feature.geometry.type))
      throw new Error('Richiesto un tracciato LineString o MultiLineString.');
    const parts=linee(feature);
    if (!Array.isArray(parts) || !parts.length) throw new Error('Tracciato vuoto.');
    let vertices=0;
    for (const part of parts) {
      if (!Array.isArray(part) || part.length<2) throw new Error('Ogni linea richiede almeno due vertici.');
      for (const p of part) {
        if (!Array.isArray(p) || p.length<2 || p.length>3 || !p.every(Number.isFinite) || Math.abs(p[0])>180 || Math.abs(p[1])>90)
          throw new Error('Coordinate non valide: richiesti longitudine e latitudine WGS84.');
        if (++vertices>100000) throw new Error('Superato il limite di 100000 vertici.');
      }
      if (!part.some(p=>p[0]!==part[0][0] || p[1]!==part[0][1])) throw new Error('Linea di lunghezza nulla.');
    }
    return feature;
  }
  function parseTracciatoFile(content, filename='tracciato') {
    if (content.length>10*1024*1024) throw new Error('File superiore a 10 MB.');
    if (/\.kml$/i.test(filename) || /<(?:\w+:)?kml\b/i.test(content)) {
      const xml=new DOMParser().parseFromString(content,'text/xml');
      if (xml.getElementsByTagName('parsererror').length) throw new Error('KML non valido.');
      const nodes=Array.from(xml.getElementsByTagNameNS('*','LineString'));
      const parts=nodes.map(node=>{
        const coordinates=node.getElementsByTagNameNS('*','coordinates')[0];
        if (!coordinates) throw new Error('LineString KML senza coordinate.');
        return coordinates.textContent.trim().split(/\s+/).map(tuple=>tuple.split(',').map(v=>v.trim()===''?NaN:Number(v)));
      });
      if (!parts.length) throw new Error('Nessuna LineString KML: punti e anelli non sono assi.');
      return valida({type:'Feature',geometry:parts.length===1?{type:'LineString',coordinates:parts[0]}:{type:'MultiLineString',coordinates:parts},properties:{nome:filename,fonte:'File KML caricato',verifica:'da_verificare_sulla_fonte'}});
    }
    const parsed=JSON.parse(content);
    if (parsed.crs) throw new Error('Riproiettare in WGS84 GeoJSON RFC 7946 prima del caricamento.');
    const features=parsed.type==='FeatureCollection'?parsed.features:[parsed.type==='Feature'?parsed:{type:'Feature',geometry:parsed,properties:{}}];
    if (!Array.isArray(features) || !features.length) throw new Error('File privo di geometrie.');
    const parts=[];
    for (const feature of features) {
      if (feature.crs || feature.geometry?.crs) throw new Error('CRS alternativo non supportato: riproiettare in WGS84.');
      valida(feature);
      parts.push(...linee(feature));
    }
    return valida({type:'Feature',geometry:parts.length===1?{type:'LineString',coordinates:parts[0]}:{type:'MultiLineString',coordinates:parts},properties:{...(features.length===1?features[0].properties:{}),file_sorgente:filename,verifica:'da_verificare_sulla_fonte'}});
  }
  function esportaGeoJsonTracciato(op) {
    if (!op.tracciato_geojson || !op.fonte_tracciato_url) { alert('Nessun tracciato documentato disponibile.'); return; }
    const data={...op.tracciato_geojson,metadata:{fonte_url:op.fonte_tracciato_url,opera_slug:op.slug,crs:'EPSG:4326'}};
    const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/geo+json'}));
    const anchor=document.createElement('a');anchor.href=url;anchor.download=`Tracciato_${op.slug}.geojson`;anchor.click();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  return {KNOWN_TRACCIATI:Object.freeze({}),generaTracciatoParametrico:()=>null,generaSuiteGeoJsonPerOpera:()=>null,
    distanzaMetriWgs84,coordinateTracciato,lunghezzaTracciato,parseTracciatoFile,esportaGeoJsonTracciato};
});
