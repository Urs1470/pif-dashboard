#!/usr/bin/env python3
"""
llm_enrich.py — Complete LLM rewrite for parametri_master LLM-only fields:
  - explicatie (RO text, 2-3 propozitii, fara diacritice)
  - influenteaza (lista coduri separate prin virgula)
  - categorie (fixed list)

Verifica TOTI parametrii (nu doar gaps), cu decision: keep|rewrite|new.

Output format: 3-line prefix (nu JSON) — MiniMax nu e reliable cu JSON.

Usage:
  python scripts/llm_enrich.py --familie ACS580 --field explicatie --limit 20 --dry-run
  python scripts/llm_enrich.py --familie ALL --field categorie --limit 5000
"""

import argparse, json, logging, os, re, sqlite3, sys, time
from datetime import datetime

AUTH_FILE = os.path.expanduser("~/.hermes/auth.json")
CATEGORII = ["Motor", "Limite", "Rampe", "I/O", "Comunicatii", "Protectii", "Diagnostic", "Altul"]

# System prompt - 3-line output format
SYSTEM_BASE = (
    "You are a VFD parameter analyst.\n"
    "Output EXACTLY 3 lines:\n"
    "EXPLICATIE: <2-3 sentences, Romanian without diacritics, plain text, no HTML>\n"
    "INFLUENTEAZA: <comma-separated param codes, or empty>\n"
    "CATEGORIE: <Motor|Limite|Rampe|IO|Comunicatii|Protectii|Diagnostic|Altul>\n\n"
    "Example:\n"
    "EXPLICATIE: Defineste viteza minima a motorului. Seteaza negativ pentru directie inversa. Vezi 30.12.\n"
    "INFLUENTEAZA: 30.12, 22.01\n"
    "CATEGORIE: Limite\n\n"
    "IMPORTANT: Output only the 3 lines. Do not truncate."
)

FEW_SHOT_EXPL = (
    "\n\nExplicate (RO fara diacritice, 2-3 propozitii):\n"
    '- "Defineste viteza minima a motorului. Setare critica daca aplicatia cere reverse — pune negativ. Vezi 30.12 pentru limita superioara."\n'
    '- "Selecteaza sursa referintei de viteza. AI1 = potentiometru 0-10V, AI2 = traductor 4-20mA. Vezi si 22.01 pentru scalare."\n'
    '- "Seteaza curentul nominal motor in amperi. Trebuie setat corect pentru protectie termica si calcul cuplu."\n'
    '- "Activeaza functia PID pentru control proces. Feedback de la senzorul de presiune prin AI2."\n\n'
    "Explicatiile EXISTENTE sunt in format HTML cu emoji. ACESTEA SUNT GRESITE — trebuie rescrise ca text simplu RO fara HTML."
)


def get_token():
    with open(AUTH_FILE) as f:
        return json.load(f)["providers"]["minimax-oauth"]["access_token"]


def anthro_client():
    import anthropic
    return anthropic.Anthropic(
        api_key=get_token(),
        base_url="https://api.minimax.io/anthropic"
    )


def producator(familie):
    if familie.startswith("ACS"): return "ABB"
    if familie.startswith("SINAMICS"): return "Siemens"
    if "Lenze" in familie: return "Lenze"
    if "Danfoss" in familie or "FC302" in familie: return "Danfoss"
    return familie.split("_")[0]


def setup_log(log_file):
    os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
    lg = logging.getLogger("llm_enrich")
    lg.setLevel(logging.DEBUG)
    for h in [logging.FileHandler(log_file, encoding="utf-8"),
               logging.StreamHandler(sys.stdout)]:
        h.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s"))
        lg.addHandler(h)
    return lg


def parse_response(text):
    """Parse 3-line prefix format into dict."""
    result = {"explicatie": "", "influenteaza": "", "categorie": ""}
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("EXPLICATIE:"):
            result["explicatie"] = line[12:].strip()
        elif line.startswith("INFLUENTEAZA:"):
            result["influenteaza"] = line[14:].strip()
        elif line.startswith("CATEGORIE:"):
            result["categorie"] = line[11:].strip()
    return result


def quality_check(param_code, existing, field):
    """Return 'keep' if existing value is good, 'rewrite' otherwise."""
    if not existing or len(str(existing).strip()) < 10:
        return "new"
    s = str(existing).strip()
    if field == "explicatie":
        if re.search(r"<[^>]+>", s): return "rewrite"
        if re.search(r"[\U0001F300-\U0001FFFF\u26A0\u2705\u274C]", s): return "rewrite"
        if len(s) > 600: return "rewrite"
        return "keep"
    if field == "categorie":
        return "keep" if s in CATEGORII else "rewrite"
    return "rewrite"


