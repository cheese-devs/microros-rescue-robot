# สรุปความรู้: RoboRescue with microROS

โน้ตสรุปเนื้อหาทั้งหมดของโปรเจกต์ Tutorial-RoboRescue-with-microROS สำหรับใช้อ้างอิงเร็ว ๆ

---

## 1. ภาพรวมระบบ

หุ่นยนต์กู้ภัย (Yahboom 4-wheel differential drive) สำหรับการแข่ง RoboRescue บนสนาม 320×280 cm
ใช้ **micro-ROS** บน ESP32 คุยกับ **ROS 2 Humble** บนคอมพิวเตอร์ฝั่ง host ผ่าน Wi-Fi

```
┌──────────────────┐        Wi-Fi UDP4         ┌──────────────────────┐
│  ESP32 (Robot)   │  ◄────── port 8090 ─────► │  Host PC (Ubuntu)    │
│  - micro-ROS     │                            │  - micro-ROS Agent   │
│  - มอเตอร์/IMU   │                            │    (Docker)          │
│  - LiDAR/Servo   │                            │  - ROS 2 Humble      │
└──────────────────┘                            │  - Nav2 / SLAM       │
                                                 │  - RViz2             │
┌──────────────────┐        Wi-Fi UDP4         │                      │
│  ESP32 Camera    │  ◄────── port 9999 ─────► │                      │
└──────────────────┘                            └──────────────────────┘
```

**สำคัญ:** หุ่นยนต์ **ไม่ได้** รัน ROS 2 เอง — มันคุย micro-ROS (DDS-XRCE) มา Agent บน host แล้ว Agent ค่อย bridge เข้า ROS 2 graph

---

## 2. Hardware Stack

| ส่วนประกอบ | รายละเอียด |
|---|---|
| ฐานหุ่น | Yahboom 4-wheel differential drive |
| MCU | ESP32 (รันเฟิร์มแวร์ micro-ROS) |
| LiDAR | RPLiDAR (publish `/scan`) |
| กล้อง | ESP32 Camera Module (แยก agent) |
| Servo | ใช้ปล่อยของ (payload drop) ผ่าน `/servo_s1` |
| Sensor อื่น ๆ | IMU, Battery monitor, Buzzer |
| USB | CP210x (มี driver ใน `Driver/` สำหรับ Windows) |

---

## 3. Software Stack

- **OS:** Ubuntu + ROS 2 Humble
- **Container:** Docker → `microros/micro-ros-agent:humble`
- **SLAM:** `slam_toolbox` (online_async mode)
- **Navigation:** `Nav2` (RPP controller default, มี DWB ให้เลือก)
- **Vision:** OpenCV + MediaPipe Pose + `pupil-apriltags` (tag36h11)
- **Bringup package:** `yahboomcar_bringup`, `yahboom_esp32_camera`
- **Custom msgs:** `yahboomcar_msgs` (มี `PointArray`)
- **Teleop:** keyboard + LiDAR safety stop (~30 cm)

---

## 4. ROS Topics หลัก

| Topic | Type | ทิศทาง | หมายเหตุ |
|---|---|---|---|
| `/cmd_vel` | `geometry_msgs/Twist` | host → robot | ความเร็วเชิงเส้น/เชิงมุม |
| `/scan` | `sensor_msgs/LaserScan` | robot → host | LiDAR |
| `/imu` | `sensor_msgs/Imu` | robot → host | IMU |
| `/battery` | `std_msgs/UInt16` | robot → host | ค่า = โวลต์ × 10 |
| `/servo_s1` | `std_msgs/Int32` | host → robot | **-40 = ปล่อย, 0 = อาร์ม** (pulse, ไม่ latch) |
| `/beep` | `std_msgs/UInt16` | host → robot | เสียง buzzer |
| `/espRos/esp32camera` | image | camera → host | ภาพจาก ESP32 cam |
| `/mediapipe/points` | `yahboomcar_msgs/PointArray` | host → host | landmark มนุษย์ |
| `/vision/latest_at_id` | `std_msgs/String` | host → host | ID AprilTag ล่าสุด |

---

## 5. การตั้งค่าหุ่นยนต์ (Robot Config)

ตั้งค่าผ่าน **USB Serial** ก่อนใช้งานครั้งแรก (สคริปต์ `start_up_robot/config_robot.py`)

- **Port:** `/dev/ttyUSB0`
- **Baudrate:** 115200
- **โปรโตคอล:** binary, head `0xFF`, device id `0xF8`, return id `0xF7`

ค่าที่ตั้งได้ (อ้างอิงจากตาราง `ORDER` ในโค้ด):

| คำสั่ง | Address |
|---|---|
| WIFI_SSID | 0x01 |
| WIFI_PASSWD | 0x02 |
| AGENT_IP | 0x03 |
| AGENT_PORT | 0x04 |
| CAR_TYPE | 0x05 |
| DOMAIN_ID | 0x06 |
| SERIAL_BAUDRATE | 0x07 |
| SERVO_OFFSET | 0x08 |
| MOTOR_PID | 0x09 |
| IMU_YAW_PID | 0x0A |
| ROS_NAMESPACE | 0x0B |
| REBOOT_DEVICE | 0x20 |
| RESET_CONFIG | 0x21 |
| REQUEST_DATA | 0x50 |
| FIRMWARE_VERSION | 0x51 |

