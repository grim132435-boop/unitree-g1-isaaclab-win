#!/usr/bin/env python3
# sim_pick.py -- DDS 없이 G1 이 앞의 큐브를 집는 데모.
#
# 핵심 사실 (sim_probe.py 로 실측):
#  - 액션 = JointPositionActionCfg(joint_names=[".*"], use_default_offset=True)
#    이고 default_joint_pos 가 전부 0 이므로 **action[i] = 목표 관절각(rad)** 이다.
#  - 기본 자세에서 왼손 그리퍼는 red_block 에서 약 7cm 거리에 있다.
#  - 그래서 Isaac Lab 내장 DifferentialIKController(Jacobian 기반)로
#    EE 를 블록 파지점까지 보내고, 그리퍼를 닫고, 들어올린다.
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

parser = argparse.ArgumentParser(description="G1 picks a cube (no DDS, Jacobian IK)")
parser.add_argument("--task", type=str, default="Isaac-Stack-RgyBlock-G129-Dex1-Joint")
parser.add_argument("--target", type=str, default="red_block", help="집을 블록")
parser.add_argument("--arm", type=str, default="left", choices=["left", "right"])
parser.add_argument("--grip", type=float, default=0.5, help="그리퍼 닫힘 각(rad). 부호는 로그 보고 조정")
parser.add_argument("--grip-sign2", type=float, default=1.0, help="두번째 손가락 부호 배수(+1/-1)")
parser.add_argument("--lift", type=float, default=0.15, help="들어올릴 높이(m)")
parser.add_argument("--loop", action="store_true", help="시퀀스를 반복")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import gymnasium as gym
import torch

import tasks  # noqa: F401
from isaaclab.controllers import DifferentialIKController, DifferentialIKControllerCfg
from isaaclab.managers import SceneEntityCfg
from isaaclab.utils.math import subtract_frame_transforms
from isaaclab_tasks.utils.parse_cfg import parse_env_cfg

A = args_cli.arm

# 페이즈: (이름, 지속시간 초, 그리퍼 닫힘 여부, 목표 오프셋 z)
PHASES = [
    ("settle", 1.5, False, 0.0),
    ("approach", 3.0, False, 0.0),
    ("close", 1.5, True, 0.0),
    ("lift", 2.5, True, None),  # None -> lift 높이 사용
    ("hold", 2.0, True, None),
]


