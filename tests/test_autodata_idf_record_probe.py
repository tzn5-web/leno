"""Synthetic repeat-width regression checks; no original archive data."""
from pathlib import Path
import sys
import tempfile
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from autodata_idf_record_probe import probe

ROOT="Autodata__3.45/ADCDA2/COMMON/"
ROWS=19658
WIDTH=21

def make_record(i, source):
    key=(i % 178).to_bytes(8, "little")
    # Deterministic differing payloads, all 13 bytes.
    payload=(i * 277 + source).to_bytes(13, "little")
    return key+payload

def test_synthetic():
    with tempfile.TemporaryDirectory() as tmp:
        folder=Path(tmp)
        for part,filename,source in [(1,"SGINT.IDF",11),(2,"SGOPS.IDF",22)]:
            b=b"".join(make_record(i,source) for i in range(ROWS))
            # First divergent 8-byte field is exactly at the next 21-byte record.
            b+=(1000+part).to_bytes(8,"little")+b"X"*13
            b+=b"Q"*(128*1024)
            with zipfile.ZipFile(folder/f"autodata_part_{part:04d}.zip","w") as z:
                z.writestr(ROOT+filename,b)
        result=probe(folder)
        assert result["shared_prefix_length"]==ROWS*WIDTH,result
        assert result["fixed_21_byte_records_in_shared_prefix"]==ROWS,result
        assert result["distinct_8byte_field_values"]==178,result
        assert result["identical_8byte_field_count"]==ROWS,result
        assert result["same_13byte_region_count"]==0,result
        assert result["original_executable_executed"] is False
        print("PASS: synthetic 21-byte repeated rows, 8-byte common field and precise boundary")

if __name__=="__main__":
    test_synthetic()