**ค่าตัวอย่างที่ใช้ในห้องเรียน:**
- Wi-Fi: `wifi-inex` / `123456789-0`
- Agent IP/Port: `<REDACTED-IP>:8090`
- Domain ID: 99
- ROS Serial Baudrate: 921600
- Motor PID: 1, 0.2, 0.2
- IMU YAW PID: 1, 0, 0.2

---

## 6. micro-ROS Agent (Docker)

รัน Agent 2 ตัวพร้อมกัน คนละพอร์ต:

```bash
# Robot base (port 8090)
docker run -it --rm --name uros_agent_8090 \
  -v /dev:/dev -v /dev/shm:/dev/shm \
  --privileged --net=host \
  microros/micro-ros-agent:humble udp4 --port 8090 -v4

# ESP32 Camera (port 9999)
docker run -it --rm --name uros_agent_9999 \
  -v /dev:/dev -v /dev/shm:/dev/shm \
  --privileged --net=host \
  microros/micro-ros-agent:humble udp4 --port 9999 -v4
```

มีสคริปต์ wrapper ให้แล้ว: `start_agent_computer.sh` และ `start_Camera_computer.sh`

---

## 7. Workflow 3 เฟส

### เฟส 1: Bring-up (`microROS-X_Example/start_up_robot/`)

```bash
./start_agent_computer.sh     # เปิด agent หุ่นยนต์
./start_Camera_computer.sh    # เปิด agent กล้อง
./check_robot.sh              # เปิด 3 หน้าต่าง: cam viewer + teleop + vision
```

ไฟล์สำคัญ:
- `config_robot.py` — class `MicroROS_Robot` ตั้งค่าผ่าน serial
- `ctrl_robot.py` — keyboard teleop + LiDAR safety stop (30 cm) + servo control (`p`)
- `Cam_Pose_AprilTag.py` — MediaPipe pose + AprilTag detection + dashboard
- `watchdog.py` — แสดงสถานะ camera/IMU/battery real-time
- `SET_Camera.py`, `config_camera.py` — ตั้งค่ากล้อง ESP32

### เฟส 2: SLAM Mapping (`microROS-X_Example/slam_map/`)

```bash
./slam_map.sh         # launch slam_toolbox + RViz
# ขับหุ่นด้วย ctrl_robot.py จากเฟส 1
./save_map.sh         # บันทึก my_robot_map.pgm + .yaml
```

พารามิเตอร์ SLAM ที่ใช้ (`map_slamtoolbox_launch.py`):
- `resolution`: 0.05 (5 cm/pixel)
- `max_laser_range`: 3.0 m
- `minimum_travel_distance`: 0.15 m
- `minimum_travel_heading`: 0.05 rad (~2.8°)
- `do_loop_closing`: true
- TF offset: `base_link → laser_frame` = (-0.0046412, 0, 0.094079)

### เฟส 3: Navigation (`microROS-X_Example/navigator_map/`)

```bash
ros2 launch nav2_launch.py                       # default เปิด RViz
ros2 launch nav2_launch.py open_rviz:=false      # ไม่เปิด RViz
python3 navigator_script.py                       # วิ่งตาม waypoints
```

ไฟล์สำคัญ:
- `nav2_launch.py` — รวม yahboomcar_bringup + nav2_bringup (default: RPP controller)
- `navigator_script.py` — loop อ่าน waypoints + เรียก mission_script ที่จุดที่ไม่ใช่ HOME
- `mission_script.py` — รอ pose มนุษย์สูงสุด 5 วิ → สั่ง servo `-40` → รอ 1 วิ → กลับ `0`
- `nav_waypoints.yaml` — รายการ waypoints (reload ทุก loop, แก้ขณะรันได้)
- `get_waypoint.py` / `ctrl_robot_get_waypoint.py` — capture pose ปัจจุบัน → append เข้า YAML
- `cal_yaw.py` — แปลง yaw เป็น quaternion z/w

รูปแบบ `nav_waypoints.yaml`:
```yaml
waypoints:
- task: waypoint_1
  x: 2.354
  y: -0.488
  orientation:
    z: 0.70791
    w: 0.90631
- task: HOME           # ชื่อ HOME = ไม่รัน mission แค่กลับจุดเริ่ม
  x: 0.0
  y: 0.0
  orientation: {z: 0.0, w: 1.0}
```

Controller มี 2 ตัวให้เลือก:
- `prarams/rpp_nav_params.yaml` (default — Regulated Pure Pursuit)
- `prarams/dwb_nav_params.yaml` (DWB — ต้องแก้ใน launch file เพื่อสลับ)

---

## 8. ตัวอย่างโค้ดเบื้องต้น (`code_basic/`)

สคริปต์ทดสอบสั้น ๆ สำหรับเรียนรู้ทีละ topic:

