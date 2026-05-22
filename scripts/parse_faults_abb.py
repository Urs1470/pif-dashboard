#!/usr/bin/env python3
"""
Parser for ABB ACS580 / ACS880 drive fault codes ("Fault tracing" chapter).

These manuals lay the fault list out as a 4-column table:

    Code (hex) | Warning/Fault/Event name (+ Aux. code sub-rows) | Cause | What to do

Plain text extraction collapses the columns into nonsense, so this parser uses
LAYOUT-AWARE extraction via pymupdf (`page.get_text("words")`) and reconstructs
rows + columns from word x/y coordinates -- the same technique audit_pdf.py's
`parse_abb()` uses for parameter tables.

The 3-line table header ("Code (hex)" / "Warning|Fault / Aux. code" /
"Cause" / "What to do") repeats at the top of every table page; we re-detect the
four column x-boundaries from it on each page (the left margin shifts ~20 px
between odd and even pages).

Output: one JSON file per manual -- data/fault_codes/fault_codes_<familie>.json
(the deployed data location that load_fault_codes.py reads) -- a JSON array of
fault objects (see MODULE doc / the spec for the schema).

Usage:
    python scripts/parse_faults_abb.py            # parse both manuals
    python scripts/parse_faults_abb.py ACS580     # just one
"""
import os
import re
import sys
import json
from pathlib import Path

try:
    import fitz  # pymupdf
except ImportError:
    sys.stderr.write("ERROR: pymupdf not installed. Run: pip install pymupdf\n")
    sys.exit(2)

ROOT = Path(__file__).resolve().parent.parent
MANUALS_DIR = ROOT / 'manuals'
# Deployed data location -- the same directory load_fault_codes.py reads from
# (ROOT/data/fault_codes). The parser writes the regenerated JSON straight here.
OUT_DIR = ROOT / 'data' / 'fault_codes'

# Per-manual config. `pages` is the 0-indexed page span of the Fault tracing
# chapter (inclusive) -- a generous superset; non-table pages are skipped
# automatically because they lack the 4-column header.
MANUALS = {
    'ACS580': {
        'pdf': 'ACS580_Firmware_Manual.pdf',
        'pages': range(534, 567),
    },
    'ACS880': {
        'pdf': 'ACS880_Primary_Firmware_Manual.pdf',
        'pages': range(574, 629),
    },
}

# A main 4-char code: hex (warnings A2B4, faults 2310/FF61) -- exactly 4 hex chars.
MAIN_CODE_RE = re.compile(r'^[0-9A-Fa-f]{4}$')
# An aux code in the name column: a short hex/number token, optionally a pair
# ("0000 0001"), or a range ("000E...0010"). The separator between a pair may be
# whitespace, literal dots, or the unicode ellipsis U+2026 that ABB's PDF uses.
AUX_CODE_RE = re.compile(
    '^[0-9A-Fa-f]{2,4}(?:[\\s\u2026.]+[0-9A-Fa-f]{2,4})?$'
)

# Tokens that make up the running header / footer: the words "Fault" / "tracing"
# and a bare page number. NOTE: a 4-digit fault code (1080, 2310, ...) is NOT
# noise -- noise is detected at ROW level (see _is_noise_row), never by matching
# a single 4-digit token, which would wrongly reject numeric fault codes.
_RUNHEAD_WORD_RE = re.compile(r'^(?:fault|tracing)$', re.IGNORECASE)
_PAGENUM_RE = re.compile(r'^\d{1,4}$')

# Annotation text that ABB places in the NAME column on continuation rows but
# which is NOT part of the warning/fault name -- e.g. "Programmable warning:
# 31.24 Stall function" or the tag "(Editable message text)". These annotation
# rows are interleaved (by y-position) with the real Cause text, so they cannot
# be cleanly merged into either field; once detected, the parser simply drops
# the name-column tokens for the rest of that main code's block. The Cause
# column's own text still reconstructs correctly on its own.
_NAME_ANNOTATION_RE = re.compile(
    r'^(?:Programmable\s+(?:warning|fault|event)|\(Editable\s+message\s+text\))',
    re.IGNORECASE,
)


