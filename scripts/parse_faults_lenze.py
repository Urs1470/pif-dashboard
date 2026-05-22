# -*- coding: utf-8 -*-
"""
Parser pentru codurile de eroare ale convertoarelor Lenze i550 / i950.

Extrage sectiunea "Events, causes and remedies" din 2 manuale Lenze si
scrie cate un fisier JSON per manual.

Fiecare manual are doua parti, ambele tabele cu 3-4 coloane:
  1. "Event ID overview"   -> Event ID | Event (hex + nume) | Severity | Configurable in
  2. "Causes and remedies" -> per eveniment: header (Event ID + hex + nume),
                              apoi coloanele Cause | Remedy | Severity/response

Layout-ul textului extras de PyMuPDF aplatizeaza tabelul intr-un singur flux,
deci nu se poate distinge fiabil unde se termina coloana "Cause" si incepe
"Remedy" doar din text. Solutia: folosim geometria (coordonata x a fiecarei
linii) ca sa repartizam liniile pe coloane.

Output: scripts/fault_codes_<familie>.json  -- array JSON UTF-8 (ensure_ascii=false).
"""

import os
import re
import json

import fitz  # pymupdf

# ---------------------------------------------------------------------------
# Configuratie
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
MANUALS_DIR = os.path.join(PROJECT_ROOT, "manuals")

# Per manual: fisier PDF, familie, intervalul (0-indexat) de pagini al cap. 17.x
MANUALS = [
    {
        "file": "Lenze_i550_Manual.pdf",
        "familie": "Lenze_i550",
        # cap. 17.6 -> overview ~704-706, detaliat ~707-728
        "scan_start": 700,
        "scan_end": 740,
    },
    {
        "file": "Lenze_i950_Manual.pdf",
        "familie": "Lenze_i950",
        # cap. 17.5 -> overview ~568-579, detaliat ~580-647
        "scan_start": 565,
        "scan_end": 660,
    },
]

# Praguri coloane (coordonata x0 a liniei). Aceleasi in ambele manuale.
#   overview: Event ID ~58-65 | Event(hex+nume) ~93-155 | Severity ~380 | Config ~444
#             (i550: hex+nume la ~93;  i950: hex la ~109, nume la ~155)
#   detaliat: Cause ~58-67 | Remedy ~219-242 | Severity/response ~380
#             header eveniment: Event ID ~66-70, nume ~123-155
X_COL2 = 200.0   # detaliat: < X_COL2 -> Cause ; >= X_COL2 -> Remedy
X_COL3 = 340.0   # >= X_COL3 -> coloana Severity (overview si detaliat)
X_CONFIG = 420.0  # overview: >= X_CONFIG -> "Configurable in"
# overview: coloana "Event ID" e o banda ingusta in stanga; restul de sub
# X_COL3 (dar >= X_OVERVIEW_EVENT) apartine coloanei "Event" (hex + nume).
X_OVERVIEW_EVENT = 85.0  # overview: x0 < X_OVERVIEW_EVENT -> coloana Event ID

# Linii de antet/subsol care trebuie eliminate.
HEADER_FOOTER = {
    "diagnostics and fault elimination",
    "events, causes and remedies",
    "event id overview",
    "causes and remedies",
    "event id",
    "event",
    "severity",
    "configurable in",
    "cause",
    "remedy",
    "severity/response",
}

# Maparea Severity -> tip.  Severitatea poate avea sufixe (" > CiA402",
# " (configurable)") sau poate fi in germana ("Fehler").
SEVERITY_MAP = {
    "fault": "fault",
    "fehler": "fault",      # uneori manualul i950 are randuri ramase in germana
    "warning": "warning",
    "warnung": "warning",
    "trouble": "trouble",
    "no response": "no_response",
    "information": "info",
}

# Regex: header de eveniment din sectiunea detaliata, ex. "8784 0x2250"
# sau "537526027 0x2009FF0B" sau "0 0x00000000".
RE_DETAIL_HEADER = re.compile(r"^(\d+)\s+(0x[0-9A-Fa-f]+)\s*$")

