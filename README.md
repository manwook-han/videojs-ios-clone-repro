# video.js iOS `<video>` 복제 재현

iOS에서 video.js는 `<video>`를 래퍼 안으로 옮긴 뒤 **복제본으로 바꿔치기**한다. 그래서 원래 `<video>`에 단 이벤트 리스너는 한 번도 불리지 않는다. React처럼 JSX로 `<video>`를 그리고 `onLoadedData` 같은 prop을 단 채 그 요소를 `videojs()`에 넘기면, iPhone에서는 그 핸들러가 죽는다.

이 리포는 앱 없이 video.js 8.24.1과 짧은 mp4만으로 이 동작을 재현한다.

## 원인

video.js 8.24.1 `src/js/tech/html5.js`:

```js
// Check if this browser supports moving the element into the box.
// On the iPhone video will break if you move the element,
// So we have to create a brand new element.
if (!el || !(this.options_.playerElIngest || this.movingMediaElementInDOM)) {
  if (el) {
    const clone = el.cloneNode(true);
    el.parentNode.insertBefore(clone, el);
    Html5.disposeMediaElement(el);
    el = clone;
  }
  // ...
}

Html5.prototype.movingMediaElementInDOM = !browser.IS_IOS;
```

1. `Player.createEl`은 환경과 관계없이 `<video>`를 래퍼 `<div>` 안으로 옮긴다(`prependTo(tag, el)`, 주석 "Breaks iPhone, fixed in HTML5 setup.").
2. iOS(`IS_IOS = IS_IPHONE || IS_IPAD || IS_IPOD`)에서는 Html5 tech가 옮겨진 원본을 `cloneNode(true)`로 복제해 그 자리에 끼우고 원본은 버린다.
3. `cloneNode`는 이벤트 리스너를 복사하지 않는다. React 19는 미디어 이벤트(`loadeddata`, `progress`, `play` 등)를 루트에 위임하지 않고 요소에 직접 달기 때문에(`nonDelegatedEvents`), React prop 핸들러는 버려진 원본에만 남는다.

