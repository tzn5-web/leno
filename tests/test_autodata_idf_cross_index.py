"""Synthetic tests for read-only Autodata IDF cross-file opaque-key joins."""
import hashlib
import importlib.util
import tempfile
import zipfile
from pathlib import Path

def load_module():
    module_path = Path(__file__).resolve().parents[1] / "tools" / "autodata_idf_cross_index.py"
    spec = importlib.util.spec_from_file_location("autodata_cross_index", module_path)
    import sys
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

def main():
    mod = load_module()
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        cases = [
            (1,"MIDS.IDF",17,[b"A"*8,b"B"*8,b"C"*8]),
            (1,"MIDTDoc.IDF",17,[b"A"*8,b"C"*8,b"D"*8]),
            (1,"FAS.IDF",19,[b"X"*8,b"Y"*8]),
            (1,"SGINT.IDF",21,[b"M"*8,b"N"*8]),
            (2,"SGOPS.IDF",21,[b"M"*8,b"N"*8]),
        ]
        for part,name,width,keys in cases:
            records = b"".join((key + b"!"*(width-8))*400 for key in keys)
            noise = b"".join(hashlib.sha256(i.to_bytes(8,"little")+name.encode()).digest()[:width]
                            for i in range(2000))
            archive = folder / f"autodata_part_{part:04d}.zip"
            with zipfile.ZipFile(archive,"a") as zf:
                zf.writestr(mod.ROOT+name,records+noise)
        result = mod.audit(folder)
        relationships = result["cross_file_relationships"]
        linked = relationships["MIDS.IDF :: MIDTDoc.IDF"]
        assert linked["shared_opaque_keys"] == 2, linked
        assert linked["all_shared_keys_in_same_order"] is True, linked
        unrelated = relationships["FAS.IDF :: MIDS.IDF"]
        assert unrelated["shared_opaque_keys"] == 0, unrelated
        assert unrelated["all_shared_keys_in_same_order"] is None, unrelated
        assert relationships["SGINT.IDF :: SGOPS.IDF"]["shared_opaque_keys"] == 2
        assert relationships["SGINT.IDF :: SGOPS.IDF"]["group_size_pearson"] is None
        assert all(value["candidate_rows"] == (800 if name in ("FAS.IDF","SGINT.IDF","SGOPS.IDF") else 1200)
                   for name,value in result["table_candidates"].items()),result["table_candidates"]
        assert not result["original_programs_executed"]
    print("PASS: synthetic cross-index joins, nonmatch case, boundary detection")

if __name__ == "__main__":
    main()
