#!/usr/bin/env python3
"""
Isaac Sim standalone script for loading the SO-100 5-DOF arm from URDF.

This script imports the SO-100 robot arm into Isaac Sim with correct joint
properties, physics settings, and scene configuration (ground plane, lighting,
fixed base at origin). It validates that all required URDF and STL mesh files
exist before attempting import to avoid partial instantiation.

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5
"""

import os
import sys
from dataclasses import dataclass, field
from typing import List, Tuple

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Path resolution: locate the URDF and mesh directory relative to this script.
# Expected layout:
#   <workspace_root>/so_arm_100_isaac_sim/scripts/load_robot.py  (this file)
#   <workspace_root>/so_arm_100_description/urdf/so_arm_100_5dof.urdf.xacro
#   <workspace_root>/so_arm_100_description/models/so_arm_100_5dof/meshes/*.STL

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Resolve the workspace root.
# When installed via colcon, scripts live under:
#   <ws>/install/<pkg>/share/<pkg>/scripts/
# When running from source, scripts live under:
#   <ws>/src/<pkg>/scripts/
# We try ament_index first (works when workspace is sourced), then fall
# back to the source layout (/workspace/src/).
def _resolve_workspace_root():
    """Resolve the workspace root for locating description packages."""
    try:
        from ament_index_python.packages import get_package_share_directory
        # If ament_index works, return the share directory for so_arm_100_description
        desc_share = get_package_share_directory('so_arm_100_description')
        return desc_share, True  # (path, is_installed)
    except Exception:
        pass

    # Fallback: assume source layout at /workspace/src
    src_root = '/workspace/src'
    if os.path.isdir(os.path.join(src_root, 'so_arm_100_description')):
        return src_root, False

    # Final fallback: two levels up from script (original behavior)
    return os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..')), False


_RESOLVED_ROOT, _IS_INSTALLED = _resolve_workspace_root()

if _IS_INSTALLED:
    # When installed, _RESOLVED_ROOT IS the so_arm_100_description share dir
    URDF_RELATIVE_PATH = os.path.join(
        _RESOLVED_ROOT, "urdf", "so_arm_100_5dof.urdf.xacro"
    )
    MESH_RELATIVE_DIR = os.path.join(
        _RESOLVED_ROOT, "models", "so_arm_100_5dof", "meshes"
    )
    WORKSPACE_ROOT = None  # Not used when installed
else:
    WORKSPACE_ROOT = _RESOLVED_ROOT
    URDF_RELATIVE_PATH = os.path.join(
        "so_arm_100_description", "urdf", "so_arm_100_5dof.urdf.xacro"
    )
    MESH_RELATIVE_DIR = os.path.join(
        "so_arm_100_description", "models", "so_arm_100_5dof", "meshes"
    )

# All STL meshes that must be present for a complete robot import.
REQUIRED_MESHES = [
    "Base.STL",
    "Shoulder_Rotation_Pitch.STL",
    "Lower_Arm.STL",
    "Upper_Arm.STL",
    "Wrist_Pitch_Roll.STL",
    "Fixed_Gripper.STL",
    "Moving_Jaw.STL",
]

# Physics simulation step rate in Hz.
PHYSICS_STEP_RATE_HZ = 60

# Joint damping (Ns/m) applied uniformly to all revolute joints.
JOINT_DAMPING = 0.1


# ---------------------------------------------------------------------------
# Data Models — extracted directly from so_arm_100_5dof_arm.urdf.xacro
# ---------------------------------------------------------------------------


@dataclass
class InertialProperties:
    """Inertial properties for a robot link, extracted from URDF."""

    mass: float
    origin_xyz: Tuple[float, float, float]
    ixx: float
    ixy: float
    ixz: float
    iyy: float
    iyz: float
    izz: float


@dataclass
class JointConfig:
    """Joint configuration extracted from URDF."""

    name: str
    joint_type: str  # "revolute" or "fixed"
    parent_link: str
    child_link: str
    origin_xyz: Tuple[float, float, float]
    origin_rpy: Tuple[float, float, float]
    axis: Tuple[float, float, float]
    lower_limit: float
    upper_limit: float
    effort: float
    velocity: float
    damping: float


