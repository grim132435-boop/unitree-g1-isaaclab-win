# Copyright (c) 2022-2025, The Isaac Lab Project Developers.
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Package containing task implementations for various robotic environments."""

import os
import toml

# Conveniences to other module directories via relative paths
ISAACLAB_TASKS_EXT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "./"))
"""Path to the extension source directory."""

ISAACLAB_TASKS_METADATA = toml.load(os.path.join(ISAACLAB_TASKS_EXT_DIR, "config", "extension.toml"))
"""Extension metadata dictionary parsed from the extension.toml file."""

# Configure the module-level variables
__version__ = ISAACLAB_TASKS_METADATA["package"]["version"]

##
# Register Gym environments.
##

from .utils import import_packages

# The blacklist is used to prevent importing configs from sub-packages
# TODO(@ashwinvk): Remove pick_place from the blacklist once pinocchio from Isaac Sim is compatibility
_BLACKLIST_PKGS = ["utils", ".mdp", "pick_place"]
# NOTE (Windows 우회): 아래 태스크들은 `pink`(pinocchio 기반 IK) 를 요구하는데
# pinocchio 는 Windows 에서 C++ 소스 빌드가 필요해 설치되지 않는다. 원본은 __init__.py.bak.
_BLACKLIST_PKGS += [
    "move_cylinder",
    "pick_place_cylinder_g1_29dof_dex1",
    "pick_place_cylinder_g1_29dof_inspire",
    "pick_place_redblock_g1_29dof_dex3",
    "pick_redblock_into_drawer_g1_29dof_dex3",
    "pick_place_cylinder_h12_27dof_inspire",
]
# Import all configs in this package
import_packages(__name__, _BLACKLIST_PKGS)
