/* 四維八德 介面程式（原 index.html 內嵌 <script>）。以 window.pywebview.api 呼叫後端。 */
/* ---------- icons (24px line set) ---------- */
const IC={search:'<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',plus:'<path d="M12 5v14M5 12h14"/>',x:'<path d="M18 6 6 18M6 6l12 12"/>',
chev:'<path d="m9 6 6 6-6 6"/>',chevdown:'<path d="m6 9 6 6 6-6"/>',up:'<path d="m6 15 6-6 6 6"/>',down:'<path d="m6 9 6 6 6-6"/>',
convert:'<path d="M20 11a8 8 0 0 0-14.9-3.9M4 4v4h4"/><path d="M4 13a8 8 0 0 0 14.9 3.9M20 20v-4h-4"/>',
video:'<rect x="2.5" y="6" width="13.5" height="12" rx="2.5"/><path d="m16 10.5 5.5-3v9l-5.5-3"/>',audio:'<path d="M4 10v4M8 6.5v11M12 3.5v17M16 7.5v9M20 10v4"/>',
image:'<rect x="3" y="4" width="18" height="16" rx="3"/><circle cx="9" cy="9.5" r="1.8"/><path d="m21 15.5-4.5-4.5L7 20.5"/>',
pdf:'<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h4"/>',
disc:'<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="2.5"/>',cd:'<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="2.5"/><path d="M16.8 7.2A6.5 6.5 0 0 1 18.5 11"/>',
shield:'<path d="M12 3 4.5 6v5.5c0 4.6 3.2 8.2 7.5 9.5 4.3-1.3 7.5-4.9 7.5-9.5V6z"/><path d="m9 12 2 2 4-4"/>',
record:'<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4" fill="currentColor" stroke="none"/>',download:'<path d="M12 3.5v12M7 10.5l5 5 5-5M5 20.5h14"/>',
bolt:'<path d="M13 2.5 4.5 14H11l-1 7.5L18.5 10H12z"/>',phone:'<rect x="7" y="2.5" width="10" height="19" rx="2.5"/><path d="M11 18.5h2"/>',
aspect:'<rect x="7" y="2.5" width="10" height="19" rx="2"/><path d="M3 8v8M21 8v8"/>',crop:'<path d="M6 2v14a2 2 0 0 0 2 2h14"/><path d="M18 22V8a2 2 0 0 0-2-2H2"/>',
rotate:'<path d="M3.5 12a8.5 8.5 0 1 0 2.6-6.1L3.5 8.5"/><path d="M3.5 3.5v5h5"/>',speed:'<path d="m3.5 6 7.5 6-7.5 6zM12.5 6l8 6-8 6z"/>',
textmark:'<path d="M5 7.5V5h14v2.5M12 5v14M9 19h6"/>',logo:'<rect x="3" y="4" width="18" height="16" rx="3"/><rect x="12.5" y="12" width="5" height="4.5" rx="1"/>',
eraser:'<path d="m7 20.5-3.6-3.6a2 2 0 0 1 0-2.8L13.2 4.3a2 2 0 0 1 2.8 0l3.6 3.6a2 2 0 0 1 0 2.8L9.8 20.5zM20.5 20.5H9.8M8.5 9l6.5 6.5"/>',
captions:'<rect x="2.5" y="5" width="19" height="14" rx="3"/><path d="M6.5 12h4M13 12h4.5M6.5 15.5h7"/>',
sparkles:'<path d="M11 3.5 12.9 8.6 18 10.5l-5.1 1.9L11 17.5l-1.9-5.1L4 10.5l5.1-1.9z"/><path d="m18.5 15 .8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8z"/>',
music:'<path d="M9 18V5.5l11.5-2V16"/><circle cx="6" cy="18" r="3"/><circle cx="17.5" cy="16" r="3"/>',mute:'<path d="M11 5 6 9H3v6h3l5 4z"/><path d="m22 9-6 6M16 9l6 6"/>',
scissors:'<circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M20 4 8.1 15.9M14.5 14.5 20 20M8.1 8.1 12 12"/>',
stabilize:'<rect x="6.5" y="6.5" width="11" height="11" rx="2"/><path d="M2.5 9v6M21.5 9v6M9 2.5h6M9 21.5h6"/>',
sliders:'<path d="M4 6h9M17 6h3M4 12h3M11 12h9M4 18h11M19 18h1"/><circle cx="15" cy="6" r="2"/><circle cx="9" cy="12" r="2"/><circle cx="17" cy="18" r="2"/>',
fade:'<circle cx="12" cy="12" r="9"/><path d="M12 3a9 9 0 0 1 0 18z" fill="currentColor" stroke="none"/>',rewind:'<path d="M11 18.5 3 12l8-6.5zM21 18.5 13 12l8-6.5z"/>',
frames:'<path d="M4 7.5h3l2-2.5h6l2 2.5h3a1 1 0 0 1 1 1V18a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V8.5a1 1 0 0 1 1-1z"/><circle cx="12" cy="13" r="3.5"/>',
grid:'<rect x="3" y="3" width="7.5" height="7.5" rx="1.5"/><rect x="13.5" y="3" width="7.5" height="7.5" rx="1.5"/><rect x="3" y="13.5" width="7.5" height="7.5" rx="1.5"/><rect x="13.5" y="13.5" width="7.5" height="7.5" rx="1.5"/>',
volume:'<path d="M11 5 6 9H3v6h3l5 4z"/><path d="M15.5 8.5a5 5 0 0 1 0 7M18.5 5.5a9 9 0 0 1 0 13"/>',pitch:'<path d="M9 3v6a3 3 0 0 0 6 0V3M12 12v9M9 21h6"/>',
mic:'<rect x="9" y="2.5" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3.5M3 3l18 18"/>',wind:'<path d="M3 8h11a3 3 0 1 0-3-3M3 12h15a3 3 0 1 1-3 3M3 16h7"/>',
silence:'<rect x="6" y="5" width="4" height="14" rx="1"/><rect x="14" y="5" width="4" height="14" rx="1"/>',mix:'<path d="M6 4v5M6 13v7M12 4v11M12 19v1M18 4v1M18 9v11M4 11h4M10 17h4M16 7h4"/>',
bell:'<path d="M6 8.5a6 6 0 0 1 12 0c0 6.5 3 8 3 8H3s3-1.5 3-8"/><path d="M10.3 20a2 2 0 0 0 3.4 0"/>',tag:'<path d="M3 12.2V4a1 1 0 0 1 1-1h8.2l8.6 8.6a1 1 0 0 1 0 1.4l-7.8 7.8a1 1 0 0 1-1.4 0z"/><circle cx="7.5" cy="7.5" r="1.4"/>',
resize:'<path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/>',copyright:'<circle cx="12" cy="12" r="9"/><path d="M14.8 9.5a3.5 3.5 0 1 0 0 5"/>',
collage:'<rect x="3" y="3" width="18" height="18" rx="2.5"/><path d="M12 3v18M3 12h9"/>',slideshow:'<rect x="3" y="5" width="18" height="14" rx="2.5"/><path d="m10 9 5 3-5 3z"/>',
gif:'<rect x="3" y="5" width="18" height="14" rx="2.5"/><path d="M3 9h18M3 15h18M8 5v4M16 5v4M8 15v4M16 15v4"/>',
pages:'<rect x="8" y="2.5" width="12" height="15" rx="2"/><path d="M16 21.5H6a2 2 0 0 1-2-2v-12"/>',list:'<path d="M9 6h11M9 12h11M9 18h11"/><circle cx="4.5" cy="6" r=".8"/><circle cx="4.5" cy="12" r=".8"/><circle cx="4.5" cy="18" r=".8"/>',
lock:'<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',unlock:'<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 7.6-1.8"/>',
archive:'<rect x="3" y="4" width="18" height="5" rx="1.5"/><path d="M5 9v9a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V9M10 13h4"/>',folder:'<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
doc:'<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>',book:'<path d="M4 4.5A1.5 1.5 0 0 1 5.5 3H20v15H5.5A1.5 1.5 0 0 0 4 19.5zM4 19.5A1.5 1.5 0 0 0 5.5 21H20v-3"/>',
table:'<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M3 15h18M9 4v16"/>',cube:'<path d="M12 2.5 20.5 7v10L12 21.5 3.5 17V7z"/><path d="M3.5 7 12 11.5 20.5 7M12 11.5v10"/>',
cc:'<rect x="2.5" y="5" width="19" height="14" rx="3"/><path d="M10 10.2a2.5 2.5 0 1 0 0 3.6M17 10.2a2.5 2.5 0 1 0 0 3.6"/>',show:'<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="m10 12 4 0M12 10l2 2-2 2"/>'};
const svg=(k,cls='i')=>`<svg class="${cls}" viewBox="0 0 24 24">${IC[k]||IC.doc}</svg>`;
document.querySelectorAll('svg[data-i]').forEach(s=>{s.setAttribute('viewBox','0 0 24 24');s.innerHTML=IC[s.dataset.i]});
const GC={smart:'var(--purple)',pdfhub:'var(--red)',system:'var(--gray)',workflow:'var(--teal)',convert:'var(--blue)',video:'var(--indigo)',audio:'var(--pink)',image:'var(--green)',pdf:'var(--red)',other:'var(--teal)',disc:'var(--brown)',rec:'var(--red)',dl:'var(--cyan)',auto:'var(--gray)'};
const GI={smart:'sparkles',pdfhub:'pdf',system:'sliders',workflow:'folder',convert:'convert',video:'video',audio:'audio',image:'image',pdf:'pdf',other:'shield',disc:'disc',rec:'record',dl:'download',auto:'bolt'};
const tile=(icon,color,size='')=>`<span class="tile ${size}" style="background:${color}">${svg(icon)}</span>`;
/* ---------- state ---------- */
const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];let PC={},S={},files=[],API,TS=null,tool=null,tfiles=[],TV={},group='video';
const CAT={video:'影片',audio:'音訊',image:'圖片',pdf:'PDF',office:'文件',doc:'文件',sheet:'試算表',ebook:'電子書',archive:'壓縮檔',subtitle:'字幕',model:'3D'};
const CATC={video:'var(--indigo)',audio:'var(--pink)',image:'var(--green)',pdf:'var(--red)',doc:'var(--blue)',office:'var(--blue)',sheet:'#1D9A55',ebook:'var(--purple)',archive:'var(--gray)',subtitle:'var(--teal)',model:'var(--orange)'};
const CATI={video:'video',audio:'audio',image:'image',pdf:'pdf',doc:'doc',office:'doc',sheet:'table',ebook:'book',archive:'archive',subtitle:'cc',model:'cube'};
const TL=t=>t=='extract'?'解壓縮':t.toUpperCase();let FT=[];
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmtSize=b=>b>1<<30?(b/(1<<30)).toFixed(1)+' GB':b>1<<20?(b/(1<<20)).toFixed(1)+' MB':Math.max(1,Math.round(b/1024))+' KB';
const fmtDur=s=>{s=Math.round(s||0);const h=Math.floor(s/3600),m=Math.floor(s%3600/60),x=s%60;return h?`${h}:${String(m).padStart(2,'0')}:${String(x).padStart(2,'0')}`:`${m}:${String(x).padStart(2,'0')}`};
const MI={};async function loadInfo(list,cb){const need=list.filter(f=>(f.cat=='video'||f.cat=='audio')&&!(f.path in MI)).map(f=>f.path);if(!need.length||!API)return;need.forEach(p=>MI[p]=null);
 try{for(let i=0,k=16;i<need.length;i+=k,k=60){const r=await API.media_info(need.slice(i,i+k));Object.assign(MI,r);cb()}}catch(e){need.filter(p=>MI[p]===null).forEach(p=>delete MI[p]);toast('部分媒體資訊無法讀取',1)}}
