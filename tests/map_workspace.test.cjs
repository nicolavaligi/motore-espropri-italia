// Esecuzione: node --test tests/map_workspace.test.cjs
// Esegue la logica dell'app con un adattatore DOM/MapLibre, senza tile remoti.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.join(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const inline = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]).join('\n');

function app() {
  const elements = new Map();
  function element() { return {value:'', checked:false, textContent:'', innerHTML:'', style:{setProperty(){}},
    offsetWidth:352, dataset:{}, attrs:{}, classList:{add(){}, remove(){}, toggle(){}},
    setAttribute(k,v){this.attrs[k]=v;}, addEventListener(){}, scrollIntoView(){}, focus(){}}; }
  const document = {
    getElementById(id){if(!elements.has(id))elements.set(id,element()); return elements.get(id);},
    createElement:element, querySelectorAll(){return [];}, addEventListener(){}
  };
  for(const id of ['chk-st-avanzata','chk-st-elenco'])document.getElementById(id).checked=true;
  const sources = {};
  const map = {getBounds:()=>({contains:([lng,lat])=>lng>=10&&lng<=13&&lat>=44&&lat<=46}),
    getZoom:()=>6, getPitch:()=>0, isStyleLoaded:()=>true,
    getSource(id){return sources[id] ||= {setData(data){this.data=data;}};},
    fitBounds(bounds,opts){this.lastFit={bounds,opts};}, flyTo(){}, getLayer:()=>null};
  class Popup {setHTML(html){this.html=html;return this;}isOpen(){return false;}remove(){}}
  class Marker {
    constructor(options){this.options=options;this.removed=false;}
    setLngLat(p){this.position=p;return this;}setPopup(p){this.popup=p;return this;}
    addTo(){return this;}remove(){this.removed=true;return this;}getPopup(){return this.popup;}
  }
  class Bounds {constructor(){this.points=[];}extend(p){this.points.push(p);return this;}}
  const window = {innerWidth:1440, location:{href:'https://example.test/',hostname:'example.test',pathname:'/'},
    addEventListener(){},matchMedia:()=>({matches:false})};
  const context = vm.createContext({window, document, maplibregl:{Popup,Marker,LngLatBounds:Bounds},
    console, setTimeout, clearTimeout, setInterval, requestAnimationFrame:fn=>setTimeout(fn,0),
    URL, AbortSignal});
  vm.runInContext(fs.readFileSync(path.join(root,'map_workspace.js'),'utf8'),context);
  vm.runInContext(inline, context);
  context.map=map;
  vm.runInContext('state.map=map',context);
  return {context,document,map,sources,run:code=>vm.runInContext(code,context)};
}
const opere = [
 {slug:'vicenza',titolo:'Linea ferroviaria',ente:'RFI',comune:'Vicenza',regione:'Veneto',stato_opera:'AVANZATA_SENZA_ELENCO',geo:{lat:45.5,lng:11.5},ditte:[]},
 {slug:'roma',titolo:'Opera Roma',ente:'Comune',comune:'Roma',regione:'Lazio',stato_opera:'ELENCO_PUBBLICATO',geo:{lat:41.9,lng:12.5},ditte:[]},
 {slug:'chiusa',titolo:'Opera chiusa',regione:'Veneto',stato_opera:'CHIUSA',geo:{lat:45.1,lng:11.5},ditte:[]}
];
function dataset(a,data=opere){a.context.dataset=structuredClone(data);a.run('state.opere=dataset');}

