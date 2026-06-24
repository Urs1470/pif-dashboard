import fitz, os, re
DIR = r"C:\Users\ion.ursu\pif-dashboard\private_docs\standards"
def is_toc(t):
    h = re.sub(r"\s+"," ",t).strip().lower()[:120]
    return h.startswith("contents") or "cuprins" in h or len(re.findall(r"\.{4,}\s*\d+",t)) >= 5
A = {"iec60076-7":"hot-spot","iec60034-14":"vibration velocity","iec62061":"safety integrity level",
     "iso13849-1":None,"iec60034-5":"degrees of protection","iec60076-21":"voltage regulator",
     "iec60034-30-2":"IES","iec60034-17":"derating","iec60034-18":"insulation system",
     "iec61800-6":"duty","npi7-2011":"sectiune"}
bad = 0
for sid, ph in A.items():
    p = os.path.join(DIR, sid+"-extras.pdf")
    if not os.path.exists(p):
        print(sid, "LIPSA"); bad += 1; continue
    d = fitz.open(p); n = d.page_count; toc0 = is_toc(d.load_page(0).get_text("text"))
    if ph is None:
        print(f"{sid:15} pag={n} primaToc={toc0} (page-only)")
    else:
        pg = next((i+1 for i in range(n) if ph.lower() in d.load_page(i).get_text("text").lower()), None)
        ok = pg is not None and not toc0; bad += 0 if ok else 1
        print(f"{sid:15} pag={n} primaToc={toc0} ancora='{ph}' peExtras={pg} {'OK' if ok else '<<PROBLEMA'}")
    d.close()
print("total fisiere:", len([f for f in os.listdir(DIR) if f.endswith('.pdf')]), "| probleme:", bad)