@dataclass
class LinkConfig:
    """Link configuration extracted from URDF."""

    name: str
    mesh_filename: str  # STL filename (e.g., "Base.STL")
    inertial: InertialProperties
    visual_origin_xyz: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    visual_origin_rpy: Tuple[float, float, float] = (0.0, 0.0, 0.0)


# Link definitions with inertial properties from URDF
LINK_CONFIGS: List[LinkConfig] = [
    LinkConfig(
        name="Base",
        mesh_filename="Base.STL",
        inertial=InertialProperties(
            mass=0.193184127927598,
            origin_xyz=(-2.4596e-07, 0.0311418169687909, 0.0175746661003382),
            ixx=0.000137030709467877,
            ixy=2.10136126944992e-08,
            ixz=4.24087422551286e-09,
            iyy=0.000169089551209259,
            iyz=2.26514711036514e-05,
            izz=0.000145097720857224,
        ),
    ),
    LinkConfig(
        name="Shoulder_Rotation_Pitch",
        mesh_filename="Shoulder_Rotation_Pitch.STL",
        inertial=InertialProperties(
            mass=0.119226314127197,
            origin_xyz=(-9.07886224712597e-05, 0.0590971820568318, 0.031089016892169),
            ixx=5.90408775624429e-05,
            ixy=4.90800532852998e-07,
            ixz=-5.90451772654387e-08,
            iyy=3.21498601038881e-05,
            iyz=-4.58026206663885e-06,
            izz=5.86058514263952e-05,
        ),
    ),
    LinkConfig(
        name="Upper_Arm",
        mesh_filename="Upper_Arm.STL",
        inertial=InertialProperties(
            mass=0.162409284599177,
            origin_xyz=(-1.7205170190925e-05, 0.0701802156327694, 0.00310545118155671),
            ixx=0.000167153146617081,
            ixy=1.03902689187701e-06,
            ixz=-1.20161820645189e-08,
            iyy=7.01946992214245e-05,
            iyz=2.11884806298698e-06,
            izz=0.000213280241160769,
        ),
    ),
    LinkConfig(
        name="Lower_Arm",
        mesh_filename="Lower_Arm.STL",
        inertial=InertialProperties(
            mass=0.147967774582291,
            origin_xyz=(-0.00339603710186651, 0.00137796353960074, 0.0768006751156044),
            ixx=0.000105333995841409,
            ixy=1.73059237226499e-07,
            ixz=-1.1720305455211e-05,
            iyy=0.000138766654485212,
            iyz=1.77429964684103e-06,
            izz=5.08741652515214e-05,
        ),
    ),
    LinkConfig(
        name="Wrist_Pitch_Roll",
        mesh_filename="Wrist_Pitch_Roll.STL",
        inertial=InertialProperties(
            mass=0.066132067097723,
            origin_xyz=(-0.00852653127372418, -0.0352278997897927, -2.34622481569413e-05),
            ixx=1.95717492443445e-05,
            ixy=-6.62714374412293e-07,
            ixz=5.20089016442066e-09,
            iyy=2.38028417569933e-05,
            iyz=4.09549055863776e-08,
            izz=3.4540143384536e-05,
        ),
    ),
    LinkConfig(
        name="Fixed_Gripper",
        mesh_filename="Fixed_Gripper.STL",
        inertial=InertialProperties(
            mass=0.0929859131176897,
            origin_xyz=(0.00552376906426563, -0.0280167153359021, 0.000483582592841092),
            ixx=4.3328249304211e-05,
            ixy=7.09654328670947e-06,
            ixz=5.99838530879484e-07,
            iyy=3.04451747368212e-05,
            iyz=-1.58743247545413e-07,
            izz=5.02460913506734e-05,
        ),
    ),
    LinkConfig(
        name="Moving_Jaw",
        mesh_filename="Moving_Jaw.STL",
        inertial=InertialProperties(
            mass=0.0202443794940372,
            origin_xyz=(-0.00161744605468241, -0.0303472584046471, 0.000449645961853651),
            ixx=1.10911325081525e-05,
            ixy=-5.35076503033314e-07,
            ixz=-9.46105662101403e-09,
            iyy=3.03576451001973e-06,
            iyz=-1.71146075110632e-07,
            izz=8.9916083370498e-06,
        ),
    ),
]

