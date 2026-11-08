# 모닝 30 — 매일 아침 30초 뉴스 쇼츠 자동 제작

매일 새벽 5시(KST)에 밤사이 주요 뉴스를 모아 **개표방송 스타일 모션그래픽 + 남녀 가상 앵커**가 번갈아 전하는
30초 이내 세로 영상을 만들고 유튜브에 예약 업로드합니다.

```
05:00 KST  GitHub Actions 실행
  ① collect.py      국내 언론 RSS 9곳 수집 → 같은 사건끼리 묶고, 보도 언론사 수로 중요도 산정
  ② write_script.py Claude가 뉴스 3~4개 선정 + 대사/그래픽/밈 스티커 작성 (JSON 스키마 강제)
                    └ 팩트체크: 그래픽 숫자가 원문에 없으면 다시 쓰게 하고, 그래도 없으면 숫자 그래픽 제거
  ③ timeline.py     앵커별 TTS(단어 타이밍) → 자막·장면 길이·립싱크·효과음·BGM 믹스 (30초 넘으면 자동 압축)
  ④ renderer/       HTML 모션그래픽을 헤드리스 크롬으로 프레임 단위 렌더 → ffmpeg (1080×1920, 30fps)
  ⑤ upload.py       유튜브 업로드: 비공개 + 07:00 예약 공개 (2시간 동안 폰으로 확인하고 문제 있으면 삭제 가능)
매주 월 03:00  memes.py update  → Claude 웹검색으로 요즘 한국 밈 조사 → data/memes.json 갱신·커밋
```

## 왜 이렇게 만들었나 (원래 영상이 어색했던 이유와 해결)
| 문제 | 해결 |
|---|---|
| 실사형 AI 아바타(D-ID)의 입·몸 움직임이 어색함 (불쾌한 골짜기) | 웹툰풍 벡터 캐릭터 앵커. 음성 크기로 입을 움직이고, 눈 깜빡임·고개 끄덕임·호흡을 넣음. 캐릭터라서 어색함이 오히려 '캐릭터성'이 됨 |
| 정지 이미지 + 고정 박스 = 슬라이드쇼 느낌 | 모든 요소가 매 프레임 움직임: 대각선 와이프 전환, 단어별 팝업 헤드라인, 숫자 카운트업, VS 대결, 도장 쾅, 순위 막대, 3D 패널, 움직이는 그리드 배경 |
| 41초, 첫 화면이 약함 | 30초 하드캡, 첫 2초에 날짜 슬램 + 오늘의 키워드 3개 티저, 상단 진행바(이야기 몇 개 남았는지) |
| 소리 없이 보는 시청자 | 큰 자막 + 지금 말하는 단어 노란색 하이라이트 |
| 저작권 | BGM·효과음은 코드로 직접 합성, 뉴스는 제목/요약만 사실 근거로 쓰고 문장은 새로 씀, 밈은 '문구'만 사용(이미지 X) |

## 처음 한 번 설정
1. **Anthropic API 키** → 저장소 Settings › Secrets › Actions 에 `ANTHROPIC_API_KEY`
2. **YouTube 업로드 권한**
   - Google Cloud Console에서 프로젝트 생성 → *YouTube Data API v3* 사용 설정 → OAuth 클라이언트(데스크톱 앱) 생성 → `client_secret.json` 다운로드
   - 내 컴퓨터에서 한 번: `pip install -r requirements.txt && python -m pipeline.upload auth client_secret.json`
   - 출력된 값을 `YT_REFRESH_TOKEN`, 클라이언트 ID/시크릿을 `YT_CLIENT_ID`, `YT_CLIENT_SECRET` 로 저장
   - ⚠️ 구글 **API 감사(audit)를 통과하지 않은 프로젝트는 업로드 영상이 강제로 비공개**가 됩니다. 초기엔 비공개 업로드 후 수동 공개하거나, [YouTube API 감사 신청](https://support.google.com/youtube/contact/yt_api_form)을 하세요.
3. Actions 탭 › *Daily morning shorts* › **Run workflow** (upload 체크 해제)로 시험 실행 → Artifacts 에서 mp4 확인

## 로컬에서 돌려보기
```bash
cd shorts
pip install -r requirements.txt
(cd renderer && npm install && npx playwright install chromium)
python -m pipeline.run_daily --episode samples/demo_episode.json --no-upload --out runs/demo   # 샘플 대본으로
python -m pipeline.run_daily --no-upload                                                     # 실제 뉴스로
```

## 바꾸고 싶을 때
- 앵커 이름/목소리: `pipeline/config.py` (`ANCHORS`, `TTS_RATE`) — 무료 Edge TTS 기본, 더 자연스러운 목소리는 `tts.py`에 상용 한국어 TTS(타입캐스트, 수퍼톤, ElevenLabs 등) 추가
- 앵커 생김새: `renderer/anchors.js` (색·헤어 프리셋)
- 그래픽: `renderer/engine.js`, `renderer/style.css` — 카테고리별 색은 `THEMES`
- 대본 톤/뉴스 선정 기준: `data/style_guide.md`
- 밈 사전: `data/memes.json` (주 1회 자동 갱신, 직접 추가/`sensitive: true` 지정 가능)
- 공개 시각: 저장소 Variables 에 `YT_PUBLISH_AT_KST` (빈 값이면 즉시 업로드)

## 운영 시 주의
- 유튜브 정책상 AI 음성/가상 인물 사용은 '변경되거나 합성된 콘텐츠' 표시 대상 → 업로드 시 자동으로 `containsSyntheticMedia=true` 설정, 설명란에 고지
- 사건·사고·사망·재난 뉴스엔 밈을 쓰지 않도록 대본 규칙에 들어가 있음. 그래도 07:00 공개 전 한 번 보는 것을 권장
- GitHub 예약 실행은 수~수십 분 늦어질 수 있음 → 그래서 업로드는 07:00 예약 공개로 맞춤