def main():
    env_cfg = parse_env_cfg(args_cli.task, device=args_cli.device, num_envs=1)
    env_cfg.env_name = args_cli.task
    env = gym.make(args_cli.task, cfg=env_cfg).unwrapped
    env.reset()

    robot = env.scene["robot"]
    device = env.device
    print(f"[pick] is_fixed_base = {robot.is_fixed_base}")

    # ---- 팔 관절 / EE body 해석 ----
    arm_cfg = SceneEntityCfg(
        "robot",
        joint_names=[f"{A}_shoulder_.*", f"{A}_elbow_joint", f"{A}_wrist_.*"],
        body_names=[f"{A}_hand_base_link"],
    )
    arm_cfg.resolve(env.scene)
    arm_joint_ids = arm_cfg.joint_ids
    ee_body_id = arm_cfg.body_ids[0]
    print(f"[pick] arm joints: {[robot.joint_names[i] for i in arm_joint_ids]}")
    print(f"[pick] ee body   : {robot.body_names[ee_body_id]} (idx {ee_body_id})")

    ee_jacobi_idx = ee_body_id - 1 if robot.is_fixed_base else ee_body_id

    # ---- 그리퍼 관절 + 한계 ----
    grip_ids = [i for i, n in enumerate(robot.joint_names) if f"{A}_hand_Joint" in n]
    lim = robot.data.soft_joint_pos_limits[0]
    for i in grip_ids:
        print(f"[pick] gripper joint [{i}] {robot.joint_names[i]}  limits={lim[i].tolist()}")

    # 손가락 끝 body (거리 로그용)
    tip_ids = [i for i, n in enumerate(robot.body_names) if f"{A}_hand_Link" in n and n.endswith("_3")]
    print(f"[pick] finger tips: {[robot.body_names[i] for i in tip_ids]}")

    # ---- 파지점 오프셋: hand_base_link -> 손가락 끝 중점 ----
    ee_pos_w0 = robot.data.body_pos_w[0, ee_body_id]
    tips_w0 = robot.data.body_pos_w[0, tip_ids].mean(dim=0)
    grasp_offset_w = tips_w0 - ee_pos_w0
    print(f"[pick] grasp offset (world, at rest) = {[round(v,4) for v in grasp_offset_w.tolist()]}")

    # ---- 목표 블록 ----
    block = env.scene[args_cli.target]
    block_pos_w = block.data.root_pos_w[0].clone()
    print(f"[pick] target {args_cli.target} pos_w = {[round(v,4) for v in block_pos_w.tolist()]}")

    # EE(hand_base) 가 가야 할 world 위치 = 블록 - 파지오프셋
    ee_goal_w_base = block_pos_w - grasp_offset_w
    print(f"[pick] ee goal (world) = {[round(v,4) for v in ee_goal_w_base.tolist()]}")

    # 자세는 초기 자세를 유지한다 (블록이 이미 정면이라 회전이 필요 없다)
    ee_quat_w0 = robot.data.body_quat_w[0, ee_body_id].clone()

    # ---- IK 컨트롤러 ----
    ik_cfg = DifferentialIKControllerCfg(command_type="pose", use_relative_mode=False, ik_method="dls")
    ik = DifferentialIKController(ik_cfg, num_envs=1, device=device)

    action = torch.zeros(env.action_space.shape, device=device)
    dt = env.step_dt if hasattr(env, "step_dt") else 0.01

    def run_sequence():
        t_phase = 0.0
        pi = 0
        step = 0
        ik.reset()
        while simulation_app.is_running() and pi < len(PHASES):
            name, dur, closed, zoff = PHASES[pi]

            goal_w = ee_goal_w_base.clone()
            if name == "settle":
                goal_w = robot.data.body_pos_w[0, ee_body_id].clone()
            elif zoff is None:
                goal_w[2] += args_cli.lift
            else:
                goal_w[2] += zoff

            # world goal -> root frame
            root_pose_w = robot.data.root_pose_w
            goal_pos_b, goal_quat_b = subtract_frame_transforms(
                root_pose_w[:, 0:3],
                root_pose_w[:, 3:7],
                goal_w.unsqueeze(0),
                ee_quat_w0.unsqueeze(0),
            )
            ik.set_command(torch.cat([goal_pos_b, goal_quat_b], dim=-1))

            # 현재 EE (root frame)
            ee_pose_w = robot.data.body_pose_w[:, ee_body_id]
            ee_pos_b, ee_quat_b = subtract_frame_transforms(
                root_pose_w[:, 0:3], root_pose_w[:, 3:7], ee_pose_w[:, 0:3], ee_pose_w[:, 3:7]
            )
            jacobian = robot.root_physx_view.get_jacobians()[:, ee_jacobi_idx, :, arm_joint_ids]
            joint_pos = robot.data.joint_pos[:, arm_joint_ids]
            joint_pos_des = ik.compute(ee_pos_b, ee_quat_b, jacobian, joint_pos)

            action[:] = 0.0
            action[0, arm_joint_ids] = joint_pos_des[0]
            if closed:
                action[0, grip_ids[0]] = args_cli.grip
                if len(grip_ids) > 1:
                    action[0, grip_ids[1]] = args_cli.grip * args_cli.grip_sign2

            with torch.inference_mode():
                env.step(action)

            # 로그
            if step % 25 == 0:
                tips = robot.data.body_pos_w[0, tip_ids]
                tip_mid = tips.mean(dim=0)
                bpos = block.data.root_pos_w[0]
                d = torch.norm(tip_mid - bpos).item()
                spread = torch.norm(tips[0] - tips[1]).item() if len(tip_ids) > 1 else float("nan")
                print(
                    f"[pick] {name:8s} t={t_phase:4.1f}  tip-block={d:.4f}m  "
                    f"finger_spread={spread:.4f}m  block_z={bpos[2].item():.4f}"
                )

            t_phase += dt
            step += 1
            if t_phase >= dur:
                print(f"[pick] --- phase '{name}' done ---")
                pi += 1
                t_phase = 0.0

    run_sequence()
    while args_cli.loop and simulation_app.is_running():
        print("[pick] restarting sequence")
        env.reset()
        run_sequence()

    # 결과 요약
    bpos = block.data.root_pos_w[0]
    print(f"[pick] FINAL block pos = {[round(v,4) for v in bpos.tolist()]}")
    print(f"[pick] block lifted by  = {(bpos[2].item() - block_pos_w[2].item()):.4f} m")

    while simulation_app.is_running():
        with torch.inference_mode():
            env.step(action)

    env.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("[pick] interrupted")
    except Exception:
        import traceback

        traceback.print_exc()
        sys.stdout.flush()
    finally:
        simulation_app.close()
