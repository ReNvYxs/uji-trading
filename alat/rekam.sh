#!/usr/bin/env bash
# Commit balik bukti ke repo ini. Repo ini publik dan TIDAK menyimpan kredensial,
# jadi tidak ada langkah sensor rahasia di sini.
set -uo pipefail
LABEL="${1:-hasil}"
[ -d hasil ] || exit 0
git config user.name 'uji-bot'
git config user.email 'uji-bot@users.noreply.github.com'
git add -A hasil
if git diff --cached --quiet; then
  echo "tidak ada perubahan untuk: $LABEL"
  exit 0
fi
git commit -q -m "[hasil] $LABEL ${GITHUB_SHA:-} [skip ci]"
for i in 1 2 3 4 5; do
  if git pull -q --rebase --autostash origin main && git push -q origin HEAD:main; then
    echo "terkirim: $LABEL"
    exit 0
  fi
  sleep 5
done
echo "GAGAL push: $LABEL"
exit 1