def _clean(text):
    """Collapse whitespace and repair PDF line-break hyphenation."""
    text = re.sub(r'\s+', ' ', text or '').strip()
    # 'intern- ally' -> 'internally'  (hyphen + space + lowercase continuation)
    text = re.sub(r'(\w)-\s+([a-z])', r'\1\2', text)
    # Normalise unicode ellipsis / odd glyphs sometimes used as bullets.
    text = text.replace('\u2026', '...')
    return text.strip()


# Bullet / dot glyphs that ABB's PDF leaves dangling in otherwise-empty
# continuation cells. When such a glyph lands alone in the Cause or What-to-do
# column it is decoration, not content, and ends up stuck on the tail of the
# field. U+2022 BULLET, U+00B7 MIDDLE DOT, U+25CF/25AA black shapes, U+2023
# TRIANGULAR bullet, U+2043 HYPHEN BULLET, plus the symbol-font code points
# U+F06E / U+F0B7 ABB uses for list markers.
_BULLET_CHARS = '\u2022\u00b7\u25cf\u25aa\u25a0\u2023\u2043\u2219\uf06e\uf0b7\uf0a7'
# A token that is *only* bullet glyphs (a stray decoration cell).
_BULLET_ONLY_RE = re.compile('^[' + _BULLET_CHARS + r'\s]+$')
# Trailing run of whitespace + bullet glyphs to peel off a finished field.
_TRAILING_BULLET_RE = re.compile('[\\s' + _BULLET_CHARS + ']*[' + _BULLET_CHARS
                                 + '][\\s' + _BULLET_CHARS + ']*$')


def _strip_trailing_bullets(text):
    """Remove any trailing whitespace + stray bullet/dot glyphs from a finished
    `cauza` / `remediu` value. ABB scatters lone bullet glyphs into empty
    continuation cells; the parser appends them, leaving a dangling 'B7'/'2022'
    on the tail. Mid-text bullets (genuine inline list separators) are kept."""
    if not text:
        return text
    return _TRAILING_BULLET_RE.sub('', text).rstrip()


def _looks_like_instruction(text):
    """True if `text` looks like the START of a real "What to do" instruction
    rather than a stray wrapped fragment of the main code's instruction.

    ABB instructions begin with a capitalised verb ("Check ...", "Contact ...",
    "Reset ...", "See ...") or a bullet glyph. A wrapped fragment instead begins
    mid-sentence with a lowercase word ("drive.", "and closing in motor cable").
    """
    text = (text or '').strip()
    if len(text) < 4:
        return False
    # Bullet-led aux instructions.
    if text[0] in '\u2022\u25cf*?\uf06e':
        return True
    # A genuine instruction starts with a capitalised word; a wrapped fragment
    # starts lowercase ("drive.", "and closing ..."). Require >= 2 words too.
    if len(text.split()) < 2:
        return False
    return text[0].isalpha() and text[0].isupper()


def _is_noise_row(all_toks):
    """True if a row is nothing but running-header/footer junk -- i.e. it holds
    only the words 'Fault'/'tracing' and/or a single bare page number, with no
    real content. A 4-digit fault code never triggers this because such a row
    always carries a name token alongside it (so `leftover` is non-empty)."""
    if not all_toks:
        return True
    leftover = [t for t in all_toks
                if not _RUNHEAD_WORD_RE.match(t) and not _PAGENUM_RE.match(t)]
    return not leftover


def _is_bullet_only_row(all_toks):
    """True if a row holds nothing but stray bullet/dot glyphs. ABB sprinkles
    lone bullet glyphs into otherwise-empty Cause / What-to-do cells (they
    render their own y-row); such a row carries no content and must not be
    appended to any field, or it leaves a dangling bullet on the tail."""
    if not all_toks:
        return False
    return all(_BULLET_ONLY_RE.match(t) for t in all_toks)


# NOTE: there is intentionally no per-token "strip noise from content" helper.
# The running header ("Fault tracing 553") always occupies its own y-row near
# the page top (~y18), far above the first table row (~y48+), so `_is_noise_row`
# discards it wholesale. Content rows never contain stray header words, and the
# word "fault" is common, legitimate content ("internal fault limit", "earth
# fault") that must never be removed.


