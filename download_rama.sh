#!/bin/bash
set -euo pipefail

OUT="data/raw"
mkdir -p "$OUT"

echo "=== Descargando datos historicos RAMA (1986-2026) ==="
echo "Destino: $OUT"
echo "Paralelismo: 4 workers"
echo ""

CODES=()
for y in {1986..1999}; do CODES+=(${y:2:2}); done
for y in {2000..2026}; do CODES+=($(printf "%02d" $((y % 100)))); done

COUNT=0
TOTAL=${#CODES[@]}
OK=0

for code in "${CODES[@]}"; do
    (
        url="https://aire.cdmx.gob.mx/descargas/Opendata/Bases_publicas/RAMA/${code}RAMA.zip"
        out="${OUT}/${code}RAMA.zip"
        http=$(curl -fsSL -o "$out" -w "%{http_code}" \
            -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36" \
            -H "Referer: https://www.aire.cdmx.gob.mx/default.php?opc='aKBh'" \
            --connect-timeout 15 --max-time 120 \
            "$url" 2>/dev/null)
        size=$(wc -c < "$out" 2>/dev/null || echo 0)
        echo "  [${code}] HTTP ${http}  ${size} bytes"
    ) &

    COUNT=$((COUNT + 1))

    if (( COUNT % 4 == 0 )) || (( COUNT == TOTAL )); then
        wait
    fi
done

wait

OK=$(ls -1 "$OUT"/*.zip 2>/dev/null | wc -l | tr -d ' ')
echo ""
echo "=== Completado: ${OK}/${TOTAL} archivos ==="
du -sh "$OUT"