def system_prompt(familie, field):
    base = SYSTEM_BASE
    if field in ("explicatie", "influenteaza"):
        base += FEW_SHOT_EXPL
    return base


def user_prompt(row, existing_val, field):
    parts = [
        f"Parameter: {row['parametru']}",
        f"Short desc: {row['descriere_scurta'] or 'n/a'}",
        f"Desc: {row['descriere'] or 'n/a'}",
    ]
    if row.get("valoare_default_str"):
        parts.append(f"Default: {row['valoare_default_str']}")
    if row.get("min") is not None:
        parts.append(f"Min: {row['min']}")
    if row.get("max") is not None:
        parts.append(f"Max: {row['max']}")
    if row.get("unitate"):
        parts.append(f"Unitate: {row['unitate']}")
    return " | ".join(parts)


CATEGORIE_RULES = [
    (re.compile(r"^0[1-5]\."), "Diagnostic"),
    (re.compile(r"^06\.|^16\."), "I/O"),
    (re.compile(r"^07\.|^08\."), "I/O"),
    (re.compile(r"^09\."), "Comunicatii"),
    (re.compile(r"^1[0-6]\."), "I/O"),
    (re.compile(r"^19\."), "Diagnostic"),
    (re.compile(r"^20\."), "I/O"),
    (re.compile(r"^21\."), "Protectii"),
    (re.compile(r"^22\."), "Rampe"),
    (re.compile(r"^23\."), "Rampe"),
    (re.compile(r"^24\."), "Rampe"),
    (re.compile(r"^25\."), "Diagnostic"),
    (re.compile(r"^26\."), "I/O"),
    (re.compile(r"^28\."), "Motor"),
    (re.compile(r"^30\."), "Limite"),
    (re.compile(r"^31\."), "Motor"),
    (re.compile(r"^32\."), "Protectii"),
    (re.compile(r"^33\."), "Diagnostic"),
    (re.compile(r"^34\."), "Protectii"),
    (re.compile(r"^35\.|^36\."), "Motor"),
    (re.compile(r"^37\."), "I/O"),
    (re.compile(r"^4[0-5]\."), "Motor"),
    (re.compile(r"^46\."), "Motor"),
    (re.compile(r"^47\."), "Protectii"),
    (re.compile(r"^49\."), "Motor"),
    (re.compile(r"^5[0-9]\."), "Comunicatii"),
    (re.compile(r"^60\."), "Comunicatii"),
    (re.compile(r"^61\."), "Diagnostic"),
    (re.compile(r"^6[2-9]\."), "Motor"),
    (re.compile(r"^7[0-9]\."), "Motor"),
    (re.compile(r"^8[0-9]\."), "Motor"),
    (re.compile(r"^9[0-9]\."), "Motor"),
]


def rule_categorie(code):
    for rx, cat in CATEGORIE_RULES:
        if rx.match(code):
            return cat
    return "Altul"


def call_llm(client, system, user, row, field, logger):
    """Call MiniMax, return (result_dict, usage_dict, error_str_or_None)."""
    for attempt in range(3):
        try:
            resp = client.messages.create(
                model="MiniMax-M2.7-highspeed",
                max_tokens=8000,
                system=[{"type": "text", "text": system}],
                messages=[{"role": "user", "content": user}],
            )
            text = "".join(
                b.text for b in resp.content
                if hasattr(b, "text") and b.text
            )
            result = parse_response(text)
            usage = {
                "input_tokens": resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
            }

            # Normalize IO -> I/O before validation
            if result.get("categorie"):
                result["categorie"] = result["categorie"].replace("IO", "I/O")

            # Validate: need both explicatie and categorie
            if not result.get("explicatie") or not result.get("categorie"):
                logger.warning(
                    f"  Incomplete response for {row['parametru']}: "
                    f"exp='{result.get('explicatie', '')[:30]}' "
                    f"cat='{result.get('categorie', '')}', retry {attempt+1}/3"
                )
                time.sleep(1 * (attempt + 1))
                continue

            # Validate categorie
            if result.get("categorie") not in CATEGORII:
                logger.warning(
                    f"  Bad categorie '{result.get('categorie')}' for {row['parametru']}, retry"
                )
                time.sleep(1 * (attempt + 1))
                continue

            return result, usage, None

        except Exception as e:
            logger.error(f"  Error {row['parametru']}: {e}")
            time.sleep(2 * (attempt + 1))

    return {}, {"input_tokens": 0, "output_tokens": 0}, "error"


