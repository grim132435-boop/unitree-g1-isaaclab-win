
# Copyright (c) 2025, Unitree Robotics Co., Ltd. All Rights Reserved.
# License: Apache License, Version 2.0
"""Unitree G1 robot task module
contains various task implementations for the G1 robot, such as pick and place, motion control, etc.
"""

# NOTE (Windows 우회): 일부 태스크는 `pink`(pinocchio 기반 IK) 를 요구하는데,
# pinocchio 는 Windows 에서 C++ 소스 빌드가 필요해 설치되지 않는다.
# 그래서 import 실패한 태스크는 건너뛰고 나머지만 등록한다.
# 원본은 __init__.py.bak 에 보관돼 있다.
import logging as _logging

_SUBMODULES = [
    "pick_place_cylinder_g1_29dof_dex3",
    "pick_place_cylinder_g1_29dof_dex1",
    "pick_place_cylinder_g1_29dof_inspire",
    "pick_place_redblock_g1_29dof_dex1",
    "pick_place_redblock_g1_29dof_dex3",
    "stack_rgyblock_g1_29dof_dex1",
    "stack_rgyblock_g1_29dof_dex3",
    "stack_rgyblock_g1_29dof_inspire",
    "pick_redblock_into_drawer_g1_29dof_dex1",
    "pick_redblock_into_drawer_g1_29dof_dex3",
    "pick_place_redblock_g1_29dof_inspire",
    "move_cylinder_g1_29dof_dex1_wholebody",
    "move_cylinder_g1_29dof_dex3_wholebody",
    "move_cylinder_g1_29dof_inspire_wholebody",
]

__all__ = []

for _name in _SUBMODULES:
    try:
        _mod = __import__(f"{__name__}.{_name}", fromlist=[_name])
        globals()[_name] = _mod
        __all__.append(_name)
    except ModuleNotFoundError as _e:
        print(f"[g1_tasks] skipped {_name}: missing dependency ({_e.name})")
    except Exception as _e:  # noqa: BLE001
        print(f"[g1_tasks] skipped {_name}: {type(_e).__name__}: {_e}")
