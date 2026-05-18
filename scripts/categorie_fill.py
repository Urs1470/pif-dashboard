#!/usr/bin/env python3
"""
categorie_fill.py — Rule-based + LLM backup for categorie field.
Covers ~95% params with rules, LLM only for truly ambiguous ones.

Usage:
  python scripts/categorie_fill.py [--llm-backup] [--limit N]
  --llm-backup: also call LLM for params not covered by rules
"""

import argparse, re, sqlite3, sys, time, json, logging, os
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from llm_enrich import anthro_client, CATEGORII, SYSTEM_BASE, FEW_SHOT_EXPL, user_prompt, call_llm

AUTH_FILE = os.path.expanduser("~/.hermes/auth.json")

# ── Rules for categorie ──────────────────────────────────────────────────────
# Format: (regex_pattern, categorie)
# Ordered: most specific first
CATEGORIE_RULES = [
    # 0-group params (Danfoss style: 1-01, 0-01, etc.)
    (re.compile(r'^(0|[1-9])-[0-9]+$'), 'Diagnostic'),

    # Hex addresses (Lenze/Sinamics): 0xNNNN, 0xNNNN:NNN
    (re.compile(r'^0x[0-9A-Fa-f]+'), 'I/O'),

    # Sinamics r/p codes: rNNNN, pNNNN
    (re.compile(r'^[pr][0-9]+$'), 'Motor'),

    # Group 0: Diagnostic
    (re.compile(r'^0[1-5]\.'), 'Diagnostic'),
    # Group 1: mostly I/O
    (re.compile(r'^1[0-6]\.'), 'I/O'),
    # Group 2: Protectii
    (re.compile(r'^21\.'), 'Protectii'),
    # Groups 22-24: Rampe
    (re.compile(r'^2[2-4]\.'), 'Rampe'),
    # Group 25: Diagnostic
    (re.compile(r'^25\.'), 'Diagnostic'),
    # Group 26: I/O
    (re.compile(r'^26\.'), 'I/O'),
    # Group 28: Motor
    (re.compile(r'^28\.'), 'Motor'),
    # Group 30: Limite
    (re.compile(r'^30\.'), 'Limite'),
    # Group 31: Motor
    (re.compile(r'^31\.'), 'Motor'),
    # Group 32: Protectii
    (re.compile(r'^32\.'), 'Protectii'),
    # Group 33: Diagnostic
    (re.compile(r'^33\.'), 'Diagnostic'),
    # Group 34: Protectii
    (re.compile(r'^34\.'), 'Protectii'),
    # Groups 35-36: Motor
    (re.compile(r'^3[56]\.'), 'Motor'),
    # Group 37: I/O
    (re.compile(r'^37\.'), 'I/O'),
    # Groups 40-45: Motor
    (re.compile(r'^4[0-5]\.'), 'Motor'),
    # Group 46: Motor
    (re.compile(r'^46\.'), 'Motor'),
    # Group 47: Protectii
    (re.compile(r'^47\.'), 'Protectii'),
    # Group 49: Motor
    (re.compile(r'^49\.'), 'Motor'),
    # Groups 50-59: Comunicatii
    (re.compile(r'^5[0-9]\.'), 'Comunicatii'),
    # Group 60: Comunicatii
    (re.compile(r'^60\.'), 'Comunicatii'),
    # Group 61: Diagnostic
    (re.compile(r'^61\.'), 'Diagnostic'),
    # Groups 62-69: Motor
    (re.compile(r'^6[2-9]\.'), 'Motor'),
    # Groups 70-89: Motor
    (re.compile(r'^7[0-9]\.'), 'Motor'),
    (re.compile(r'^8[0-9]\.'), 'Motor'),
    # Groups 90-99: Motor
    (re.compile(r'^9[0-9]\.'), 'Motor'),
]


def rule_categorie(code):
    for rx, cat in CATEGORIE_RULES:
        if rx.match(str(code)):
            return cat
    return None  # Not covered by rules


