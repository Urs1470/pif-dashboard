# v2: extrage SECTIUNEA INTREAGA pe tema (nu cuprins/coperta) din standardele IEC/EN.
# - foloseste paginile reale din outline (get_toc) cand exista (>0);
# - daca outline n-are pagini (-1), localizeaza titlul COMPLET CU NUMAR in corp (compact, evita antetele);
# - sare coperta + cuprinsul; alege o fraza-ancora VERIFICATA prezenta in sectiune (pt highlight).
# Scrie si _std_anchors.json (id -> anchor) ca sa sincronizez href-urile din driveCalc.
import fitz, json, os, re

SRC = r"C:\Users\ion.ursu\My Drive\wiki_job\raw\standards"
OUT = r"C:\Users\ion.ursu\pif-dashboard\private_docs\standards"
HERE = os.path.dirname(os.path.abspath(__file__))
os.makedirs(OUT, exist_ok=True)
MAXSPAN = 12

# (id, fisier, [kw titlu clauza], [fraze-ancora candidate, in ordine de preferinta])
STDS = [
 ("iec60034-1","IEC_60034-1_2010_Rating-and-performance.pdf",["duty"],["duty type","continuous running duty","intermittent periodic","S6"]),
 ("iec60034-12","IEC_60034-12_2016b_Caracteristici-pornire-DOL-Ed3.pdf",["starting"],["locked rotor","starting current","pull-up torque"]),
 ("iec60034-25","IEC_60034-25_Ed3_Motoare-AC-pentru-VFD.pdf",["voltage stress","stress"],["voltage stress","peak voltage","rise time"]),
 ("iec60034-18-41","IEC_60034-18-41_Descarcari-partiale-PD-VFD.pdf",["qualification","type test"],["partial discharge","impulse voltage","Type I"]),
 ("iec60034-30-1","IEC_60034-30-1_Clase-eficienta-IE1-IE4-motoare-retea.pdf",["classification","efficiency class","limits"],["efficiency classes","IE3","IE4","nominal efficiency"]),
 ("iec61800-2","IEC_61800-2_2015_Ratings-specificatii-VFD-joasa-tensiune.pdf",["rating"],["overload","output current","rated current","duty"]),
 ("iec61800-3","IEC_61800-3_2017_Cerinte-EMC-metode-test-VFD.pdf",["categor","environment"],[]),
 ("iec61800-5-1","IEC_61800-5-1_2007_Siguranta-electrica-termica-VFD.pdf",["protection","protective"],["protective","touch current","clearance","creepage"]),
 ("iec61800-5-2","IEC_61800-5-2_Siguranta-functionala-SIL-STO-VFD.pdf",["safety functions"],["Safe torque off","STO","safety function"]),
 ("iec60364-5-52","IEC_60364-5-52_Selectie-pozare-cabluri-wiring-systems.pdf",["current-carrying"],["current-carrying capacity","installation method","rated current"]),
 ("iec60909","IEC_60909_Curenti-scurtcircuit-sisteme-trifazate.pdf",["characteristics of short-circuit"],["short-circuit current","initial symmetrical","peak short-circuit"]),
 ("iec60204-1","IEC_60204-1_2006_Echipament-electric-masini-generale.pdf",["stop"],["stop category","category 0","category 1","emergency stop"]),
 ("iec61000-3-12","IEC_61000-3-12_Limite-armonice-16A-75A.pdf",["limit"],["harmonic current","short-circuit ratio","Rsce"]),
 ("iec61000-2","IEC_61000-2_Mediu-electromagnetic-compatibilitate.pdf",["compatibility level"],["compatibility level","harmonic"]),
 ("iec61000-4-30","IEC_61000-4-30_Masurare-calitate-energie-power-quality.pdf",["measurement"],["measurement method","power quality","Class A"]),
 ("iec60076-1","IEC_60076-1_Transformatoare-putere-general.pdf",["rating"],["rated power","temperature rise","connection symbol","tapping"]),
 ("iso9906","ISO_9906-IEC_60193_Pompe-rotodynamice-teste-hidraulice.pdf",["npsh"],["NPSH","cavitation"]),
 ("en50160","EN_50160_2007_Caracteristici-tensiune-retea-publica.pdf",["characteristics of the","harmonic"],["harmonic voltage","voltage characteristics","total harmonic"]),
]

def norm(s): return re.sub(r"\s+"," ", s).strip().lower()
def compact(s): return re.sub(r"\s+","", s).lower()
def ptext(doc,p): return doc.load_page(p).get_text("text")
def is_toc(txt):
    head = norm(txt)[:120]
    if head.startswith("contents") or "cuprins" in head: return True
    return len(re.findall(r"\.{4,}\s*\d+", txt)) >= 5

def heading_page(doc, title, start):
    # titlu COMPLET cu numar -> compact (ex "4 Duty"->"4duty"); evita antetele (care n-au numarul clauzei)
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

results = []; anchors_map = {}
for sid, fn, seckws, cands in STDS:
    src = os.path.join(SRC, fn); rec = {"id": sid}
    if not os.path.exists(src): rec.update(ok=False, err="lipsa"); results.append(rec); continue
    doc = fitz.open(src); toc = doc.get_toc()
    start = end = None; via = None
    idx = next((i for i,(l,t,p) in enumerate(toc)
                if any(k in norm(t) for k in seckws) and re.match(r"^\s*\d", t)), None)
    if idx is not None:
        lvl, title, pg = toc[idx]
        start = (pg-1) if pg and pg > 0 else heading_page(doc, title, 0)
        if start is not None:
            # boundary: urmatoarea intrare cu nivel <= lvl
            nxt = next(((l2,t2,p2) for (l2,t2,p2) in toc[idx+1:] if l2 <= lvl), None)
            if nxt:
                _,nt,npg = nxt
                ep = (npg-1) if npg and npg > 0 else heading_page(doc, nt, start+1)
                end = (ep-1) if (ep and ep > start) else None
            if end is None: end = min(start+MAXSPAN, doc.page_count-1)
            end = min(end, start+MAXSPAN); via = "outline:"+title.strip()[:38]
    if start is None:
        # fallback: prima fraza-ancora in CORP (sare coperta<6 + cuprins)
        ph,p = anchor_in(doc, 6, doc.page_count-1, cands or seckws)
        if p is None: p = next((q for q in range(6,doc.page_count) if not is_toc(ptext(doc,q))), 6)
        start = p; end = min(p+3, doc.page_count-1); via = "fallback-anchor"
    # daca pagina de start e cuprins, avanseaza la prima non-cuprins
    while start < end and is_toc(ptext(doc,start)): start += 1
    out = fitz.open(); out.insert_pdf(doc, from_page=start, to_page=end)
    path = os.path.join(OUT, sid+"-extras.pdf"); out.save(path, garbage=4, deflate=True)
    aph, apage = anchor_in(doc, start, end, cands) if cands else (None,None)
    anchors_map[sid] = aph
    rec.update(ok=True, via=via, page_from=start+1, page_to=end+1, n_pages=end-start+1,
               first_is_toc=is_toc(ptext(doc,start)), anchor=aph,
               anchor_on=(apage-start+1) if apage is not None else None, kb=round(os.path.getsize(path)/1024))
    out.close(); doc.close(); results.append(rec)

json.dump(anchors_map, open(os.path.join(HERE,"_std_anchors.json"),"w"), ensure_ascii=False, indent=1)
print(json.dumps(results, ensure_ascii=False, indent=1))
