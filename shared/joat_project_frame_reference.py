"""Bind an already owner-approved project still without altering its evidence.
Embedded file version 1.0.1. No generation, canonical registration or QC authority.
"""
FILE_VERSION='1.0.1'
import hashlib,json,re
from pathlib import Path
from datetime import datetime,timezone
from PIL import Image
ROOT=Path('/studio/joat-studio')
SCHEMA='joat.approved_project_job_reference.v1'
def fp(v):return hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def checked(path):
    if any(p.is_symlink() for p in (path,*path.parents)):raise ValueError('Project frame symlink rejected.')
    return path
def read(path):
    path=checked(path)
    if not path.is_file() or path.stat().st_size>1024*1024:raise ValueError('Project frame evidence missing/oversized.')
    return json.loads(path.read_text())
def verify(v,key):
    if fp({k:x for k,x in v.items() if k!=key})!=v.get(key):raise ValueError('Invalid project frame '+key)
def origin(project,key,identifier,root):
    if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]{0,127}',project) or not re.fullmatch('[A-Z0-9-]{1,96}',key) or not re.fullmatch('[a-f0-9]{32}',identifier):raise ValueError('Invalid project frame scope.')
    return checked(Path(root)/'production-projects'/project/'references'/key/identifier)
def evidence(project,key,identifier,root):
    base=origin(project,key,identifier,root);review=read(base/'candidate_review.json');approval=read(base/'owner_visual_approval.json');verify(approval,'approval_fingerprint');q=review.get('source_request',{})
    if review.get('schema')!='joat.project_reference_candidate.v1' or review.get('kind')!='shot_start_frame' or review.get('project_id')!=project or review.get('asset_key')!=key or review.get('request_id')!=identifier or review.get('plan_fingerprint')!=fp(q):raise ValueError('Project candidate provenance mismatch.')
    if q.get('project_id')!=project or q.get('asset_key')!=key or q.get('request_id')!=identifier:raise ValueError('Project candidate source scope changed.')
    a=approval.get('owner_approval',{})
    if approval.get('schema')!='joat.project_frame_visual_approval.v1' or approval.get('project_id')!=project or approval.get('asset_key')!=key or approval.get('source_request_id')!=identifier or approval.get('candidate_plan_fingerprint')!=review['plan_fingerprint'] or approval.get('candidate_review_fingerprint')!=fp(review) or approval.get('image_sha256')!=review.get('sha256') or a.get('owner')!='Dezz-9-10' or a.get('approved') is not True or a.get('scope')!='still_only':raise ValueError('Exact original owner still approval required.')
    if review.get('canonical_registration') is not False or review.get('production_qc_approved') is not False:raise ValueError('Project reference cannot grant canon/QC authority.')
    image=checked(base/'candidate.png')
    if not image.is_file() or image.stat().st_size>25*1024*1024 or image.stat().st_size!=review.get('size_bytes') or hashlib.sha256(image.read_bytes()).hexdigest()!=review.get('sha256'):raise ValueError('Project frame image differs from approval.')
    with Image.open(image) as im:
        im.load()
        if im.format!='PNG' or im.size!=(review.get('width'),review.get('height')):raise ValueError('Project frame format/dimensions changed.')
    return review,approval,image
def validate_manifest(v):
    verify(v,'fingerprint');d=v.get('descriptor',{});asset=v.get('asset_id','')
    if v.get('schema')!=SCHEMA or not re.fullmatch('[a-f0-9]{64}',asset) or d.get('asset_id')!=asset or fp({k:x for k,x in d.items() if k!='asset_id'})!=asset:raise ValueError('Approved project descriptor differs.')
    if d.get('schema')!='joat.approved_project_job_reference_descriptor.v1' or d.get('role')!='shot_start_frame' or d.get('canonical_registration') is not False or d.get('production_qc_approved') is not False:raise ValueError('Project reference authority differs.')
    scope=d.get('scope',{});o=d.get('origin',{});origin(scope.get('project_id',''),o.get('asset_key',''),o.get('request_id',''),ROOT)
    for k in ['scene_id','shot_id','character_id','environment_id']:
        if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]{0,127}',scope.get(k,'')):raise ValueError('Invalid project reference context.')
    a=v.get('owner_approval',{});b=d.get('canonical_identity_binding',{});q=d.get('source_request',{})
    identities=[s.get('source_sha256') for s in q.get('sources',[]) if s.get('role')=='identity']
    from joat_visible_cast import validate_descriptor
    validate_descriptor(d)
    if b.get('status')!='canonical_source_hash_matched' or b.get('character_id')!=scope['character_id'] or b.get('biometric_identity_verified') is not False:raise ValueError('Project reference canonical binding differs.')
    if q.get('project_id')!=scope['project_id'] or fp(q)!=o.get('candidate_plan_fingerprint') or q.get('asset_key')!=o['asset_key'] or q.get('request_id')!=o['request_id']:raise ValueError('Original project reference plan changed.')
    if a.get('owner')!='Dezz-9-10' or a.get('kind')!='visual_job_reference' or not a.get('approved_at') or a.get('descriptor_fingerprint')!=asset:raise ValueError('Owner assignment approval required.')
    expected='hf://buckets/Dezz-9-10/J.O.A.T.-Studio-storage/joat-studio/production-projects/'+scope['project_id']+'/references/'+o['asset_key']+'/'+o['request_id']+'/candidate.png'
    if v.get('image_uri')!=expected:raise ValueError('Project frame URI changed.')
    return d