const miText=p=>{const m=MI[p];if(!m)return'';const q=m.h?(m.h>=2160?'4K':m.h>=1440?'1440p':m.h>=1080?'1080p':m.h>=720?'720p':m.h+'p'):'';return [q,m.dur?fmtDur(m.dur):'',m.hdr?'HDR':''].filter(Boolean).join(' · ')};
const fmtT=s=>s==null?'':s<60?s+' 秒':s<3600?Math.floor(s/60)+' 分 '+(s%60)+' 秒':Math.floor(s/3600)+' 小時 '+Math.floor(s%3600/60)+' 分';
function toast(m,err,act){const t=$('#toast');t.innerHTML=esc(m)+(act?`<button class="btn tint">${esc(act[0])}</button>`:'');t.className='toast on'+(err?' err':'')+(act?' act':'');if(act)t.querySelector('button').onclick=()=>{t.className='toast';act[1]()};clearTimeout(t._t);t._t=setTimeout(()=>t.className='toast',act?7000:err?5000:2400)}
async function call(fn,...a){try{return await API[fn](...a)}catch(e){toast(String(e.message||e).replace(/^.*?Error:\s*/,''),1);throw e}}
let saveTimer;function save(){clearTimeout(saveTimer);saveTimer=setTimeout(()=>{if(API)call('save_settings',S).catch(()=>{})},250)}
function setSeg(id,v){$$(id+' button').forEach(b=>b.classList.toggle('on',b.dataset.v==v))}
const mq=matchMedia('(prefers-color-scheme: dark)');
function theme(){const t=S.theme||'auto';document.body.classList.toggle('dark',t=='dark'||(t=='auto'&&mq.matches));setSeg('#theme',t)}
mq.addEventListener('change',theme);$('#theme').onclick=e=>{const v=e.target.dataset.v;if(v){S.theme=v;theme();save()}};
const sw=(id,on)=>$('#'+id).classList.toggle('on',!!on),isOn=id=>$('#'+id).classList.contains('on');
/* ---------- navigation ---------- */
const PAGES={pdfhub:['PDF 工作台','完整本機工具 · 文件不送到雲端'],system:['電腦工具','健康檢查、硬體資訊與暫存清理'],workflow:['交付工作台','選用途，拿到可交付的成品包'],convert:['轉檔','把任何檔案轉成需要的格式'],rec:['螢幕錄影','錄下整個螢幕或指定範圍'],dl:['下載影片','從網站下載影片或音樂'],auto:['自動化','監控資料夾與完成後動作']};
function navHTML(){if(!TS)return'';const it=(k,name,extra='')=>`<div class="nav ${S.tab==k||(k=='pdfhub'&&S.tab=='pdf')?'on':''}" data-k="${k}" title="${name}">${tile(GI[k],GC[k])}<span>${name}</span>${extra}</div>`;
 const cnt=g=>TS.tools.filter(t=>t.group==g).length;
 return it('workflow','交付工作台')+it('convert','一般轉檔')+'<div class="sb-label">工具</div>'+TS.groups.map(([g,n])=>it(g=='pdf'?'pdfhub':g,g=='pdf'?'PDF 工作台':n.replace('工具',''),`<span class="cnt">${cnt(g)}</span>`)).join('')
  +'<div class="sb-label">更多</div>'+it('rec','螢幕錄影','<i class="live" id="recdot"></i>')+it('dl','下載影片')+it('auto','自動化')+it('system','電腦工具')}
function renderNav(){$('#nav').innerHTML=navHTML();recUI()}
$('#nav').onclick=e=>{const n=e.target.closest('.nav');if(n){$('#gsearch').value='';go(n.dataset.k)}};
function go(k){S.tab=k;const isTool=TS.groups.some(g=>g[0]==k)||k=='search';$$('.page').forEach(p=>p.classList.remove('on'));
 if(isTool){group=k;$('#p-tools').classList.add('on');const gn=k=='search'?['搜尋結果','']:TS.groups.find(g=>g[0]==k);$('#ptitle').textContent=k=='search'?'搜尋結果':gn[1];$('#psub').textContent=k=='search'?'':`${TS.tools.filter(t=>t.group==k).length} 個工具`;renderTList();
  const want=(S.tool_by_group||{})[k];const list=visibleTools();pickTool(list.some(t=>t.id==want)?want:(list[0]||{}).id)}
 else{$('#p-'+k).classList.add('on');$('#ptitle').textContent=PAGES[k][0];$('#psub').textContent=PAGES[k][1];if(k=='rec')recInit();if(k=='auto')autoInit();if(k=='system')systemInit();if(k=='pdfhub')PDFUI.init()}
 renderNav();if(k!='search')save()}
/* 搜尋列也接受白話指令（smart_intent，離線規則解析）：例如「把影片壓到 25MB」「會議錄音整理重點」 */
let INT={q:'',tools:[],convert:null},intTimer;
$('#gsearch').oninput=e=>{const q=e.target.value.trim();if(q){S.tab='search';go('search');clearTimeout(intTimer);intTimer=setTimeout(()=>askIntent(q),220)}else{INT={q:'',tools:[],convert:null};go(group=='search'?'video':group)}};
async function askIntent(q){if(!API||!API.smart_intent)return;let r;try{r=await API.smart_intent(q)}catch(e){return}
 if($('#gsearch').value.trim()!=q||group!='search')return;INT={q,tools:(r&&r.tools)||[],convert:(r&&r.convert)||null};renderTList();const list=visibleTools();if(list.length&&(!tool||!list.some(t=>t.id==tool.id)||INT.tools.length&&INT.tools[0].tool!=tool.id))pickTool(list[0].id)}
function visibleTools(){const q=$('#gsearch').value.trim().toLowerCase();if(group!='search')return TS.tools.filter(t=>t.group==group);
 const smart=INT.q==$('#gsearch').value.trim()?INT.tools.map(x=>TS.tools.find(t=>t.id==x.tool)).filter(Boolean):[];const ids=new Set(smart.map(t=>t.id));
 return smart.concat(TS.tools.filter(t=>!ids.has(t.id)&&(t.name+t.desc).toLowerCase().includes(q)))}
const intentOf=id=>group=='search'&&INT.q==$('#gsearch').value.trim()?INT.tools.find(x=>x.tool==id):null;
/* ---------- convert ---------- */
function addFiles(list){const have=new Set(files.map(f=>f.path));const added=[];list.forEach(f=>{if(!have.has(f.path)){f.target=f.suggest;files.push(f);have.add(f.path);added.push(f)}});render();if(list.length&&!added.length)toast('這些檔案已經在清單裡了');smartSuggest(added)}
/* 智慧建議：依實際內容（HEVC、HDR、透明 PNG、掃描 PDF…）換成更合適的格式並說明原因；使用者改過的不動 */
async function smartSuggest(list){list=list.filter(f=>f.targets&&f.targets.length);if(!list.length||!API||!API.smart_suggest)return;
 for(let i=0;i<list.length;i+=60){const part=list.slice(i,i+60);let r;try{r=await API.smart_suggest(part.map(f=>f.path))}catch(e){return}
  part.forEach(f=>{const x=r&&r[f.path];if(!x)return;f.why=x.why||'';f.tip=x.tip||'';if(x.target&&f.targets.includes(x.target)){f.smart=x.target;if(f.target==f.suggest)f.target=x.target}});render()}}
/* 用途快選：一次設定格式、品質、大小與相關開關 */
const USE={msg:{d:'影片 MP4 720p、小檔案；音訊 M4A；圖片 JPG。',preset:'small',h:'720',tmb:'',v:'mp4',a:'m4a',i:'jpg'},
 mail:{d:'影片壓到 20 MB 內（MP4）；圖片 JPG；文件轉 PDF。',preset:'balanced',h:'0',tmb:'20',v:'mp4',a:'mp3',i:'jpg',doc:'pdf'},
 web:{d:'影片 MP4 高畫質並把音量調到一致的響度；圖片 JPG。',preset:'high',h:'0',tmb:'',v:'mp4',a:'m4a',i:'jpg',loud:true},
 keep:{d:'能直接換封裝就不重新編碼；音訊轉 FLAC 無損；圖片 PNG。',preset:'high',h:'0',tmb:'',v:'mkv',a:'flac',i:'png',fast:true},
 audio:{d:'影片只取出聲音存成 MP3；音訊檔維持建議格式。',preset:'balanced',h:'0',tmb:'',v:'mp3'},
 reset:{d:'已回到每個檔案的建議格式，並清除大小、片段與畫面高度。',preset:'balanced',h:'0',tmb:''}};
$('#uses').onclick=e=>{const b=e.target.closest('[data-use]');if(!b)return;const k=b.dataset.use,u=USE[k];
 S.preset=u.preset;presetUI();$('#h').value=u.h;$('#tmb').value=u.tmb;if(k=='reset'){$('#ts').value='';$('#te').value=''}
 if(u.loud!==undefined||k=='reset'){S.loudnorm=!!u.loud;sw('loudnorm',S.loudnorm)}if(u.fast||k=='reset'){S.fastcopy=true;sw('fastcopy',true)}
 let n=0;files.forEach(f=>{const want=k=='reset'?(f.smart||f.suggest):f.cat=='video'?u.v:f.cat=='audio'?u.a:f.cat=='image'?u.i:['doc','sheet','office'].includes(f.cat)?u.doc:null;if(want&&f.targets.includes(want)&&f.target!=want){f.target=want;n++}});
 $$('#uses button').forEach(x=>x.classList.toggle('on',x==b&&k!='reset'));$('#usedesc').textContent=u.d;$('#alltarget').value='';render();save();toast(k=='reset'?'已清除調整':`已套用「${b.firstChild.textContent}」`+(n?`，${n} 個檔案改了格式`:''))};
$('#applysmart').onclick=()=>{let n=0;files.forEach(f=>{const t=f.smart||f.suggest;if(t&&f.target!=t&&f.targets.includes(t)){f.target=t;n++}});$('#alltarget').value='';render();toast(n?`已套用 ${n} 個建議`:'已經是建議格式')};
/* 依清單內容只顯示用得到的選項 */
function ctxUI(){const has=c=>files.some(f=>c.includes(f.cat)),any=files.length>0,media=has(['video','audio']),video=has(['video']);
 const set=(el,on)=>{const r=el&&el.closest('.row');if(r)r.classList.toggle('ctx-off',any&&!on)};
 set($('#tmb'),media||has(['image']));set($('#ts'),media);set($('#h'),video||has(['image']));set($('#hw'),video);set($('#fastcopy'),media);set($('#loudnorm'),media);
 const cats=new Set(files.map(f=>f.cat));set($('#merge'),files.length>1&&(cats.size==1||[...cats].every(c=>c=='image'||c=='pdf')));
 set($('#codec'),video);set($('#verify_full'),media)}
window.onDropped=(list,raw)=>{if($('#p-tools').classList.contains('on')&&tool)addToolFiles(raw);else{if(S.tab=='workflow'){wfAdd(list);return}if(S.tab!='convert')go('convert');addFiles(list);if(!list.length)toast('沒有可以轉換的檔案',1)}};
function render(){const el=$('#files');
 el.innerHTML=files.length?files.slice(0,200).map((f,i)=>`<div class="row ic">${tile(CATI[f.cat]||'doc',CATC[f.cat]||'var(--gray)','md')}<span class="lab"><span class="nm" title="${esc(f.path)}" style="display:block">${esc(f.name)}</span><small>${CAT[f.cat]||''} · ${fmtSize(f.size)}${miText(f.path)?' · '+miText(f.path):''}${f.note?' · <span class="warn">'+esc(f.note)+'</span>':''}</small>${f.why?`<small class="why" title="${esc(f.why)}">建議：${esc(f.why)}${f.smart&&f.target!=f.smart?`（建議 ${esc(TL(f.smart))}）`:''}</small>`:''}</span>
  <span class="val">${f.targets.length?`<span class="mute small">轉成</span><select data-i="${i}" style="width:110px">${f.targets.map(t=>`<option ${t==f.target?'selected':''} value="${t}">${TL(t)}</option>`).join('')}</select>`:`<span class="warn small">${f.note?'不支援':'缺少元件'}</span>`}
  <button class="btn icon" data-r="${i}" title="移除">${svg('x')}</button></span></div>`).join('')+(files.length>200?`<div class="more">還有 ${files.length-200} 個檔案沒有列出，轉檔時會一併處理</div>`:''):'<div class="empty">還沒有加入檔案<br><span class="mute small">拖進來後會依內容自動建議格式，也可以在右側選「用途快選」</span></div>';
 const byCat={};let tot=0,dur=0;files.forEach(f=>{byCat[f.cat]=(byCat[f.cat]||0)+1;tot+=f.size||0;const m=MI[f.path];if(m&&m.dur)dur+=m.dur});
 $('#fsum').innerHTML=files.length?Object.entries(byCat).map(([c,n])=>`<span class="pill">${esc(CAT[c]||c)} ${n}</span>`).join('')+`<span class="pill">${fmtSize(tot)}</span>`+(dur?`<span class="pill">共 ${fmtDur(dur)}</span>`:''):'';
 $('#applysmart').style.display=files.some(f=>(f.smart||f.suggest)&&f.target!=(f.smart||f.suggest))?'':'none';ctxUI();
 const all=new Set();files.forEach(f=>f.targets.forEach(t=>all.add(t)));$('#alltarget').innerHTML='<option value="">每個檔案用建議格式</option>'+[...all].map(t=>`<option value="${t}">全部轉成 ${TL(t)}</option>`).join('');
 const n=files.filter(f=>f.targets.length).length;$('#go').disabled=!n;$('#go').textContent=n>1?`轉檔 ${n} 個檔案`:'開始轉檔';
 $('#gohint').innerHTML=n?'按 <kbd>Ctrl</kbd> <kbd>Enter</kbd> 開始':files.length?'清單中的檔案都無法轉換':'加入檔案後即可開始';loadInfo(files,render)}
