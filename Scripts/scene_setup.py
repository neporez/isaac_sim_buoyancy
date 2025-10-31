"""
물리 씬, 조명, 물탱크 설정 관리
"""
import omni.usd
from pxr import UsdGeom, Gf, Sdf, UsdPhysics, UsdShade, UsdLux


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
    
    @staticmethod
    def create_water_tank(stage, tank_path, size=20.0):
        """물 탱크 생성 (4면 벽 + 바닥)"""
        # 기존 탱크 제거
        if stage.GetPrimAtPath(tank_path):
            stage.RemovePrim(tank_path)
        
        # 탱크 그룹 생성
        UsdGeom.Xform.Define(stage, tank_path)
        
        wall_thickness = 0.5
        wall_height = 5.0
        
        # 파란색 재질 생성
        tank_material_path = "/World/Looks/TankMaterial"
        tank_material = UsdShade.Material.Define(stage, tank_material_path)
        
        tank_shader = UsdShade.Shader.Define(stage, tank_material_path + "/Shader")
        tank_shader.CreateIdAttr("UsdPreviewSurface")
        tank_shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set((0.1, 0.3, 0.8))
        tank_shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.1)
        tank_shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.4)
        
        tank_material.CreateSurfaceOutput().ConnectToSource(tank_shader.ConnectableAPI(), "surface")
        
        # 벽 정의
        walls = [
            ("Wall_North", 0, size/2, size + wall_thickness, wall_thickness, wall_height),
            ("Wall_South", 0, -size/2, size + wall_thickness, wall_thickness, wall_height),
            ("Wall_East", size/2, 0, wall_thickness, size + wall_thickness, wall_height),
            ("Wall_West", -size/2, 0, wall_thickness, size + wall_thickness, wall_height),
            ("Floor", 0, 0, size, size, wall_thickness)
        ]
        
        for wall_name, pos_x, pos_y, scale_x, scale_y, scale_z in walls:
            wall_path = f"{tank_path}/{wall_name}"
            cube = UsdGeom.Cube.Define(stage, wall_path)
            cube.CreateSizeAttr(1.0)
            
            xform_api = UsdGeom.XformCommonAPI(cube)
            xform_api.SetScale(Gf.Vec3f(scale_x, scale_y, scale_z))
            
            if wall_name == "Floor":
                xform_api.SetTranslate((pos_x, pos_y, -wall_height/2))
            else:
                xform_api.SetTranslate((pos_x, pos_y, 0))
            
            prim = cube.GetPrim()
            UsdPhysics.CollisionAPI.Apply(prim)
            
            if not prim.HasAPI(UsdPhysics.RigidBodyAPI):
                rigid_body = UsdPhysics.RigidBodyAPI.Apply(prim)
                rigid_body.CreateRigidBodyEnabledAttr(False)
            
            UsdShade.MaterialBindingAPI(prim).Bind(tank_material)
        
        print(f"Water tank created: {size}m x {size}m x {wall_height}m (Blue color)")