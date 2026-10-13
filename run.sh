#!/usr/bin/env bash
# usage: run.sh <udid> <label> <test...>
# 각 테스트 페이지를 시뮬레이터 Safari로 열고, 결과를 기다려 요약과 스크린샷을 남긴다.
U="$1"; LABEL="$2"; shift 2
DIR="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$DIR/screenshots"
for t in "$@"; do
  id="${LABEL}-${t}"
  xcrun simctl openurl "$U" "http://localhost:8765/test.html?t=${t}&id=${id}"
  curl -s --max-time 70 "http://127.0.0.1:8765/wait?id=${id}" > "$DIR/last.json"
  xcrun simctl io "$U" screenshot "$DIR/screenshots/${id}.png" >/dev/null 2>&1
  python3 -I - "$DIR/last.json" <<'PY'
import json, sys
r = json.load(open(sys.argv[1]))
if r.get("timeout"):
    print(f'{r["id"]}: TIMEOUT'); sys.exit()
c = r.get("counts", {})
fmt = lambda d: ",".join(f"{k}={v}" for k, v in (d or {}).items()) or "(없음)"
st = lambda s: s and f'connected={s["connected"]} t={s["currentTime"]} rs={s["readyState"]} paused={s["paused"]} err={s["error"]} frame={s["frameAvg"]}'
line = [f'{r["id"]}:']
if r["t"].startswith("vjs"):
    line.append(f'IS_IOS={r["IS_IOS"]} moving={r["movingMediaElementInDOM"]} actualIsOrig={r["actualIsOrig"]} videos={r["videoCountInDocument"]}')
    line.append(f'\n    orig   : {st(r["orig"])}\n    actual : {st(r["actual"])}')
    line.append(f'\n    events orig   : {fmt(c.get("orig"))}\n    events actual : {fmt(c.get("actual"))}\n    events player : {fmt(c.get("player.on"))}')
else:
    line.append(f'movedAtReadyState={r.get("movedAtReadyState")} timeAtMove={r.get("timeAtMove")}\n    video : {st(r["video"])}\n    events: {fmt(c.get("video"))}')
if r.get("playError"):
    line.append(f'\n    playError={r["playError"]}')
print(" ".join(line))
PY
done
