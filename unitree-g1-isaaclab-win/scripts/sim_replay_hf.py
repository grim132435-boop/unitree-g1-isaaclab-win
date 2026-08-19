#!/usr/bin/env python3
"""sim_replay_hf.py -- 유니트리 공식 데이터셋을 이 시뮬에서 재생한다 (DDS 없이).

궤적은 전부 유니트리 공식 자료다. 이 스크립트는 연결만 한다.
  - 데이터: https://huggingface.co/datasets/unitreerobotics/G1_Dex1_StackRygBlock_Dataset_Sim
           (robot_type = Unitree_G1_Dex1_Sim, 즉 unitree_sim_isaaclab 에서 수집됨)
  - 관절 매핑: action_provider/action_provider_replay.py 의
              left_arm_joint / right_arm_joint / gripper_joint_mapping 과 동일
  - 그리퍼 변환: tools/data_convert.py 의 convert_to_joint_range (공식 함수 그대로 import)

액션 규격 (meta/info.json): action float32 shape=16
  [0:7]  left arm   qpos
  [7:14] right arm  qpos
  [14]   right gripper 명령값 (0=닫힘, 5.4=열림)
  [15]   left  gripper 명령값
"""
import os

project_root = os.path.dirname(os.path.abspath(__file__))
os.environ["PROJECT_ROOT"] = project_root

import argparse
import importlib.util
import sys
import types


def _install_dds_stub():
    """unitree_sdk2py(cyclonedds) 는 Windows 에서 빌드되지 않는다. import 만 통과시킨다."""
    if importlib.util.find_spec("unitree_sdk2py") is not None:
        return

    class _Stub:
        def __init__(self, *a, **k):
            pass

        def __call__(self, *a, **k):
            return _Stub()

        def __getattr__(self, name):
            return _Stub()

    def _make_getattr():
        def _getattr(attr):
            if attr.startswith("__") and attr.endswith("__"):
                raise AttributeError(attr)
            return _Stub

        return _getattr

    for name in [
        "unitree_sdk2py",
        "unitree_sdk2py.core",
        "unitree_sdk2py.core.channel",
        "unitree_sdk2py.idl",
        "unitree_sdk2py.idl.default",
        "unitree_sdk2py.idl.std_msgs",
        "unitree_sdk2py.idl.std_msgs.msg",
        "unitree_sdk2py.idl.std_msgs.msg.dds_",
        "unitree_sdk2py.idl.unitree_hg",
        "unitree_sdk2py.idl.unitree_hg.msg",
        "unitree_sdk2py.idl.unitree_hg.msg.dds_",
        "unitree_sdk2py.idl.unitree_go",
        "unitree_sdk2py.idl.unitree_go.msg",
        "unitree_sdk2py.idl.unitree_go.msg.dds_",
        "unitree_sdk2py.utils",
        "unitree_sdk2py.utils.crc",
    ]:
        mod = types.ModuleType(name)
        mod.__path__ = []
        mod.__getattr__ = _make_getattr()
        sys.modules[name] = mod


_install_dds_stub()

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="Replay official Unitree dataset in unitree_sim_isaaclab")
parser.add_argument("--task", type=str, default="Isaac-Stack-RgyBlock-G129-Dex1-Joint")
parser.add_argument("--parquet", type=str, default=r"D:\ic\tmp\ds\data.parquet")
parser.add_argument("--episode", type=int, default=0)
parser.add_argument("--fps", type=float, default=30.0, help="데이터셋 fps (meta/info.json 기준)")
parser.add_argument("--speed", type=float, default=1.0, help="재생 배속")
parser.add_argument("--swap-grippers", action="store_true", help="그리퍼 좌/우 채널을 바꿔서 재생")
parser.add_argument("--loop", action="store_true")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import gymnasium as gym
import numpy as np
import torch

import tasks  # noqa: F401
from isaaclab_tasks.utils.parse_cfg import parse_env_cfg
from tools.data_convert import convert_to_joint_range  # 공식 변환 함수

