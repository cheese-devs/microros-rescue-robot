#!/usr/bin/env python3
# encoding: utf-8

import subprocess
import socket
import time
import os
import sys

GREEN  = '\033[92m'
RED    = '\033[91m'
YELLOW = '\033[93m'
CYAN   = '\033[96m'
RESET  = '\033[0m'
BOLD   = '\033[1m'

EXPECTED_TOPICS = [
    '/imu',
    '/battery',
    '/cmd_vel',
    '/odom_raw',
    '/scan',
    '/beep',
    '/servo_s1',
    '/servo_s2',
    '/espRos/esp32camera',
]

EXPECTED_NODES = [
    'micro_ros_agent',
]

AGENT_PORTS = [8090, 9999]
EXPECTED_CONTAINERS = ['uros_agent_9999']


def ok(msg):   return f"{GREEN}[OK]{RESET}    {msg}"
def fail(msg): return f"{RED}[FAIL]{RESET}  {msg}"
def warn(msg): return f"{YELLOW}[WARN]{RESET}  {msg}"
def info(msg): return f"{CYAN}[INFO]{RESET}  {msg}"


def run(cmd):
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", 1


def check_ros2_daemon():
    out, rc = run("ros2 daemon status")
    if rc == 0 and "running" in out.lower():
        return True, out
    return False, out


def check_topics():
    out, rc = run("ros2 topic list")
    if rc != 0 or not out:
        return [], []
    active = out.splitlines()
    found    = [t for t in EXPECTED_TOPICS if t in active]
    missing  = [t for t in EXPECTED_TOPICS if t not in active]
    return found, missing


def check_topic_hz(topic, duration=2):
    out, _ = run(f"timeout {duration} ros2 topic hz {topic} 2>&1 | head -5")
    return out


def check_nodes():
    out, rc = run("ros2 node list")
    if rc != 0 or not out:
        return [], [], EXPECTED_NODES
    active  = out.splitlines()
    found   = [n for n in EXPECTED_NODES if any(n in a for a in active)]
    missing = [n for n in EXPECTED_NODES if not any(n in a for a in active)]
    return active, found, missing


def check_micro_ros_agent_process():
    out, rc = run("pgrep -a micro_ros_agent")
    return rc == 0, out


def check_agent_port(port):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        s.bind(('', port))
        s.close()
        return False  # port ว่าง = ไม่มีใครใช้
    except OSError:
        return True   # port ถูกใช้อยู่


def check_docker_containers():
    out, rc = run("docker ps --format '{{.Names}}\t{{.Status}}\t{{.Ports}}'")
    if rc != 0:
        return None, []  # docker ไม่ได้ติดตั้ง หรือ daemon ไม่รัน
    running = []
    for line in out.splitlines():
        parts = line.split('\t')
        name   = parts[0] if len(parts) > 0 else ''
        status = parts[1] if len(parts) > 1 else ''
        ports  = parts[2] if len(parts) > 2 else ''
        running.append({'name': name, 'status': status, 'ports': ports})
    return True, running


def check_domain_id():
    domain_id = os.environ.get('ROS_DOMAIN_ID', '0')
    return domain_id


def check_ros2_doctor():
    out, rc = run("ros2 doctor --report 2>&1 | head -30")
    return rc == 0, out


def separator(title=""):
    w = 55
    if title:
        pad = (w - len(title) - 2) // 2
        print(f"\n{'─'*pad} {BOLD}{title}{RESET} {'─'*pad}")
    else:
        print("─" * w)


