#!/usr/bin/env python3
# sim_view.py -- DDS 없이 G1 씬만 띄워 보는 최소 실행기
# sim_main.py 는 unitree_sdk2py(cyclonedds) 를 요구하는데 Windows 에서 빌드가 막힌다.
# 이 스크립트는 같은 태스크 환경을 gym.make 로 직접 띄우고 zero action 으로만 스텝한다.
import os

project_root = os.path.dirname(os.path.abspath(__file__))
os.environ["PROJECT_ROOT"] = project_root

import argparse
import importlib.util
import sys
import types


def _install_dds_stub():
    """unitree_sdk2py(cyclonedds) 가 Windows 에서 빌드되지 않으므로 import 만 통과시킨다.

    tasks/common_observations/g1_29dof_state.py 가 모듈 레벨에서
    `from dds.dds_master import dds_manager` 를 하고, 그게 unitree_sdk2py 를 끌어온다.
    이 뷰어는 DDS 로 실제 통신을 하지 않으므로 껍데기만 있으면 된다.
    """
    if importlib.util.find_spec("unitree_sdk2py") is not None:
        print("[view] real unitree_sdk2py found -- stub not installed")
        return

    class _Stub:
        def __init__(self, *a, **k):
            pass

        def __call__(self, *a, **k):
            return _Stub()

        def __getattr__(self, name):
            return _Stub()

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
    def _make_getattr():
        def _getattr(attr):
            # dunder 는 진짜 AttributeError 를 내야 한다.
            # 안 그러면 Isaac Sim 확장 로더가 __file__/__spec__ 자리에서 클래스를 받고
            # "TypeError: expected str, bytes or os.PathLike object, not type" 로 깨진다.
            if attr.startswith("__") and attr.endswith("__"):
                raise AttributeError(attr)
            return _Stub

        return _getattr

    for name in names:
        mod = types.ModuleType(name)
        mod.__path__ = []  # 패키지로 취급되게 한다
        mod.__getattr__ = _make_getattr()
        sys.modules[name] = mod
    print("[view] unitree_sdk2py stub installed (DDS 통신 없음)")


_install_dds_stub()

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="Unitree G1 scene viewer (no DDS)")
parser.add_argument("--task", type=str, default="Isaac-PickPlace-Cylinder-G129-Dex1-Joint")
parser.add_argument("--seed", type=int, default=42)
parser.add_argument("--steps", type=int, default=0, help="0 이면 무한")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import gymnasium as gym
import torch

import tasks  # noqa: F401  -- gym.register 를 실행시킨다
from isaaclab_tasks.utils.parse_cfg import parse_env_cfg


def main():
    env_cfg = parse_env_cfg(args_cli.task, device=args_cli.device, num_envs=1)
    env_cfg.env_name = args_cli.task
    env_cfg.seed = args_cli.seed

    print(f"\n[view] creating env: {args_cli.task}")
    env = gym.make(args_cli.task, cfg=env_cfg).unwrapped
    env.seed(args_cli.seed)
    print("[view] env created")

    try:
        for name, sensor in getattr(env.scene, "sensors", {}).items():
            print(f"[view] sensor: {name}")
    except Exception as e:
        print(f"[view] failed to list sensors: {e}")

    env.reset()
    print("[view] reset done -- 뷰포트에서 카메라를 움직여 스크린샷을 찍으세요")

    action = torch.zeros(env.action_space.shape, device=env.device)

    step = 0
    while simulation_app.is_running():
        if args_cli.steps and step >= args_cli.steps:
            break
        with torch.inference_mode():
            env.step(action)
        step += 1

    env.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback

        traceback.print_exc()
    finally:
        simulation_app.close()