def _group_rows(words, y_tol=3):
    """Group word tuples into rows keyed by quantised y0. Returns sorted list of
    (y, [(x0, x1, text), ...]) with each row's words sorted left-to-right."""
    buckets = {}
    for w in words:
        x0, y0, x1, y1, txt = w[0], w[1], w[2], w[3], w[4]
        if not txt.strip():
            continue
        key = round(y0 / y_tol) * y_tol
        buckets.setdefault(key, []).append((x0, x1, txt))
    rows = []
    for key in sorted(buckets):
        row = sorted(buckets[key], key=lambda t: t[0])
        rows.append((key, row))
    return rows


def _detect_columns(rows):
    """Locate the 4-column table header and return column x-boundaries.

    The header spans up to 3 stacked y-rows that sit close together, e.g.:
        Code            Warning / Aux. code     Cause     What to do
        (hex)
    Strategy: find the ANCHOR row -- the one holding both 'cause' and a 'what'
    token. Then read column-label x-positions only from rows within a tight
    y-window (+/- ~28 px) of that anchor, so stray body words like 'Fault' in a
    fault name, or the running header 'Fault tracing', cannot poison the result.

    Returns dict {x_name, x_cause, x_todo, x_code, header_y_max} or None.
    `header_y_max` is the y of the lowest header line so callers skip the header.
    """
    top = rows[:14]

    # 1) Anchor: the row containing 'cause' AND a 'what' token.
    anchor_y = cause_x = todo_x = None
    for y, row in top:
        toks = [(x0, t.lower()) for x0, x1, t in row]
        joined = ' '.join(t for _, t in toks)
        if any(t == 'cause' for _, t in toks) and 'what' in joined and 'do' in joined:
            anchor_y = y
            for x0, t in toks:
                if t == 'cause':
                    cause_x = x0
                elif t == 'what':
                    todo_x = x0
            break
    if anchor_y is None or cause_x is None or todo_x is None:
        return None

    # 2) Header block = rows whose y is within +/-14 px of the anchor. The
    # header is at most 3 stacked lines (~9 px total) so this window is tight
    # enough to exclude both the page-top running header (~y18) and the section
    # heading ("Fault messages" / "Warning messages", ~24 px above the anchor),
    # whose word "Fault"/"Warning" would otherwise be mistaken for a column.
    code_x = name_x = None
    header_ys = [anchor_y]
    for y, row in top:
        if abs(y - anchor_y) > 14:
            continue
        toks = [(x0, t.lower()) for x0, x1, t in row]
        is_header_row = False
        for x0, t in toks:
            if t == 'code':
                # Leftmost 'code' that is left of the cause column.
                if x0 < cause_x - 5 and (code_x is None or x0 < code_x):
                    code_x = x0
                is_header_row = True
            if t in ('event', 'warning', 'fault') and x0 < cause_x - 5:
                if name_x is None or x0 < name_x:
                    name_x = x0
                is_header_row = True
            if t in ('(hex)', 'hex') or 'aux' in t:
                is_header_row = True
        if is_header_row:
            header_ys.append(y)

    # 3) Fallbacks if a label was not isolated (rare).
    if code_x is None:
        code_x = 34
    if name_x is None:
        name_x = code_x + 25

    # Column boundaries: a word belongs to a column if x0 >= the column start.
    # Small left pads absorb words that begin a hair early.
    return {
        'x_name': name_x - 6,
        'x_cause': cause_x - 6,
        'x_todo': todo_x - 6,
        'x_code': code_x - 6,
        'header_y_max': max(header_ys),
    }


def _split_row(row, cols):
    """Split one row's words into the four columns by x-coordinate.
    Returns (code_toks, name_toks, cause_toks, todo_toks)."""
    code_toks, name_toks, cause_toks, todo_toks = [], [], [], []
    for x0, x1, t in row:
        if x0 < cols['x_name']:
            code_toks.append(t)
        elif x0 < cols['x_cause']:
            name_toks.append(t)
        elif x0 < cols['x_todo']:
            cause_toks.append(t)
        else:
            todo_toks.append(t)
    return code_toks, name_toks, cause_toks, todo_toks


