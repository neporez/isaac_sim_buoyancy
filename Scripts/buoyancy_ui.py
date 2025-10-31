"""
Buoyancy Manager UI
"""
import omni.usd
import omni.ui as ui
from pxr import UsdGeom, Gf


class BuoyancyUI:
    """UI 관리"""
    
    def __init__(self, manager):
        self.manager = manager
        self.window = None
        self.path_field = None
        self.density_slider = None
        self.density_label = None
        self.objects_list = None
        
        self.create_ui()
    
    def create_ui(self):
        """GUI 생성"""
        self.window = ui.Window("Buoyancy Manager", width=400, height=600)
        
        with self.window.frame:
            with ui.ScrollingFrame():
                with ui.VStack(spacing=10, style={"margin": 10}):
                    ui.Label("Dynamic Buoyancy Manager", height=30, alignment=ui.Alignment.CENTER)
                    
                    ui.Spacer(height=5)
                    
                    # Object Section
                    self._create_object_section()
                    
                    ui.Spacer(height=5)
                    
                    # Objects List
                    self._create_objects_list()
                    
                    ui.Spacer(height=5)
                    
                    # Wave Settings
                    self._create_wave_settings()
                    
                    ui.Spacer(height=10)
                    
                    ui.Button("Pause/Resume Wave", height=35, clicked_fn=self.manager.toggle_pause)
        
        self.update_objects_list()
    
    def _create_object_section(self):
        """물체 추가/제거 섹션"""
        ui.Label("Add Object", height=25, alignment=ui.Alignment.CENTER)
        
        ui.Label("Object Path:", height=20)
        self.path_field = ui.StringField(height=25)
        self.path_field.model.set_value("/World/Cube")
        
        ui.Label("Material Density (kg/m^3):", height=20)
        with ui.HStack():
            self.density_slider = ui.FloatSlider(min=10, max=500, height=20)
            self.density_slider.model.set_value(50.0)
            self.density_label = ui.Label("50.0", width=60)
            
            def on_density_change(m):
                val = m.get_value_as_float()
                self.density_label.text = f"{val:.1f}"
            self.density_slider.model.add_value_changed_fn(on_density_change)
        
        ui.Label("Styrofoam=50, Wood=500, Water=1000", height=15)
        
        with ui.HStack(height=30, spacing=5):
            ui.Button("Add Buoyancy", clicked_fn=self.on_add_buoyancy)
            ui.Button("Remove", clicked_fn=self.on_remove_buoyancy)
        
        ui.Label("Quick Actions:", height=20)
        ui.Button("Create Platform (3x3x0.2m)", height=25, clicked_fn=self.create_platform)
        ui.Button("Enable Debug Output", height=25, clicked_fn=self.manager.enable_debug)
    
    def _create_objects_list(self):
        """등록된 물체 목록"""
        ui.Label("Registered Objects", height=25, alignment=ui.Alignment.CENTER)
        
        with ui.ScrollingFrame(height=100):
            self.objects_list = ui.VStack(spacing=2)
        
        ui.Button("Refresh List", height=25, clicked_fn=self.update_objects_list)
    
    def _create_wave_settings(self):
        """파도 설정 섹션"""
        ui.Label("Wave Settings", height=25, alignment=ui.Alignment.CENTER)
        
        # Amplitude
        ui.Label("Amplitude:", height=20)
        with ui.HStack():
            s = ui.FloatSlider(min=0, max=1, height=20)
            s.model.set_value(0.2)
            l = ui.Label("0.2", width=50)
            def on_amp(m):
                stage = omni.usd.get_context().get_stage()
                prim = stage.GetPrimAtPath(self.manager.mesh_path)
                if prim:
                    val = m.get_value_as_float()
                    prim.GetAttribute("wave:amplitude").Set(val)
                    l.text = f"{val:.2f}"
            s.model.add_value_changed_fn(on_amp)
        
        # Speed
        ui.Label("Speed:", height=20)
        with ui.HStack():
            s = ui.FloatSlider(min=0, max=5, height=20)
            s.model.set_value(1.5)
            l = ui.Label("1.5", width=50)
            def on_spd(m):
                stage = omni.usd.get_context().get_stage()
                prim = stage.GetPrimAtPath(self.manager.mesh_path)
                if prim:
                    val = m.get_value_as_float()
                    prim.GetAttribute("wave:speed").Set(val)
                    l.text = f"{val:.1f}"
            s.model.add_value_changed_fn(on_spd)
        
        # Tank Size
        ui.Label("Tank Size (m):", height=20)
        with ui.HStack():
            s = ui.FloatSlider(min=10, max=50, height=20)
            s.model.set_value(20.0)
            l = ui.Label("20.0", width=50)
            def on_size(m):
                stage = omni.usd.get_context().get_stage()
                prim = stage.GetPrimAtPath(self.manager.mesh_path)
                if prim:
                    val = m.get_value_as_float()
                    prim.GetAttribute("wave:size").Set(val)
                    self.manager.update_water_tank_size(val)
                    l.text = f"{val:.1f}"
            s.model.add_value_changed_fn(on_size)
        
        # Resolution
        ui.Label("Resolution (quality):", height=20)
        with ui.HStack():
            s = ui.FloatSlider(min=10, max=50, height=20)
            s.model.set_value(20.0)
            l = ui.Label("20", width=50)
            def on_resolution(m):
                val = int(m.get_value_as_float())
                self.manager.resolution = val
                stage = omni.usd.get_context().get_stage()
                self.manager.rebuild_wave_mesh(stage)
                l.text = f"{val}"
            s.model.add_value_changed_fn(on_resolution)
    
    def on_add_buoyancy(self):
        """물체 추가"""
        path = self.path_field.model.get_value_as_string()
        density = self.density_slider.model.get_value_as_float()
        if path:
            self.manager.add_buoyancy_to_object(path, density)
            self.update_objects_list()
    
    def on_remove_buoyancy(self):
        """물체 제거"""
        path = self.path_field.model.get_value_as_string()
        if path:
            self.manager.remove_buoyancy_from_object(path)
            self.update_objects_list()
    
    def create_platform(self):
        """플랫폼 생성"""
        stage = omni.usd.get_context().get_stage()
        
        import random
        platform_name = f"Platform_{random.randint(1000, 9999)}"
        platform_path = f"/World/{platform_name}"
        
        cube = UsdGeom.Cube.Define(stage, platform_path)
        cube.CreateSizeAttr(1.0)
        
        xform_api = UsdGeom.XformCommonAPI(cube)
        xform_api.SetScale(Gf.Vec3f(3.0, 3.0, 0.2))
        xform_api.SetTranslate((0.0, 0.0, 2.0))
        
        self.path_field.model.set_value(platform_path)
        print(f"Platform created: {platform_path}")
        print("  Size: 3m x 3m x 0.2m")
        print("  Position: (0, 0, 2)")
    
    def update_objects_list(self):
        """물체 목록 업데이트"""
        self.objects_list.clear()
        
        if not self.manager.buoyant_objects:
            with self.objects_list:
                ui.Label("(No objects)", height=20)
        else:
            with self.objects_list:
                for path, obj in self.manager.buoyant_objects.items():
                    ui.Label(f"{path.split('/')[-1]} ({obj.material_density}kg/m3)", height=20)