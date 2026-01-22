"""
물리 씬, 조명 설정 관리
"""
import omni.usd
from pxr import UsdGeom, Gf, UsdPhysics, UsdLux


class SceneSetup:
    """씬 설정 관리"""
    
    @staticmethod
    def setup_physics_scene(stage):
        """Physics Scene 설정"""
        scene_path = "/World/PhysicsScene"
        if not stage.GetPrimAtPath(scene_path):
            scene = UsdPhysics.Scene.Define(stage, scene_path)
            scene.CreateGravityDirectionAttr().Set(Gf.Vec3f(0.0, 0.0, -1.0))
            scene.CreateGravityMagnitudeAttr().Set(9.81)
            print("Physics Scene created with gravity = 9.81 m/s^2")
    
    @staticmethod
    def setup_lighting(stage):
        """조명 설정"""
        # Distant Light (태양광)
        sun_light_path = "/World/SunLight"
        if stage.GetPrimAtPath(sun_light_path):
            stage.RemovePrim(sun_light_path)
        
        sun_light = UsdLux.DistantLight.Define(stage, sun_light_path)
        sun_light.CreateIntensityAttr(8000.0)
        sun_light.CreateAngleAttr(0.5)
        
        xform_api = UsdGeom.XformCommonAPI(sun_light)
        xform_api.SetRotate((45, 45, 0), UsdGeom.XformCommonAPI.RotationOrderXYZ)
        
        print("Lighting setup complete (Sun light only)")
    
