#!/bin/bash
set -euo pipefail

# Check for required environment variables
if [[ -z "${SUPABASE_ACCESS_TOKEN:-}" ]]; then
  echo "Error: SUPABASE_ACCESS_TOKEN environment variable is required"
  echo "Get it from: https://supabase.com/dashboard/account/tokens"
  exit 1
fi

if [[ -z "${SUPABASE_PROJECT_REF:-}" ]]; then
  echo "Error: SUPABASE_PROJECT_REF environment variable is required"
  echo "Find it in your Supabase project settings"
  exit 1
fi

if [[ -z "${DEMO_OPERATOR_PASSWORD:-}" ]]; then
  echo "Error: DEMO_OPERATOR_PASSWORD environment variable is required"
  exit 1
fi

if [[ -z "${DEMO_SUPERVISOR_PASSWORD:-}" ]]; then
  echo "Error: DEMO_SUPERVISOR_PASSWORD environment variable is required"
  exit 1
fi

# Supabase CLI commands
SUPABASE="supabase"

# Link to project
echo "Linking to Supabase project $SUPABASE_PROJECT_REF..."
$SUPABASE link --project-ref $SUPABASE_PROJECT_REF

# Push migrations
echo "Pushing migrations..."
$SUPABASE db push

# Create private buckets (no public policies)
echo "Creating private storage buckets..."
for bucket in originals blurred outbox; do
  echo "Creating bucket: $bucket"
  $SUPABASE storage create $bucket --private || echo "Bucket $bucket may already exist"
done

# Create demo users
echo "Creating demo users..."
# Create operator user
OPERATOR_ID=$($SUPABASE auth admin create-user \
  --email operator@sakshi.demo \
  --password "$DEMO_OPERATOR_PASSWORD" \
  --email-confirmed \
  --raw-response | jq -r .id)

# Create supervisor user
SUPERVISOR_ID=$($SUPABASE auth admin create-user \
  --email supervisor@sakshi.demo \
  --password "$DEMO_SUPERVISOR_PASSWORD" \
  --email-confirmed \
  --raw-response | jq -r .id)

# Insert profiles
echo "Inserting profiles..."
$SUPABASE db execute --sql "
INSERT INTO profiles (id, role) VALUES 
  ('$OPERATOR_ID', 'operator'),
  ('$SUPERVISOR_ID', 'supervisor')
ON CONFLICT (id) DO NOTHING;
"

# Load seeds via demo reset endpoint
echo "Loading seeds via demo reset endpoint..."
# Get the Supabase URL
SUPABASE_URL=$($SUPABASE status --field project_url)

# Wait for API to be ready
echo "Waiting for API to be ready..."
sleep 5

# Call demo reset endpoint (requires DEMO_MODE=true to be set in env)
# We'll need to set this via supabase edge functions env or assume it's configured
DEMO_RESET_URL="${SUPABASE_URL}/functions/v1/demo/reset"
echo "Calling demo reset at $DEMO_RESET_URL..."

# Note: The actual demo reset endpoint is in the worker, not as a separate function
# So we need to call the worker's /demo/reset endpoint
WORKER_URL=${WORKER_URL:-"http://localhost:8000"}  # Default to local worker
echo "Calling worker demo reset at $WORKER_URL/demo/reset..."

# Try to call the endpoint, but don't fail if worker isn't running yet
if curl -X POST "$WORKER_URL/demo/reset" -s -o /dev/null -w "%{http_code}" | grep -q "200\|403"; then
  echo "Demo reset endpoint responded (200 OK or 403 if DEMO_MODE=false)"
else
  echo "Warning: Could not reach worker demo reset endpoint. Make sure worker is running."
  echo "You can manually load seeds later with: curl -X POST $WORKER_URL/demo/reset"
fi

echo "Setup complete!"
