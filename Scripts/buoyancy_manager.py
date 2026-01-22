"""
Buoyancy Manager - 메인 컨트롤러 (Scripts2 버전)
- 포인트 클라우드 기반 부력 시스템
- 시뮬레이션 시작 시 초기화
"""
import omni
import omni.usd
import omni.kit.app
import omni.timeline
from pxr import UsdGeom, Gf, Usd

import sys
SCRIPTS_PATH = "/home/rain/isaac_sim_test/Scripts"
if SCRIPTS_PATH not in sys.path:
    sys.path.insert(0, SCRIPTS_PATH)

from buoyant_object import BuoyantObject
from scene_setup import SceneSetup
from wave_mesh import WaveMesh
from buoyancy_physics import BuoyancyPhysics
from buoyancy_ui import BuoyancyUI
from thruster_controller import ThrusterController


class BuoyancyManager:
    """부력 시뮬레이션 매니저 (포인트 클라우드 기반)"""

    def __init__(self):
        self.time = 0.0
        self.resolution = 20
        self.mesh_path = "/World/GerstnerWave"

        self.buoyant_objects = {}  # {prim_path: BuoyantObject}
        self.debug_mode = True

        # 초기화 상태
        self.is_playing = False
        self.needs_initialization = False

        self.grid_resolution = 0.2

        stage = omni.usd.get_context().get_stage()

        # 기존 오브젝트 제거
        if stage.GetPrimAtPath(self.mesh_path):
            stage.RemovePrim(self.mesh_path)

        # 씬 설정
        SceneSetup.setup_physics_scene(stage)
        WaveMesh.create_wave_mesh(stage, self.mesh_path, self.resolution)
        SceneSetup.setup_lighting(stage)

        # Thruster 컨트롤러 생성
        self.thruster_controller = ThrusterController(self)

        # UI 생성
        self.ui = BuoyancyUI(self)

        # 업데이트 구독
        self.sub = omni.kit.app.get_app().get_update_event_stream().create_subscription_to_pop(
            self.update
        )

        print("=" * 60)
        print("Buoyancy Manager (Point Cloud Based)")
        print("=" * 60)

    def add_buoyancy_to_object(self, prim_path):
        """
        물체에 부력 추가

        Args:
            prim_path: 최상위 prim 경로 (하위에 Collider + Mass 필요)
        """
        stage = omni.usd.get_context().get_stage()
        prim = stage.GetPrimAtPath(prim_path)

        if not prim or not prim.IsValid():
            print(f"Error: Object not found: {prim_path}")
            return False

        if prim_path in self.buoyant_objects:
            print(f"Warning: Object already registered: {prim_path}")
            return False

        # RigidBody 설정
        BuoyancyPhysics.setup_rigidbody(stage, prim_path)

        # BuoyantObject 생성
        buoyant_obj = BuoyantObject(prim_path)
        self.buoyant_objects[prim_path] = buoyant_obj

        # 시뮬레이션 중이면 즉시 초기화
        timeline = omni.timeline.get_timeline_interface()
        if timeline.is_playing():
            self.grid_resolution = self.ui.resolution_field.model.get_value_as_float()
            buoyant_obj.initialize_sample_points(stage,grid_resolution=self.grid_resolution)

        print(f"Buoyancy added: {prim_path}")
        print("  Note: Sample points will be initialized when simulation starts")

        return True

    def remove_buoyancy_from_object(self, prim_path):
        """물체에서 부력 제거"""
        if prim_path in self.buoyant_objects:
            del self.buoyant_objects[prim_path]
            print(f"Buoyancy removed: {prim_path}")
            return True
        return False

    def _initialize_all_objects(self, stage):
        """시뮬레이션 시작 시 모든 물체 초기화"""
        print("\n" + "=" * 40)
        print("Initializing buoyant objects...")
        print("=" * 40)

        for prim_path, buoyant_obj in self.buoyant_objects.items():
            if not buoyant_obj.is_initialized:
                self.grid_resolution = self.ui.resolution_field.model.get_value_as_float()
                buoyant_obj.initialize_sample_points(stage,grid_resolution=self.grid_resolution)

        print("=" * 40 + "\n")

    def rebuild_wave_mesh(self, stage):
        """Wave Mesh 재생성"""
        prim = stage.GetPrimAtPath(self.mesh_path)
        if not prim or not prim.IsValid():
            WaveMesh.create_wave_mesh(stage, self.mesh_path, self.resolution)
            return

        # 기존 속성 저장
        amp = prim.GetAttribute("wave:amplitude").Get()
        wlen = prim.GetAttribute("wave:wavelength").Get()
        spd = prim.GetAttribute("wave:speed").Get()
        steep = prim.GetAttribute("wave:steepness").Get()
        size = prim.GetAttribute("wave:size").Get()
        pause = prim.GetAttribute("wave:paused").Get()
        num_waves = prim.GetAttribute("wave:num_waves").Get()

        # 메시 재생성
        mesh = UsdGeom.Mesh.Get(stage, self.mesh_path)

        faces = []
        for i in range(self.resolution - 1):
            for j in range(self.resolution - 1):
                idx = i * self.resolution + j
                faces.extend([idx, idx + 1, idx + self.resolution + 1,
                              idx, idx + self.resolution + 1, idx + self.resolution])

        mesh.GetFaceVertexCountsAttr().Set([3] * (len(faces) // 3))
        mesh.GetFaceVertexIndicesAttr().Set(faces)

        # 속성 복원
        prim.GetAttribute("wave:amplitude").Set(amp)
        prim.GetAttribute("wave:wavelength").Set(wlen)
        prim.GetAttribute("wave:speed").Set(spd)
        prim.GetAttribute("wave:steepness").Set(steep)
        prim.GetAttribute("wave:size").Set(size)
        prim.GetAttribute("wave:paused").Set(pause)
        prim.GetAttribute("wave:num_waves").Set(num_waves)

        print(f"Wave mesh rebuilt with resolution: {self.resolution}")

    def enable_debug(self):
        """디버그 출력 활성화"""
        self.debug_mode = True
        print("\nDebug output enabled")

    def toggle_pause(self):
        """파도 일시정지/재개"""
        stage = omni.usd.get_context().get_stage()
        prim = stage.GetPrimAtPath(self.mesh_path)
        if prim:
            current = prim.GetAttribute("wave:paused").Get()
            prim.GetAttribute("wave:paused").Set(not current)

    def update(self, e):
        """매 프레임 업데이트"""
        try:
            stage = omni.usd.get_context().get_stage()
            prim = stage.GetPrimAtPath(self.mesh_path)

            if not prim or not prim.IsValid():
                return

            # Wave 속성
            amp = prim.GetAttribute("wave:amplitude").Get()
            wlen = prim.GetAttribute("wave:wavelength").Get()
            spd = prim.GetAttribute("wave:speed").Get()
            steep = prim.GetAttribute("wave:steepness").Get()
            size = prim.GetAttribute("wave:size").Get()
            pause = prim.GetAttribute("wave:paused").Get()
            num_waves = prim.GetAttribute("wave:num_waves").Get()

            if pause:
                return

            self.time += 1 / 60.0

            # Wave mesh 업데이트
            WaveMesh.update_wave_mesh(stage, self.mesh_path, self.resolution, self.time,
                                       amp, wlen, spd, steep, size, num_waves)

            # 시뮬레이션 상태 확인
            timeline = omni.timeline.get_timeline_interface()
            is_now_playing = timeline.is_playing()

            # 시뮬레이션 시작 감지 → 초기화
            if is_now_playing and not self.is_playing:
                self._initialize_all_objects(stage)

            self.is_playing = is_now_playing

            # 부력 적용
            if is_now_playing:
                for prim_path, buoyant_obj in list(self.buoyant_objects.items()):
                    if not buoyant_obj.is_active:
                        continue

                    if not buoyant_obj.is_initialized:
                        continue

                    success = BuoyancyPhysics.apply_buoyancy_force(
                        stage, buoyant_obj, self.mesh_path, self.time,
                        amp, wlen, spd, steep, num_waves,
                        self.debug_mode
                    )

                    if not success:
                        print(f"Object removed: {prim_path}")
                        del self.buoyant_objects[prim_path]

                # Thruster 업데이트
                self.thruster_controller.update(stage)

                # 디버그 모드 비활성화
                if self.debug_mode:
                    self.debug_mode = False

        except Exception as ex:
            import traceback
            print(f"Error in update: {ex}")
            traceback.print_exc()
