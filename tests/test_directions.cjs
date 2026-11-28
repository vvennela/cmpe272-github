const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM } = require('jsdom');
const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'backend/templates/dashboard.html'), 'utf8');
const script = fs.readFileSync(path.join(root, 'backend/static/dashboard.js'), 'utf8');
const hub = { id: '1', name: 'Sunnyvale', address: 'Hub Road', type: 'BUS_STOP', position: {lat:37.3781,lng:-122.0307} };
const other = { ...hub, id: '2', name: 'Berryessa' };
const route = { duration:'600s', distanceMeters:1200, polyline:{encodedPolyline:'test-path'}, warnings:['Use sidewalks.'], legs:[{steps:[{navigationInstruction:{instructions:'Walk north.'}},{transitDetails:{transitLine:{nameShort:'22'},stopDetails:{departureStop:{name:'A'},arrivalStop:{name:'B'}}}}]}] };
const tick = () => new Promise((resolve) => setImmediate(resolve));
async function setup(t, directionsResponse, browserMap = false) {
  const dom = new JSDOM(html, { url:'http://localhost/?hub=1', runScripts:'outside-only' });
  t.after(() => dom.window.close());
  const w = dom.window;
  w.AbortController = AbortController; w.AbortSignal = AbortSignal;
  const calls = [];
  w.fetch = async (url, options = {}) => {
    calls.push({url,options});
    if (url.endsWith('/network')) return {ok:true,json:async()=>({hubs:[hub,other],routes:[]})};
    if (url.endsWith('/shuttles')) return {ok:true,json:async()=>({shuttles:[]})};
    return directionsResponse ? directionsResponse(url, options) : {ok:true,json:async()=>({routes:[route]})};
  };
  const $ = (id) => w.document.getElementById(id);
  // No external resources or browser credentials are loaded by these DOM tests.
  w.document.querySelector('.directions-panel').dataset.browserKey = '';
  const maps = { polylines:[] };
  if (browserMap) {
    w.google = {maps:{
      Map:class { fitBounds(bounds) { maps.bounds = bounds; } },
      LatLngBounds:class { constructor(){this.points=[];} extend(point){this.points.push(point);} },
      Polyline:class { constructor(options){maps.polylines.push(options);} setMap(value){maps.removed=value;} },
      geometry:{encoding:{decodePath:()=>[hub.position,other.position]}}
    }};
  }
  w.eval(script); await tick(); await tick();
  function submit(address = '1 Main St', mode = 'WALK') {
    $('directions-origin').value = address;
    w.document.querySelector(`input[value="${mode}"]`).checked = true;
    $('directions-form').dispatchEvent(new w.Event('submit',{cancelable:true}));
  }
  return {w,$,calls,submit,maps};
}

test('blank address focuses the input without a billable directions request',async(t)=>{
  const {$,submit,calls,w}=await setup(t);
  submit('   ');
  assert.equal($('directions-origin').getAttribute('aria-invalid'),'true');
  assert.equal(w.document.activeElement,$('directions-origin'));
  assert.equal(calls.filter(c=>c.url.endsWith('/directions')).length,0);
});

test('shows duration, distance, instructions, warnings and a safe Google navigation link',async(t)=>{
  const {$,submit,calls}=await setup(t);
  submit('1 Main St','TRANSIT'); await tick(); await tick();
  const sent=calls.find(c=>c.url.endsWith('/directions'));
  assert.deepEqual(JSON.parse(sent.options.body),{origin:'1 Main St',travelMode:'TRANSIT'});
  assert.match($('directions-results').textContent,/10 min · 1.2 km · Transit/);
  assert.match($('directions-results').textContent,/Take 22 from A to B/);
  assert.match($('directions-results').textContent,/Use sidewalks/);
  assert.equal(new URL($('directions-results').querySelector('a').href).hostname,'www.google.com');
  assert.match($('directions-map-status').textContent,/Route map unavailable/);
  assert.equal($('get-directions').disabled,false);
});

test('draws returned geometry on Google Maps when available',async(t)=>{
  const {$,submit,maps}=await setup(t,null,true);
  submit(); await tick(); await tick();
  assert.equal($('directions-map').hidden,false);
  assert.equal(maps.polylines.length,1);
  assert.equal(maps.polylines[0].path.length,2);
  assert.equal(maps.bounds.points.length,2);
});

test('empty routes and missing Google configuration have useful retry states',async(t)=>{
  let error=false;
  const {$,submit}=await setup(t,async()=>({ok:!error,json:async()=>error?{error:'Google Maps is not configured.'}:{routes:[]}}));
  submit(); await tick();
  assert.match($('directions-results').textContent,/No route found/);
  error=true; submit(); await tick();
  assert.match($('directions-status').textContent,/not configured yet/);
  assert.equal($('directions-origin').value,'1 Main St');
  assert.equal($('get-directions').disabled,false);
});

test('switching hubs aborts requests and ignores a late response',async(t)=>{
  let finish, signal;
  const {$,w,submit}=await setup(t,(_url,options)=>{
    signal=options.signal;
    return new Promise(resolve=>{finish=resolve;});
  });
  submit();
  w.document.querySelectorAll('.hub-card')[1].click();
  assert.equal(signal.aborted,true);
  finish({ok:true,json:async()=>({routes:[route]})});await tick();
  assert.match($('directions-destination').textContent,/Berryessa/);
  assert.doesNotMatch($('directions-results').textContent,/10 min/);
  assert.equal($('get-directions').disabled,false);
});

test('input/mode changes invalidate old directions and duplicate submit is blocked',async(t)=>{
  let finish;
  const {$,w,submit,calls}=await setup(t,()=>new Promise(resolve=>{finish=resolve;}));
  submit();submit();
  assert.equal(calls.filter(c=>c.url.endsWith('/directions')).length,1);
  $('directions-origin').dispatchEvent(new w.Event('input'));
  finish({ok:true,json:async()=>({routes:[route]})});await tick();
  assert.doesNotMatch($('directions-results').textContent,/10 min/);
  w.document.querySelector('input[value="DRIVE"]').dispatchEvent(new w.Event('change'));
  assert.match($('directions-status').textContent,/Travel mode changed/);
});

test('instructions are text rather than executable HTML',async(t)=>{
  const bad={...route,legs:[{steps:[{navigationInstruction:{instructions:'<img src=x onerror=alert(1)>'}}]}]};
  const {$,submit}=await setup(t,async()=>({ok:true,json:async()=>({routes:[bad]})}));
  submit();await tick();
  assert.equal($('directions-results').querySelectorAll('img').length,0);
  assert.match($('directions-results').textContent,/<img/);
});