| ไฟล์ | ทดสอบ |
|---|---|
| `test_cmd_vel.py` | publish `/cmd_vel` หมุน 0.5 rad/s 10 วิ แล้วหยุด |
| `test_beep.py` | publish `/beep` |
| `test_drop.py` | publish `/servo_s1` ปล่อยของ |
| `test_humanDetection.py` | subscribe `/mediapipe/points` |

---

## 9. Firmware

ใน `firmware/`:
- `microROS_Robot_2025_3.bin` (ใหม่)
- `microROS_Robot_V2.1.0.bin`

ขั้นตอนการ flash อ้างอิงจากสไลด์ `Appendix 1 - Firmware Update.pptx`

---

## 10. Vision Pipeline

```
ESP32 Camera ─► /espRos/esp32camera ─► Cam_Pose_AprilTag.py
                                            │
                                            ├─► MediaPipe Pose
                                            │     └─► /mediapipe/points (PointArray)
                                            │
                                            └─► pupil-apriltags (tag36h11)
                                                  └─► /vision/latest_at_id (String)
```

ใช้ AprilTag จากไฟล์ `Tag36h11_00-31_.pdf` (ID 0–31) ติดในสนามเพื่อระบุตำแหน่ง/จุดสำคัญ

---

## 11. Mission Logic (ค่าเริ่มต้น)

`navigator_script.py` + `mission_script.py` ทำงานร่วมกันแบบนี้:

1. อ่าน `nav_waypoints.yaml`
2. วน waypoint ทีละจุด → ส่งเป้าหมายให้ Nav2
3. เมื่อถึงจุด:
   - ถ้าชื่อ = `HOME` → แค่หยุด 2 วิ
   - ถ้าอื่น ๆ → `subprocess.run(["python3", "mission_script.py"])` (blocking)
     - subscribe `/mediapipe/points` รอตรวจคน
     - เจอ → publish `/servo_s1 = -40` (ปล่อย) → 1 วิ → publish `0` (อาร์ม) → จบ
     - ไม่เจอภายใน 5 วิ → timeout จบ
4. ไป waypoint ถัดไป
5. จบ list แล้ว loop ใหญ่จะ reload YAML ใหม่ (แก้ไฟล์ระหว่างรันได้)

---

## 12. จุดที่ต้องระวัง (Gotchas)

1. **โฟลเดอร์ `prarams/`** — สะกดผิดในโค้ดจริง (`prarams` ไม่ใช่ `params`) อย่าเปลี่ยนชื่อข้างเดียว
2. **Relative path** — launch files ใช้ `os.path.abspath()` กับ CWD ต้องรันจากในโฟลเดอร์เฟสนั้น ๆ
3. **TF offset ซ้ำ 2 ที่** — `slam_map/map_slamtoolbox_launch.py` กับ `navigator_map/nav2_launch.py` มี static TF `base_link → laser_frame` เหมือนกัน แก้แล้วต้องแก้ทั้งคู่
4. **ไม่ใช่ ROS package** — ไม่มี `setup.py`/`package.xml` รันด้วย path ตรง ๆ
5. **Servo เป็น pulse** — ต้องสั่ง `-40` แล้วตามด้วย `0` เพื่อ reset อย่า latch ค้าง
6. **ภาษาไทยใน comments/prints** — รักษาภาษาเดิมเวลาแก้
7. **Domain ID ต้องตรงกัน** — host PC ต้อง `export ROS_DOMAIN_ID=99` ให้ตรงกับที่ตั้งไว้ในหุ่น
8. **ต้อง copy map ข้ามเฟส** — `my_robot_map.yaml/.pgm` ที่ save จาก slam_map ต้องเอาไปวางใน navigator_map ก่อนรัน Nav2

---

## 13. คอร์สเอกสาร (.pptx)

| ไฟล์ | เนื้อหา |
|---|---|
| 0. microROS Robot Introduction | แนะนำหุ่นและระบบโดยรวม |
| 1.1 / 1.2 / 1.3 | การติดตั้ง (VM Yahboom / ISO INEX / WiFi Camera) |
| 2. microROS Agent Connection | ตั้งค่า + เชื่อม Agent |
| 3. LiDAR Course | การใช้ LiDAR |
| Appendix 1 | Firmware update |
| B1–B4 | คอร์สพื้นฐาน Python / ROS2 / ROS2-Python / Linux |

---

## 14. คำสั่งที่ใช้บ่อย

```bash
# ตรวจว่าหุ่นเชื่อมต่อ ROS graph ได้แล้ว
ros2 topic list
ros2 topic echo /battery
ros2 topic echo /scan --once

# ขับด้วยมือ
cd microROS-X_Example/start_up_robot && python3 ctrl_robot.py

# ทำแผนที่
cd microROS-X_Example/slam_map && ./slam_map.sh
# ... ขับวน ...
./save_map.sh

# Nav
cd microROS-X_Example/navigator_map
ros2 launch nav2_launch.py
python3 navigator_script.py

# เพิ่ม waypoint ขณะใช้งาน
python3 get_waypoint.py        # capture pose ปัจจุบันลง YAML
```
