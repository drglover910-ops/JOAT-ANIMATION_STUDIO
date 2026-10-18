"""CPU-only inspection of the existing native I2V graph. File version 1.0.4."""
FILE_VERSION='1.0.4'
import inspect,math,ast,operator

PROFILE='__joat_controlled_composed_i2v_v1__'
def configure_graph(workflow,width,height,frames):
 if any(k.startswith('msr_') for k in workflow):raise ValueError('Controlled I2V cannot use MSR nodes')
 if workflow.get('534',{}).get('class_type')!='EmptyLTXVLatentVideo' or workflow.get('532',{}).get('class_type')!='ResizeImageMaskNode':raise ValueError('Native I2V template changed')
 workflow['534']['inputs'].update(width=width,height=height,length=frames)
 workflow['532']['inputs'].update({'resize_type':'scale by multiplier','resize_type.multiplier':1.0})
 workflow['596']['inputs']['av_latent']=['510',1]
 workflow['597']['inputs']['frame_rate']=24
 for node in workflow.values():
  if node.get('class_type')=='LTXVConditioning':node['inputs']['frame_rate']=24
  if node.get('class_type')=='LTXVEmptyLatentAudio':node['inputs'].update(frames_number=frames,frame_rate=24)
 return workflow

def build_graph(context,width,height,seconds):
 for value in (width,height):
  if type(value)is not int or not 64<=value<=2048 or value%32:raise ValueError('Unsupported controlled I2V dimensions')
 if isinstance(seconds,bool) or not math.isfinite(seconds) or not 1<=seconds<=12:raise ValueError('Unsupported shot duration')
 frames=context['_safe_frames'](seconds)
 inject=context['_inject_params'];kw={}
 for name,param in inspect.signature(inject).parameters.items():
  if name.endswith(('_lora_strength','_audio_strength')):kw[name]=0.0
 kw.update(preset='original',image_name='joat-i2v-preflight.png',prompt='CPU graph inspection',negative_prompt='',seed=21,width=width,height=height,frames=frames,mode='anchor only',face_bbox='',likeness_strength=.65,likeness_anchor_strength=.08,latent_anchor_strength=.08,first_frame_strength=.82,msr_enabled=False,msr_lora_strength=0,skip_refine=True,user_lora_files=[],sigma_string=context['_SIGMA_TUNED'])
 return configure_graph(inject(context['_workflow_template'](),**kw),width,height,frames),frames