def _classify(code, table_tip):
    """Decide tip ('warning' | 'fault' | 'event') for a main code.

    table_tip is what the surrounding table says ('warning', 'fault', or None
    when the manual mixes everything in one table). For the mixed case we fall
    back to the ABB convention: warning codes start with 'A'.
    """
    if table_tip in ('warning', 'fault', 'event'):
        return table_tip
    # Mixed table (ACS880 main list): A-prefixed = warning, else fault.
    if code[:1].upper() == 'A':
        return 'warning'
    return 'fault'


def _parse_page(page, cols_hint, table_tip):
    """Parse one table page. Returns (entries, cols, todo_target_is_aux) where
    `entries` is a list of raw row-records and `cols` is the column layout
    detected (or the hint).

    Each entry: {code, name, cause, remediu, aux_codes:[{cod,cauza,remediu}]}.
    `aux_codes` accumulates aux sub-rows that belong to the *last* main code; a
    main code's aux rows may also continue onto the next page, handled by the
    caller via the `pending` mechanism.

    `todo_target_is_aux` reports, for the LAST main code of the page, whether its
    "What to do" stream was last flowing into an aux sub-row (True) or into the
    main code itself (False). ABB's "What to do" column frequently wraps PAST the
    bottom of the page; the first rows of the next page then carry the tail of
    that cell. The caller uses this flag to route that page-leading continuation
    back to the correct record (see `_leading_continuation`).
    """
    rows = _group_rows(page.get_text("words"))
    cols = _detect_columns(rows) or cols_hint
    if cols is None:
        return [], cols_hint, False

    # Index the first row strictly below the header so we don't ingest header
    # words as content.
    body = [(y, r) for y, r in rows if y > cols['header_y_max'] + 1]

    entries = []          # finished main-code records on this page
    current = None        # main record being built
    current_aux = None    # aux sub-record being built (dict) or None
    # ABB interleaves a main code's multi-line "What to do" with its aux-code
    # rows. Two layouts exist and are consistent within one main code's block:
    #   (a) aux codes carry their OWN what-to-do (e.g. fault FF61);
    #   (b) aux codes carry only a cause and the main's what-to-do is a single
    #       instruction list that wraps PAST the aux rows (e.g. warning A2B4).
    # We decide which layout applies from the FIRST aux row of each main code
    # and stick with it: `aux_block_owns_todo` True => route aux + continuation
    # todo to the aux; False => all wrapped todo belongs to the main.
    aux_block_owns_todo = None  # None until the first aux row of the main code
    # Once an "(Editable message text)" tag or "Programmable warning:" annotation
    # appears in the name column, every later name-column row for this main code
    # is part of that annotation -- route it to the cause, never the name.
    name_annotation_mode = False
    # ABB's "What to do" column can wrap PAST the next code's row. While the
    # current code has not yet started its own what-to-do, todo-column fragments
    # that do not look like a fresh instruction (lowercase, mid-sentence) are
    # really the PREVIOUS code's wrapped what-to-do -- routed back to it.
    prev_entry = None            # the most recently flushed main record
    current_todo_started = False  # has `current` received any what-to-do yet?
    # Tracks, for the main code currently open, whether the most recent piece of
    # "What to do" text went into an aux sub-row (True) or the main code (False).
    # ABB's What-to-do cell can wrap past the bottom of the page; the caller
    # needs to know which record on the previous page should receive that
    # page-crossing tail. Reset to False at the start of every main code.
    last_todo_was_aux = False

    def flush_aux():
        nonlocal current_aux
        if current_aux is not None and current is not None:
            current_aux['cauza'] = _clean(current_aux['cauza'])
            current_aux['remediu'] = _clean(current_aux['remediu'])
            if current_aux['cod'] or current_aux['cauza'] or current_aux['remediu']:
                current['aux_codes'].append(current_aux)
        current_aux = None

    def flush_main():
        nonlocal current, prev_entry
        flush_aux()
        if current is not None:
            current['name'] = _clean(current['name'])
            current['cause'] = _clean(current['cause'])
            current['remediu'] = _clean(current['remediu'])
            entries.append(current)
            prev_entry = current
        current = None

    for y, row in body:
        code_toks, name_toks, cause_toks, todo_toks = _split_row(row, cols)

        # Discard pure running-header/footer rows ("Fault tracing 553") up front.
        if _is_noise_row(code_toks + name_toks + cause_toks + todo_toks):
            continue
        # Discard rows that are only stray bullet glyphs (ABB decoration cells).
        if _is_bullet_only_row(code_toks + name_toks + cause_toks + todo_toks):
            continue
        name_join = ' '.join(name_toks).strip()

        # ---- Is this row a new MAIN code? ----
        # A main code is a single 4-hex token sitting in the code column.
        is_main = (
            len(code_toks) == 1
            and MAIN_CODE_RE.match(code_toks[0])
        )

        if is_main:
            flush_main()
            own_todo = ' '.join(todo_toks)
            current = {
                'code': code_toks[0].upper(),
                'name': name_join,
                'cause': ' '.join(cause_toks),
                'remediu': own_todo,
                'aux_codes': [],
                'tip': table_tip,
            }
            aux_block_owns_todo = None
            name_annotation_mode = False
            # If the code's own row carries what-to-do text, the code has begun
            # its instruction list; otherwise todo text seen next may still be
            # the previous code's wrap.
            current_todo_started = bool(own_todo.strip())
            # A fresh main code: any What-to-do text starts in the main itself.
            last_todo_was_aux = False
            continue

        # ---- Is this row an AUX-code sub-row? ----
        # Aux codes live in the *name* column band, are short hex tokens, and
        # only count when we already have a main code open.
        aux_candidate = (
            current is not None
            and not code_toks                     # nothing in the code column
            and name_toks
            and AUX_CODE_RE.match(name_join)
        )
        if aux_candidate:
            flush_aux()
            aux_todo = ' '.join(todo_toks).strip()
            # Lock the layout decision on the FIRST aux row of this main code.
            if aux_block_owns_todo is None:
                aux_block_owns_todo = _looks_like_instruction(aux_todo)
            current_aux = {
                'cod': re.sub(r'\s+', ' ', name_join).strip(),
                'cauza': ' '.join(cause_toks),
                'remediu': aux_todo if aux_block_owns_todo else '',
            }
            # In main-owns layout, todo text sharing this aux row's y is really
            # the main's wrapped instruction -> give it back to the main.
            if not aux_block_owns_todo and aux_todo:
                current['remediu'] += ' ' + aux_todo
            # Track where What-to-do text is now flowing: into the aux sub-row
            # itself (layout (a)) or back into the main code (layout (b)).
            last_todo_was_aux = aux_block_owns_todo
            continue

        # ---- Otherwise: a continuation row -> append to the open record. ----
        if current is None:
            # Stray row before any main code (e.g. aux continuation that spilled
            # from the previous page with no main on this page). Skip.
            continue

        # Cause / name continuation goes to the aux if one is open (the main's
        # cause is finished before aux rows start), else to the main.
        if current_aux is not None:
            if name_toks:
                # Aux name col sometimes carries cause text that wrapped left.
                current_aux['cauza'] += ' ' + ' '.join(name_toks)
            if cause_toks:
                current_aux['cauza'] += ' ' + ' '.join(cause_toks)
        else:
            if name_toks:
                name_cont = ' '.join(name_toks)
                # A "Programmable warning: ..." annotation or "(Editable message
                # text)" tag in the name column is metadata, not the name. Once
                # it starts it spans several interleaved name-column rows; a
                # sticky flag makes the parser drop all of them (see the
                # _NAME_ANNOTATION_RE comment for why dropping beats merging).
                if _NAME_ANNOTATION_RE.match(name_cont.strip()):
                    name_annotation_mode = True
                if not name_annotation_mode:
                    current['name'] += ' ' + name_cont
            if cause_toks:
                current['cause'] += ' ' + ' '.join(cause_toks)

        # ---- What-to-do continuation routing. ----
        if todo_toks:
            todo_text = ' '.join(todo_toks)
            if current_aux is not None and aux_block_owns_todo:
                # Aux owns its what-to-do (layout (a)).
                current_aux['remediu'] += ' ' + todo_text
                last_todo_was_aux = True
            elif (not current_todo_started and current_aux is None
                  and prev_entry is not None
                  and not _looks_like_instruction(todo_text)):
                # `current` has not begun its own what-to-do and this fragment
                # is mid-sentence -> it is the PREVIOUS code's what-to-do that
                # wrapped past `current`'s row. Route it back to prev_entry.
                prev_entry['remediu'] = (prev_entry['remediu'] + ' '
                                         + todo_text).strip()
            else:
                # Belongs to the current code (or its aux). The first such row
                # marks the start of the current code's instruction list.
                if current_aux is None:
                    current_todo_started = True
                current['remediu'] += ' ' + todo_text
                last_todo_was_aux = False

    flush_main()
    # `last_todo_was_aux` now reflects the LAST main code of the page: True if
    # its "What to do" text was last flowing into an aux sub-row. The caller
    # uses this to route a page-leading What-to-do continuation (a cell that
    # wrapped past the bottom of this page) back to the right record.
    return entries, cols, last_todo_was_aux


