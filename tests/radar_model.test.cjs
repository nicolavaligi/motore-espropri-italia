const {test}=require('node:test');
const assert=require('node:assert/strict');
const M=require('../radar_model.js');
test('freccia su vertice reale senza trasformare il pin in posizione opera',()=>{
  const op={geo:null,ditte:[{geometry:{type:'Polygon',coordinates:[[[9,45],[9.1,45],[9.1,45.1],[9,45]]]}}]};
  const before=JSON.stringify(op), anchor=M.markerAnchor(op);
  assert.deepEqual(anchor,{coordinates:[9,45],type:'particelle'});
  assert.equal(JSON.stringify(op),before);
  assert.equal(M.markerAnchor({geo:null,comune:'Roma',ditte:[]}),null);
});
test('coordinate nulle o invalide non generano frecce, zero è valido',()=>{
  assert.equal(M.markerAnchor({geo:{lat:null,lng:11}}),null);
  assert.equal(M.markerAnchor({geo:{lat:'NaN',lng:11}}),null);
  assert.deepEqual(M.markerAnchor({geo:{lat:0,lng:0}}).coordinates,[0,0]);
});
test('filtri origine stato ed elenco rimangono indipendenti e includono ricerca senza accenti',()=>{
  const items=[{titolo:'Autorità portuale',origine:'ARCHIVIO_DOCUMENTALE',regione:'Veneto',stato_procedurale:'DA_VERIFICARE',disponibilita:'ELENCO_DISPONIBILE',localizzata:true},
    {titolo:'Altra opera',origine:'LEAD',regione:'Lazio',stato_procedurale:'AVANZATA_SENZA_ELENCO',disponibilita:'DA_ACQUISIRE',localizzata:false}];
  assert.equal(M.filter(items,{q:'AUTORITA',availability:'ELENCO_DISPONIBILE'}).length,1);
  assert.equal(M.filter(items,{phase:'AVANZATA_SENZA_ELENCO',availability:'ELENCO_DISPONIBILE'}).length,0);
  assert.equal(M.filter(items,{origin:'LEAD',location:'missing'}).length,1);
  assert.equal(M.filter(items).length,2);
});
test('CSV mantiene tutti i risultati, valori sconosciuti vuoti e celle formula neutralizzate',()=>{
 const rows=Array.from({length:550},(_,i)=>({titolo:i===0?'=1+1':`Opera ${i}`,cup:null,documenti:0}));
 const csv=M.csv(rows);
 assert.ok(csv.startsWith('\ufeff'));
 assert.equal(csv.split('\r\n').length,551);
 assert.ok(csv.includes('"\'=1+1"'));
 assert.ok(!csv.includes('undefined'));
});