def check_graph(workflow,mappings,width,height,frames,image_name='joat-i2v-preflight.png'):
 from joat_graph_contract import _registered,_input_specs,_is_link,_validate_literal
 if any(k.startswith('msr_') for k in workflow):raise ValueError('Unexpected MSR nodes in single-image graph')
 expected={'534':'EmptyLTXVLatentVideo','548':'LTXVConcatAVLatent','596':'LTXVSeparateAVLatent','740':'VAEDecode','597':'VHS_VideoCombine','834':'LoadImage'}
 checked=[]
 for key,kind in expected.items():
  node=workflow.get(key,{})
  if node.get('class_type')!=kind:raise ValueError('Unexpected I2V node '+key)
  _,schema,_=_registered(mappings,kind);values=node.get('inputs',{});required,specs=_input_specs(schema,values,kind)
  if any(name not in values for name in required):raise ValueError('Missing required I2V node input '+kind)
  for name,value in values.items():
   if name not in specs:continue
   if _is_link(value):
    other=workflow.get(value[0]);outputs=_registered(mappings,other['class_type'])[2] if other else ()
    if not 0<=value[1]<len(outputs):raise ValueError('Invalid I2V connection output')
    wanted=specs[name][0]
    if isinstance(wanted,str) and '*' not in wanted and '*' not in str(outputs[value[1]]) and not set(wanted.split(',')).intersection(str(outputs[value[1]]).split(',')):raise ValueError('I2V connection type mismatch')
   elif kind=='LoadImage' and name=='image':
    if value!=image_name:raise ValueError('Unexpected I2V placeholder')
   else:_validate_literal(value,specs[name],kind+'.'+name)
  checked.append(kind)
 def literal(value,depth=0):
  if depth>8:raise ValueError('Unsupported I2V dimension dependency')
  if not _is_link(value):return value
  values=workflow[value[0]]['inputs']
  if 'value' in values:return literal(values['value'],depth+1)
  if 'expression' in values:
   expression=values['expression']
   if not isinstance(expression,str) or len(expression)>200:raise ValueError('Unsupported I2V dimension expression')
   operations={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv,ast.FloorDiv:operator.floordiv,ast.Mod:operator.mod}
   def arithmetic(node):
    if isinstance(node,ast.Constant) and type(node.value) in (int,float):return node.value
    if isinstance(node,ast.Name) and node.id in values:return literal(values[node.id],depth+1)
    if isinstance(node,ast.BinOp) and type(node.op) in operations:return operations[type(node.op)](arithmetic(node.left),arithmetic(node.right))
    if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.USub,ast.UAdd)):return -arithmetic(node.operand) if isinstance(node.op,ast.USub) else arithmetic(node.operand)
    raise ValueError('Unsupported I2V dimension arithmetic')
   result=arithmetic(ast.parse(expression,mode='eval').body)
   return int(result) if value[1]==0 else result
  if len(values)==1:return literal(next(iter(values.values())),depth+1)
  raise ValueError('Unresolved I2V dimension at '+value[0]+' '+workflow[value[0]]['class_type']+' keys '+str(sorted(values)))
 active=set();pending=['597']
 while pending:
  key=pending.pop()
  if key in active:continue
  if key not in workflow:raise ValueError('Missing I2V graph dependency '+key)
  active.add(key)
  pending.extend(value[0] for value in workflow[key].get('inputs',{}).values() if _is_link(value))
 loaders=[key for key in active if workflow[key].get('class_type')=='LoadImage']
 if loaders!=['834']:raise ValueError('Unexpected active I2V image loaders '+str(sorted(loaders)))
 actual={key:literal(workflow['534']['inputs'][key]) for key in ('width','height','length')}
 if actual!={'width':width,'height':height,'length':frames}:raise ValueError('Native I2V latent dimensions/frame count differ: '+str(actual)+'; expected length '+str(frames))
 if literal(workflow['597']['inputs']['frame_rate'])!=24:raise ValueError('Unexpected I2V output fps')
 for key in active:
  if workflow[key].get('class_type')=='LTXVEmptyLatentAudio':
   values=workflow[key]['inputs']
   if literal(values['frames_number'])!=frames or literal(values['frame_rate'])!=24:raise ValueError('I2V audio timing differs from video')
 return {'schema':'joat.i2v_graph_preflight.v1','file_version':FILE_VERSION,'status':'passed','width':width,'height':height,'output_frames':frames,'image_input_count':1,'msr_node_count':0,'checked_node_types':checked,'gpu_called':False}

def check(context,width,height,seconds,gen_budget):
 for value in (width,height):
  if isinstance(value,bool) or not math.isfinite(float(value)) or float(value)!=int(value):raise ValueError('I2V dimensions must be integers')
 if isinstance(gen_budget,bool) or type(gen_budget) not in (int,float) or not math.isfinite(gen_budget) or float(gen_budget)!=int(gen_budget) or not (gen_budget==0 or 45<=gen_budget<=600):raise ValueError('Use calculated reservation0 or an explicit integer ceiling of45–600seconds')
 if isinstance(seconds,bool) or not math.isfinite(float(seconds)) or not 1<=float(seconds)<=12:raise ValueError('Unsupported shot duration')
 context['_prepare_runtime']();import nodes
 graph,frames=build_graph(context,int(width),int(height),float(seconds));report=check_graph(graph,nodes.NODE_CLASS_MAPPINGS,int(width),int(height),frames)
 values={'seconds':float(seconds),'input_mode':'single image (i2v)','mode':'anchor only','sigma_string':context['_SIGMA_TUNED'],'skip_refine':True,'gen_budget':gen_budget}
 profile=context['_joat_profile'](values,int(width),int(height),0);budget=context['_joat_reservation'](values,profile)
 return {'schema':'joat.i2v_runtime_check.v1','file_version':FILE_VERSION,'status':'passed' if budget['status']=='ready' else 'blocked','graph':report,'workload':profile,'budget':budget,'versions':{'app':context['APP_VERSION'],'msr_runtime':context['JOAT_MSR_PATCH_VERSION'],'gpu_contract':context['JOAT_GPU_VERSION'],'graph_contract':context['JOAT_GRAPH_VERSION']},'runtime_dependencies':context['_joat_dependency_manifest'](),'gpu_called':False}
