#!/usr/bin/env python3
# sim_demo.py -- DDS 없이 G1 을 실제로 움직이는 데모.
#
# 이 태스크의 액션은 JointPositionActionCfg(joint_names=[".*"], use_default_offset=True) 라서
# action 벡터 = "기본 자세로부터의 관절 목표 오프셋(rad)" 이다. action=0 이면 기본 자세.
# 그래서 팔 관절에 사인파를 넣으면 그대로 움직인다. 정책도 텔레옵도 필요 없다.
import os

project_root = os.path.dirname(os.path.abspath(__file__))
os.environ["PROJECT_ROOT"] = project_root

import argparse
import importlib.util
import math
import sys
import types


def _install_dds_stub():
    """unitree_sdk2py(cyclonedds) 가 Windows 에서 빌드되지 않으므로 import 만 통과시킨다."""
    if importlib.util.find_spec("unitree_sdk2py") is not None:
        print("[demo] real unitree_sdk2py found -- stub not installed")
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

    names = [
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
    ]
    for name in names:
        mod = types.ModuleType(name)
        mod.__path__ = []
        mod.__getattr__ = _make_getattr()
        sys.modules[name] = mod
    print("[demo] unitree_sdk2py stub installed (DDS 통신 없음)")


_install_dds_stub()

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="Move Unitree G1 without DDS")
parser.add_argument("--task", type=str, default="Isaac-Stack-RgyBlock-G129-Dex1-Joint")
parser.add_argument("--seed", type=int, default=42)
parser.add_argument("--amp", type=float, default=0.35, help="관절 진폭(rad)")
parser.add_argument("--period", type=float, default=4.0, help="주기(초)")
parser.add_argument("--list-joints", action="store_true", help="관절 이름만 출력하고 종료")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import gymnasium as gym
import torch

import tasks  # noqa: F401
from isaaclab_tasks.utils.parse_cfg import parse_env_cfg

# 움직일 관절: (이름에 포함된 문자열, 위상, 진폭배수)
# G1 29DOF 팔 체인. 이름이 없으면 조용히 건너뛴다.
MOTION = [
    ("left_shoulder_pitch", 0.0, 1.0),
    ("right_shoulder_pitch", math.pi, 1.0),
    ("left_shoulder_roll", 0.0, 0.5),
    ("right_shoulder_roll", math.pi, 0.5),
    ("left_elbow", math.pi / 2, 1.2),
    ("right_elbow", math.pi / 2 + math.pi, 1.2),
    ("left_wrist_pitch", 0.0, 0.6),
    ("right_wrist_pitch", math.pi, 0.6),
]


def main():
    env_cfg = parse_env_cfg(args_cli.task, device=args_cli.device, num_envs=1)
    env_cfg.env_name = args_cli.task
    env_cfg.seed = args_cli.seed

    print(f"[demo] creating env: {args_cli.task}")
    env = gym.make(args_cli.task, cfg=env_cfg).unwrapped
    env.seed(args_cli.seed)
    print("[demo] env created")

    robot = env.scene["robot"]
    joint_names = list(robot.joint_names)
    print(f"[demo] {len(joint_names)} joints:")
    for i, n in enumerate(joint_names):
        print(f"   [{i:2d}] {n}")

    if args_cli.list_joints:
        env.close()
        return

    # 액션 인덱스는 joint_names 순서와 같다 (joint_names=[".*"])
    plan = []
    for key, phase, gain in MOTION:
        idx = [i for i, n in enumerate(joint_names) if key in n]
        if not idx:
            print(f"[demo] joint not found, skipped: {key}")
            continue
        for i in idx:
            plan.append((i, phase, gain))
            print(f"[demo] will move [{i}] {joint_names[i]}  (phase={phase:.2f}, gain={gain})")

    if not plan:
        print("[demo] 움직일 관절을 하나도 못 찾았습니다 -- --list-joints 로 이름을 확인하세요")

    env.reset()
    print("[demo] reset done -- 움직임 시작 (Ctrl+C 로 종료)")

    action = torch.zeros(env.action_space.shape, device=env.device)
    dt = env.step_dt if hasattr(env, "step_dt") else 0.01
    step = 0

    while simulation_app.is_running():
        t = step * dt
        w = 2.0 * math.pi / args_cli.period
        action[:] = 0.0
        for i, phase, gain in plan:
            action[0, i] = args_cli.amp * gain * math.sin(w * t + phase)
        with torch.inference_mode():
            env.step(action)
        step += 1

    env.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("[demo] interrupted")
    except Exception:
        import traceback

        traceback.print_exc()
        sys.stdout.flush()
    finally:
        simulation_app.close()
