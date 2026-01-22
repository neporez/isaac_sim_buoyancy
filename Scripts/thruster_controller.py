"""
Thruster Controller for Catamaran (쌍동선)
- ROS2 cmd_vel subscriber
- Converts Twist messages to thruster forces
- Sets local X force on thruster Xforms
"""
import omni
import omni.usd
import threading
from pxr import Gf, Sdf


class ThrusterController:
    """쌍동선 Thruster 제어기"""

    def __init__(self, manager):
        self.manager = manager

        # Thruster paths
        self.thruster_l_path = None
        self.thruster_r_path = None

        # Thruster parameters
        self.max_thrust = 1000.0  # Maximum thrust force (N)

        # Current velocity command
        self.linear_x = 0.0
        self.angular_z = 0.0

        # ROS2 related
        self.ros2_enabled = False
        self.ros2_node = None
        self.ros2_thread = None
        self.ros2_running = False
        self.ros2_initialized_by_us = False

        print("ThrusterController initialized")

    def set_thruster_paths(self, left_path, right_path):
        """Thruster prim 경로 설정"""
        self.thruster_l_path = left_path
        self.thruster_r_path = right_path

        stage = omni.usd.get_context().get_stage()

        # Validate and setup force attributes
        for path, name in [(left_path, "Left"), (right_path, "Right")]:
            prim = stage.GetPrimAtPath(path)
            if not prim or not prim.IsValid():
                print(f"Warning: {name} thruster not found: {path}")
            else:
                # Create force attribute if not exists
                if not prim.GetAttribute("physxForce:force"):
                    prim.CreateAttribute("physxForce:force", Sdf.ValueTypeNames.Float3).Set(Gf.Vec3f(0, 0, 0))
                print(f"{name} thruster set: {path}")

    def start_ros2(self):
        """ROS2 노드 시작"""
        if self.ros2_enabled:
            print("ROS2 already running")
            return

        try:
            import rclpy
            from geometry_msgs.msg import Twist

            def ros2_thread_func():
                if not rclpy.ok():
                    rclpy.init()
                    self.ros2_initialized_by_us = True
                self.ros2_node = rclpy.create_node('isaac_thruster_controller')

                self.ros2_node.create_subscription(
                    Twist,
                    'cmd_vel',
                    self._cmd_vel_callback,
                    10
                )

                print("ROS2 node started - Subscribing to /cmd_vel")
                self.ros2_running = True

                while self.ros2_running:
                    rclpy.spin_once(self.ros2_node, timeout_sec=0.1)

                self.ros2_node.destroy_node()
                if self.ros2_initialized_by_us:
                    rclpy.shutdown()
                    self.ros2_initialized_by_us = False
                print("ROS2 node stopped")

            self.ros2_thread = threading.Thread(target=ros2_thread_func, daemon=True)
            self.ros2_thread.start()
            self.ros2_enabled = True

        except ImportError as e:
            print(f"Error: ROS2 not available - {e}")
        except Exception as e:
            print(f"Error starting ROS2: {e}")

    def stop_ros2(self):
        """ROS2 노드 중지"""
        self.ros2_running = False
        self.ros2_enabled = False
        self.linear_x = 0.0
        self.angular_z = 0.0
        print("ROS2 stopped")

    def _cmd_vel_callback(self, msg):
        """ROS2 cmd_vel 콜백"""
        self.linear_x = msg.linear.x
        self.angular_z = msg.angular.z

    def cmd_vel_to_thrust(self, linear_x, angular_z):
        """
        cmd_vel을 좌/우 Thruster 추력으로 변환

        Differential drive:
        - thrust_l = linear - angular
        - thrust_r = linear + angular
        """
        linear_gain = self.max_thrust / 2.0
        angular_gain = self.max_thrust / 4.0

        linear_thrust = linear_x * linear_gain
        angular_thrust = angular_z * angular_gain

        thrust_l = linear_thrust - angular_thrust
        thrust_r = linear_thrust + angular_thrust

        # Clamp
        thrust_l = max(-self.max_thrust, min(self.max_thrust, thrust_l))
        thrust_r = max(-self.max_thrust, min(self.max_thrust, thrust_r))

        return thrust_l, thrust_r

    def update(self, stage):
        """매 프레임 업데이트 - Thruster force 설정"""
        import omni.timeline
        timeline = omni.timeline.get_timeline_interface()

        if not timeline.is_playing():
            return

        if not self.thruster_l_path or not self.thruster_r_path:
            return

        # Get thrust values
        thrust_l, thrust_r = self.cmd_vel_to_thrust(self.linear_x, self.angular_z)

        # Set local X force on each thruster
        self._set_thruster_force(stage, self.thruster_l_path, thrust_l)
        self._set_thruster_force(stage, self.thruster_r_path, thrust_r)

    def _set_thruster_force(self, stage, prim_path, force_x):
        """Thruster의 local X force 설정"""
        prim = stage.GetPrimAtPath(prim_path)
        if not prim or not prim.IsValid():
            return

        # Set force as local X direction
        force_attr = prim.GetAttribute("physxForce:force")
        if force_attr:
            force_attr.Set(Gf.Vec3f(force_x, 0, 0))
