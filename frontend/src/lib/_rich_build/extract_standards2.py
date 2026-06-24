# Extrage sectiunile pe tema pt STANDARDELE NOI (carduri noi + surse noi). Aceeasi logica v2.
import fitz, json, os, re
SRC = r"C:\Users\ion.ursu\My Drive\wiki_job\raw\standards"
OUT = r"C:\Users\ion.ursu\pif-dashboard\private_docs\standards"
HERE = os.path.dirname(os.path.abspath(__file__))
os.makedirs(OUT, exist_ok=True)
MAXSPAN = 12

STDS = [
 ("iec60076-7","IEC_60076-7_2005_Ghid-incarcare-trafo-ulei.pdf",["limitations","loading","temperature"],["hot-spot","relative ageing","load factor","permissible loading"]),
 ("iec60034-14","IEC_60034-14_2007_Vibratii-mecanice.pdf",["vibration","limits"],["vibration velocity","vibration magnitude","mm/s"]),
 ("iec61508-1","IEC_61508-1_2010_Siguranta-functionala-sisteme-E-E-EP.pdf",["safety integrity"],["safety integrity level"]),
 ("iec62061","IEC_62061_2005_Siguranta-masinilor-SRECS-SIL.pdf",["safety integrity","requirements"],["safety integrity level","SILCL"]),
 ("iso13849-1","ISO_13849-1_2015_Parti-siguranta-sisteme-comanda-PLd.pdf",["performance level","determination"],["performance level","required performance","category"]),
 ("iec60034-5","IEC_60034-5_2006_Grade-protectie-IP.pdf",["degrees of protection","classification"],["degrees of protection","first characteristic","IP code"]),
 ("iec60076-21","IEC_60076-21_2011_Regulatoare-tensiune-pas-cu-pas.pdf",["general","rating","requirements"],["voltage regulator","regulation","tap"]),
 ("iec60034-30-2","IEC_60034-30-2_Clase-eficienta-IES1-IES2-motoare-VFD.pdf",["efficiency class","classification"],["IES","efficiency class","loss"]),
 ("iec60034-17","IEC_60034-17_2006_Motoare-inductie-colivie-pentru-VFD.pdf",["general","converter","application"],["converter","voltage","cage induction"]),
 ("iec60034-18","IEC_60034-18_2013_Evaluare-sisteme-izolatie.pdf",["thermal","evaluation","classification"],["insulation system","thermal","evaluation"]),
 ("iec61800-6","IEC_61800-6_2003_Tipuri-sarcina-dimensionare-curent.pdf",["load","duty","rating"],["duty","load type","current"]),
 ("npi7-2011","NP_I7-2011_Normativ-instalatii-electrice-cladiri.pdf",["cabluri","protectie","sectiuni"],["instalatii electrice","sectiune","protectie","cabluri"]),
]

def norm(s): return re.sub(r"\s+"," ", s).strip().lower()
def compact(s): return re.sub(r"\s+","", s).lower()
def ptext(doc,p): return doc.load_page(p).get_text("text")
def is_toc(txt):
    head = norm(txt)[:120]
    if head.startswith("contents") or "cuprins" in head: return True
    return len(re.findall(r"\.{4,}\s*\d+", txt)) >= 5
def heading_page(doc, title, start):
    tc = compact(title)
    if len(tc) < 4: return None
    for p in range(max(start,3), doc.page_count):
        if is_toc(ptext(doc,p)): continue
        if tc in compact(ptext(doc,p)): return p
    return None
def anchor_in(doc, p0, p1, cands):
    for ph in cands:
        pl = ph.lower()
        for p in range(p0, p1+1):
            if is_toc(ptext(doc,p)): continue
            if pl in ptext(doc,p).lower(): return ph, p
    return None, None

results = []; amap = {}
for sid, fn, seckws, cands in STDS:
    src = os.path.join(SRC, fn); rec = {"id": sid}
    if not os.path.exists(src): rec.update(ok=False, err="lipsa "+fn); results.append(rec); continue
    doc = fitz.open(src); toc = doc.get_toc()
    start = end = None; via=None
    idx = next((i for i,(l,t,p) in enumerate(toc) if any(k in norm(t) for k in seckws) and re.match(r"^\s*\d", t)), None)
    if idx is not None:
        lvl,title,pg = toc[idx]
        start = (pg-1) if pg and pg>0 else heading_page(doc,title,0)
        if start is not None:
            nxt = next(((l2,t2,p2) for (l2,t2,p2) in toc[idx+1:] if l2<=lvl), None)
            if nxt:
                _,nt,npg = nxt
                ep = (npg-1) if npg and npg>0 else heading_page(doc,nt,start+1)
                end = (ep-1) if (ep and ep>start) else None
            if end is None: end = min(start+MAXSPAN, doc.page_count-1)
            end = min(end, start+MAXSPAN); via="outline:"+title.strip()[:38]
    if start is None:
        ph,p = anchor_in(doc,6,doc.page_count-1,cands or seckws)
        if p is None: p = next((q for q in range(6,doc.page_count) if not is_toc(ptext(doc,q))),6)
        start=p; end=min(p+3,doc.page_count-1); via="fallback-anchor"
    while start<end and is_toc(ptext(doc,start)): start+=1
    out=fitz.open(); out.insert_pdf(doc,from_page=start,to_page=end)
    path=os.path.join(OUT,sid+"-extras.pdf"); out.save(path,garbage=4,deflate=True)
    aph,apage = anchor_in(doc,start,end,cands)
    amap[sid]=aph
    rec.update(ok=True,via=via,page_from=start+1,page_to=end+1,n_pages=end-start+1,
               first_is_toc=is_toc(ptext(doc,start)),anchor=aph,kb=round(os.path.getsize(path)/1024))
    out.close(); doc.close(); results.append(rec)

json.dump(amap, open(os.path.join(HERE,"_std_anchors2.json"),"w"), ensure_ascii=False, indent=1)
print(json.dumps(results, ensure_ascii=False, indent=1))
