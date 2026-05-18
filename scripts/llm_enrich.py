#!/usr/bin/env python3
"""
llm_enrich.py — Complete LLM rewrite for parametri_master LLM-only fields:
  - explicatie (RO text, 2-3 propozitii, fara diacritice)
  - influenteaza (lista coduri separate prin virgula)
  - categorie (fixed list)

Verifica TOTI parametrii (nu doar gaps), cu decision: keep|rewrite|new.

Usage:
  python scripts/llm_enrich.py --familie ACS580 --field explicatie --limit 20 --dry-run
  python scripts/llm_enrich.py --familie ALL --field categorie --limit 5000
"""

import argparse, json, logging, os, re, sqlite3, sys, time
from datetime import datetime

AUTH_FILE = os.path.expanduser("~/.hermes/auth.json")
CATEGORII = ["Motor", "Limite", "Rampe", "I/O", "Comunicatii", "Protectii", "Diagnostic", "Altul"]

FEW_SHOT = {
  "explicatie": [
    {"in": {"parametru":"30.11","descriere_scurta":"Minimum speed","descriere":"Defines the minimum speed of the motor.","default":"0 rpm","min":-20000,"max":30000,"unitate":"rpm"},
     "out": {"explicatie":"Defineste viteza minima a motorului. Setare critica daca aplicatia cere reverse — pune negativ pentru directie inversa. Vezi 30.12 pentru limita superioara.","decision":"new"}},
    {"in": {"parametru":"22.01","descriere_scurta":"Speed ref1 select","descriere":"Selects the source for speed reference 1.","default":"AI1","min":None,"max":None,"unitate":""},
     "out": {"explicatie":"Selecteaza sursa referintei de viteza 1. AI1 = potentiometru 0-10V, AI2 = traductor 4-20mA, DI = semnal digital. Vezi si 22.11 pentru scarificare.","decision":"new"}},
    {"in": {"parametru":"46.01","descriere_scurta":"Speed scaling","descriere":"Defines the speed that corresponds to the maximum reference value.","default":"1500 rpm","min":0,"max":30000,"unitate":"rpm"},
     "out": {"explicatie":"Seteaza viteza nominala pentru scalare. La referinta 100% = viteza din 46.01. Usor de confundat cu 99.06 dar 46.01 e pentru scalare, nu pentru protectie.","decision":"new"}},
  ],
  "influenteaza": [
    {"in":{"parametru":"30.11","descriere_scurta":"Minimum speed"},
     "out":{"influenteaza":"30.12, 22.01, 06.16","decision":"new"}},
    {"in":{"parametru":"22.01","descriere_scurta":"Speed ref1 select"},
     "out":{"influenteaza":"06.16, 01.61","decision":"new"}},
  ],
  "categorie": [
    {"in":{"parametru":"30.11","descriere_scurta":"Minimum speed"},
     "out":{"categorie":"Limite","decision":"new"}},
    {"in":{"parametru":"06.16","descriere_scurta":"Motor speed"},
     "out":{"categorie":"Diagnostic","decision":"new"}},
    {"in":{"parametru":"22.01","descriere_scurta":"Speed ref1 select"},
     "out":{"categorie":"Rampe","decision":"new"}},
  ]
}

FEW_SHOT_PROMPT = {
  "explicatie": 'Exemple explicatii (RO fara diacritice, 2-3 propozitii, stil inginerescu):\n- "Defineste viteza minima a motorului. Setare critica daca aplicatia cere reverse — pune negativ. Vezi 30.12 pentru limita superioara."\n- "Selecteaza sursa referintei de viteza. AI1 = potentiometru 0-10V, AI2 = traductor 4-20mA. Vezi si 22.11 pentru scalare."\n- "Seteaza curentul nominal motor in amperi. Trebuie setat corect pentru protectie termica si calcul cuplu."\n- "Activeaza functia PID pentru control proces. Feedback de la senzorul de presiune prin AI2. Vezi 40.02."\n- "Definesc timpul de accelerare de la 0 la viteza nominala. Creste daca motorul porneste greu."\n\nExplicatiile EXISTENTE sunt in format HTML cu emoji. ACESTEA SUNT GRESITE — trebuie rescrise ca text simplu RO fara HTML.',
  "influenteaza": 'Exemple influenteaza (coduri separate prin virgula, DOAR numere): "30.11, 30.12, 22.01"\nDaca parametrul nu influenteaza pe nimeni direct, returneaza stringul gol "".',
  "categorie": f'Categorii disponibile (alege UNA): {", ".join(CATEGORII)}\nInferat din grupa parametrului:\n- gr01-05: Diagnostic | gr06-16: I/O | gr19-25: Diagnostic | gr26-37: I/O/Motor\n- gr22-24: Rampe | gr30: Limite | gr31: Motor | gr32-34: Protectii\n- gr40-45: Motor | gr46-49: Motor | gr50-60: Comunicatii/I/O | gr61-69: Diagnostic/Motor\n- gr70-89: Motor | gr90-99: Motor'
}


