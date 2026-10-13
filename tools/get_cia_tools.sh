#!/usr/bin/env bash
# Puts `makerom` and `bannertool` into ./bin (the Makefile adds ./bin to PATH).
# Tries the latest GitHub release first; if that fails, builds from source.
# Used by the GitHub Actions workflow, but works on any Linux box too.
set -uo pipefail
cd "$(dirname "$0")/.."
mkdir -p bin work
AUTH=()
[ -n "${GH_TOKEN:-}" ] && AUTH=(-H "Authorization: Bearer ${GH_TOKEN}")

asset_url() {  # $1 = owner/repo   $2 = regex matched against the asset download URL
  curl -fsSL "${AUTH[@]}" "https://api.github.com/repos/$1/releases/latest" \
    | jq -r --arg re "$2" '[.assets[].browser_download_url | select(test($re))][0] // empty'
}

fetch_zip() {  # $1 = url, $2 = binary name, $3 = path regex for `find`
  local url="$1" name="$2" hint="$3"
  [ -n "$url" ] || return 1
  rm -rf "work/$name" && mkdir -p "work/$name"
  curl -fsSL -o "work/$name.zip" "$url" && unzip -qo "work/$name.zip" -d "work/$name" || return 1
  local f
  f=$(find "work/$name" -type f -name "$name" | grep -E "$hint" | head -n1)
  [ -n "$f" ] || f=$(find "work/$name" -type f -name "$name" | head -n1)
  [ -n "$f" ] || return 1
  cp "$f" "bin/$name" && chmod +x "bin/$name"
}

# ---- makerom -------------------------------------------------------------
if [ ! -x bin/makerom ]; then
  echo "== makerom: trying release download"
  fetch_zip "$(asset_url 3DSGuy/Project_CTR 'ubuntu.*x86_64|linux.*x86_64')" makerom 'ubuntu|linux' \
  || {
    echo "== makerom: building from source"
    rm -rf work/Project_CTR
    git clone --depth 1 https://github.com/3DSGuy/Project_CTR work/Project_CTR \
      && ( cd work/Project_CTR/makerom && (make deps || true) && make -j"$(nproc)" ) \
      && cp work/Project_CTR/makerom/bin/makerom bin/makerom
  }
fi

# ---- bannertool ----------------------------------------------------------
if [ ! -x bin/bannertool ]; then
  echo "== bannertool: trying release download"
  fetch_zip "$(asset_url Steveice10/bannertool 'bannertool.*\.zip')" bannertool 'linux.*x86_64|linux' \
  || {
    echo "== bannertool: building from source"
    rm -rf work/bannertool
    git clone --depth 1 https://github.com/Mtgxyz/bannertool work/bannertool \
      && git clone --depth 1 https://github.com/Steveice10/buildtools work/bannertool/buildtools \
      && make -C work/bannertool -j"$(nproc)" \
      && cp "$(find work/bannertool/output -type f -name bannertool | head -n1)" bin/bannertool
  }
fi

ls -l bin
for t in makerom bannertool; do
  [ -x "bin/$t" ] || { echo "ERROR: could not obtain $t"; exit 1; }
done
echo "makerom + bannertool ready"
