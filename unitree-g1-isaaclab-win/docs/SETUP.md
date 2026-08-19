# Windows 우회 설치 절차 (2026-08-19 실측)

> 전제: `PC방_환경_재구축_가이드.md` 의 **경로 B** 로 Isaac Sim 5.1.0 + Python 3.11 (`D:\ic\env`) 가
> 이미 준비돼 있고 `torch 2.7.0+cu128 / cuda True` 가 확인된 상태.

아래는 그 위에 `unitree_sim_isaaclab` 을 얹는 절차다. 각 단계마다 **왜 필요한지**를 같이 적었다.

---

## 1. Git (PortableGit) — 관리자 권한 불필요

```powershell
$ProgressPreference = 'SilentlyContinue'
$rel   = Invoke-RestMethod -Uri 'https://api.github.com/repos/git-for-windows/git/releases/latest' -Headers @{ 'User-Agent' = 'pwsh' }
$asset = $rel.assets | Where-Object { $_.name -like 'PortableGit-*-64-bit.7z.exe' } | Select-Object -First 1
Invoke-WebRequest -Uri $asset.browser_download_url -OutFile 'D:\ic\PortableGit.exe' -UseBasicParsing
Start-Process -FilePath 'D:\ic\PortableGit.exe' -ArgumentList '-o"D:\ic\Git"', '-y' -Wait
& 'D:\ic\Git\bin\git.exe' --version
```

## 2. Isaac Lab 2.3.2

```powershell
$env:PATH = "D:\ic\Git\bin;D:\ic\Git\cmd;$env:PATH"
git clone https://github.com/isaac-sim/IsaacLab.git D:\ic\IsaacLab
git -C D:\ic\IsaacLab checkout v2.3.2

$env:TEMP='D:\ic\tmp'; $env:TMP='D:\ic\tmp'
$env:PIP_CACHE_DIR='D:\ic\pipcache'      # ★ 없으면 torch 3.3GB 재다운로드
$env:CONDA_PREFIX='D:\ic\env'
$env:OMNI_KIT_ACCEPT_EULA='YES'

# flatdict 빌드 실패 우회 (setuptools 81+ 가 pkg_resources 를 제거해서 깨짐)
& 'D:\ic\env\python.exe' -m pip install "setuptools<81" --cache-dir D:\ic\pipcache
& 'D:\ic\env\python.exe' -m pip install flatdict==4.0.1 --no-build-isolation --cache-dir D:\ic\pipcache

Set-Location D:\ic\IsaacLab
& .\isaaclab.bat --install

# 코어가 조용히 빠지는 경우가 있으므로 반드시 확인
& 'D:\ic\env\python.exe' -c "import isaaclab; print('isaaclab OK')"
& 'D:\ic\env\python.exe' -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```
실측 결과: `isaaclab 0.54.2`, `torch 2.7.0+cu128 True`.

## 3. unitree_sim_isaaclab 클론 + 서브모듈

```powershell
$env:PATH = "D:\ic\Git\bin;D:\ic\Git\cmd;D:\ic\Git\mingw64\bin;$env:PATH"
New-Item -ItemType Directory -Force D:\ic\repos | Out-Null
git lfs install
git clone https://github.com/unitreerobotics/unitree_sim_isaaclab.git D:\ic\repos\unitree_sim_isaaclab
cd D:\ic\repos\unitree_sim_isaaclab
git submodule update --init --recursive     # teleimager -- sim_main.py 가 import 함
```

## 4. Python 의존성

```powershell
& 'D:\ic\env\python.exe' -m pip install -r D:\ic\repos\unitree_sim_isaaclab\requirements.txt --cache-dir D:\ic\pipcache
```

> ⚠️ 이 과정에서 `cryptography` 가 44.0.0 → 50.0.0 으로 올라가
> `isaacsim-core 5.1.0.0 requires cryptography==44.0.0` 경고가 뜬다. 실행에는 지장 없었지만,
> 렌더링/보안 관련 이상이 나오면 이 지점을 되돌려 볼 것.

