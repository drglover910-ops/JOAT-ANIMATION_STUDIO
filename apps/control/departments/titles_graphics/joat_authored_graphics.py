"""CPU-authored illustrative booking animations. Embedded file version1.0.1.
Produces real candidate MP4s, never a QC PASS or a claim of live booking integration.
Native worker integration and owner review remain separate.
"""
FILE_VERSION='1.0.1'
import hashlib,json,math,re,subprocess,tempfile
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
W,H,FPS=1024,576,24
FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
BOLD='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
BG='#10232c';WHITE='#f5f5ee';INK='#18323a';ACC='#94cdb6';MUT='#64777a'
def digest(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def font(size,bold=False):return ImageFont.truetype(BOLD if bold else FONT,size)
def ease(v):v=max(0,min(1,v));return 1-(1-v)**3

def validate(plan):
 if not isinstance(plan,dict) or set(plan)!={'schema','file_version','project_id','shot_id','mission_fingerprint','duration_seconds','title','subtitle','rows','mode','illustrative','plan_fingerprint'}:raise ValueError('Exact authored graphics plan required.')
 if plan['schema']!='joat.authored_graphics_plan.v1' or plan['file_version'] not in ('1.0.0',FILE_VERSION) or plan['illustrative'] is not True:raise ValueError('Illustrative source plan required.')
 if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,95}',plan['project_id']) or not re.fullmatch('SHOT-[0-9]{3}',plan['shot_id']) or not re.fullmatch('[a-f0-9]{64}',plan['mission_fingerprint']):raise ValueError('Invalid source context.')
 if plan['plan_fingerprint']!=digest({k:v for k,v in plan.items() if k!='plan_fingerprint'}):raise ValueError('Graphics source fingerprint mismatch.')
 duration=plan['duration_seconds']
 if isinstance(duration,bool) or not isinstance(duration,(int,float)) or not math.isfinite(duration) or not 1<=duration<=20 or abs(duration*FPS-round(duration*FPS))>0.0001:raise ValueError('Use1–20 seconds aligned to24fps.')
 if plan['mode'] not in ('messages','setup','booking','confirmation','link','reminders','exceptions','afterhours','cta','style001_workflow'):raise ValueError('Unsupported authored scene.')
 for key,limit in [('title',70),('subtitle',100)]:
  if not isinstance(plan[key],str) or not 1<=len(plan[key])<=limit:raise ValueError('Invalid graphics '+key)
 if not isinstance(plan['rows'],list) or not 1<=len(plan['rows'])<=3:raise ValueError('Use1–3 short screen rows.')
 for row in plan['rows']:
  if not isinstance(row,list) or len(row)!=3 or not isinstance(row[2],bool) or any(not isinstance(s,str) or not 1<=len(s)<=100 for s in row[:2]):raise ValueError('Invalid authored row.')
 if plan['mode']=='style001_workflow':
  expected={'title':'A simpler way to get booked.','subtitle':'Customer, calendar, confirmation and business workflow','rows':[['Appointments confirmed','Customer receives confirmation',True],['Reminders sent','Appointment reminder scheduled',True],['Customers informed','Business dashboard updated',True]]}
  if any(plan[k]!=value for k,value in expected.items()):raise ValueError('Use the exact reviewed workflow text; no ignored custom labels.')
  if (plan['file_version']!=FILE_VERSION or plan['project_id']!='PROJECT-OTU-STYLE001-90S-001' or plan['shot_id']!='SHOT-012' or plan['mission_fingerprint']!='2a881aa9651cd9058fd3f9ddaf199f1c2cbfc849b82caf511b1bcd661921868d' or duration!=6):raise ValueError('Use the exact approved portrait workflow shot and timing.')
 return plan

def textfit(draw,xy,text,max_width,size=24,fill=INK,bold=False):
 while size>12 and draw.textlength(text,font=font(size,bold))>max_width:size-=1
 if draw.textlength(text,font=font(size,bold))>max_width:raise ValueError('Text does not fit authored safe area.')
 draw.text(xy,text,font=font(size,bold),fill=fill)

