"""
parse_faults_danfoss.py
Parse the Troubleshooting chapter of the Danfoss VLT FC302 Programming Guide
and produce fault_codes_Danfoss_VLT_FC302.json.

Two-pass approach:
  1. Parse Table 6.1 (pages 352-354, 0-indexed) for each code's name, type
     indicators, trip-lock flag, and parameter reference.
  2. Parse detailed entries (pages 357-365, 0-indexed) for cauza + remediu.
  3. Merge by code number.
"""

import re
import json
import fitz  # pymupdf

PDF_PATH = r"D:\Projects\pif-dashboard\manuals\Danfoss_VLT_FC302_Programming_Guide.pdf"
OUT_PATH = r"D:\Projects\pif-dashboard\scripts\fault_codes_Danfoss_VLT_FC302.json"

# ---------------------------------------------------------------------------
# Noise detection — page headers / footers
# ---------------------------------------------------------------------------
NOISE_RE = [
    re.compile(r"^VLT[®\xae]?\s+AutomationDrive"),
    re.compile(r"^Danfoss A/S"),
    re.compile(r"^M0013101\s*$"),
    re.compile(r"^Programming Guide\s*$"),
    re.compile(r"^\d{3,}\s*$"),    # bare page numbers (3+ digits, e.g. 351)
    re.compile(r"^6\s*6\s*$"),     # section marker "6 6"
]
NOISE_EXACT = {
    "VLT® AutomationDrive FC 301/302",
}

# Additional noise only used in the TABLE parser (running head on table pages)
TABLE_NOISE_EXACT = {
    "Troubleshooting",
}


def is_noise(line: str) -> bool:
    """Noise for the details parser (does NOT filter 'Troubleshooting')."""
    s = line.strip()
    if s in NOISE_EXACT:
        return True
    for pat in NOISE_RE:
        if pat.match(s):
            return True
    return False


def is_table_noise(line: str) -> bool:
    """Noise for the table parser (includes 'Troubleshooting' running head)."""
    s = line.strip()
    if s in TABLE_NOISE_EXACT:
        return True
    return is_noise(s)


# ---------------------------------------------------------------------------
# PART 1 – Table 6.1 parser
#
# The PDF extracts each table cell on its own line, in left-to-right,
# top-to-bottom column order per page.  For each fault row the order is:
#   <number>
#   <description>          (sometimes multi-line, but each part on own line)
#   <warning-marker>       X | (X) | –
#   <alarm-marker>         X | (X) | – [optional footnote suffix]
#   <triplock-marker>      X | (X) | –
#   <param-ref>            text or –  (may be 2 lines; absent for some rows)
#
# The dash character used in the table is U+2013 (–), not ASCII minus.
# ---------------------------------------------------------------------------

TABLE_PAGES = range(352, 355)   # 0-indexed pages 352, 353, 354

# Column header tokens to skip
TABLE_HEADERS = {"Number", "Description", "Warning", "Alarm/",
                 "trip", "trip lock", "Parameter", "reference"}

# Introduction / prose lines to skip on these pages
INTRO_SKIP_PREFIXES = (
    "A warning or an alarm",
    "light on the front",
    "by a code",
    "A warning remains",
    "present.",
    "motor may still",
    "critical,",
    "In the event of an alarm,",
    "Reset the alarm",
    "been rectified",
    "3 ways to reset",
    "Press [Reset]",
    "Via a digital input",
    "Via serial communication",
    "NOTICE",
    "After a manual reset",
    "restart the motor",
    "If an alarm cannot",
    "cause has not been",
    "(see also Table",
    "Alarms that are trip locked",
    "that the mains supply",
    "alarm can be reset",
    "frequency converter is no longer",
    "once the cause",
    "Alarms that are not trip locked",
    "automatic reset function",
    "(Warning: Automatic",
    "If a warning or alarm",
    "this means that either",
    "it is possible to specify",
    "should be shown",
    "This is possible, for instance",
    "Thermal Protection.",
    "on coasting,",
    "problem has been rectified",
    "flashing until",
    "No missing motor phase",
    "no stall detection",
    "Construction is set",
    "(X) Dependent",
    "1) Cannot",
    "Table 6.1",
    "6.1 Status Messages",
    "6 Troubleshooting",
    "6 6",
    "•",
)


def is_table_skip(s: str) -> bool:
    if not s:
        return True
    if is_table_noise(s):
        return True
    if s in TABLE_HEADERS:
        return True
    for pfx in INTRO_SKIP_PREFIXES:
        if s.startswith(pfx):
            return True
    return False


# A marker cell is one of: X, (X), –, –  (or with trailing footnote like 1))
MARKER_RE = re.compile(r"^[\(\)Xx–\-—]+\d*\)?\s*$")


def is_marker(s: str) -> bool:
    return bool(MARKER_RE.match(s.strip()))


def marker_has_x(s: str) -> bool:
    return "x" in s.lower() or "X" in s


NUMBER_RE = re.compile(r"^\d+$")