$('#files').addEventListener('change',e=>{if(e.target.dataset.i)files[e.target.dataset.i].target=e.target.value});
$('#files').addEventListener('click',e=>{const b=e.target.closest('[data-r]');if(b){files.splice(+b.dataset.r,1);render()}});
$('#alltarget').onchange=e=>{const v=e.target.value;files.forEach(f=>{f.target=v&&f.targets.includes(v)?v:f.suggest});render();$('#alltarget').value=v};
let dragN=0;const ov=$('#dropov');
document.addEventListener('dragenter',e=>{e.preventDefault();if(dragN++==0){const tp=$('#p-tools').classList.contains('on')&&tool;$('#dropt').textContent=tp?`放開以加入到「${tool.name}」`:'放開以加入要轉檔的檔案';
 $('#drops').textContent=tp?`可以使用：${tool.accept.map(a=>ACC[a]).join('、')}`:'影片、音訊、圖片、文件、電子書、壓縮檔都可以，資料夾也行';ov.classList.add('on')}});
document.addEventListener('dragover',e=>e.preventDefault());
document.addEventListener('dragleave',e=>{e.preventDefault();if(--dragN<=0){dragN=0;ov.classList.remove('on')}});
document.addEventListener('drop',e=>{e.preventDefault();dragN=0;ov.classList.remove('on')});
$('#addf').onclick=async()=>addFiles(await call('pick_files'));$('#addf').title='Ctrl+O';
$('#addd').onclick=async()=>{const r=await call('pick_folder','add');if(r)addFiles(r)};
$('#clr').onclick=()=>{const old=files;files=[];render();if(old.length)toast('已移除檔案',false,['復原',()=>{files=old;render()}])};
const PD={high:'畫質優先，檔案較大；適合保存與剪輯。',balanced:'畫質與大小兼顧，大部分情況建議用這個。',small:'檔案最小，適合傳訊息、寄信；畫質略降。'};
function presetUI(){setSeg('#preset',S.preset);$('#presetdesc').textContent=PD[S.preset]||''}
$('#preset').onclick=e=>{if(e.target.dataset.v){S.preset=e.target.dataset.v;presetUI();save()}};
$('#outmode').onclick=async e=>{const v=e.target.dataset.v;if(!v)return;if(v=='custom'&&!S.out_dir||v=='custom'&&e.target.classList.contains('on')){const p=await call('pick_folder','out');if(p)S.out_dir=p;else if(!S.out_dir)return}S.out_mode=v;outUI();save()};
$('#outdir').onclick=()=>$('#outmode button[data-v=custom]').click();
function outUI(){setSeg('#outmode',S.out_mode);$('#outdir').innerHTML=S.out_mode=='custom'?esc(S.out_dir)+'　<span style="color:var(--blue)">更換…</span>':'存在原檔案旁邊，永遠不會覆蓋原檔。'}
['merge','hw','fastcopy','loudnorm'].forEach(id=>$('#'+id).onclick=()=>{$('#'+id).classList.toggle('on');const k={hw:'hwaccel',fastcopy:'fastcopy',loudnorm:'loudnorm'}[id];if(k){S[k]=isOn(id);save()}});
$('#go').onclick=async()=>{const ts=parseFloat($('#ts').value)||0,te=parseFloat($('#te').value)||0;
 if(te&&te<=ts){toast('「結束秒」要大於「開始秒」',1);$('#te').focus();return}if((parseFloat($('#tmb').value)||0)<0){toast('目標大小不能是負數',1);return}
 const opt={preset:S.preset,target_mb:$('#tmb').value,trim_start:$('#ts').value,trim_end:$('#te').value,height:$('#h').value,hwaccel:S.hwaccel,fastcopy:S.fastcopy,loudnorm:S.loudnorm,out_dir:S.out_mode=='custom'?S.out_dir:'',codec:S.codec||'auto',verify_full:!!S.verify_full,resource_mode:S.resource_mode||'auto'};
 const items=files.filter(f=>f.target&&f.targets.length).map(f=>({path:f.path,target:f.target}));await call('start',items,opt,isOn('merge'));toast(`已加入 ${items.length} 個工作`);files=[];render();poll()};
/* ---------- activity ---------- */
$('#queue').onclick=async e=>{const b=e.target.closest('button');if(!b)return;if(b.dataset.preview)waiting(b,async()=>{const r=await call('compare_job',b.dataset.preview);$('#comparebefore').src=r.before.src;$('#compareafter').src=r.after.src;$('#comparebeforeinfo').textContent=r.before.w+' × '+r.before.h;$('#compareafterinfo').textContent=r.after.w+' × '+r.after.h;$('#comparecheck').textContent=r.validation;$('#comparemodal').classList.add('on');$('#compareclose').focus()});if(b.dataset.c)call('cancel',b.dataset.c).catch(()=>{});if(b.dataset.o)waiting(b,()=>call('reveal',b.dataset.o));if(b.dataset.f)waiting(b,()=>call('open_file',b.dataset.f));if(b.dataset.notes)PDFUI.notes(JSON.parse(b.dataset.notes));
 if(b.dataset.rt){await call('retry',b.dataset.rt);lastQ='';poll()}};
$('#queue').ondblclick=e=>{const b=e.target.closest('.q');const f=b&&b.querySelector('[data-f]');if(f)call('open_file',f.dataset.f).catch(()=>{})};
function sizeDelta(j){if(!j.out_size||!j.in_size||j.kind=='rec'||j.kind=='dl')return j.out_size&&j.kind?fmtSize(j.out_size)+'　':'';const d=(j.out_size-j.in_size)/j.in_size;
 return `${fmtSize(j.in_size)} → ${fmtSize(j.out_size)}${Math.abs(d)>=0.01?`（<span class="${d<0?'save':''}">${d<0?'−':'+'}${Math.abs(d*100).toFixed(0)}%</span>）`:''}　`}
$('#openlog').onclick=async()=>{let ok=false;try{ok=await API.open_issue()}catch(e){}if(!ok)toast('無法開啟瀏覽器，請到 github.com/welwang/format-converter-factory/issues 提出問題',1)};
function about(welcome){$('#awel').style.display=welcome?'':'none';$('#aok').textContent=welcome?'開始使用':'完成';$('#amodal').classList.add('on')}
$('#sbhead').onclick=()=>about(false);$('#aok').onclick=()=>{$('#amodal').classList.remove('on');if(!S.welcomed){S.welcomed=true;save()}};
$('#amodal .links').onclick=e=>{const d=e.target.dataset.doc;if(!d)return;if(d=='log')call('open_log');else call('open_doc',d)};
$('#cancelall').onclick=()=>API.cancel_all();$('#cleardone').onclick=async()=>{await API.clear_done();lastQ='';poll()};
$('#amin').onclick=()=>{$('#activity').classList.toggle('min');S.qmin=$('#activity').classList.contains('min');$('#amin').style.transform=S.qmin?'rotate(180deg)':'';save()};
$('#finsel').onchange=e=>{S.finish=e.target.value;setSeg('#finish',S.finish);save();if(S.finish=='shutdown')toast('全部完成後會倒數 2 分鐘關機')};
$('#finish').onclick=e=>{const v=e.target.dataset.v;if(v){S.finish=v;setSeg('#finish',v);$('#finsel').value=v;save()}};
$('#noshut').onclick=async()=>{await API.cancel_shutdown();toast('已取消關機')};
const SN={partial:'部分完成',queued:'等待中',running:'處理中',done:'完成',error:'失敗',cancelled:'已取消'};
const KC=j=>j.kind=='health_check'?['sliders','var(--green)']:j.kind=='hardware_test'?['sliders','var(--gray)']:j.kind=='workflow'?['folder','var(--teal)']:j.kind=='rec'?['record','var(--red)']:j.kind=='dl'?['download','var(--cyan)']:j.kind?[(TS&&TS.tools.find(t=>t.id==j.kind)||{}).icon||'sliders',GC[(TS&&TS.tools.find(t=>t.id==j.kind)||{}).group]||'var(--gray)']:['convert','var(--blue)'];
let lastQ='',busy=false,recState={},seen={},wasBusy=false,shownHw='';
$('#sys_result').onclick=e=>{const b=e.target.closest('[data-hwopen]');if(b)waiting(b,()=>call('open_file',b.dataset.hwopen))};
let polling=false;async function poll(){if(polling||!API)return;polling=true;try{const r=await API.status();if(r.finish){S.finish=r.finish;setSeg('#finish',S.finish)}const js=r.jobs;recState=r.rec||{};busy=r.busy??js.some(j=>j.state=='queued'||j.state=='running');recUI();$('#noshut').style.display=r.shutdown?'':'none';
 if(S.finish!==undefined&&$('#finsel').value!=S.finish)$('#finsel').value=S.finish;
 if(busy&&!wasBusy&&$('#activity').classList.contains('min'))$('#amin').click();
 if(wasBusy&&!busy){const all=js.filter(j=>j.finished&&Date.now()/1000-j.finished<120);const ok=all.filter(j=>j.state=='done'),bad=all.filter(j=>j.state=='error'||j.state=='partial');
  if(bad.length)toast(`${bad.length} 個工作失敗，詳細原因在下方`,1);
  else if(ok.length){const saved=ok.reduce((a,j)=>a+(j.in_size&&j.out_size&&!j.kind?Math.max(0,j.in_size-j.out_size):0),0);const last=ok[ok.length-1];
   toast(`全部完成（${ok.length} 個）${saved>1<<20?'，省下 '+fmtSize(saved):''}`,0,last.output?['顯示位置',()=>API.reveal(last.output)]:null)}}
 wasBusy=busy;
 hcWatch(js);
 const hw=[...js].reverse().find(j=>j.kind=='hardware_test'&&(j.state=='done'||j.state=='partial'));
 if(hw&&hw.id!=shownHw){shownHw=hw.id;const box=$('#sys_result');box.style.display='';box.innerHTML=`<div class="row"><b class="lab">${esc(hw.validation||'硬體短測完成')}</b><button class="btn plain" data-hwopen="${esc(hw.output)}">開啟報告</button></div>`+(hw.notes||[]).filter(l=>!/^【|^說明/.test(l)).map(l=>`<div class="row"><span class="lab" style="white-space:normal">${esc(l)}</span></div>`).join('')}
 const key=JSON.stringify(js);if(key==lastQ)return;lastQ=key;const act=r.active??js.filter(j=>j.state=='queued'||j.state=='running').length;
 $('#qcount').textContent=act?`${act} 個進行中`:js.length?(js.some(j=>j.state=='error'||j.state=='partial')?'有工作需要檢查':'全部完成'):'';
 $('#queue').innerHTML=js.length?js.slice(-100).reverse().map(j=>{const rec=j.kind=='rec'&&j.state=='running';const [ic,col]=KC(j);
  const title=j.kind=='dl'?esc(j.label.replace(/^下載：/,'')||j.name):j.kind=='rec'?'螢幕錄影':`${esc(j.name)}<span class="mute"> → ${esc(j.label||TL(j.target))}</span>`;
  const sub=j.state=='running'?(rec?`<span class="err">● ${esc(j.speed)}</span>　${esc(j.msg)}`:[`${(j.progress*100).toFixed(0)}%`,j.speed,j.eta!=null&&j.progress>0.01?'剩 '+fmtT(j.eta):'',j.encoder].filter(Boolean).map(esc).join('　'))
   :(j.state=='done'||j.state=='partial')?`<span class="${j.state=='partial'?'warn':'ok'}">${j.state=='partial'?'部分完成':'完成'}</span>　${sizeDelta(j)}${fmtT(Math.round(j.elapsed))||'不到 1 秒'}${j.validation?'　'+esc(j.validation):''}${j.state=='partial'?'　'+esc(j.msg):''}${j.encoder?'　'+esc(j.encoder):''}`:j.state=='error'?`<span class="err">${esc(j.msg)}</span>`:j.state=='queued'&&j.msg?esc(j.msg):SN[j.state];
  return `<div class="q ${j.state}">${tile(ic,col,'md')}<div style="min-width:0"><div class="nm t" title="${esc(j.output||j.name)}">${title}</div><div class="s" title="${esc(j.state=='error'?j.msg:j.encoder)}">${sub}</div>${j.state=='running'&&!rec||j.state=='queued'?`<div class="prog"><i style="width:${(j.progress*100).toFixed(1)}%"></i></div>`:''}</div>
  <div class="acts">${j.state=='queued'||j.state=='running'?`<button class="btn plain${rec?' danger':''}" data-c="${j.id}">${rec?'停止':'取消'}</button>`
   :(j.state=='done'||j.state=='partial')&&j.output?`<button class="btn plain" data-f="${esc(j.output)}">開啟</button>${!j.kind&&/\.(mp4|mkv|webm|mov|avi|gif|jpg|jpeg|png|webp|avif|bmp|tiff)$/i.test(j.output)?`<button class="btn plain" data-preview="${j.id}">預覽</button>`:''}<button class="btn icon" data-o="${esc(j.output)}" title="在檔案總管中顯示">${svg('folder')}</button>${j.notes?.length?`<button class="btn plain" data-notes="${esc(JSON.stringify(j.notes))}">說明</button>`:''}`
   :(j.state=='error'||j.state=='cancelled')&&j.retry?`${j.output?`<button class="btn plain" data-o="${esc(j.output)}">檢查成品</button>`:''}<button class="btn plain" data-rt="${j.id}">重試</button>`:''}</div></div>`}).join(''):'<div class="empty" style="padding:14px">沒有工作</div>'}catch(e){toast('無法更新工作狀態，稍後會再試',1)}finally{polling=false}}
