"""
Buoyancy Manager - 메인 컨트롤러
"""
import omni
import omni.usd
import omni.kit.app
import omni.timeline
from pxr import UsdGeom, Gf, Usd

import sys
SCRIPTS_PATH = "/home/rain/isaac_sim_test/Scripts"  # 실제 Scripts 폴더 경로
if SCRIPTS_PATH not in sys.path:
    sys.path.insert(0, SCRIPTS_PATH)


from buoyant_object import BuoyantObject
from scene_setup import SceneSetup
from wave_mesh import WaveMesh
from buoyancy_physics import BuoyancyPhysics
from buoyancy_ui import BuoyancyUI


class BuoyancyManager:
    """부력 시뮬레이션 매니저"""
    
    def __init__(self):
        self.time = 0.0
        self.resolution = 20
        self.mesh_path = "/World/GerstnerWave"
        self.tank_path = "/World/WaterTank"
        
        self.buoyant_objects = {}
        self.debug_mode = True
        
        stage = omni.usd.get_context().get_stage()
        
        # 기존 오브젝트 제거
        if stage.GetPrimAtPath(self.mesh_path):
            stage.RemovePrim(self.mesh_path)
        if stage.GetPrimAtPath(self.tank_path):
            stage.RemovePrim(self.tank_path)
        
        # 씬 설정
        SceneSetup.setup_physics_scene(stage)
        WaveMesh.create_wave_mesh(stage, self.mesh_path, self.resolution)
        SceneSetup.create_water_tank(stage, self.tank_path, 20.0)
        SceneSetup.setup_lighting(stage)
        
        # UI 생성
        self.ui = BuoyancyUI(self)
        
        # 업데이트 구독
        self.sub = omni.kit.app.get_app().get_update_event_stream().create_subscription_to_pop(
            self.update
        )
        
        print("="*60)
        print("Physics-Based Buoyancy Manager")
        print("="*60)
    
    def add_buoyancy_to_object(self, prim_path, material_density=50.0):
        """물체에 부력 추가"""
        stage = omni.usd.get_context().get_stage()
        prim = stage.GetPrimAtPath(prim_path)
        
        if not prim or not prim.IsValid():
            print(f"Object not found: {prim_path}")
            return False
        
        if prim_path in self.buoyant_objects:
            print(f"Object already has buoyancy: {prim_path}")
            return False
        
        buoyant_obj = BuoyantObject(prim_path, material_density)
        
        # 부피 계산
        bbox_cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ['default'])
        bbox = bbox_cache.ComputeLocalBound(prim)
        
        if bbox:
            bbox_range = bbox.GetRange()
            size = bbox_range.GetMax() - bbox_range.GetMin()
            
            scale = BuoyancyPhysics.get_world_scale(prim)
            size = Gf.Vec3f(size[0] * scale[0], size[1] * scale[1], size[2] * scale[2])
            
            volume = abs(size[0] * size[1] * size[2])
            mass = volume * material_density
            
            print(f"  Object size: {size[0]:.2f} x {size[1]:.2f} x {size[2]:.2f} m")
            print(f"  Volume: {volume:.4f} m^3")
            print(f"  Mass: {mass:.2f} kg")
            print(f"  Weight: {mass * 9.81:.2f} N")
            print(f"  Max buoyancy: {volume * 1000 * 9.81:.2f} N")
        else:
            volume = 1.0
            mass = material_density
            print("  Warning: Could not compute bounding box")
        
        # 물리 속성 추가
        BuoyancyPhysics.add_physics_to_object(prim, mass)
        
        self.buoyant_objects[prim_path] = buoyant_obj
        print(f"Buoyancy added successfully to: {prim_path}")
        
        return True
    
    def remove_buoyancy_from_object(self, prim_path):
        """물체에서 부력 제거"""
        if prim_path in self.buoyant_objects:
            del self.buoyant_objects[prim_path]
            print(f"Buoyancy removed from: {prim_path}")
            return True
        return False
    
    def update_water_tank_size(self, new_size):
        """탱크 크기 업데이트"""
        stage = omni.usd.get_context().get_stage()
        SceneSetup.create_water_tank(stage, self.tank_path, new_size)
        print(f"Water tank updated to size: {new_size}m")
    
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
                faces.extend([idx, idx+1, idx+self.resolution+1, idx, idx+self.resolution+1, idx+self.resolution])
        
        mesh.GetFaceVertexCountsAttr().Set([3] * (len(faces)//3))
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
        print("\nDebug output enabled - will show on next frame")
    
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
            
            # Wave 속성 가져오기
            amp = prim.GetAttribute("wave:amplitude").Get()
            wlen = prim.GetAttribute("wave:wavelength").Get()
            spd = prim.GetAttribute("wave:speed").Get()
            steep = prim.GetAttribute("wave:steepness").Get()
            size = prim.GetAttribute("wave:size").Get()
            pause = prim.GetAttribute("wave:paused").Get()
            num_waves = prim.GetAttribute("wave:num_waves").Get()
            
            if pause:
                return
            
            self.time += 1/60.0
            
            # Wave mesh 업데이트
            WaveMesh.update_wave_mesh(stage, self.mesh_path, self.resolution, self.time,
                                     amp, wlen, spd, steep, size, num_waves)
            
            # 부력 적용
            timeline = omni.timeline.get_timeline_interface()
            if timeline.is_playing():
                for prim_path, buoyant_obj in list(self.buoyant_objects.items()):
                    if not buoyant_obj.is_active:
                        continue
                    
                    success = BuoyancyPhysics.apply_buoyancy_force(
                        stage, buoyant_obj, self.time,
                        amp, wlen, spd, steep, num_waves,
                        self.debug_mode
                    )
                    
                    if not success:
                        print(f"Object removed from scene: {prim_path}")
                        del self.buoyant_objects[prim_path]
                
                # 디버그 모드 비활성화
                if self.debug_mode:
                    self.debug_mode = False
            
        except Exception as ex:
            import traceback
            print(f"Error in update: {ex}")
            traceback.print_exc()