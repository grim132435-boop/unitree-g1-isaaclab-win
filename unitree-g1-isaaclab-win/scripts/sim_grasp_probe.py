#!/usr/bin/env python3
"""공식 궤적을 재생하며 '그리퍼가 닫히는 순간'의 손 위치를 뽑는다.

그 위치가 곧 데이터 수집 당시 블록이 놓여 있던 자리다.
(LeRobot 데이터셋에는 sim_state 가 없어 공식 replay 의 reset_to 방식을 쓸 수 없기 때문)
"""
import os

project_root = os.path.dirname(os.path.abspath(__file__))
os.environ["PROJECT_ROOT"] = project_root

import argparse
import importlib.util
import sys
import types


def _install_dds_stub():
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

parser = argparse.ArgumentParser()
parser.add_argument("--task", type=str, default="Isaac-Stack-RgyBlock-G129-Dex1-Joint")
parser.add_argument("--parquet", type=str, default=r"D:\ic\tmp\ds\data.parquet")
parser.add_argument("--episode", type=int, default=0)
parser.add_argument("--fps", type=float, default=30.0)
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import numpy as np
import gymnasium as gym
import torch

import tasks  # noqa: F401
from isaaclab_tasks.utils.parse_cfg import parse_env_cfg
from tools.data_convert import convert_to_joint_range

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


def load_actions(path, episode):
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    t = pq.read_table(path)
    ep = t.filter(pc.equal(t.column("episode_index"), episode))
    return np.stack(ep.column("action").to_pylist()).astype(np.float32)


def close_events(g, thresh=2.7):
    """열림->닫힘 전이 프레임 목록"""
    closed = g < thresh
    idx = np.where(np.diff(closed.astype(int)) == 1)[0] + 1
    return idx.tolist()


def main():
    a = load_actions(args_cli.parquet, args_cli.episode)
    n = len(a)
    ev_right = close_events(a[:, 14])
    ev_left = close_events(a[:, 15])
    print(f"[probe] frames={n}  right close@{ev_right}  left close@{ev_left}")
    watch = sorted(set(ev_right + ev_left))

    env_cfg = parse_env_cfg(args_cli.task, device=args_cli.device, num_envs=1)
    env_cfg.env_name = args_cli.task
    # 카메라를 꺼서 재생을 빠르게 한다 (좌표만 필요)
    for cam in ("world_camera", "front_camera", "left_wrist_camera", "right_wrist_camera"):
        if hasattr(env_cfg.scene, cam):
            setattr(env_cfg.scene, cam, None)
            print(f"[probe] disabled sensor: {cam}")

    env = gym.make(args_cli.task, cfg=env_cfg).unwrapped
    env.reset()

    robot = env.scene["robot"]
    n2i = {x: i for i, x in enumerate(robot.joint_names)}
    la = [n2i[x] for x in LEFT_ARM_JOINTS]
    ra = [n2i[x] for x in RIGHT_ARM_JOINTS]
    lg = [n2i[x] for x in ("left_hand_Joint1_1", "left_hand_Joint2_1")]
    rg = [n2i[x] for x in ("right_hand_Joint1_1", "right_hand_Joint2_1")]

    b2i = {x: i for i, x in enumerate(robot.body_names)}
    ltips = [b2i[x] for x in ("left_hand_Link1_3", "left_hand_Link2_3")]
    rtips = [b2i[x] for x in ("right_hand_Link1_3", "right_hand_Link2_3")]

    for k in ("red_block", "yellow_block", "green_block"):
        if k in env.scene.keys():
            p = env.scene[k].data.root_pos_w[0]
            print(f"[probe] scene {k:14s} = {[round(v,4) for v in p.tolist()]}")

    action = torch.zeros(env.action_space.shape, device=env.device)
    dt = env.step_dt if hasattr(env, "step_dt") else 0.01

    t = 0.0
    last_f = -1
    results = {}
    while simulation_app.is_running():
        f = int(t * args_cli.fps)
        if f >= n:
            break
        act = a[f]
        action[:] = 0.0
        action[0, la] = torch.as_tensor(act[0:7], device=env.device)
        action[0, ra] = torch.as_tensor(act[7:14], device=env.device)
        for i in lg:
            action[0, i] = convert_to_joint_range(float(act[15]))
        for i in rg:
            action[0, i] = convert_to_joint_range(float(act[14]))
        with torch.inference_mode():
            env.step(action)

        if f != last_f and f in watch:
            lp = robot.data.body_pos_w[0, ltips].mean(dim=0)
            rp = robot.data.body_pos_w[0, rtips].mean(dim=0)
            results[f] = (lp.tolist(), rp.tolist())
            tag = []
            if f in ev_right:
                tag.append("RIGHT-CLOSE")
            if f in ev_left:
                tag.append("LEFT-CLOSE")
            print(f"[probe] frame {f:5d} {'/'.join(tag):22s} "
                  f"L={[round(v,4) for v in lp.tolist()]}  R={[round(v,4) for v in rp.tolist()]}")
        last_f = f
        t += dt

    print("\n[probe] ===== SUMMARY (grasp points, world) =====")
    for f in sorted(results):
        lp, rp = results[f]
        which = "RIGHT" if f in ev_right else "LEFT"
        p = rp if f in ev_right else lp
        print(f"  frame {f:5d}  {which:5s} grasp @ {[round(v,4) for v in p]}")

    env.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback

        traceback.print_exc()
        sys.stdout.flush()
    finally:
        simulation_app.close()
