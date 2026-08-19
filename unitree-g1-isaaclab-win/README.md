# unitree-g1-isaaclab-win

**유니트리 G1 시뮬레이션(`unitree_sim_isaaclab`)을 Windows 에서 구동한 기록과 스크립트.**

공식 저장소 [unitreerobotics/unitree_sim_isaaclab](https://github.com/unitreerobotics/unitree_sim_isaaclab) 은
Ubuntu 전용(`auto_setup_env.sh`, `sudo apt`, DDS)이라 Windows 에서는 그대로 돌아가지 않는다.
막힌 지점을 하나씩 원인 규명해 우회하고, **유니트리 공식 데이터셋의 시연 궤적을 재생**하는 데까지 갔다.

- 환경: Windows 10 · RTX 5070 12GB · Isaac Sim **5.1.0** · Isaac Lab **2.3.2** · Python **3.11** (`D:\ic\env`)
- 대상 태스크: `Isaac-Stack-RgyBlock-G129-Dex1-Joint` (G1 29DOF + Dex1 그리퍼, 블록 적치)
- 최초 작업일: 2026-08-19

---

## 지금까지 된 것 / 안 된 것

| 상태 | 내용 |
|---|---|
| ✅ | Isaac Lab 2.3.2 설치 (flatdict 이슈 우회), G1 씬 로드, 센서 4종 활성 |
| ✅ | 헤드리스 카메라 캡처 → `captures/*.png` (씬 전경 · 헤드 · 양 손목) |
| ✅ | GUI 창 구동 (`scripts/run_gui.bat`) |
| ✅ | 유니트리 **공식 데이터셋** 다운로드·구조 해독 (LeRobot v3, 204 에피소드) |
| ✅ | 공식 궤적 재생 — 양팔이 움직이고 그리퍼가 여닫힘 |
| ⚠️ | **블록이 집히지 않음** — 오픈루프라 데이터 수집 당시 블록 위치와 현재 씬 위치가 다름 (아래 "다음 할 일") |
| ❌ | `sim_main.py`(공식 진입점) — `unitree_sdk2py`/`cyclonedds` Windows 빌드 불가 |
| ❌ | pink/pinocchio 필요 태스크 8종 — Windows 빌드 불가, 나머지로 진행 |

---

## 다음에 오면 바로 여기부터

### 0) 환경 재구축 (PC방은 매 세션 초기화됨)
`Isaac-simready-validation/docs/PC방_환경_재구축_가이드.md` 의 **경로 B** 를 그대로 따라간다.
그 다음 이 문서의 [SETUP.md](docs/SETUP.md) 로 Windows 우회 절차를 적용한다.

### 1) 막힌 지점 — 블록이 집히지 않는 이유와 해법

공식 `FileActionProviderReplay` 는 액션을 넣는 게 아니라
`env.scene.reset_to(sim_state)` 로 **저장된 시뮬 상태를 복원**한다.
그런데 HuggingFace 의 LeRobot 형식 데이터셋에는 `sim_state` 가 없다.
그래서 우리는 액션만 오픈루프로 재생하는데, **블록 초기 위치가 수집 당시와 달라** 손이 허공을 지난다.
(실측: `green_block` 이 frame 1350 에서 0.8211 로 살짝 들렸다 떨어짐 = 스침)

**해법 (진행하던 것)** — 공식 궤적에서 그리퍼가 닫히는 순간의 손 위치를 뽑아,
그 자리에 블록을 놓고 재생한다. 궤적은 공식 것을 그대로 쓰고 씬만 맞추는 방식.

이미 파악된 파지 시점 (에피소드 0, 30fps):

| 손 | 그리퍼가 닫히는 프레임 | 시각 |
|---|---|---|
| 오른손 | **741**, **1374**, **1869** | 24.7s / 45.8s / 62.3s |
| 왼손 | 214, 529 | 7.1s / 17.6s |

오른손 3회 = 블록 3개(red→yellow→green) 적치와 일치.

바로 실행할 것:
```powershell
$env:TEMP='D:\ic\tmp'; $env:TMP='D:\ic\tmp'; $env:OMNI_KIT_ACCEPT_EULA='YES'
cd D:\ic\repos\unitree_sim_isaaclab
& 'D:\ic\env\python.exe' -u sim_grasp_probe.py --headless --enable_cameras --device cuda
```
→ 위 프레임들에서의 손 world 좌표가 출력된다.
그 좌표로 블록을 배치(`write_root_pose_to_sim`)한 뒤 `sim_replay_hf.py` 를 돌리면 파지가 성립할 것으로 본다.

**대안 경로 (더 정석)**
- 유니트리가 `sim_state` 를 포함한 원본 json(`episode_XXXX/data.json`) 형식 데이터를 공개했는지 다시 찾는다.
  있으면 공식 `--action_source replay` 경로를 그대로 쓸 수 있다 (단 `sim_main.py` 는 DDS 를 요구하므로
  `FileActionProviderReplay` 만 떼어내 호출해야 함).
- `unitree_lerobot` 의 `eval_g1_sim.py` 는 **학습된 정책**을 시뮬에서 돌리는 경로다.
  공식 사전학습 체크포인트가 공개돼 있는지 확인되지 않았다 — 확인 필요.

### 2) 확보해두면 좋은 것
- GUI 에서 `front_cam` 뷰 + Perspective 듀얼 뷰포트 스크린샷
- 재생 영상 녹화 (PT 용)

---

## 폴더 구성

```
scripts/     Windows 우회 실행기 (원본 repo 에 넣어 쓰는 파일들)
patches/     원본 repo 에서 수정한 파일 (파일명은 원경로를 __ 로 이어붙임)
captures/    헤드리스 렌더 결과 PNG
docs/        설치 우회 절차와 실측 기록
```

### scripts

| 파일 | 역할 |
|---|---|
| `sim_view.py` | DDS 없이 씬만 띄우는 최소 뷰어 (zero action) |
| `sim_capture.py` | 헤드리스로 카메라 4종을 PNG 저장 |
| `sim_replay_hf.py` | **유니트리 공식 데이터셋(LeRobot) 궤적 재생** |
| `sim_grasp_probe.py` | 그리퍼가 닫히는 순간의 손 좌표 추출 (다음 단계 핵심) |
| `sim_probe.py` | 씬 키·body 이름·관절·오브젝트 좌표 덤프 |
| `sim_demo.py` | 팔 사인파 모션 (동작 확인용) |
| `sim_pick.py` | Jacobian IK 파지 시도 — **미검증**, 공식 자료 우선 방침에 따라 보류 |
| `inspect_ds.py` | 데이터셋 parquet 구조 확인 (pyarrow only, pandas 불필요) |
| `grip_events.py` | 데이터셋에서 그리퍼 개폐 구간 추출 (시뮬 불필요) |
| `run_gui.bat` | GUI 실행 |

> `scripts/*.py` 는 `D:\ic\repos\unitree_sim_isaaclab\` 에 복사해 놓고 실행한다
> (원본 repo 의 `tasks`, `tools` 를 상대 import 하기 때문).

---

## 참고 링크

- 공식 시뮬: https://github.com/unitreerobotics/unitree_sim_isaaclab
- 공식 데이터셋: https://huggingface.co/datasets/unitreerobotics/G1_Dex1_StackRygBlock_Dataset_Sim
- 공식 LeRobot 연동: https://github.com/unitreerobotics/unitree_lerobot
- h5py DLL 충돌 이슈: https://github.com/isaac-sim/IsaacLab/issues/5076
