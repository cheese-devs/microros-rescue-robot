#!/usr/bin/env python3
# encoding: utf-8

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage, Imu, LaserScan
from nav_msgs.msg import Odometry
from std_msgs.msg import UInt16
import time

class SystemWatchdog(Node):
    def __init__(self):
        super().__init__('system_watchdog')
        
        self.last_cam_time = 0.0
        self.last_imu_time = 0.0
        self.last_battery_time = 0.0
        self.last_scan_time = 0.0
        self.last_odom_time = 0.0
        self.last_imu_z = 0.0
        self.imu_active = False
        self.battery_voltage = 0.0 # เก็บเป็นหน่วย Volt (float)
        
        self.sub_cam  = self.create_subscription(CompressedImage, '/espRos/esp32camera', self.cam_callback, 10)
        self.sub_imu  = self.create_subscription(Imu, '/imu', self.imu_callback, 10)
        self.sub_bat  = self.create_subscription(UInt16, '/battery', self.bat_callback, 10)
        self.sub_scan = self.create_subscription(LaserScan, '/scan', self.scan_callback, 10)
        self.sub_odom = self.create_subscription(Odometry, '/odom_raw', self.odom_callback, 10)
            
        self.timer = self.create_timer(1.0, self.check_status)
        
        print("\n" + "="*55)
        print("   YAHBOOM SYSTEM WATCHDOG Cam,IMU,BAT,LiDAR,Odom")
        print("="*55)

    def cam_callback(self, msg):
        self.last_cam_time = time.time()

    def imu_callback(self, msg):
        # บันทึกเวลาล่าสุดที่ได้รับข้อมูล
        self.last_imu_time = time.time()
        # เก็บค่าแกน Z ไว้ตรวจสอบ
        self.last_imu_z = msg.linear_acceleration.z
        
        # Logic: ถ้าแกน Z ไม่เป็น 0 แสดงว่าเซนเซอร์ทำงานปกติ (มีแรงโน้มถ่วงโลก)
        if abs(self.last_imu_z) > 0.1:
            self.imu_active = True
        else:
            self.imu_active = False
    def scan_callback(self, msg):
        self.last_scan_time = time.time()

    def odom_callback(self, msg):
        self.last_odom_time = time.time()

    def bat_callback(self, msg):
        self.last_battery_time = time.time()
        # แปลงจาก mV (เช่น 12400) เป็น V (12.4) โดยการหาร 1000
        # **หมายเหตุ: ถ้าค่าที่ได้มาเป็น V อยู่แล้ว (เช่น 12) ให้เอา / 1000.0 ออกครับ**
        self.battery_voltage = msg.data / 10.0  # firmware ส่งค่า x10 ของ Volt เช่น 74 = 7.4V
    def check_status(self):
        now = time.time()

        # 1. เช็คกล้อง (ขาดหายเกิน 2 วิ)
        cam_alive = (now - self.last_cam_time) < 2.0

        # 2. เช็ค IMU (ต้องมีข้อมูลมา และ แกน Z ต้องไม่เป็น 0)
        imu_com_alive = (now - self.last_imu_time) < 2.0
        imu_functional = imu_com_alive and self.imu_active

        bat_alive  = (now - self.last_battery_time) < 3.0
        scan_alive = (now - self.last_scan_time) < 2.0
        odom_alive = (now - self.last_odom_time) < 2.0

        GREEN = '\033[92m'
        RED = '\033[91m'
        RESET = '\033[0m'
        YELLOW = '\033[93m'


        def col(text, color, width=0):
            return f"{color}{text:<{width}}{RESET}"

        cam_status = col("ONLINE" if cam_alive else "OFFLINE", GREEN if cam_alive else RED, 10)

        if not imu_com_alive:
            imu_status = col("OFFLINE (No Data)", RED)
        elif not self.imu_active:
            imu_status = col("OFFLINE (Sensor Fault / Z=0)", RED)
        else:
            imu_status = col(f"ONLINE (IMU.Z: {self.last_imu_z:.2f})", GREEN)

        if not bat_alive:
            bat_status = col("OFFLINE", RED, 10)
        else:
            bat_color = GREEN if self.battery_voltage > 7.8 else YELLOW if self.battery_voltage > 7.2 else RED
            bat_status = col(f"{self.battery_voltage:.2f} V", bat_color, 10)

        scan_status = col("ONLINE" if scan_alive else "OFFLINE", GREEN if scan_alive else RED, 10)
        odom_status = col("ONLINE" if odom_alive else "OFFLINE", GREEN if odom_alive else RED)

        ts = time.strftime('%H:%M:%S')
        print(f"[{ts}] Cam: {cam_status} | IMU: {imu_status}")
        print(f"           BAT: {bat_status} | LiDAR: {scan_status} | Odom: {odom_status}")
        print()

def main():
    rclpy.init()
    node = SystemWatchdog()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
