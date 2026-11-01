// Mutates only a disposable demo at localhost:18080. Never targets a system service.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
const modulePath=process.env.PLAYWRIGHT_MODULE;
if(!modulePath)throw Error('Set PLAYWRIGHT_MODULE to an installed Playwright ESM module.');
const {chromium}=await import(pathToFileURL(modulePath).href);
const base='http://127.0.0.1:18080/apps/travel/';
const origin=new URL(base).origin;
const output=process.env.QA_OUTPUT||'qa-output/screenshots';
await fs.mkdir(output,{recursive:true});
const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});
const desktop=await browser.newContext({viewport:{width:1440,height:1050}});
const mobile=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
const a=await desktop.newPage(),b=await mobile.newPage();
const errors=[];for(const p of[a,b])p.on('pageerror',e=>errors.push(e.message));
const downloads=[];
for(const context of[desktop,mobile])context.on('page',p=>p.on('download',d=>downloads.push(d.suggestedFilename())));
for(const p of[a,b])p.on('download',d=>downloads.push(d.suggestedFilename()));
const request=desktop.request;
let customId,arrivalOriginal;
async function mutate(body){const r=await request.post(base+'api/items',{headers:{Origin:origin,'X-Travel-App':'1'},data:body});assert.equal(r.status(),200,await r.text());return r.json();}
async function overflow(p){assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);}
try{
 await Promise.all([a.goto(base),b.goto(base)]);await a.locator('.booking').first().waitFor();await b.locator('.booking').first().waitFor();
 assert.equal(await a.locator('#bookings .booking').count(),2);assert.equal(await a.locator('#bookings .pdf-links a').count(),10);assert.equal(await a.locator('.flight').count(),6);
 assert.equal(await a.locator('#boarding-passes .pdf-links a').count(),10);
 for(const page of[a,b])await overflow(page);
 for(const [page,label] of[[a,'desktop'],[b,'mobile']]){
  const links=page.locator('.pdf-links a,#boarding-pass-bundle');
  assert.equal(await links.count(),21);
  for(const link of await links.all()){
   assert.equal(await link.getAttribute('download'),null);
   assert.equal(await link.getAttribute('target'),'_blank');
   assert.match(await link.textContent(),/Read.*PDF/);
  }
  for(const selector of['#bookings .pdf-links a','#boarding-passes .pdf-links a','#boarding-pass-bundle']){
   const link=page.locator(selector).first();
   const href=await link.evaluate(a=>a.href);
   const [response,reader]=await Promise.all([
    page.context().waitForEvent('response',{predicate:r=>r.url()===href&&r.request().isNavigationRequest()}),
    page.waitForEvent('popup'),link.click()
   ]);
   assert.equal(response.status(),200);
   assert.equal(await response.headerValue('content-type'),'application/pdf');
   assert.match(await response.headerValue('content-disposition'),/^inline; /);
   await reader.waitForLoadState('load');
   await reader.waitForLoadState('networkidle');
   assert.equal(reader.url(),href);
   if(selector==='#boarding-pass-bundle')await reader.screenshot({path:output+'/pdf-reader-'+label+'.png'});
   await reader.close();
  }
 }
 assert.deepEqual(downloads,[]);
 await a.locator('[data-copy="0"]').click();await a.locator('#toast').waitFor({state:'visible'});assert.match(await a.locator('#toast').textContent(),/copied|Press and hold/);
 await a.locator('#toast').waitFor({state:'hidden'});await a.evaluate(()=>window.scrollTo(0,0));await b.evaluate(()=>window.scrollTo(0,0));
 await a.screenshot({path:output+'/demo-desktop.png',fullPage:true});await b.screenshot({path:output+'/demo-mobile.png',fullPage:true});
 await a.locator('[data-tab=packing]').click();await b.locator('[data-tab=packing]').click();
 await a.locator('#search').fill('Homer');assert.equal(await a.locator('[data-check]').count(),2);await a.locator('#search').fill('');
 const literal='QA emergency donut <b>literal</b>';await a.locator('#new-item').fill(literal);await a.locator('#add-form button').click();await a.getByText(literal,{exact:true}).waitFor();
 const s=await(await request.get(base+'api/state')).json();customId=s.items.find(i=>i.text===literal).id;assert.equal(await a.locator(`[data-item="${customId}"] b`).count(),0);
 await b.getByText(literal,{exact:true}).waitFor({timeout:12000});await a.locator(`[data-check="${customId}"]`).check();await b.waitForFunction(id=>document.querySelector(`[data-check="${id}"]`)?.checked,customId,{timeout:12000});
 await b.locator('#remaining').check();assert.equal(await b.locator(`[data-check="${customId}"]`).count(),0);await b.locator('#remaining').uncheck();
 await a.locator('[data-tab=admin]').click();arrivalOriginal=await a.locator('[data-check=visitor-cards]').isChecked();await a.locator('[data-check=visitor-cards]').setChecked(!arrivalOriginal);await a.waitForFunction(()=>document.querySelector('#sync').textContent.includes('saved'));
 assert.ok((await(await request.get(base+'todo.md')).text()).includes(`- [${arrivalOriginal?' ':'x'}] **28 May 2030`));
 await mutate({action:'toggle',id:'visitor-cards',done:arrivalOriginal});arrivalOriginal=undefined;
 await mutate({action:'remove',id:customId});customId=undefined;
 assert.deepEqual(errors,[]);
 const report={result:'passed',viewports:[1440,390],checks:['six fictional legs','21 PDF links open new tabs without download attributes','ticket, pass and combined PDF navigation on desktop and mobile','inline PDF responses and no download events','copy control','search','custom add/remove','safe literal rendering','two-browser checklist synchronization','hide completed','visitor-card Markdown mirror','no horizontal overflow','no browser exceptions']};
 await fs.writeFile(output+'/browser-results.json',JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
}finally{
 if(customId)await mutate({action:'remove',id:customId}).catch(()=>{});
 if(arrivalOriginal!==undefined)await mutate({action:'toggle',id:'visitor-cards',done:arrivalOriginal}).catch(()=>{});
 await browser.close();
}
