#!/bin/bash

mkdir -p /etc/firefox/policies

cat > /etc/firefox/policies/policies.json <<'EOF'
{
  "policies": {
    "ExtensionSettings": {
      "{d634138d-c276-4fc8-924b-40a0ea21d284}": {
        "installation_mode": "force_installed"
      },
      "*": {
        "installation_mode": "blocked"
      }
    }
  }
}
EOF

chmod 644 /etc/firefox/policies/policies.json