let tick=0;setInterval(()=>{tick++;if(API&&(busy||recState.rec||tick%4==0))poll()},700);
/* ---------- tools ---------- */
const NEW=new Set(['s_jumpcut','s_highlight','s_chapters','s_bestframe','s_photocull','s_autocrop','s_loudness','s_smartname','s_quality']);
const SPEECH=new Set(['v_autosub','a_transcribe','a_meeting','s_chapters']);
const speechMsg=()=>TS.whisper_ffmpeg===false?'目前的 FFmpeg 沒有語音辨識功能':'缺少離線語音辨識模型（tools\\models\\ggml-base.bin），請重新安裝完整版本';
function renderTList(){const list=visibleTools();const col=g=>GC[g];const cv=group=='search'&&INT.q==$('#gsearch').value.trim()?INT.convert:null;
 $('#tlist').innerHTML=(cv?`<div class="row ic click intent" id="intentconv">${tile('convert',GC.convert,'md')}<span class="lab"><span>到一般轉檔套用</span><small class="why">${esc(cv.why)}</small></span><span class="chev">${svg('chev')}</span></div>`:'')
 +(list.length?list.map(t=>{const it=intentOf(t.id);return `<div class="row ic click ${tool&&tool.id==t.id?'on':''}" data-t="${t.id}">${tile(t.icon,col(t.group),'md')}<span class="lab"><span style="display:flex;gap:6px;align-items:center">${esc(t.name)}${NEW.has(t.id)?'<span class="badge">新</span>':''}</span><small class="${it&&it.why!='名稱或說明相符'?'why':''}">${esc(it&&it.why!='名稱或說明相符'?'建議：'+it.why+(Object.keys(it.params).length?'（已帶入設定）':''):t.desc)}</small></span><span class="chev">${svg('chev')}</span></div>`}).join('')
 :cv?'':'<div class="empty">找不到符合的工具<br><span class="mute small">可以直接描述想做的事，例如「剪掉影片停頓」「把照片 GPS 拿掉」</span></div>');
 if($('#intentconv'))$('#intentconv').onclick=()=>{const c=INT.convert;$('#gsearch').value='';INT={q:'',tools:[],convert:null};go('convert');if(c.target_mb)$('#tmb').value=c.target_mb;if(c.target){const v=c.target;files.forEach(f=>{if(f.targets.includes(v))f.target=v});render();if(files.some(f=>f.targets.includes(v)))$('#alltarget').value=v}toast(c.why.replace(/^一般轉檔：/,'已設定：')+(files.length?'':'，再加入檔案即可'))}}
$('#tlist').onclick=e=>{const r=e.target.closest('[data-t]');if(r)pickTool(r.dataset.t)};
function pickTool(id){if(!id)return;const keep=tool&&tfiles.length?tfiles:[];tool=TS.tools.find(t=>t.id==id);S.tool_by_group=S.tool_by_group||{};if(group!='search'){S.tool_by_group[group]=id;save()}
 tfiles=keep.filter(f=>tool.accept.includes(f.cat));const it=intentOf(id);TV=Object.assign({},...tool.fields.map(f=>({[f.k]:f.default})),(S.tool_opts||{})[id]||{},it?it.params:{});
 $('#t_tile').outerHTML=`<div class="tile lg" id="t_tile" style="background:${GC[tool.group]}">${svg(tool.icon)}</div>`;$('#t_name').textContent=tool.name;$('#t_desc').textContent=tool.desc;
 $$('#tlist .row').forEach(r=>r.classList.toggle('on',r.dataset.t==id));renderTFiles();renderForm()}
const ACC={video:'影片',audio:'音訊',image:'圖片',pdf:'PDF',disc:'光碟'};
async function addToolFiles(paths){if(!paths||!paths.length)return;if(tool.accept.includes('disc')){tfiles=[{path:paths[0],name:paths[0],cat:'disc',size:0}];renderTFiles();return}
 const got=await call('tool_files',paths,tool.id);const have=new Set(tfiles.map(f=>f.path));got.forEach(f=>{if(!have.has(f.path))tfiles.push(f)});
 if(!got.length)toast(`這個工具只能用在${tool.accept.map(a=>ACC[a]).join('、')}`,1);renderTFiles()}
async function renderTFiles(){const disc=tool.accept.includes('disc');
 $('#t_fhead').innerHTML=(disc?'來源':'檔案')+'<span class="r">'+(disc?`<select id="t_drv" style="width:190px;padding-top:3px;padding-bottom:3px"><option value="">選擇光碟機…</option></select><button class="btn plain" id="t_dir">選擇資料夾</button>`
  :`<button class="btn plain" id="t_addf">${svg('plus')}加入檔案</button><button class="btn plain" id="t_addd">加入資料夾</button>${tfiles.length?'<button class="btn plain" id="t_clr">全部移除</button>':''}`)+'</span>';
 $('#t_list').innerHTML=tfiles.length?tfiles.map((f,i)=>`<div class="row ic">${tile(CATI[f.cat]||'disc',CATC[f.cat]||GC.disc,'md')}<span class="lab"><span class="nm" style="display:block" title="${esc(f.path)}">${esc(f.name)}</span>${f.size?`<small>${fmtSize(f.size)}${miText(f.path)?' · '+miText(f.path):''}</small>`:''}</span>
  <span class="val">${tool.together&&tfiles.length>1?`<span class="order"><button class="btn icon" data-u="${i}" title="上移">${svg('up')}</button><button class="btn icon" data-d="${i}" title="下移">${svg('down')}</button></span>`:''}<button class="btn icon" data-r="${i}" title="移除">${svg('x')}</button></span></div>`).join('')
  :`<div class="empty">${disc?'放入光碟後從上方選擇光碟機，<br>或選擇硬碟裡的 VIDEO_TS／BDMV 資料夾。':'將'+tool.accept.map(a=>ACC[a]).join('、')+'拖到這裡，或按「加入檔案」。'}</div>`;
 $('#t_fnote').textContent=tool.together&&!disc?'多個檔案會依清單順序合成一個，可以用箭頭調整順序。':'';
 if(disc){const dv=await API.drives();const s=$('#t_drv');s.innerHTML='<option value="">'+(dv.length?'選擇光碟機…':'找不到光碟機')+'</option>'+dv.map(d=>`<option value="${esc(d.path)}">${esc(d.label)}</option>`).join('');s.onchange=()=>{if(s.value){tfiles=[{path:s.value,name:s.selectedOptions[0].text,cat:'disc'}];renderTFiles()}};
  $('#t_dir').onclick=async()=>{const p=await call('pick_folder','out');if(p){tfiles=[{path:p,name:p,cat:'disc'}];renderTFiles()}}}
 else{$('#t_addf').onclick=async()=>{const r=await call('pick_files');addToolFiles(r.map(x=>x.path))};$('#t_addd').onclick=async()=>{const p=await call('pick_folder','out');if(p)addToolFiles([p])};if($('#t_clr'))$('#t_clr').onclick=()=>{tfiles=[];renderTFiles()}}
 updGo()}
$('#t_list').onclick=e=>{const b=e.target.closest('button');if(!b)return;const D=b.dataset;
 if(D.r!==undefined){tfiles.splice(+D.r,1)}else if(D.u!==undefined&&+D.u>0){const i=+D.u;[tfiles[i-1],tfiles[i]]=[tfiles[i],tfiles[i-1]]}else if(D.d!==undefined&&+D.d<tfiles.length-1){const i=+D.d;[tfiles[i+1],tfiles[i]]=[tfiles[i],tfiles[i+1]]}else return;renderTFiles()};
function shown(f){if(!f.show)return true;return Object.entries(f.show).every(([k,v])=>Array.isArray(v)?v.includes(String(TV[k])):String(TV[k])==String(v))}
function renderForm(){const fs=tool.fields.filter(f=>shown(f)&&f.type!='json');$('#t_optwrap').style.display=fs.length?'':'none';
 $('#t_form').innerHTML=fs.map(f=>{const v=TV[f.k];let inp='';
  if(f.type=='check')return `<div class="row"><span class="lab">${esc(f.label)}</span><div class="sw ${v?'on':''}" data-k="${f.k}"></div></div>`;
  if(f.type=='select')inp=`<select data-k="${f.k}">${f.options.map(([a,b])=>`<option value="${esc(a)}" ${String(a)==String(v)?'selected':''}>${esc(b)}</option>`).join('')}</select>`;
  else if(f.type=='number')inp=`<input type="number" data-k="${f.k}" value="${esc(v)}" ${f.min!=null?`min="${f.min}"`:''} ${f.max!=null?`max="${f.max}"`:''} step="${f.step||'any'}">`;
  else if(f.type=='color')inp=`<input type="color" data-k="${f.k}" value="${esc(v)}">`;
  else if(f.type=='file')inp=`<span class="fpick"><span class="nm" title="${esc(v)}">${v?esc(v.split(/[\\/]/).pop()):'未選擇'}</span><button class="btn tint" data-file="${f.k}">選擇…</button></span>`;
  else if(f.type=='rect')inp=`<span class="fpick"><span class="nm">${v?esc(v.split(',').slice(2).join(' × '))+' 像素':'尚未框選'}</span><button class="btn tint" data-rect="${f.k}">在畫面上框選</button></span>`;
  else inp=`<input type="${f.k=='pw'||f.type=='password'?'password':'text'}" autocomplete="off" data-k="${f.k}" value="${esc(v)}" placeholder="${esc(f.placeholder||'')}">`;
  return `<div class="row"><span class="lab">${esc(f.label)}</span><span class="val">${inp}</span></div>`}).join('');
 let note='';if(SPEECH.has(tool.id))note=TS.whisper?('完全離線辨識，錄音不會上傳。'+(tool.id=='a_meeting'?'先轉成逐字稿，再整理出摘要、重點、決議與待辦事項；產出 Word、Markdown 與 SRT。'+(TS.ai?'':'<br><span class="warn">缺少離線文字模型，請選「快速摘錄」。</span>'):tool.id=='a_transcribe'?'長錄音會依停頓自動分段，並附上時間。':'')+(PC.low?'<br><span class="warn">這台電腦效能較精簡，1 小時錄音約需數十分鐘，建議先處理較短的片段。</span>':'')):'<span class="warn">'+speechMsg()+'。</span>';
 if(['i_watermark','v_wm_text'].includes(tool.id)&&!TS.font)note='<span class="warn">找不到中文字型。</span>';
 if(tool.id=='a_vocal')note='原理是消去左右聲道相同的聲音，對多數流行歌有效；現場錄音或單聲道效果有限。';
 if(tool.id=='v_stab')note='防手震需要先完整分析一次影片，時間約為一般轉檔的兩倍。';
 const SN2={s_jumpcut:'自動量這段錄音的音量來決定什麼算「停頓」；剪完會保留每段前後一點空隙，聽起來不突兀。',s_highlight:'掃描整支影片的聲音起伏與畫面切換，挑出最熱鬧的片段依時間順序接起來。',
  s_chapters:'先離線聽打，再依話題轉換與停頓切章節；YouTube 章節文字可直接貼到說明欄。',s_bestframe:'依清晰度、曝光、對比、色彩與主體位置評分，並排除相似畫面。',
  s_photocull:'相似的連拍會分成一組，每組留最好的一張；原始照片不會被移動或刪除。',s_autocrop:'偵測整支影片最穩定的黑邊範圍後裁切；畫面內容不會被縮放。',
  s_loudness:'先完整量測一次，再精準校正到平台規範；影片畫面不重新編碼。',s_smartname:'讀取照片 EXIF、影片建立時間、PDF 標題與歌曲資訊；複製成新名稱並附對照表。',
  s_quality:'先用 3 段樣本試壓並量測 SSIM，找出畫質達標的最小檔案；使用 CPU 編碼，較慢但結果穩定。'};
 if(SN2[tool.id]&&!SPEECH.has(tool.id))note=SN2[tool.id];if(tool.id=='s_chapters'&&TS.whisper)note=SN2.s_chapters+(TS.ai?'':'<br><span class="warn">缺少離線文字模型，章節標題會改用關鍵句摘錄。</span>');
 if(tool.id=='x_privacy')note='JPG、PNG 直接移除資訊、不重新壓縮；影片與音訊不重新編碼。';
 $('#t_note').innerHTML=(PDFUI.edits.has(tool.id)?'<button class="btn tint" id="pdf_open_editor">在 PDF 頁面上編輯</button><p class="gfoot">'+(Array.isArray(TV.actions)?TV.actions.length+' 個項目已套用。':'加入 PDF 後可預覽、框選與編輯。')+'</p>':'')+note;if($('#pdf_open_editor'))$('#pdf_open_editor').onclick=()=>waiting($('#pdf_open_editor'),()=>PDFUI.open(tool.id));updGo()}