# Joint definitions extracted from URDF (6 revolute joints)
JOINT_CONFIGS: List[JointConfig] = [
    JointConfig(
        name="Shoulder_Rotation",
        joint_type="revolute",
        parent_link="Base",
        child_link="Shoulder_Rotation_Pitch",
        origin_xyz=(0.0, -0.0452, 0.0165),
        origin_rpy=(1.5708, 0.0, 0.0),
        axis=(0.0, -1.0, 0.0),
        lower_limit=-1.96,
        upper_limit=1.96,
        effort=1000.0,
        velocity=5.0,
        damping=JOINT_DAMPING,
    ),
    JointConfig(
        name="Shoulder_Pitch",
        joint_type="revolute",
        parent_link="Shoulder_Rotation_Pitch",
        child_link="Upper_Arm",
        origin_xyz=(0.0, 0.1025, 0.0306),
        origin_rpy=(0.0, 0.0, 0.0),
        axis=(1.0, 0.0, 0.0),
        lower_limit=-1.745,
        upper_limit=1.745,
        effort=1000.0,
        velocity=5.0,
        damping=JOINT_DAMPING,
    ),
    JointConfig(
        name="Elbow",
        joint_type="revolute",
        parent_link="Upper_Arm",
        child_link="Lower_Arm",
        origin_xyz=(0.0, 0.11257, 0.028),
        origin_rpy=(0.0, 0.0, 0.0),
        axis=(1.0, 0.0, 0.0),
        lower_limit=-1.5,
        upper_limit=1.5,
        effort=1000.0,
        velocity=5.0,
        damping=JOINT_DAMPING,
    ),
    JointConfig(
        name="Wrist_Pitch",
        joint_type="revolute",
        parent_link="Lower_Arm",
        child_link="Wrist_Pitch_Roll",
        origin_xyz=(0.0, 0.0052, 0.1349),
        origin_rpy=(-1.57079, 0.0, 0.0),
        axis=(1.0, 0.0, 0.0),
        lower_limit=-1.658,
        upper_limit=1.658,
        effort=1000.0,
        velocity=5.0,
        damping=JOINT_DAMPING,
    ),
    JointConfig(
        name="Wrist_Roll",
        joint_type="revolute",
        parent_link="Wrist_Pitch_Roll",
        child_link="Fixed_Gripper",
        origin_xyz=(0.0, -0.0601, 0.0),
        origin_rpy=(0.0, 1.57079, 0.0),
        axis=(0.0, 1.0, 0.0),
        lower_limit=-2.75,
        upper_limit=2.75,
        effort=1000.0,
        velocity=5.0,
        damping=JOINT_DAMPING,
    ),
    JointConfig(
        name="Gripper",
        joint_type="revolute",
        parent_link="Fixed_Gripper",
        child_link="Moving_Jaw",
        origin_xyz=(-0.0202, -0.0244, 0.0),
        origin_rpy=(3.1416, 0.0, 3.1416),
        axis=(0.0, 0.0, 1.0),
        lower_limit=-0.1792,
        upper_limit=1.5708,
        effort=1000.0,
        velocity=5.0,
        damping=JOINT_DAMPING,
    ),
]


# ---------------------------------------------------------------------------
# File Validation
# ---------------------------------------------------------------------------


