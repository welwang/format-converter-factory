/* SPDX-License-Identifier: AGPL-3.0-only; Copyright (c) 2026 Wel Wang */
/* Own offline PDF workspace. Uses only the application's local desktop bridge. */
globalThis.PDFUI=(()=>{
 let doc=null,pending=null,actions=[],pointer=null,revision=0,cache=new Map(),formValues={},activeTool='';
 const names={text:'文字',image:'圖片',rectangle:'矩形',highlight:'螢光標記',draw:'手繪',signature:'手寫簽名',redact:'永久遮蔽',field_text:'文字欄位',field_checkbox:'核取方塊',field_choice:'下拉單選',field_list:'清單欄位',date:'日期'};
 const edits=new Set(['p_edit','p_sign','p_forms','p_redact','p_crop']);
 function init(){
  if(!TS?.pdf)return;
  const cap=TS.pdf;$('#pdf_status').innerHTML=[['ocr','離線 OCR'],['ai','離線 AI 模型'],['pdfa','本機 PDF/A'],['office','Office 轉換']].map(([k,n])=>`<span>${n}：${cap[k]?'已備妥':'元件未包含'}</span>`).join('');
  const term=$('#pdf_search').value.trim().toLowerCase();const colours={'整理':'var(--orange)','優化':'var(--green)','轉成 PDF':'var(--blue)','從 PDF 轉換':'var(--teal)','編輯':'var(--purple)','安全':'var(--indigo)','智慧':'var(--pink)','更多':'var(--gray)'};
  $('#pdf_catalog').innerHTML=cap.sections.map(section=>{const list=cap.catalogue.filter(t=>t.section==section&&(!term||(t.name+' '+t.description).toLowerCase().includes(term)));return list.length?`<div class="pdf-section"><h2>${esc(section)}</h2><div class="pdf-tools">${list.map(t=>`<button class="pdf-card" data-pdf-tool="${esc(t.id)}">${tile('pdf',colours[section],'md')}<span><b>${esc(t.name)}</b><small>${esc(t.description)}</small></span></button>`).join('')}</div></div>`:''}).join('');
 }
 function use(id){if(id=='workflow'){go('workflow');$('#wf_recipe').value='pipeline';wfMode();return}go('pdf');pickTool(id)}
 function typeOptions(){
  const allowed=activeTool=='p_redact'?['redact']:activeTool=='p_forms'?['field_text','field_checkbox','field_choice','field_list']:activeTool=='p_sign'?['signature','text','date','image']:activeTool=='p_crop'?['rectangle']:['text','image','rectangle','highlight','draw'];
  $('#pdf_kind').innerHTML=allowed.map(k=>`<option value="${k}">${names[k]}</option>`).join('');
 }
 async function open(id){
  if(!tfiles.length||tfiles[0].cat!='pdf'){toast('請先加入 PDF 文件',1);return}
  if(tfiles.length>1){toast('視覺編輯請一次處理一份 PDF',1);return}
  activeTool=id;actions=Array.isArray(TV.actions)?JSON.parse(JSON.stringify(TV.actions)):[];formValues={};pending=null;cache.clear();revision++;
  doc={path:tfiles[0].path,pw:TV.pw||'',page:Math.max(1,+TV.preview_page||1),count:1,w:1,h:1};typeOptions();
  $('#pdf_editor_title').textContent=tool.name+' · '+tfiles[0].name;$('#pdf_editor').classList.add('on');$('#pdf_editor').setAttribute('aria-hidden','false');
  $('#pdf_edittext').value='';$('#pdf_editor_tip').textContent=id=='p_forms'?'框選建立欄位，或在右側填寫既有欄位。自動偵測請關閉工作台後選擇偵測模式。':id=='p_sign'?'選擇手寫簽名後在頁面直接畫。憑證簽章請使用獨立工具。':id=='p_redact'?'框選的是待移除範圍，尚未修改文件；儲存前會再次要求確認。':id=='p_crop'?'框選保留的頁面範圍。裁切不能代替永久遮蔽。':'選擇工具後，在頁面拖拉範圍；文字與圖片使用「加入項目」。';
  try{await page(doc.page)}catch(e){close()}
 }
 async function page(number){
  if(!doc)return;const rev=++revision;pending=null;$('#pdf_editor_body').classList.add('pdf-loading');
  try{let result=cache.get(number);if(!result){result=await call('pdf_preview',doc.path,number,doc.pw);cache.set(result.page,result);while(cache.size>3)cache.delete(cache.keys().next().value)}
   if(rev!==revision||!doc)return;Object.assign(doc,{page:result.page,count:result.count,w:result.w,h:result.h,forms:result.forms});$('#pdf_page').value=doc.page;$('#pdf_count').textContent='/ '+doc.count;$('#pdf_page').max=doc.count;$('#pdf_pageimage').src=result.src;$('#pdf_prev').disabled=doc.page<=1;$('#pdf_next').disabled=doc.page>=doc.count;render();
  }finally{if(rev===revision)$('#pdf_editor_body').classList.remove('pdf-loading')}
 }
 function outline(a,preview=false){const n=a.rect||[0,0,0,0],r=[n[0]*doc.w,n[1]*doc.h,n[2]*doc.w,n[3]*doc.h],ink=esc(a.color||'#007AFF'),line=+(a.width||1.5);
  if(a.kind=='draw'||a.kind=='signature'){return `<polyline points="${(a.points||[]).map(p=>[p[0]*doc.w,p[1]*doc.h].join(',')).join(' ')}" fill="none" stroke="${ink}" stroke-width="${line}" stroke-linecap="round" stroke-linejoin="round"/>`}
  let display='';if(a.kind=='text'||a.kind=='date')display=`<text x="${r[0]+1}" y="${r[1]+(+a.size||12)}" font-size="${(+a.size||12)}" fill="${ink}" style="line-height:1;letter-spacing:normal">${esc(a.text||new Date().toLocaleDateString('sv'))}</text>`;
  if(a.preview?.startsWith('data:image/'))display=`<image x="${r[0]}" y="${r[1]}" width="${r[2]}" height="${r[3]}" href="${a.preview}" preserveAspectRatio="xMidYMid meet"/>`;
  const fill=a.kind=='redact'?'#0008':a.kind=='highlight'?ink+'44':'transparent';
  return `<rect x="${r[0]}" y="${r[1]}" width="${r[2]}" height="${r[3]}" fill="${fill}" stroke="${ink}" stroke-width="1" stroke-dasharray="${preview?4:0}"/>`+display;
 }
 function render(){
  if(!doc)return;$('#pdf_overlay').setAttribute('viewBox',`0 0 ${doc.w} ${doc.h}`);$('#pdf_overlay').innerHTML=actions.filter(a=>a.page==doc.page).map(a=>outline(a)).join('')+(pending?outline(pending,true):'');
  $('#pdf_actions').innerHTML=actions.length?actions.map((a,i)=>`<div class="pdf-action"><div class="row"><span class="lab">${esc(names[a.kind]||a.kind)} · 第 ${a.page} 頁</span><button class="btn icon" data-pdf-remove="${i}" aria-label="移除項目">${svg('x')}</button></div><small class="mute">${esc(a.text||a.name||a.file?.split(/[\\/]/).pop()||'')}</small></div>`).join(''):'<div class="empty">尚未加入項目</div>';
  $('#pdf_addaction').disabled=!pending;$('#pdf_undo').disabled=!actions.length;$('#pdf_action_count').textContent=actions.length+' 個項目';
  const widgets=doc.forms||[];$('#pdf_existing').innerHTML=activeTool=='p_forms'&&widgets.length?'<div class="ghead">既有表單欄位</div>'+widgets.map((w,i)=>`<label class="pdf-action" style="display:block"><span>${esc(w.name)}</span>${w.type=='CheckBox'||w.type=='RadioButton'?`<input type="checkbox" data-pdf-field="${i}" ${(formValues[w.name]??w.value) && (formValues[w.name]??w.value)!='Off'?'checked':''}>`:w.choices.length?`<select data-pdf-field="${i}">${w.choices.map(v=>`<option ${v==(formValues[w.name]??w.value)?'selected':''}>${esc(v)}</option>`).join('')}</select>`:`<input type="text" data-pdf-field="${i}" value="${esc(formValues[w.name]??w.value??'')}">`}</label>`).join(''):'';
 }
 function point(e){const bounds=$('#pdf_paper').getBoundingClientRect();return [Math.max(0,Math.min(1,(e.clientX-bounds.left)/bounds.width)),Math.max(0,Math.min(1,(e.clientY-bounds.top)/bounds.height))]}
 function down(e){if(!doc||e.button!==0)return;e.preventDefault();const p=point(e);pointer={first:p,kind:$('#pdf_kind').value};pending={kind:pointer.kind,page:doc.page,rect:[p[0],p[1],0,0],normalized:true,color:$('#pdf_ink').value,size:+$('#pdf_textsize').value||12,width:+$('#pdf_penwidth').value||1.5};if(['draw','signature'].includes(pointer.kind))pending.points=[p];$('#pdf_overlay').setPointerCapture(e.pointerId);render()}
 function move(e){if(!pointer||!pending)return;const p=point(e);if(pending.points){if(pending.points.length<5000)pending.points.push(p)}else pending.rect=[Math.min(pointer.first[0],p[0]),Math.min(pointer.first[1],p[1]),Math.abs(pointer.first[0]-p[0]),Math.abs(pointer.first[1]-p[1])];render()}
 function up(){if(!pointer||!pending)return;pointer=null;if(pending.points){
   if(pending.points.length<2){pending=null;render();return}const xs=pending.points.map(p=>p[0]),ys=pending.points.map(p=>p[1]);pending.rect=[Math.min(...xs),Math.min(...ys),Math.max(.005,Math.max(...xs)-Math.min(...xs)),Math.max(.005,Math.max(...ys)-Math.min(...ys))];
   pending.kind='draw';actions.push(pending);pending=null;render();return
  }if(pending.rect[2]<.005||pending.rect[3]<.005)pending=null;render()}
 async function add(){
  if(!pending)return;const action=JSON.parse(JSON.stringify(pending));
  if(['text','date'].includes(action.kind)){action.text=action.kind=='date'?new Date().toLocaleDateString('sv'):$('#pdf_edittext').value;if(!action.text.trim()){toast('請輸入文字',1);return}}
  else if(action.kind=='image'){const file=await call('pick_file','圖片 (*.png;*.jpg;*.webp)');if(!file)return;action.file=file;action.preview=(await call('preview',file)).src}
  else if(action.kind.startsWith('field_')){action.name=$('#pdf_edittext').value.trim();if(!action.name){toast('請輸入欄位名稱',1);return}action.field_type=action.kind.slice(6);action.value='';if(['choice','list'].includes(action.field_type))action.choices=$('#pdf_choices').value.split(',').map(s=>s.trim()).filter(Boolean)}
  actions.push(action);pending=null;render();
 }
 function close(){revision++;doc=null;pointer=null;pending=null;cache.clear();$('#pdf_editor').classList.remove('on');$('#pdf_editor').setAttribute('aria-hidden','true')}
 function apply(){
  if(!doc)return;const cleaned=actions.map(({preview,...a})=>a);
  if(activeTool=='p_crop'){
   const crop=actions.filter(a=>a.page==doc.page).at(-1)||pending;if(!crop){toast('請先框選保留範圍',1);return}
   TV.mode='rect';TV.rect=[crop.rect[0]*doc.w,crop.rect[1]*doc.h,crop.rect[2]*doc.w,crop.rect[3]*doc.h].join(',');TV.preview_page=doc.page;
  }else if(activeTool=='p_forms'){
   if(cleaned.length){TV.mode='create';TV.actions=cleaned}else if(Object.keys(formValues).length){TV.mode='fill';TV.actions=Object.entries(formValues).map(([name,value])=>({name,value}))}else{toast('請加入欄位或填寫既有欄位',1);return}
  }else{
   if(!cleaned.length){toast('請先加入項目',1);return}
   TV.actions=cleaned;if(activeTool=='p_redact'){TV.confirmed=false;TV.rect=''}
  }
  close();renderForm();toast('編輯項目已套用；按「開始」產生新檔');
 }
 function notes(list){$('#pdf_result_notes').innerHTML=list.map(note=>`<li>${esc(note)}</li>`).join('');$('#pdf_notes_modal').classList.add('on')}
 $('#pdf_catalog').onclick=e=>{const button=e.target.closest('[data-pdf-tool]');if(button)use(button.dataset.pdfTool)};$('#pdf_search').oninput=init;
 $('#pdf_alltools').onclick=()=>go('pdf');$('#pdf_editor_close').onclick=close;$('#pdf_editor_apply').onclick=apply;
 $('#pdf_prev').onclick=()=>page(doc.page-1).catch(()=>{});$('#pdf_next').onclick=()=>page(doc.page+1).catch(()=>{});$('#pdf_page').onchange=()=>page(+$('#pdf_page').value||1).catch(()=>{});
 $('#pdf_kind').onchange=()=>{pending=null;$('#pdf_choices').style.display=['field_choice','field_list'].includes($('#pdf_kind').value)?'':'none';render()};
 $('#pdf_overlay').onpointerdown=down;$('#pdf_overlay').onpointermove=move;$('#pdf_overlay').onpointerup=up;$('#pdf_overlay').onpointercancel=()=>{pointer=null;pending=null;render()};
 $('#pdf_addaction').onclick=()=>add().catch(()=>{});$('#pdf_undo').onclick=()=>{actions.pop();render()};$('#pdf_actions').onclick=e=>{const b=e.target.closest('[data-pdf-remove]');if(b){actions.splice(+b.dataset.pdfRemove,1);render()}};
 $('#pdf_existing').onchange=e=>{const i=e.target.dataset.pdfField;if(i!=null){const w=doc.forms[+i];formValues[w.name]=e.target.type=='checkbox'?e.target.checked:e.target.value}};
 $('#pdf_notes_close').onclick=()=>$('#pdf_notes_modal').classList.remove('on');
 $('#pdf_scan_source').onclick=()=>waiting($('#pdf_scan_source'),async()=>{use('p_scan');const files=await call('pdf_scan');addToolFiles(files.map(f=>f.path))});
 $('#pdf_paste_html').onclick=()=>$('#pdf_html_modal').classList.add('on');$('#pdf_html_cancel').onclick=()=>$('#pdf_html_modal').classList.remove('on');
 $('#pdf_html_add').onclick=()=>waiting($('#pdf_html_add'),async()=>{const files=await call('pdf_html',$('#pdf_html_text').value);$('#pdf_html_modal').classList.remove('on');use('p_html_pdf');addToolFiles(files.map(f=>f.path))});
 window.addEventListener('keydown',e=>{if(e.key=='Escape'&&$('#pdf_editor').classList.contains('on')){e.preventDefault();close()}});
 return {init,use,open,notes,edits};
})();
