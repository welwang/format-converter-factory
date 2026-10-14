const fs=require('fs'),path=require('path');
const {chromium}=require('C:/Users/wel30/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const root=__dirname,schema=JSON.parse(fs.readFileSync(path.join(root,'scratch/tool-schema.json'),'utf8'));
 const browser=await chromium.launch({headless:true}),page=await browser.newPage({viewport:{width:1366,height:900},reducedMotion:'reduce'});
 const errors=[],results=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('file:///'+path.join(root,'src/ui/index.html').replaceAll('\\','/'));
 await page.evaluate(schema=>{
  globalThis.testCalls=[];globalThis.testJobs=[];
  API={save_settings:async()=>true,drives:async()=>[],status:async()=>({jobs:testJobs,rec:{rec:false},busy:false}),rec_state:async()=>({rec:false}),open_file:async p=>testCalls.push(['open_file',p]),reveal:async p=>testCalls.push(['reveal',p]),open_doc:async p=>testCalls.push(['open_doc',p]),
   pdf_preview:async(p,n)=>({src:'data:image/svg+xml;base64,'+btoa('<svg xmlns="http://www.w3.org/2000/svg" width="400" height="600"><rect width="400" height="600" fill="white"/><text x="30" y="60">Offline test</text></svg>'),w:400,h:600,page:n,count:3,forms:[]})};
  S={tab:'pdfhub',theme:'light',preset:'balanced',finish:'sound',tool_opts:{}};TS=schema;PC={ram:4,cores:2};go('pdfhub');PDFUI.init();
 },schema);
 for(const t of schema.tools){
  const detail=await page.evaluate(async id=>{
   const item=TS.tools.find(t=>t.id===id);go(item.group);pickTool(id);
   let variants=1;
   for(const f of item.fields.filter(f=>f.type==='select')){
    for(const [value] of f.options){TV[f.k]=value;renderForm();variants++;}
    TV[f.k]=f.default;
   }
   renderForm();await new Promise(r=>setTimeout(r,0));
   if($('#t_name').textContent!==item.name)throw Error('Tool name mismatch: '+id);
   if($('#t_form').innerHTML.includes('undefined'))throw Error('Undefined form: '+id);
   return {name:id,ok:true,variants};
  },t.id);results.push(detail);
 }
 await page.evaluate(()=>go('pdfhub'));await page.screenshot({path:path.join(root,'ui-pdf-catalogue.png')});
 if(await page.locator('.pdf-card').count()!==schema.pdf.catalogue.length)throw Error('PDF catalogue count mismatch');
 await page.keyboard.press('Control+f');if(await page.locator('#gsearch').evaluate(e=>e!==document.activeElement))throw Error('Search focus');await page.keyboard.press('Escape');results.push({name:'keyboard_search_escape',ok:true});
 await page.evaluate(()=>{testJobs=[{id:'test',name:'本機影片',kind:'dl',label:'下載：測試',target:'mp4',state:'done',output:'C:\\測試 資料\\完成影片.mp4',progress:1,elapsed:3,out_size:1000}];return poll()});
 await page.locator('#queue [data-f]').click();await page.locator('#queue [data-o]').click();
 const calls=await page.evaluate(()=>testCalls);if(!calls.some(c=>c[0]==='open_file')||!calls.some(c=>c[0]==='reveal'))throw Error('Completed job buttons');results.push({name:'open_and_reveal_buttons',ok:true});
 await page.evaluate(()=>about(false));await page.locator('[data-doc="tests"]').click();if(!await page.evaluate(()=>testCalls.some(c=>c[0]==='open_doc'&&c[1]==='tests')))throw Error('Test report button');await page.locator('#aok').click();results.push({name:'offline_report_button',ok:true});
 await page.evaluate(async()=>{go('pdf');pickTool('p_edit');tfiles=[{path:'synthetic.pdf',name:'合成 PDF.pdf',cat:'pdf',size:100}];TV.actions=[];await PDFUI.open('p_edit')});
 await page.waitForSelector('#pdf_pageimage');await page.locator('#pdf_pageimage').evaluate(i=>i.decode());
 const box=await page.locator('#pdf_paper').boundingBox();await page.locator('#pdf_edittext').fill('Added text');
 await page.mouse.move(box.x+box.width*.1,box.y+box.height*.2);await page.mouse.down();await page.mouse.move(box.x+box.width*.8,box.y+box.height*.3,{steps:8});await page.mouse.up();await page.locator('#pdf_addaction').click();
 await page.screenshot({path:path.join(root,'ui-pdf-editor.png')});await page.locator('#pdf_editor_apply').click();
 if(!await page.evaluate(()=>TV.actions.length===1&&TV.actions[0].text==='Added text'&&Math.abs(TV.actions[0].rect[0]-.1)<.02))throw Error('Visual editor selection');results.push({name:'pdf_drag_text_action',ok:true});
 for(const [width,height] of [[1024,768],[1366,900],[1920,1080]]){
  await page.setViewportSize({width,height});await page.evaluate(()=>go('pdfhub'));
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);if(overflow)throw Error('Horizontal page overflow '+width);results.push({name:'viewport_'+width,ok:true});
 }
 for(const mode of ['dark','light']){await page.evaluate(m=>{S.theme=m;theme()},mode);await page.screenshot({path:path.join(root,'ui-'+mode+'.png')});results.push({name:'theme_'+mode,ok:true});}
 const logo=await page.locator('img[src="logo.png"]').first().evaluate(i=>i.complete&&i.naturalWidth>0);if(!logo)throw Error('Logo failed to load');results.push({name:'logo_loaded',ok:true});
 if(errors.length)throw Error(errors.join('\n'));results.push({name:'javascript_no_errors',ok:true});
 fs.writeFileSync(path.join(root,'ui-results.json'),JSON.stringify(results,null,2));await browser.close();console.log('PASSED',results.length,'/',results.length,'form variants',results.reduce((n,r)=>n+(r.variants||0),0));
})().catch(e=>{console.error(e);process.exit(1)});
