"""
부력 물리 계산 엔진 (포인트 클라우드 기반)
- 미리 수집된 샘플 포인트를 사용하여 효율적인 부력 계산
- 최상위 RigidBody에 힘과 토크 적용
"""
import sys
import os

try:
    module_dir = os.path.dirname(os.path.abspath(__file__))
except:
    module_dir = os.getcwd()

if module_dir not in sys.path:
    sys.path.insert(0, module_dir)

from pxr import UsdGeom, Gf, Usd, UsdPhysics, PhysxSchema
from wave_mesh import WaveMesh

class BuoyancyPhysics:
    """부력 물리 계산 (포인트 클라우드 기반)"""

    @staticmethod
    def setup_rigidbody(stage, prim_path):
        """
        최상위 prim에 RigidBody 설정
        하위 콜라이더들의 mass를 자동으로 합산

        Args:
            stage: USD stage
            prim_path: 최상위 prim 경로
        """
        prim = stage.GetPrimAtPath(prim_path)
        if not prim or not prim.IsValid():
            print(f"Error: Prim not found at {prim_path}")
            return False

        # RigidBody API (최상위에만)
        if not prim.HasAPI(UsdPhysics.RigidBodyAPI):
            rigid_body = UsdPhysics.RigidBodyAPI.Apply(prim)
            rigid_body.CreateRigidBodyEnabledAttr(True)

        # PhysX RigidBody API
        if not prim.HasAPI(PhysxSchema.PhysxRigidBodyAPI):
            physx_rigid = PhysxSchema.PhysxRigidBodyAPI.Apply(prim)
            physx_rigid.CreateLinearDampingAttr(0.1)
            physx_rigid.CreateAngularDampingAttr(0.5)
            physx_rigid.CreateSleepThresholdAttr(0.0)

        # ForceAPI (부력 적용용)
        if not prim.HasAPI(PhysxSchema.PhysxForceAPI):
            force_api = PhysxSchema.PhysxForceAPI.Apply(prim)
            force_api.CreateForceEnabledAttr().Set(True)
            force_api.CreateForceAttr().Set(Gf.Vec3f(0, 0, 0))
            force_api.CreateTorqueAttr().Set(Gf.Vec3f(0, 0, 0))
            force_api.CreateModeAttr().Set("force")
            force_api.CreateWorldFrameEnabledAttr().Set(True)

        print(f"RigidBody setup complete: {prim_path}")
        return True

    @staticmethod
    def apply_buoyancy_force(stage, buoyant_obj, wave_mesh_path, time,
                              amp, wlen, spd, steep, num_waves, debug_mode=False):
        """
        포인트 클라우드 기반 부력 적용

        Args:
            stage: USD stage
            buoyant_obj: BuoyantObject 인스턴스
            wave_mesh_path: 파도 메시 경로
            time: 현재 시간
            amp, wlen, spd, steep, num_waves: 파도 파라미터
            debug_mode: 디버그 출력 여부
        """
        if not buoyant_obj.is_initialized:
            print(f"Warning: {buoyant_obj.prim_path} not initialized")
            return False

        prim = stage.GetPrimAtPath(buoyant_obj.prim_path)
        if not prim or not prim.IsValid():
            return False

        # Wave mesh 위치
        wave_mesh_prim = stage.GetPrimAtPath(wave_mesh_path)
        if not wave_mesh_prim or not wave_mesh_prim.IsValid():
            return False

        wave_mesh_xform = UsdGeom.Xformable(wave_mesh_prim)
        wave_mesh_transform = wave_mesh_xform.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        wave_mesh_pos = wave_mesh_transform.ExtractTranslation()

        # 무게 중심 구하기
        xform = UsdGeom.Xformable(prim)
        world_transform = xform.ComputeLocalToWorldTransform(Usd.TimeCode.Default())

        com_local_vec = Gf.Vec3d(buoyant_obj.local_com)
        world_com_pos = world_transform.Transform(com_local_vec)

        obj_pos = Gf.Vec3f(world_com_pos[0], world_com_pos[1], world_com_pos[2])

        # 로컬 포인트를 월드 좌표로 변환
        world_points = buoyant_obj.get_world_sample_points(world_transform)

        if len(world_points) == 0:
            return True

        # 잠긴 포인트 계산
        submerged_points = []
        submerged_depths = []

        for world_pt in world_points:
            water_height = WaveMesh.get_water_height_at_position(
                world_pt[0], world_pt[1], time,
                amp, wlen, spd, steep, num_waves, wave_mesh_pos
            )

            depth = water_height - world_pt[2]
            if depth > 0:
                submerged_points.append(world_pt)
                submerged_depths.append(depth)

        submerged_ratio = len(submerged_points) / len(world_points)

        # Damping 업데이트
        BuoyancyPhysics._update_damping(prim, submerged_ratio)

        # 물 밖이면 힘 0
        if len(submerged_points) == 0:
            force_api = PhysxSchema.PhysxForceAPI(prim)
            if force_api:
                force_api.GetForceAttr().Set(Gf.Vec3f(0, 0, 0))
                force_api.GetTorqueAttr().Set(Gf.Vec3f(0, 0, 0))
            return True

        # 부력 계산
        submerged_volume = len(submerged_points) * buoyant_obj.point_volume
        buoyancy_magnitude = buoyant_obj.water_density * submerged_volume * buoyant_obj.gravity
        buoyancy_force = Gf.Vec3f(0, 0, buoyancy_magnitude)

        # 부력 중심 계산
        buoyancy_center = Gf.Vec3f(0, 0, 0)
        for pt in submerged_points:
            buoyancy_center += pt
        buoyancy_center /= len(submerged_points)

        # 항력 계산
        drag_force = BuoyancyPhysics._calculate_drag_force(
            prim, buoyant_obj, submerged_volume
        )

        total_force = buoyancy_force + drag_force

        # 토크 계산 (부력 중심 - 질량 중심)
        r = Gf.Vec3f(
            buoyancy_center[0] - obj_pos[0],
            buoyancy_center[1] - obj_pos[1],
            buoyancy_center[2] - obj_pos[2]
        )

        buoyancy_torque = Gf.Vec3f(
            r[1] * buoyancy_force[2] - r[2] * buoyancy_force[1],
            r[2] * buoyancy_force[0] - r[0] * buoyancy_force[2],
            r[0] * buoyancy_force[1] - r[1] * buoyancy_force[0]
        )

        angular_drag_torque = BuoyancyPhysics._calculate_angular_drag(
            prim, buoyant_obj, submerged_volume
        )

        total_torque = buoyancy_torque + angular_drag_torque

        # 힘 적용 (월드 좌표계)
        force_api = PhysxSchema.PhysxForceAPI(prim)
        if force_api:
            force_api.GetWorldFrameEnabledAttr().Set(True)
            force_api.GetForceAttr().Set(total_force)
            force_api.GetTorqueAttr().Set(total_torque)

        # 처음 10프레임 디버그 출력
        if not hasattr(buoyant_obj, '_debug_count'):
            buoyant_obj._debug_count = 0
        buoyant_obj._debug_count += 1

        if debug_mode or buoyant_obj._debug_count <= 10:
            weight = buoyant_obj.total_mass * buoyant_obj.gravity
            print(f"\n=== BUOYANCY DEBUG [{buoyant_obj._debug_count}]: {buoyant_obj.prim_path} ===")
            print(f"  CoM local: ({com_local_vec[0]:.2f}, {com_local_vec[1]:.2f}, {com_local_vec[2]:.2f})")
            print(f"  CoM world: ({obj_pos[0]:.2f}, {obj_pos[1]:.2f}, {obj_pos[2]:.2f})")
            print(f"  Buoyancy center: ({buoyancy_center[0]:.2f}, {buoyancy_center[1]:.2f}, {buoyancy_center[2]:.2f})")
            print(f"  Submerged: {len(submerged_points)}/{len(world_points)} ({submerged_ratio:.1%})")
            print(f"  Weight: {weight:.1f} N, Buoyancy: {buoyancy_magnitude:.1f} N (ratio: {buoyancy_magnitude/weight:.2f})")
            print(f"  Total force: ({total_force[0]:.1f}, {total_force[1]:.1f}, {total_force[2]:.1f}) N")
            print(f"  Total torque: ({total_torque[0]:.1f}, {total_torque[1]:.1f}, {total_torque[2]:.1f}) Nm")
            print(f"===========================================")

        return True

    @staticmethod
    def _update_damping(prim, submerged_ratio):
        """잠긴 비율에 따른 damping 업데이트"""
        physx_rigid = PhysxSchema.PhysxRigidBodyAPI(prim)
        if not physx_rigid:
            return

        # 공기 중 vs 물 속 damping
        air_linear = 0.1
        air_angular = 0.5
        water_linear = 5.0
        water_angular = 10.0

        linear = air_linear + (water_linear - air_linear) * submerged_ratio
        angular = air_angular + (water_angular - air_angular) * submerged_ratio

        physx_rigid.GetLinearDampingAttr().Set(linear)
        physx_rigid.GetAngularDampingAttr().Set(angular)

    @staticmethod
    def _calculate_drag_force(prim, buoyant_obj, submerged_volume):
        """속도 기반 항력 계산"""
        rigid_body_api = UsdPhysics.RigidBodyAPI(prim)
        if not rigid_body_api:
            return Gf.Vec3f(0, 0, 0)

        velocity_attr = rigid_body_api.GetVelocityAttr()
        current_velocity = velocity_attr.Get() if velocity_attr else Gf.Vec3f(0, 0, 0)

        if current_velocity.GetLength() < 0.01:
            return Gf.Vec3f(0, 0, 0)

        v_mag = current_velocity.GetLength()
        v_dir = current_velocity.GetNormalized()

        reference_area = submerged_volume ** (2.0 / 3.0)
        drag_magnitude = 0.1 * buoyant_obj.water_density * (v_mag ** 2) * \
                         buoyant_obj.drag_coefficient * reference_area

        return -v_dir * drag_magnitude

    @staticmethod
    def _calculate_angular_drag(prim, buoyant_obj, submerged_volume):
        """각속도 기반 회전 항력 계산"""
        rigid_body_api = UsdPhysics.RigidBodyAPI(prim)
        if not rigid_body_api:
            return Gf.Vec3f(0, 0, 0)

        angular_velocity_attr = rigid_body_api.GetAngularVelocityAttr()
        current_angular = angular_velocity_attr.Get() if angular_velocity_attr else Gf.Vec3f(0, 0, 0)

        if current_angular.GetLength() < 0.01:
            return Gf.Vec3f(0, 0, 0)

        omega_mag = current_angular.GetLength()
        omega_dir = current_angular.GetNormalized()

        angular_drag_magnitude = 0.5 * buoyant_obj.angular_drag_coefficient * \
                                  omega_mag * submerged_volume

        return -omega_dir * angular_drag_magnitude
