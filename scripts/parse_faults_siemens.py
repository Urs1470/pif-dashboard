"""
parse_faults_siemens.py
Parse "List of faults and alarms" from Siemens SINAMICS List Manuals.
Writes one JSON file per manual to the scripts/ directory.
"""

import re
import json
import sys
from pathlib import Path

import fitz  # PyMuPDF


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MANUALS_DIR = Path(__file__).parent.parent / "manuals"
OUTPUT_DIR = Path(__file__).parent

MANUALS = [
    {
        "pdf": "SINAMICS_G120_List_Manual.pdf",
        "familie": "SINAMICS_G120",
        "page_start": 700,   # 0-indexed, inclusive
        "page_end": 810,     # 0-indexed, exclusive
    },
    {
        "pdf": "SINAMICS_G130_G150_List_Manual.pdf",
        "familie": "SINAMICS_G130_G150",
        "page_start": 1064,
        "page_end": 1495,
    },
    {
        "pdf": "SINAMICS_S120_S150_List_Manual.pdf",
        "familie": "SINAMICS_S120_S150",
        "page_start": 2450,
        "page_end": 2972,
    },
]

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Code line: letter + 5 digits, optionally followed by space and "(A)" / "(N)" / "(F)" etc.
CODE_RE = re.compile(r'^([FAC]\d{5})(?:\s*\([A-Z]\))?$', re.IGNORECASE)

# Label lines — each starts a named section
LABEL_RE = re.compile(
    r'^(Reaction(?: upon [A-Z])?|Acknowledge(?:ment)?(?:\. upon [A-Z])?|Acknowl\. upon [A-Z]|'
    r'Cause|Remedy|Note|See also'
    r'|Message value[^:]*|Fault value[^:]*|Alarm value[^:]*'
    r'|Message class|Drive object'
    r')\s*:(.*)$',
    re.IGNORECASE,
)

# Lines that are page headers/footers to be stripped
# Pattern 1: exactly "Faults and alarms" or "List of faults and alarms"
# Pattern 2: starts with "© Siemens AG"
# Pattern 3: starts with "SINAMICS" and contains "List Manual"
# Pattern 4: bare page number like "3-731" or "2510 " (standalone)
# Pattern 5: S120 chapter headers like "4 Faults and alarms" / "4.2 List of faults and alarms"
HEADER_EXACT = {
    "faults and alarms",
    "list of faults and alarms",
}

def is_header_footer(line: str) -> bool:
    stripped = line.strip()
    low = stripped.lower()

    # exact strings (case-insensitive)
    if low in HEADER_EXACT:
        return True

    # copyright line
    if stripped.startswith("© Siemens AG"):
        return True

    # SINAMICS ... List Manual lines
    if stripped.startswith("SINAMICS") and "List Manual" in stripped:
        return True

    # bare page-number patterns: "3-731", "3-1099", "2510", "2510 "
    if re.match(r'^\d+-\d+\s*$', stripped):
        return True
    if re.match(r'^\d{4}\s*$', stripped):
        return True

    # S120/S150 chapter sub-headers
    if re.match(r'^4\s+Faults and alarms\s*$', stripped, re.IGNORECASE):
        return True
    if re.match(r'^4\.\d+\s+List of faults and alarms\s*$', stripped, re.IGNORECASE):
        return True

    return False


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def extract_clean_lines(pdf_path: Path, page_start: int, page_end: int):
    """
    Yields (page_1based, line_text) for all non-empty, non-header/footer lines
    in pages [page_start, page_end).
    """
    doc = fitz.open(str(pdf_path))
    for page_idx in range(page_start, min(page_end, len(doc))):
        page = doc[page_idx]
        text = page.get_text("text")
        for raw_line in text.split("\n"):
            line = raw_line.rstrip()
            if not line.strip():
                continue
            if is_header_footer(line):
                continue
            yield (page_idx + 1, line)
    doc.close()


# ---------------------------------------------------------------------------
# Entry parsing
# ---------------------------------------------------------------------------

