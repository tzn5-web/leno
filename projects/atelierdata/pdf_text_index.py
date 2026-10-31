"""Private on-device searchable text index for PDFs already authorized and stored.

No OCR, no automated download, no AI guesses of torque values. Text is extracted
from PDF text layers only and stored in the existing local SQLite backup.
"""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
from document_library import verified_library_file

MAX_PAGES=500
MAX_PAGE_TEXT=50000
MAX_TOTAL_TEXT=4_000_000

def ensure_schema(store):
    store.db.executescript("""
    CREATE TABLE IF NOT EXISTS pdf_page_text(
       attachment_id INTEGER NOT NULL REFERENCES attachments(id) ON DELETE CASCADE,
       page_number INTEGER NOT NULL CHECK(page_number>=1),
       file_sha256 TEXT NOT NULL,
       content TEXT NOT NULL,
       extracted_utc TEXT NOT NULL,
       PRIMARY KEY(attachment_id,page_number)
    );
    CREATE INDEX IF NOT EXISTS idx_pdf_page_attachment
      ON pdf_page_text(attachment_id,page_number);
    """)
    store.db.commit()

def index_pdf(store,vehicle_id,attachment_id):
    ensure_schema(store)
    verified=verified_library_file(store,attachment_id,vehicle_id)
    if Path(verified).suffix.lower()!=".pdf":
        raise ValueError("Indexarea este disponibilă doar pentru PDF")
    import pypdfium2 as pdfium
    doc=pdfium.PdfDocument(str(verified))
    rows=[]
    total=0
    try:
        pages=len(doc)
        if pages<1 or pages>MAX_PAGES:
            raise ValueError("Număr de pagini PDF în afara limitei")
        for i in range(pages):
            page=doc[i]
            try:
                textpage=page.get_textpage()
                try:
                    text=textpage.get_text_bounded().replace("\r\n","\n")
                finally:textpage.close()
            finally:page.close()
            if len(text)>MAX_PAGE_TEXT:
                text=text[:MAX_PAGE_TEXT]
            total+=len(text)
            if total>MAX_TOTAL_TEXT:raise ValueError("PDF prea mare pentru index")
            if text.strip():
                rows.append((attachment_id,i+1,Path(verified).name[:64],text,
                    datetime.now(timezone.utc).isoformat(timespec="seconds")))
    finally:doc.close()
    # Old entries are replaced only if all pages extracted successfully.
    with store.db:
        store.db.execute("DELETE FROM pdf_page_text WHERE attachment_id=?",(attachment_id,))
        store.db.executemany("""INSERT INTO pdf_page_text(
          attachment_id,page_number,file_sha256,content,extracted_utc)
          VALUES(?,?,?,?,?)""",rows)
    return {"pages_total":pages,"pages_with_text":len(rows),
            "characters":total,"scanned_pages_without_text":pages-len(rows)}

def search_pdf_text(store,vehicle_id,query,limit=100):
    ensure_schema(store)
    if not isinstance(query,str) or not query.strip() or len(query)>120:
        raise ValueError("Căutarea trebuie să conțină 1–120 caractere")
    if not isinstance(limit,int) or not 1<=limit<=300:raise ValueError("Limită invalidă")
    needle=query.strip()
    like="%"+needle.replace("\\","\\\\").replace("%","\\%").replace("_","\\_")+"%"
    rows=store.db.execute(r"""SELECT t.attachment_id,t.page_number,
        a.title AS article_title,v.make,v.model,v.engine,
        t.file_sha256,t.content
      FROM pdf_page_text t JOIN attachments att ON att.id=t.attachment_id
      JOIN articles a ON a.id=att.article_id
      JOIN vehicles v ON v.id=a.vehicle_id
      WHERE v.id=? AND t.content LIKE ? ESCAPE '\'
      ORDER BY a.title,t.page_number LIMIT ?""",(vehicle_id,like,limit)).fetchall()
    output=[]
    for row in rows:
        text=row["content"]
        start=text.casefold().find(needle.casefold())
        clip_start=max(0,start-70) if start>=0 else 0
        output.append({
           "attachment_id":row["attachment_id"],"page_number":row["page_number"],
           "article_title":row["article_title"],"make":row["make"],
           "model":row["model"],"engine":row["engine"],
           "excerpt":text[clip_start:clip_start+240],
        })
    return output