def get_rows(familie, limit):
    conn = sqlite3.connect("pif_dashboard.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    sql = "SELECT * FROM parametri_master"
    args = []
    if familie != "ALL":
        sql += " WHERE familie = ?"
        args.append(familie)
    sql += " ORDER BY familie, id"
    if limit:
        sql += f" LIMIT {limit}"
    cur.execute(sql, args)
    while True:
        rows = cur.fetchmany(50)
        if not rows:
            break
        for r in rows:
            yield dict(r)
    conn.close()


def write_row(param_id, field, value, logger):
    conn = sqlite3.connect("pif_dashboard.db")
    cur = conn.cursor()
    cur.execute(
        f"UPDATE parametri_master SET {field} = ? WHERE id = ?",
        (value, param_id)
    )
    conn.commit()
    conn.close()


def git_commit(count, famille, field, decisions, cost, logger):
    import subprocess
    k = decisions.get("keep", 0)
    r = decisions.get("rewrite", 0)
    n = decisions.get("new", 0)
    e = decisions.get("error", 0)
    msg = (
        f"LLM enrich: {famille} +{count} params (keep={k} rewrite={r} new={n} error={e}), "
        f"field={field}, cost=${cost:.2f}\n\n"
        f"Co-Authored-By: Hermes <noreply@anthropic.com>"
    )
    try:
        def run(cmd):
            return subprocess.run(cmd, cwd="/home/ion-ursu/Projects/pif-dashboard",
                                 capture_output=True, text=True)
        r2 = run(["git", "status", "--porcelain"])
        if not r2.stdout.strip():
            return
        run(["git", "add", "-A"])
        r3 = run(["git", "commit", "-m", msg])
        if r3.returncode == 0:
            run(["git", "push", "origin", "master"])
            logger.info(f"  Committed + pushed (k={k} r={r} n={n} e={e})")
        else:
            logger.warning(f"  Commit issue: {r3.stderr}")
    except Exception as e:
        logger.error(f"  Git error: {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--familie", default="ALL")
    ap.add_argument("--field", required=True,
                    choices=["explicatie", "influenteaza", "categorie"])
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--batch-size", type=int, default=100)
    ap.add_argument("--log", default="scripts/llm_enrich.log")
    args = ap.parse_args()

    lg = setup_log(args.log)
    lg.info(f"START: {args.familie}/{args.field}  dry={args.dry_run}")

    client = anthro_client()
    total = 0
    cost = 0.0
    batch_rows = []
    batch_results = []
    decisions = {"keep": 0, "rewrite": 0, "new": 0, "error": 0}

    for row in get_rows(args.familie, args.limit):
        pid = row["id"]
        pcode = row["parametru"]
        existing_val = row.get(args.field)
        qc = quality_check(pcode, existing_val, args.field)

        lg.info(
            f"{pid} {pcode} ({row['familie']})  "
            f"existing_len={len(str(existing_val)) if existing_val else 0}  qc={qc}"
        )

        if args.dry_run:
            result_test = {
                "explicatie": "[DRY] " + str(existing_val or "")[:60],
                "influenteaza": "",
                "categorie": "Diagnostic",
            }
            lg.info(f"  DRY: {json.dumps(result_test, ensure_ascii=False)}")
            total += 1
            continue

        if qc == "keep":
            decisions["keep"] += 1
            lg.info(f"  -> keep (existing OK)")
            total += 1
            continue

        system = system_prompt(row["familie"], args.field)
        user = user_prompt(row, existing_val, args.field)
        result, usage, err = call_llm(client, system, user, row, args.field, lg)

        if err:
            decisions["error"] += 1
            total += 1
            continue

        new_val = result.get(args.field, "")
        if qc == "rewrite":
            decisions["rewrite"] += 1
        else:
            decisions["new"] += 1

        write_row(pid, args.field, new_val, lg)
        cost += (usage["input_tokens"] or 0) * 0.000001 + (usage["output_tokens"] or 0) * 0.000003
        batch_rows.append(pid)
        batch_results.append(result)
        total += 1

        lg.info(f"  -> {qc}: {str(new_val)[:80]}")

        if len(batch_rows) >= args.batch_size:
            git_commit(len(batch_rows), args.familie, args.field, decisions, cost, lg)
            batch_rows = []
            batch_results = []

        time.sleep(0.05)

    if batch_rows and not args.dry_run:
        git_commit(len(batch_rows), args.familie, args.field, decisions, cost, lg)

    lg.info(f"DONE: total={total} {decisions} cost=${cost:.4f}")


if __name__ == "__main__":
    main()
