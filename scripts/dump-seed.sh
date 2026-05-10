#!/usr/bin/env bash
# Дамп таблицы problems → dist/problems-YYYY-MM-DD.sql.gz.
# --data-only: схему создаст бот через create_all, чтобы не следить за
# совпадением версий схемы и дампа.
#
# usage: ./scripts/dump-seed.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="${REPO_ROOT}/dist"
CONTAINER="${POSTGRES_CONTAINER:-ege_postgres}"
DB_NAME="${POSTGRES_DB:-ege_helper}"
DB_USER="${POSTGRES_USER:-ege_user}"
DATE_TAG="$(date +%Y-%m-%d)"
OUT="${DIST_DIR}/problems-${DATE_TAG}.sql.gz"
LATEST="${DIST_DIR}/problems.sql.gz"

if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo "❌ контейнер ${CONTAINER} не запущен. Подними postgres: docker compose up -d postgres"
    exit 1
fi

mkdir -p "${DIST_DIR}"

echo "📊 текущее состояние БД:"
docker exec "${CONTAINER}" psql -U "${DB_USER}" -d "${DB_NAME}" -t -A -c "
  SELECT subject || ': ' || count(*)
  FROM problems GROUP BY subject ORDER BY count(*) DESC;
" | sed 's/^/   /'

TOTAL="$(docker exec "${CONTAINER}" psql -U "${DB_USER}" -d "${DB_NAME}" -t -A -c \
  "SELECT count(*) FROM problems;")"
echo "   ─────────"
echo "   всего: ${TOTAL}"

if [[ "${TOTAL}" == "0" ]]; then
    echo "❌ в БД нет задач, дампить нечего"
    exit 1
fi

echo "💾 снимаю дамп → ${OUT}"
docker exec "${CONTAINER}" pg_dump \
    --data-only \
    --table=problems \
    --no-owner \
    --no-privileges \
    -U "${DB_USER}" "${DB_NAME}" \
  | gzip -9 > "${OUT}"

# latest-симлинк — на него смотрит release-seed.sh
ln -sf "$(basename "${OUT}")" "${LATEST}"

SIZE="$(du -h "${OUT}" | cut -f1)"
echo "✅ готово: ${OUT} (${SIZE}, ${TOTAL} задач)"
echo "   симлинк: ${LATEST} → $(basename "${OUT}")"
echo ""
echo "следующий шаг: ./scripts/release-seed.sh seed-${DATE_TAG}"
