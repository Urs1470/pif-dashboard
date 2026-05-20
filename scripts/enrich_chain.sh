#!/bin/bash
# Chain pentru enrichment serial — un job la un moment dat
# Rula cu: bash scripts/enrich_chain.sh

LOG="scripts/llm_single.log"
cd ~/Projects/pif-dashboard

echo "=== CHAIN START $(date) ==="

run_field() {
    local FAM=$1
    local FIELD=$2
    echo "[$(date)] START $FAM $FIELD"
    python scripts/llm_batch_enrich.py --familie "$FAM" --field "$FIELD" --force 2>&1 | tee -a "$LOG"
    local EXIT=${PIPESTATUS[0]}
    echo "[$(date)] END $FAM $FIELD (exit=$EXIT)"
    return $EXIT
}

# 1. Danfoss categorie
run_field "Danfoss_VLT_FC302" "categorie"

# 2. Danfoss influenteaza
run_field "Danfoss_VLT_FC302" "influenteaza"

# 3. Lenze i550 categorie
run_field "Lenze_i550" "categorie"

# 4. Lenze i550 influenteaza
run_field "Lenze_i550" "influenteaza"

# 5. Lenze i950 categorie
run_field "Lenze_i950" "categorie"

# 6. Lenze i950 influenteaza
run_field "Lenze_i950" "influenteaza"

echo "=== CHAIN DONE $(date) ==="
