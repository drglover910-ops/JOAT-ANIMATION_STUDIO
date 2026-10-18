"""Multi-character source lineage and legacy compatibility. File version: 1.0.0."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

FILE_VERSION = '1.0.0'
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'shared'))
sys.path.insert(1, str(ROOT/'apps/main'))
import joat_visible_cast as cast
import joat_project_frame_reference as frames


def packet(cid, letter):
    return {'character_id':cid, 'identity_locked':True, 'source_asset_hashes':{cid+'-A01':letter*64}}


class VisibleCastTests(unittest.TestCase):
    def setUp(self):
        self.founder = packet('CHAR-001','a')
        self.cristu = packet('CHAR-004','b')
        self.sources = [{'role':'identity','source_sha256':'b'*64},
                        {'role':'identity','source_sha256':'a'*64},
                        {'role':'environment','source_sha256':'c'*64}]
        self.bindings = cast.bind_sources(self.sources,[self.founder,self.cristu],'CHAR-001')
        self.descriptor = {'scope':{'character_id':'CHAR-001'},
                           'source_request':{'sources':self.sources},
                           'canonical_identity_binding':self.bindings[1],
                           'canonical_cast_bindings':self.bindings}
        self.director = {'character_refs':[self.founder,self.cristu]}

    def test_source_order_is_preserved_without_replacing_primary_identity(self):
        self.assertEqual([b['character_id'] for b in self.bindings],['CHAR-004','CHAR-001'])
        result = cast.validate_for_job(self.descriptor,self.director,self.founder)
        self.assertEqual(result['character_ids'],['CHAR-001','CHAR-004'])
        self.assertFalse(result['biometric_identity_verified'])
        self.assertFalse(result['production_qc_approved'])

    def test_primary_only_frame_rejected_for_two_person_shot(self):
        d = copy.deepcopy(self.descriptor)
        d.pop('canonical_cast_bindings')
        d['source_request']['sources'] = [self.sources[1]]
        with self.assertRaisesRegex(ValueError,'every visible'):
            cast.validate_for_job(d,self.director,self.founder)

    def test_two_source_frame_cannot_claim_legacy_primary_only_binding(self):
        d = copy.deepcopy(self.descriptor)
        d.pop('canonical_cast_bindings')
        with self.assertRaisesRegex(ValueError,'explicit canonical cast'):
            cast.validate_descriptor(d)

    def test_legacy_single_character_frame_remains_valid(self):
        d = copy.deepcopy(self.descriptor)
        d.pop('canonical_cast_bindings')
        d['source_request']['sources'] = [self.sources[1]]
        result = cast.validate_for_job(d,{'character_refs':[self.founder]},self.founder)
        self.assertTrue(result['all_visible_sources_matched'])

    def test_wrong_secondary_hash_rejected(self):
        director = copy.deepcopy(self.director)
        director['character_refs'][1]['source_asset_hashes']['CHAR-004-A01']='d'*64
        with self.assertRaisesRegex(ValueError,'approved Director'):
            cast.validate_for_job(self.descriptor,director,self.founder)

    def test_omitted_or_extra_declared_person_rejected(self):
        for packets in ([self.founder], [self.founder,self.cristu,packet('CHAR-002','e')]):
            with self.assertRaises(ValueError):
                cast.bind_sources(self.sources,packets,'CHAR-001')

    def test_two_characters_cannot_share_one_source_identity(self):
        changed = copy.deepcopy(self.cristu)
        changed['source_asset_hashes']={'CHAR-004-A01':'a'*64}
        with self.assertRaises(ValueError):
            cast.bind_sources(self.sources,[self.founder,changed],'CHAR-001')

    def test_duplicate_and_unlocked_canonical_packets_rejected(self):
        for characters in ([self.founder,self.founder], [self.founder,dict(self.cristu,identity_locked=False)]):
            with self.assertRaises(ValueError):
                cast.bind_sources(self.sources,characters,'CHAR-001')

    def test_swapped_primary_and_perceptual_claim_rejected(self):
        for change in ({'canonical_identity_binding':self.bindings[0]},
                       {'canonical_cast_bindings':[dict(self.bindings[0],biometric_identity_verified=True),self.bindings[1]]}):
            d = copy.deepcopy(self.descriptor)
            d.update(change)
            with self.assertRaises(ValueError):
                cast.validate_descriptor(d)

    def test_register_actual_multi_character_manifest_and_verify_readback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'joat-studio'
            base = root/'production-projects/PROJECT-TEST/references/PAIR'/('1'*32)
            base.mkdir(parents=True)
            image = base/'candidate.png'
            image.write_bytes(b'unit-test-image-placeholder')
            request = {'project_id':'PROJECT-TEST','asset_key':'PAIR','request_id':'1'*32,'sources':self.sources}
            review = {'source_request':request,'plan_fingerprint':frames.fp(request),
                      'sha256':hashlib.sha256(image.read_bytes()).hexdigest(),'size_bytes':image.stat().st_size,
                      'width':576,'height':1024}
            approval = {'approval_fingerprint':'f'*64}
            scope = {'project_id':'PROJECT-TEST','scene_id':'SCENE-001','shot_id':'SHOT-009',
                     'character_id':'CHAR-001','environment_id':'ENV-001'}
            # Image/evidence bytes are covered by their existing separate validators; this
            # test exercises the real registration, descriptor seal and persistent manifest.
            with patch.object(frames,'evidence',return_value=(review,approval,image)), patch.object(frames,'load_approved_frame',return_value=image):
                manifest = frames.register('PROJECT-TEST','PAIR','1'*32,scope,self.founder,True,
                                          root=root,visible_characters=[self.founder,self.cristu])
            descriptor = frames.validate_manifest(manifest)
            cast.validate_for_job(descriptor,self.director,self.founder)
            self.assertEqual(descriptor['canonical_identity_binding']['character_id'],'CHAR-001')
            self.assertEqual(len(descriptor['canonical_cast_bindings']),2)
            saved = json.loads((root/'approved-project-references'/manifest['asset_id']/'manifest.json').read_text())
            self.assertEqual(saved,manifest)

    def test_register_without_second_packet_fails_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            review = {'source_request':{'sources':self.sources}}
            with patch.object(frames,'evidence',return_value=(review,{},Path(tmp)/'image.png')):
                with self.assertRaises(ValueError):
                    frames.register('PROJECT-TEST','PAIR','1'*32,
                                    {'project_id':'PROJECT-TEST','character_id':'CHAR-001'},
                                    self.founder,True,root=Path(tmp))
            self.assertFalse(list(Path(tmp).rglob('manifest.json')))

    def test_single_character_descriptor_keeps_existing_data_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'joat-studio'
            image = root/'production-projects/PROJECT-TEST/references/SINGLE'/('2'*32)/'candidate.png'
            image.parent.mkdir(parents=True)
            image.write_bytes(b'unit-test-single')
            request = {'project_id':'PROJECT-TEST','asset_key':'SINGLE','request_id':'2'*32,'sources':[self.sources[1]]}
            review = {'source_request':request,'plan_fingerprint':frames.fp(request),
                      'sha256':hashlib.sha256(image.read_bytes()).hexdigest(),'size_bytes':image.stat().st_size,
                      'width':576,'height':1024}
            scope = {'project_id':'PROJECT-TEST','scene_id':'SCENE-001','shot_id':'SHOT-001',
                     'character_id':'CHAR-001','environment_id':'ENV-001'}
            with patch.object(frames,'evidence',return_value=(review,{'approval_fingerprint':'f'*64},image)), patch.object(frames,'load_approved_frame',return_value=image):
                manifest = frames.register('PROJECT-TEST','SINGLE','2'*32,scope,self.founder,True,root=root)
            self.assertEqual(manifest['descriptor']['file_version'],'1.0.0')
            self.assertNotIn('canonical_cast_bindings',manifest['descriptor'])
            self.assertEqual(frames.FILE_VERSION,'1.0.1')

    def test_registration_wrapper_uses_both_actual_approved_director_characters(self):
        source = json.loads((ROOT/'tests/fixtures/source_shot009.json').read_text())
        with patch.object(frames,'register',return_value={'checked':True}) as register:
            result = frames.register_from_source(source,'PAIR','1'*32,True)
        refs = register.call_args.kwargs['visible_characters']
        self.assertEqual({r['character_id'] for r in refs},{'CHAR-001','CHAR-004'})
        self.assertEqual(result,{'checked':True})

    def test_registration_wrapper_rejects_altered_approved_source(self):
        source = json.loads((ROOT/'tests/fixtures/source_shot009.json').read_text())
        source['generation_job']['project_context']['project_id']='OTHER'
        with patch.object(frames,'register') as register:
            with self.assertRaises(ValueError):
                frames.register_from_source(source,'PAIR','1'*32,True)
        register.assert_not_called()

    def test_frame_assignment_task_accepts_exact_candidate_scope_and_legacy_asset_scope(self):
        path = ROOT/'apps/main/joat_frame_assignment_task.py'
        spec = importlib.util.spec_from_file_location('cast_assignment_task',path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        common = {'scene_id':'SCENE-001','shot_id':'SHOT-009','job_fingerprint':'a'*64,'supervisor_fingerprint':'b'*64}
        for row in (dict(common,asset_id='c'*64),dict(common,asset_key='PAIR',request_id='1'*32)):
            value = {'project_id':'PROJECT-TEST','assignments':[row],'owner_approved':True,'gpu_allowed':False}
            self.assertEqual(module.validate(value),value)
        for change in ({'asset_key':'../PAIR'}, {'request_id':'wrong'}):
            row = dict(common,asset_key='PAIR',request_id='1'*32)
            row.update(change)
            with self.assertRaises(ValueError):
                module.validate({'project_id':'PROJECT-TEST','assignments':[row],'owner_approved':True,'gpu_allowed':False})


if __name__ == '__main__':
    unittest.main()
