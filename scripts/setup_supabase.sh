#!/usr/bin/env bash
# Provisioning is intentionally opt-in and contains no destructive SQL.
set -euo pipefail

for name in SUPABASE_ACCESS_TOKEN SUPABASE_PROJECT_REF SUPABASE_DB_PASSWORD; do
  [[ -n "${!name:-}" ]] || { echo "missing required environment variable: $name" >&2; exit 2; }
done

npx --yes supabase@latest link --project-ref "$SUPABASE_PROJECT_REF" --password "$SUPABASE_DB_PASSWORD"
npx --yes supabase@latest db push --dry-run
echo "Dry run passed. Apply migrations explicitly with: npx supabase@latest db push"
