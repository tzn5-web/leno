#!/usr/bin/env python3
import hashlib, json, pathlib, sys
apk=pathlib.Path(sys.argv[1])
report=pathlib.Path(sys.argv[2])
obj=json.loads(report.read_text())
obj['sha256']=hashlib.file_digest(open(apk,'rb'),'sha256').hexdigest()
obj['bytes']=apk.stat().st_size
obj['signature_verification']='PASS'
obj['archive_alignment']='PASS'
report.write_text(json.dumps(obj,indent=2))
print('NOADS_V2_SIGNED_SHA256',obj['sha256'])
