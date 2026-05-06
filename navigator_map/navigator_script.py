import rclpy
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
from geometry_msgs.msg import PoseStamped, Twist
import yaml
import time
import subprocess
import os

class TaskNavigator:
    def __init__(self):
        self.nav = BasicNavigator()
        self.cmd_vel_pub = self.nav.create_publisher(Twist, '/cmd_vel', 10)

    def run_external_script(self, script_name):
        script_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), script_name)
        print(f"   -> รัน: {script_name}")
        try:
            subprocess.run(["python3", script_path], check=True)
            print("   -> เสร็จสิ้น")
        except subprocess.CalledProcessError as e:
            print(f"   -> [ERROR] {e}")
        except FileNotFoundError:
            print(f"   -> [ERROR] ไม่พบไฟล์: {script_path}")

    def perform_task(self, waypoint_name, wp_type):
        print(f"--- ถึงจุด {waypoint_name} (ประเภท: {wp_type}) ---")
        if wp_type == 'h':
            time.sleep(2)
        elif wp_type == 'a':
            self.run_external_script("apriltag_script.py")
        else:
            self.run_external_script("mission_script.py")
        print(f"--- เสร็จสิ้นภารกิจที่ {waypoint_name} ---\n")
def main():
    rclpy.init()
    task_nav = TaskNavigator()
    nav = task_nav.nav

    print("กำลังรอให้ Nav2 พร้อมใช้งาน...")
    nav.waitUntilNav2Active()

    # เริ่ม Loop ใหญ่เพื่อให้รับค่าได้เรื่อยๆ
    while rclpy.ok():
        # โหลดไฟล์ YAML ทุกครั้งที่เริ่มรอบใหม่ (เผื่อมีการอัปเดตไฟล์ขณะโปรแกรมรัน)
        try:
            with open('nav_waypoints.yaml', 'r') as f:
                data = yaml.safe_load(f)
                all_waypoints = data['waypoints']
        except Exception as e:
            print(f"Error loading YAML: {e}")
            break

        # แสดงรายการ Waypoint
        print("\n" + "="*30)
        print("รายการ Waypoints ที่พร้อมใช้งาน:")
        for i, wp in enumerate(all_waypoints):
            print(f"[{i+1}] {wp['task']} (x: {wp['x']}, y: {wp['y']},z: {wp['orientation']['z']}, w: {wp['orientation']['w']})")
        print("[0] ออกจากโปรแกรม (Exit)")
        print("="*30)
        
        # รับค่า Input
        user_input = input("\nระบุลำดับการวิ่ง (เช่น 3,1,2) หรือกด 0 เพื่อเลิก: ")
        
        if user_input.strip() == '0':
            print("ปิดโปรแกรม...")
            break
        
        try:
            order_indices = [int(x.strip()) - 1 for x in user_input.split(',') if x.strip()]
            planned_waypoints = [all_waypoints[i] for i in order_indices]
        except (ValueError, IndexError):
            print("[!] ใส่ตัวเลขไม่ถูกต้อง กรุณาลองใหม่")
            continue

        # ถามประเภทแต่ละจุด
        wp_types = []
        print("\nระบุประเภทแต่ละจุด (a=apriltag, s=survivor, h=home):")
        for wp in planned_waypoints:
            while True:
                t = input(f"  {wp['task']} [a/s/h]: ").strip().lower()
                if t in ('a', 's', 'h'):
                    wp_types.append(t)
                    break
                print("  [!] ใส่แค่ a, s, หรือ h")

        # เริ่มการเดินทางตามลำดับที่ป้อน
        print(f"\nเริ่มการเดินทางทั้งหมด {len(planned_waypoints)} จุด...")

        for wp, wp_type in zip(planned_waypoints, wp_types):
            goal_pose = PoseStamped()
            goal_pose.header.frame_id = 'map'
            goal_pose.header.stamp = nav.get_clock().now().to_msg()
            goal_pose.pose.position.x = wp['x']
            goal_pose.pose.position.y = wp['y']
            goal_pose.pose.orientation.z = wp['orientation']['z']
            goal_pose.pose.orientation.w = wp['orientation']['w']

            print(f">> มุ่งหน้าไป: {wp['task']}")
            nav.goToPose(goal_pose)

            # ตรวจสอบสถานะการวิ่ง
            while not nav.isTaskComplete():
                # คุณสามารถเพิ่ม logic ตรวจสอบ Feedback ตรงนี้ได้
                pass

            result = nav.getResult()
            if result == TaskResult.SUCCEEDED:
                task_nav.perform_task(wp['task'], wp_type)
            elif result == TaskResult.CANCELED:
                print(f"ภารกิจไป {wp['task']} ถูกยกเลิก")
            elif result == TaskResult.FAILED:
                print(f"ไม่สามารถไปถึง {wp['task']} ได้ (อาจมีสิ่งกีดขวาง) ข้ามไปจุดถัดไป...")

        print("\n[SUCCESS] วิ่งครบตามแผนงานแล้ว!")
        print("กลับไปรอรับคำสั่งชุดใหม่...")

    rclpy.shutdown()

if __name__ == '__main__':
    main()