def setup_log(log_file):
    os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
    lg = logging.getLogger("categorie_fill")
    lg.setLevel(logging.DEBUG)
    for h in [logging.FileHandler(log_file, encoding="utf-8"),
               logging.StreamHandler(sys.stdout)]:
        h.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s"))
        lg.addHandler(h)
    return lg


def fill_all_rules(conn, logger):
    """Fill categorie for all params covered by rules. Returns (filled, uncovered)."""
    cur = conn.cursor()
    filled = 0
    uncovered = []

    cur.execute("SELECT id, parametru, categorie FROM parametri_master")
    rows = cur.fetchall()

    for pid, pcode, existing in rows:
        cat = rule_categorie(pcode)
        if cat:
            if existing != cat:
                cur.execute(
                    "UPDATE parametri_master SET categorie = ? WHERE id = ?",
                    (cat, pid)
                )
            filled += 1
        else:
            uncovered.append((pid, pcode))

    conn.commit()
    return filled, uncovered


def fill_llm_backup(conn, logger, limit=None):
    """Call LLM for params not covered by rules."""
    cur = conn.cursor()

    # Get params with no categorie
    cur.execute(
        "SELECT id, parametru, descriere_scurta, descriere, valoare_default_str, "
        "min, max, unitate, familie FROM parametri_master WHERE categorie IS NULL OR categorie = ''"
    )
    rows = cur.fetchall()

    if limit:
        rows = rows[:limit]

    logger.info(f"LLM backup needed for {len(rows)} params")

    client = anthro_client()
    done = 0
    errors = 0

    for i, row in enumerate(rows):
        pid, pcode, desc_sc, desc, default, min_v, max_v, unit, familie = row

        row_dict = {
            'parametru': pcode,
            'descriere_scurta': desc_sc,
            'descriere': desc,
            'valoare_default_str': default,
            'min': min_v,
            'max': max_v,
            'unitate': unit,
            'familie': familie,
        }

        system = SYSTEM_BASE
        user = user_prompt(row_dict, None, 'categorie')

        result, usage, err = call_llm(
            client, system, user, row_dict, 'categorie', logger
        )

        if err:
            errors += 1
            logger.warning(f"  LLM error for {pcode}: {err}")
        else:
            cat = result.get('categorie', '')
            if cat in CATEGORII:
                cur.execute(
                    "UPDATE parametri_master SET categorie = ? WHERE id = ?",
                    (cat, pid)
                )
                conn.commit()
                done += 1
            else:
                errors += 1
                logger.warning(f"  Bad categorie '{cat}' for {pcode}")

        if (i + 1) % 50 == 0:
            logger.info(f"  LLM progress: {i+1}/{len(rows)} done, {errors} errors")

        time.sleep(0.1)

    return done, errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm-backup", action="store_true",
                    help="Also call LLM for params not covered by rules")
    ap.add_argument("--limit", type=int, default=None,
                    help="Limit LLM calls (for testing)")
    ap.add_argument("--log", default="scripts/categorie_fill.log")
    args = ap.parse_args()

    logger = setup_log(args.log)
    logger.info(f"START categorie_fill  llm_backup={args.llm_backup}  limit={args.limit}")

    conn = sqlite3.connect("pif_dashboard.db")

    # Phase 1: fill with rules
    filled, uncovered = fill_all_rules(conn, logger)
    logger.info(f"Rules filled: {filled} params")
    logger.info(f"Uncovered by rules: {len(uncovered)} params")

    # Phase 2: LLM backup
    if args.llm_backup:
        if uncovered:
            rows_to_llm = [(pid, pcode) for pid, pcode in uncovered]
            if args.limit:
                rows_to_llm = rows_to_llm[:args.limit]
            logger.info(f"Starting LLM backup for {len(rows_to_llm)} params...")

            # Run LLM
            done, errors = fill_llm_backup(conn, logger, args.limit)
            logger.info(f"LLM done: {done} written, {errors} errors")

    conn.close()
    logger.info("DONE")


if __name__ == "__main__":
    main()