def parse_table(doc: fitz.Document) -> dict:
    """
    Returns dict: code_str -> {
        "nome": str,
        "warning": bool,
        "alarm": bool,
        "triplock": bool,
        "parametru": str | None,
    }
    """
    lines = []
    for pg in TABLE_PAGES:
        page = doc[pg]
        for raw in page.get_text().split("\n"):
            s = raw.strip()
            if not is_table_skip(s):
                lines.append(s)

    table = {}
    i = 0
    n = len(lines)

    while i < n:
        s = lines[i]

        if not NUMBER_RE.match(s):
            i += 1
            continue

        code = s
        i += 1

        # Collect description lines (until we hit a marker or another number)
        desc_parts = []
        while i < n:
            nxt = lines[i]
            if not nxt:
                i += 1
                continue
            if is_marker(nxt) or NUMBER_RE.match(nxt):
                break
            desc_parts.append(nxt)
            i += 1
        description = " ".join(desc_parts)

        # Collect 1-3 marker cells
        markers = []
        while i < n and len(markers) < 3:
            nxt = lines[i]
            if not nxt:
                i += 1
                continue
            if is_marker(nxt):
                markers.append(nxt)
                i += 1
            else:
                break

        # Pad to 3 if fewer (e.g., some rows have only 2 dashes before param)
        while len(markers) < 3:
            markers.append("–")

        # Collect parameter reference (text until next number or marker)
        param_parts = []
        while i < n:
            nxt = lines[i]
            if not nxt:
                i += 1
                continue
            if NUMBER_RE.match(nxt) or is_marker(nxt):
                break
            # A lone dash means no param ref; stop collecting
            if nxt in ("–", "-", "—"):
                i += 1
                break
            param_parts.append(nxt)
            i += 1

        parametru = " ".join(param_parts).strip() or None
        if parametru in ("–", "-", "—", ""):
            parametru = None

        table[code] = {
            "nome": description,
            "warning": marker_has_x(markers[0]),
            "alarm": marker_has_x(markers[1]),
            "triplock": marker_has_x(markers[2]),
            "parametru": parametru,
        }

    return table


# ---------------------------------------------------------------------------
# PART 2 – Detailed entries parser
#
# Entry header: (WARNING|ALARM|WARNING/ALARM) N, Name
# Body: cause text (possibly multi-paragraph), then optional "Troubleshooting"
#       section with bulleted steps.
# Bullets: "•" on its own line, then one or more continuation lines.
#
# The "WARNING HIGH VOLTAGE" safety box must be filtered from remedia.
# ---------------------------------------------------------------------------

DETAIL_PAGES = range(357, 366)  # 0-indexed 357..365

ENTRY_HDR_RE = re.compile(
    r"^(WARNING/ALARM|WARNING|ALARM)\s+(\d+),?\s*(.*?)\s*$"
)

# Lines to skip inside bullet sections (embedded tables, footnotes, etc.)
# Also matches voltage-table data lines like "3 x 200–", "[VDC]", bare numbers
BULLET_SKIP_RE = re.compile(
    r"^Table\s+\d+\.\d+"              # "Table 6.4 ..."
    r"|^3 x \d+"                       # "3 x 200–"
    r"|^\[VDC\]"                       # "[VDC]"
    r"|^\d+\s*(V|Hz|kHz|A|rpm|°C)?\s*$"  # bare numbers or simple values
)


def normalize_text(text: str) -> str:
    """Join hyphenated line-break artifacts like 'communi- cation' -> 'communication'."""
    return re.sub(r"(\w)-\s+(\w)", r"\1\2", text)


# Safety warning box lines to drop entirely
SAFETY_LINES = {
    "WARNING",
    "HIGH VOLTAGE",
    "Frequency converters contain high voltage when",
    "connected to AC mains input, DC supply, or load sharing.",
    "Failure to use qualified personnel to install, start up, and",
    "maintain the frequency converter can result in death or",
    "serious injury.",
    "Disconnect power before proceeding.",
}


