#!/usr/bin/env bash
# Публикует dist/problems.sql.gz как GitHub Release через gh CLI.
#
# usage: ./scripts/release-seed.sh seed-2026-05-10 ["заметки в release notes"]

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="${REPO_ROOT}/dist"
DUMP="${DIST_DIR}/problems.sql.gz"

if [[ $# -lt 1 ]]; then
    echo "usage: $0 <tag> [notes]"
    echo "пример: $0 seed-$(date +%Y-%m-%d) 'math complete, russian ~50%'"
    exit 1
fi

TAG="$1"
NOTES="${2:-Seed dump из локальной БД на $(date +%Y-%m-%d).}"

if ! command -v gh >/dev/null 2>&1; then
    echo "❌ gh CLI не найден. Поставь: brew install gh"
    exit 1
fi
if ! gh auth status >/dev/null 2>&1; then
    echo "❌ gh не залогинен. Запусти: gh auth login"
    exit 1
fi
if [[ ! -f "${DUMP}" ]]; then
    echo "❌ ${DUMP} не существует. Сначала: ./scripts/dump-seed.sh"
    exit 1
fi

# вшиваем разбивку по предметам в release notes, чтобы видеть что внутри
# без скачивания дампа
CONTAINER="${POSTGRES_CONTAINER:-ege_postgres}"
DB_NAME="${POSTGRES_DB:-ege_helper}"
DB_USER="${POSTGRES_USER:-ege_user}"
STATS=""
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    STATS="$(docker exec "${CONTAINER}" psql -U "${DB_USER}" -d "${DB_NAME}" -t -A -c "
        SELECT '- **' || subject || '**: ' || count(*)
        FROM problems GROUP BY subject ORDER BY count(*) DESC;
    ")"
fi

SIZE="$(du -h "${DUMP}" | cut -f1)"
BODY=$(cat <<EOF
${NOTES}

## Что внутри

${STATS:-(stats недоступны, postgres не запущена)}

## Как использовать

В \`.env\` пропиши URL (GitHub автоматически редиректит на свежак этого релиза):

\`\`\`env
PARSER_SEED_URL=https://github.com/\${OWNER}/\${REPO}/releases/download/${TAG}/problems.sql.gz
\`\`\`

Или просто:

\`\`\`env
PARSER_SEED_URL=https://github.com/\${OWNER}/\${REPO}/releases/latest/download/problems.sql.gz
\`\`\`

При первом старте \`parser\`-сервис загрузит этот дамп в пустую БД.

---

Размер: ${SIZE}
EOF
)

echo "🚀 создаю релиз ${TAG}…"
gh release create "${TAG}" "${DUMP}" \
    --title "Seed dump · ${TAG}" \
    --notes "${BODY}"

echo "✅ релиз готов:"
gh release view "${TAG}" --json url --jq .url
