"""Knowledge scope, integrity and authority tests. File version: 1.0.0."""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

FILE_VERSION = '1.0.0'
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'shared'))
import joat_production_knowledge as k
import joat_studio_capabilities as c


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT/'shared', self.root/'library')
        self.root /= 'library'
        self.now = datetime(2026, 10, 18, 18, 0, tzinfo=timezone.utc)

    def tearDown(self):
        self.temp.cleanup()

    def get(self, **kwargs):
        kwargs.setdefault('now', self.now)
        return k.retrieve(root=self.root, **kwargs)

    def edit(self, identity, **updates):
        index = json.loads((self.root/'approved_knowledge_index.json').read_text())
        item = next(x for x in index['records'] if x['id'] == identity)
        p = self.root/item['path']
        record = json.loads(p.read_text())
        record.update(updates)
        p.write_text(json.dumps(record))
        item['sha256'] = hashlib.sha256(p.read_bytes()).hexdigest()
        (self.root/'approved_knowledge_index.json').write_text(json.dumps(index))
        return hashlib.sha256((self.root/'approved_knowledge_index.json').read_bytes()).hexdigest()

    def ids(self, result):
        return {x['id'] for x in result['lessons']}

    def test_all_twenty_roles_have_distinct_guidance(self):
        self.assertEqual(len(k.ROLES), 20)
        for role in k.ROLES:
            self.assertIn('role-'+role, self.ids(self.get(role=role)))

    def test_main_director_and_executive_responsibilities_remain_separate(self):
        for role in ('main', 'director', 'executive'):
            ids = self.ids(self.get(role=role))
            self.assertIn('role-'+role, ids)
            for other in {'main', 'director', 'executive'}-{role}:
                self.assertNotIn('role-'+other, ids)

    def test_general_retrieval_does_not_leak_project_story(self):
        self.assertNotIn('style001-locked-story', self.ids(self.get()))

    def test_other_project_does_not_receive_locked_story(self):
        self.assertNotIn('style001-locked-story', self.ids(self.get(project_id='OTHER', style_id='STYLE001')))

    def test_exact_project_and_style_receive_approved_story(self):
        result = self.get(project_id='PROJECT-OTU-STYLE001-90S-001', style_id='STYLE001')
        record = next(x for x in result['lessons'] if x['id'] == 'style001-locked-story')
        self.assertIn('Cristu CHAR-004 is the business owner', record['guidance'])
        self.assertIn('90-second', record['guidance'])

    def test_expired_guidance_is_excluded(self):
        self.assertFalse(self.get(now=datetime(2028, 1, 1, tzinfo=timezone.utc))['lessons'])

    def test_unreviewed_status_cannot_be_retrieved_even_in_new_index(self):
        sha = self.edit('role-director', status='candidate')
        with patch.object(k, 'INDEX_SHA256', sha):
            self.assertNotIn('role-director', self.ids(self.get()))

    def test_raw_new_record_is_not_automatically_promoted(self):
        (self.root/'knowledge/raw-auto-approved.json').write_text('{"status":"approved"}')
        self.assertEqual(self.ids(self.get()), self.ids(k.retrieve(now=self.now)))

    def test_tampered_index_rejected(self):
        with (self.root/'approved_knowledge_index.json').open('a') as f:
            f.write(' ')
        with self.assertRaisesRegex(ValueError, 'integrity'):
            self.get()

    def test_tampered_record_rejected(self):
        with (self.root/'knowledge/role-director.json').open('a') as f:
            f.write(' ')
        with self.assertRaisesRegex(ValueError, 'reviewed bytes'):
            self.get()

    def test_source_symlink_rejected(self):
        source = self.root/'knowledge/role-director.json'
        data = source.read_bytes()
        source.unlink()
        target = self.root/'outside.json'
        target.write_bytes(data)
        source.symlink_to(target)
        with self.assertRaisesRegex(ValueError, 'symbolic link'):
            self.get()

    def test_versions_must_match_before_technique_is_retrieved(self):
        sha = self.edit('role-director', versions={'renderer_revision': 'specific-reviewed-revision'})
        with patch.object(k, 'INDEX_SHA256', sha):
            self.assertNotIn('role-director', self.ids(self.get()))
            self.assertNotIn('role-director', self.ids(self.get(versions={'renderer_revision':'changed'})))
            self.assertIn('role-director', self.ids(self.get(versions={'renderer_revision':'specific-reviewed-revision'})))

    def test_project_lesson_cannot_supersede_global_guidance_for_another_project(self):
        sha = self.edit('style001-locked-story', supersedes=['authority-boundaries'])
        with patch.object(k, 'INDEX_SHA256', sha):
            self.assertIn('authority-boundaries', self.ids(self.get()))
            exact = self.get(project_id='PROJECT-OTU-STYLE001-90S-001', style_id='STYLE001')
            self.assertNotIn('authority-boundaries', self.ids(exact))

    def test_retrieval_never_grants_authority(self):
        result = self.get()
        for field in ('execution_authorized', 'qc_approved', 'gpu_called', 'creative_decisions_modified'):
            self.assertIs(result[field], False)

    def test_invalid_role_query_scope_and_limits_rejected(self):
        for kwargs in ({'role':'agent_factory'}, {'project_id':'../escape'}, {'query':'x'*2001},
                       {'limit':True}, {'limit':21}, {'style_id':'STYLE 001'}):
            with self.assertRaises(ValueError):
                self.get(**kwargs)

    def test_shared_deployment_copies_match(self):
        for name in ('joat_production_knowledge.py', 'approved_knowledge_index.json',
                     'joat_studio_capabilities.py', 'joat_studio_capabilities.json'):
            for app in ('main','control'):
                self.assertEqual((ROOT/'shared'/name).read_bytes(), (ROOT/'apps'/app/name).read_bytes())

    def test_role_allowlist_matches_every_native_department(self):
        tree = ast.parse((ROOT/'apps/control/joat_local_cpu.py').read_text())
        node = next(n for n in tree.body if isinstance(n, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == 'ROLES' for t in n.targets))
        self.assertEqual(set(k.ROLES), set(ast.literal_eval(node.value)))

    def test_owner_authentication_happens_before_private_knowledge_lookup(self):
        import types
        import joat_production_knowledge_ui as ui
        managed = types.ModuleType('joat_managed_generation')
        managed.owner_token = lambda *args: (_ for _ in ()).throw(ValueError('Owner required'))
        with patch.dict(sys.modules, {'joat_managed_generation': managed}), patch.object(ui, 'retrieve') as read:
            with self.assertRaisesRegex(ValueError, 'Owner required'):
                ui.lookup('', 'director', '', '', None, None, None)
            read.assert_not_called()

    def test_owner_lookup_retains_explicit_project_and_style_scope(self):
        import types
        import joat_production_knowledge_ui as ui
        managed = types.ModuleType('joat_managed_generation')
        managed.owner_token = lambda *args: 'owner-verified-for-unit-test'
        with patch.dict(sys.modules, {'joat_managed_generation': managed}):
            result = ui.lookup('', 'director', 'PROJECT-OTU-STYLE001-90S-001', 'STYLE001', None, None, None)
        self.assertIn('style001-locked-story', self.ids(result))
        self.assertFalse(result['execution_authorized'])

    def test_correct_renderer_pin_and_all_features_retained(self):
        value = c.registry()
        self.assertEqual(value['renderer_revision'], 'be1591ad2ad05c3af51f27fd671658d1873e15af')
        self.assertEqual(len(value['features']), 30)
        self.assertFalse(c.catalogue()['execution_authorized'])

    def test_main_actual_prompt_uses_general_reviewed_guidance_without_changing_route(self):
        tree = ast.parse((ROOT/'apps/main/app.py').read_text())
        node = next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='build_system_prompt')
        ns = {'Any':__import__('typing').Any, 'BOT_NAME':'Main', 'REPORTS_TO':'Owner', 'STUDIO_KNOWLEDGE':{},
              'JOAT_PERSISTENCE_ENABLED':True, 'JOAT_AUDIT_ENABLED':True, 'JOAT_APPROVAL_GATES_ENABLED':True,
              'JOAT_GHL_ENABLED':False, 'JOAT_SPECIALIST_TOKEN':'presence-only', 'JOAT_EP_SPACE':'Control',
              'JOAT_HF_MASTER_SPACE':'HF', 'JOAT_BROWSER_WORKER_SPACE':'Browser'}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])), 'actual-prompt','exec'),ns)
        route = dict(domain='studio', selected_bot='Control', selected_status='ready', live_execution_connected=True)
        before = copy.deepcopy(route)
        text = ns['build_system_prompt'](route,dict(required=True,type='creative',reason='owner'))
        self.assertIn('REVIEWED PRODUCTION GUIDANCE',text)
        self.assertIn('Director owns studio creative work',text)
        self.assertNotIn('Cristu CHAR-004 is the business owner',text)
        self.assertEqual(route,before)


if __name__ == '__main__':
    unittest.main()