function updGo(){const b=$('#t_go');const n=tfiles.length;const disc=tool.accept.includes('disc');b.disabled=!n||(tool.together&&n<(tool.min_files||(['i_slideshow','i_gif'].includes(tool.id)?1:2)))||(tool.max_files&&n!=tool.max_files)||(SPEECH.has(tool.id)&&!TS.whisper);
 b.textContent=disc?'開始':tool.together?(n>1?`合成 ${n} 個檔案`:'開始'):n>1?`處理 ${n} 個檔案`:'開始';
 const need=tool.min_files||(tool.together&&!['i_slideshow','i_gif'].includes(tool.id)?2:1);
 $('#t_gohint').innerHTML=SPEECH.has(tool.id)&&!TS.whisper?speechMsg():!n?(disc?'先選擇光碟機或資料夾':`先加入${need>1?'至少 2 個':''}${tool.accept.map(a=>ACC[a]).join('或')}`):n<need?'至少需要 2 個檔案':'按 <kbd>Ctrl</kbd> <kbd>Enter</kbd> 開始';loadInfo(tfiles,()=>renderTFiles())}
$('#t_form').addEventListener('change',e=>{const k=e.target.dataset.k;if(!k)return;TV[k]=e.target.value;if(tool.fields.some(f=>f.show&&k in f.show))renderForm()});
$('#t_form').addEventListener('input',e=>{const k=e.target.dataset.k;if(k&&e.target.tagName!='SELECT')TV[k]=e.target.value});
$('#t_form').addEventListener('click',async e=>{const t=e.target.closest('.sw,button');if(!t)return;
 if(t.classList.contains('sw')){t.classList.toggle('on');TV[t.dataset.k]=t.classList.contains('on');if(tool.fields.some(f=>f.show&&t.dataset.k in f.show))renderForm();return}
 if(t.dataset.file){const f=tool.fields.find(x=>x.k==t.dataset.file);const p=await call('pick_file',f.filter||'');if(p){TV[f.k]=p;renderForm()}}
 if(t.dataset.rect){if(!tfiles.length){toast('請先加入檔案',1);return}openRect(tfiles[0].path,t.dataset.rect)}});
$('#t_go').onclick=async()=>{const fs=tool.fields.filter(shown);for(const f of fs){if(f.type=='file'&&!TV[f.k]&&!/選填/.test(f.label)){toast(`請先選擇「${f.label}」`,1);return}if(f.type=='rect'&&!TV[f.k]&&!/選填/.test(f.label)){toast('請先在畫面上框選範圍',1);return}}
 const p={};tool.fields.forEach(f=>{if(shown(f))p[f.k]=TV[f.k]});const ids=await call('run_tool',tool.id,tfiles.map(f=>f.path),p);S.tool_opts=S.tool_opts||{};S.tool_opts[tool.id]=Object.fromEntries(Object.entries(p).filter(([k])=>!['rect','actions','pw','pfx','pfx_pw'].includes(k)));
 toast(`已加入 ${ids.length} 個工作`);if(!tool.accept.includes('disc'))tfiles=[];renderTFiles();poll()};
/* ---------- rectangle picker ---------- */
let RP=null;
async function openRect(path,key){$('#rmodal').classList.add('on');$('#sel').style.display='none';RP={path,key,r:null};await loadFrame(null)}
async function loadFrame(t){const p=/\.pdf$/i.test(RP.path)?await call('pdf_preview',RP.path,+TV.preview_page||1,TV.pw||''):await call('preview',RP.path,t);RP.w=p.w;RP.h=p.h;RP.dur=p.dur;$('#simg').src=p.src;
 $('#stime').style.visibility=p.dur?'visible':'hidden';$('#stimel').textContent=p.dur?fmtT(Math.round(t??p.dur*0.3)):'';$('#r_info').textContent=`原始尺寸 ${p.w} × ${p.h}`;
 const cur=TV[RP.key];if(cur&&!RP.r){const [x,y,w,h]=cur.split(',').map(Number);RP.r={x,y,w,h};setTimeout(drawSel,60)}}
$('#stime').onchange=e=>loadFrame(RP.dur*e.target.value/1000);
function drawSel(){const r=RP.r,img=$('#simg'),s=$('#sel');if(!r){s.style.display='none';return}const k=img.clientWidth/RP.w;
 Object.assign(s.style,{display:'block',left:r.x*k+'px',top:r.y*k+'px',width:r.w*k+'px',height:r.h*k+'px'});$('#r_info').textContent=`原始尺寸 ${RP.w} × ${RP.h}　·　選取 ${r.w} × ${r.h}`}
(()=>{const st=$('#stage');let a=null;
 st.onmousedown=e=>{const b=$('#simg').getBoundingClientRect();a={x:e.clientX-b.left,y:e.clientY-b.top,b}};
 window.addEventListener('mousemove',e=>{if(!a)return;const k=RP.w/a.b.width;const cx=Math.max(0,Math.min(a.b.width,e.clientX-a.b.left)),cy=Math.max(0,Math.min(a.b.height,e.clientY-a.b.top));
  RP.r={x:Math.round(Math.min(a.x,cx)*k),y:Math.round(Math.min(a.y,cy)*k),w:Math.round(Math.abs(cx-a.x)*k),h:Math.round(Math.abs(cy-a.y)*k)};drawSel()});
 window.addEventListener('mouseup',()=>a=null)})();
$('#rcancel').onclick=()=>$('#rmodal').classList.remove('on');
$('#rok').onclick=()=>{const r=RP.r;if(!r||r.w<4||r.h<4){toast('請在畫面上拖拉出一個範圍',1);return}TV[RP.key]=[r.x,r.y,r.w,r.h].join(',');$('#rmodal').classList.remove('on');renderForm()};
/* ---------- recorder ---------- */
let recLoaded=false;
async function recInit(){if(recLoaded)return;recLoaded=true;const r=await API.rec_info();const o=r.opts||{};
 $('#r_mon').innerHTML=r.monitors.map(m=>`<option value="${m.idx}">${esc(m.label)}</option>`).join('');
 $('#r_audio').innerHTML=r.audio.length?r.audio.map(a=>`<div class="row"><span class="lab nm">${esc(a)}</span><div class="sw ${(o.audio||[]).includes(a)?'on':''}" data-a="${esc(a)}"></div></div>`).join(''):'<div class="empty" style="padding:16px">找不到麥克風或錄音裝置，將只錄畫面。</div>';
 if(o.fps)$('#r_fps').value=o.fps;if(o.monitor!=null)$('#r_mon').value=o.monitor;if(o.region){$('#r_area').value='custom';$('#r_region').value=o.region}$('#r_regwrap').style.display=o.region?'':'none';
 sw('r_mouse',o.mouse!==false);sw('r_min',o.minimize!==false)}
$('#r_audio').onclick=e=>{const t=e.target.closest('.sw');if(t)t.classList.toggle('on')};['r_mouse','r_min','d_pl','d_subs','d_thumb'].forEach(id=>$('#'+id).onclick=()=>$('#'+id).classList.toggle('on'));
$('#r_area').onchange=e=>$('#r_regwrap').style.display=e.target.value?'':'none';
$('#recbtn').onclick=async()=>{if(recState.rec){await call('rec_stop');toast('錄影已儲存');poll();return}
 const region=$('#r_area').value?$('#r_region').value.trim():'';if($('#r_area').value&&!/^\d+,\d+,\d+,\d+$/.test(region)){toast('區域格式：x,y,寬,高（例如 0,0,1280,720）',1);return}
 const o={monitor:+$('#r_mon').value,fps:+$('#r_fps').value,region,mouse:isOn('r_mouse'),minimize:isOn('r_min'),audio:$$('#r_audio .sw.on').map(i=>i.dataset.a)};
 $('#recbtn').disabled=true;$('#recsub').textContent='準備中…';try{await call('rec_start',o)}finally{$('#recbtn').disabled=false}poll()};
function recUI(){const on=!!recState.rec;const d=$('#recdot');if(d)d.classList.toggle('on',on);const b=$('#recbtn');b.classList.toggle('stop',on);
 const s=recState.sec||0;$('#rectime').textContent=`${String(Math.floor(s/60)).padStart(2,'0')}:${String(s%60).padStart(2,'0')}`;$('#rectime').style.color=on?'var(--red)':'';
 if(on)$('#recsub').innerHTML=`錄影中 · ${fmtSize(recState.size||0)}<br>按 <kbd>Ctrl</kbd> <kbd>Shift</kbd> <kbd>F9</kbd> 或按鈕停止`;
 else if(!b.disabled)$('#recsub').innerHTML='開始後視窗會自動縮小，影片存在「影片」資料夾<br>隨時按 <kbd>Ctrl</kbd> <kbd>Shift</kbd> <kbd>F9</kbd> 停止'}
/* ---------- downloader ---------- */
$('#d_paste').onclick=async()=>{try{const t=await navigator.clipboard.readText();$('#d_urls').value=($('#d_urls').value.trim()+'\n'+t).trim()}catch(e){toast('無法讀取剪貼簿，請按 Ctrl+V 貼上',1)}};
$('#d_dirbtn').onclick=async()=>{const p=await call('pick_folder','out');if(p){S.dl=S.dl||{};S.dl.out_dir=p;$('#d_dir').textContent=p;save()}};
$('#d_go').onclick=async()=>{const o={quality:$('#d_q').value,playlist:isOn('d_pl'),subs:isOn('d_subs'),thumb:isOn('d_thumb'),out_dir:(S.dl||{}).out_dir||''};
 const ids=await call('dl_start',$('#d_urls').value,o);toast(`開始下載 ${ids.length} 個網址`);$('#d_urls').value='';poll()};
$('#d_upd').onclick=async()=>{$('#d_msg').textContent='更新中…';try{$('#d_msg').textContent=await call('dl_update')}catch(e){$('#d_msg').textContent=''}};
/* ---------- automation ---------- */
let W=[];const WT=[['auto','自動建議格式'],['mp4','MP4'],['mp3','MP3'],['m4a','M4A'],['jpg','JPG'],['webp','WebP'],['png','PNG'],['pdf','PDF'],['docx','Word'],['epub','EPUB'],['extract','解壓縮']];
async function autoInit(){W=await API.watch_get();wRender();setSeg('#finish',S.finish||'sound')}
function wRender(){$('#w_rows').innerHTML=W.length?W.map((r,i)=>`<div class="row ic">${tile('folder','var(--blue)','md')}<span class="lab"><span class="nm" style="display:block" title="${esc(r.folder)}">${esc(r.folder.split(/[\\/]/).filter(Boolean).pop()||r.folder)}</span><small>${esc(r.folder)}</small></span>
 <span class="val"><select data-i="${i}" data-k="target" style="width:130px">${WT.map(([a,b])=>`<option value="${a}" ${r.target==a?'selected':''}>${b}</option>`).join('')}</select>
 <select data-i="${i}" data-k="preset" style="width:120px">${[['','目前品質'],['high','高品質'],['balanced','均衡'],['small','小檔案']].map(([a,b])=>`<option value="${a}" ${(r.preset||'')==a?'selected':''}>${b}</option>`).join('')}</select>
 <label class="mute small" style="display:flex;gap:5px;align-items:center;white-space:nowrap"><input type="checkbox" data-i="${i}" data-k="recursive" ${r.recursive?'checked':''}>子資料夾</label>
 <div class="sw ${r.on!==false?'on':''}" data-i="${i}" data-k="on" title="啟用"></div><button class="btn icon" data-del="${i}" title="移除">${svg('x')}</button></span></div>`).join('')
 :'<div class="empty">還沒有監控任何資料夾</div>'}
