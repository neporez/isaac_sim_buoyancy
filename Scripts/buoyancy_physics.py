"""
부력 물리 계산 엔진
"""
import sys
import os

# 현재 모듈의 디렉토리 찾기
try:
    module_dir = os.path.dirname(os.path.abspath(__file__))
except:
    module_dir = os.getcwd()

if module_dir not in sys.path:
    sys.path.insert(0, module_dir)

import omni.usd
from pxr import UsdGeom, Gf, Usd, UsdPhysics, PhysxSchema
from wave_mesh import WaveMesh


class BuoyancyPhysics:
    """부력 물리 계산"""
    
    @staticmethod
    def get_world_scale(prim):
        """물체의 월드 스케일 추출"""
        xform = UsdGeom.Xformable(prim)
        if not xform:
            return Gf.Vec3f(1, 1, 1)
        
        world_transform = xform.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        
        scale_x = Gf.Vec3f(world_transform[0][0], world_transform[0][1], world_transform[0][2]).GetLength()
        scale_y = Gf.Vec3f(world_transform[1][0], world_transform[1][1], world_transform[1][2]).GetLength()
        scale_z = Gf.Vec3f(world_transform[2][0], world_transform[2][1], world_transform[2][2]).GetLength()
        
        return Gf.Vec3f(scale_x, scale_y, scale_z)
    
    @staticmethod
    def add_physics_to_object(prim, mass):
        """물체에 물리 속성 추가"""
        # Rigid Body API
        if not prim.HasAPI(UsdPhysics.RigidBodyAPI):
            rigid_body = UsdPhysics.RigidBodyAPI.Apply(prim)
            rigid_body.CreateRigidBodyEnabledAttr(True)
        
        # PhysX Rigid Body API
        if not prim.HasAPI(PhysxSchema.PhysxRigidBodyAPI):
            physx_rigid = PhysxSchema.PhysxRigidBodyAPI.Apply(prim)
            physx_rigid.CreateLinearDampingAttr(0.1)
            physx_rigid.CreateAngularDampingAttr(0.5)
            physx_rigid.CreateSleepThresholdAttr(0.0)
        else:
            physx_rigid = PhysxSchema.PhysxRigidBodyAPI(prim)
            physx_rigid.GetLinearDampingAttr().Set(0.1)
            physx_rigid.GetAngularDampingAttr().Set(0.5)
        
        # Mass API
        if not prim.HasAPI(UsdPhysics.MassAPI):
            mass_api = UsdPhysics.MassAPI.Apply(prim)
            mass_api.CreateMassAttr().Set(mass)
        else:
            mass_api = UsdPhysics.MassAPI(prim)
            mass_api.GetMassAttr().Set(mass)
        
        # Collision API
        if not prim.HasAPI(UsdPhysics.CollisionAPI):
            UsdPhysics.CollisionAPI.Apply(prim)
        
        # Force API
        if not prim.HasAPI(PhysxSchema.PhysxForceAPI):
            force_api = PhysxSchema.PhysxForceAPI.Apply(prim)
            force_api.CreateForceEnabledAttr().Set(True)
            force_api.CreateForceAttr().Set(Gf.Vec3f(0, 0, 0))
            force_api.CreateTorqueAttr().Set(Gf.Vec3f(0, 0, 0))
            force_api.CreateModeAttr().Set("Force")
    
    @staticmethod
    def apply_buoyancy_force(stage, buoyant_obj, time, amp, wlen, spd, steep, num_waves, debug_mode):
        """단일 물체에 부력 적용"""
        prim = stage.GetPrimAtPath(buoyant_obj.prim_path)
        if not prim or not prim.IsValid():
            return False
        
        # 물체 위치 및 크기
        xform = UsdGeom.Xformable(prim)
        world_transform = xform.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        obj_pos = world_transform.ExtractTranslation()
        
        bbox_cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ['default'])
        bbox = bbox_cache.ComputeLocalBound(prim)
        
        if not bbox:
            return False
        
        bbox_range = bbox.GetRange()
        min_pt = bbox_range.GetMin()
        max_pt = bbox_range.GetMax()
        
        scale = BuoyancyPhysics.get_world_scale(prim)
        
        size = Gf.Vec3f(
            (max_pt[0] - min_pt[0]) * scale[0],
            (max_pt[1] - min_pt[1]) * scale[1],
            (max_pt[2] - min_pt[2]) * scale[2]
        )
        
        total_volume = abs(size[0] * size[1] * size[2])
        
        # 샘플 포인트 개수를 scale에 비례해서 동적 조정
        # 각 축의 크기에 비례하되, 최소 3개, 최대 10개로 제한
        base_samples = 3  # 최소 샘플 개수
        max_samples = 10  # 최대 샘플 개수
        sample_density = 0.5  # 1m당 샘플 개수 (조정 가능)
        
        num_samples_x = max(base_samples, min(max_samples, int(size[0] * sample_density) + base_samples))
        num_samples_y = max(base_samples, min(max_samples, int(size[1] * sample_density) + base_samples))
        num_samples_z = max(base_samples, min(max_samples, int(size[2] * sample_density) + base_samples))
        
        # 디버그 출력
        if debug_mode:
            print(f"\nSample grid for {buoyant_obj.prim_path}:")
            print(f"  Size: {size[0]:.2f} x {size[1]:.2f} x {size[2]:.2f} m")
            print(f"  Sample points: {num_samples_x} x {num_samples_y} x {num_samples_z} = {num_samples_x * num_samples_y * num_samples_z}")
        
        sample_points_local = []
        
        for i in range(num_samples_x):
            for j in range(num_samples_y):
                for k in range(num_samples_z):
                    t_x = i / (num_samples_x - 1) if num_samples_x > 1 else 0.5
                    t_y = j / (num_samples_y - 1) if num_samples_y > 1 else 0.5
                    t_z = k / (num_samples_z - 1) if num_samples_z > 1 else 0.5
                    
                    local_x = min_pt[0] + (max_pt[0] - min_pt[0]) * t_x
                    local_y = min_pt[1] + (max_pt[1] - min_pt[1]) * t_y
                    local_z = min_pt[2] + (max_pt[2] - min_pt[2]) * t_z
                    
                    sample_points_local.append(Gf.Vec3d(local_x, local_y, local_z))
        
        # 잠긴 깊이 계산
        submerged_depths = []
        submerged_positions = []
        
        for local_pt in sample_points_local:
            world_pt = world_transform.Transform(local_pt)
            
            water_height = WaveMesh.get_water_height_at_position(
                world_pt[0], world_pt[1], time,
                amp, wlen, spd, steep, num_waves
            )
            
            depth = water_height - world_pt[2]
            
            if depth > 0:
                submerged_depths.append(depth)
                submerged_positions.append(Gf.Vec3f(world_pt[0], world_pt[1], world_pt[2]))
        
        if len(submerged_depths) == 0:
            force_api = PhysxSchema.PhysxForceAPI(prim)
            if force_api:
                force_api.GetForceAttr().Set(Gf.Vec3f(0, 0, 0))
                force_api.GetTorqueAttr().Set(Gf.Vec3f(0, 0, 0))
            return True
        
        # 부력 계산
        submerged_ratio = len(submerged_depths) / len(sample_points_local)
        submerged_volume = total_volume * submerged_ratio
        
        buoyancy_center = Gf.Vec3f(0, 0, 0)
        for pos in submerged_positions:
            buoyancy_center += pos
        buoyancy_center /= len(submerged_positions)
        
        buoyancy_magnitude = buoyant_obj.water_density * submerged_volume * buoyant_obj.gravity
        buoyancy_force = Gf.Vec3f(0, 0, buoyancy_magnitude)
        
        # 속도 및 항력
        rigid_body_api = UsdPhysics.RigidBodyAPI(prim)
        velocity_attr = rigid_body_api.GetVelocityAttr()
        angular_velocity_attr = rigid_body_api.GetAngularVelocityAttr()
        
        current_velocity = velocity_attr.Get() if velocity_attr else Gf.Vec3f(0, 0, 0)
        current_angular_velocity = angular_velocity_attr.Get() if angular_velocity_attr else Gf.Vec3f(0, 0, 0)
        
        drag_force = Gf.Vec3f(0, 0, 0)
        if current_velocity.GetLength() > 0.01:
            v_mag = current_velocity.GetLength()
            v_dir = current_velocity.GetNormalized()
            
            reference_area = (submerged_volume ** (2.0/3.0))
            drag_magnitude = 0.5 * buoyant_obj.water_density * (v_mag ** 2) * buoyant_obj.drag_coefficient * reference_area
            drag_force = -v_dir * drag_magnitude
        
        total_force = buoyancy_force + drag_force
        
        # 토크
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
        
        angular_drag_torque = Gf.Vec3f(0, 0, 0)
        if current_angular_velocity.GetLength() > 0.01:
            omega_mag = current_angular_velocity.GetLength()
            omega_dir = current_angular_velocity.GetNormalized()
            
            angular_drag_magnitude = buoyant_obj.angular_drag_coefficient * omega_mag * submerged_volume
            angular_drag_torque = -omega_dir * angular_drag_magnitude
        
        total_torque = buoyancy_torque + angular_drag_torque
        
        # 적용
        force_api = PhysxSchema.PhysxForceAPI(prim)
        if force_api:
            force_api.GetForceAttr().Set(total_force)
            force_api.GetTorqueAttr().Set(total_torque)
        
        return True