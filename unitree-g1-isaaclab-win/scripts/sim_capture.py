#!/usr/bin/env python3
# sim_capture.py -- GUI 없이(headless) G1 씬을 렌더링해 PNG 로 저장한다.
# 창을 못 띄우는 환경에서도 스크린샷을 남기기 위한 경로.
import os

project_root = os.path.dirname(os.path.abspath(__file__))
os.environ["PROJECT_ROOT"] = project_root

import argparse
import importlib.util
import sys
import types


def _install_dds_stub():
    """unitree_sdk2py(cyclonedds) 가 Windows 에서 빌드되지 않으므로 import 만 통과시킨다."""
    if importlib.util.find_spec("unitree_sdk2py") is not None:
        print("[cap] real unitree_sdk2py found -- stub not installed")
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
    print("[cap] unitree_sdk2py stub installed (DDS 통신 없음)")


_install_dds_stub()

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="Capture G1 scene to PNG (headless)")
parser.add_argument("--task", type=str, default="Isaac-Stack-RgyBlock-G129-Dex1-Joint")
parser.add_argument("--seed", type=int, default=42)
parser.add_argument("--warmup", type=int, default=30, help="캡처 전 스텝 수")
parser.add_argument("--outdir", type=str, default="capture_out")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import gymnasium as gym
import numpy as np
import torch

import tasks  # noqa: F401
from isaaclab_tasks.utils.parse_cfg import parse_env_cfg


def save_png(path, arr):
    from PIL import Image

    if arr.dtype != np.uint8:
        arr = np.clip(arr, 0, 255).astype(np.uint8)
    if arr.shape[-1] == 4:
        arr = arr[..., :3]
    Image.fromarray(arr).save(path)
    print(f"[cap] saved {path}  shape={arr.shape}")


def main():
    outdir = os.path.join(project_root, args_cli.outdir)
    os.makedirs(outdir, exist_ok=True)

    env_cfg = parse_env_cfg(args_cli.task, device=args_cli.device, num_envs=1)
    env_cfg.env_name = args_cli.task
    env_cfg.seed = args_cli.seed

    print(f"[cap] creating env: {args_cli.task}")
    env = gym.make(args_cli.task, cfg=env_cfg).unwrapped
    env.seed(args_cli.seed)
    print("[cap] env created")

    sensors = getattr(env.scene, "sensors", {})
    for name in sensors:
        print(f"[cap] sensor: {name}")

    env.reset()
    print("[cap] reset done")

    action = torch.zeros(env.action_space.shape, device=env.device)
    for i in range(args_cli.warmup):
        with torch.inference_mode():
            env.step(action)
    print(f"[cap] stepped {args_cli.warmup} times")

    for name, sensor in sensors.items():
        try:
            data = sensor.data.output
            if "rgb" in data:
                arr = data["rgb"][0].detach().cpu().numpy()
                save_png(os.path.join(outdir, f"{name}.png"), arr)
        except Exception as e:  # noqa: BLE001
            print(f"[cap] sensor {name} capture failed: {type(e).__name__}: {e}")

    print(f"[cap] output dir: {outdir}")
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
