#!/usr/bin/env python3
import rclpy, math, threading, queue, sys, os
from rclpy.node import Node
from sensor_msgs.msg import Imu
from rclpy.qos import QoSProfile, ReliabilityPolicy
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

data_queue = queue.Queue(maxsize=1)
latest = {"pitch": 0.0, "roll": 0.0, "gz": 0.0}
qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE)

class IMUNode(Node):
    def __init__(self):
        super().__init__('imu_monitor_gui')
        self.create_subscription(Imu, '/imu', self.cb, qos)

    def cb(self, msg):
        ax = msg.linear_acceleration.x
        ay = msg.linear_acceleration.y
        az = msg.linear_acceleration.z
        d = {
            "pitch": math.degrees(math.atan2(ax, az)),
            "roll":  math.degrees(math.atan2(ay, az)),
            "gz":    math.degrees(msg.angular_velocity.z),
        }
        try:
            data_queue.put_nowait(d)
        except queue.Full:
            pass

def ros_spin():
    rclpy.init()
    rclpy.spin(IMUNode())

threading.Thread(target=ros_spin, daemon=True).start()

fig, axes = plt.subplots(1, 3, figsize=(11, 4), facecolor='#1e1e2e')
fig.suptitle('IMU Monitor', color='white', fontsize=14, fontweight='bold')

titles  = ['Pitch\n(หน้า/หลัง)', 'Roll\n(ซ้าย/ขวา)', 'Spin\n(หมุน)']
ranges  = [(-90, 90), (-90, 90), (-180, 180)]
colors  = ['#f38ba8', '#89dceb', '#a6e3a1']

def draw_gauge(ax, title, value, vmin, vmax, color):
    ax.cla()
    ax.set_facecolor('#2a2a3e')
    ax.set_xlim(-1.4, 1.4)
    ax.set_ylim(-1.4, 1.4)
    ax.set_aspect('equal')
    ax.axis('off')
    ax.set_title(title, color='white', fontsize=11, pad=8)

    ax.add_patch(plt.Circle((0,0), 1.1, color='#3a3a5e', zorder=1))
    ax.add_patch(plt.Circle((0,0), 1.1, fill=False, edgecolor='#555577', linewidth=2, zorder=2))
    ax.plot([-1.0, 1.0], [0,0], color='#555577', linewidth=1, linestyle='--', zorder=3)
    ax.plot([0,0], [-1.0, 1.0], color='#555577', linewidth=1, linestyle='--', zorder=3)

    # clamp value
    value = max(vmin, min(vmax, value))
    angle = math.radians(180 - (value - vmin) / (vmax - vmin) * 180)
    nx = math.cos(angle) * 0.85
    ny = math.sin(angle) * 0.85
    ax.annotate('', xy=(nx, ny), xytext=(0,0),
                arrowprops=dict(arrowstyle='->', color=color, lw=3))
    ax.add_patch(plt.Circle((0,0), 0.07, color=color, zorder=5))
    ax.text(0, -1.3, f'{value:+.1f}°', ha='center', color=color,
            fontsize=16, fontweight='bold')

def update(frame):
    try:
        d = data_queue.get_nowait()
        latest.update(d)
    except queue.Empty:
        pass
    draw_gauge(axes[0], titles[0], latest["pitch"], *ranges[0], colors[0])
    draw_gauge(axes[1], titles[1], latest["roll"],  *ranges[1], colors[1])
    draw_gauge(axes[2], titles[2], latest["gz"],    *ranges[2], colors[2])

def on_close(event=None):
    os._exit(0)

def on_key(event):
    if event.key in ('q', 'Q', 'escape'):
        on_close()

fig.canvas.mpl_connect('close_event', on_close)
fig.canvas.mpl_connect('key_press_event', on_key)
plt.tight_layout()
ani = FuncAnimation(fig, update, interval=150, cache_frame_data=False)
plt.show(block=False)
plt.pause(0.2)

try:
    fig.canvas.manager.window.protocol("WM_DELETE_WINDOW", on_close)
except Exception:
    pass

while plt.fignum_exists(fig.number):
    plt.pause(0.05)
