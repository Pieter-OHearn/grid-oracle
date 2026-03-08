#!/usr/bin/env bash
# Apply the main-branch ruleset to Pieter-OHearn/grid-oracle.
#
# Prerequisites:
#   - gh CLI authenticated: gh auth login
#   - Token must have 'repo' scope (classic) or 'administration:write' (fine-grained)
#
# Usage:
#   chmod +x scripts/setup-branch-protection.sh
#   ./scripts/setup-branch-protection.sh

set -euo pipefail

REPO="Pieter-OHearn/grid-oracle"
OWNER="Pieter-OHearn"

echo "Fetching your GitHub user ID..."
ACTOR_ID=$(gh api users/"$OWNER" --jq '.id')
echo "  -> user ID: $ACTOR_ID"

# Delete any existing ruleset named "Protect main" so we can recreate cleanly.
EXISTING_ID=$(gh api repos/"$REPO"/rulesets --jq '.[] | select(.name=="Protect main") | .id' 2>/dev/null || true)
if [ -n "$EXISTING_ID" ]; then
  echo "Deleting existing 'Protect main' ruleset (id=$EXISTING_ID)..."
  gh api -X DELETE repos/"$REPO"/rulesets/"$EXISTING_ID"
fi

echo "Creating 'Protect main' ruleset..."
gh api -X POST repos/"$REPO"/rulesets \
  --input - <<EOF
{
  "name": "Protect main",
  "target": "branch",
  "enforcement": "active",
  "conditions": {
    "ref_name": {
      "include": ["refs/heads/main"],
      "exclude": []
    }
  },
  "bypass_actors": [
    {
      "actor_id": $ACTOR_ID,
      "actor_type": "User",
      "bypass_mode": "always"
    }
  ],
  "rules": [
    {
      "type": "deletion"
    },
    {
      "type": "non_fast_forward"
    },
    {
      "type": "required_linear_history"
    },
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews_on_push": true,
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": false
      }
    },
    {
      "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": true,
        "required_status_checks": [
          { "context": "Ruff lint" },
          { "context": "ESLint + Vite build" }
        ]
      }
    }
  ]
}
EOF

echo ""
echo "Done. Rules applied to 'main' on $REPO:"
echo "  - Deletion blocked"
echo "  - Force-pushes blocked"
echo "  - Linear history required (no merge commits)"
echo "  - Pull request required before merging"
echo "  - CI must pass: 'Ruff lint' and 'ESLint + Vite build'"
echo "  - Bypass actor: $OWNER (can push directly in emergencies)"