def _table_type_for_page(page, prev_type):
    """Inspect a page's section headings to see which table we are entering.

    Returns 'warning', 'fault', or None (mixed/unknown -> classify by code).
    Carries `prev_type` forward when the page has no new section heading.
    """
    rows = _group_rows(page.get_text("words"))
    # The section heading is a large-ish standalone line near the top.
    head_text = ' '.join(
        t for _, row in rows[:6] for _, _, t in row
    ).lower()
    if 'warning messages' in head_text:
        return 'warning'
    if 'fault messages' in head_text:
        return 'fault'
    # ACS580 'Pure events' is only a paragraph; events live in the warning table.
    # ACS880 single combined table -> stays mixed.
    if 'warning, fault and pure event' in head_text:
        return None
    if 'line-side converter warnings' in head_text:
        return 'warning'
    if 'line-side converter faults' in head_text:
        return 'fault'
    return prev_type


def parse_manual(familie):
    """Parse one manual's Fault tracing chapter. Returns list of fault dicts."""
    cfg = MANUALS[familie]
    pdf_path = MANUALS_DIR / cfg['pdf']
    if not pdf_path.exists():
        sys.stderr.write(f"ERROR: PDF not found: {pdf_path}\n")
        return []

    doc = fitz.open(pdf_path)
    results = []          # final fault dicts
    by_code = {}          # code -> result dict (first occurrence wins / merge)
    table_type = None     # current table identity
    cols_hint = None      # last detected column layout, reused on header-less pages
    pending = None        # main record whose aux list / What-to-do may continue
    pending_todo_was_aux = False  # did `pending`'s What-to-do end on an aux row?

    try:
        for pno in cfg['pages']:
            if pno >= doc.page_count:
                break
            page = doc.load_page(pno)
            rows = _group_rows(page.get_text("words"))
            cols = _detect_columns(rows)

            # Update which table we are inside (heading sticks until changed).
            table_type = _table_type_for_page(page, table_type)

            if cols is None:
                # Not a table page (intro/prose) -> nothing to extract.
                pending = None
                pending_todo_was_aux = False
                continue
            cols_hint = cols

            entries, cols, todo_was_aux = _parse_page(page, cols, table_type)

            # --- Attach page-leading continuation to the pending main record. ---
            # The top of this page may carry (1) the tail of `pending`'s "What
            # to do" cell, which wrapped past the previous page's bottom, and/or
            # (2) aux sub-rows of `pending`. _parse_page drops both when its own
            # `current` is None at page start; recover them here.
            if pending is not None:
                lead_todo, lead_aux = _leading_continuation(
                    page, cols, table_type)
                if lead_todo:
                    # Route the wrapped What-to-do tail back to whichever record
                    # was last receiving `pending`'s What-to-do text: its last
                    # aux sub-row (aux-owns-todo layout) or the main code itself.
                    if pending_todo_was_aux and pending['extra']['aux_codes']:
                        tgt = pending['extra']['aux_codes'][-1]
                        tgt['remediu'] = (tgt['remediu'] + ' '
                                          + lead_todo).strip()
                    else:
                        pending['remediu'] = (pending['remediu'] + ' '
                                              + lead_todo).strip()
                for a in lead_aux:
                    pending['extra']['aux_codes'].append(a)

            for e in entries:
                tip = _classify(e['code'], e['tip'])
                rec = {
                    'producator': 'ABB',
                    'familie': familie,
                    'cod': e['code'],
                    'cod_secundar': None,
                    'tip': tip,
                    'nume': e['name'],
                    'cauza': e['cause'],
                    'remediu': e['remediu'],
                    'reactie': None,
                    'confirmare': None,
                    'extra': {'aux_codes': [
                        {'cod': a['cod'], 'cauza': a['cauza'], 'remediu': a['remediu']}
                        for a in e['aux_codes']
                    ]},
                    'pagina': pno + 1,
                    'sursa': cfg['pdf'],
                }
                if e['code'] in by_code:
                    # Duplicate code (rare; e.g. appears in two sub-tables).
                    # Keep the richer record.
                    old = by_code[e['code']]
                    if _richness(rec) > _richness(old):
                        idx = results.index(old)
                        results[idx] = rec
                        by_code[e['code']] = rec
                else:
                    by_code[e['code']] = rec
                    results.append(rec)

            # The last entry of the page may have aux rows OR a wrapped "What
            # to do" cell continuing overleaf. Remember it and where its
            # What-to-do stream ended so the next page's leading continuation
            # is routed correctly.
            if entries:
                pending = results[-1] if results else None
                pending_todo_was_aux = todo_was_aux
            # If the page produced no entries (e.g. a pure continuation page),
            # keep `pending` pointing at the previous main code so its What-to-do
            # can keep accumulating across several page breaks.
    finally:
        doc.close()

    # Final cleanup pass: trim, strip stray trailing bullet glyphs, drop empty
    # aux entries. `_strip_trailing_bullets` removes the lone bullet/dot glyphs
    # ABB leaves dangling in empty continuation cells (see its docstring).
    for r in results:
        r['nume'] = _clean(r['nume'])
        r['cauza'] = _strip_trailing_bullets(_clean(r['cauza']))
        r['remediu'] = _strip_trailing_bullets(_clean(r['remediu']))
        cleaned_aux = []
        for a in r['extra']['aux_codes']:
            a['cod'] = re.sub(r'\s+', ' ', (a['cod'] or '')).strip()
            a['cauza'] = _strip_trailing_bullets(_clean(a['cauza']))
            a['remediu'] = _strip_trailing_bullets(_clean(a['remediu']))
            if a['cod'] and (a['cauza'] or a['remediu']):
                cleaned_aux.append(a)
        r['extra']['aux_codes'] = cleaned_aux

    return results


