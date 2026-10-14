const config = window.FORM_CONFIG;
const $ = id => document.getElementById(id);
let soundEnabled = true, audioContext;
function chime() {
  if (!soundEnabled) return;
  try {
    audioContext ||= new (window.AudioContext || window.webkitAudioContext)();
    audioContext.resume();
    const oscillator = audioContext.createOscillator(), gain = audioContext.createGain();
    oscillator.connect(gain); gain.connect(audioContext.destination);
    oscillator.frequency.setValueAtTime(740, audioContext.currentTime);
    oscillator.frequency.exponentialRampToValueAtTime(990, audioContext.currentTime + .08);
    gain.gain.setValueAtTime(.045, audioContext.currentTime);
    gain.gain.exponentialRampToValueAtTime(.001, audioContext.currentTime + .15);
    oscillator.start(); oscillator.stop(audioContext.currentTime + .16);
  } catch (_) { /* Sound is optional on unsupported browsers. */ }
}
$('sound').onclick = () => { soundEnabled = !soundEnabled; $('sound').setAttribute('aria-pressed', String(soundEnabled)); $('sound').textContent = soundEnabled ? '♫ الصوت مفعّل' : '♫ الصوت مغلق'; chime(); };
const steps = config.steps;
const questions = steps.flatMap(s => s.questions);
let current = 0;
const answers = {};
$('form-title').textContent = config.title;
$('form-description').textContent = config.description;
$('setup-note').hidden = true;
if(config.submissionMode !== 'server'){
  $('send').textContent='إرسال الإجابات عبر واتساب ↗';
  document.querySelector('#summary .privacy').textContent='يفتح واتساب برسالة تحتوي إجاباتك كاملة. اضغط إرسال داخل واتساب لمشاركتها مع الدكتورة.';
  document.querySelector('.form-card > .privacy').textContent='إجاباتك لا تُحفظ على خادم في هذه النسخة؛ تُشارك مع الدكتورة عبر واتساب باختيارك.';
}
function node(tag, text) { const el=document.createElement(tag); if(text !== undefined) el.textContent=text; return el; }
function capture() {
  const data = new FormData($('consultation-form'));
  for(const q of steps[current].questions) { answers[q.id] = data.getAll(q.id); answers[q.id+'_detail'] = data.get(q.id+'_detail') || ''; }
}
function render(focus=false) {
  $('questions').replaceChildren(); $('step-nav').replaceChildren();
  steps.forEach((s,i)=>{ const mark=node('span', `${i+1} · ${s.title}`); mark.className=i===current?'active':i<current?'done':''; if(i===current) mark.setAttribute('aria-current','step'); $('step-nav').append(mark); });
  $('step-title').textContent=steps[current].title;
  $('cheer').textContent=steps[current].cheer;
  $('progress-label').textContent=`الخطوة ${current+1} من ${steps.length}`;
  $('progress-bar').style.width=`${(current+1)/steps.length*100}%`;
  $('back').hidden=current===0;
  $('review').textContent=current===steps.length-1?'مراجعة الإجابات ✓':'التالي ←';
  $('form-error').hidden=true;
  for(const q of steps[current].questions) {
    const group=node('fieldset'); group.className='field'; group.dataset.question=q.id;
    const legend=node('legend',q.title); const star=node('span',' *'); star.className='required'; legend.append(star); group.append(legend);
    if(q.type==='radio'||q.type==='checkbox') {
      for(const value of q.options) {
        const label=node('label'); label.className='option'; const input=node('input'); input.type=q.type; input.name=q.id; input.value=value; input.checked=(answers[q.id]||[]).includes(value); input.required=q.type==='radio'; label.append(input,node('span',value)); group.append(label);
      }
    } else {
      const input=node(q.type==='textarea'?'textarea':'input'); if(q.type!=='textarea') input.type=q.type;
      input.name=q.id; input.id=q.id; input.required=true; input.setAttribute('aria-label',q.title); input.value=(answers[q.id]||[''])[0];
      if(q.type==='number'){input.min='1'; input.max=q.id==='q2'?'120':q.id==='q6'?'300':'600'; input.step='any'; input.inputMode='decimal';}
      if(q.type==='tel'){input.inputMode='tel';input.pattern='[+0-9٠-٩۰-۹ ()-]{8,20}'; input.dir='ltr';}
      group.append(input);
    }
    if(q.other||q.id==='q21'||q.id==='q18') {
      const detail=node('textarea'); detail.name=q.id+'_detail';detail.setAttribute('aria-label','اذكر التفاصيل');detail.placeholder='اذكر التفاصيل هنا';detail.value=answers[q.id+'_detail']||'';group.append(detail);
    }
    $('questions').append(group);
  }
  syncValidation();
  if(focus){$('step-title').focus({preventScroll:true});$('form-title').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'start'});}
}
function syncValidation() {
  for(const q of steps[current].questions) {
    const group=document.querySelector(`[data-question="${q.id}"]`);
    const inputs=[...group.querySelectorAll('input')];
    if(q.type==='checkbox') inputs[0].setCustomValidity(inputs.some(i=>i.checked)?'':'اختار إجابة واحدة على الأقل');
    for(const input of group.querySelectorAll('input[type=text],textarea')) input.setCustomValidity(input.required&&!input.value.trim()?'اكتب إجابة قبل المتابعة':'');
    const detail=group.querySelector(`[name="${q.id}_detail"]`);
    if(detail) {
      const chosen=inputs.filter(i=>i.checked).map(i=>i.value);
      const needed=chosen.includes('أخرى')||chosen.includes('كربوهيدرات أخرى أستخدمها بشكل متكرر')||(q.id==='q21'&&chosen.includes('نعم'));
      detail.hidden=!needed; detail.disabled=!needed; detail.required=needed;
      detail.setCustomValidity(needed&&!detail.value.trim()?'اذكر التفاصيل قبل المتابعة':'');
    }
  }
}
$('consultation-form').addEventListener('input',syncValidation);
$('consultation-form').addEventListener('change',e=>{
  const group=e.target.closest('.field');
  if(e.target.type==='checkbox'&&group) {
    const boxes=[...group.querySelectorAll('input[type=checkbox]')];
    if(e.target.checked&&e.target.value==='لا يوجد') boxes.forEach(b=>{if(b!==e.target)b.checked=false;});
    else if(e.target.checked) boxes.forEach(b=>{if(b.value==='لا يوجد')b.checked=false;});
  }
  syncValidation();chime();
});
$('back').onclick=()=>{capture();current--;render(true);chime();};
function allValues(){return questions.map(q=>({title:q.title,value:[...(answers[q.id]||[]),answers[q.id+'_detail']||''].filter(Boolean).join('، ')}));}
$('consultation-form').onsubmit=e=>{
  e.preventDefault();syncValidation();
  if(!$('consultation-form').reportValidity()){$('form-error').textContent='كمّل كل الإجابات المطلوبة علشان ننتقل للخطوة اللي بعدها.';$('form-error').hidden=false;return;}
  capture();chime();
  if(current<steps.length-1){current++;render(true);return;}
  $('answers').replaceChildren();for(const a of allValues()) $('answers').append(node('dt',a.title),node('dd',a.value));
  $('consultation-form').hidden=true;$('step-title').hidden=true;$('step-nav').hidden=true;$('summary').hidden=false;
  $('cheer').textContent='برافو عليك! جاهز تبدأ رحلة التغيير؟ 🎉';
  $('summary').setAttribute('tabindex','-1');$('summary').focus();
};
$('edit').onclick=()=>{$('summary').hidden=true;$('consultation-form').hidden=false;$('step-title').hidden=false;$('step-nav').hidden=false;current=0;render(true);};
$('send').onclick=async()=>{
  if(questions.some(q=>!answers[q.id]?.length))return;
  if(config.submissionMode !== 'server'){
    const message='استمارة متابعة تغذية — د. سمر صلاح أبو العين\n\n'+allValues().map(a=>a.title+'\n'+a.value).join('\n\n');
    window.open('https://wa.me/'+config.whatsapp+'?text='+encodeURIComponent(message),'_blank','noopener,noreferrer');
    $('submission-status').textContent='تم تجهيز إجاباتك. اضغط إرسال داخل واتساب لتصل للدكتورة؛ فتح واتساب وحده لا يرسل الرسالة.';return;
  }
  const button=$('send');button.disabled=true;button.textContent='جاري حفظ الاستمارة…';
  try {
    const response=await fetch('/api/submit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({answers})});
    const result=await response.json();if(!response.ok)throw Error(result.error||'تعذر حفظ الاستمارة');
    button.textContent='تم حفظ الاستمارة بنجاح ✓';$('edit').hidden=true;
    $('submission-status').textContent='شكرًا لمشاركتك! تم تسجيل إجاباتك للدكتورة. رقم الاستمارة: '+result.id;chime();
  }catch(error){button.disabled=false;button.textContent='إرسال الاستمارة';$('submission-status').textContent=error.message||'تعذر الإرسال، حاول مرة أخرى';}
};
render();
