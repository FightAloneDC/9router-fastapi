#!/bin/bash
# Test script untuk testing provider satu-satu
# Menggunakan curl yang sudah ada di system

BACKEND_URL="http://localhost:9000"
ADMIN_PASSWORD="123456"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=== 9Router Provider Testing ==="
echo ""

# 1. Login
echo "1. Authenticating..."
TOKEN=$(curl -s -X POST "$BACKEND_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"password\":\"$ADMIN_PASSWORD\"}" | \
  python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null)

if [ -z "$TOKEN" ]; then
  echo -e "   ${RED}✗ Failed to authenticate${NC}"
  exit 1
fi
echo -e "   ${GREEN}✓ Authenticated${NC}"
echo ""

# 2. Get active providers
echo "2. Fetching active providers..."
PROVIDERS=$(curl -s -H "Authorization: Bearer $TOKEN" "$BACKEND_URL/providers")

if [ -z "$PROVIDERS" ]; then
  echo -e "   ${RED}✗ Failed to fetch providers${NC}"
  exit 1
fi

COUNT=$(echo "$PROVIDERS" | python3 -c "import sys,json; print(len([p for p in json.load(sys.stdin) if p['is_active']]))")
echo -e "   ${GREEN}✓ Found $COUNT active providers${NC}"
echo ""

# 3. List providers
echo "3. Active providers:"
echo "$PROVIDERS" | python3 -c "
import sys, json
providers = [p for p in json.load(sys.stdin) if p['is_active']]
for i, p in enumerate(providers, 1):
    print(f\"   {i}. {p['provider']:20} - {p.get('name', 'N/A'):30} (status: {p['test_status']})\")
"

echo ""
echo "============================================================"
echo "Ready to test providers."
echo "Usage: ./test_providers.sh [provider_id] [model_id]"
echo "============================================================"

# If provider_id provided, test it
if [ -n "$1" ]; then
  PROVIDER_ID="$1"
  MODEL_ID="${2:-}"
  
  echo ""
  echo "Testing provider: $PROVIDER_ID"
  
  # Get provider details
  PROVIDER_DATA=$(echo "$PROVIDERS" | python3 -c "
import sys, json
providers = json.load(sys.stdin)
for p in providers:
    if p['provider'] == '$PROVIDER_ID':
        print(json.dumps(p))
        break
")
  
  if [ -z "$PROVIDER_DATA" ]; then
    echo -e "${RED}✗ Provider '$PROVIDER_ID' not found${NC}"
    exit 1
  fi
  
  # Get first model if not specified
  if [ -z "$MODEL_ID" ]; then
    MODEL_ID=$(echo "$PROVIDER_DATA" | python3 -c "
import sys, json
p = json.load(sys.stdin)
if p.get('models') and len(p['models']) > 0:
    print(p['models'][0]['id'])
")
  fi
  
  if [ -z "$MODEL_ID" ]; then
    echo -e "${RED}✗ No models found for provider '$PROVIDER_ID'${NC}"
    exit 1
  fi
  
  echo "Model: $MODEL_ID"
  echo ""
  
  # TODO: Add actual test logic here
  echo -e "${YELLOW}Test logic not implemented yet${NC}"
fi
