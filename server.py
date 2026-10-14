"""Nutrition intake server. Python stdlib; durable SQLite and private doctor dashboard."""
import os,json,sqlite3,secrets,time,hashlib,hmac,urllib.request,urllib.error,re,threading
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from http.cookies import SimpleCookie
from collections import defaultdict,deque
ROOT=Path(__file__).parent
DB=Path(os.environ.get('DATA_DIR',str(ROOT/'data')))/'submissions.sqlite3'
PASSWORD=os.environ.get('ADMIN_PASSWORD','')
SESSION_KEY=os.environ.get('SESSION_SECRET','')
BASE=os.environ.get('PUBLIC_BASE_URL','').rstrip('/')
CONFIG=json.loads((ROOT/'form-config.js').read_text().split('=',1)[1].strip().rstrip(';'))
QUESTIONS=[q for s in CONFIG['steps'] for q in s['questions']]
RATE=defaultdict(deque);LOCK=threading.Lock()
def connection():
 c=sqlite3.connect(DB,timeout=10);c.row_factory=sqlite3.Row;return c
def initialize():
 DB.parent.mkdir(parents=True,exist_ok=True)
 with connection() as c:c.execute('CREATE TABLE IF NOT EXISTS submissions(id TEXT PRIMARY KEY, created INTEGER, answers TEXT, notification TEXT)')
def validate(data):
 if not isinstance(data,dict):raise ValueError('بيانات غير صالحة')
 cleaned=[]
 for q in QUESTIONS:
  v=data.get(q['id']);detail=data.get(q['id']+'_detail','')
  if not isinstance(v,list) or not v or len(v)>20 or any(not isinstance(x,str) or not x.strip() or len(x)>2000 for x in v):raise ValueError('أجب عن كل الأسئلة المطلوبة')
  if q['type']!='checkbox' and len(v)!=1:raise ValueError('اختر إجابة واحدة')
  if q.get('options') and any(x not in q['options'] for x in v):raise ValueError('اختيار غير صالح')
  if not isinstance(detail,str) or len(detail)>2000:raise ValueError('تفاصيل غير صالحة')
  needs='أخرى' in v or 'كربوهيدرات أخرى أستخدمها بشكل متكرر' in v or (q['id']=='q21' and 'نعم' in v)
  if needs and not detail.strip():raise ValueError('اذكر تفاصيل الاختيار')
  if q['type']=='number':
   try:n=float(v[0]);assert 0<n<=(120 if q['id']=='q2' else 300 if q['id']=='q6' else 600)
   except (ValueError,AssertionError):raise ValueError('قياس أو سن غير صالح')
  if q['type']=='tel' and not re.fullmatch(r'[+0-9٠-٩۰-۹ ()-]{8,20}',v[0]):raise ValueError('رقم هاتف غير صالح')
  cleaned.append({'title':q['title'],'value':'، '.join(v+([detail.strip()] if needs else []))})
 return cleaned
def notify(sid):
 token=os.environ.get('WHATSAPP_ACCESS_TOKEN');phone=os.environ.get('WHATSAPP_PHONE_NUMBER_ID');template=os.environ.get('WHATSAPP_TEMPLATE_NAME')
 if not all([token,phone,template,BASE]):return 'not_configured'
 payload={'messaging_product':'whatsapp','to':CONFIG['whatsapp'],'type':'template','template':{'name':template,'language':{'code':os.environ.get('WHATSAPP_TEMPLATE_LANGUAGE','ar')},'components':[{'type':'body','parameters':[{'type':'text','text':BASE+'/admin#'+sid}]}]}}
 req=urllib.request.Request('https://graph.facebook.com/'+os.environ.get('WHATSAPP_API_VERSION','v23.0')+'/'+phone+'/messages',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=15) as r:json.load(r)
  return 'accepted' # API acceptance does not prove delivery.
 except (urllib.error.URLError,ValueError):return 'failed'
def notify_async(sid):
 status=notify(sid)
 with connection() as c:c.execute('UPDATE submissions SET notification=? WHERE id=?',(status,sid))
