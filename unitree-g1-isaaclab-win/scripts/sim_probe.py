#!/usr/bin/env python3
# sim_probe.py -- 씬 구성 조사: scene 키, body 이름, 큐브/손 좌표, 기본 관절값
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
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import gymnasium as gym
import torch

import tasks  # noqa: F401
from isaaclab_tasks.utils.parse_cfg import parse_env_cfg


def main():
    env_cfg = parse_env_cfg(args_cli.task, device=args_cli.device, num_envs=1)
    env_cfg.env_name = args_cli.task
    env = gym.make(args_cli.task, cfg=env_cfg).unwrapped
    env.reset()

    print("\n===== SCENE KEYS =====")
    for k in env.scene.keys():
        print(f"  scene['{k}']")

    robot = env.scene["robot"]

    print("\n===== BODY NAMES =====")
    for i, n in enumerate(robot.body_names):
        print(f"  [{i:2d}] {n}")

    print("\n===== ROBOT ROOT / DEFAULT JOINT POS =====")
    print("  root_pos_w:", robot.data.root_pos_w[0].tolist())
    dj = robot.data.default_joint_pos[0]
    for i, n in enumerate(robot.joint_names):
        print(f"  [{i:2d}] {n:32s} default={dj[i].item(): .4f}")

    print("\n===== HAND / EE BODY POSES (world) =====")
    for i, n in enumerate(robot.body_names):
        if "hand" in n.lower() or "wrist" in n.lower():
            p = robot.data.body_pos_w[0, i]
            print(f"  {n:32s} pos={[round(v,4) for v in p.tolist()]}")

    print("\n===== OBJECT POSES (world) =====")
    for k in env.scene.keys():
        try:
            obj = env.scene[k]
            if hasattr(obj, "data") and hasattr(obj.data, "root_pos_w"):
                p = obj.data.root_pos_w[0]
                print(f"  {k:24s} pos={[round(v,4) for v in p.tolist()]}")
        except Exception:
            pass

    print("\n===== ACTION SPACE =====")
    print("  shape:", env.action_space.shape)

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
