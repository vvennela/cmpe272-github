const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM} = require('jsdom');
const root = path.resolve(__dirname,'..');
const template = fs.readFileSync(path.join(root,'backend/templates/account.html'),'utf8');
const script = fs.readFileSync(path.join(root,'backend/static/account.js'),'utf8');
const tick = () => new Promise(resolve=>setImmediate(resolve));
function setup(t,mode='signup',handler) {
  // Keep the actual form markup; the backend suite separately verifies Jinja rendering.
  const html=template.replace(/{% if not config\['SECRET_KEY'\] %}disabled{% endif %}/g,'')
    .replace(/{% if mode == 'signup' %}([\s\S]*?){% endif %}/g,(_match,body)=>mode==='signup'?body:'')
    .replace('data-mode="{{ mode }}"',`data-mode="${mode}"`)
    .replace(/{{[\s\S]*?}}|{%[\s\S]*?%}/g,'');
  const dom=new JSDOM(html,{url:`http://localhost/${mode}`,runScripts:'outside-only'});
  t.after(()=>dom.window.close());
  const w=dom.window, $=id=>w.document.getElementById(id);
  w.AbortController=AbortController;
  const calls=[];
  w.fetch=async(url,options)=>{calls.push({url,options});return handler?handler(url,options):{ok:false,status:401,headers:{get:()=> 'application/json'},json:async()=>({error:'Email or password is incorrect.',errors:{}})};};
  w.eval(script);
  const submit=()=> $('account-form').dispatchEvent(new w.Event('submit',{cancelable:true}));
  const fill=()=>{
    if(mode==='signup') {$('name').value='QA Employee';$('address').value='1 Test Road';$('confirm_password').value='A long test passphrase!';}
    $('email').value='employee@example.com';$('password').value='A long test passphrase!';
  };
  return {w,$,submit,fill,calls};
}

test('signup validates required fields and focuses the first error',async(t)=>{
 const {w,$,submit,calls}=setup(t);submit();
 assert.equal(w.document.activeElement,$('name'));
 assert.equal($('password').getAttribute('aria-invalid'),'true');
 assert.equal(calls.length,0);
});

test('show/hide password controls update state and preserve the password',async(t)=>{
 const {w,$}=setup(t);$('password').value='A long test passphrase!';
 const toggle=w.document.querySelector('[data-password-toggle="password"]');
 toggle.click();assert.equal($('password').type,'text');assert.equal(toggle.getAttribute('aria-pressed'),'true');
 toggle.click();assert.equal($('password').type,'password');assert.equal($('password').value,'A long test passphrase!');
});

test('invalid login preserves email, clears password, and focuses the generic error',async(t)=>{
 const {w,$,fill,submit}=setup(t,'login');fill();submit();await tick();
 assert.equal($('email').value,'employee@example.com');
 assert.equal($('password').value,'');
 assert.match($('account-error').textContent,/Email or password/);
 assert.equal(w.document.activeElement,$('account-error'));
 assert.equal($('account-submit').disabled,false);
});

test('duplicate-email response focuses the field and never renders HTML',async(t)=>{
 const {w,$,fill,submit}=setup(t,'signup',async()=>({ok:false,status:409,headers:{get:()=> 'application/json'},json:async()=>({error:'Check your email.',errors:{email:'<img src=x onerror=alert(1)>'}})}));
 fill();submit();await tick();
 assert.equal(w.document.activeElement,$('email'));
 assert.equal(w.document.querySelectorAll('img').length,0);
 assert.match($('email-error').textContent,/<img/);
});

test('prevents duplicate submission and recovers from unavailable service',async(t)=>{
 let finish;
 const {$,fill,submit,calls}=setup(t,'login',()=>new Promise(resolve=>{finish=resolve;}));
 fill();submit();submit();assert.equal(calls.length,1);assert.equal($('account-submit').disabled,true);
 finish({ok:false,status:503,headers:{get:()=> 'application/json'},json:async()=>({error:'Accounts are temporarily unavailable.',errors:{}})});await tick();
 assert.equal($('account-submit').disabled,false);
 assert.equal($('account-form').getAttribute('aria-busy'),'false');
 assert.match($('account-error').textContent,/temporarily unavailable/);
});

test('offline submission preserves entered fields without sending a request',async(t)=>{
 const {w,$,fill,submit,calls}=setup(t);fill();
 Object.defineProperty(w.navigator,'onLine',{value:false});submit();
 assert.equal(calls.length,0);assert.match($('account-error').textContent,/offline/);
 assert.equal($('email').value,'employee@example.com');
});

test('password mismatch is shown before sending a signup request',async(t)=>{
 const {w,$,fill,submit,calls}=setup(t);fill();$('confirm_password').value='Different password';submit();
 assert.equal(calls.length,0);assert.equal(w.document.activeElement,$('confirm_password'));
 assert.match($('confirm_password-error').textContent,/must match/);
});