$('#w_add').onclick=async()=>{const p=await call('pick_folder','out');if(!p)return;if(W.some(r=>r.folder==p)){toast('這個資料夾已經在監控中');return}W.push({folder:p,target:'auto',preset:'',recursive:false,on:true});await API.watch_set(W);wRender();toast('開始監控，之後放進去的檔案會自動轉檔')};
$('#w_rows').addEventListener('change',async e=>{const t=e.target,i=t.dataset.i;if(i==null)return;W[i][t.dataset.k]=t.type=='checkbox'?t.checked:t.value;await API.watch_set(W)});
$('#w_rows').addEventListener('click',async e=>{const t=e.target.closest('.sw,[data-del]');if(!t)return;if(t.classList.contains('sw')){t.classList.toggle('on');W[t.dataset.i].on=t.classList.contains('on');await API.watch_set(W)}if(t.dataset.del){W.splice(+t.dataset.del,1);await API.watch_set(W);wRender()}});
/* ---------- formats ---------- */
function ft(q){q=(q||'').toLowerCase().replace('.','');$('#ftb').innerHTML=FT.filter(r=>!q||r.cat.includes(q)||r.inputs.concat(r.outputs).some(e=>e.includes(q))).map(r=>`<tr><td><span class="chip" style="background:${CATC[r.key]||'var(--gray)'}">${r.cat}</span></td><td class="fx">${r.inputs.join(' ')}</td><td class="fx">${r.outputs.map(TL).join(' ')||'—'}</td><td>${r.engine}</td><td class="warn">${r.note}</td></tr>`).join('')||'<tr><td colspan=5 class="empty">找不到這個格式</td></tr>'}
$('#fmtbtn').onclick=async()=>{if(!FT.length)FT=await API.formats();ft($('#q').value);$('#modal').classList.add('on');$('#q').focus()};
$('#mclose').onclick=()=>$('#modal').classList.remove('on');$$('.modal').forEach(m=>m.onclick=e=>{if(e.target==m){if(m.id=='amodal'){$('#aok').click();return}m.classList.remove('on')}});
$('#q').oninput=e=>ft(e.target.value);
document.addEventListener('keydown',e=>{const c=e.ctrlKey||e.metaKey,inField=/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName);
 if(e.key=='Escape'){$$('.modal').forEach(m=>m.classList.remove('on'));if(document.activeElement==$('#gsearch')&&$('#gsearch').value){$('#gsearch').value='';$('#gsearch').dispatchEvent(new Event('input'))}}
 if(c&&e.key=='f'){e.preventDefault();$('#gsearch').focus();$('#gsearch').select()}
 if(c&&e.key=='o'){e.preventDefault();if(S.tab=='workflow'){$('#wf_addf').click();return}if($('#p-tools').classList.contains('on')&&tool&&!tool.accept.includes('disc'))$('#t_addf').click();else if(S.tab=='convert')$('#addf').click()}
 if(c&&e.key=='Enter'){e.preventDefault();const b=$('#p-tools').classList.contains('on')?$('#t_go'):S.tab=='workflow'?$('#wf_go'):S.tab=='convert'?$('#go'):S.tab=='dl'?$('#d_go'):null;if(b&&!b.disabled)b.click()}});

