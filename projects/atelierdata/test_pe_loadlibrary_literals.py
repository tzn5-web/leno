"""Synthetic PE32 fixtures only: no original binaries or proprietary strings."""
import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path
from pe_loadlibrary_literals import analyze, parse_pe, run


def fake_pe(literal=b'example.dll\0', with_call=True):
    b = bytearray(0x800)
    b[:2] = b'MZ'
    struct.pack_into('<I', b, 0x3c, 0x80)
    b[0x80:0x84] = b'PE\0\0'
    struct.pack_into('<HHIIIHH',b,0x84,0x14c,2,0,0,0,0xe0,0x102)
    opt=0x98
    struct.pack_into('<H',b,opt,0x10b)
    struct.pack_into('<I',b,opt+28,0x400000)
    struct.pack_into('<I',b,opt+92,16)
    struct.pack_into('<II',b,opt+104,0x2000,0x80)
    for index,(name,rva,offset,flags,size) in enumerate((
        (b'.text',0x1000,0x200,0x60000020,0x200),
        (b'.idata',0x2000,0x400,0xc0000040,0x400))):
        p=opt+0xe0+index*40
        b[p:p+8]=name.ljust(8,b'\0')
        struct.pack_into('<IIII',b,p+8,size,rva,size,offset)
        struct.pack_into('<I',b,p+36,flags)
    struct.pack_into('<IIIII',b,0x400,0x2060,0,0,0x2090,0x2070)
    struct.pack_into('<II',b,0x460,0x20a0,0)
    struct.pack_into('<II',b,0x470,0x20a0,0)
    b[0x490:0x49d]=b'KERNEL32.dll\0'
    b[0x4a2:0x4af]=b'LoadLibraryA\0'
    b[0x4c0:0x4c0+len(literal)]=literal
    if with_call:
        b[0x210:0x21b]=b'\x68'+struct.pack('<I',0x4020c0)+b'\xff\x15'+struct.pack('<I',0x402070)
    return bytes(b)


class StaticLoaderTests(unittest.TestCase):
    def test_valid_fixture_and_privacy(self):
        blob=fake_pe()
        digest=hashlib.sha256(blob).hexdigest()
        public,private=analyze(blob,digest)
        self.assertEqual(public['adjacent_push_call_candidates'],1)
        self.assertEqual(public['resolved_dll_literal_candidates'],1)
        self.assertEqual(public['distinct_dll_literals'],1)
        self.assertEqual(private['candidates'][0]['literal'],'example.dll')
        self.assertNotIn('example.dll',json.dumps(public))
        self.assertFalse(public['cfg_reachability_proven'])
        self.assertFalse(public['idf_decoder_proven'])
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'synthetic.exe').write_bytes(blob)
            run(root/'synthetic.exe',digest,root/'public.json',root/'private.json')
            self.assertNotIn('example.dll',(root/'public.json').read_text())
            self.assertIn('example.dll',(root/'private.json').read_text())

    def test_invalid_sha_and_headers(self):
        blob=fake_pe()
        with self.assertRaisesRegex(ValueError,'SHA256 mismatch'):
            analyze(blob,'0'*64)
        with self.assertRaisesRegex(ValueError,'PE signature'):
            parse_pe(blob[:0x80]+b'NOPE'+blob[0x84:])
        with self.assertRaisesRegex(ValueError,'Only PE32'):
            bad=bytearray(blob)
            struct.pack_into('<H',bad,0x98,0x20b)
            parse_pe(bytes(bad))

    def test_unresolved_or_nonadjacent_argument(self):
        for blob in (fake_pe(b'no-suffix\0'),fake_pe(with_call=False)):
            public,_=analyze(blob,hashlib.sha256(blob).hexdigest())
            self.assertEqual(public['resolved_dll_literal_candidates'],0)

    def test_out_of_bounds_and_output_collision(self):
        b=bytearray(fake_pe())
        struct.pack_into('<I',b,0x210+1,0xffffffff)
        blob=bytes(b)
        public,_=analyze(blob,hashlib.sha256(blob).hexdigest())
        self.assertEqual(public['unresolved_candidates'],1)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'a.exe';p.write_bytes(blob)
            with self.assertRaisesRegex(ValueError,'must differ'):
                run(p,hashlib.sha256(blob).hexdigest(),p,p)

if __name__=='__main__':
    unittest.main()