이 분기는 2012년 video.js 코드에도 있다("In iOS, if you move a video element in the DOM, it breaks video playback."). 메인테이너는 [#7830](https://github.com/videojs/video.js/issues/7830)에서 같은 유형의 리포트를 의도된 동작으로 보고, `data-vjs-player` 래퍼(player-div ingest)나 `<video-js>` 임베드를 쓰고, 초기화 뒤에는 `<video>`를 직접 다루지 말고 플레이어 API를 쓰라고 답했다. 옮기면 깨진다는 판단의 근거로 보이는 것은 2011년 [jQuery #8015](https://bugs.jquery.com/ticket/8015)(iPad·iPhone에서 `<video>`를 `wrap()`하면 검은 상자만 보임)다.

## 실행

```bash
python3 server.py www 8765
```

iOS Safari는 mp4를 byte-range로 요청하므로 `server.py`가 Range(206)를 처리한다. 페이지는 결과를 `POST /log`로 보내고, 서버는 `results/results.jsonl`에 쌓는다.

시뮬레이터 Safari로 케이스를 돌리고 요약과 스크린샷을 남긴다.

```bash
./run.sh <simulator-udid> <label> vjs vjs-noplay vjs-override vjs-ingest nomove noplay move-early move-meta move-playing
```

브라우저로 한 케이스만 볼 때는 `http://localhost:8765/test.html?t=vjs`를 연다.

`www/clip.mp4`는 아래 명령으로 만들었다.

```bash
ffmpeg -f lavfi -i testsrc2=size=640x360:rate=30 -t 12 -c:v libx264 -pix_fmt yuv420p -profile:v baseline -movflags +faststart www/clip.mp4
```

## 케이스

| `t` | 내용 |
| --- | --- |
| `vjs` | 기본 video.js. 원래 `<video>`(React prop 자리), `player.contentEl()`의 video, `player.on`에 같은 이벤트를 달아 비교한다. 재생은 `player.play()`(muted, playsinline) |
| `vjs-noplay` | `vjs`에서 재생만 하지 않는다. `preload="auto"`만으로 `loadeddata`가 오는지 본다 |
| `vjs-override` | `Html5.prototype.movingMediaElementInDOM = true`로 iOS 복제를 끈다 |
| `vjs-ingest` | `<div data-vjs-player>`로 감싸 video.js가 요소를 바꿔치기하지 않게 한다 |
| `nomove` | video.js 없이 `<video>`만. 대조군 |
| `noplay` | video.js 없이, 재생하지 않고 `loadeddata`가 오는지 본다 |
| `move-early` | 넣자마자 래퍼 div 안으로 옮긴다(video.js와 같은 방식) |
| `move-meta` | `loadedmetadata` 뒤 재생 전에 옮기고 재생한다 |
| `move-playing` | 재생 시작 1초 뒤에 옮긴다 |

각 케이스는 6초 뒤 `currentTime`, `readyState`, `paused`, 오류, 디코딩된 프레임 평균 밝기(`frameAvg`, 검으면 0 근처)와 이벤트 수를 기록한다.

## 결과 (2026-10-13)

환경: Xcode 26.6 시뮬레이터의 Safari. iPhone 16 Pro(iOS 18.6), iPhone 17 Pro(iOS 26.5). 대조군은 데스크톱 Chromium. 원본 데이터는 [`results/results.jsonl`](results/results.jsonl), 화면은 [`screenshots/`](screenshots/)에 있다.

두 iOS 버전의 결과는 모든 케이스에서 같았다.

| 케이스 | iOS 18.6 / 26.5 | 데스크톱 Chromium |
| --- | --- | --- |
| `vjs` | `IS_IOS=true`, 실제 재생 요소 ≠ 원본. **원본 이벤트 0건**, 원본은 DOM에서 떨어짐. 실제 요소와 `player.on`은 모든 이벤트를 받고 정상 재생 | 복제 없음(같은 요소). 원본이 이벤트를 받음 |
| `vjs-override` | 같은 요소. 원본이 모든 이벤트를 받고 정상 재생 | - |
| `vjs-ingest` | 같은 요소. 원본이 모든 이벤트를 받고 정상 재생 | - |
| `move-early`·`move-meta`·`move-playing` | 셋 다 정상 재생(시간 흐름, `readyState 4`, 프레임 그려짐) | - |
| `noplay`·`vjs-noplay` | **`readyState 1`에서 멈춤. `loadedmetadata`·`progress`만 오고 `loadeddata`는 오지 않음** | 재생 없이도 `readyState 4`, `loadeddata` 옴 |

### 정리

- **재현됨.** iOS에서는 원래 `<video>`에 단 리스너가 이벤트를 하나도 받지 못한다. 플레이어 이벤트는 `player.on(...)`이나 `player.contentEl()`의 video에 달아야 한다.
- **시뮬레이터에서는 옮겨도 재생이 깨지지 않았다.** 복제를 끈 두 방식(`movingMediaElementInDOM = true`, `data-vjs-player`)도 정상이었다. 다만 시뮬레이터는 실기기와 미디어 처리 경로가 달라서, 이것만으로 지금의 iOS에서 옮겨도 된다고 결론 내릴 수는 없다.
- **iOS는 progressive mp4를 재생 전에 메타데이터까지만 받는다.** "자동재생이 아니면 `loadeddata`가 온 뒤 포스터를 걷는다" 같은 로직은 iOS의 mp4에서는 재생 전에 동작하지 않는다. HLS를 VHS(MSE·ManagedMediaSource)로 재생하면 VHS가 직접 세그먼트를 받으므로 다를 수 있다. 이번에는 확인하지 않았다.

## 한계

- 시뮬레이터 결과다. 실기기, 특히 옮기기 케이스는 다를 수 있다.
- HLS(VHS·ManagedMediaSource 경로)는 다루지 않았다.
- iOS 17, 27 런타임은 돌리지 않았다.

## 라이선스

`www/video.min.js`, `www/video-js.min.css`는 [Video.js](https://github.com/videojs/video.js) 8.24.1 배포본이며 Apache License 2.0을 따른다(파일 머리의 라이선스 주석 참고).