def parse_code_line(line: str):
    """
    Returns (code, tip) if line is a fault-code line, else None.
    Handles variants like:
      'F07083'
      'F07451 (A)'       — G120/S120: single letter
      'A01507 (F, N)'    — G130: two-letter, comma-separated
      'F01910 (N, A)'
    """
    stripped = line.strip()
    # Remove trailing annotation like " (A)", " (N, A)", " (F, N)", " (F, N, A)" etc.
    clean = re.sub(r'\s*\([A-Z,\s]+\)\s*$', '', stripped)
    clean = clean.strip()
    m = re.match(r'^([FAC])(\d{5})$', clean, re.IGNORECASE)
    if not m:
        return None
    letter = m.group(1).upper()
    tip_map = {'F': 'fault', 'A': 'alarm', 'C': 'safety'}
    return (clean.upper(), tip_map.get(letter, 'fault'))


def normalise_label(label: str) -> str:
    """Map raw label to a canonical key."""
    l = label.strip().lower()
    # Qualified variants MUST be checked before the bare 'reaction'/'acknowledge'
    # so they don't collapse into the main reaction/acknowledge slots.
    if re.match(r'^reaction upon\s+[a-z]$', l):
        # e.g. "reaction upon a" -> "reaction_upon_a"
        return l.replace(' ', '_')
    if re.match(r'^acknowledge upon\s+[a-z]$', l):
        return l.replace(' ', '_')
    if re.match(r'^acknowl\. upon\s+[a-z]$', l):
        return l.replace(' ', '_').replace('.', '')
    if l == 'reaction':
        return 'reaction'
    if l == 'acknowledge' or l == 'acknowledgement':
        return 'acknowledge'
    if l == 'cause':
        return 'cause'
    if l == 'remedy':
        return 'remedy'
    if l == 'note':
        return 'note'
    if l == 'see also':
        return 'see_also'
    if 'message value' in l and 'fault' not in l and 'alarm' not in l:
        return 'message_value'
    if 'fault value' in l:
        return 'fault_value'
    if 'alarm value' in l:
        return 'alarm_value'
    if l == 'message class':
        return 'message_class'
    if l == 'drive object':
        return 'drive_object'
    return l


# Labels that are "structural metadata" — they go into extra, not main fields
META_LABELS = {'message_value', 'fault_value', 'alarm_value',
               'see_also', 'note', 'message_class', 'drive_object'}

# Labels that qualify whether the reaction/ack applies
# (e.g., "Reaction upon A:", "Reaction upon F:", "Acknowl. upon A:")
# — stored in extra under e.g. "reaction_upon_a"
QUALIFIED_LABEL_RE = re.compile(
    r'^(Reaction upon ([A-Z])|Acknowledge upon ([A-Z])|Acknowl\. upon ([A-Z]))\s*:(.*)$',
    re.IGNORECASE,
)