## 5. ★ h5py 다운그레이드 (Windows 필수)

```powershell
& 'D:\ic\env\python.exe' -m pip install "h5py<3.16" --cache-dir D:\ic\pipcache
```

**왜** — h5py 3.16.0 은 Isaac Sim 이 번들한 `hdf5.dll` 과 심볼이 충돌한다.
단독 `import h5py` 는 되는데 **Isaac Sim 앱 안에서만** 다음으로 죽는다:
```
ImportError: DLL load failed while importing _errors
```
공식 이슈: [isaac-sim/IsaacLab#5076](https://github.com/isaac-sim/IsaacLab/issues/5076).
실측 설치 버전: `h5py 3.15.1`.

## 6. ★ 에셋 (1.31GB) — LFS clone 이 안 된다

`fetch_assets.sh` 는 bash 이고, HuggingFace 데이터셋을 `git clone` 하는데
**LFS 포인터조차 내려오지 않았다**(clone 은 성공하는데 `assets.zip` 이 없음).
직접 받아서 Windows 내장 `tar` 로 푼다 (`Expand-Archive` 는 `-Force` 처리에서 깨짐).

```powershell
$ProgressPreference='SilentlyContinue'
Invoke-WebRequest -Uri 'https://huggingface.co/datasets/unitreerobotics/unitree_sim_isaaclab_usds/resolve/main/assets.zip' `
                  -OutFile 'D:\ic\tmp\assets.zip' -UseBasicParsing

New-Item -ItemType Directory -Force 'D:\ic\tmp\assets_unzip' | Out-Null
tar -xf 'D:\ic\tmp\assets.zip' -C 'D:\ic\tmp\assets_unzip'
Move-Item 'D:\ic\tmp\assets_unzip\assets' 'D:\ic\repos\unitree_sim_isaaclab\assets'

# 확인
Test-Path 'D:\ic\repos\unitree_sim_isaaclab\assets\robots\g1-29dof-dex1-base-fix-usd\g1_29dof_with_dex1_base_fix1.usd'
Test-Path 'D:\ic\repos\unitree_sim_isaaclab\assets\objects\PackingTable\PackingTable.usd'
```
실측: 전개 후 1,691.7 MB, G1 USD 7종 + H1-2 1종.

## 7. ★ pink(pinocchio) 회피 패치

`pin` 설치는 Windows 에서 `CMAKE_C_COMPILER not set`, `'nmake' 없음` 으로 실패한다.
17개 태스크 중 **8개만** pink 를 쓰므로 나머지로 진행한다.

문제는 두 군데에서 **모든** 태스크를 강제로 import 한다는 것:
- `tasks/g1_tasks/__init__.py`, `tasks/h1-2_tasks/__init__.py` — 명시적 import
- `tasks/__init__.py` 의 `import_packages` — 하위 패키지 **재귀 스캔**

`patches/` 의 세 파일로 교체한다 (원본은 `*.bak` 로 보관됨).
- 각 `__init__.py`: import 실패 시 건너뛰도록 try/except
- `tasks/__init__.py`: `_BLACKLIST_PKGS` 에 pink 사용 패키지 추가

## 8. ★ DDS(`unitree_sdk2py`) 는 포기한다

`sim_main.py` → `dds.dds_master` → `unitree_sdk2py` → **`cyclonedds` C 라이브러리**.
pip 설치가 `Could not locate cyclonedds. Try to set CYCLONEDDS_HOME` 으로 실패하고,
공식 절차는 CMake 소스 빌드를 요구한다 (Windows 지원 언급 없음).

**판단** — 이 저장소의 DDS 는 *시뮬레이터 ↔ 텔레옵/실기* 통신용이다.
씬 로드·재생이 목적이면 필요 없다. 그래서 `sim_main.py` 를 쓰지 않고
`gym.make()` 로 같은 태스크 환경을 직접 띄운다 (`scripts/sim_*.py`).

다만 `tasks/common_observations/g1_29dof_state.py` 가 **모듈 레벨**에서 DDS 를 import 하므로
`scripts/*.py` 안의 `_install_dds_stub()` 가 import 만 통과시킨다.

> ### ⚠️ 스텁의 함정 — dunder 를 막지 않으면 엉뚱한 데서 터진다
> 처음에 스텁의 `__getattr__` 이 `__file__`, `__spec__` 같은 dunder 에도 클래스를 반환하게 만들었더니
> Isaac Sim 확장 로더가 `TypeError: expected str, bytes or os.PathLike object, not type` 로 깨지고,
> 이어서 **`Only a single TORCH_LIBRARY can be used to register the namespace prims` 가 37건** 터졌다.
> 증상과 원인이 전혀 달랐다. **순수 Isaac Lab 만 따로 띄워 정상 동작을 확인**해 원인을 갈라냈고,
> dunder 는 `AttributeError` 를 내도록 고쳐 해결했다.

## 9. 실행

```powershell
$env:TEMP='D:\ic\tmp'; $env:TMP='D:\ic\tmp'; $env:OMNI_KIT_ACCEPT_EULA='YES'
cd D:\ic\repos\unitree_sim_isaaclab

# GUI
.\run_gui.bat

# 헤드리스 캡처
& 'D:\ic\env\python.exe' -u sim_capture.py --task Isaac-Stack-RgyBlock-G129-Dex1-Joint --headless --enable_cameras --device cuda

# 공식 데이터셋 재생
& 'D:\ic\env\python.exe' -u sim_replay_hf.py --task Isaac-Stack-RgyBlock-G129-Dex1-Joint --episode 0 --enable_cameras --device cuda
```

> **`--enable_cameras` 를 빼면** `RuntimeError: A camera was spawned without the --enable_cameras flag` 로 죽는다.
> 씬 생성 + 시뮬 시작에 **100초 이상** 걸린다(첫 실행은 셰이더·MDL 컴파일로 더). 멈춘 게 아니다.
> `MDLC comp error: C120 could not find module ...` 은 창고 씬 일부 머티리얼 누락 경고로, 렌더는 정상 진행된다.

## 10. 공식 데이터셋 받기

```powershell
New-Item -ItemType Directory -Force 'D:\ic\tmp\ds' | Out-Null
Invoke-WebRequest -Uri 'https://huggingface.co/datasets/unitreerobotics/G1_Dex1_StackRygBlock_Dataset_Sim/resolve/main/data/chunk-000/file-000.parquet' `
                  -OutFile 'D:\ic\tmp\ds\data.parquet' -UseBasicParsing
```

---

## 자주 막히는 지점 요약

| 증상 | 원인 | 해결 |
|---|---|---|
| `ImportError: DLL load failed while importing _errors` (h5py) | Isaac Sim 번들 hdf5.dll 과 충돌 | `pip install "h5py<3.16"` |
| `Only a single TORCH_LIBRARY ... namespace prims` 다수 | DDS 스텁이 dunder 에 클래스 반환 | 스텁 `__getattr__` 이 dunder 에 `AttributeError` |
| `ModuleNotFoundError: No module named 'pink'` | pinocchio Windows 빌드 불가 | `patches/` 적용 (blacklist + try/except) |
| `Could not locate cyclonedds` | C 라이브러리 소스 빌드 필요 | DDS 포기, `gym.make()` 직접 사용 |
| `A camera was spawned without --enable_cameras` | 플래그 누락 | 항상 `--enable_cameras` |
| `assets.zip` 이 안 받아짐 | HF LFS clone 실패 | resolve URL 직접 + `tar -xf` |
| `Expand-Archive` 가 `-Force` 에서 예외 | PowerShell 5.1 아카이브 모듈 | Windows 내장 `tar` 사용 |
