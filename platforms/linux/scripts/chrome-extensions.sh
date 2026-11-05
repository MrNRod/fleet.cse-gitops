#!/bin/bash

mkdir -p /etc/opt/chrome/policies/managed

cat > /etc/opt/chrome/policies/managed/fleet-extensions.json <<'EOF'
{
  "ExtensionInstallBlocklist": [
    "*"
  ],
  "ExtensionInstallAllowlist": ["glnpjglilkicbckjpbgcfkogebgllemb"],
  "ExtensionInstallForcelist": [
    "aeblfdkhhhdcdjpifhhbdiojplfjncoa;https://clients2.google.com/service/update2/crx",
    "fcoeoabgfenejglbffodgkkbkcdhcgfn;https://clients2.google.com/service/update2/crx",

  ]
}
EOF

chmod 644 /etc/opt/chrome/policies/managed/fleet-extensions.json