# Regex: cod hex la inceputul textului "Event" din overview.
RE_HEX_PREFIX = re.compile(r"^(0x[0-9A-Fa-f]+)\b\s*(.*)$", re.DOTALL)


# ---------------------------------------------------------------------------
# Utilitare text
# ---------------------------------------------------------------------------

def clean_text(s):
    """Normalizeaza un fragment de text extras dintr-un PDF.

    - inlocuieste caracterele de bullet Wingdings ('' etc. si REPLACEMENT
      CHARACTER folosit ca bullet) cu '-'
    - normalizeaza spatiile
    """
    if not s:
        return ""
    # PyMuPDF reda glifele Wingdings ca U+FFFD (replacement) sau private-use.
    # In sectiunile cause/remedy acestea sunt marcatori de lista.
    out = []
    for ch in s:
        cp = ord(ch)
        if cp == 0xFFFD or 0xF000 <= cp <= 0xF0FF:
            out.append("-")
        else:
            out.append(ch)
    s = "".join(out)
    # normalizeaza spatii albe
    s = s.replace(" ", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\s*\n\s*", "\n", s)
    return s.strip()


def is_header_footer(line):
    """True daca linia e antet/subsol sau un numar de pagina simplu."""
    t = line.strip().lower()
    if not t:
        return True
    if t in HEADER_FOOTER:
        return True
    if re.fullmatch(r"\d{1,4}", t):  # numar de pagina simplu
        return True
    # marcaje de sectiune gen "17.6", "17.5.2"
    if re.fullmatch(r"\d{1,2}(\.\d{1,2}){1,3}", t):
        return True
    return False


def join_lines(lines):
    """Uneste linii de text aplicand de-hyphenation simpla.

    Liniile dintr-o coloana ingusta de PDF se rup des; reconstruim un text
    lizibil: liniile bullet ('- ...') raman pe randuri separate, restul se
    unesc cu spatiu.
    """
    if not lines:
        return None
    parts = []
    for raw in lines:
        ln = clean_text(raw)
        if not ln:
            continue
        if not parts:
            parts.append(ln)
            continue
        prev = parts[-1]
        starts_bullet = ln.startswith("- ") or ln == "-"
        if starts_bullet:
            parts.append(ln)
        elif prev.endswith("-") and not prev.endswith(" -"):
            # cuvant despartit la capat de rand
            parts[-1] = prev[:-1] + ln
        else:
            parts[-1] = prev + " " + ln
    text = "\n".join(p.strip() for p in parts if p.strip())
    text = re.sub(r"\n{2,}", "\n", text).strip()
    return text or None


# ---------------------------------------------------------------------------
# Extragerea liniilor cu geometrie
# ---------------------------------------------------------------------------

# Toleranta verticala (puncte) pentru gruparea liniilor pe acelasi rand vizual.
# In headerele sectiunii detaliate, Event ID si numele evenimentului sunt pe
# acelasi rand dar cu y0 diferit cu ~0.7 pt; le grupam pe acelasi rand ca sa
# Event ID-ul sa fie procesat inaintea numelui.
ROW_Y_TOL = 4.0


def get_page_lines(page):
    """Returneaza liniile unei pagini ca dict-uri {x0,y0,text}, sortate vizual.

    Liniile se grupeaza in randuri vizuale (dupa proximitatea y), apoi se
    ordoneaza randurile sus->jos si, in interiorul fiecarui rand, stanga->
    dreapta. Acest lucru garanteaza ca pe randul de antet al unei intrari
    detaliate "Event ID" (x0 mic) apare inaintea numelui (x0 mai mare), chiar
    daca numele are un y0 usor mai mic.
    """
    d = page.get_text("dict")
    raw = []
    for block in d.get("blocks", []):
        if block.get("type") != 0:  # doar blocuri de text
            continue
        for ln in block.get("lines", []):
            spans = ln.get("spans", [])
            txt = "".join(sp.get("text", "") for sp in spans)
            if txt is None:
                continue
            bbox = ln.get("bbox", [0, 0, 0, 0])
            raw.append({"x0": bbox[0], "y0": bbox[1], "text": txt})

    # grupare in randuri vizuale dupa y
    raw.sort(key=lambda l: l["y0"])
    rows = []
    for ln in raw:
        if rows and abs(ln["y0"] - rows[-1][0]) <= ROW_Y_TOL:
            rows[-1][1].append(ln)
        else:
            rows.append([ln["y0"], [ln]])

    lines = []
    for _y, group in rows:
        group.sort(key=lambda l: l["x0"])
        lines.extend(group)
    return lines


# ---------------------------------------------------------------------------
# Parsarea tabelului "Event ID overview"
# ---------------------------------------------------------------------------

def parse_overview_page(page, page_no, rows):
    """Parseaza un tabel overview de pe o pagina si adauga randuri in `rows`.

    Coloanele se determina dupa x0:
      Event ID  : x0 < X_OVERVIEW_EVENT          (numar pur -> rand nou)
      Event     : X_OVERVIEW_EVENT <= x0 < X_COL3 (hex + nume; hexul si numele
                                                   pot fi pe linii separate)
      Severity  : X_COL3 <= x0 < X_CONFIG
      Config    : x0 >= X_CONFIG

    Un rand logic incepe cand intalnim un numar pur in coloana "Event ID".
    Liniile urmatoare (nume care se intinde pe mai multe randuri, configurare
    pe doua linii) se acumuleaza in randul curent pana la urmatorul Event ID.
    """
    lines = get_page_lines(page)

    cur = None  # randul logic curent
    for ln in lines:
        text = ln["text"]
        stripped = text.strip()
        if not stripped:
            continue
        low = stripped.lower()
        x0 = ln["x0"]

        # antete de coloana
        if low in HEADER_FOOTER:
            continue

        # --- coloana Event ID (banda ingusta din stanga) ---
        if x0 < X_OVERVIEW_EVENT:
            if re.fullmatch(r"\d+", stripped):
                # Numar pur in coloana Event ID. Poate fi un Event ID real sau
                # numarul de pagina din subsol. Numarul de pagina ramane fara
                # coloana "Event" si va fi eliminat la finalizare.
                cur = {
                    "event_id": stripped,
                    "event_lines": [],
                    "severity": [],
                    "config": [],
                    "pagina": page_no,
                }
                rows.append(cur)
            # alt text in banda din stanga (bullet, markeri de sectiune) -> ignora
            continue

        if cur is None:
            continue

        # --- coloana Configurable in (dreapta) ---
        if x0 >= X_CONFIG:
            cur["config"].append(stripped)
            continue

        # --- coloana Severity (~340..X_CONFIG) ---
        if x0 >= X_COL3:
            cur["severity"].append(stripped)
            continue

        # --- coloana Event (hex + nume) ---
        # ignoram fragmente de paragraf descriptiv (ex. textul introductiv
        # "The following table contains..." apare la x0 ~ 56-70, deci sub
        # X_OVERVIEW_EVENT si e deja eliminat mai sus).
        cur["event_lines"].append(stripped)


def finalize_overview_row(row):
    """Transforma un rand brut de overview intr-un dict normalizat sau None."""
    event_id = row["event_id"].strip()
    if not event_id or not event_id.isdigit():
        return None

    event_text = clean_text(" ".join(row["event_lines"]).strip())
    if not event_text:
        # rand fara coloana Event -> probabil numarul de pagina captat gresit
        return None

    # separam codul hex de nume
    m = RE_HEX_PREFIX.match(event_text)
    if m:
        cod = m.group(1)
        nume = clean_text(m.group(2))
    else:
        cod = None
        nume = event_text

    severity_text = clean_text(" ".join(row["severity"]).strip())

    # Caz special: cand numele evenimentului e lung, extractia PDF poate lipi
    # cuvantul de severitate la sfarsitul coloanei "Event" (coloana Severity
    # ramane goala). Daca severitatea lipseste dar numele se termina cu o
    # eticheta de severitate recunoscuta, o desprindem din nume.
    if not severity_text and nume:
        nume, recovered = _split_trailing_severity(nume)
        if recovered:
            severity_text = recovered

    tip = severity_to_tip(severity_text)

    config_text = clean_text(" ".join(row["config"]).strip())
    if config_text in ("", "-"):
        config_text = None

    return {
        "event_id": event_id,
        "cod": cod,
        "nume": nume or None,
        "severity_raw": severity_text or None,
        "tip": tip,
        "configurable_in": config_text,
        "pagina": row["pagina"],
    }


# Etichete de severitate care pot fi lipite la coada numelui (cele mai lungi
# intai, ca sa potrivim varianta cu sufix inainte de cea simpla).
_TRAILING_SEVERITY = [
    "Fault > CiA402",
    "Fehler > CiA402",
    "Warning > CiA402",
    "No response",
    "Information",
    "Warning",
    "Trouble",
    "Fault",
    "Fehler",
]


def _split_trailing_severity(nume):
    """Daca `nume` se termina cu o eticheta de severitate, o desprinde.

    Returneaza (nume_curatat, severitate_sau_None).
    """
    for sev in _TRAILING_SEVERITY:
        if nume.endswith(" " + sev) or nume == sev:
            cut = nume[: len(nume) - len(sev)].rstrip()
            # nu desprindem daca ar ramane un nume gol
            if cut:
                return cut, sev
    return nume, None


def severity_to_tip(severity_text):
    """Converteste textul Severity in valoarea `tip`."""
    if not severity_text:
        return None
    s = severity_text.lower()
    # elimina sufixe gen "(configurable)" sau "> cia402"
    s = s.split(">")[0]
    s = s.split("(")[0]
    s = s.strip()
    # potriviri exacte intai
    if s in SEVERITY_MAP:
        return SEVERITY_MAP[s]
    # "no response" poate aparea ca "no response"
    for key, val in SEVERITY_MAP.items():
        if s.startswith(key):
            return val
    return None


# ---------------------------------------------------------------------------
# Parsarea sectiunii detaliate "Causes and remedies"
# ---------------------------------------------------------------------------

def parse_detail_pages(doc, page_indices):
    """Parseaza paginile sectiunii detaliate.

    Returneaza dict {event_id(str) -> {"cauza":..., "remediu":...}}.

    Algoritm:
      - liniile fiecarei pagini se grupeaza in randuri vizuale; pe randul de
        antet al unei intrari, "Event ID" (x0 mic) e procesat inaintea numelui
      - un header de eveniment ("<id> <hex>") deschide o intrare noua
      - intre header si eticheta "Cause" se afla numele evenimentului si
        eventual "Keypad display: ..."; aceste linii se IGNORA (poarta
        `seen_labels`: colectarea cauza/remediu incepe doar dupa ce am vazut
        etichetele de coloana)
      - dupa etichete, liniile se repartizeaza pe coloane dupa x0:
          Cause   : x0 < X_COL2
          Remedy  : X_COL2 <= x0 < X_COL3
          Severity: x0 >= X_COL3   (ignorat - severitatea vine din overview)
      - blocul "Related topics" si referintele "4..." sunt eliminate
    """
    result = {}
    cur = None  # {"event_id":..., "cause":[], "remedy":[], ...}

    def flush(entry):
        if not entry:
            return
        cauza = join_lines(entry["cause"])
        remediu = join_lines(entry["remedy"])
        # nu suprascriem o intrare deja existenta (un eveniment apare o
        # singura data in sectiunea detaliata, dar pastram prima aparitie)
        if entry["event_id"] not in result:
            result[entry["event_id"]] = {
                "cauza": cauza,
                "remediu": remediu,
            }

    for pidx in page_indices:
        page = doc[pidx]
        lines = get_page_lines(page)
        for ln in lines:
            text = ln["text"]
            stripped = text.strip()
            x0 = ln["x0"]

            if not stripped:
                continue

            # header de eveniment?  (ex. "8784 0x2250" / "0 0x00000000")
            hm = RE_DETAIL_HEADER.match(stripped)
            if hm:
                flush(cur)
                cur = {
                    "event_id": hm.group(1),
                    "cause": [],
                    "remedy": [],
                    "seen_labels": False,  # am intalnit randul Cause/Remedy/Sev?
                    "stop": False,         # am intrat in "Related topics"?
                }
                continue

            if cur is None:
                continue

            low = stripped.lower()

            # eticheta "Cause" deschide poarta de colectare (randul de etichete
            # apare imediat dupa numele evenimentului)
            if low == "cause":
                cur["seen_labels"] = True
                continue
            # celelalte etichete de coloana
            if low in ("remedy", "severity/response"):
                continue

            # blocul "Related topics" + referintele incrucisate ("4...^ NNN")
            if low == "related topics":
                cur["stop"] = True
                continue
            if cur.get("stop"):
                continue

            # inainte de etichete: numele evenimentului / "Keypad display:" ->
            # le ignoram (numele real vine din overview)
            if not cur["seen_labels"]:
                continue

            # antet/subsol (numar de pagina, marcaje de sectiune)
            if low in HEADER_FOOTER:
                continue
            if is_header_footer(stripped):
                continue

            # repartizare pe coloane dupa x0
            if x0 >= X_COL3:
                # coloana Severity/response -> ignorata (severitatea vine din
                # overview; contine si "Setting parameters:", "Blocking time:")
                continue
            elif x0 >= X_COL2:
                cur["remedy"].append(stripped)
            else:
                cur["cause"].append(stripped)

    flush(cur)
    return result


# ---------------------------------------------------------------------------
# Detectarea paginilor overview vs. detaliate
# ---------------------------------------------------------------------------

def classify_pages(doc, scan_start, scan_end):
    """Imparte intervalul scanat in pagini de overview si pagini detaliate.

    Returneaza (overview_pages, detail_pages) ca liste de indecsi 0-based.

    - Pagina de start a overview-ului contine titlul de subsectiune
      "17.x.1 Event ID overview" (titlul real, nu o referinta incrucisata).
    - Pagina de start a sectiunii detaliate contine "17.x.2 Causes and
      remedies".
    - Sectiunea detaliata se opreste la urmatoarea subsectiune ".3" sau la
      urmatorul capitol.

    Ancorele pe numarul de subsectiune sunt importante: in i950 exista, chiar
    inaintea capitolului 17.5, pagini cu tabele asemanatoare (liste de
    parametri, un tabel de evenimente rezidual) care altfel ar fi confundate
    cu overview-ul.
    """
    overview_pages = []
    detail_pages = []

    start_overview = None
    start_detail = None
    end_detail = None

    n = doc.page_count
    lo = max(0, scan_start)
    hi = min(n, scan_end)

    # titlul "17.x.1" urmat de "Event ID overview" (pe linia urmatoare)
    re_ov_head = re.compile(r"17\.\d+\.1\s*\nEvent ID overview")
    re_cr_head = re.compile(r"17\.\d+\.2\s*\nCauses and remedies")

    for pidx in range(lo, hi):
        text = doc[pidx].get_text()

        # inceputul subsectiunii "Event ID overview"
        if start_overview is None and re_ov_head.search(text):
            start_overview = pidx
        # inceputul subsectiunii detaliate "Causes and remedies"
        if start_detail is None and re_cr_head.search(text):
            start_detail = pidx
        # sfarsitul sectiunii detaliate = urmatoarea subsectiune .3 / capitol nou
        if start_detail is not None and end_detail is None and pidx > start_detail:
            if re.search(r"17\.\d+\.3\b", text) or re.search(r"^\s*18\s*\n", text):
                end_detail = pidx
                break

    if start_overview is None:
        start_overview = lo
    if start_detail is None:
        # fallback: cauta prima pagina cu un header de eveniment detaliat
        for pidx in range(start_overview, hi):
            if re.search(r"\n\d+\s+0x[0-9A-Fa-f]+\s*\n", "\n" + doc[pidx].get_text()):
                if "Causes and remedies" in doc[pidx].get_text():
                    start_detail = pidx
                    break
    if start_detail is None:
        start_detail = hi
    if end_detail is None:
        end_detail = hi

    overview_pages = list(range(start_overview, start_detail))
    detail_pages = list(range(start_detail, end_detail))
    return overview_pages, detail_pages


# ---------------------------------------------------------------------------
# Procesarea unui manual
# ---------------------------------------------------------------------------

def process_manual(spec):
    pdf_path = os.path.join(MANUALS_DIR, spec["file"])
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(pdf_path)

    doc = fitz.open(pdf_path)
    try:
        overview_pages, detail_pages = classify_pages(
            doc, spec["scan_start"], spec["scan_end"]
        )

        print(f"[{spec['familie']}] overview pages (0-idx): "
              f"{overview_pages[0] if overview_pages else '-'}.."
              f"{overview_pages[-1] if overview_pages else '-'}  "
              f"detail pages (0-idx): "
              f"{detail_pages[0] if detail_pages else '-'}.."
              f"{detail_pages[-1] if detail_pages else '-'}")

        # --- 1. parsam overview ---
        raw_rows = []
        for pidx in overview_pages:
            parse_overview_page(doc[pidx], pidx + 1, raw_rows)  # pagina 1-based

        overview = []
        for r in raw_rows:
            fr = finalize_overview_row(r)
            if fr is not None:
                overview.append(fr)

        # de-dup pe event_id (pastram prima aparitie)
        overview_by_id = {}
        for o in overview:
            if o["event_id"] not in overview_by_id:
                overview_by_id[o["event_id"]] = o

        # --- 2. parsam sectiunea detaliata ---
        detail_map = parse_detail_pages(doc, detail_pages)

        # --- 3. merge dupa Event ID ---
        records = []
        for event_id, ov in overview_by_id.items():
            det = detail_map.get(event_id, {})
            extra = {}
            if ov.get("configurable_in"):
                extra["configurable_in"] = ov["configurable_in"]

            rec = {
                "producator": "Lenze",
                "familie": spec["familie"],
                "cod": ov.get("cod"),
                "cod_secundar": event_id,
                "tip": ov.get("tip"),
                "nume": ov.get("nume"),
                "cauza": det.get("cauza"),
                "remediu": det.get("remediu"),
                "reactie": None,
                "confirmare": None,
                "extra": extra,
                "pagina": ov.get("pagina"),
                "sursa": spec["file"],
            }
            records.append(rec)

        # sortare numerica dupa Event ID, stabil
        records.sort(key=lambda r: int(r["cod_secundar"]))

        out_path = os.path.join(SCRIPT_DIR,
                                f"fault_codes_{spec['familie']}.json")
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(records, fh, ensure_ascii=False, indent=2)

        # statistici
        n_detail_matched = sum(
            1 for r in records if r["cauza"] or r["remediu"]
        )
        detail_only = set(detail_map) - set(overview_by_id)

        print(f"[{spec['familie']}] overview events: {len(overview_by_id)}  "
              f"detail entries: {len(detail_map)}  "
              f"merged-with-detail: {n_detail_matched}  "
              f"detail-without-overview: {len(detail_only)}")
        if detail_only:
            print(f"[{spec['familie']}] detail IDs not in overview (sample): "
                  f"{sorted(detail_only)[:10]}")
        print(f"[{spec['familie']}] -> {out_path}  ({len(records)} records)")

        return records
    finally:
        doc.close()


def main():
    for spec in MANUALS:
        process_manual(spec)
        print()


if __name__ == "__main__":
    main()
