/* Radar operativo: interfaccia ricostruita dal riferimento, dati dalle API del motore. */
(function() {
  'use strict';
  const M=RadarModel, $=id=>document.getElementById(id), pageSize=25;
  const state={items:[], originals:new Map(), filtered:[], phase:'', page:0, map:null, markers:new Map(), selected:null, satellite:true, loaded:false};
  const colors={AVANZATA_SENZA_ELENCO:'#f59e0b',ELENCO_PUBBLICATO:'#22c55e',PRELIMINARE:'#94a3b8',CHIUSA:'#ef4444',DA_VERIFICARE:'#a78bfa'};
  const esc=v=>String(v ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function sourceLink(value) {try {const u=new URL(value);return ['https:','http:'].includes(u.protocol)&&!u.username&&!u.password?u.href:null;} catch{return null;}}
  function when(value) {const d=new Date(value);return value && Number.isFinite(d.getTime()) ? new Intl.DateTimeFormat('it-IT',{dateStyle:'short',timeStyle:'short',timeZone:'Europe/Rome'}).format(d) : 'non disponibile';}
  function filters(){return {origin:$('origin').value,region:$('region').value,availability:$('availability').value,location:$('location').value,q:$('query').value,phase:state.phase};}
  function option(select,value,label){const o=document.createElement('option');o.value=value;o.textContent=label;select.appendChild(o);}
  function refresh(){
    state.filtered=M.filter(state.items,filters());
    if(state.selected && !state.filtered.some(o=>o.slug===state.selected))state.selected=null;
    state.page=Math.min(state.page,Math.max(0,Math.ceil(state.filtered.length/pageSize)-1));
    render();renderMap();
  }
  function geometries(items) {
    const seen=new Set(),features=[];
    for(const item of items)for(const row of state.originals.get(item.slug)?.ditte || []) {
      const g=row.geometry || row.geojson?.geometry;
      if(!['Polygon','MultiPolygon'].includes(g?.type))continue;
      const key=row.riferimento_catastale || JSON.stringify(g);
      if(seen.has(key))continue;seen.add(key);
      features.push({type:'Feature',geometry:g,properties:{slug:item.slug}});
    }
    return {type:'FeatureCollection',features};
  }
  function render(){
    const items=state.filtered, sum=key=>items.reduce((n,o)=>n+(o[key] || 0),0);
    $('k-total').textContent=items.length;
    $('k-lists').textContent=items.filter(o=>o.disponibilita==='ELENCO_DISPONIBILE').length;
    $('k-documents').textContent=sum('documenti');
    $('k-located').textContent=items.filter(o=>o.localizzata).length;
    $('k-parcels').textContent=geometries(items).features.length;
    $('k-unknown').textContent=items.filter(o=>o.stato_procedurale==='DA_VERIFICARE').length;
    $('k-regions').textContent=new Set(items.map(o=>o.regione).filter(Boolean)).size;
    $('list-count').textContent=`${items.length} di ${state.items.length}`;
    const located=items.filter(o=>M.markerAnchor(state.originals.get(o.slug))).length;
    $('coverage-count').textContent=`${located}/${items.length} posizioni`;
    $('coverage-text').innerHTML=`<b>${located}</b> opere con posizione documentata · <b>${items.length-located}</b> da localizzare. ${sum('righe_catalogo')} righe nel catalogo; ${sum('righe_archivio')} nell’archivio di origine. Le righe non sono proprietari unici.`;
    $('map-coverage').textContent=`${located} frecce di navigazione · ${items.length-located} opere senza posizione disponibile. Freccia azzurra: accesso alle particelle localizzate, non posizione generale dell’opera. Copertura parziale.`;
    const phaseButtons=Object.entries(M.labels).map(([key,label])=>{
      const n=state.items.filter(o=>o.stato_procedurale===key).length;
      return `<button type="button" class="stpill${state.phase===key?' on':''}" data-phase="${key}" aria-pressed="${state.phase===key}" ${n===0?'disabled':''}><span class="dot" style="background:${colors[key]}"></span><span class="txt">${esc(label)}</span><span class="n">${n}</span></button>`;
    }).join('');
    $('phases').innerHTML=`<span class="lb">Fase espropriativa</span>${phaseButtons}`;
    $('chart').innerHTML=Object.entries(M.availability).map(([key,label])=>{
      const n=items.filter(o=>o.disponibilita===key).length;
      return `<div class="bar"><div class="lab">${esc(label)}</div><div class="track"><div class="fill" style="width:${items.length?n/items.length*100:0}%;background:${key==='ELENCO_DISPONIBILE'?'#22c55e':'#f59e0b'}"></div></div><div class="val">${n}</div></div>`;
    }).join('');
    const ordered=[...items].sort((a,b)=>Number(b.localizzata)-Number(a.localizzata) || Number(b.disponibilita==='ELENCO_DISPONIBILE')-Number(a.disponibilita==='ELENCO_DISPONIBILE') || a.titolo.localeCompare(b.titolo,'it'));
    const shown=ordered.slice(state.page*pageSize,(state.page+1)*pageSize);
    $('list').innerHTML=shown.length ? shown.map(o=>{
      const url=sourceLink(o.fonte_atto_url);
      const mapped=Boolean(M.markerAnchor(state.originals.get(o.slug)));
      return `<article class="card${state.selected===o.slug?' selected':''}" style="border-left-color:${colors[o.stato_procedurale] || '#94a3b8'}" data-slug="${esc(o.slug)}"><div class="top"><span class="tag" style="background:#22c55e">${esc(o.origine_label)}</span><span class="st">${o.documenti} documenti</span></div><h2 class="t" style="font-size:13px">${esc(o.titolo)}</h2><div class="m">${esc(o.regione || 'Regione da verificare')} · ${esc(o.ente || 'Ente da verificare')}</div><div class="cup">CUP ${esc(o.cup || 'da verificare')} · ${esc(M.labels[o.stato_procedurale])}</div><div class="position${mapped?' located':''}">${o.tipo_posizione==='particelle'?'↗ Particelle localizzate':mapped?'↗ Punto documentato':'○ Posizione da acquisire'} · ${esc(M.availability[o.disponibilita])}</div><div class="source-line">${esc(o.host_fonti.join(' · ') || 'Fonte dell’opera collegata')}</div><div><button type="button" class="mt" data-select="${esc(o.slug)}">${mapped?'⌖ Mostra sulla mappa':'Apri fascicolo'} →</button><a href="/quadro-interferenze?opera=${encodeURIComponent(o.slug)}">Documenti e particelle ↗</a>${url?`<a href="${esc(url)}" target="_blank" rel="noopener">Fonte ente ↗</a>`:''}</div></article>`;
    }).join('') : '<div class="empty">Nessuna opera con questi filtri. Usa “Azzera filtri” per rivedere il catalogo.</div>';
    $('previous').disabled=state.page===0;
    $('next').disabled=(state.page+1)*pageSize>=items.length;
    $('page-status').textContent=items.length?`${state.page*pageSize+1}–${Math.min(items.length,(state.page+1)*pageSize)} di ${items.length}`:'0 risultati';
    $('fit-results').disabled=!located || !state.map;
    $('export-csv').disabled=!items.length;
  }
  function popup(item,anchor){return `<div><h3>${esc(item.titolo)}</h3><p>${esc(item.comune || item.regione || '')}</p><p>${anchor.type==='particelle'?'Freccia ancorata a un vertice delle particelle documentate. Non rappresenta l’asse o il centro dell’opera.':'Punto generale documentato dell’opera.'}</p><p>${item.documenti} documenti · ${item.particelle_uniche} particelle distinte</p><a href="/quadro-interferenze?opera=${encodeURIComponent(item.slug)}">Apri fascicolo e originali ↗</a></div>`;}
  function renderMap(){
    const map=state.map;
    if(!map || !state.loaded)return;
    const wanted=new Set(state.filtered.map(o=>o.slug));
    for(const [slug,m] of state.markers)if(!wanted.has(slug)){m.remove();state.markers.delete(slug);}
    for(const item of state.filtered){
      if(state.markers.has(item.slug))continue;
      const anchor=M.markerAnchor(state.originals.get(item.slug));if(!anchor)continue;
      const node=document.createElement('button');node.type='button';node.className='radar-pin';node.setAttribute('aria-label',`Mostra ${item.titolo}`);
      node.title=anchor.type==='particelle'?'Accesso alle particelle documentate':'Punto generale documentato';
      const color=anchor.type==='particelle'?'#22d3ee':'#22c55e';
      node.innerHTML=`<svg viewBox="0 0 40 54" aria-hidden="true"><path d="M20 52 4 27a19 19 0 1 1 32 0Z" fill="${color}" stroke="#0d1826" stroke-width="2"/><circle cx="20" cy="19" r="10" fill="#0d1826"/><path d="m16 22 8-8m-7 0h7v7" fill="none" stroke="white" stroke-width="2"/></svg>`;
      const marker=new maplibregl.Marker({element:node,anchor:'bottom'}).setLngLat(anchor.coordinates).setPopup(new maplibregl.Popup({offset:40}).setHTML(popup(item,anchor))).addTo(map);
      node.addEventListener('click',e=>{e.stopPropagation();select(item.slug);});state.markers.set(item.slug,marker);
    }
    map.getSource('parcels')?.setData(geometries(state.filtered));
  }
  function points(items){
    const result=[];
    function visit(c){if(!Array.isArray(c))return;if(typeof c[0]==='number'){if(Number.isFinite(c[0])&&Number.isFinite(c[1]))result.push(c.slice(0,2));}else c.forEach(visit);}
    geometries(items).features.forEach(f=>visit(f.geometry.coordinates));
    items.forEach(o=>{const a=M.markerAnchor(state.originals.get(o.slug));if(a)result.push(a.coordinates);});return result;
  }
  function fit(items){if(!state.map || !state.loaded)return;const pts=points(items);if(!pts.length)return;const b=new maplibregl.LngLatBounds();pts.forEach(p=>b.extend(p));state.map.fitBounds(b,{padding:55,maxZoom:items.length===1?16:13,duration:matchMedia('(prefers-reduced-motion: reduce)').matches?0:550});}
  function select(slug){
    const item=state.items.find(o=>o.slug===slug);if(!item)return;
    state.selected=slug;render();
    if(!state.map || !M.markerAnchor(state.originals.get(slug))){location.href=`/quadro-interferenze?opera=${encodeURIComponent(slug)}`;return;}
    fit([item]);
    for(const [key,m] of state.markers){if(key!==slug && m.getPopup().isOpen())m.togglePopup();}
    const marker=state.markers.get(slug);if(marker && !marker.getPopup().isOpen())marker.togglePopup();
  }
  function initMap(){
    try {
      if(typeof maplibregl==='undefined')throw Error('Libreria cartografica non disponibile');
      const source={type:'raster',tiles:['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'],tileSize:256,attribution:'Esri World Imagery',maxzoom:19};
      state.map=new maplibregl.Map({container:'radar-map',style:{version:8,sources:{base:source},layers:[{id:'basemap',type:'raster',source:'base'}]},center:[12.6,42.2],zoom:5.3});
      state.map.addControl(new maplibregl.NavigationControl({showCompass:false}),'bottom-right');state.map.addControl(new maplibregl.ScaleControl({unit:'metric'}),'bottom-left');
      state.map.on('load',()=>{state.loaded=true;state.map.addSource('parcels',{type:'geojson',data:{type:'FeatureCollection',features:[]}});state.map.addLayer({id:'parcel-fill',type:'fill',source:'parcels',paint:{'fill-color':'#22d3ee','fill-opacity':.28}});state.map.addLayer({id:'parcel-line',type:'line',source:'parcels',paint:{'line-color':'#67e8f9','line-width':2}});renderMap();render();fit(state.filtered);});
      state.map.on('error',()=>{ $('map-error').hidden=false; });
    } catch(error){state.map=null;$('map-error').hidden=false;console.warn('Radar cartografico:',error.message);}
  }
  async function request(url){const response=await fetch(url,{cache:'no-store',signal:AbortSignal.timeout(15000)});if(!response.ok)throw Error(`Archivio non disponibile (${response.status})`);return response.json();}
  async function load(){
    try{
      const [data,originals]=await Promise.all([request('/api/radar'),request('/api/opere')]);
      if(data.schema!=='motore-radar-v1' || !Array.isArray(data.opere) || !Array.isArray(originals))throw Error('Formato catalogo non valido');
      state.items=data.opere;state.originals=new Map(originals.map(o=>[o.slug,o]));
      const origins=new Map(state.items.map(o=>[o.origine,o.origine_label]));origins.forEach((label,value)=>option($('origin'),value,label));
      [...new Set(state.items.map(o=>o.regione).filter(Boolean))].sort().forEach(r=>option($('region'),r,r));
      const a=data.acquisizioni;
      let text=a.modalita==='catalogo_pubblico_sola_lettura'?`Catalogo pubblico · aggiornato ${when(a.aggiornato_il)}`:`Archivio documentale · ultima acquisizione ${when(a.ultima_acquisizione_il)}`;
      if(a.monitoraggio==='non_pubblicato')text+=' · monitoraggio crawler non pubblicato';
      else text+=` · ultimo tentativo ${when(a.ultimo_tentativo_il)} · ${a.errori_tentativi} errori su ${a.tentativi_considerati} tentativi registrati`;
      $('acquisition-text').textContent=text;
      refresh();if(state.loaded)fit(state.filtered);
      const slug=new URLSearchParams(location.search).get('opera');if(slug && state.items.some(o=>o.slug===slug))select(slug);
    } catch(error){$('acquisition-text').textContent=error.message;$('list').innerHTML='<div class="errorbox">Il catalogo non è disponibile. Nessun dato sostitutivo mostrato.<br><button id="retry" type="button">Riprova</button></div>';$('retry').addEventListener('click',()=>location.reload());$('map-coverage').textContent='Dati non disponibili';$('fit-results').disabled=true;$('export-csv').disabled=true;}
  }
  for(const id of ['origin','region','availability','location'])$(id).addEventListener('change',()=>{state.page=0;refresh();});
  let timer;$('query').addEventListener('input',()=>{clearTimeout(timer);timer=setTimeout(()=>{state.page=0;refresh();},150);});
  $('phases').addEventListener('click',e=>{const b=e.target.closest('[data-phase]');if(!b)return;state.phase=state.phase===b.dataset.phase?'':b.dataset.phase;state.page=0;refresh();});
  $('list').addEventListener('click',e=>{const b=e.target.closest('[data-select]');if(b)select(b.dataset.select);});
  $('clear-filters').addEventListener('click',()=>{for(const id of ['origin','region','availability','location','query'])$(id).value='';state.phase='';state.page=0;refresh();});
  $('previous').addEventListener('click',()=>{state.page=Math.max(0,state.page-1);render();$('list').scrollTop=0;});
  $('next').addEventListener('click',()=>{state.page++;render();$('list').scrollTop=0;});
  $('fit-results').addEventListener('click',()=>fit(state.filtered));
  $('overview').addEventListener('click',()=>{state.selected=null;for(const m of state.markers.values())if(m.getPopup().isOpen())m.togglePopup();render();fit(state.filtered);});
  document.addEventListener('keydown',e=>{if(e.key==='Escape' && !e.target.closest('input,select'))$('overview').click();});
  $('basemap').addEventListener('click',()=>{if(!state.map)return;state.satellite=!state.satellite;state.map.getSource('base').setTiles([state.satellite?'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}':'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}']);$('basemap').textContent=state.satellite?'◉ Satellite':'◉ Mappa scura';$('basemap').setAttribute('aria-pressed',String(state.satellite));});
  $('export-csv').addEventListener('click',()=>{const url=URL.createObjectURL(new Blob([M.csv(state.filtered)],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=`opere-radar-${new Date().toISOString().slice(0,10)}.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
  function clock(){$('clock').textContent=new Intl.DateTimeFormat('it-IT',{timeZone:'Europe/Rome',hour:'2-digit',minute:'2-digit',second:'2-digit'}).format(new Date())+' ora IT';}
  clock();setInterval(clock,1000);initMap();load();
})();
