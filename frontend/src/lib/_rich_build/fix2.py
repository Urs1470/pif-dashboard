import fitz, os, re
SRC = r"C:\Users\ion.ursu\My Drive\wiki_job\raw\standards"
OUT = r"C:\Users\ion.ursu\pif-dashboard\private_docs\standards"
def is_toc(t):
    h = re.sub(r"\s+"," ",t).strip().lower()[:120]
    return h.startswith("contents") or "cuprins" in h or len(re.findall(r"\.{4,}\s*\d+",t)) >= 5
def first_content(doc, phrases, start=6):
    for ph in phrases:
        pl = ph.lower()
        for p in range(start, doc.page_count):
            txt = doc.load_page(p).get_text("text")
            if is_toc(txt): continue
            if pl in txt.lower(): return p, ph
    return None, None
def save(doc, a, b, sid):
    o = fitz.open(); o.insert_pdf(doc, from_page=a, to_page=b)
    p = os.path.join(OUT, sid+"-extras.pdf"); o.save(p, garbage=4, deflate=True); o.close()
    return round(os.path.getsize(p)/1024)

# 60076-7: prima pagina de CONTINUT (non-cuprins) cu metoda de incalzire
d = fitz.open(os.path.join(SRC, "IEC_60076-7_2005_Ghid-incarcare-trafo-ulei.pdf"))
p, ph = first_content(d, ["relative ageing rate", "hot-spot temperature", "hot-spot"], 8)
kb = save(d, p, min(p+10, d.page_count-1), "iec60076-7")
print("60076-7 ->", p+1, "-", min(p+11, d.page_count), kb, "KB anchor", ph, "toc", is_toc(d.load_page(p).get_text("text"))); d.close()

# 60034-17: prima pagina de continut cu derating/converter
d = fitz.open(os.path.join(SRC, "IEC_60034-17_2006_Motoare-inductie-colivie-pentru-VFD.pdf"))
p, ph = first_content(d, ["derating", "converter supply", "voltage stresses", "torque"], 8)
if p is None: p, ph = first_content(d, ["converter"], 8)
kb = save(d, p, min(p+8, d.page_count-1), "iec60034-17")
print("60034-17 ->", p+1, "-", min(p+9, d.page_count), kb, "KB anchor", ph, "toc", is_toc(d.load_page(p).get_text("text"))); d.close()
