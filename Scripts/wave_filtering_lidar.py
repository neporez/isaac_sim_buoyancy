import numpy as np
import omni
import omni.usd
import omni.kit.app
import omni.timeline
import carb.settings
from isaacsim.sensors.rtx import LidarRtx

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import PointCloud2, PointField
from std_msgs.msg import Header

class FilteredLidarPublisher:
    def __init__(self, lidar_path="/World/lidar", target_objects=None, exclude_mode=False):
        self.lidar_path = lidar_path
        self.target_objects = target_objects or []
        self.exclude_mode = exclude_mode
        self.timeline = omni.timeline.get_timeline_interface()

        if not rclpy.ok():
            rclpy.init()
        self.node = Node('filtered_lidar_publisher')
        self.publisher = self.node.create_publisher(PointCloud2, '/lidar/filtered_points', 10)

        carb.settings.get_settings().set("/rtx-transient/stableIds/enabled", True)

        self._setup_lidar()

        self.my_lidar.initialize()
        self.my_lidar.attach_annotator("IsaacCreateRTXLidarScanBuffer", outputObjectId=True)
        self.my_lidar.attach_annotator("StableIdMap")

        self._frame_count = 0
        self._is_playing = False
        self._warmup_frames = 10
        self._data_ready = False

        self._sub = omni.kit.app.get_app().get_update_event_stream().create_subscription_to_pop(
            self._on_update
        )

    def _setup_lidar(self):
        stage = omni.usd.get_context().get_stage()

        if stage.GetPrimAtPath(self.lidar_path):
            omni.kit.commands.execute("DeletePrims", paths=[self.lidar_path])

        self.my_lidar = LidarRtx(
            prim_path=self.lidar_path,
            name="lidar",
            position=np.array([0, 0, 0]),
            config_file_name="HESAI_XT32_SD10",
            **{"omni:sensor:Core:auxOutputType": "FULL"}
        )

    def _create_pointcloud2_message(self, pc, stamp, frame_id='lidar_link'):
        if pc is None or len(pc) == 0:
            return None

        header = Header()
        header.frame_id = frame_id
        header.stamp = stamp

        fields = [
            PointField(name='x', offset=0, datatype=PointField.FLOAT32, count=1),
            PointField(name='y', offset=4, datatype=PointField.FLOAT32, count=1),
            PointField(name='z', offset=8, datatype=PointField.FLOAT32, count=1),
        ]

        point_step = 12

        data = pc.astype(np.float32).tobytes()

        return PointCloud2(
            header=header,
            height=1,
            width=pc.shape[0],
            fields=fields,
            is_bigendian=False,
            point_step=point_step,
            row_step=point_step * pc.shape[0],
            is_dense=True,
            data=data,
        )

    def _filter_and_publish(self, scan_buffer, stable_id_map):
        if 'data' not in scan_buffer or 'objectId' not in scan_buffer:
            return

        xyz_data = scan_buffer['data']
        obj_ids_buffer = scan_buffer['objectId']

        if xyz_data is None or len(xyz_data) == 0:
            return

        if obj_ids_buffer is None or len(obj_ids_buffer) == 0:
            return

        self._data_ready = True

        if not self.target_objects:
            filtered_xyz = xyz_data
        else:
            try:
                obj_ids = LidarRtx.get_object_ids(obj_ids_buffer)

                if not obj_ids:
                    return

                unique_obj_ids = set(obj_ids)

                target_ids_in_scene = set()
                for oid in unique_obj_ids:
                    if oid in stable_id_map:
                        path = stable_id_map[oid]
                        for target in self.target_objects:
                            if path == target or path.startswith(target + "/"):
                                target_ids_in_scene.add(oid)
                                break

                if not target_ids_in_scene:
                    if self.exclude_mode:
                        filtered_xyz = xyz_data
                    else:
                        return
                else:
                    mask = np.array([oid in target_ids_in_scene for oid in obj_ids], dtype=bool)

                    if self.exclude_mode:
                        mask = ~mask

                    filtered_xyz = xyz_data[mask]

            except Exception:
                return

        n_points = len(filtered_xyz)

        if n_points == 0:
            return

        try:
            stamp = self.node.get_clock().now().to_msg()
            msg = self._create_pointcloud2_message(filtered_xyz, stamp)

            if msg is not None:
                self.publisher.publish(msg)

        except Exception:
            pass

    def _on_update(self, e):
        try:
            is_now_playing = self.timeline.is_playing()

            if not is_now_playing:
                if self._is_playing:
                    self._frame_count = 0
                    self._data_ready = False
                self._is_playing = False
                return

            if is_now_playing and not self._is_playing:
                self._is_playing = True
                self._frame_count = 0
                self._data_ready = False

            self._frame_count += 1

            if self._frame_count <= self._warmup_frames:
                return

            frame = self.my_lidar.get_current_frame()

            if frame is None:
                return

            stable_id_map_buffer = frame.get("StableIdMap")
            scan_buffer = frame.get("IsaacCreateRTXLidarScanBuffer")

            if stable_id_map_buffer is None or scan_buffer is None:
                return

            if len(stable_id_map_buffer) == 0:
                return

            try:
                stable_id_map = LidarRtx.decode_stable_id_mapping(stable_id_map_buffer.tobytes())
            except Exception:
                return

            self._filter_and_publish(scan_buffer, stable_id_map)

        except Exception:
            pass

    def cleanup(self):
        self._sub = None
        if hasattr(self, 'my_lidar'):
            self.my_lidar.detach_all_annotators()
        if hasattr(self, 'node'):
            self.node.destroy_node()


publisher = FilteredLidarPublisher(
    lidar_path="/World/lidar",
    target_objects=["/World/GerstnerWave"],
    exclude_mode=True
)