def parse_entries(lines_iter):
    """
    lines_iter: iterable of (page_1based, line_text)
    Returns list of parsed entry dicts.
    """
    entries = []

    # State machine
    state = 'HUNTING'          # HUNTING -> IN_NAME -> IN_SECTION
    current_code = None
    current_tip = None
    current_page = None
    name_lines = []
    sections = {}              # label -> list of text lines
    current_label = None

    # Buffer to lookahead for "real entry" validation
    # We require a Reaction: or Cause: label within 6 non-empty lines after the code

    def flush_entry():
        """Assemble and store the current entry."""
        nonlocal current_code, current_tip, current_page, name_lines, sections, current_label

        if current_code is None:
            return

        # Build main fields
        nome = " ".join(name_lines).strip()
        cauza = "\n".join(sections.get('cause', [])).strip()
        remediu = "\n".join(sections.get('remedy', [])).strip()
        reactie = "\n".join(sections.get('reaction', [])).strip()
        confirmare = "\n".join(sections.get('acknowledge', [])).strip()

        # Extra fields
        extra = {}
        for key in ('message_value', 'fault_value', 'alarm_value',
                    'see_also', 'note', 'message_class', 'drive_object'):
            if key in sections:
                val = "\n".join(sections[key]).strip()
                if val:
                    extra[key] = val

        # Qualified reaction/ack variants go into extra too
        for key, val_lines in sections.items():
            if key.startswith('reaction_upon_') or key.startswith('acknowledge_upon_') or key.startswith('acknowl._upon_'):
                val = "\n".join(val_lines).strip()
                if val:
                    extra[key] = val

        entry = {
            "producator": "Siemens",
            "familie": None,       # filled by caller
            "cod": current_code,
            "cod_secundar": None,
            "tip": current_tip,
            "nume": nome,
            "cauza": cauza,
            "remediu": remediu,
            "reactie": reactie,
            "confirmare": confirmare,
            "extra": extra,
            "pagina": current_page,
            "sursa": None,         # filled by caller
        }
        entries.append(entry)

        # Reset state
        current_code = None
        current_tip = None
        current_page = None
        name_lines = []
        sections = {}
        current_label = None

    # We buffer lines to do a forward-scan for validation
    # Use a simple sliding window: collect up to 8 lines after a potential code
    pending_code = None
    pending_tip = None
    pending_page = None
    post_code_buf = []   # lines seen after pending_code before validation passes

    def try_commit_pending():
        """
        Check if post_code_buf has a Reaction: or Cause: label (real entry).
        Returns True if validated (pending becomes current), False if too many
        lines without a label (discard pending).
        """
        nonlocal pending_code, pending_tip, pending_page, post_code_buf
        nonlocal current_code, current_tip, current_page, name_lines, sections, current_label
        nonlocal state

        non_empty = [l for (_, l) in post_code_buf if l.strip()]
        for pg, line in post_code_buf:
            m = LABEL_RE.match(line.strip())
            if m:
                # Validated
                flush_entry()
                state = 'IN_NAME'
                current_code = pending_code
                current_tip = pending_tip
                current_page = pending_page
                name_lines = []
                sections = {}
                current_label = None
                pending_code = None
                pending_tip = None
                pending_page = None
                post_code_buf = []
                return True
        # Not yet enough lines to decide? Wait more
        if len(non_empty) < 8:
            return None  # undecided
        # Too many lines without a label — discard pending
        pending_code = None
        pending_tip = None
        pending_page = None
        post_code_buf = []
        return False

    def handle_line_in_state(page_no, line):
        nonlocal state, current_code, current_tip, current_page
        nonlocal name_lines, sections, current_label
        nonlocal pending_code, pending_tip, pending_page, post_code_buf

        stripped = line.strip()

        # Always check if this line is a new code
        parsed = parse_code_line(stripped)
        if parsed:
            new_code, new_tip = parsed
            # If we already have a pending code, check if validated
            if pending_code is not None:
                r = try_commit_pending()
                # Whether True/False/None, the new code starts a new pending
            if pending_code is not None:
                # still pending (undecided or just discarded)
                pass
            # Start new pending
            pending_code = new_code
            pending_tip = new_tip
            pending_page = page_no
            post_code_buf = []
            return

        # If there's a pending code, accumulate into post_code_buf
        if pending_code is not None:
            post_code_buf.append((page_no, line))
            r = try_commit_pending()
            if r is True:
                # Now in IN_NAME state; replay lines from post_code_buf
                # (they were already consumed above in try_commit_pending, but
                #  we need to process them as name/section content)
                # Actually they're already in the buffer — we process them below
                # via the replayed lines. try_commit_pending() only sets state.
                # We need to replay post_code_buf content:
                replay = list(post_code_buf)  # post_code_buf is cleared inside
                # But post_code_buf was cleared in try_commit_pending — we saved it above
                # Actually try_commit_pending clears post_code_buf to []; the current line
                # is already in post_code_buf before the call. Let's replay:
                for rp, rl in replay:
                    handle_line_in_state(rp, rl)
            return

        # Normal processing after validation
        if state == 'HUNTING':
            return  # shouldn't reach here normally

        # Check for a label
        # First try qualified variant
        qm = QUALIFIED_LABEL_RE.match(stripped)
        if qm:
            raw_label = qm.group(1)
            inline_val = qm.group(5).strip() if qm.group(5) else ''
            key = normalise_label(raw_label)
            # e.g. "reaction_upon_a", "acknowledge_upon_n"
            if key not in sections:
                sections[key] = []
            if inline_val:
                sections[key].append(inline_val)
            current_label = key
            state = 'IN_SECTION'
            return

        # Standard label
        m = LABEL_RE.match(stripped)
        if m:
            raw_label = m.group(1)
            inline_val = m.group(2).strip() if m.group(2) else ''
            key = normalise_label(raw_label)
            if key not in sections:
                sections[key] = []
            if inline_val:
                sections[key].append(inline_val)
            current_label = key
            state = 'IN_SECTION'
            return

        # Regular content line
        if state == 'IN_NAME':
            name_lines.append(stripped)
        elif state == 'IN_SECTION':
            if current_label is not None:
                if current_label not in sections:
                    sections[current_label] = []
                sections[current_label].append(stripped)

    # Process all lines
    for page_no, line in lines_iter:
        handle_line_in_state(page_no, line)

    # Commit any remaining pending
    if pending_code is not None:
        non_empty = [l for (_, l) in post_code_buf if l.strip()]
        for pg, ln in post_code_buf:
            m = LABEL_RE.match(ln.strip())
            if m:
                flush_entry()
                current_code = pending_code
                current_tip = pending_tip
                current_page = pending_page
                name_lines = []
                sections = {}
                current_label = 'IN_NAME'
                # process remaining post_code_buf lines
                for rpg, rln in post_code_buf:
                    if rln != ln:
                        handle_line_in_state(rpg, rln)
                break

    # Flush last entry
    flush_entry()

    return entries


