import importlib.util
import pathlib
import tempfile
import unittest
import zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location("release",ROOT/"package_release.py")
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class ReleaseChecks(unittest.TestCase):
 def test_constants_and_identifier(self):
  self.assertEqual(m.VERSION,"21.40.5")
  self.assertNotEqual(m.BUNDLE,"com.google.ios.youtube")
  self.assertEqual(len(m.SOURCE_HASH),64)
 def test_reject_unsafe_archive(self):
  with tempfile.TemporaryDirectory() as td:
   p=pathlib.Path(td)/"bad.zip"
   with zipfile.ZipFile(p,"w") as z:z.writestr("../bad",b"x")
   with zipfile.ZipFile(p) as z:
    with self.assertRaisesRegex(ValueError,"unsafe"):m.check_zip(z)
