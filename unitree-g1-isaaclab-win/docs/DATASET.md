# 유니트리 공식 데이터셋 해독 (2026-08-19 실측)

**[unitreerobotics/G1_Dex1_StackRygBlock_Dataset_Sim](https://huggingface.co/datasets/unitreerobotics/G1_Dex1_StackRygBlock_Dataset_Sim)**

`robot_type = "Unitree_G1_Dex1_Sim"` — 즉 **`unitree_sim_isaaclab` 에서 수집된 공식 시뮬 데이터**다.
우리가 띄운 태스크(`Isaac-Stack-RgyBlock-G129-Dex1-Joint`)와 같은 씬이다.

## 규격 (meta/info.json)

| 항목 | 값 |
|---|---|
| 포맷 | LeRobot v3 (parquet + mp4) |
| 에피소드 | 204 |
| 프레임 | 493,366 |
| fps | 30 |
| `action` | float32, **shape 16** |
| `observation.state` | float32, shape 16 |
| 영상 | `cam_left_high`, `cam_left_wrist`, `cam_right_wrist` (480×640×3) |

태스크 문구 (`meta/tasks.parquet`):
> "Place the wooden blocks into the yellow frame, stacking them from bottom to top in the order: red, yellow, green."

## action 16채널 매핑

`action_provider/action_provider_replay.py` 의 `arm_joint_mapping` / `gripper_joint_mapping` 과 같은 순서다.

```
[0:7]   left  arm  qpos  (shoulder_pitch, shoulder_roll, shoulder_yaw, elbow, wrist_roll, wrist_pitch, wrist_yaw)
[7:14]  right arm  qpos  (동일 순서)
[14]    right gripper 명령값
[15]    left  gripper 명령값
```

> 그리퍼 채널 순서가 `[right, left]` 인 근거 — `action_provider_replay.py` 의 `save_date()` 가
> `right_hand_action = hand_action[:1]`, `left_hand_action = hand_action[1:]` 로 저장한다.
> `sim_replay_hf.py` 에 `--swap-grippers` 를 두었으니 반대로 보이면 그 플래그로 확인할 것.

## 그리퍼 값 변환

값은 사실상 **0(닫힘) / 5.4(열림)** 두 상태로만 나온다.
Isaac Lab 관절각으로 바꿀 때는 공식 함수를 그대로 쓴다 — `tools/data_convert.py`:

```python
convert_to_joint_range(v)   # [0, 5.4] -> [0.024, -0.02] rad
#   0.0 (fully closed) -> +0.024
#   5.4 (fully open)   -> -0.020
```

관절은 손마다 2개: `{side}_hand_Joint1_1`, `{side}_hand_Joint2_1` (둘에 같은 값).

## 에피소드 0 파지 구간 (실측)

`scripts/grip_events.py` 로 뽑은 결과. 시뮬 없이 데이터만으로 계산된다.

```
--- right gripper (ch14) ---
  CLOSED  0-  581 (19.37s)
  open  582-  740 ( 5.27s)
  CLOSED741- 1092 (11.70s)   <- 1번째 파지
  open 1093- 1373 ( 9.33s)
  CLOSED1374- 1766 (13.07s)  <- 2번째 파지
  open 1767- 1868 ( 3.37s)
  CLOSED1869- 1989 ( 4.00s)  <- 3번째 파지

--- left gripper (ch15) ---
  CLOSED  0-   47 ( 1.57s)
  open   48-  213 ( 5.50s)
  CLOSED214-  452 ( 7.93s)
  open  453-  528 ( 2.50s)
  CLOSED529- 1989 (48.67s)
```

**오른손이 3회 파지** — 블록 3개(red → yellow → green) 적치와 정확히 일치한다.
열림→닫힘 전이 프레임: 오른손 **741 / 1374 / 1869**, 왼손 214 / 529.

## 왜 그대로 재생하면 블록이 안 집히나

공식 `FileActionProviderReplay.get_action()` 은 액션을 적용하지 않는다. 대신:

```python
env.scene.reset_to(self.sim_state_list[self.action_index], ..., is_relative=True)
env.sim.render()
return None
```

즉 **저장된 시뮬 상태를 프레임마다 복원**하는 방식이고, 그래서 블록 위치가 항상 맞는다.
그 데이터는 유니트리 자체 형식(`episode_XXXX/data.json`, `sim_state.init_state` 포함)을 전제로 한다.

**HuggingFace 의 LeRobot 형식에는 `sim_state` 가 없다.**
그래서 우리는 액션만 오픈루프로 재생할 수밖에 없고, 씬의 블록 초기 위치가
수집 당시와 다르면 손이 허공을 지난다.

실측 증거 — 재생 중 블록 z 는 거의 고정이고, `green_block` 만 frame 1350 에서
0.8191 → 0.8211 로 잠깐 올라갔다 떨어졌다(스침).

## 해결 방향 (다음 세션)

1. `scripts/sim_grasp_probe.py` 로 파지 프레임(741/1374/1869)에서의 손 world 좌표를 뽑는다.
2. 그 좌표에 블록을 배치(`write_root_pose_to_sim`)한 뒤 `sim_replay_hf.py` 재생.
   → 궤적은 공식 것 그대로, 씬만 데이터에 맞추는 방식.
3. 또는 `sim_state` 를 포함한 원본 json 형식 공개본을 찾아 공식 replay 경로를 그대로 사용.