def _leading_continuation(page, cols, table_tip):
    """Recover everything at the top of a page that belongs to the PREVIOUS
    page's last main code -- i.e. content that appears *before* this page's
    first main code.

    Two distinct things can spill across the page boundary:

      1. A "What to do" cell that wraps past the bottom of the page. Its tail
         lands as todo-column-only rows at the very top of the next page,
         BEFORE any aux row or main code. The old `_leading_aux` dropped these
         outright -- the truncation bug. They are returned as `lead_todo`.

      2. Aux sub-rows of that main code. These are returned as `aux_list`,
         exactly as before.

    Returns (lead_todo, aux_list): `lead_todo` is the joined continuation text
    of the wrapped What-to-do cell (empty string if none); `aux_list` is the
    list of aux sub-row dicts.

    Layout note: a leading todo-only continuation that occurs while aux rows of
    an aux-OWNS-todo block are still open continues that *aux's* What-to-do, not
    the main's. The caller is told where the main's stream ended (see
    `_parse_page`'s `todo_target_is_aux`) and routes `lead_todo` accordingly --
    but a continuation interleaved INSIDE this page's recovered aux block is
    attached here directly to that aux.
    """
    rows = _group_rows(page.get_text("words"))
    cols = _detect_columns(rows) or cols
    if cols is None:
        return '', []
    body = [(y, r) for y, r in rows if y > cols['header_y_max'] + 1]
    out = []
    cur = None                    # aux sub-record being built
    aux_owns_todo = None          # locked on the first aux row of the block
    lead_todo_parts = []          # tail of the main's wrapped What-to-do cell
    seen_aux = False              # has any aux row appeared yet?

    for y, row in body:
        code_toks, name_toks, cause_toks, todo_toks = _split_row(row, cols)
        all_toks = code_toks + name_toks + cause_toks + todo_toks
        if _is_noise_row(all_toks):
            continue
        # Stray bullet-glyph rows carry no content -- skip them entirely.
        if _is_bullet_only_row(all_toks):
            continue
        # Stop as soon as a main code appears.
        if len(code_toks) == 1 and MAIN_CODE_RE.match(code_toks[0]):
            break
        name_join = ' '.join(name_toks).strip()

        # ---- An aux sub-row. ----
        if not code_toks and name_toks and AUX_CODE_RE.match(name_join):
            seen_aux = True
            if cur is not None:
                cur['cauza'] = _clean(cur['cauza'])
                cur['remediu'] = _clean(cur['remediu'])
                if cur['cod']:
                    out.append(cur)
            aux_todo = ' '.join(todo_toks).strip()
            if aux_owns_todo is None:
                aux_owns_todo = _looks_like_instruction(aux_todo)
            cur = {'cod': re.sub(r'\s+', ' ', name_join).strip(),
                   'cauza': ' '.join(cause_toks),
                   'remediu': aux_todo if aux_owns_todo else ''}
            continue

        # ---- A continuation row (no code, not an aux header). ----
        if cur is not None:
            # Inside this page's recovered aux block -> append to that aux.
            if name_toks:
                cur['cauza'] += ' ' + ' '.join(name_toks)
            if cause_toks:
                cur['cauza'] += ' ' + ' '.join(cause_toks)
            # Wrapped what-to-do belongs to the aux only if the block owns its
            # todo; otherwise it is the main's wrap -- but the main was emitted
            # on the previous page, so route it to the leading-todo bucket.
            if todo_toks:
                if aux_owns_todo:
                    cur['remediu'] += ' ' + ' '.join(todo_toks)
                else:
                    lead_todo_parts.append(' '.join(todo_toks))
        elif not seen_aux and todo_toks and not (code_toks or name_toks
                                                 or cause_toks):
            # A todo-column-only row before any aux row: this is the tail of the
            # previous page's last main code's "What to do" cell, which wrapped
            # past the page bottom. THIS is what the old parser dropped.
            lead_todo_parts.append(' '.join(todo_toks))
        else:
            # Cause/name continuation of the previous page's main code with no
            # aux open. Rare; the main's cause is normally complete before the
            # page break. Ignore (we only recover the What-to-do tail + aux).
            continue

    if cur is not None and cur['cod']:
        cur['cauza'] = _clean(cur['cauza'])
        cur['remediu'] = _clean(cur['remediu'])
        out.append(cur)

    return _clean(' '.join(lead_todo_parts)), out


