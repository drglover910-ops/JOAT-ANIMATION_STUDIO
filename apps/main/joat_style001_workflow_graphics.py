"""Style001 shot012: authored portrait workflow animation, CPU only. Version1.0.0.
Illustrative interface, not evidence of a live booking transaction. No film QC grant.
"""
FILE_VERSION='1.0.0'
import hashlib,json,math,subprocess,sys
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
W,H,FPS,SECONDS=576,1024,24,6
FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
BOLD='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
def font(size,bold=False):return ImageFont.truetype(BOLD if bold else FONT,size)
def ease(x):x=max(0,min(1,x));return x*x*(3-2*x)
def frame(t):
 im=Image.new('RGB',(W,H));d=ImageDraw.Draw(im)
 for y in range(H):
  a=y/H;d.line((0,y,W,y),fill=(8+int(3*a),16+int(10*a),29+int(11*a)))
 # Fine grid, warm highlights and a restrained camera drift.
 for x in range(-60,W+60,48):d.line((x,0,x+50,H),fill='#112b3b')
 for y in range(0,H,48):d.line((0,y,W,y),fill='#112534')
 d.text((42,72),'OTU',font=font(34,True),fill='#dfbd74')
 d.text((42,116),'DIGITAL MARKETING GROUP',font=font(13),fill='#a6b7c5')
 d.text((42,181),'A simpler way',font=font(32,True),fill='#f0f4f8')
 d.text((42,222),'to get booked.',font=font(32,True),fill='#f0f4f8')
 nodes=[('CUSTOMER','Booking request',0.0),('CALENDAR','Available time selected',1.0),('CONFIRMATION','Appointment confirmed',2.1),('BUSINESS','Reminder scheduled',3.2)]
 shift=round(7*math.sin(t*.38));centers=[(81,366+i*126+shift) for i in range(4)]
 for i in range(3):
  x,y=centers[i];end=centers[i+1][1]-31;d.line((x,y+31,x,end),fill='#1c4658',width=2)
  p=ease((t-(i*.95+.7))/.8)
  if p:
   d.line((x,y+31,x,round(y+31+(end-y-31)*p)),fill='#43d6e6',width=3)
   cy=y+31+(end-y-31)*p;d.ellipse((x-4,cy-4,x+4,cy+4),fill='#c1fbff')
 for i,(label,detail,start) in enumerate(nodes):
  x,y=centers[i];progress=ease((t-start)/.65);active=progress>.8
  d.rounded_rectangle((115,y-40,534,y+43),radius=14,fill='#102a3e',outline='#33677d' if active else '#1b3a4c',width=1)
  d.ellipse((x-29,y-29,x+29,y+29),fill='#102a3e',outline='#dfbd74' if active else '#325063',width=2)
  color='#dfbd74' if active else '#78909e'
  if i==0:
   d.ellipse((x-7,y-14,x+7,y),outline=color,width=2);d.arc((x-14,y-1,x+14,y+23),180,360,fill=color,width=2)
  elif i==1:
   d.rounded_rectangle((x-12,y-12,x+12,y+13),radius=3,outline=color,width=2);d.line((x-12,y-5,x+12,y-5),fill=color,width=2)
   for a,b in [(-6,1),(1,1),(8,1),(-6,7),(1,7),(8,7)]:d.rectangle((x+a-1,y+b-1,x+a+1,y+b+1),fill=color)
  elif i==2:
   d.rounded_rectangle((x-14,y-10,x+14,y+9),radius=3,outline=color,width=2);d.line((x-8,y+9,x-8,y+16,x,y+9),fill=color,width=2)
  else:
   for j,bar in enumerate([8,17,25]):d.rectangle((x-12+j*9,y+12-bar,x-7+j*9,y+12),fill=color)
  d.text((133,y-24),label,font=font(12,True),fill='#69d4e0' if active else '#8296a8')
  d.text((133,y-1),detail,font=font(17,True),fill='#f0f4f8' if active else '#91a3b3')
  if active:d.line((510,y-3,515,y+2,523,y-7),fill='#dfbd74',width=2)
 d.line((42,889,534,889),fill='#294552')
 d.text((42,911),'BOOKING • CONFIRMATIONS • REMINDERS',font=font(12,True),fill='#dfbd74')
 d.text((42,947),'Illustrative workflow',font=font(12),fill='#93a8b8')
 d.text((42,966),'Availability and reminders are configured per business.',font=font(10),fill='#93a8b8')
 return im

def render(directory):
 out=Path(directory);out.mkdir(parents=True,exist_ok=True);target=out/'SHOT-012_WORKFLOW.mp4'
 if target.exists():raise ValueError('Preserve existing candidate instead of rendering again.')
 cmd=['ffmpeg','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','pipe:0','-an','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(target)]
 process=subprocess.Popen(cmd,stdin=subprocess.PIPE)
 try:
  for index in range(FPS*SECONDS):process.stdin.write(frame(index/FPS).tobytes())
  process.stdin.close();code=process.wait(timeout=90)
 except BaseException:process.kill();process.wait();raise
 if code:raise ValueError('CPU workflow encoding failed.')
 frame(4.9).save(out/'workflow_review.png')
 import av
 with av.open(str(target)) as container:
  stream=container.streams.video[0];count=sum(1 for _ in container.decode(stream))
  if (stream.width,stream.height,float(stream.average_rate),count)!=(W,H,FPS,FPS*SECONDS):raise ValueError('Encoded workflow does not match exact approved geometry and duration.')
 result={'schema':'joat.style001_workflow_candidate.v1','file_version':FILE_VERSION,'project_id':'PROJECT-OTU-STYLE001-90S-001','shot_id':'SHOT-012','source_prompt_sha256':'1aee010f5c991fd25ed48245b7fbbd9271232c8dc4e9ebd90616db245aa2329b','approved_timing_adjustment':True,'width':W,'height':H,'fps':FPS,'decoded_frames':count,'duration_seconds':SECONDS,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'size_bytes':target.stat().st_size,'gpu_called':False,'audio_present':False,'narration_required':'Appointments confirmed. Reminders sent. Customers informed.','music_and_sound_design_pending':True,'illustrative':True,'production_qc_approved':False,'final_film':False}
 report=out/'workflow_candidate_v1.0.0.json';report.write_text(json.dumps(result,indent=2))
 return result,str(target),str(report)
if __name__=='__main__':print(json.dumps(render(sys.argv[1])[0]))
