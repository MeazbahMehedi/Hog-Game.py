"""Linux installer ownership, quoting, upgrades and data preservation."""

import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('hog_install_linux', ROOT / 'tools/install_linux.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


@unittest.skipUnless(sys.platform.startswith('linux'), 'Linux installer')
class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.folder = Path(self.directory.name)
        self.source = self.folder / 'source'
        self.source.mkdir()
        (self.source / '_internal').mkdir()
        (self.source / 'Hog').write_text('#!/bin/sh\nprintf "%s\\n" "test-client"\n')
        self.prefix = self.folder / "prefix with spaces ' $dollar %"

    def tearDown(self): self.directory.cleanup()

    def test_install_and_launcher_quote_paths(self):
        launcher = installer.install(self.prefix, self.source)
        result = subprocess.run([launcher, '--version'], capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.strip(), 'test-client')
        self.assertIn('%%', (self.prefix/'share/applications/hog.desktop').read_text())
        self.assertTrue(installer._owned(self.prefix/'lib/hog'))

    def test_uninstall_preserves_unrelated_files(self):
        installer.install(self.prefix, self.source)
        data = self.prefix/'settings.json'; data.write_text('keep')
        installer.uninstall(self.prefix)
        self.assertEqual(data.read_text(), 'keep')
        self.assertFalse((self.prefix/'lib/hog').exists())
        self.assertFalse((self.prefix/'bin/hog').exists())

    def test_upgrade_replaces_owned_client(self):
        installer.install(self.prefix, self.source)
        (self.source/'Hog').write_text('#!/bin/sh\necho upgraded\n')
        launcher = installer.install(self.prefix, self.source)
        self.assertEqual(subprocess.check_output([launcher], text=True).strip(), 'upgraded')

    def test_refuses_foreign_destination(self):
        target = self.prefix/'lib/hog'; target.mkdir(parents=True)
        (target/'personal.txt').write_text('keep')
        with self.assertRaises(ValueError): installer.install(self.prefix, self.source)
        with self.assertRaises(ValueError): installer.uninstall(self.prefix)
        self.assertEqual((target/'personal.txt').read_text(), 'keep')


if __name__ == '__main__': unittest.main()
