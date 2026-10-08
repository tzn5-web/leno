import importlib.util,plistlib,struct,tempfile,unittest,zipfile
from pathlib import Path
p=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location("audit",p/"verify_source.py")
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class TestSourceGate(unittest.TestCase):
 def setUp(self):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.target=Path(t.name)/"sample.ipa"
 def make(self,bundle="com.google.ios.youtube",version="21.40.5",encrypted=0,extra=None):
  cmd=struct.pack("<6I",0x2c,24,0,0,encrypted,0)
  data=struct.pack("<8I",0xfeedfacf,0x100000c,0,2,1,24,0,0)+cmd
  with zipfile.ZipFile(self.target,"w") as z:
   z.writestr("Payload/YouTube.app/Info.plist",plistlib.dumps({"CFBundleIdentifier":bundle,"CFBundleShortVersionString":version,"CFBundleExecutable":"YouTube"}))
   z.writestr("Payload/YouTube.app/YouTube",data)
   for path,content in (extra or {}).items():z.writestr(path,content)
 def test_plain_structure_does_not_attest_origin(self):
  self.make();r=m.audit(self.target);self.assertEqual(r["status"],"STRUCTURE_PASS_PROVENANCE_UNVERIFIED");self.assertFalse(r["attested_official"])
 def test_wrong_version(self):
  self.make(version="20.21.6")
  with self.assertRaisesRegex(ValueError,"wrong version"):m.audit(self.target)
 def test_wrong_bundle(self):
  self.make(bundle="ro.ion.youtubevanced")
  with self.assertRaisesRegex(ValueError,"wrong bundle"):m.audit(self.target)
 def test_known_injection(self):
  self.make(extra={"Payload/YouTube.app/Frameworks/VancedCore.dylib":b"bad"})
  self.assertEqual(m.audit(self.target)["status"],"REJECT_KNOWN_INJECTION")
 def test_advanced_resource_not_suspicious(self):
  self.make(extra={"Payload/YouTube.app/mainapp_filegroup/_srs_resources_eml_bundle/advanced_quality_sheet_content.eml-js_dacade31c0706ce2":b"data"})
  self.assertEqual(m.audit(self.target)["status"],"STRUCTURAL_PASS_ORIGIN_UNVERIFIED")
 def test_encryption(self):
  self.make(encrypted=1);self.assertEqual(m.audit(self.target)["status"],"REJECT_ENCRYPTED")
 def test_zip_traversal(self):
  self.make(extra={"../escape":b"x"})
  with self.assertRaisesRegex(ValueError,"unsafe archive path"):m.audit(self.target)
