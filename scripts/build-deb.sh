#!/usr/bin/env bash
# Build the edgecall .deb without debhelper. Produces:
#   dist/edgecall_<version>_all.deb
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
VERSION=$(sed -nE '1 s/^[^(]*\(([^)]+)\).*/\1/p' "$ROOT/debian/changelog")
[ -n "$VERSION" ] || { echo "could not parse version from debian/changelog" >&2; exit 1; }

mkdir -p "$ROOT/dist"

PKG="$ROOT/dist/edgecall_${VERSION}_all"
DEB="$ROOT/dist/edgecall_${VERSION}_all.deb"
rm -rf "$PKG" "$DEB"

mkdir -p "$PKG/DEBIAN" \
         "$PKG/usr/bin" \
         "$PKG/usr/lib/edgecall/edgecall" \
         "$PKG/usr/share/edgecall/functions" \
         "$PKG/usr/share/doc/edgecall"

install -m 0755 "$ROOT/bin/edgecall"              "$PKG/usr/bin/edgecall"
install -m 0644 "$ROOT"/lib/edgecall/*.py         "$PKG/usr/lib/edgecall/edgecall/"
install -m 0644 "$ROOT"/functions/*.py            "$PKG/usr/share/edgecall/functions/"
install -m 0644 "$ROOT/functions/motd.txt"        "$PKG/usr/share/edgecall/functions/motd.txt"
install -m 0644 "$ROOT/functions/README.md"       "$PKG/usr/share/edgecall/functions/README.md"
install -m 0644 "$ROOT/README.md"                 "$PKG/usr/share/doc/edgecall/README.md"
install -m 0644 "$ROOT/LICENSE"                   "$PKG/usr/share/doc/edgecall/copyright"
install -m 0755 "$ROOT/debian/postinst"           "$PKG/DEBIAN/postinst"
install -m 0755 "$ROOT/debian/postrm"             "$PKG/DEBIAN/postrm"

# Strip the #DEBHELPER# placeholder lines: we build without debhelper.
sed -i '/#DEBHELPER#/d' "$PKG/DEBIAN/postinst" "$PKG/DEBIAN/postrm"

cat > "$PKG/DEBIAN/control" <<EOF
Package: edgecall
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: all
Depends: python3 (>= 3.10), python3-fastapi, python3-uvicorn, python3-httpx, python3-pydantic
Maintainer: Ramazan Yavuz <yavuzramazan1994@gmail.com>
Homepage: https://github.com/ra-yavuz/edgecall
Description: route plain-language requests to your functions with a weak local model
 edgecall is a small self-hosted, OpenAI-compatible API. You POST a sentence
 and a deliberately weak local model (phi3-class, the kind that runs on a
 Raspberry Pi or a phone) reads a short paginated menu of your registered
 functions, picks one, and edgecall runs it and returns the result.
 .
 The model never sees the whole function list at once: functions are shown a
 few at a time as a numbered menu, paged through with a "next" option. There
 is no embedding model and no index to maintain. edgecall does not host a
 model; it talks to any OpenAI-compatible endpoint you already run. Add a
 function by dropping a Python file into the functions directory.
 .
 DISCLAIMER: provided AS IS, WITHOUT WARRANTY OF ANY KIND. A weak model may
 route a request to the wrong function and edgecall will run it; do not rely
 on it for safety-critical actions. The author is not liable for any damage
 to hardware, data, or system, or for model output or function results. See
 /usr/share/doc/edgecall/README.md for the full disclaimer.
EOF

dpkg-deb --build --root-owner-group "$PKG" "$DEB"
echo "Built: $DEB"
echo
ls -la "$ROOT/dist/"*.deb