def session():
 raw=str(int(time.time())+43200)+':'+secrets.token_hex(16)
 return raw+':'+hmac.new(SESSION_KEY.encode(),raw.encode(),hashlib.sha256).hexdigest()
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass # Never log clinical answers or credentials.
 def respond(self,status,data,ctype='application/json; charset=utf-8',cookie=None):
  blob=json.dumps(data,ensure_ascii=False).encode() if ctype.startswith('application/json') else data
  self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(blob)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer');self.send_header('X-Frame-Options','DENY')
  if cookie:self.send_header('Set-Cookie',cookie)
  self.end_headers();self.wfile.write(blob)
 def authenticated(self):
  if not PASSWORD or not SESSION_KEY:return False
  try:
   cookie=SimpleCookie(self.headers.get('Cookie',''));s=cookie['doctor_session'].value;expiry,nonce,signature=s.split(':');raw=expiry+':'+nonce
   return int(expiry)>time.time() and hmac.compare_digest(signature,hmac.new(SESSION_KEY.encode(),raw.encode(),hashlib.sha256).hexdigest())
  except (KeyError,ValueError):return False
 def do_GET(self):
  path=self.path.split('?',1)[0]
  if path=='/api/health':return self.respond(200,{'ok':True})
  if path=='/api/submissions':
   if not self.authenticated():return self.respond(401,{'error':'سجل الدخول أولًا'})
   with connection() as c:rows=c.execute('SELECT * FROM submissions ORDER BY created DESC LIMIT 200').fetchall()
   return self.respond(200,{'submissions':[dict(r,answers=json.loads(r['answers'])) for r in rows]})
  if path=='/admin':return self.respond(200,(ROOT/'admin.html').read_bytes(),'text/html; charset=utf-8')
  files={'/':'index.html','/index.html':'index.html','/app.js':'app.js','/form-config.js':'form-config.js','/style.css':'style.css','/assets/doctor.png':'assets/doctor.png'}
  if path not in files:return self.respond(404,{'error':'غير موجود'})
  f=ROOT/files[path];ctype='text/html; charset=utf-8' if f.suffix=='.html' else 'text/css' if f.suffix=='.css' else 'application/javascript; charset=utf-8' if f.suffix=='.js' else 'image/png'
  return self.respond(200,f.read_bytes(),ctype)
 def do_POST(self):
  origin=self.headers.get('Origin')
  if origin and origin!=BASE and origin not in ['http://'+self.headers.get('Host',''),'https://'+self.headers.get('Host','')]:return self.respond(403,{'error':'طلب غير مسموح'})
  with LOCK:
   now=time.time();bucket=RATE[self.client_address[0]]
   while bucket and bucket[0]<now-600:bucket.popleft()
   if len(bucket)>=20:return self.respond(429,{'error':'طلبات كثيرة، حاول بعد قليل'})
   bucket.append(now)
  try:
   length=int(self.headers.get('Content-Length','0'))
   if not 0<length<=100000:raise ValueError('حجم الطلب غير صالح')
   data=json.loads(self.rfile.read(length))
   if not isinstance(data,dict):raise ValueError('بيانات غير صالحة')
  except (ValueError,UnicodeDecodeError):return self.respond(400,{'error':'طلب غير صالح'})
  if self.path=='/api/login':
   if not PASSWORD or not SESSION_KEY:return self.respond(503,{'error':'لوحة الدكتورة تحتاج إعداد بيانات الدخول'})
   supplied=data.get('password','')
   if not isinstance(supplied,str) or not hmac.compare_digest(supplied.encode(),PASSWORD.encode()):return self.respond(401,{'error':'كلمة المرور غير صحيحة'})
   secure='; Secure' if BASE.startswith('https://') else ''
   return self.respond(200,{'ok':True},cookie='doctor_session='+session()+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200'+secure)
  if self.path=='/api/logout':return self.respond(200,{'ok':True},cookie='doctor_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
  if self.path!='/api/submit':return self.respond(404,{'error':'غير موجود'})
  try:answers=validate(data.get('answers'))
  except ValueError as e:return self.respond(400,{'error':str(e)})
  sid=secrets.token_urlsafe(18)
  with connection() as c:c.execute('INSERT INTO submissions VALUES(?,?,?,?)',(sid,int(time.time()),json.dumps(answers,ensure_ascii=False),'pending'))
  threading.Thread(target=notify_async,args=(sid,),daemon=True).start()
  return self.respond(201,{'id':sid,'saved':True})
if __name__=='__main__':
 initialize();ThreadingHTTPServer(('0.0.0.0',int(os.environ.get('PORT','8000'))),Handler).serve_forever()
