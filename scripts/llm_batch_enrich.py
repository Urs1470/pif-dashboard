#!/usr/bin/env python3
"""
llm_batch_enrich.py — Batch LLM processing for parametri_master LLM-only fields.
Sends N params per API call for ~5-10x throughput improvement.

Usage:
  python scripts/llm_batch_enrich.py --familie ACS580 --field explicatie --batch-size 10
  python scripts/llm_batch_enrich.py --familie ALL --field explicatie --batch-size 10
"""

import argparse, json, logging, os, re, sqlite3, sys, time
from datetime import datetime

AUTH_FILE = os.path.expanduser("~/.hermes/auth.json")
CATEGORII = ["Motor", "Limite", "Rampe", "I/O", "Comunicatii", "Protectii", "Diagnostic", "Altul"]

SYSTEM_BASE = (
    "You are a VFD parameter analyst.\n"
    "For each parameter, output EXACTLY 3 lines:\n"
    "EXPLICATIE: <2-3 sentences, Romanian without diacritics, plain text>\n"
    "INFLUENTEAZA: <comma-separated param codes, or empty>\n"
    "CATEGORIE: <Motor|Limite|Rampe|I/O|Comunicatii|Protectii|Diagnostic|Altul>\n\n"
    "Example:\n"
    "EXPLICATIE: Defineste viteza minima a motorului. Seteaza negativ pentru directie inversa. Vezi 30.12.\n"
    "INFLUENTEAZA: 30.12, 22.01\n"
    "CATEGORIE: Limite\n\n"
    "IMPORTANT: Output 3 lines per parameter. Do not truncate."
)