def get_token():
    with open(AUTH_FILE) as f:
        return json.load(f)["providers"]["minimax-oauth"]["access_token"]


def client():
    import anthropic
    return anthropic.Anthropic(api_key=get_token(), base_url="https://api.minimax.io/anthropic")


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
    for h in [logging.FileHandler(log_file, encoding="utf-8"), logging.StreamHandler(sys.stdout)]:
        h.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s"))
        lg.addHandler(h)
    return lg



def extract_json(resp_or_text):
    if hasattr(resp_or_text, 'content'):
        # It's an Anthropic response - find TextBlock
        text = ""
        for block in resp_or_text.content:
            if hasattr(block, 'text') and block.text:
                text = block.text
                break
    else:
        text = resp_or_text
    """Extract JSON from LLM response. Handles markdown code blocks."""
    import re, json as _json
    # Try JSON in code blocks first
    for pat in [r"```json\s*(.*?)```", r"```\s*(.*?)```"]:
        m = re.search(pat, text, re.DOTALL)
        if m:
            try:
                return _json.loads(m.group(1).strip())
            except: pass
    # Try raw JSON
    try:
        return _json.loads(text.strip())
    except: pass
    # Try finding {...} in text
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return _json.loads(m.group(0))
        except: pass
    return None

def rule_categorie(code):
    for rx, cat in CATEGORIE_RULES:
        if rx.match(code): return cat
    return "Altul"


def quality_check(param_code, existing, field):
    """Return 'keep' if existing value is good, 'rewrite' otherwise."""
    if not existing or len(str(existing).strip()) < 10:
        return "new"

    s = str(existing).strip()

    if field == "explicatie":
        # Bad patterns: HTML tags, emoji, diacritics, too long, too generic
        if re.search(r"<[^>]+>", s): return "rewrite"
        if re.search(r"[\U0001F300-\U0001FFFF\u26A0\u2705\u274C]", s): return "rewrite"
        if len(s) > 600: return "rewrite"
        # Check diacritics (should be removed per Ion convention)
        if re.search(r"[ăâășț]", s): return "rewrite"
        # Placeholder patterns
        if re.search(r"^Parametrul\s+\d+\.\d+\s+-\s*[A-Z]", s): return "rewrite"
        return "keep"

    if field == "influenteaza":
        # Should be comma-separated numeric codes
        if re.match(r"^[\d\.,\s]+$", s): return "keep"
        return "rewrite"

    if field == "categorie":
        if s in CATEGORII: return "keep"
        return "rewrite"

    return "rewrite"


def system_prompt(producator, familie, field):
    cats = ", ".join(CATEGORII)
    base = (f"Esti inginer commissioning convertizoare frecventa. "
            f"Producator: {producator}. Familie: {familie}. "
            "Stil: RO fara diacritice, maxim 2-3 propozitii, ingineresc dar accesibil. "
            "Nu inventa informatii care nu sunt in descrierea PDF. "
            "Raspuns: JSON valid cu toate campurile cerute.")
    if field == "categorie":
        return base + f"\n\nCategorii: {cats}\n{FEW_SHOT_PROMPT['categorie']}"
    return base + f"\n\n{FEW_SHOT_PROMPT[field]}"


def user_prompt(row, existing, field):
    parts = [
        f"Parametru: {row['parametru']}",
        f"Familie: {row['familie']}",
        f"Descriere scurta: {row['descriere_scurta'] or 'n/a'}",
        f"Descriere PDF: {row['descriere'] or 'n/a'}",
    ]
    if row.get("valoare_default_str"):
        parts.append(f"Default: {row['valoare_default_str']}")
    if row.get("min") is not None:
        parts.append(f"Min: {row['min']}")
    if row.get("max") is not None:
        parts.append(f"Max: {row['max']}")
    if row.get("unitate"):
        parts.append(f"Unitate: {row['unitate']}")

    existing_val = existing.get(field) if existing else None
    qc = quality_check(row["parametru"], existing_val, field)

    parts.append(f"\nExplicatie existenta: {existing_val or '(gol)'}")
    parts.append(f"Quality check decision: {qc}")
    parts.append(f"\nCamp cerut: {field}")
    return "\n".join(parts)