# ---------------------------------------------------------------------------
# Robust streaming parser (simpler, more reliable alternative)
# ---------------------------------------------------------------------------

def parse_entries_v2(lines_iter):
    """
    Cleaner two-pass approach:
    Pass 1: collect all (page, line) pairs.
    Pass 2: scan for code lines, validate, build entries.
    """
    all_lines = list(lines_iter)

    entries = []
    i = 0
    n = len(all_lines)

    while i < n:
        page_no, line = all_lines[i]
        stripped = line.strip()
        parsed = parse_code_line(stripped)

        if not parsed:
            i += 1
            continue

        code, tip = parsed

        # Lookahead: find first label within next 8 non-empty lines
        non_empty_count = 0
        found_label = False
        for j in range(i + 1, min(i + 30, n)):
            _, lj = all_lines[j]
            sj = lj.strip()
            if not sj:
                continue
            non_empty_count += 1
            if LABEL_RE.match(sj) or QUALIFIED_LABEL_RE.match(sj):
                found_label = True
                break
            if non_empty_count >= 8:
                break

        if not found_label:
            i += 1
            continue

        # Valid entry — parse it
        entry_page = page_no
        i += 1

        # Collect name lines (before first label)
        name_lines = []
        while i < n:
            pg, ln = all_lines[i]
            s = ln.strip()
            if not s:
                i += 1
                continue
            # Stop at label or new code
            if LABEL_RE.match(s) or QUALIFIED_LABEL_RE.match(s):
                break
            pc = parse_code_line(s)
            if pc:
                break
            name_lines.append(s)
            i += 1

        # Collect sections until next code or end
        sections = {}
        current_label = None

        while i < n:
            pg, ln = all_lines[i]
            s = ln.strip()
            if not s:
                i += 1
                continue

            # New code line = end of this entry
            pc = parse_code_line(s)
            if pc:
                break

            # Check qualified label
            qm = QUALIFIED_LABEL_RE.match(s)
            if qm:
                raw_label = qm.group(1)
                inline_val = qm.group(5).strip() if qm.group(5) else ''
                key = normalise_label(raw_label)
                if key not in sections:
                    sections[key] = []
                if inline_val:
                    sections[key].append(inline_val)
                current_label = key
                i += 1
                continue

            # Check standard label
            m = LABEL_RE.match(s)
            if m:
                raw_label = m.group(1)
                inline_val = m.group(2).strip() if m.group(2) else ''
                key = normalise_label(raw_label)
                if key not in sections:
                    sections[key] = []
                if inline_val:
                    sections[key].append(inline_val)
                current_label = key
                i += 1
                continue

            # Content line
            if current_label is not None:
                sections[current_label].append(s)
            i += 1

        # Assemble entry
        nome = " ".join(name_lines).strip()
        cauza = "\n".join(sections.get('cause', [])).strip()
        remediu = "\n".join(sections.get('remedy', [])).strip()
        reactie = "\n".join(sections.get('reaction', [])).strip()
        confirmare = "\n".join(sections.get('acknowledge', [])).strip()

        extra = {}
        for key in ('message_value', 'fault_value', 'alarm_value',
                    'see_also', 'note', 'message_class', 'drive_object'):
            if key in sections:
                val = "\n".join(sections[key]).strip()
                if val:
                    extra[key] = val

        # Qualified reaction/ack variants
        for key, val_lines in sections.items():
            if (key.startswith('reaction_upon_') or
                    key.startswith('acknowledge_upon_') or
                    key.startswith('acknowl._upon_')):
                val = "\n".join(val_lines).strip()
                if val:
                    extra[key] = val

        entry = {
            "producator": "Siemens",
            "familie": None,
            "cod": code,
            "cod_secundar": None,
            "tip": tip,
            "nume": nome,
            "cauza": cauza,
            "remediu": remediu,
            "reactie": reactie,
            "confirmare": confirmare,
            "extra": extra,
            "pagina": entry_page,
            "sursa": None,
        }
        entries.append(entry)

    return entries


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def process_manual(cfg):
    pdf_path = MANUALS_DIR / cfg["pdf"]
    familie = cfg["familie"]
    sursa = cfg["pdf"]
    page_start = cfg["page_start"]
    page_end = cfg["page_end"]

    print(f"\n[{familie}] Opening {pdf_path.name} ...")
    if not pdf_path.exists():
        print(f"  ERROR: file not found: {pdf_path}")
        return 0

    print(f"  Extracting pages {page_start}..{page_end-1} (0-indexed) ...")
    lines_iter = extract_clean_lines(pdf_path, page_start, page_end)

    print(f"  Parsing entries ...")
    entries = parse_entries_v2(lines_iter)

    # Fill in familie and sursa
    for e in entries:
        e["familie"] = familie
        e["sursa"] = sursa

    out_path = OUTPUT_DIR / f"fault_codes_{familie}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    print(f"  -> {len(entries)} entries written to {out_path.name}")
    return len(entries)