def load_approved_frame(v,root=ROOT):
    d=validate_manifest(v);stored=read(checked(Path(root)/'approved-project-references'/v['asset_id']/'manifest.json'))
    if stored!=v:raise ValueError('Stored approved project reference differs.')
    o=d['origin'];review,approval,image=evidence(d['scope']['project_id'],o['asset_key'],o['request_id'],root)
    if review['source_request']!=d['source_request'] or fp(review)!=o['candidate_review_fingerprint'] or approval['approval_fingerprint']!=o['approval_fingerprint'] or review['sha256']!=d['image_sha256'] or review['size_bytes']!=d['size_bytes'] or (review['width'],review['height'])!=(d['width'],d['height']):raise ValueError('Project reference no longer matches original approval.')
    return image
def register(project,key,identifier,scope,character,approved,root=ROOT,*,visible_characters=None):
    if approved is not True or scope.get('project_id')!=project or scope.get('character_id')!=character.get('character_id'):raise ValueError('Owner-approved exact project assignment required.')
    review,approval,image=evidence(project,key,identifier,root)
    identity=[s['source_sha256'] for s in review['source_request']['sources'] if s['role']=='identity']
    from joat_visible_cast import bind_sources
    bindings=bind_sources(review['source_request']['sources'],visible_characters if visible_characters is not None else [character],character['character_id'])
    primary=next(b for b in bindings if b['character_id']==character['character_id'])
    if character.get('identity_locked') is not True or character.get('source_asset_hashes',{}).get(primary['identity_asset_id'])!=primary['identity_source_sha256']:raise ValueError('Primary canonical source differs.')
    matches=[primary['identity_asset_id']]
    d=dict(schema='joat.approved_project_job_reference_descriptor.v1',file_version=FILE_VERSION,scope=scope,role='shot_start_frame',image_sha256=review['sha256'],size_bytes=review['size_bytes'],width=review['width'],height=review['height'],source_request=review['source_request'],origin=dict(asset_key=key,request_id=identifier,candidate_plan_fingerprint=review['plan_fingerprint'],candidate_review_fingerprint=fp(review),approval_fingerprint=approval['approval_fingerprint']),canonical_identity_binding=dict(status='canonical_source_hash_matched',character_id=character['character_id'],identity_source_sha256=primary['identity_source_sha256'],identity_asset_id=matches[0],biometric_identity_verified=False),canonical_registration=False,production_qc_approved=False)
    if len(bindings)>1:d['canonical_cast_bindings']=bindings
    # Preserve existing single-subject descriptor bytes/asset IDs and their saved approvals.
    # Module FILE_VERSION identifies the new code; legacy data semantics remain unchanged.
    if len(bindings)==1:d['file_version']='1.0.0'
    asset=fp(d);d['asset_id']=asset
    target=checked(Path(root)/'approved-project-references'/asset/'manifest.json')
    if target.exists():
        v=read(target);load_approved_frame(v,root);return v
    v=dict(schema=SCHEMA,file_version=FILE_VERSION,asset_id=asset,descriptor=d,image_uri='hf://buckets/Dezz-9-10/J.O.A.T.-Studio-storage/'+str(image.relative_to(Path(root).parent)),owner_approval=dict(owner='Dezz-9-10',kind='visual_job_reference',descriptor_fingerprint=asset,approved_at=datetime.now(timezone.utc).isoformat()),canonical_registration=False,production_qc_approved=False)
    v['fingerprint']=fp(v);validate_manifest(v);target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('x') as f:json.dump(v,f,indent=2)
    load_approved_frame(v,root);return v

def register_from_source(packet,key,identifier,approved,root=ROOT):
    """Use the exact approved source packet to declare all visible canonical subjects."""
    from joat_job_frame_binding import source
    job,context,snapshot=source(packet)
    primary=snapshot['character']
    scope=dict(context,character_id=primary['character_id'],environment_id=snapshot['environment']['environment_id'])
    characters=snapshot['director'].get('character_refs') or [primary]
    return register(context['project_id'],key,identifier,scope,primary,approved,
                    root=root,visible_characters=characters)