def call_llm(cli, system, user, row, field, logger):
    """Call MiniMax, return (result_dict, usage_dict, error_str_or_None)."""
    for attempt in range(3):
        try:
            resp = cli.messages.create(
                model="MiniMax-M2.7-highspeed",
                max_tokens=512,
                system=[{"type": "text", "text": system}],
                messages=[{"role": "user", "content": user}],
            )
            j = extract_json(resp)
            usage = {"input_tokens": resp.usage.input_tokens,
                     "output_tokens": resp.usage.output_tokens}

            if not j:
                logger.warning(f"  No JSON from {row['parametru']}, retry {attempt+1}/3")
                time.sleep(1 * (attempt + 1))
                continue

            if field == "categorie" and j.get("categorie") not in CATEGORII:
                logger.warning(f"  Bad categorie '{j.get('categorie')}' retry {attempt+1}/3")
                time.sleep(1 * (attempt + 1))
                continue

            return j, usage, None

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
        if not rows: break
        for r in rows: yield dict(r)
    conn.close()


def write_row(param_id, field, value, decision, logger):
    conn = sqlite3.connect("pif_dashboard.db")
    cur = conn.cursor()
    cur.execute(f"UPDATE parametri_master SET {field} = ? WHERE id = ?", (value, param_id))
    conn.commit()
    conn.close()


def git_commit(count, famille, field, decisions, cost, logger):
    import subprocess
    k = decisions.get("keep", 0)
    r = decisions.get("rewrite", 0)
    n = decisions.get("new", 0)
    msg = f"LLM enrich: {famille} +{count} params (keep={k} rewrite={r} new={n}), field={field}, cost=${cost:.2f}\n\nCo-Authored-By: Hermes <noreply@anthropic.com>"
    try:
        sub = lambda cmd: subprocess.run(cmd, cwd="/home/ion-ursu/Projects/pif-dashboard",
                                        capture_output=True, text=True)
        sub(["git", "add", "-A"])
        r2 = sub(["git", "commit", "-m", msg])
        if r2.returncode == 0:
            sub(["git", "push", "origin", "master"])
            logger.info(f"  Committed + pushed (keep={k} rew={r} new={n})")
        else:
            logger.warning(f"  Commit issue: {r2.stderr}")
    except Exception as e:
        logger.error(f"  Git error: {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--familie", default="ALL")
    ap.add_argument("--field", required=True, choices=["explicatie", "influenteaza", "categorie"])
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--batch-size", type=int, default=100)
    ap.add_argument("--log", default="scripts/llm_enrich.log")
    args = ap.parse_args()

    lg = setup_log(args.log)
    lg.info(f"START: {args.familie}/{args.field}  dry={args.dry_run}")

    cli = client()
    total = 0
    cost = 0.0
    batch_rows = []
    batch_writes = []
    decisions = {"keep": 0, "rewrite": 0, "new": 0, "error": 0}

    for row in get_rows(args.familie, args.limit):
        pid = row["id"]
        pcode = row["parametru"]
        existing = {
            "explicatie": row.get("explicatie"),
            "influenteaza": row.get("influenteaza"),
            "categorie": row.get("categorie"),
        }
        existing_val = existing.get(args.field)
        qc = quality_check(pcode, existing_val, args.field)

        lg.info(f"{pid} {pcode} ({row['familie']})  existing_len={len(str(existing_val)) if existing_val else 0}  qc={qc}")

        if args.dry_run:
            # Show decision + sample output
            system = system_prompt(producator(row["familie"]), row["familie"], args.field)
            user = user_prompt(row, existing, args.field)
            result, usage, err = call_llm(cli, system, user, row, args.field, lg)
            result["decision"] = qc
            lg.info(f"  DRY: {json.dumps({args.field: result.get(args.field,''), 'decision': qc}, ensure_ascii=False)}")
            total += 1
            continue

        # Decision logic
        if qc == "keep":
            decisions["keep"] += 1
            lg.info(f"  -> keep (existing OK)")
            total += 1
            continue

        # Need to rewrite or new
        system = system_prompt(producator(row["familie"]), row["familie"], args.field)
        user = user_prompt(row, existing, args.field)
        result, usage, err = call_llm(cli, system, user, row, args.field, lg)

        if err:
            decisions["error"] += 1
            total += 1
            continue

        new_val = result.get(args.field, "")
        actual_decision = qc  # already determined

        if actual_decision == "rewrite":
            decisions["rewrite"] += 1
        else:
            decisions["new"] += 1

        write_row(pid, args.field, new_val, actual_decision, lg)
        cost += (usage.input_tokens or 0) * 0.000001 + (usage.output_tokens or 0) * 0.000003
        batch_rows.append(pid)
        batch_writes.append(new_val)
        total += 1

        lg.info(f"  -> {actual_decision}: {str(new_val)[:80]}")

        if len(batch_rows) >= args.batch_size:
            git_commit(len(batch_rows), args.familie, args.field, decisions, cost, lg)
            batch_rows = []
            batch_writes = []

        time.sleep(0.05)  # rate limit

    if batch_rows and not args.dry_run:
        git_commit(len(batch_rows), args.familie, args.field, decisions, cost, lg)

    lg.info(f"DONE: total={total} {decisions} cost=${cost:.4f}")


if __name__ == "__main__":
    main()
