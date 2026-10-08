#!/usr/bin/env bash
# Spiegelt die in plugins.txt gelisteten Plugins aus Klotzkette/claude-fuer-deutsches-recht.
set -euo pipefail
UPSTREAM="https://github.com/Klotzkette/claude-fuer-deutsches-recht.git"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

git clone -q --depth 1 --filter=blob:none --sparse "$UPSTREAM" "$WORK/upstream"
git -C "$WORK/upstream" sparse-checkout set --no-cone /.claude-plugin/marketplace.json '/LICENSE*' /NOTICE

python3 -I - "$WORK" <<'PY'
import json, sys
work = sys.argv[1]
names = [l.strip() for l in open('plugins.txt') if l.strip() and not l.lstrip().startswith('#')]
m = json.load(open(f'{work}/upstream/.claude-plugin/marketplace.json'))
sel = [p for p in m['plugins'] if p['name'] in names]
missing = sorted(set(names) - {p['name'] for p in sel})
if missing:
    sys.exit(f'Nicht im Upstream gefunden: {missing}')
paths = []
for p in sel:
    src = p['source'].removeprefix('./').rstrip('/')
    paths.append(src)
    p['source'] = './plugins/' + src
m['name'] = 'mehmet-familienrecht'
m['description'] = 'Familienrecht aus Klotzkette/claude-fuer-deutsches-recht, automatisch gespiegelt.'
m['plugins'] = sel
open(f'{work}/paths.txt', 'w').write('\n'.join(paths) + '\n')
with open(f'{work}/marketplace.json', 'w') as f:
    json.dump(m, f, ensure_ascii=False, indent=2)
    f.write('\n')
PY

git -C "$WORK/upstream" sparse-checkout add $(sed 's#.*#/&/#' "$WORK/paths.txt")

rm -rf plugins
mkdir -p plugins .claude-plugin
while read -r p; do
  [ -n "$p" ] || continue
  mkdir -p "plugins/$(dirname "$p")"
  cp -a "$WORK/upstream/$p" "plugins/$p"
done < "$WORK/paths.txt"
cp "$WORK/marketplace.json" .claude-plugin/marketplace.json
cp "$WORK"/upstream/LICENSE* "$WORK"/upstream/NOTICE .

size=$(du -sm --exclude=.git . | cut -f1)
echo "Groesse: ${size} MB, Plugins: $(wc -l < "$WORK/paths.txt")"
if [ "$size" -ge 450 ]; then
  echo "Abbruch: zu nah am claude.ai-Limit von 512 MB" >&2
  exit 1
fi
