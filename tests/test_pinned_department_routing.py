"""Preserve owner transport while avoiding repeated discovery. File version: 1.0.0."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

FILE_VERSION='1.0.0'
ROOT=Path(__file__).resolve().parents[1]

class PinnedDepartmentTests(unittest.TestCase):
    def setUp(self):
        self.contract=types.ModuleType('joat_control_contract')
        self.native=Mock()
        self.contract.create=Mock(return_value=self.native)
        self.local=types.ModuleType('joat_local_cpu')
        self.local.LocalClient=Mock()
        self.local.role_for=lambda x:None
        self.local.stable=lambda x:__import__('json').dumps(x)
        self.local.enabled=lambda:True
        self.patch=patch.dict(sys.modules,{'joat_control_contract':self.contract,'joat_local_cpu':self.local})
        self.patch.start()
        spec=importlib.util.spec_from_file_location('actual_pinned_department',ROOT/'apps/main/joat_runtime_client.py')
        self.module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def tearDown(self):
        self.patch.stop()

    def test_constructor_uses_verified_contract_and_preserves_auth_delegation(self):
        with patch.object(self.module,'NativeClient') as discovery:
            client=self.module.RemoteDepartmentClient('director',token='owner-test-token',
                headers={'Authorization':'Bearer owner-test-token','x-ip-token':'actual-request-delegation'},
                download_files=False)
        discovery.assert_not_called()
        self.contract.create.assert_called_once_with(self.module.HOST,'owner-test-token',
            {'Authorization':'Bearer owner-test-token','x-ip-token':'actual-request-delegation'},False)
        client.close()
        self.native.close.assert_called_once()

    def test_changed_revision_rejected_without_falling_back_to_discovery(self):
        self.contract.create.side_effect=ValueError('Control source changed')
        with patch.object(self.module,'NativeClient') as discovery:
            with self.assertRaisesRegex(ValueError,'source changed'):
                self.module.RemoteDepartmentClient('director',token='owner-test-token')
        discovery.assert_not_called()

if __name__=='__main__':unittest.main()
