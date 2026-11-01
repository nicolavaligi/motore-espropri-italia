const {test}=require('node:test');
const assert=require('node:assert/strict');
const suite=require('../tracciato_suite.js');
const line=coordinates=>({type:'Feature',geometry:{type:'LineString',coordinates},properties:{}});
test('parti separate conservate senza segmento inventato',()=>{
 const result=suite.parseTracciatoFile(JSON.stringify({type:'FeatureCollection',features:[line([[9,45],[9.001,45]]),line([[12,45],[12.001,45]])]}),'reale.geojson');
 assert.equal(result.geometry.type,'MultiLineString');
 assert.ok(suite.lunghezzaTracciato(result)<160);
 assert.equal(suite.coordinateTracciato(result).length,4);
});
test('coordinate proiettate, punti, vuoti e linee degeneri rifiutati',()=>{
 for(const data of [line([[500000,5000000],[500100,5000100]]),line([[9,45],[9,45]]),{type:'Point',coordinates:[9,45]},{type:'FeatureCollection',features:[]}])
   assert.throws(()=>suite.parseTracciatoFile(JSON.stringify(data),'dato.geojson'));
});
test('nessuna ricostruzione o buffer disponibile',()=>{
 assert.equal(suite.generaSuiteGeoJsonPerOpera({slug:'opera'}),null);
 assert.equal(suite.calcolaBufferPoligono,undefined);
});