test('i filtri iniziali non mostrano opere chiuse; il conteggio in vista usa il territorio',()=>{
 const a=app();dataset(a);a.run('applyFilters()');
 assert.equal(a.run('state.filteredOpere.length'),2);
 assert.equal(a.run('state.markers.length'),2);
 assert.equal(a.document.getElementById('stat-in-vista').textContent,1);
 assert.match(a.document.getElementById('map-view-status').textContent,/1 in vista · 2 opere filtrate/);
});
test('i marker superstiti vengono riutilizzati e quelli esclusi rimossi',()=>{
 const a=app();dataset(a);a.run('applyFilters(); globalThis.first=state.markerMap.vicenza; globalThis.excluded=state.markerMap.roma');
 a.document.getElementById('filter-search').value='ferroviaria';a.run('applyFilters()');
 assert.equal(a.run('state.markerMap.vicenza===first'),true);
 assert.equal(a.run('excluded.removed'),true);
 assert.equal(a.run('state.markers.length'),1);
});
test('la ricerca ignora accenti e include ente_promotore',()=>{
 const a=app();dataset(a,[{...opere[0],ente:null,ente_promotore:'Autorità Portuale'}]);
 a.document.getElementById('filter-search').value='AUTORITA';a.run('applyFilters()');
 assert.equal(a.run('state.filteredOpere.length'),1);
});
test('solo area visibile esclude le opere esterne senza modificare la camera',()=>{
 const a=app();dataset(a);a.document.getElementById('filter-in-view').checked=true;a.run('applyFilters()');
 assert.equal(a.run('state.filteredOpere.length'),1);
 assert.equal(a.map.lastFit,undefined);
});
test('zero risultati disabilita inquadramento e conserva una lista vuota',()=>{
 const a=app();dataset(a);a.document.getElementById('filter-search').value='inesistente';a.run('applyFilters();fitMapResults()');
 assert.equal(a.run('state.filteredOpere.length'),0);
 assert.equal(a.document.getElementById('btn-fit-results').disabled,true);
 assert.equal(a.map.lastFit,undefined);
 assert.match(a.document.getElementById('quick-opere-list').innerHTML,/Azzera filtri/);
});
test('inquadra risultati limita lo zoom e considera lo spazio dei pannelli',()=>{
 const a=app();dataset(a);a.run('applyFilters();fitMapResults()');
 assert.equal(a.map.lastFit.bounds.points.length,2);
 assert.equal(a.map.lastFit.opts.maxZoom,13);
 assert.ok(a.map.lastFit.opts.padding.left>350);
});
test('senza geometrie non vengono fabbricate particelle o assi',()=>{
 const a=app();dataset(a,[{...opere[0],ditte:[{intestatario:'Rossi',sup_mq:1000}]}]);a.run('applyFilters()');
 assert.equal(a.sources['particellare-source'].data.features.length,0);
 assert.equal(a.sources['opera-source'].data.features.length,0);
});
test('le geometrie effettive conservano forma e informazioni senza inventare relitti',()=>{
 const a=app();const geometry={type:'Polygon',coordinates:[[[11,45],[11.1,45],[11.1,45.1],[11,45]]]};
 dataset(a,[{...opere[0],ditte:[{geometry,delta:800,sup_esproprio_mq:100}]}]);a.run('applyFilters()');
 const feature=a.sources['particellare-source'].data.features[0];
 assert.deepEqual(feature.geometry,geometry);
 assert.equal(feature.properties.relitto_critico,false);
 assert.equal(feature.properties.sup_esproprio_mq,100);
});
test('coordinate zero valide, coordinate mancanti o non numeriche escluse',()=>{
 const a=app();
 assert.equal(a.run('validMapCoordinates({geo:{lat:0,lng:0}})'),true);
 assert.equal(Boolean(a.run('validMapCoordinates({geo:{lat:null,lng:10}})')),false);
 assert.equal(Boolean(a.run('validMapCoordinates({geo:{lat:"err",lng:10}})')),false);
});
test('le righe catastali non sono conteggiate come nominativi distinti',()=>{
 const a=app();a.context.rows=[{intestatario:'Rossi Mario'},{intestatario:' ROSSI MARIO '},{intestatario:'Bianchi Anna'}];
 assert.equal(a.run('countMapIntestatari(rows)'),2);
});

test('le opere documentate senza coordinate aprono comunque il fascicolo',()=>{
 const a=app();dataset(a,[{...opere[0],tipo_dati:'documentale',geo:null,documenti:[],ditte:[]}]);
 a.run("applyFilters();selectAndOpenPin('vicenza')");
 assert.equal(a.run('state.selectedOpera.slug'),'vicenza');
 assert.equal(a.run('state.markers.length'),0);
});
test('il catalogo di produzione non genera tracciati ricostruiti',()=>{
 const a=app();dataset(a,[{...opere[0],tipo_dati:'documentale',ditte:[]}]);
 a.context.window.TracciatoSuite={KNOWN_TRACCIATI:{vicenza:{}},generaSuiteGeoJsonPerOpera(){throw new Error('Ricostruzione non ammessa');}};
 a.run('applyFilters()');
 assert.equal(a.sources['opera-source'].data.features.length,0);
});
test('i fascicoli restano disponibili quando il motore cartografico non si avvia',()=>{
 const a=app();dataset(a,[{...opere[0],tipo_dati:'documentale',geo:null,documenti:[],ditte:[]}]);
 a.run('state.map=null;applyFilters()');
 assert.match(a.document.getElementById('quick-opere-list').innerHTML,/Linea ferroviaria/);
});

test('le particelle senza pin consentono inquadramento e filtro in vista',()=>{
 const a=app();
 const geometry={type:'Polygon',coordinates:[[[11,45],[11.01,45],[11.01,45.01],[11,45]]]};
 dataset(a,[{...opere[0],geo:null,tipo_dati:'documentale',ditte:[{geometry}]}]);
 a.run('applyFilters();fitMapResults()');
 assert.equal(a.document.getElementById('btn-fit-results').disabled,false);
 assert.equal(a.map.lastFit.bounds.points.length,4);
 assert.equal(a.map.lastFit.opts.maxZoom,17);
 a.document.getElementById('filter-in-view').checked=true;a.run('applyFilters()');
 assert.equal(a.run('state.filteredOpere.length'),1);
});
test('i subalterni non duplicano la geometria catastale rappresentata',()=>{
 const a=app();const geometry={type:'Polygon',coordinates:[[[11,45],[11.01,45],[11.01,45.01],[11,45]]]};
 dataset(a,[{...opere[0],geo:null,ditte:[{geometry,riferimento_catastale:'comune/1/2',sub:'1'},{geometry,riferimento_catastale:'comune/1/2',sub:'2'}]}]);
 a.run('applyFilters()');
 assert.equal(a.sources['particellare-source'].data.features.length,1);
 assert.match(a.document.getElementById('map-view-status').textContent,/1 particelle localizzate/);
});
test('apertura geometrie effettive non richiede un asse di progetto',()=>{
 const a=app();const geometry={type:'Polygon',coordinates:[[[11,45],[11.01,45],[11.01,45.01],[11,45]]]};
 dataset(a,[{...opere[0],geo:null,ditte:[{geometry}]}]);
 a.run("applyFilters();selectAndOpenPin('vicenza')");
 assert.equal(a.run('state.selectedOpera.slug'),'vicenza');
 assert.equal(a.map.lastFit.bounds.points.length,4);
});
