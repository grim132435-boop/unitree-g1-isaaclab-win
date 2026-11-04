# 사진 위 결선 표시 도구 (`annotate.py`)

실제 사진(현장 휴대폰 사진, 제조사 데이터시트 사진, CAD 렌더 캡처)에
동그라미, 화살표, 번호, 배선 경로를 직접 그려 넣는 도구입니다.
위치를 글로 설명하는 대신, 결선할 지점을 사진 위에 바로 표시합니다.

필요한 것: Python 3 + Pillow (`pip install pillow`). 한글 폰트는 자동으로 찾습니다
(Windows는 맑은 고딕). 다른 폰트를 쓰려면 `ANNOTATE_FONT` 환경변수에 경로를 넣으세요.

## Claude와 함께 쓰는 순서

1. 사용자: 사진을 채팅에 첨부하고 "X1-3에 어디 꽂는지 표시해줘"처럼 요청
2. Claude: `grid` 명령으로 좌표 격자를 겹친 사진을 만들어 직접 보고, 포트/나사 위치를 픽셀 좌표로 읽음
3. Claude: 좌표를 JSON 스펙에 적고 `render` → 결과 PNG를 확인한 뒤 사용자에게 보냄
4. 사용자: 틀린 위치가 있으면 "2번이 한 칸 오른쪽이야"라고 말하면 스펙만 고쳐 다시 그림

```bash
python tools/visual/annotate.py grid  photo.jpg photo_grid.png --step 100
python tools/visual/annotate.py render spec.json out.png
```

## 표시 종류

| type | 용도 | 주요 키 |
|---|---|---|
| `circle` | 포트, 나사, 소켓에 동그라미 | `at`, `r`(또는 `rx`,`ry`), `label`, `label_pos` |
| `box` | 부품/영역 묶음 | `xy`=[x1,y1,x2,y2], `label` |
| `arrow` | 가리키기 | `from`, `to`, `label` |
| `marker` | 작업 순서 번호 ①②③ | `at`, `n`, `label` |
| `wire` | 배선 경로(꺾은선) | `points`, `color`, `label`(전선색/굵기), `arrow` |
| `text` | 자유 메모 | `at`, `text` |

모든 표시는 `color`, `width`를 받습니다. 어두운 배경과 밝은 배경 모두에서 보이도록
흰 테두리를 자동으로 넣습니다.

전체 옵션:
- `enhance: true`: 흐리거나 어두운 휴대폰 사진을 자동 대비와 샤픈으로 보정합니다.
- `max_width`: 큰 사진을 줄입니다. 좌표는 원본 기준 그대로 둡니다.
- `units: "frac"`: 좌표를 0~1 비율로 받습니다.
- `title`, `legend`: 상단 제목과 하단 범례(전선 색 설명)를 넣습니다.

## 여러 부품 사진을 한 장에 놓고 결선 (결선 시트)

`image` 대신 `canvas`와 `place`를 쓰면, 흰 바탕에 부품 사진 여러 장(PLC, 단자대,
솔레노이드 밸브, 센서 등)을 배치하고 그 사이를 `wire`로 잇는 결선 시트가 됩니다.
좌표는 캔버스 기준입니다.

```json
{
  "canvas": {"w": 1800, "h": 1000},
  "place": [
    {"image": "plc.jpg",   "x": 40,  "y": 80, "w": 700, "title": "PLC 입력부"},
    {"image": "valve.jpg", "x": 1000,"y": 80, "w": 700, "title": "5/2 솔레노이드 밸브"}
  ],
  "marks": [
    {"type": "wire", "points": [[600,400],[850,400],[850,300],[1100,300]],
     "color": "#8B4513", "label": "BN 0.5sq  Y1+"}
  ]
}
```

이렇게 만든 PNG는 PPT/PDF에 그대로 넣을 수 있습니다(`python-pptx`, `reportlab`).