# action_provider/action_provider_replay.py 와 동일한 순서
LEFT_ARM_JOINTS = [
    "left_shoulder_pitch_joint",
    "left_shoulder_roll_joint",
    "left_shoulder_yaw_joint",
    "left_elbow_joint",
    "left_wrist_roll_joint",
    "left_wrist_pitch_joint",
    "left_wrist_yaw_joint",
]
RIGHT_ARM_JOINTS = [n.replace("left_", "right_") for n in LEFT_ARM_JOINTS]
LEFT_GRIPPER_JOINTS = ["left_hand_Joint1_1", "left_hand_Joint2_1"]
RIGHT_GRIPPER_JOINTS = ["right_hand_Joint1_1", "right_hand_Joint2_1"]


def load_episode(path, episode):
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    table = pq.read_table(path)
    ep = table.filter(pc.equal(table.column("episode_index"), episode))
    if ep.num_rows == 0:
        raise ValueError(f"episode {episode} not found in {path}")
    actions = np.stack(ep.column("action").to_pylist()).astype(np.float32)
    return actions


def main():
    actions_ds = load_episode(args_cli.parquet, args_cli.episode)
    n_frames = len(actions_ds)
    print(f"[replay] episode {args_cli.episode}: {n_frames} frames "
          f"({n_frames / args_cli.fps:.1f}s @ {args_cli.fps}fps)")

    env_cfg = parse_env_cfg(args_cli.task, device=args_cli.device, num_envs=1)
    env_cfg.env_name = args_cli.task
    env = gym.make(args_cli.task, cfg=env_cfg).unwrapped
    env.reset()

    robot = env.scene["robot"]
    name_to_idx = {n: i for i, n in enumerate(robot.joint_names)}
    left_arm_idx = [name_to_idx[n] for n in LEFT_ARM_JOINTS]
    right_arm_idx = [name_to_idx[n] for n in RIGHT_ARM_JOINTS]
    left_grip_idx = [name_to_idx[n] for n in LEFT_GRIPPER_JOINTS]
    right_grip_idx = [name_to_idx[n] for n in RIGHT_GRIPPER_JOINTS]
    print(f"[replay] left arm  -> {left_arm_idx}")
    print(f"[replay] right arm -> {right_arm_idx}")
    print(f"[replay] grippers  -> L{left_grip_idx} R{right_grip_idx}")

    blocks = {k: env.scene[k] for k in ("red_block", "yellow_block", "green_block") if k in env.scene.keys()}
    z0 = {k: v.data.root_pos_w[0, 2].item() for k, v in blocks.items()}
    print(f"[replay] initial block z: { {k: round(v,4) for k,v in z0.items()} }")

    action = torch.zeros(env.action_space.shape, device=env.device)
    dt = env.step_dt if hasattr(env, "step_dt") else 0.01

    def play_once():
        t = 0.0
        last_f = -1
        while simulation_app.is_running():
            f = int(t * args_cli.fps * args_cli.speed)
            if f >= n_frames:
                break
            a = actions_ds[f]

            action[:] = 0.0
            action[0, left_arm_idx] = torch.as_tensor(a[0:7], device=env.device)
            action[0, right_arm_idx] = torch.as_tensor(a[7:14], device=env.device)

            g_right, g_left = a[14], a[15]
            if args_cli.swap_grippers:
                g_right, g_left = g_left, g_right
            for i in left_grip_idx:
                action[0, i] = convert_to_joint_range(float(g_left))
            for i in right_grip_idx:
                action[0, i] = convert_to_joint_range(float(g_right))

            with torch.inference_mode():
                env.step(action)

            if f != last_f and f % 150 == 0:
                zs = {k: round(v.data.root_pos_w[0, 2].item(), 4) for k, v in blocks.items()}
                print(f"[replay] frame {f:5d}/{n_frames}  gripL={g_left:.2f} gripR={g_right:.2f}  block_z={zs}")
            last_f = f
            t += dt

    play_once()
    while args_cli.loop and simulation_app.is_running():
        print("[replay] loop -> reset")
        env.reset()
        play_once()

    print("[replay] done. final block z:")
    for k, v in blocks.items():
        z = v.data.root_pos_w[0, 2].item()
        print(f"    {k:14s} {z:.4f}  (Δ {z - z0[k]:+.4f} m)")

    while simulation_app.is_running():
        with torch.inference_mode():
            env.step(action)
    env.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("[replay] interrupted")
    except Exception:
        import traceback

        traceback.print_exc()
        sys.stdout.flush()
    finally:
        simulation_app.close()
