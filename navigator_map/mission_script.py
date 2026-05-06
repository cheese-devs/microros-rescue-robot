import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32
from yahboomcar_msgs.msg import PointArray
from geometry_msgs.msg import Twist
import time
import subprocess
import os
import signal
import math

class SingleActionWithTimeout(Node):
    def __init__(self):
        super().__init__('single_action_timeout')
        self.pub_servo = self.create_publisher(Int32, '/servo_s1', 10)
        self.pub_cmd_vel = self.create_publisher(Twist, '/cmd_vel', 10)
        self.sub_points = self.create_subscription(
            PointArray, '/mediapipe/points', self.listener_callback, 10)

        self.timeout_sec = 6.0
        self.max_rotations = 8  # 8 * 45° = 360°
        self.rotation_count = 0
        self.found = False

        self.timer = self.create_timer(self.timeout_sec, self.timeout_callback)
        self.get_logger().info(f"เริ่มรอตรวจจับ (มีเวลา {self.timeout_sec} วินาที)...")

    def _rotate_45(self):
        twist = Twist()
        twist.angular.z = 0.5  # rad/s
        duration = (math.pi / 4) / 0.5  # ~1.57 วินาที
        end_time = time.time() + duration
        while time.time() < end_time:
            self.pub_cmd_vel.publish(twist)
            time.sleep(0.05)
        twist.angular.z = 0.0
        self.pub_cmd_vel.publish(twist)
        time.sleep(0.2)

    def timeout_callback(self):
        self.timer.cancel()
        if self.rotation_count >= self.max_rotations:
            self.get_logger().warn("หมุนครบ 360° แล้วยังไม่พบคน ข้ามไปจุดถัดไป...")
            raise SystemExit
        self.rotation_count += 1
        self.get_logger().info(
            f"ไม่พบคน หมุน 45° (ครั้งที่ {self.rotation_count}/{self.max_rotations})...")
        self._rotate_45()
        self.timer = self.create_timer(self.timeout_sec, self.timeout_callback)

    def listener_callback(self, msg):
        if len(msg.points) > 0 and not self.found:
            self.found = True
            self.timer.cancel()
            self.get_logger().info("ตรวจพบข้อมูล! กำลังสั่งงาน Servo...")

            val = Int32()
            val.data = -90
            self.pub_servo.publish(val)
            time.sleep(1.0)

            val.data = 0
            self.pub_servo.publish(val)
            time.sleep(1.0)

            self.get_logger().info("ทำงานเสร็จสิ้น ปิดโปรแกรม...")
            raise SystemExit

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cam_proc = subprocess.Popen(
        ['python3', os.path.join(script_dir, 'Cam_Pose_AprilTag.py')],
        preexec_fn=os.setsid
    )
    time.sleep(4.0)  # รอให้ MediaPipe + camera พร้อม

    rclpy.init()
    node = SingleActionWithTimeout()
    try:
        rclpy.spin(node)
    except SystemExit:
        pass
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
        try:
            os.killpg(os.getpgid(cam_proc.pid), signal.SIGTERM)
        except ProcessLookupError:
            pass

if __name__ == '__main__':
    main()