def parse_details(doc: fitz.Document) -> dict:
    """
    Returns dict: code_str -> {
        "tip": "warning" | "alarm" | "warning_alarm",
        "nome": str | None,
        "cauza": str | None,
        "remediu": str | None,
        "pagina": int,   # 1-based physical PDF page
    }
    """
    # Collect (page_0idx, stripped_line)
    items = []
    for pg in DETAIL_PAGES:
        page = doc[pg]
        for raw in page.get_text().split("\n"):
            items.append((pg, raw.strip()))

    n = len(items)
    entries = {}

    i = 0
    while i < n:
        pg, s = items[i]

        m = ENTRY_HDR_RE.match(s)
        if not m:
            i += 1
            continue

        typ_raw = m.group(1)
        code = m.group(2)
        name = m.group(3).strip(" ,") or None

        if typ_raw == "WARNING/ALARM":
            tip = "warning_alarm"
        elif typ_raw == "WARNING":
            tip = "warning"
        else:
            tip = "alarm"

        pagina = pg + 1   # 1-based

        i += 1

        cauza_parts = []
        remediu_lines = []
        in_troubleshooting = False
        bullet_open = False       # True when we've just seen a bare "•"
        in_embedded_table = False # True after we detect a Table N.N line

        while i < n:
            _pg, s2 = items[i]

            # Stop at next entry header
            if ENTRY_HDR_RE.match(s2):
                break

            # Skip noise and blanks
            if not s2 or is_noise(s2):
                i += 1
                continue

            # Skip safety box
            if s2 in SAFETY_LINES:
                i += 1
                continue

            # Detect Troubleshooting section boundary
            if s2 == "Troubleshooting":
                in_troubleshooting = True
                bullet_open = False
                in_embedded_table = False
                i += 1
                continue

            if not in_troubleshooting:
                # Ignore stray bullet markers in cause text
                if s2 == "•":
                    i += 1
                    continue
                cauza_parts.append(s2)
            else:
                if s2 == "•":
                    bullet_open = True
                    in_embedded_table = False
                    i += 1
                    continue
                # Detect embedded table start (e.g. "Table 6.4 shows ...")
                if re.match(r"^Table\s+\d+\.\d+", s2):
                    in_embedded_table = True
                    i += 1
                    continue
                # Skip embedded table / footnote / bare data lines
                if in_embedded_table or BULLET_SKIP_RE.match(s2):
                    i += 1
                    continue
                if bullet_open:
                    # First line of a new bullet
                    remediu_lines.append("- " + s2)
                    bullet_open = False
                else:
                    # Continuation line of the previous bullet
                    if remediu_lines:
                        remediu_lines[-1] = remediu_lines[-1] + " " + s2
                    else:
                        # No bullet yet — treat as first bullet line
                        remediu_lines.append("- " + s2)

            i += 1

        cauza_raw = " ".join(cauza_parts).strip() or None
        cauza = normalize_text(cauza_raw) if cauza_raw else None

        remediu_raw = "\n".join(remediu_lines).strip() or None
        remediu = normalize_text(remediu_raw) if remediu_raw else None

        entries[code] = {
            "tip": tip,
            "nome": name,
            "cauza": cauza,
            "remediu": remediu,
            "pagina": pagina,
        }

    return entries


# ---------------------------------------------------------------------------
# PART 3 – Merge table + details -> output list
# ---------------------------------------------------------------------------

def derive_tip(row: dict) -> str:
    w = row["warning"]
    a = row["alarm"]
    tl = row["triplock"]
    if w and a:
        return "warning_alarm"
    if w:
        return "warning"
    if a or tl:
        return "alarm"
    return "alarm"


def build_output(table: dict, details: dict) -> list:
    all_codes = sorted(
        set(table.keys()) | set(details.keys()),
        key=lambda x: int(x)
    )

    results = []
    for code in all_codes:
        t = table.get(code)
        d = details.get(code)

        if t and d:
            tip = d["tip"]
            nome = d["nome"] or t["nome"]
            cauza = d["cauza"]
            remediu = d["remediu"]
            parametru = t["parametru"]
            trip_lock = t["triplock"]
            pagina = d["pagina"]
        elif t:
            tip = derive_tip(t)
            nome = t["nome"]
            cauza = None
            remediu = None
            parametru = t["parametru"]
            trip_lock = t["triplock"]
            pagina = None
        else:
            # Details only (no table row)
            tip = d["tip"]
            nome = d["nome"]
            cauza = d["cauza"]
            remediu = d["remediu"]
            parametru = None
            trip_lock = False
            pagina = d["pagina"]

        results.append({
            "producator": "Danfoss",
            "familie": "Danfoss_VLT_FC302",
            "cod": code,
            "cod_secundar": None,
            "tip": tip,
            "nume": nome,
            "cauza": cauza,
            "remediu": remediu,
            "reactie": None,
            "confirmare": None,
            "extra": {
                "parametru": parametru,
                "trip_lock": trip_lock,
            },
            "pagina": pagina,
            "sursa": "Danfoss_VLT_FC302_Programming_Guide.pdf",
        })

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    doc = fitz.open(PDF_PATH)
    print(f"PDF loaded: {len(doc)} pages")

    print("Parsing Table 6.1 ...")
    table = parse_table(doc)
    print(f"  Table entries: {len(table)}")
    if len(table) < 50:
        # Debug: show first 5 table entries
        for k, v in list(table.items())[:5]:
            print(f"    [{k}] {v}")

    print("Parsing detailed entries ...")
    details = parse_details(doc)
    print(f"  Detail entries: {len(details)}")

    print("Merging ...")
    output = build_output(table, details)
    print(f"  Total merged entries: {len(output)}")

    doc.close()

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nWritten: {OUT_PATH}")

    # Spot-check entries 1, 17, 29
    print("\n--- Spot check: codes 1, 17, 29 ---")
    for entry in output:
        if entry["cod"] in ("1", "17", "29"):
            print(json.dumps(entry, ensure_ascii=False, indent=2))
            print()

    # Stats
    with_remediu = sum(1 for e in output if e["remediu"])
    table_only = sum(1 for e in output if e["pagina"] is None)
    print(f"Entries with remediu: {with_remediu}")
    print(f"Table-only entries (no detail page): {table_only}")


if __name__ == "__main__":
    main()
