"""
부력을 받는 개별 물체 클래스
"""

class BuoyantObject:
    """부력을 받는 개별 물체"""
    def __init__(self, prim_path, material_density=50.0):
        self.prim_path = prim_path
        self.material_density = material_density
        self.is_active = True
        
        # 물리 상수
        self.water_density = 1000.0
        self.gravity = 9.81
        self.drag_coefficient = 1.0
        self.angular_drag_coefficient = 1.0
        
        print(f"BuoyantObject registered: {prim_path}")
        print(f"  Material density: {material_density} kg/m^3")