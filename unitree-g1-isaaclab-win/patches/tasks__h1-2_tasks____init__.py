
# Copyright (c) 2025, Unitree Robotics Co., Ltd. All Rights Reserved.
# License: Apache License, Version 2.0
"""Unitree H1-2 robot task module."""

# NOTE (Windows 우회): g1_tasks/__init__.py 와 같은 이유로 import 실패 태스크는 건너뛴다.
# 원본은 __init__.py.bak 에 보관돼 있다.

_SUBMODULES = [
    "pick_place_cylinder_h12_27dof_inspire",
    "stack_rgyblock_h12_27dof_inspire",
    "pick_place_redblock_h12_27dof_inspire",
]

__all__ = []

for _name in _SUBMODULES:
    try:
        _mod = __import__(f"{__name__}.{_name}", fromlist=[_name])
        globals()[_name] = _mod
        __all__.append(_name)
    except ModuleNotFoundError as _e:
        print(f"[h1-2_tasks] skipped {_name}: missing dependency ({_e.name})")
    except Exception as _e:  # noqa: BLE001
        print(f"[h1-2_tasks] skipped {_name}: {type(_e).__name__}: {_e}")