def frame(plan,t):
 im=Image.new('RGB',(W,H),BG);d=ImageDraw.Draw(im)
 # Restrained editorial motion; all interfaces remain legible in the final hold.
 d.rectangle((0,0,W,5),fill=ACC)
 textfit(d,(60,30),'OTU  /  DIGITAL MARKETING GROUP',900,18,ACC,True)
 y=78+round(14*(1-ease(t/0.7)))
 textfit(d,(60,y),plan['title'],904,35,WHITE,True)
 textfit(d,(62,133),plan['subtitle'],900,20,'#bfd0cf')
 d.rounded_rectangle((52,188,972,510),radius=22,fill=WHITE)
 d.ellipse((76,207,83,214),fill='#bb7568');d.ellipse((91,207,98,214),fill='#c6aa69');d.ellipse((106,207,113,214),fill=ACC)
 textfit(d,(724,202),'KIANA / SALON',210,13,MUT,True)
 mode=plan['mode']
 if mode=='booking':
  textfit(d,(88,246),'Cut + finish',700,26,INK,True);textfit(d,(88,284),'45 minutes  /  Choose an available appointment',830,18,MUT)
  selected=t>=plan['duration_seconds']*.57
  for i,label in enumerate(('10:00','11:00','14:00')):
   x=88+i*280;chosen=selected and i==1;d.rounded_rectangle((x,332,x+245,390),radius=12,fill=ACC if chosen else '#e5ebe7',outline='#4a8d77' if chosen else '#cdd8d3',width=2);textfit(d,(x+74,348),label,150,22,INK,True)
  if selected:textfit(d,(92,432),'Selected: Tuesday at 11:00',700,22,INK,True)
  else:textfit(d,(92,432),'Only available times can be selected',800,19,MUT)
  progress=ease((t-plan['duration_seconds']*.28)/(plan['duration_seconds']*.27));cx=880+(475-880)*progress;cy=457+(363-457)*progress;d.polygon([(cx,cy),(cx+3,cy+25),(cx+10,cy+18),(cx+20,cy+16)],fill=INK)
 elif mode=='cta':
  textfit(d,(88,257),'Make it easy to do business with you.',830,29,INK,True)
  pulse=ease((t-.6)/.8);d.rounded_rectangle((88,335,936,413),radius=14,fill=ACC if pulse>.2 else '#dbe8df');textfit(d,(130,359),'Book Your Free Consultation',740,29,INK,True)
  textfit(d,(90,450),'OTU Digital Marketing Group',800,21,MUT)
 else:
  for i,(title,detail,positive) in enumerate(plan['rows']):
   a=ease((t-.2-i*.33)/.5);x=78+round(45*(1-a));y=237+i*85
   if a<=0:continue
   d.rounded_rectangle((x,y,x+866,y+72),radius=11,fill='#e7ede8');d.rounded_rectangle((x+12,y+14,x+17,y+57),radius=2,fill='#408570' if positive else '#ac7157');textfit(d,(x+34,y+9),title,804,21,INK,True);textfit(d,(x+34,y+39),detail,804,17,MUT)
  if mode=='confirmation' and t>.7:
   # Confirmation content already states the same11:00 slot selected in booking.
   d.ellipse((906,203,930,227),fill=ACC);d.line([(912,215),(917,220),(925,209)],fill=INK,width=3)
 textfit(d,(61,540),'Illustrative workflow  /  Availability, reminders and consent are configured for each business.',905,13,'#acc1bf')
 return im

def render(plan,directory=None):
 validate(plan)
 if plan['mode']=='style001_workflow':
  from joat_style001_workflow_graphics import render as workflow_render
  evidence,output,original_report=workflow_render(directory or tempfile.mkdtemp(prefix='joat-style001-graphics-'))
  media={key:evidence[key] for key in ('sha256','size_bytes','width','height','fps','decoded_frames','duration_seconds','audio_present')};media['video_fully_decoded']=True
  result=dict(schema='joat.authored_graphics_candidate.v1',file_version=FILE_VERSION,project_id=plan['project_id'],shot_id=plan['shot_id'],source_kind='authored_motion_graphics',source_plan=plan,media_evidence=media,status='awaiting_independent_review',illustrative=True,gpu_called=False,production_qc_approved=False,delivery_authorized=False,native_preset='style001_workflow_v1',source_prompt_sha256=evidence['source_prompt_sha256'])
  result['candidate_fingerprint']=digest(result);report=Path(output).parent/'native_candidate_review.json';report.write_text(json.dumps(result,indent=2));return result,output,str(report)
 out=Path(directory or tempfile.mkdtemp(prefix='joat-authored-graphics-'));out.mkdir(parents=True,exist_ok=True);target=out/(plan['shot_id']+'.mp4')
 if target.exists():raise ValueError('Authored output already exists; preserve existing candidate.')
 frames=round(plan['duration_seconds']*FPS)
 cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pixel_format','rgb24','-video_size',f'{W}x{H}','-framerate',str(FPS),'-i','pipe:0','-an','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(target)]
 with tempfile.TemporaryFile() as err:
  process=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=err)
  try:
   for i in range(frames):process.stdin.write(frame(plan,i/FPS).tobytes())
   process.stdin.close();code=process.wait(timeout=120)
  except BaseException:
   process.kill();process.wait();raise
  if code:raise ValueError('CPU graphics encoding failed.')
 # Full decode counts actual frames; do not trust only metadata.
 import av
 with av.open(str(target)) as container:
  stream=container.streams.video[0];count=sum(1 for _ in container.decode(stream));rate=float(stream.average_rate);width,height=stream.width,stream.height
 if count!=frames or rate!=FPS or (width,height)!=(W,H):raise ValueError('Actual authored MP4 differs from its plan.')
 evidence=dict(sha256=hashlib.sha256(target.read_bytes()).hexdigest(),size_bytes=target.stat().st_size,width=width,height=height,fps=rate,decoded_frames=count,duration_seconds=count/rate,video_fully_decoded=True,audio_present=False)
 result=dict(schema='joat.authored_graphics_candidate.v1',file_version=FILE_VERSION,project_id=plan['project_id'],shot_id=plan['shot_id'],source_kind='authored_motion_graphics',source_plan=plan,media_evidence=evidence,status='awaiting_independent_review',illustrative=True,gpu_called=False,production_qc_approved=False,delivery_authorized=False)
 result['candidate_fingerprint']=digest(result);report=out/(plan['shot_id']+'_candidate.json');report.write_text(json.dumps(result,indent=2));return result,str(target),str(report)
