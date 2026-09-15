# -*- coding: utf-8 -*-
import os
import unittest
from unittest import mock
import tempfile
import shutil

from tests.safety import guvenlik_zirhi_kur, guvenlik_zirhi_kaldir
import build_and_deploy

def setUpModule():
    guvenlik_zirhi_kur()

def tearDownModule():
    guvenlik_zirhi_kaldir()

class TestBuildAndDeploy(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    @mock.patch("subprocess.run")
    def test_run_build_success(self, mock_run):
        mock_run.return_value.returncode = 0
        
        # Oluşturulan sahte spec
        spec_path = os.path.join(self.tmp_dir, "ULTRON.spec")
        with open(spec_path, "w", encoding="utf-8") as f:
            f.write("# dummy spec")
            
        res = build_and_deploy.run_build(cwd=self.tmp_dir)
        self.assertTrue(res)
        mock_run.assert_called_once()

    def test_deploy_build_copies_files(self):
        dist_dir = os.path.join(self.tmp_dir, "dist", "ULTRON")
        os.makedirs(dist_dir, exist_ok=True)
        exe_file = os.path.join(dist_dir, "ULTRON.exe")
        with open(exe_file, "w") as f:
            f.write("dummy exe")
            
        target_dir = os.path.join(self.tmp_dir, "target", "ULTRON")
        
        res = build_and_deploy.deploy_build(dist_dir=dist_dir, target_dir=target_dir)
        self.assertTrue(res)
        self.assertTrue(os.path.exists(os.path.join(target_dir, "ULTRON.exe")))

if __name__ == "__main__":
    unittest.main()