def validate_required_files(workspace_root: str) -> None:
    """
    Validate that the URDF and all required STL mesh files exist.

    Aborts the process with a descriptive error if any file is missing.
    This prevents partial robot instantiation per Requirement 3.5.
    """
    if _IS_INSTALLED:
        urdf_path = URDF_RELATIVE_PATH  # Already absolute
        mesh_dir = MESH_RELATIVE_DIR    # Already absolute
    else:
        urdf_path = os.path.join(workspace_root, URDF_RELATIVE_PATH)
        mesh_dir = os.path.join(workspace_root, MESH_RELATIVE_DIR)

    if not os.path.isfile(urdf_path):
        print(
            f"ERROR: URDF file not found: {urdf_path}\n"
            "Cannot proceed with robot import. Aborting.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not os.path.isdir(mesh_dir):
        print(
            f"ERROR: Mesh directory not found: {mesh_dir}\n"
            "Cannot proceed with robot import. Aborting.",
            file=sys.stderr,
        )
        sys.exit(1)

    missing_meshes = []
    for mesh_name in REQUIRED_MESHES:
        mesh_path = os.path.join(mesh_dir, mesh_name)
        if not os.path.isfile(mesh_path):
            missing_meshes.append(mesh_path)

    if missing_meshes:
        print(
            "ERROR: The following required STL mesh files are missing:\n"
            + "\n".join(f"  - {p}" for p in missing_meshes)
            + "\nCannot proceed with robot import. Aborting.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"All required files validated successfully.")
    print(f"  URDF: {urdf_path}")
    print(f"  Meshes: {mesh_dir} ({len(REQUIRED_MESHES)} STL files)")


# ---------------------------------------------------------------------------
# Isaac Sim Scene Setup
# ---------------------------------------------------------------------------


def setup_isaac_sim():
    """
    Initialize Isaac Sim in standalone mode.

    Returns the SimulationApp instance. Must be called before any other
    omni imports.
    """
    from isaacsim import SimulationApp

    # Launch Isaac Sim in headless mode by default; override with
    # ISAAC_SIM_HEADLESS=0 environment variable for GUI mode.
    headless = os.environ.get("ISAAC_SIM_HEADLESS", "1") == "1"

    config = {
        "headless": headless,
        "width": 1280,
        "height": 720,
        "anti_aliasing": 0,
    }

    simulation_app = SimulationApp(config)
    print("Isaac Sim application started.")
    return simulation_app


def configure_physics_scene():
    """
    Configure the physics scene with 60 Hz step rate and gravity.
    """
    import omni.isaac.core.utils.stage as stage_utils
    from pxr import UsdPhysics, PhysxSchema, Gf

    stage = stage_utils.get_current_stage()

    # Get or create physics scene
    physics_scene_path = "/World/PhysicsScene"
    physics_scene = UsdPhysics.Scene.Define(stage, physics_scene_path)

    # Set gravity (Earth standard, downward along Z in Isaac Sim)
    physics_scene.CreateGravityDirectionAttr(Gf.Vec3f(0.0, 0.0, -1.0))
    physics_scene.CreateGravityMagnitudeAttr(9.81)

    # Configure PhysX-specific settings for 60 Hz
    physx_scene = PhysxSchema.PhysxSceneAPI.Apply(stage.GetPrimAtPath(physics_scene_path))
    time_steps_per_second = PHYSICS_STEP_RATE_HZ
    physx_scene.CreateTimeStepsPerSecondAttr(time_steps_per_second)
    physx_scene.CreateEnableCCDAttr(False)
    physx_scene.CreateEnableStabilizationAttr(True)

    print(f"Physics scene configured: {time_steps_per_second} Hz step rate.")


def add_ground_plane():
    """
    Add a ground plane to the scene at z=0.
    """
    from omni.isaac.core.objects import GroundPlane

    ground_plane = GroundPlane(
        prim_path="/World/GroundPlane",
        z_position=0.0,
        size=10.0,
    )
    print("Ground plane added at z=0.")


def add_directional_light():
    """
    Add a directional light source to illuminate the scene.
    """
    import omni.isaac.core.utils.stage as stage_utils
    from pxr import UsdLux, Gf

    stage = stage_utils.get_current_stage()

    light_path = "/World/DirectionalLight"
    light = UsdLux.DistantLight.Define(stage, light_path)
    light.CreateIntensityAttr(3000.0)
    light.CreateAngleAttr(0.53)

    # Position and orient the light
    xform = light.GetPrim()
    from pxr import UsdGeom

    xformable = UsdGeom.Xformable(xform)
    xformable.ClearXformOpOrder()
    xformable.AddRotateXYZOp().Set(Gf.Vec3f(-45.0, 45.0, 0.0))

    print("Directional light added to scene.")


def import_robot_urdf(workspace_root: str):
    """
    Import the SO-100 5-DOF arm URDF into the Isaac Sim stage.

    Uses the Isaac Sim URDF importer to load the robot with all meshes
    at visual scale 1.0, and configures joint limits, physics properties,
    and damping values.
    """
    import omni.isaac.core.utils.stage as stage_utils
    from omni.isaac.urdf import _urdf as urdf_interface
    from pxr import UsdPhysics, PhysxSchema, Gf, UsdGeom

    if _IS_INSTALLED:
        urdf_path = URDF_RELATIVE_PATH  # Already absolute
    else:
        urdf_path = os.path.join(workspace_root, URDF_RELATIVE_PATH)

    # Configure URDF import settings
    import_config = urdf_interface.ImportConfig()
    import_config.merge_fixed_joints = False
    import_config.fix_base = True  # Fix robot base to world frame at [0,0,0]
    import_config.import_inertia_tensor = True
    import_config.distance_scale = 1.0
    import_config.density = 0.0  # Use mass from URDF instead of density
    import_config.default_drive_type = urdf_interface.UrdfJointTargetType.JOINT_DRIVE_POSITION
    import_config.default_drive_strength = 1000.0
    import_config.default_position_drive_damping = JOINT_DAMPING

    # Perform URDF import
    urdf_importer = urdf_interface.acquire_urdf_interface()

    # Parse the URDF
    parse_result = urdf_importer.parse_urdf(urdf_path, import_config)
    if parse_result is None:
        print(
            f"ERROR: Failed to parse URDF file: {urdf_path}\n"
            "The file may be malformed or contain unsupported xacro elements.\n"
            "Aborting robot import.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Import into the stage
    robot_prim_path = "/World/SO100Arm"
    result = urdf_importer.import_robot(
        urdf_path, robot_prim_path, import_config, ""
    )

    if result is None:
        print(
            f"ERROR: Failed to import robot from URDF: {urdf_path}\n"
            "Check that all mesh files are accessible and the URDF is valid.\n"
            "Aborting robot import.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Robot imported at prim path: {robot_prim_path}")

    # Post-import configuration: set joint limits and damping
    stage = stage_utils.get_current_stage()
    _configure_joints(stage, robot_prim_path)
    _configure_link_physics(stage, robot_prim_path)

    # Fix the base link to world at [0, 0, 0]
    robot_prim = stage.GetPrimAtPath(robot_prim_path)
    if robot_prim.IsValid():
        xformable = UsdGeom.Xformable(robot_prim)
        xformable.ClearXformOpOrder()
        xformable.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, 0.0))
        xformable.AddOrientOp().Set(Gf.Quatd(1.0, 0.0, 0.0, 0.0))

    print("Robot base fixed at world origin [0, 0, 0].")
    return robot_prim_path


def _configure_joints(stage, robot_prim_path: str):
    """
    Configure joint limits and damping for all revolute joints.

    Iterates over all prims under the robot and applies the joint
    configurations defined in JOINT_CONFIGS.
    """
    from pxr import UsdPhysics, PhysxSchema

    joint_config_map = {jc.name: jc for jc in JOINT_CONFIGS}
    configured_joints = set()

    # Traverse all prims under the robot to find joints
    robot_prim = stage.GetPrimAtPath(robot_prim_path)
    for prim in robot_prim.GetDescendants():
        if prim.HasAPI(UsdPhysics.RevoluteJoint):
            joint_api = UsdPhysics.RevoluteJoint(prim)
            prim_name = prim.GetName()

            # Match prim to our joint config by name
            matched_config = None
            for jname, jconfig in joint_config_map.items():
                if jname in prim_name:
                    matched_config = jconfig
                    break

            if matched_config is not None:
                # Set joint limits (URDF values are in radians, USD uses degrees
                # for revolute joints)
                import math

                lower_deg = math.degrees(matched_config.lower_limit)
                upper_deg = math.degrees(matched_config.upper_limit)
                joint_api.CreateLowerLimitAttr(lower_deg)
                joint_api.CreateUpperLimitAttr(upper_deg)

                # Set damping via PhysX joint API
                if prim.HasAPI(PhysxSchema.PhysxJointAPI):
                    physx_joint = PhysxSchema.PhysxJointAPI(prim)
                else:
                    physx_joint = PhysxSchema.PhysxJointAPI.Apply(prim)

                # Configure drive for position control with damping
                drive_api = UsdPhysics.DriveAPI.Get(prim, "angular")
                if not drive_api:
                    drive_api = UsdPhysics.DriveAPI.Apply(prim, "angular")
                drive_api.CreateDampingAttr(matched_config.damping)
                drive_api.CreateStiffnessAttr(matched_config.effort)

                configured_joints.add(matched_config.name)
                print(
                    f"  Joint '{matched_config.name}': "
                    f"limits=[{matched_config.lower_limit:.4f}, "
                    f"{matched_config.upper_limit:.4f}] rad, "
                    f"damping={matched_config.damping} Ns/m"
                )

    # Verify all joints were configured
    missing_joints = set(joint_config_map.keys()) - configured_joints
    if missing_joints:
        print(
            f"WARNING: The following joints were not found in the imported model: "
            f"{missing_joints}",
            file=sys.stderr,
        )


def _configure_link_physics(stage, robot_prim_path: str):
    """
    Configure mass and inertia tensor properties for each link.

    Uses the values extracted from the URDF inertial elements.
    """
    from pxr import UsdPhysics, PhysxSchema, Gf

    link_config_map = {lc.name: lc for lc in LINK_CONFIGS}
    configured_links = set()

    robot_prim = stage.GetPrimAtPath(robot_prim_path)
    for prim in robot_prim.GetDescendants():
        if prim.HasAPI(UsdPhysics.MassAPI):
            prim_name = prim.GetName()

            matched_config = None
            for lname, lconfig in link_config_map.items():
                if lname in prim_name:
                    matched_config = lconfig
                    break

            if matched_config is not None:
                mass_api = UsdPhysics.MassAPI(prim)
                inertial = matched_config.inertial

                # Set mass
                mass_api.CreateMassAttr(inertial.mass)

                # Set center of mass
                mass_api.CreateCenterOfMassAttr(
                    Gf.Vec3f(
                        float(inertial.origin_xyz[0]),
                        float(inertial.origin_xyz[1]),
                        float(inertial.origin_xyz[2]),
                    )
                )

                # Set diagonal inertia (principal moments)
                mass_api.CreateDiagonalInertiaAttr(
                    Gf.Vec3f(
                        float(inertial.ixx),
                        float(inertial.iyy),
                        float(inertial.izz),
                    )
                )

                configured_links.add(matched_config.name)

    print(f"  Configured physics for {len(configured_links)} links.")


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------


def main():
    """
    Main entry point for the Isaac Sim standalone robot loading script.

    Workflow:
    1. Validate all required files exist (URDF + 7 STL meshes)
    2. Start Isaac Sim application
    3. Configure physics scene (60 Hz)
    4. Add ground plane and directional light
    5. Import robot URDF with physics properties
    6. Keep simulation running (or return app for external control)
    """
    print("=" * 60)
    print("SO-100 5-DOF Arm — Isaac Sim Robot Loader")
    print("=" * 60)

    # Step 1: Validate required files before starting Isaac Sim
    # This prevents wasting time loading Isaac Sim only to fail on missing files.
    validate_required_files(WORKSPACE_ROOT)

    # Step 2: Start Isaac Sim
    simulation_app = setup_isaac_sim()

    try:
        # Now that Isaac Sim is running, we can import omni modules
        from omni.isaac.core import World

        # Step 3: Create the simulation world
        world = World(
            stage_units_in_meters=1.0,
            physics_dt=1.0 / PHYSICS_STEP_RATE_HZ,
            rendering_dt=1.0 / PHYSICS_STEP_RATE_HZ,
        )

        # Step 4: Configure physics scene
        configure_physics_scene()

        # Step 5: Add environment elements
        add_ground_plane()
        add_directional_light()

        # Step 6: Import the robot
        robot_prim_path = import_robot_urdf(WORKSPACE_ROOT)

        # Reset the world to initialize physics
        world.reset()

        print("=" * 60)
        print("Robot loaded successfully. Simulation ready.")
        print(f"  Physics rate: {PHYSICS_STEP_RATE_HZ} Hz")
        print(f"  Robot prim: {robot_prim_path}")
        print(f"  Joints: {len(JOINT_CONFIGS)}")
        print(f"  Links: {len(LINK_CONFIGS)}")
        print("=" * 60)

        # Keep simulation running until user closes
        while simulation_app.is_running():
            world.step(render=True)

    except Exception as e:
        print(f"ERROR: Unexpected error during scene setup: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
    finally:
        simulation_app.close()
        print("Isaac Sim application closed.")


if __name__ == "__main__":
    main()