def main():
    print(f"\n{'═'*55}")
    print(f"  {BOLD}ROS2 / microROS Connection Status Check{RESET}")
    print(f"  {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'═'*55}")

    # 1. Domain ID
    separator("Environment")
    domain_id = check_domain_id()
    print(info(f"ROS_DOMAIN_ID = {domain_id}"))
    if domain_id == '0':
        print(warn("Domain ID is 0 (default). Robot uses 20 — set ROS_DOMAIN_ID=20"))

    # 2. ROS2 daemon
    separator("ROS2 Daemon")
    alive, msg = check_ros2_daemon()
    if alive:
        print(ok("ROS2 daemon is running"))
    else:
        print(fail("ROS2 daemon is NOT running"))
        print(warn("Run: ros2 daemon start"))

    # 3. micro-ROS agent process
    separator("micro-ROS Agent")
    proc_running, proc_info = check_micro_ros_agent_process()
    if proc_running:
        print(ok(f"micro_ros_agent process found"))
        print(info(f"  {proc_info}"))
    else:
        print(fail("micro_ros_agent process NOT found"))

    for port in AGENT_PORTS:
        if check_agent_port(port):
            print(ok(f"UDP port {port} is in use (agent listening)"))
        else:
            print(warn(f"UDP port {port} is free (agent may not be running)"))

    # 4. Docker containers
    separator("Docker Containers")
    docker_ok, containers = check_docker_containers()
    if docker_ok is None:
        print(warn("Docker not available"))
    elif not containers:
        print(warn("No running containers"))
        for name in EXPECTED_CONTAINERS:
            print(fail(f"Expected container not running: {name}"))
    else:
        running_names = [c['name'] for c in containers]
        for c in containers:
            print(info(f"  {c['name']:25} {c['status']}"))
        for name in EXPECTED_CONTAINERS:
            if name in running_names:
                print(ok(f"Container '{name}' is running"))
            else:
                print(fail(f"Expected container not running: {name}"))

    # 5. Nodes
    separator("Active Nodes")
    all_nodes, found_nodes, missing_nodes = check_nodes()
    if all_nodes:
        for n in all_nodes:
            print(info(f"  {n}"))
    else:
        print(warn("No nodes found"))

    if missing_nodes:
        for n in missing_nodes:
            print(fail(f"Expected node not found: {n}"))

    # 5. Topics
    separator("Topics")
    found_topics, missing_topics = check_topics()

    for t in found_topics:
        print(ok(t))
    for t in missing_topics:
        print(fail(f"{t}  (not published)"))

    # 6. Topic frequency check (เฉพาะที่พบ)
    if found_topics:
        separator("Topic Frequency (2s sample)")
        hz_targets = [t for t in ['/imu', '/battery', '/espRos/esp32camera'] if t in found_topics]
        for topic in hz_targets:
            hz_out = check_topic_hz(topic, duration=2)
            # ดึงแค่บรรทัด average rate
            rate_line = next((l for l in hz_out.splitlines() if 'average rate' in l), None)
            if rate_line:
                print(ok(f"{topic}  →  {rate_line.strip()}"))
            else:
                print(warn(f"{topic}  →  no rate data"))

    # 7. สรุป
    separator("Summary")
    issues = []
    if not alive:
        issues.append("ROS2 daemon not running")
    any_port_used = any(check_agent_port(p) for p in AGENT_PORTS)
    if not proc_running and not any_port_used:
        issues.append("micro-ROS agent not running")
    if docker_ok is not None:
        running_names = [c['name'] for c in containers]
        for name in EXPECTED_CONTAINERS:
            if name not in running_names:
                issues.append(f"Docker container '{name}' is not running")
    if missing_topics:
        issues.append(f"{len(missing_topics)} expected topic(s) missing: {', '.join(missing_topics)}")
    if domain_id != '20':
        issues.append(f"ROS_DOMAIN_ID={domain_id} (expected 20 for this robot)")

    if not issues:
        print(f"\n  {GREEN}{BOLD}All checks passed — ROS2 connection looks healthy!{RESET}\n")
    else:
        print(f"\n  {RED}{BOLD}Issues found:{RESET}")
        for i in issues:
            print(f"  {RED}•{RESET} {i}")
        print()

    print(f"{'═'*55}\n")


if __name__ == '__main__':
    main()
