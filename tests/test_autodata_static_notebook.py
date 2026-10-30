"""Offline synthetic validation of the read-only Autodata Colab notebook."""
import ast, copy, hashlib, io, json, math, re, tempfile, zipfile
from pathlib import Path
from collections import Counter

def main():
    nb_path=Path(__file__).resolve().parents[1]/"notebooks/autodata_3_45_static_audit.ipynb"
    nb=json.loads(nb_path.read_text(encoding="utf-8"))
    assert nb["nbformat"]==4
    code=["".join(c["source"]) for c in nb["cells"] if c["cell_type"]=="code"]
    assert len(code)==6
    for i,s in enumerate(code):ast.parse(s,filename=f"cell_{i}.py")
    combined="\n".join(code)
    assert "pageSize=1000" in combined and "page_size=1000" not in combined
    assert "acknowledgeAbuse" not in combined and "subprocess" not in combined
    assert "KNOWN_BLOCKED" in combined and "manifest_structural_audit.json" in combined
    with tempfile.TemporaryDirectory() as d:
        root=Path(d)
        p1,p2=root/"autodata_part_0001.zip",root/"autodata_part_0002.zip"
        base="Autodata__3.45/ADCDA2/"
        records=[(base+"COMMON/SMALL.IDF",b"\x00\x01abc"),
                 (base+"ENG/lang.xml",b"<root><value>example</value></root>"),
                 (base+"ADBCD.exe",b"MZ\x00\x00test"),
                 (base+"GRAPHICS/SPLIT.IDF",b"a"*30+b"b"*20)]
        files=[]
        with zipfile.ZipFile(p1,"w") as z1,zipfile.ZipFile(p2,"w") as z2:
            for path,data in records:
                parts=[data[:30],data[30:]] if path.endswith("SPLIT.IDF") else [data]
                chunks=[]
                for ix,part in enumerate(parts):
                    pkg=p1.name if ix==0 else p2.name
                    entry=f"{path}.chunk{ix:04d}" if len(parts)>1 else path
                    (z1 if ix==0 else z2).writestr(entry,part)
                    chunks.append({"package":pkg,"entry":entry,"bytes":len(part),"sha256":hashlib.sha256(part).hexdigest()})
                files.append({"path":path,"size_bytes":len(data),"chunks":chunks})
        manifest={"files":files,"file_count":len(files),"package_count":2,
                  "total_extracted_bytes":sum(f["size_bytes"] for f in files)}
        def run(m):
            reports={}
            ns={"manifest":m,"zips":[{"name":p1.name},{"name":p2.name}],
                "missing_zip_names":[f"autodata_part_{i:04d}.zip" for i in range(3,17)],
                "expected_zip_names":[f"autodata_part_{i:04d}.zip" for i in range(1,17)],
                "zip_paths":{p1.name:p1,p2.name:p2},
                "save_csv":lambda n,r:reports.update({n:r}),
                "save_json":lambda n,r:reports.update({n:r}),
                "re":re,"zipfile":zipfile,"hashlib":hashlib,"math":math,"Counter":Counter,
                "json":json,"io":io,"WORK":root,"MAX_ENTRY_BYTES":1024**3,
                "MAX_SMALL_BYTES":12*1024**2,"SAMPLE_BYTES":128*1024,"failures":[]}
            for cell in code[2:5]:exec(compile(cell,"<notebook>","exec"),ns)
            return ns,reports
        ns,rep=run(manifest)
        assert ns["structure"]["status"]=="STRUCTURE_PASS",ns["structural_errors"]
        assert len(ns["manifest_rows"])==4 and all(r["status"]=="PASS" for r in ns["manifest_rows"])
        assert len(ns["unknown_rows"])>=2
        assert ns["safe_type"]("foo.reg")=="dangerous_hash_only"
        assert "manifest_structural_audit.json" in rep
        corrupt=copy.deepcopy(manifest)
        corrupt["files"][0]["chunks"][0]["sha256"]="f"*64
        bad,_=run(corrupt)
        assert bad["structure"]["status"]=="STRUCTURE_PASS"
        assert bad["manifest_rows"][0]["status"]=="FAIL_OR_UNAVAILABLE"
    print("PASS: notebook parses; synthetic ZIP and manifest PASS; tampered SHA256 FAIL")

if __name__=="__main__":main()
