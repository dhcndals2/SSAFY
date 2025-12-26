import rclpy
from rclpy.node import Node
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
from geometry_msgs.msg import PoseStamped, Twist
from sensor_msgs.msg import BatteryState
from std_msgs.msg import String
from rclpy.executors import MultiThreadedExecutor
import time
import json
import os
import threading
import sys
import socket

# === 설정값 ===
BATTERY_THRESHOLD = 30.0
CHARGING_STATION = [0.0, 0.0, 0.0, 1.0]
TCP_HOST = '127.0.0.1'
TCP_PORT = 65432
ARRIVAL_THRESHOLD = 0.25
MAX_CAPACITY = 5
WAIT_TIME_FIRST = 10.0
WAIT_TIME_ADD = 10.0
UNLOADING_TIME = 8.0
BACKUP_FILE = "task_backup.json"

WAYPOINTS = {
    "A": [2.55, 0.0596, 0.00247, 1.0],
    "B": [1.8, 0.0, 0.0, 1.0],
    #"B": [2.5, 2.21, 0.0247, 1.0],
    "C": [2.06, -0.572, 0.00644, 1.0]
    #"C": [2.18, -1.83, 0.00247, 1.0]
}

class LogisticsRobot(Node):
    def __init__(self):
        super().__init__('logistics_robot_node')
        
        self.current_battery = 100.0
        self.task_queue = []
        self.current_batch = []
        self.force_start = False
        self.is_stopping = False
        
        # TCP 연결 상태 확인용 플래그
        self.is_tcp_connected = False
        
        self.lock = threading.Lock()
        self.load_tasks_from_file()

        # Pub/Sub
        self.status_pub = self.create_publisher(String, '/robot_status', 10)
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.create_subscription(BatteryState, '/battery_state', self.battery_callback, 10)
        self.create_subscription(String, '/turtlebot3_move_command', self.command_callback, 10)

        self.navigator = BasicNavigator()

        # TCP Thread 시작
        self.tcp_thread = threading.Thread(target=self.tcp_client_loop, daemon=True)
        self.tcp_thread.start()
    
    def tcp_client_loop(self):
        """TCP 서버 연결 및 상태 관리"""
        while rclpy.ok():
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(5.0)
                    s.connect((TCP_HOST, TCP_PORT))
                    
                    if not self.is_tcp_connected:
                        self.get_logger().info(f"✅ TCP 서버 연결됨 ({TCP_HOST}:{TCP_PORT})")
                        self.send_log("SYSTEM: TCP Server Connected.")
                        self.is_tcp_connected = True
                    
                    while rclpy.ok():
                        try:
                            data = s.recv(1024)
                            if not data:
                                raise socket.error("Closed")
                            
                            # 서버에서 "A\n"을 보내면 strip()이 \n을 제거하고 "A"만 남김 -> 완벽
                            decoded_data = data.decode('utf-8').strip().upper()
                            
                            # 만약 "A\nB\n" 처럼 뭉쳐 오면 split()이 ['A', 'B']로 나눔 -> 완벽
                            commands = decoded_data.split()
                            for cmd in commands:
                                self.handle_command(cmd)
                                
                        except socket.timeout:
                            continue
                        
            except (socket.error, Exception):
                if self.is_tcp_connected:
                    self.get_logger().warn("⚠️ TCP 연결 끊김. 재접속 대기...")
                    self.send_log("Error: TCP Disconnected.")
                    self.is_tcp_connected = False
                time.sleep(5)
                        
            except (socket.error, Exception):
                # [수정] 연결이 끊겼을 때 한 번만 로그 출력
                if self.is_tcp_connected:
                    self.get_logger().warn("⚠️ TCP 서버 연결 끊김. 재연결 시도 중...")
                    self.send_log("Error: TCP Server Disconnected.")
                    self.is_tcp_connected = False
                
                time.sleep(5) # 5초 후 재시도

    def handle_command(self, data):
        with self.lock:
            if data == "STOP":
                if self.is_stopping: return
                self.is_stopping = True
                self.get_logger().error("🚨 EMERGENCY STOP!")
                self.navigator.cancelTask()
                stop_msg = Twist()
                for _ in range(10): self.cmd_vel_pub.publish(stop_msg)
                self.save_tasks_to_file()
                os._exit(0)
        
            if data in ["GO", "START", "DEPART"]:
                self.force_start = True
                self.get_logger().info("🚀 출발 명령 수신.")
                return

            if data in WAYPOINTS:
                self.task_queue.append(data)
                self.save_tasks_to_file()
                self.get_logger().info(f"📥 큐 추가: '{data}' | 현재 대기열: {self.task_queue}")

    def command_callback(self, msg):
        self.handle_command(msg.data.strip())

    def send_log(self, message):
        msg = String()
        msg.data = message
        self.status_pub.publish(msg)

    def battery_callback(self, msg):
        self.current_battery = msg.percentage

    def save_tasks_to_file(self):
        data = {"queue": self.task_queue, "batch": self.current_batch}
        with open(BACKUP_FILE, 'w') as f:
            json.dump(data, f)

    def load_tasks_from_file(self):
        if os.path.exists(BACKUP_FILE):
            try:
                with open(BACKUP_FILE, 'r') as f:
                    data = json.load(f)
                    self.task_queue = data.get("batch", []) + data.get("queue", [])
            except Exception: pass

    def go_to_pose(self, pose_data):
        goal_pose = PoseStamped()
        goal_pose.header.frame_id = 'map'
        goal_pose.header.stamp = self.get_clock().now().to_msg()
        goal_pose.pose.position.x = pose_data[0]
        goal_pose.pose.position.y = pose_data[1]
        goal_pose.pose.orientation.w = pose_data[3]
        self.navigator.goToPose(goal_pose)

    def run_process_loop(self):
        print("\n🚀 Logistics Robot Ready!")
        while True:
            if self.current_battery < BATTERY_THRESHOLD:
                print("\n🪫 배터리 부족! 홈으로 복귀합니다.")
                self.send_log("Warning: 배터리 부족! 복귀합니다.")
                self.go_to_pose(CHARGING_STATION)
                while not self.navigator.isTaskComplete():
                    fb = self.navigator.getFeedback()
                    if fb and fb.distance_remaining < ARRIVAL_THRESHOLD:
                        self.navigator.cancelTask()
                        break
                    time.sleep(0.5)
                os._exit(0)

            with self.lock:
                queue_empty = (len(self.task_queue) == 0)

            if not queue_empty:
                print("\n" + "="*45)
                print("       📦 LOADING PHASE STARTED       ")
                print("="*45)
                
                with self.lock:
                    self.current_batch = []
                    self.force_start = False
                    item = self.task_queue.pop(0)
                    self.current_batch.append(item)
                    self.save_tasks_to_file()
                
                deadline = time.time() + WAIT_TIME_FIRST
                self.send_log(f"Loading: 물품 '{item}' 적재됨.")

                while True:
                    remaining = deadline - time.time()
                    if remaining <= 0 or self.force_start: break
                    
                    print(f"⏳ 대기: {remaining:.1f}s (적재: {len(self.current_batch)}/{MAX_CAPACITY}) | 강제출발: 'GO'", end='\r')
                    
                    with self.lock:
                        if self.task_queue and len(self.current_batch) < MAX_CAPACITY:
                            new_item = self.task_queue.pop(0)
                            self.current_batch.append(new_item)
                            self.save_tasks_to_file()
                            print(f"\n[+] 추가 적재: '{new_item}'")
                            deadline = max(deadline, time.time() + WAIT_TIME_ADD)
                    time.sleep(0.1)

                print("\n\n🚛 배송을 시작합니다!")
                delivery_list = sorted(list(self.current_batch))
                self.send_log(f"Moving: 배송 시작 (목표: {len(delivery_list)}곳)")

                for target in delivery_list:
                    print(f"📍 '{target}' 구역으로 이동 중...")
                    self.send_log(f"Moving: '{target}' 이동 중")
                    self.go_to_pose(WAYPOINTS[target])
                    
                    while not self.navigator.isTaskComplete():
                        fb = self.navigator.getFeedback()
                        if fb and fb.distance_remaining < ARRIVAL_THRESHOLD:
                            self.navigator.cancelTask()
                            break
                        time.sleep(0.5)
                    
                    print(f"✅ '{target}' 하차 중...")
                    self.send_log(f"Unloading: '{target}' 도착. 하차 중.")
                    time.sleep(UNLOADING_TIME)
                    
                    with self.lock:
                        if target in self.current_batch:
                            self.current_batch.remove(target)
                            self.save_tasks_to_file()
                
                print("\n🏠 홈으로 복귀합니다.")
                self.send_log("Moving: 배송 완료. 복귀합니다.")
                self.go_to_pose(CHARGING_STATION)
                while not self.navigator.isTaskComplete():
                    fb = self.navigator.getFeedback()
                    if fb and fb.distance_remaining < ARRIVAL_THRESHOLD:
                        self.navigator.cancelTask()
                        break
                    time.sleep(0.5)
                print("🏁 대기 장소 도착.")
            else:
                print(f"💤 명령 대기 중... (배터리: {self.current_battery:.1f}%)", end='\r')
                time.sleep(0.5)

def main():
    rclpy.init()
    robot = LogisticsRobot()
    
    # [중요] 스레드를 먼저 시작해서 통신이 가능하게 함
    executor = MultiThreadedExecutor()
    executor.add_node(robot)
    spin_thread = threading.Thread(target=executor.spin, daemon=True)
    spin_thread.start()
    
    # 그 다음 Nav2 활성화 대기 (이제 콜백 처리가 가능하므로 금방 넘어갈 것임)
    print("🛰️  Nav2 활성화 대기 중... (2D Pose Estimate 필요할 수 있음)")
    robot.navigator.waitUntilNav2Active()
    print("✅ Nav2 활성화 완료!")

    try:
        robot.run_process_loop()
    except (KeyboardInterrupt, SystemExit):
        print("\n👋 시스템을 종료합니다.")
    finally:
        rclpy.shutdown()

if __name__ == '__main__':
    main()