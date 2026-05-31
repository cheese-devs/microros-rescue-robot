# บทเรียนวันแข่งจริง — RRR26 (30-31 พ.ค. 2569)

สรุปจาก log วันแข่ง (`~/.ros/log/python3_*.log`). **ผลรวม: ผ่านทุกรอบ** — ระบบทำงานสะอาด ไม่มี FAILED / recovery loop ใน navigator/mission เลย เก็บไว้เป็น reference สำหรับครั้งหน้า.

---

## 1. สรุปผลที่เกิดขึ้นจริง

| ด้าน | ผลวันแข่ง |
|---|---|
| Vision (AprilTag) | อ่าน ID ได้ **โหวต 100% ทุกครั้ง** — 115 (6/6, 9/9), 112 (17/17), 109 (11/11 ×2 รอบ) |
| ตัดสิน tag | จบใน WARMUP 2.5s ทุกครั้ง — **spin fallback ไม่เคยถูกเรียกใช้จริง** |
| Servo (person) | `ปล่อยทันที (ข้าม detection)` ทำงานครบทุกจุด จบ ~2.8-5.7s/จุด ไม่พลาด |
| Navigation | ไม่มี FAILED/ERROR/recovery loop; BackUp 0.6m จุดติดทุก approach แล้วไปต่อได้ |
| เวลา 1 ลูปครบ | ~4 นาที (5 waypoint + HOME) — อยู่ใต้หน้าต่าง 10 นาทีสบาย ๆ |
| Localization | รอบที่อ่าน log นี้ **ไม่เจอ mislocalization** เลย |

---

## 2. สิ่งที่พิสูจน์แล้วว่าได้ผล (เก็บไว้ ห้ามรื้อ)

1. **person = ปล่อย servo ทันที ข้าม detection** — ตัดความเสี่ยง detection พลาด + ตัดการหมุนหา >10s ที่กรรมการจะสั่ง retry ออกหมด. กฎให้คะแนน "กล่องลงกรอบแดง" ไม่ใช่ "ตรวจเจอคนก่อน" จึงคุ้มสุด.
2. **tag = WARMUP vote 2.5s ยืนนิ่ง** — เพียงพอจริง 100% ของรอบที่อ่าน log นี้. กล้องนิ่ง = อ่านชัด, ไม่ต้องพึ่ง spin. (spin fallback ยังควรเก็บไว้เป็นตาข่ายกันพลาด แต่ไม่ใช่เส้นทางหลัก)
3. **publish servo/cmd ซ้ำทุก 0.1s ตลอด hold** — ผ่านสนามจริง ไม่มีคำสั่งหายจาก DDS race เลย.
4. **footprint สี่เหลี่ยม (ไม่ใช่ robot_radius วงกลม)** — เข้า U-pocket ที่ wp ได้จริง ไม่ติด recovery loop.
5. **BackUp 0.6m เป็น recovery ปกติ** — จุดติดเกือบทุก approach แล้วหุ่นถอย-เข้าใหม่ผ่านได้ทุกครั้ง ไม่ลามเป็น loop. สนามมีกำแพงรอบ + BackUp collision-aware จึงปลอดภัย.
6. **กล้อง ESP32 pre-warm ก่อน detect** — gate `/vision/detect_enable` เปิด-ปิดตรงตาม tag waypoint, เปิดแล้วเจอ tag ภายในเฟรมแรก ๆ.

---

## 3. เช็กลิสต์ก่อนสตาร์ทแต่ละรอบ (จากบทเรียนสะสม)

- [ ] วางหุ่นจุดสตาร์ทเป๊ะ yaw=0 หันหน้า +x — AMCL `set_initial_pose` seed (0,0,0) ถ้าวางเพี้ยนจะ relocalize ผิดพ็อกเก็ต
- [ ] เทียบ md5 `my_robot_map.{pgm,yaml}` ระหว่าง `slam_map/` ↔ `navigator_map/` — map ค้างทำให้ mislocalize แม้ initial_pose ถูก
- [ ] เช็กแบต ≥ ~8.0V — ต่ำกว่านี้ IMU เอ๋อ หุ่นหมุนเองใน RViz (เช็ก voltage ก่อน debug localization)
- [ ] WiFi สนามคนละวง → reflash `config_robot_<wifi>.py` (ทั้ง base :8090 และกล้อง :9999) + power-cycle, ROS_DOMAIN_ID ตรงกัน
- [ ] อัปเดต `nav_waypoints.yaml` ตามตำแหน่งผู้ประสบภัย/tag ที่ประกาศหน้างาน (แก้ระหว่างรันได้ — reload ทุก prompt loop)
- [ ] ปิด RViz วันแข่ง (`OPEN_RVIZ=false`) ลด CPU; ใช้ `watch_pose.py` มอนิเตอร์แบบ headless แทน

---

## 4. ข้อสังเกตเพื่อรอบหน้า

- BackUp จุดติดทุก approach = planner เข้าใกล้ U-pocket แล้วถอย-เข้าใหม่ ทำงานได้แต่กินเวลา ~7-15s/ครั้ง. ถ้าอยากเร็วขึ้นรอบหน้า ลองปรับ approach pose / via ให้เข้าตรงขึ้น ลดการ BackUp.
- รอบที่จบด้วย "Canceling current task" = หมดเวลา/สั่งเอง ไม่ใช่ fail — ปกติของการตัดจบเมื่อครบเวลา.
- ดูบันทึกเต็มใน memory: `project_rrr26_race_results.md`.