/* ---------- delivery workflows ---------- */
let WF={recipes:[],profiles:[]},wfFiles=[],wfSteps=[],wfExtras={logo:'',sub_file:'',out_dir:''};
function wfInit(schema){WF=schema||WF;$('#wf_recipe').innerHTML=WF.recipes.map(r=>`<option value="${r.id}">${esc(r.name)}</option>`).join('');wfProfiles();wfRender();wfMode();$('#wf_step_tool').innerHTML=TS.tools.filter(t=>!t.together&&!t.accept.includes('disc')&&!['v_split','v_frames','p_split'].includes(t.id)).map(t=>`<option value="${t.id}">${esc(t.name)}</option>`).join('')}
function wfProfiles(selected=''){$('#wf_profiles').innerHTML='<option value="">選擇已保存配方</option>'+WF.profiles.map(p=>`<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('');$('#wf_profiles').value=selected}
function wfAdd(list){const seen=new Set(wfFiles.map(f=>f.path));list.forEach(f=>{if(!seen.has(f.path)){f._fresh=true;wfFiles.push(f);seen.add(f.path)}});wfRender()}
function wfRender(){$('#wf_list').innerHTML=wfFiles.length?wfFiles.slice(0,100).map((f,i)=>`<div class="row ${f._fresh?'file-enter':''}"><span class="lab nm" title="${esc(f.path)}">${esc(f.name)}<small>${CAT[f.cat]||'素材'} · ${fmtSize(f.size)}</small></span><button class="btn icon" data-remove="${i}" aria-label="移除 ${esc(f.name)}">${svg('x')}</button></div>`).join(''):'<div class="empty">還沒有加入素材</div>';$('#wf_go').disabled=!wfFiles.length;$('#wf_hint').textContent=wfFiles.length?`${wfFiles.length} 個素材 · Ctrl+Enter 開始`:'先加入素材';wfFiles.forEach(f=>f._fresh=false);wfLabels()}
function wfLabels(){['logo','sub','out'].forEach(k=>{const key={logo:'logo',sub:'sub_file',out:'out_dir'}[k];$('#wf_'+k+'_label').textContent=wfExtras[key]||{logo:'未選擇',sub:'選填 · 可燒入所有影片版本',out:S.out_mode=='custom'&&S.out_dir?S.out_dir:'原資料夾內的新交付包'}[k]})}
function wfMode(){const recipe=$('#wf_recipe').value;$('#wf_desc').textContent=(WF.recipes.find(r=>r.id==recipe)||{}).desc||'';$$('.wf-share').forEach(e=>e.style.display=recipe=='share'?'':'none');$$('.wf-product').forEach(e=>e.style.display=recipe=='product'?'':'none');$$('.wf-brand').forEach(e=>e.style.display=['product','video'].includes(recipe)?'':'none');$('#wf_pipeline').style.display=recipe=='pipeline'?'':'none';$('#wf_video_options').style.display=recipe=='video'?'':'none';wfStepRender()}
function wfOptions(){return {prefix:$('#wf_prefix').value,preset:$('#wf_quality').value,max_mb:+$('#wf_max').value||20,size:+$('#wf_size').value||1200,watermark:$('#wf_watermark').value,zip:$('#wf_zip').checked,total_mb:+$('#wf_total').value||0,verify_full:$('#wf_verify').checked,autosub:$('#wf_autosub').checked,model:$('#wf_model').value,video_size:+$('#wf_video_size').value,resource_mode:S.resource_mode||'auto',...wfExtras,steps:JSON.parse(JSON.stringify(wfSteps))}}
function wfApply(p){$('#wf_recipe').value=p.recipe;$('#wf_name').value=p.name;const o=p.options||{};[['prefix','wf_prefix',''],['preset','wf_quality','balanced'],['max_mb','wf_max',20],['size','wf_size',1200],['watermark','wf_watermark',''],['total_mb','wf_total',0],['model','wf_model','base'],['video_size','wf_video_size',PC.ram<=4.5?480:720]].forEach(([k,id,d])=>$('#'+id).value=o[k]??d);[['zip','wf_zip'],['verify_full','wf_verify'],['autosub','wf_autosub']].forEach(([k,id])=>$('#'+id).checked=!!o[k]);wfExtras={logo:o.logo||'',sub_file:o.sub_file||'',out_dir:o.out_dir||''};wfSteps=JSON.parse(JSON.stringify(o.steps||[]));wfMode();wfRender()}
function wfStepRender(){const el=$('#wf_steps');el.innerHTML=wfSteps.length?wfSteps.map((st,i)=>{const t=TS.tools.find(t=>t.id==st.tool);if(!t)return'';const fields=t.fields.filter(f=>!f.show||Object.entries(f.show).every(([k,v])=>Array.isArray(v)?v.includes(String(st.params[k])):String(v)==String(st.params[k])));return `<div class="flow-step"><div class="flow-step-head"><b>${i+1}. ${esc(t.name)}</b><button class="btn icon" data-move="${i}" data-dir="-1" ${i==0?'disabled':''} aria-label="上移">↑</button><button class="btn icon" data-move="${i}" data-dir="1" ${i==wfSteps.length-1?'disabled':''} aria-label="下移">↓</button><button class="btn plain danger" data-delete="${i}">移除</button></div>${fields.map(f=>{const v=st.params[f.k]??f.default;let inp='';const a=`data-step="${i}" data-param="${f.k}"`;if(f.type=='check')inp=`<input type="checkbox" ${a} ${v?'checked':''}>`;else if(f.type=='select')inp=`<select ${a}>${f.options.map(([x,n])=>`<option value="${esc(x)}" ${String(x)==String(v)?'selected':''}>${esc(n)}</option>`).join('')}</select>`;else if(f.type=='file')inp=`<span class="fpick"><span class="nm">${esc(v?v.split(/[\\/]/).pop():'未選擇')}</span><button class="btn tint" data-step-file="${i}" data-param="${f.k}">選擇</button></span>`;else inp=`<input ${a} type="${f.k=='pw'?'password':f.type=='number'?'number':f.type=='color'?'color':'text'}" value="${esc(v??'')}" ${f.min!=null?`min="${f.min}"`:''} ${f.max!=null?`max="${f.max}"`:''} step="any" placeholder="${f.type=='rect'?'x,y,寬,高':''}" autocomplete="off">`;return `<div class="row"><span class="lab">${esc(f.label)}</span><span class="val">${inp}</span></div>`}).join('')}</div>`}).join(''):'<div class="empty">加入工具，建立自己的處理順序</div>'}
async function waiting(button, action){if(button.getAttribute('aria-busy')=='true')return;button.setAttribute('aria-busy','true');const was=button.disabled;button.disabled=true;try{return await action()}catch(e){return undefined}finally{button.removeAttribute('aria-busy');button.disabled=button.id=='go'?!files.some(f=>f.target):button.id=='wf_go'?!wfFiles.length:button.id=='t_go'?!tfiles.length:was}}
$('#wf_recipe').onchange=wfMode;$('#wf_addf').onclick=()=>waiting($('#wf_addf'),async()=>wfAdd(await call('pick_files')));$('#wf_addd').onclick=()=>waiting($('#wf_addd'),async()=>{const r=await call('pick_folder','add');if(r)wfAdd(r)});$('#wf_drop').onclick=()=>$('#wf_addf').click();$('#wf_drop').onkeydown=e=>{if(e.key=='Enter'||e.key==' '){e.preventDefault();$('#wf_addf').click()}};
$('#wf_clear').onclick=()=>{const previous=wfFiles;wfFiles=[];wfRender();if(previous.length)toast('已移除素材',false,['復原',()=>{wfFiles=previous;wfRender()}])};$('#wf_list').onclick=e=>{const b=e.target.closest('[data-remove]');if(b){const i=+b.dataset.remove,removed=wfFiles.splice(i,1)[0];wfRender();toast('已移除 '+removed.name,false,['復原',()=>{wfFiles.splice(Math.min(i,wfFiles.length),0,removed);wfRender()}])}};
['logo','sub'].forEach(k=>{const key=k=='sub'?'sub_file':k;$('#wf_'+k).onclick=async()=>{const p=await call('pick_file',k=='sub'?'字幕 (*.srt;*.ass;*.vtt)':'圖片 (*.png;*.jpg;*.webp)');if(p){wfExtras[key]=p;wfLabels()}};$('#wf_'+k+'_clear').onclick=()=>{wfExtras[key]='';wfLabels()}});$('#wf_out').onclick=async()=>{const p=await call('pick_folder','out');if(p){wfExtras.out_dir=p;wfLabels()}};$('#wf_out_clear').onclick=()=>{wfExtras.out_dir='';wfLabels()};
$('#wf_step_add').onclick=()=>{if(wfSteps.length>=20){toast('最多 20 個步驟',1);return}const t=TS.tools.find(t=>t.id==$('#wf_step_tool').value);wfSteps.push({tool:t.id,params:Object.fromEntries(t.fields.map(f=>[f.k,f.default]))});wfStepRender();$('#wf_steps').lastElementChild?.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'nearest'})};
$('#wf_steps').onchange=e=>{const n=e.target;if(n.dataset.step!==undefined){const st=wfSteps[+n.dataset.step];st.params[n.dataset.param]=n.type=='checkbox'?n.checked:n.type=='number'?+n.value:n.value;if((TS.tools.find(t=>t.id==st.tool)||{}).fields.some(f=>f.show&&n.dataset.param in f.show))wfStepRender()}};
$('#wf_steps').oninput=e=>{const n=e.target;if(n.dataset.step!==undefined&&n.tagName=='INPUT'&&n.type!='checkbox')wfSteps[+n.dataset.step].params[n.dataset.param]=n.type=='number'?+n.value:n.value};
$('#wf_steps').onclick=async e=>{const b=e.target.closest('button');if(!b)return;if(b.dataset.delete!==undefined){wfSteps.splice(+b.dataset.delete,1);wfStepRender()}if(b.dataset.move!==undefined){const i=+b.dataset.move,d=+b.dataset.dir;[wfSteps[i],wfSteps[i+d]]=[wfSteps[i+d],wfSteps[i]];wfStepRender()}if(b.dataset.stepFile!==undefined){const i=+b.dataset.stepFile,st=wfSteps[i],f=TS.tools.find(t=>t.id==st.tool).fields.find(f=>f.k==b.dataset.param),p=await call('pick_file',f.filter||'');if(p){st.params[f.k]=p;wfStepRender()}}};
$('#wf_go').onclick=()=>waiting($('#wf_go'),async()=>{if($('#wf_recipe').value=='pipeline'&&!wfSteps.length){toast('請先加入處理步驟',1);return}await call('workflow_run',$('#wf_recipe').value,wfFiles.map(f=>f.path),wfOptions());toast('交付工作已加入佇列');poll()});
$('#wf_save').onclick=()=>waiting($('#wf_save'),async()=>{const name=$('#wf_name').value.trim();if(!name){toast('請輸入配方名稱',1);$('#wf_name').focus();return}const id=$('#wf_profiles').value;WF=await call('workflow_save',{id,name,recipe:$('#wf_recipe').value,options:wfOptions()});wfProfiles(id||WF.profiles[WF.profiles.length-1].id);toast('配方已保存，密碼不會保存')});
$('#wf_profiles').onchange=e=>{const p=WF.profiles.find(p=>p.id==e.target.value);if(p)wfApply(p)};$('#wf_export').onclick=async()=>{const id=$('#wf_profiles').value;if(!id){toast('請先選擇已保存配方',1);return}const p=await call('workflow_export',id);if(p)toast('配方已匯出')};$('#wf_import').onclick=async()=>{WF=await call('workflow_import');wfProfiles();toast('配方清單已更新')};$('#wf_delete').onclick=async()=>{const id=$('#wf_profiles').value,p=WF.profiles.find(p=>p.id==id);if(!p)return;WF=await call('workflow_delete',id);wfProfiles();toast('配方已刪除',false,['復原',async()=>{WF=await call('workflow_save',p);wfProfiles(p.id)}])};
['go','t_go','d_go','recbtn'].forEach(id=>{const b=$('#'+id),fn=b.onclick;b.onclick=()=>waiting(b,()=>fn())});document.addEventListener('click',e=>{const n=e.target.closest('.sw');if(n)n.setAttribute('aria-checked',n.classList.contains('on'))});
$('#resource_mode').onchange=e=>{S.resource_mode=e.target.value;save()};$('#codec').onchange=e=>{S.codec=e.target.value;save()};$('#verify_full').onchange=e=>{S.verify_full=e.target.checked;save()};
function accessibility(){document.querySelectorAll('.nav').forEach(n=>{n.setAttribute('role','button');n.tabIndex=0;n.setAttribute('aria-label',n.title);n.onkeydown=e=>{if(e.key=='Enter'||e.key==' '){e.preventDefault();n.click()}}});document.querySelectorAll('.sw').forEach(n=>{n.setAttribute('role','switch');n.setAttribute('aria-checked',n.classList.contains('on'));n.tabIndex=0;n.setAttribute('aria-label',n.parentElement.querySelector('.lab')?.textContent||'切換');n.onkeydown=e=>{if(e.key=='Enter'||e.key==' '){e.preventDefault();n.click();n.setAttribute('aria-checked',n.classList.contains('on'))}}})}
const a11yObserver=new MutationObserver(()=>accessibility());a11yObserver.observe(document.querySelector('.content'),{childList:true,subtree:true});a11yObserver.observe($('#nav'),{childList:true});$('#toast').setAttribute('role','status');$('#toast').setAttribute('aria-live','polite');
$('#compareclose').onclick=()=>$('#comparemodal').classList.remove('on');

/* ---------- computer tools ---------- */
let cleanupPlan=null,systemLoaded=false;
async function systemInit(){if(systemLoaded)return;systemLoaded=true;try{const r=await call('system_info'),h=r.hardware;$('#sys_info').innerHTML=[['處理器',h.cpu],['系統',h.system+' · '+h.arch],['記憶體',h.ram+' GB'],['邏輯執行緒',h.cores],['最多同時工作',h.slots+' 個（依規格）'],['影音硬體編碼',h.gpu_encoders.length?h.gpu_encoders.join('、'):'使用 CPU'],...h.disks.map(d=>[d.path,'可用 '+fmtSize(d.free)+'／'+fmtSize(d.total)])].map(([k,v])=>`<div class="row"><span class="lab">${esc(k)}</span><span>${esc(v)}</span></div>`).join('');$('#sys_categories').innerHTML=r.cleanup.map(c=>`<div class="row"><label class="lab" for="clean_${c.id}">${esc(c.name)}<small>${esc(c.desc)}</small></label><input type="checkbox" id="clean_${c.id}" data-clean="${c.id}" ${c.default?'checked':''}></div>`).join('')}catch(e){systemLoaded=false}}
$('#sys_refresh').onclick=()=>waiting($('#sys_refresh'),async()=>{systemLoaded=false;await systemInit()});$('#sys_test').onclick=()=>waiting($('#sys_test'),async()=>{await call('system_test');toast('硬體短測已加入佇列');poll()});
$('#sys_categories').onchange=()=>{cleanupPlan=null;$('#sys_clean').disabled=true;$('#sys_preview').innerHTML='<div class="empty">範圍已變更，請重新掃描</div>'};
$('#sys_scan').onclick=()=>waiting($('#sys_scan'),async()=>{const cats=$$('[data-clean]').filter(e=>e.checked).map(e=>e.dataset.clean);if(!cats.length){toast('請選擇清理範圍',1);return}cleanupPlan=await call('cleanup_scan',cats);$('#sys_preview').innerHTML=`<div class="row"><b class="lab">${cleanupPlan.count} 個檔案</b><b>約 ${fmtSize(cleanupPlan.bytes)}</b></div>`+cleanupPlan.categories.filter(c=>c.count).map(c=>`<div class="row"><span class="lab">${esc(c.name)}<small>${c.count} 個檔案</small></span><span>${fmtSize(c.bytes)}</span></div>`).join('')+(cleanupPlan.examples.length?`<div class="row"><span class="lab"><small style="white-space:normal">檔案範例：${cleanupPlan.examples.map(esc).join('、')}</small></span></div>`:'');$('#sys_clean').disabled=!cleanupPlan.count});
$('#sys_clean').onclick=()=>{if(!cleanupPlan)return;$('#cleanreview').textContent=`將清理 ${cleanupPlan.count} 個暫存檔，預計釋放約 ${fmtSize(cleanupPlan.bytes)}。`;$('#cleanmodal').classList.add('on');$('#clean_cancel').focus()};$('#clean_cancel').onclick=()=>$('#cleanmodal').classList.remove('on');$('#clean_confirm').onclick=()=>waiting($('#clean_confirm'),async()=>{if(!cleanupPlan)return;const r=await call('cleanup_execute',cleanupPlan.token);cleanupPlan=null;$('#sys_clean').disabled=true;$('#cleanmodal').classList.remove('on');$('#sys_preview').innerHTML=`<div class="row"><span class="lab">已清理 ${r.removed} 個檔案<small>${r.skipped} 個項目已變動或無法刪除，已跳過</small></span><b>${fmtSize(r.bytes)}</b></div>`;toast('清理完成，釋放 '+fmtSize(r.bytes))});


/* ---------- computer health check ---------- */
const HC_STAGES=['認識你的電腦硬體','檢查設備是否能正常使用','測試電腦的運算能力','檢查長時間使用的穩定性','整理完整健康報告'];
const HC_COLOR={ok:'var(--green)',warn:'var(--orange)',bad:'var(--red)',partial:'var(--blue)',untested:'var(--gray)'};
let hcLevel='normal',hcJob='',hcShown='',hcData=null,hcTab='overview',hcOpen={};
const hcSt=(st,t)=>`<span class="hc-st hc-${st}">${esc(t)}</span>`;
$('#hc_level').onclick=e=>{const v=e.target.dataset.v;if(!v)return;hcLevel=v;setSeg('#hc_level',v);$('#hc').classList.toggle('pro',v=='pro');if(hcData){hcTab=v=='pro'?'pro':'overview';hcRender()}};
$('#hc_go').onclick=()=>waiting($('#hc_go'),async()=>{const pro=hcLevel=='pro';const o={mode:pro?'pro':$('#hc_mode').value,network:$('#hc_net').checked};if(pro){o.stress=+$('#hc_stress').value;o.mem_mb=+$('#hc_mem').value}
 let ids;try{ids=await API.health_check(o)}catch(e){const m=String(e.message||e).replace(/^.*?Error:\s*/,'');if(/沒有這個功能/.test(m))hcOutdated();else toast(m,1);return}hcJob=ids&&ids[0]||'';hcShown='';hcData=null;$('#hc_result').style.display='none';hcProgress({state:'queued',progress:0,msg:''});poll()});
function hcOutdated(){const box=$('#hc_progress');box.style.display='';$('#hc_go').disabled=true;
 box.innerHTML=`<div class="row"><span class="lab" style="white-space:normal"><b>背景元件還是舊版，暫時不能做健康檢查</b><small style="white-space:normal">畫面已經更新，但正在執行的背景元件 swbd-core.exe 是 ${esc(window.CORE_VER||'更新前')} 版，還沒有健康檢查。請關閉四維八德，執行 _build\\部署最新候選版.ps1 換上已通過測試的新版，再重新開啟。</small></span></div>`}
function hcProgress(j){const box=$('#hc_progress');box.style.display='';const n=j.state=='queued'?-1:Math.min(4,Math.floor((j.progress||0)*5));const detail=(j.msg||'').split(' · ')[1]||'';
 box.innerHTML=`<div class="row"><b class="lab">${n<0?'等待開始…':`第 ${n+1} / 5 階段`}<small>${n<0?'':esc(HC_STAGES[n])}</small></b><button class="btn plain" id="hc_stop">停止檢查</button></div>`+
  HC_STAGES.map((t,i)=>`<div class="hc-stage ${i<n?'done':i==n?'now':'wait'}"><i>${i<n?'✓':''}</i><div>${esc(t)}${i==n&&detail?`<small>${esc(detail)}</small>`:''}</div></div>`).join('');
 $('#hc_stop').onclick=()=>{if(hcJob)waiting($('#hc_stop'),()=>call('cancel',hcJob))}}
async function hcShow(j){hcShown=j.id;$('#hc_progress').style.display='none';try{hcData=await call('health_report',j.output);hcData._txt=j.output;hcTab=hcLevel=='pro'?'pro':'overview';hcOpen={};hcRender()}catch(e){}}
function hcWatch(js){const hc=[...js].reverse().find(j=>j.kind=='health_check');if(!hc)return;if(!hcJob)hcJob=hc.id;if(hc.id!=hcJob)return;
 if(hc.state=='queued'||hc.state=='running')hcProgress(hc);
 else if(hc.output&&hc.id!=hcShown)hcShow(hc);
 else if(!hc.output&&hc.id!=hcShown){hcShown=hc.id;$('#hc_progress').innerHTML=`<div class="row"><span class="lab ${hc.state=='error'?'err':''}">${esc(hc.state=='cancelled'?'檢查已停止':hc.msg||'檢查沒有完成')}</span></div>`}}
function hcRender(){const r=hcData,box=$('#hc_result');if(!r)return;box.style.display='';const c=r.counts,issues=c.warn+c.bad,partial=c.untested+c.partial;
 const top=r.cancelled?'untested':c.bad?'bad':c.warn?'warn':'ok';
 const head=`<div class="group"><div class="hc-head"><div class="hc-big" style="background:${HC_COLOR[top]}">${top=='ok'?'✓':'!'}</div><div style="flex:1;min-width:0"><h3>${esc(r.title)}</h3><p>${esc(r.lead)}</p>
  <div class="hc-counts">${hcSt('ok',c.ok+' 項正常')}${issues?hcSt(c.bad?'bad':'warn',issues+' 項需要處理'):''}${partial?hcSt('untested',partial+' 項未完整測試'):''}</div>
  <div class="gfoot" style="margin:8px 0 0">${esc(r.created)} · ${esc(r.mode_name)} · 費時 ${Math.max(1,Math.round(r.duration/60))} 分鐘</div></div></div>
  <div class="row"><div class="seg" id="hc_tabs" style="flex:1"><button data-v="overview">電腦總覽</button><button data-v="explain">問題解釋</button><button data-v="pro">專業資料</button></div></div></div>`;
 box.innerHTML=head+`<div class="group" style="margin-top:12px" id="hc_body">${hcTab=='overview'?hcOverview(r):hcTab=='explain'?hcExplain(r):hcPro(r)}</div>
  <div class="hc-act"><button class="btn tint" data-hcopen="${esc(r._txt)}">開啟文字報告</button>${hcLevel=='pro'?`<button class="btn plain" data-hcopen="${esc(r._txt.replace(/\.txt$/,'.json'))}">開啟原始資料（JSON）</button>`:''}<button class="btn plain" id="hc_again">重新檢查</button></div>`;
 setSeg('#hc_tabs',hcTab)}
$('#hc_result').onclick=e=>{const t=e.target.closest('[data-v]');if(t&&t.closest('#hc_tabs')){hcTab=t.dataset.v;hcRender();return}
 const o=e.target.closest('[data-hcopen]');if(o){waiting(o,()=>call('open_file',o.dataset.hcopen));return}
 if(e.target.closest('#hc_again')){$('#hc_go').scrollIntoView({behavior:'smooth',block:'center'});$('#hc_go').focus();return}
 if(e.target.closest('#hc_memdiag')){call('memory_diagnostic');return}
 const it=e.target.closest('[data-hcitem]');if(it){hcTab='explain';hcRender();const el=$('#hc_x_'+it.dataset.hcitem);if(el)el.scrollIntoView({behavior:'smooth',block:'start'});return}
 const w=e.target.closest('[data-hcwhy]');if(w){const [i,k]=w.dataset.hcwhy.split(':');hcOpen[i]=hcOpen[i]==k?'':k;hcRender();const el=$('#hc_x_'+i);if(el)el.scrollIntoView({block:'nearest'})}};
function hcOverview(r){return r.items.map(i=>`<div class="row click" data-hcitem="${esc(i.id)}" style="cursor:pointer"><span class="lab"><b>${esc(i.name)}</b><small style="white-space:normal">${esc(i.headline)}</small></span>${hcSt(i.state,i.state_text)}</div>`).join('')+
 `<div class="row"><span class="lab"><small style="white-space:normal">點任何一項可以看白話解釋。「未測試」代表這次沒有量到，不代表正常。</small></span></div>`}
function hcExplain(r){const order={bad:0,warn:1,partial:2,untested:3,ok:4};const items=[...r.items].sort((a,b)=>order[a.state]-order[b.state]);
 return items.map(i=>{const open=hcOpen[i.id];const cs=i.causes||[];const pick=open!==undefined&&open!==''?cs[+open]:null;
  return `<div class="hc-card" id="hc_x_${esc(i.id)}"><h4>${esc(i.name)} ${hcSt(i.state,i.state_text)}</h4><div style="margin-top:4px"><b>${esc(i.headline)}</b></div>
  <div class="k">這是什麼？</div><div>${esc(i.explain)}</div>
  ${i.finding?`<div class="k">這次發現</div><div>${esc(i.finding)}</div>`:''}
  ${i.impact?`<div class="k">會造成什麼影響？</div><div>${esc(i.impact)}</div>`:''}
  ${i.advice&&i.advice.length?`<div class="k">建議怎麼做</div><ol>${i.advice.map(a=>`<li>${esc(a)}</li>`).join('')}</ol>`:''}
  ${i.id=='ram'&&i.state!='ok'?`<div style="margin-top:6px"><button class="btn tint" id="hc_memdiag">開啟 Windows 記憶體診斷</button></div>`:''}
  ${cs.length&&i.state!='ok'?`<div class="k">你想先了解哪個可能原因？</div><div class="hc-why">${cs.map((c,k)=>`<button class="${open==String(k)?'on':''}" data-hcwhy="${esc(i.id)}:${k}">${esc(c.title)}<em class="${c.evidence?'y':''}">${c.evidence?'有證據':c.evidence===false?'未發現證據':'無法判斷'}</em></button>`).join('')}</div>
   ${pick?`<div class="hc-ans"><b>${esc(pick.title)}，會怎麼影響電腦？</b><div>${esc(pick.plain)}</div><div class="k">這次量到的</div><div>${esc(pick.finding)}</div><div class="k">下一步</div><div>${esc(pick.next)}</div></div>`:''}
   <div class="gfoot">「有證據」代表這次量測真的找到相關跡象；只靠你的選擇不會認定故障。</div>`:''}
  ${i.not_tested&&i.not_tested.length?`<div class="k">沒有測到的部分</div><div class="mute small">${i.not_tested.map(esc).join('<br>')}</div>`:''}</div>`}).join('')}
function hcChart(samples){const pts=(samples||[]).filter(s=>s.perf!=null||s.temp!=null);if(pts.length<3)return '<div class="hc-card"><div class="mute small">這台電腦沒有提供處理器速度或溫度的即時資料，所以沒有時間軸。</div></div>';
 const W=700,H=220,L=44,R=46,T=14,B=30,t0=pts[0].t,t1=Math.max(1,pts[pts.length-1].t-t0),x=t=>L+(W-L-R)*(t-t0)/t1;const pmax=Math.max(120,...pts.map(s=>s.perf||0));
 const yp=v=>T+(H-T-B)*(1-v/pmax),yt=v=>T+(H-T-B)*(1-(Math.min(110,Math.max(20,v))-20)/90),hasT=pts.some(s=>s.temp!=null);
 const line=(k,f)=>pts.filter(s=>s[k]!=null).map((s,i)=>`${i?'L':'M'}${x(s.t).toFixed(1)} ${f(s[k]).toFixed(1)}`).join('');const st=pts.filter(s=>s.phase=='stress');
 const band=st.length?`<rect x="${x(st[0].t)}" y="${T}" width="${Math.max(1,x(st[st.length-1].t)-x(st[0].t))}" height="${H-T-B}" fill="var(--fill2)"/><text x="${x(st[0].t)+4}" y="${H-B-6}">持續負載</text>`:'';
 const grid=[0,50,100].map(v=>`<line x1="${L}" x2="${W-R}" y1="${yp(v)}" y2="${yp(v)}" stroke="var(--sep)"/><text x="${L-6}" y="${yp(v)+4}" text-anchor="end">${v}%</text>`).join('');
 const tempAxis=hasT?[40,70,100].map(v=>`<text x="${W-R+6}" y="${yt(v)+4}">${v}°C</text>`).join(''):'';
 const ticks=[0,.25,.5,.75,1].map(f=>`<text x="${x(t0+t1*f)}" y="${H-10}" text-anchor="middle">${Math.round(t1*f/6)/10} 分</text>`).join('');
 return `<div class="hc-card"><div class="k" style="margin-top:0">處理器速度與溫度（同一條時間軸）</div><svg class="hc-chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="處理器速度與溫度的時間變化">${band}${grid}${tempAxis}${ticks}
  <path d="${line('perf',yp)}" fill="none" stroke="var(--blue)" stroke-width="2"/>${hasT?`<path d="${line('temp',yt)}" fill="none" stroke="var(--orange)" stroke-width="2"/>`:''}</svg></div>
  <div class="hc-legend"><span><b style="background:var(--blue)"></b>處理器速度（相對額定時脈 %）</span>${hasT?'<span><b style="background:var(--orange)"></b>溫度感測器 °C（ACPI 熱區，不一定是核心溫度）</span>':''}</div>`}
function hcPro(r){const tested=r.items.filter(i=>i.state!='untested').length;
 return hcChart(r.samples)+`<div class="hc-card"><div class="k" style="margin-top:0">測試覆蓋</div><div>${tested} / ${r.items.length} 個項目有實際量測 · ${esc(r.mode_name)} · ${r.system&&r.system.admin?'以系統管理員權限執行':'一般使用者權限（部分 SMART 計數無法讀取）'}</div></div>`+
 r.items.map(i=>`<div class="hc-card"><h4>${esc(i.name)} ${hcSt(i.state,i.state_text)}</h4>${i.pro&&i.pro.length?`<div class="hc-kv" style="margin-top:6px">${i.pro.map(([k,v])=>`<span>${esc(k)}</span><span>${esc(v)}</span>`).join('')}</div>`:''}
  ${(i.events||[]).slice(0,12).map(e=>`<div class="hc-ev">${esc(e.Time||'')} · ${esc(e.Provider||'')} #${esc(e.Id)} · ${esc((e.Message||'').slice(0,160))}</div>`).join('')}
  ${i.not_tested&&i.not_tested.length?`<div class="hc-ev">未測試：${i.not_tested.map(esc).join('；')}</div>`:''}</div>`).join('')}
/* ---------- boot ---------- */
window.addEventListener('pywebviewready',async()=>{API=window.pywebview.api;const r=await API.init();S=r.settings;TS=r.tools;
 PC=r.pc||{};$('#aver').textContent='版本 '+(r.version||'');window.CORE_VER=r.version||'';if(!/^(2\.3\.([4-9]|\d\d)|2\.([4-9]|\d\d)\.|[3-9]\.)/.test(window.CORE_VER))hcOutdated();$('#aed').textContent=(r.edition||'開源版')+'・免費・沒有期限';document.title='四維八德（'+(r.edition||'開源版')+'）';if(!S.welcomed)setTimeout(()=>about(true),400);if(!['auto','light','dark'].includes(S.theme))S.theme='auto';theme();presetUI();outUI();
 sw('hw',S.hwaccel);sw('fastcopy',S.fastcopy!==false);sw('loudnorm',S.loudnorm);$('#finsel').value=S.finish||'sound';
 if(S.qmin){$('#activity').classList.add('min');$('#amin').style.transform='rotate(180deg)'}
 if((S.dl||{}).out_dir)$('#d_dir').textContent=S.dl.out_dir;if(S.dl){if(S.dl.quality)$('#d_q').value=S.dl.quality;sw('d_subs',S.dl.subs);sw('d_pl',S.dl.playlist);if(S.dl.thumb===false)sw('d_thumb',false)}
 if(r.missing&&r.missing.length)toast('缺少內建元件：'+r.missing.map(m=>m.name+'（'+m.use+'）').join('、')+'。請重新安裝完整版本',1);
 if(!r.ytdlp){$('#d_go').disabled=true;$('#d_msg').innerHTML='<span class="warn">缺少下載元件（tools\\yt-dlp.exe）</span>'}
 const hwc=hw=>$('#hwchip').innerHTML=`<i style="${hw&&!hw.length?'background:var(--gray)':''}"></i>${hw==null?'偵測顯示卡中…':hw.length?'硬體加速：'+hw.join('、'):'使用 CPU 轉檔'}`;
 const hp=async()=>{const hw=await API.hwinfo();hwc(hw);if(hw==null)setTimeout(hp,800)};hp();
 const st=await API.startup_files();const valid=['pdfhub','workflow','convert','rec','dl','auto','system',...TS.groups.map(g=>g[0])];
 wfInit(r.workflows);$('#wf_video_size').value=PC.ram<=4.5?'480':'720';$('#resource_mode').value=S.resource_mode||'auto';$('#aver').textContent+=' · '+PC.system+' · '+PC.ram+' GB RAM · '+PC.cores+' 執行緒';if(PC.emulated)toast('目前在 ARM 的 x64 模擬環境執行，部分硬體加速尚未驗證',1);$('#codec').value=S.codec||'auto';$('#verify_full').checked=!!S.verify_full;go(st.length?'convert':valid.includes(S.tab)?S.tab:'workflow');if(st.length)addFiles(st);render();poll()});
render();