def _richness(rec):
    """Heuristic score: prefer the record with more text + more aux codes."""
    return (len(rec.get('cauza') or '') + len(rec.get('remediu') or '')
            + 50 * len(rec['extra']['aux_codes']))


def main():
    targets = sys.argv[1:] or list(MANUALS.keys())
    summary = []
    for familie in targets:
        if familie not in MANUALS:
            sys.stderr.write(f"Unknown familie: {familie}\n")
            continue
        sys.stderr.write(f"[{familie}] parsing {MANUALS[familie]['pdf']} ...\n")
        records = parse_manual(familie)
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = OUT_DIR / f'fault_codes_{familie}.json'
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        n_aux = sum(len(r['extra']['aux_codes']) for r in records)
        warn = sum(1 for r in records if r['tip'] == 'warning')
        flt = sum(1 for r in records if r['tip'] == 'fault')
        evt = sum(1 for r in records if r['tip'] == 'event')
        sys.stderr.write(
            f"[{familie}] {len(records)} main entries "
            f"(warning={warn}, fault={flt}, event={evt}), "
            f"{n_aux} aux codes -> {out_path}\n"
        )
        summary.append({
            'familie': familie, 'entries': len(records),
            'warning': warn, 'fault': flt, 'event': evt,
            'aux_codes': n_aux, 'output': str(out_path),
        })
    print(json.dumps({'summary': summary}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
