"""
부력을 받는 물체 클래스 (Raycast 기반 포인트 클라우드 시스템)
- 초기화 시 콜라이더 내부 포인트만 저장
- 런타임에는 좌표 변환만 수행하여 효율적
"""
from pxr import UsdGeom, Gf, Usd, UsdPhysics, PhysxSchema

try:
    from omni.physx import get_physx_scene_query_interface
    HAS_PHYSX_QUERY = True
except ImportError:
    HAS_PHYSX_QUERY = False
    print("Warning: omni.physx query interface not available")


class BuoyantObject:
    """부력을 받는 물체 (복합 메시 지원)"""

    def __init__(self, prim_path):
        self.prim_path = prim_path  # 최상위 RigidBody prim
        self.is_active = True
        self.is_initialized = False

        # 포인트 클라우드 (로컬 좌표)
        self.sample_points_local = []  # [(x, y, z), ...]
        self.point_volume = 0.0  # 각 포인트가 대표하는 부피
        self.total_volume = 0.0
        self.total_mass = 0.0

        # 물리 상수
        self.water_density = 1000.0  # kg/m^3
        self.gravity = 9.81  # m/s^2
        self.drag_coefficient = 1.0
        self.angular_drag_coefficient = 1.0

        self.local_com = Gf.Vec3d(0, 0, 0)  # 최상위 노드 기준의 로컬 무게중심
        self.total_mass = 0.0

        print(f"BuoyantObject created: {prim_path}")
        print(f"  Call initialize_sample_points() after simulation starts")

    def initialize_sample_points(self, stage, grid_resolution=0.2):
        """
        시뮬레이션 시작 시 호출 - 콜라이더 내부 포인트 수집

        Args:
            stage: USD stage
            grid_resolution: 샘플 포인트 간격 (m)
        """
        if not HAS_PHYSX_QUERY:
            print("Error: PhysX query interface not available")
            return False

        prim = stage.GetPrimAtPath(self.prim_path)
        if not prim or not prim.IsValid():
            print(f"Error: Prim not found at {self.prim_path}")
            return False

        # 최상위 prim의 월드 변환
        xform = UsdGeom.Xformable(prim)
        world_transform = xform.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        world_to_local = world_transform.GetInverse()

        # 전체 bounding box 계산 (하위 포함)
        bbox_cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ['default'])
        world_bbox = bbox_cache.ComputeWorldBound(prim)

        if not world_bbox:
            print(f"Error: Could not compute bounding box for {self.prim_path}")
            return False

        bbox_range = world_bbox.ComputeAlignedRange()
        min_pt = bbox_range.GetMin()
        max_pt = bbox_range.GetMax()

        size_x = max_pt[0] - min_pt[0]
        size_y = max_pt[1] - min_pt[1]
        size_z = max_pt[2] - min_pt[2]

        # 그리드 샘플 수 계산
        num_x = max(3, int(size_x / grid_resolution) + 1)
        num_y = max(3, int(size_y / grid_resolution) + 1)
        num_z = max(3, int(size_z / grid_resolution) + 1)

        total_grid_points = num_x * num_y * num_z
        grid_volume = size_x * size_y * size_z
        volume_per_point = grid_volume / total_grid_points

        print(f"Initializing sample points for {self.prim_path}:")
        print(f"  World bbox: ({size_x:.2f} x {size_y:.2f} x {size_z:.2f}) m")
        print(f"  Grid: {num_x} x {num_y} x {num_z} = {total_grid_points} points")

        # 하위 콜라이더 경로 수집
        collider_paths = self._collect_collider_paths(stage, prim)
        print(f"  Colliders found: {len(collider_paths)}")

        if len(collider_paths) == 0:
            print("  Warning: No colliders found, using bounding box")

        # 질량 계산 (하위 MassAPI 합산)
        self.total_mass, self.local_com = self._calculate_mass_and_com(stage, prim)
        print(f"  Total mass: {self.total_mass:.2f} kg")

        # Raycast로 내부 포인트 검사
        query_interface = get_physx_scene_query_interface()
        inside_points = []

        for i in range(num_x):
            for j in range(num_y):
                for k in range(num_z):
                    # 그리드 포인트 (월드 좌표)
                    t_x = i / (num_x - 1) if num_x > 1 else 0.5
                    t_y = j / (num_y - 1) if num_y > 1 else 0.5
                    t_z = k / (num_z - 1) if num_z > 1 else 0.5

                    world_x = min_pt[0] + size_x * t_x
                    world_y = min_pt[1] + size_y * t_y
                    world_z = min_pt[2] + size_z * t_z

                    origin = Gf.Vec3f(world_x, world_y, world_z)

                    # Raycast로 내부 판정
                    if self._is_point_inside(query_interface, origin, collider_paths, self.prim_path):
                        # 월드 좌표를 로컬 좌표로 변환
                        local_pt = world_to_local.Transform(Gf.Vec3d(world_x, world_y, world_z))
                        inside_points.append((local_pt[0], local_pt[1], local_pt[2]))

        self.sample_points_local = inside_points

        # 포인트 볼륨 계산: 내부 포인트 기준으로 재계산
        # 각 포인트가 대표하는 부피 = 물체 실제 부피 / 내부 포인트 수
        # 실제 부피 추정: (내부 포인트 수 / 전체 그리드 수) * 바운딩 박스 부피
        if len(inside_points) > 0:
            estimated_volume = (len(inside_points) / total_grid_points) * grid_volume
            self.point_volume = estimated_volume / len(inside_points)
            self.total_volume = estimated_volume
        else:
            self.point_volume = 0.0
            self.total_volume = 0.0

        self.is_initialized = True

        print(f"  Inside points: {len(inside_points)} / {total_grid_points}")
        print(f"  Estimated volume: {self.total_volume:.4f} m^3")
        print(f"  Point volume: {self.point_volume:.6f} m^3/point")

        return True

    def _collect_collider_paths(self, stage, root_prim):
        """하위 prim 중 CollisionAPI가 있는 것들의 경로 수집"""
        collider_paths = []

        def traverse(prim):
            if prim.HasAPI(UsdPhysics.CollisionAPI):
                collider_paths.append(str(prim.GetPath()))
            for child in prim.GetChildren():
                traverse(child)

        traverse(root_prim)
        return collider_paths

    def _calculate_mass_and_com(self, stage, root_prim):
        """
        하위 prim들의 mass와 위치를 이용해 전체 질량 및 무게중심 계산
        Returns: (total_mass, local_com)
        """
        total_mass = 0.0
        weighted_pos_sum = Gf.Vec3d(0, 0, 0)
        
        # 최상위 노드의 월드 변환 행렬 (하위 노드들의 상대 좌표 계산용)
        root_xform = UsdGeom.Xformable(root_prim)
        root_world_transform = root_xform.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        world_to_root = root_world_transform.GetInverse()

        def traverse(prim):
            nonlocal total_mass, weighted_pos_sum
            if prim.HasAPI(UsdPhysics.MassAPI):
                mass_api = UsdPhysics.MassAPI(prim)
                mass = mass_api.GetMassAttr().Get()
                
                if mass and mass > 0:
                    # 해당 파츠의 월드 위치 가져오기
                    part_xform = UsdGeom.Xformable(prim)
                    part_world_transform = part_xform.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
                    part_world_pos = part_world_transform.ExtractTranslation()
                    
                    # 월드 위치를 Root 기준의 로컬 위치로 변환
                    local_pos = world_to_root.Transform(part_world_pos)
                    
                    # 질량 가중치 적용
                    total_mass += mass
                    weighted_pos_sum += local_pos * mass
            
            for child in prim.GetChildren():
                traverse(child)

        traverse(root_prim)

        if total_mass <= 0:
            return 1.0, Gf.Vec3d(0, 0, 0)

        # 최종 무게중심 = (Σ mass * pos) / Σ mass
        final_com = weighted_pos_sum / total_mass
        return total_mass, final_com

    def _is_point_inside(self, query_interface, origin, collider_paths, root_path):
        """
        Raycast로 포인트가 콜라이더 내부인지 판정
        홀수 번 hit = 내부

        Args:
            query_interface: PhysX scene query interface
            origin: raycast 시작점 (world coordinates)
            collider_paths: 콜라이더 경로 목록
            root_path: 최상위 RigidBody prim 경로
        """
        if len(collider_paths) == 0:
            # 콜라이더가 없으면 bbox 내부는 모두 포함
            return True

        hit_count = 0

        def report_hit(hit):
            nonlocal hit_count
            # hit.rigid_body는 RigidBody가 부착된 최상위 prim 경로를 반환
            # 우리의 최상위 prim과 일치하는지 확인
            if hit.rigid_body == root_path:
                hit_count += 1
            return True

        # Z+ 방향으로 raycast
        query_interface.raycast_all(origin, Gf.Vec3f(0, 0, 1), 100000.0, report_hit)

        return (hit_count % 2 == 1)

    def get_world_sample_points(self, world_transform):
        """
        저장된 로컬 포인트들을 현재 월드 좌표로 변환

        Args:
            world_transform: 현재 프레임의 LocalToWorld 변환 행렬

        Returns:
            list of Gf.Vec3f: 월드 좌표 포인트들
        """
        world_points = []
        for local_pt in self.sample_points_local:
            world_pt = world_transform.Transform(Gf.Vec3d(local_pt[0], local_pt[1], local_pt[2]))
            world_points.append(Gf.Vec3f(world_pt[0], world_pt[1], world_pt[2]))
        return world_points