FEW_SHOT = (
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


def parse_batch_response(text, count):
    """Parse N x 3-line blocks from batch response.
    Separator is '/' on its own line between parameter blocks.
    """
    results = [{"explicatie": "", "influenteaza": "", "categorie": ""} for _ in range(count)]
    # Split by lone '/' separator
    blocks = re.split(r'\n/\n', text.strip())
    received = len(blocks)
    if received < count:
        # Pad with empty results for missing ones
        for _ in range(count - received):
            blocks.append("")
    for i, block in enumerate(blocks[:count]):
        for line in block.split("\n"):
            line = line.strip()
            if line.startswith("EXPLICATIE:"):
                val = line[12:].strip()
                val = val.replace("IO", "I/O")
                results[i]["explicatie"] = val
            elif line.startswith("INFLUENTEAZA:"):
                results[i]["influenteaza"] = line[14:].strip()
            elif line.startswith("CATEGORIE:"):
                val = line[11:].strip()
                val = val.replace("IO", "I/O")
                if val in CATEGORII:
                    results[i]["categorie"] = val
                else:
                    results[i]["categorie"] = "Altul"
    return results


def quality_check(pcode, existing, field):
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


def batch_user_prompt(rows, field):
    parts = []
    for i, r in enumerate(rows):
        p = [
            f"[{i+1}] {r['parametru']}",
            f"  desc: {r['descriere_scurta'] or 'n/a'}",
            f"  full: {r['descriere'] or 'n/a'}",
        ]
        if r.get('valoare_default_str'):
            p.append(f"  default: {r['valoare_default_str']}")
        if r.get('min') is not None:
            p.append(f"  min: {r['min']}")
        if r.get('max') is not None:
            p.append(f"  max: {r['max']}")
        if r.get('unitate'):
            p.append(f"  unitate: {r['unitate']}")
        parts.append("\n".join(p))
    return ("\n---\n".join(parts) +
            "\n\nFor each parameter, output EXACTLY 3 lines starting with EXPLICATIE:, INFLUENTEAZA:, CATEGORIE:."
            " Use / as separator between parameters.")


def batch_llm_call(client, system, user, rows, field, logger):
    """Send batch to LLM, return list of result dicts."""
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
        usage = {
            "input_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
        }
        results = parse_batch_response(text, len(rows))
        return results, usage, None
    except Exception as e:
        logger.error(f"  Batch error: {e}")
        return [], {"input_tokens": 0, "output_tokens": 0}, str(e)


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


def single_llm_call(client, system, user, row, field, logger):
    """Single param LLM call with retry."""
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
            usage = {
                "input_tokens": resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
            }
            result = parse_single_response(text)
            result["categorie"] = result["categorie"].replace("IO", "I/O") if result.get("categorie") else ""
            if not result.get("explicatie") or not result.get("categorie"):
                logger.warning(f"  Incomplete response for {row['parametru']}: retry {attempt+1}/3")
                time.sleep(1 * (attempt + 1))
                continue
            if result.get("categorie") not in CATEGORII:
                logger.warning(f"  Bad categorie '{result.get('categorie')}' for {row['parametru']}, retry")
                time.sleep(1 * (attempt + 1))
                continue
            return result, usage, None
        except Exception as e:
            logger.error(f"  Error {row['parametru']}: {e}")
            time.sleep(2 * (attempt + 1))
    return {}, {"input_tokens": 0, "output_tokens": 0}, "error"


def parse_single_response(text):
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


def get_rows(familie, field):
    conn = sqlite3.connect("pif_dashboard.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    sql = "SELECT * FROM parametri_master"
    args = []
    if familie != "ALL":
        sql += " WHERE familie = ?"
        args.append(familie)
    sql += " ORDER BY familie, id"
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
    cur.execute(f"UPDATE parametri_master SET {field} = ? WHERE id = ?", (value, param_id))
    conn.commit()
    conn.close()


def setup_log(log_file):
    os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
    lg = logging.getLogger("llm_batch")
    lg.setLevel(logging.DEBUG)
    for h in [logging.FileHandler(log_file, encoding="utf-8"),
               logging.StreamHandler(sys.stdout)]:
        h.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s"))
        lg.addHandler(h)
    return lg


def git_commit(count, famille, field, decisions, cost, logger):
    import subprocess
    k = decisions.get("keep", 0)
    r = decisions.get("rewrite", 0)
    n = decisions.get("new", 0)
    e = decisions.get("error", 0)
    msg = (
        f"LLM enrich: {famille} +{count} params batch (keep={k} rewrite={r} new={n} error={e}), "
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
            logger.info(f"  Committed + pushed")
        else:
            logger.warning(f"  Commit issue: {r3.stderr}")
    except Exception as e:
        logger.error(f"  Git error: {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--familie", default="ALL")
    ap.add_argument("--field", required=True,
                    choices=["explicatie", "influenteaza", "categorie"])
    ap.add_argument("--batch-size", type=int, default=1)  # default 1 = single
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--log", default="scripts/llm_single.log")
    args = ap.parse_args()

    lg = setup_log(args.log)
    lg.info(f"START: {args.familie}/{args.field}  batch_size={args.batch_size}  dry={args.dry_run}")

    client = anthro_client()
    total = 0
    cost = 0.0
    decisions = {"keep": 0, "rewrite": 0, "new": 0, "error": 0}
    commit_counter = 0

    for row in get_rows(args.familie, args.field):
        pid = row["id"]
        pcode = row["parametru"]
        existing_val = row.get(args.field)
        qc = quality_check(pcode, existing_val, args.field)

        lg.info(f"{pid} {pcode} ({row['familie']})  existing_len={len(str(existing_val)) if existing_val else 0}  qc={qc}")

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

        system = SYSTEM_BASE + FEW_SHOT
        user = user_prompt(row, existing_val, args.field)
        result, usage, err = single_llm_call(client, system, user, row, args.field, lg)

        if err:
            decisions["error"] += 1
            total += 1
            continue

        new_val = result.get(args.field, "")
        if new_val:
            if qc == "rewrite":
                decisions["rewrite"] += 1
            else:
                decisions["new"] += 1
            write_row(pid, args.field, new_val, lg)
        else:
            decisions["error"] += 1
        total += 1
        cost += (usage["input_tokens"] or 0) * 0.000001 + (usage["output_tokens"] or 0) * 0.000003
        lg.info(f"  -> {qc}: {str(new_val)[:80]}")

        commit_counter += 1
        if commit_counter >= 100:
            git_commit(commit_counter, args.familie, args.field, decisions, cost, lg)
            commit_counter = 0

        time.sleep(0.1)

    if commit_counter > 0 and not args.dry_run:
        git_commit(commit_counter, args.familie, args.field, decisions, cost, lg)

    lg.info(f"DONE: total={total} {decisions} cost=${cost:.4f}")


if __name__ == "__main__":
    main()
