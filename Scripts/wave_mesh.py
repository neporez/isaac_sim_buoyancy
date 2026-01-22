"""
Gerstner Wave 메시 생성 및 업데이트
"""
import math
from pxr import UsdGeom, Gf, Sdf, UsdShade
import carb.settings

class WaveMesh:
    """Wave Mesh 관리"""
    
    @staticmethod
    def create_wave_mesh(stage, mesh_path, resolution):
        """Wave Mesh 생성"""
        mesh = UsdGeom.Mesh.Define(stage, mesh_path)
        prim = mesh.GetPrim()
        
        # Wave 속성
        prim.CreateAttribute("wave:amplitude", Sdf.ValueTypeNames.Float).Set(0.2)
        prim.CreateAttribute("wave:wavelength", Sdf.ValueTypeNames.Float).Set(4.0)
        prim.CreateAttribute("wave:speed", Sdf.ValueTypeNames.Float).Set(1.5)
        prim.CreateAttribute("wave:steepness", Sdf.ValueTypeNames.Float).Set(0.2)
        prim.CreateAttribute("wave:size", Sdf.ValueTypeNames.Float).Set(20.0)
        prim.CreateAttribute("wave:paused", Sdf.ValueTypeNames.Bool).Set(False)
        prim.CreateAttribute("wave:num_waves", Sdf.ValueTypeNames.Int).Set(2)
        
        # Mesh 생성
        faces = []
        for i in range(resolution - 1):
            for j in range(resolution - 1):
                idx = i * resolution + j
                faces.extend([idx, idx+1, idx+resolution+1, idx, idx+resolution+1, idx+resolution])
        
        mesh.GetFaceVertexCountsAttr().Set([3] * (len(faces)//3))
        mesh.GetFaceVertexIndicesAttr().Set(faces)
        
        # ============================================
        # Glass Material 적용 (Non-visual 속성 추가)
        # ============================================
        material_path = "/World/Looks/GlassMaterial"
        material = UsdShade.Material.Define(stage, material_path)
        
        # Shader 생성 (시각적 속성)
        shader = UsdShade.Shader.Define(stage, material_path + "/Shader")
        shader.CreateIdAttr("UsdPreviewSurface")
        shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set((0.9, 0.95, 1.0))
        shader.CreateInput("emissiveColor", Sdf.ValueTypeNames.Color3f).Set((0.0, 0.0, 0.0))
        shader.CreateInput("useSpecularWorkflow", Sdf.ValueTypeNames.Int).Set(0)
        shader.CreateInput("specularColor", Sdf.ValueTypeNames.Color3f).Set((0.0, 0.0, 0.0))
        shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
        shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.0)
        shader.CreateInput("clearcoat", Sdf.ValueTypeNames.Float).Set(0.0)
        shader.CreateInput("clearcoatRoughness", Sdf.ValueTypeNames.Float).Set(0.0)
        shader.CreateInput("opacity", Sdf.ValueTypeNames.Float).Set(0.05)
        shader.CreateInput("opacityThreshold", Sdf.ValueTypeNames.Float).Set(0.0)
        shader.CreateInput("ior", Sdf.ValueTypeNames.Float).Set(1.1)
        shader.CreateInput("normal", Sdf.ValueTypeNames.Normal3f).Set((0.0, 0.0, 0.0))
        shader.CreateInput("displacement", Sdf.ValueTypeNames.Float).Set(0.0)
        
        material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
        
        # ============================================
        # Non-visual Material 속성 추가 (LiDAR용)
        # ============================================
        # Prefix 확인
        settings = carb.settings.get_settings()
        prefix = settings.get("/rtx/materialDb/nonVisualMaterialSemantics/prefix")
        if prefix is None:
            prefix = "omni:simready:nonvisual"  # 기본값
        
        # Material Prim에 non-visual 속성 추가
        mat_prim = stage.GetPrimAtPath(material_path)
        
        # 물 + 투명 속성 설정
        mat_prim.CreateAttribute(f"{prefix}:base", 
                                Sdf.ValueTypeNames.String).Set("water")
        mat_prim.CreateAttribute(f"{prefix}:attributes", 
                                Sdf.ValueTypeNames.String).Set("visually_transparent")
        
        print(f"Wave mesh created with glass material (non-visual: water + visually_transparent)")
        # ============================================
        
        # Material 바인딩
        UsdShade.MaterialBindingAPI(prim).Bind(material)

        print("Wave mesh created with glass material")
    
    @staticmethod
    def gerstner_wave(x, y, time, amplitude, wavelength, speed, steepness, direction):
        """Gerstner Wave 계산"""
        k = 2 * math.pi / wavelength
        omega = speed * k
        dx, dy = direction
        phase = k * (dx * x + dy * y) - omega * time
        
        Q = steepness / (k * amplitude) if amplitude > 0 else 0
        offset_x = Q * amplitude * dx * math.cos(phase)
        offset_y = Q * amplitude * dy * math.cos(phase)
        offset_z = amplitude * math.sin(phase)
        
        return offset_x, offset_y, offset_z
    
    @staticmethod
    def get_water_height_at_position(x, y, time, amp, wlen, spd, steep, num_waves, wave_mesh_pos):
        """특정 위치의 수면 높이 계산 (wave mesh의 위치 반영)"""
        wave_directions = [
            (1.0, 0.0),
            (0.6, 0.8),
        ]

        # Wave mesh의 월드 위치를 기준으로 상대 좌표 계산
        relative_x = x - wave_mesh_pos[0]
        relative_y = y - wave_mesh_pos[1]

        total_offset_z = 0

        for wave_idx in range(num_waves):
            direction = wave_directions[wave_idx % len(wave_directions)]
            wave_amp = amp * (1.0 - wave_idx * 0.15)
            wave_wlen = wlen * (1.0 + wave_idx * 0.3)
            wave_spd = spd * (1.0 - wave_idx * 0.1)

            k = 2 * math.pi / wave_wlen
            omega = wave_spd * k
            dx, dy = direction
            phase = k * (dx * relative_x + dy * relative_y) - omega * time

            total_offset_z += wave_amp * math.sin(phase)

        # Wave mesh의 Z 위치를 더해서 절대 높이 반환
        return total_offset_z + wave_mesh_pos[2]
    
    @staticmethod
    def update_wave_mesh(stage, mesh_path, resolution, time, amp, wlen, spd, steep, size, num_waves):
        """Wave Mesh 업데이트"""
        wave_directions = [
            (1.0, 0.0),
            (0.6, 0.8),
        ]
        
        mesh = UsdGeom.Mesh.Get(stage, mesh_path)
        points = []
        
        for i in range(resolution):
            for j in range(resolution):
                base_x = (i/(resolution-1) - 0.5) * size
                base_y = (j/(resolution-1) - 0.5) * size
                
                total_offset_x = 0
                total_offset_y = 0
                total_offset_z = 0
                
                for wave_idx in range(num_waves):
                    direction = wave_directions[wave_idx % len(wave_directions)]
                    wave_amp = amp * (1.0 - wave_idx * 0.15)
                    wave_wlen = wlen * (1.0 + wave_idx * 0.3)
                    wave_spd = spd * (1.0 - wave_idx * 0.1)
                    
                    dx, dy, dz = WaveMesh.gerstner_wave(
                        base_x, base_y, time,
                        wave_amp, wave_wlen, wave_spd, steep,
                        direction
                    )
                    
                    total_offset_x += dx
                    total_offset_y += dy
                    total_offset_z += dz
                
                final_x = base_x + total_offset_x
                final_y = base_y + total_offset_y
                final_z = total_offset_z
                
                points.append(Gf.Vec3f(final_x, final_y, final_z))
        
        mesh.GetPointsAttr().Set(points)
