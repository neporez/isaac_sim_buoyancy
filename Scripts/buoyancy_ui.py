"""
Buoyancy Manager UI (Scripts2 버전)
- 포인트 클라우드 기반 부력 시스템용 UI
- 쌍동선 Thruster 제어 UI
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
        self.resolution_field = None
        self.objects_list = None

        # Thruster UI fields
        self.thruster_l_field = None
        self.thruster_r_field = None

        self.create_ui()

    def create_ui(self):
        """GUI 생성"""
        self.window = ui.Window("Buoyancy Manager", width=400, height=1000)

        with self.window.frame:
            with ui.ScrollingFrame():
                with ui.VStack(spacing=10, style={"margin": 10}):
                    ui.Label("Point Cloud Buoyancy System",
                             height=30, alignment=ui.Alignment.CENTER,
                             style={"font_size": 16})

                    ui.Spacer(height=5)

                    # Object Section
                    self._create_object_section()

                    ui.Spacer(height=5)

                    # Objects List
                    self._create_objects_list()

                    ui.Spacer(height=5)

                    # Thruster Settings
                    self._create_thruster_settings()

                    ui.Spacer(height=5)

                    # Wave Settings
                    self._create_wave_settings()

                    ui.Spacer(height=10)

                    ui.Button("Pause/Resume Wave", height=35, clicked_fn=self.manager.toggle_pause)

        self.update_objects_list()

    def _create_object_section(self):
        """물체 추가/제거 섹션"""
        ui.Label("Add Buoyant Object", height=25, alignment=ui.Alignment.CENTER)

        ui.Label("Object Path (with Colliders + Mass):", height=20)
        self.path_field = ui.StringField(height=25)
        self.path_field.model.set_value("/root/WAMV/Xform")

        ui.Label("Sample Resolution (m):", height=20)
        with ui.HStack():
            self.resolution_field = ui.FloatField(height=20)
            self.resolution_field.model.set_value(0.2)

        ui.Spacer(height=5)

        with ui.HStack(height=30, spacing=5):
            ui.Button("Add Buoyancy", clicked_fn=self.on_add_buoyancy,
                      style={"background_color": 0xFF005588})
            ui.Button("Remove", clicked_fn=self.on_remove_buoyancy)

        ui.Spacer(height=5)

        ui.Label("Quick Actions:", height=20)
        ui.Button("Create Test Platform (3x3x0.2m)", height=25, clicked_fn=self.create_platform)
        ui.Button("Enable Debug Output", height=25, clicked_fn=self.manager.enable_debug)

    def _create_objects_list(self):
        """등록된 물체 목록"""
        ui.Label("Registered Objects", height=25, alignment=ui.Alignment.CENTER)

        with ui.ScrollingFrame(height=120):
            self.objects_list = ui.VStack(spacing=2)

        ui.Button("Refresh List", height=25, clicked_fn=self.update_objects_list)

    def _create_thruster_settings(self):
        """Thruster 설정 섹션 (쌍동선 제어)"""
        ui.Label("Thruster Settings (Catamaran)", height=25, alignment=ui.Alignment.CENTER,
                 style={"font_size": 14, "color": 0xFF00AAFF})

        # Thruster Left
        ui.Label("Thruster Left (Xform Path):", height=20)
        self.thruster_l_field = ui.StringField(height=25)
        self.thruster_l_field.model.set_value("/root/WAMV/Xform/Buoy_L/Thruster_L")

        # Thruster Right
        ui.Label("Thruster Right (Xform Path):", height=20)
        self.thruster_r_field = ui.StringField(height=25)
        self.thruster_r_field.model.set_value("/root/WAMV/Xform/Buoy_R/Thruster_R")

        ui.Spacer(height=5)

        with ui.HStack(height=30, spacing=5):
            ui.Button("Apply Thrusters", clicked_fn=self.on_apply_thrusters,
                      style={"background_color": 0xFF00AA55})
            ui.Button("Start ROS2", clicked_fn=self.on_start_ros2,
                      style={"background_color": 0xFF0055AA})
            ui.Button("Stop ROS2", clicked_fn=self.on_stop_ros2,
                      style={"background_color": 0xFFAA5500})

        # Thruster Status
        ui.Label("Thruster Status:", height=20)
        self.thruster_status_label = ui.Label("Not configured", height=20,
                                               style={"color": 0xFFAAAA00})

        # ROS2 Status
        ui.Label("ROS2 Status:", height=20)
        self.ros2_status_label = ui.Label("Not connected", height=20,
                                           style={"color": 0xFFAAAA00})

    def on_apply_thrusters(self):
        """Thruster 경로 적용"""
        left_path = self.thruster_l_field.model.get_value_as_string()
        right_path = self.thruster_r_field.model.get_value_as_string()

        if hasattr(self.manager, 'thruster_controller'):
            self.manager.thruster_controller.set_thruster_paths(left_path, right_path)
            self.thruster_status_label.text = f"L: {left_path.split('/')[-1]}, R: {right_path.split('/')[-1]}"
            self.thruster_status_label.style = {"color": 0xFF00FF00}
            print(f"Thrusters configured: L={left_path}, R={right_path}")
        else:
            print("Error: Thruster controller not initialized")

    def on_start_ros2(self):
        """ROS2 시작"""
        if hasattr(self.manager, 'thruster_controller'):
            self.manager.thruster_controller.start_ros2()
            self.ros2_status_label.text = "Connected - Listening cmd_vel"
            self.ros2_status_label.style = {"color": 0xFF00FF00}
        else:
            print("Error: Thruster controller not initialized")

    def on_stop_ros2(self):
        """ROS2 중지"""
        if hasattr(self.manager, 'thruster_controller'):
            self.manager.thruster_controller.stop_ros2()
            self.ros2_status_label.text = "Disconnected"
            self.ros2_status_label.style = {"color": 0xFFFF0000}
        else:
            print("Error: Thruster controller not initialized")

    def _create_wave_settings(self):
        """파도 설정 섹션"""
        ui.Label("Wave Settings", height=25, alignment=ui.Alignment.CENTER,
                 style={"font_size": 14, "color": 0xFF00AAFF})

        # Amplitude
        ui.Label("Amplitude (m):", height=20)
        with ui.HStack():
            s = ui.FloatSlider(min=0, max=2, height=20)
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

        # Wavelength
        ui.Label("Wavelength (m):", height=20)
        with ui.HStack():
            s = ui.FloatSlider(min=1, max=20, height=20)
            s.model.set_value(4.0)
            l = ui.Label("4.0", width=50)

            def on_wlen(m):
                stage = omni.usd.get_context().get_stage()
                prim = stage.GetPrimAtPath(self.manager.mesh_path)
                if prim:
                    val = m.get_value_as_float()
                    prim.GetAttribute("wave:wavelength").Set(val)
                    l.text = f"{val:.1f}"

            s.model.add_value_changed_fn(on_wlen)

        # Speed
        ui.Label("Speed (m/s):", height=20)
        with ui.HStack():
            s = ui.FloatSlider(min=0, max=10, height=20)
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

        # Steepness
        ui.Label("Steepness (0-1):", height=20)
        with ui.HStack():
            s = ui.FloatSlider(min=0, max=1, height=20)
            s.model.set_value(0.2)
            l = ui.Label("0.2", width=50)

            def on_steep(m):
                stage = omni.usd.get_context().get_stage()
                prim = stage.GetPrimAtPath(self.manager.mesh_path)
                if prim:
                    val = m.get_value_as_float()
                    prim.GetAttribute("wave:steepness").Set(val)
                    l.text = f"{val:.2f}"

            s.model.add_value_changed_fn(on_steep)

        # Num Waves
        ui.Label("Number of Waves:", height=20)
        with ui.HStack():
            s = ui.IntSlider(min=1, max=5, height=20)
            s.model.set_value(2)
            l = ui.Label("2", width=50)

            def on_num_waves(m):
                stage = omni.usd.get_context().get_stage()
                prim = stage.GetPrimAtPath(self.manager.mesh_path)
                if prim:
                    val = m.get_value_as_int()
                    prim.GetAttribute("wave:num_waves").Set(val)
                    l.text = f"{val}"

            s.model.add_value_changed_fn(on_num_waves)

        # Wave Size
        ui.Label("Wave Size (m):", height=20)
        with ui.HStack():
            s = ui.FloatSlider(min=10, max=200, height=20)
            s.model.set_value(20.0)
            l = ui.Label("20.0", width=50)

            def on_size(m):
                stage = omni.usd.get_context().get_stage()
                prim = stage.GetPrimAtPath(self.manager.mesh_path)
                if prim:
                    val = m.get_value_as_float()
                    prim.GetAttribute("wave:size").Set(val)
                    l.text = f"{val:.1f}"

            s.model.add_value_changed_fn(on_size)

        # Resolution
        ui.Label("Mesh Resolution (quality):", height=20)
        with ui.HStack():
            s = ui.FloatSlider(min=10, max=200, height=20)
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
        if path:
            self.manager.add_buoyancy_to_object(path)
            self.update_objects_list()

    def on_remove_buoyancy(self):
        """물체 제거"""
        path = self.path_field.model.get_value_as_string()
        if path:
            self.manager.remove_buoyancy_from_object(path)
            self.update_objects_list()

    def create_platform(self):
        """테스트 플랫폼 생성"""
        stage = omni.usd.get_context().get_stage()

        import random
        platform_name = f"Platform_{random.randint(1000, 9999)}"
        platform_path = f"/World/{platform_name}"

        # Cube 생성
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
                    name = path.split('/')[-1]
                    status = "initialized" if obj.is_initialized else "pending"
                    points = len(obj.sample_points_local)
                    ui.Label(f"{name} [{status}] - {points} points", height=20)
