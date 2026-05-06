import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32
from yahboomcar_msgs.msg import PointArray
import time
import subprocess
import os
import signal

class SingleActionWithTimeout(Node):
    def __init__(self):
        super().__init__('single_action_timeout')
        self.pub_servo = self.create_publisher(Int32, '/servo_s1', 10)
        self.sub_points = self.create_subscription(
            PointArray,
            '/mediapipe/points',
            self.listener_callback,
            10)
        
        # สร้าง Timer ให้ทำงานหลังจากผ่านไป 5 วินาที
        self.timeout_sec = 6.0
        self.timer = self.create_timer(self.timeout_sec, self.timeout_callback)
        
        self.get_logger().info(f"เริ่มรอตรวจจับ (มีเวลา {self.timeout_sec} วินาที)...")

    def timeout_callback(self):
        self.get_logger().warn("หมดเวลา 6 วินาที: ไม่พบข้อมูล ปิดโปรแกรม...")
        raise SystemExit

    def listener_callback(self, msg):
        if len(msg.points) > 0:
            # หยุด Timer ทันทีเมื่อเจอข้อมูล เพื่อไม่ให้โปรแกรมปิดตัวขณะกำลังทำงาน
            self.timer.cancel()
            
            self.get_logger().info("ตรวจพบข้อมูล! กำลังสั่งงาน Servo...")

            # 1. สั่งไปที่ -40
            val = Int32()
            val.data = -40
            self.pub_servo.publish(val)
            time.sleep(1.0)

            # 2. สั่งกลับมาที่ 0
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