def spot_check(familie: str, check_codes: list):
    """Print a few entries from the output JSON for spot-checking."""
    out_path = OUTPUT_DIR / f"fault_codes_{familie}.json"
    if not out_path.exists():
        print(f"  [spot-check] {out_path.name} not found")
        return
    with open(out_path, encoding="utf-8") as f:
        data = json.load(f)
    by_code = {e["cod"]: e for e in data}
    print(f"\n--- Spot-check {familie} ---")
    for code in check_codes:
        e = by_code.get(code)
        if e:
            print(f"\n  {e['cod']}  [{e['tip']}]  p{e['pagina']}")
            print(f"    nome  : {e['nume']}")
            print(f"    reactie: {e['reactie']}")
            print(f"    conf  : {e['confirmare']}")
            cauza_preview = (e['cauza'] or '')[:120].replace('\n', ' ')
            print(f"    cauza : {cauza_preview}")
            remediu_preview = (e['remediu'] or '')[:120].replace('\n', ' ')
            print(f"    remediu: {remediu_preview}")
            if e['extra']:
                print(f"    extra : {list(e['extra'].keys())}")
        else:
            print(f"\n  {code} NOT FOUND in {familie}")


if __name__ == "__main__":
    totals = {}
    for cfg in MANUALS:
        count = process_manual(cfg)
        totals[cfg["familie"]] = count

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for fam, cnt in totals.items():
        status = "OK" if cnt > 100 else "LOW - check page ranges"
        print(f"  {fam:35s}  {cnt:5d} entries  {status}")

    # Spot-check known entries from the inspection dump
    spot_check("SINAMICS_G120", ["F07083", "F07084", "F07086", "C01712", "C01714"])
    spot_check("SINAMICS_G130_G150", ["F01375", "F01380", "A01362", "A01416"])
    spot_check("SINAMICS_S120_S150", ["F07451", "F07452", "A07454", "F07515"])
