import cv2
import numpy as np
import pyrealsense2 as rs
import time
import threading
import math
import sys
import traceback
import os
import socket
import json

from serial.tools import list_ports
from pydobot import Dobot
from pydobot.message import Message 

from flask import Flask, render_template, Response
from flask_socketio import SocketIO

# ==========================================
# ▼ [설정] 통신 및 로봇 연결
# ==========================================
# Windows PC가 서버가 되므로, 여기서 TURTLEBOT_IP는 사용되지 않거나 로깅용으로만 씁니다.
# TURTLEBOT_PORT는 서버가 리스닝할 포트입니다.
TURTLEBOT_PORT = 65432           
DOBOT_PORT = None  

# ==========================================
# ▼ [중요] 적재 위치 및 알고리즘 설정
# ==========================================
SAFE_Z_HEIGHT = 100.0   # 이동 시 안전 높이
FLOOR_Z = -60.0         # 바닥 높이

# 전체 목표 개수 (초기값 0, HTML에서 받아옴)
MAX_STACK_COUNT = 0     

# 작업 완료 후 보낼 터틀봇 신호 목록 (예: ['A', 'B'])
MISSION_SIGNALS = []

# 구역별 좌표
DROP_ZONES = {
    'red':    {'x': -35.0,  'y': -170.0},
    'blue':   {'x': 41.0,   'y': -170.0},
    'yellow': {'x': 120.0,  'y': -171.0},
    'white_1': {'x': 220.0,  'y': -34.0},
    'white_2': {'x': 220.0,  'y': -90.0},
    'white_3': {'x': 150.0,  'y': -34.0},
    'white_4': {'x': 150.0,  'y': -90.0},
    'reject': {'x': 190.0,  'y': 20.0},
    'overflow': {'x': 225.0, 'y': 30.0}
}

LIMIT_STACK_HEIGHT = 100.0 

# ==========================================
# ▼ 전역 변수
# ==========================================
stop_event = threading.Event()
output_frame = None
lock = threading.Lock()
dobot_device = None 
turtlebot_conn = None  # [수정] 터틀봇과 연결된 소켓 객체 저장

# [수정] 색상별 적재 높이 관리를 위해 키 추가 (red, yellow, blue)
stack_status = {
    'white_1': 0.0, 'white_2': 0.0, 'white_3': 0.0, 'white_4': 0.0,
    'overflow': 0.0,
    'red': 0.0, 'yellow': 0.0, 'blue': 0.0 
}

EXPECTED_INVENTORY = {
    '7': 0, '5': 0, '4': 0, '3': 0, '2': 0,
    'red': 0, 'yellow': 0, 'blue': 0
}

# ==========================================
# ▼ 로봇/비전 캘리브레이션 값
# ==========================================
GROUND_DISTANCE_MM = 288.0   
THRESHOLD_HEIGHT = 10.0
ROI_X_START, ROI_X_END = 300, 440
ROI_Y_START, ROI_Y_END = 200, 430
TRIGGER_X = 370               

ALPHA_X = -0.278
ALPHA_Y = -0.045
SCALE = 0.984                 
THETA = np.radians(-16.94)   
OFFSET_X = 16.48
OFFSET_Y = 84.63

HOME_POSE = [150.0, 0.0, 100.0, 0.0] 

# [수정] 색깔 큐브 높이(25.0)를 후보군에 추가하여 정확한 인식 유도
CANDIDATE_HEIGHTS = [20.0, 25.0, 30.0, 40.0, 50.0, 70.0]

CONVEYOR_SPEED = 18.10        
CONVEYOR_ANGLE_DEG = 7.33     
INTERCEPT_TIME = 4.0          

conv_rad = math.radians(CONVEYOR_ANGLE_DEG)
V_X = CONVEYOR_SPEED * math.cos(conv_rad) 
V_Y = CONVEYOR_SPEED * math.sin(conv_rad) 

# ==========================================
# ▼ Flask 서버
# ==========================================
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, async_mode='threading', cors_allowed_origins="*")

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('start_simulation')
def handle_start(data):
    global LIMIT_STACK_HEIGHT, stack_status, EXPECTED_INVENTORY, MAX_STACK_COUNT, MISSION_SIGNALS
    
    if 'limit_height' in data:
        LIMIT_STACK_HEIGHT = float(data['limit_height']) * 10.0
    
    if 'inventory' in data:
        EXPECTED_INVENTORY = data['inventory']
    
    MAX_STACK_COUNT = sum(int(val) for val in EXPECTED_INVENTORY.values())
    
    # [수정] 초기화 시 색상 키도 포함되도록 리셋
    stack_status = {
        'white_1': 0.0, 'white_2': 0.0, 'white_3': 0.0, 'white_4': 0.0,
        'overflow': 0.0,
        'red': 0.0, 'yellow': 0.0, 'blue': 0.0
    }

    MISSION_SIGNALS = []
    inv = data.get('inventory', {})
    
    if int(inv.get('red', 0)) > 0:
        MISSION_SIGNALS.append('A')
    if int(inv.get('yellow', 0)) > 0:
        MISSION_SIGNALS.append('B')
    if int(inv.get('blue', 0)) > 0:
        MISSION_SIGNALS.append('C')
    
    socketio.emit('init_grid', {'limit_height': LIMIT_STACK_HEIGHT / 10.0})
    
    print(f"\n===== [시뮬레이션 시작] =====")
    print(f" - 제한 높이: {LIMIT_STACK_HEIGHT}mm")
    print(f" - 총 작업 목표 개수: {MAX_STACK_COUNT}개")
    print(f" - 완료 시 전송 신호: {MISSION_SIGNALS}")
    print(f"=============================\n")

# --- 긴급 정지 핸들러 ---
@socketio.on('emergency_stop')
def handle_emergency_stop():
    global dobot_device, stop_event
    print("\n🚨 [WEB] 긴급 정지 신호 수신!")
    stop_event.set() 
    
    if dobot_device and dobot_device.device:
        try:
            dobot_device.device.suck(False) 
            msg = Message()
            msg.id = 20 
            dobot_device.device._send_command(msg)
            print(">> 로봇 하드웨어 정지 명령 전송 완료.")
        except Exception as e:
            print(f"!! 정지 명령 중 오류: {e}")
    socketio.emit('log', {'msg': '🚨 긴급 정지로 인해 시스템이 중단되었습니다.'})

# --- 홈밍 핸들러 ---
@socketio.on('go_home')
def handle_go_home():
    global dobot_device
    print("\n🏠 [WEB] 홈밍 신호 수신!")
    if dobot_device and dobot_device.device:
        try:
            if not dobot_device.is_mission_busy:
                threading.Thread(target=perform_manual_homing).start()
                socketio.emit('log', {'msg': '🏠 홈밍(Homing)을 수행합니다. (20초 소요)'})
            else:
                socketio.emit('log', {'msg': '⚠️ 현재 작업 중이므로 홈밍을 수행할 수 없습니다.'})
        except Exception as e:
            print(f"!! 홈밍 중 오류: {e}")

def perform_manual_homing():
    global dobot_device
    if dobot_device and dobot_device.device:
        msg = Message()
        msg.id = 31 
        msg.ctrl = 0x03
        dobot_device.device._send_command(msg)
        time.sleep(20)
        dobot_device.move_to(HOME_POSE[0], HOME_POSE[1], HOME_POSE[2], HOME_POSE[3])
        print(">> 홈밍 수동 완료.")

def gen_frames():
    global output_frame, lock
    while not stop_event.is_set():
        with lock:
            if output_frame is None:
                time.sleep(0.1)
                continue
            ret, buffer = cv2.imencode('.jpg', output_frame)
        if not ret: continue
        yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        time.sleep(0.05)

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# ==========================================
# ▼ 유틸리티 함수
# ==========================================
def transform_to_robot(tx, ty, obj_height):
    corrected_tx = tx - (obj_height * ALPHA_X)
    corrected_ty = ty - (obj_height * ALPHA_Y)
    s_cx = corrected_tx * SCALE
    s_cy = corrected_ty * SCALE
    rx = (s_cx * np.cos(THETA) - s_cy * np.sin(THETA)) + OFFSET_X
    ry = (s_cx * np.sin(THETA) + s_cy * np.cos(THETA)) + OFFSET_Y
    return rx, ry

def find_closest_height(measured_h):
    closest = min(CANDIDATE_HEIGHTS, key=lambda x: abs(x - measured_h))
    return closest

def get_object_angle(rect):
    (cx, cy), (w, h), angle = rect
    if w < h: angle += 90
    if angle > 90: angle -= 180
    elif angle < -90: angle += 180
    return angle

def determine_color(image_roi):
    hsv = cv2.cvtColor(image_roi, cv2.COLOR_BGR2HSV)
    
    lower_red1 = np.array([0, 50, 50]); upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([170, 50, 50]); upper_red2 = np.array([180, 255, 255])
    lower_yellow = np.array([15, 50, 50]); upper_yellow = np.array([45, 255, 255])
    lower_blue = np.array([95, 50, 50]); upper_blue = np.array([140, 255, 255])
    lower_white = np.array([0, 0, 120]); upper_white = np.array([180, 60, 255])

    mask_red = cv2.bitwise_or(cv2.inRange(hsv, lower_red1, upper_red1), cv2.inRange(hsv, lower_red2, upper_red2))
    mask_yellow = cv2.inRange(hsv, lower_yellow, upper_yellow)
    mask_blue = cv2.inRange(hsv, lower_blue, upper_blue)
    mask_white = cv2.inRange(hsv, lower_white, upper_white)
    
    cnt_red = cv2.countNonZero(mask_red)
    cnt_yellow = cv2.countNonZero(mask_yellow)
    cnt_blue = cv2.countNonZero(mask_blue)
    cnt_white = cv2.countNonZero(mask_white)

    threshold_count = 50 
    counts = {"red": cnt_red, "yellow": cnt_yellow, "blue": cnt_blue, "white": cnt_white}
    best_color = max(counts, key=counts.get)
    max_val = counts[best_color]
    
    if best_color == "red" and cnt_white > (cnt_red * 0.5) and cnt_white > threshold_count:
         return "white"

    if max_val > threshold_count:
        return best_color
    return "white"

def get_inventory_key(color, height):
    if color != 'white':
        return color 
    else:
        return str(int(height / 10))

# ==========================================
# ▼ [신규] TCP 서버 및 신호 전송 함수
# ==========================================
def start_tcp_server():
    global turtlebot_conn
    HOST = '0.0.0.0'  # 모든 IP에서의 접속 허용
    PORT = TURTLEBOT_PORT  # 65432
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(1)
    
    print(f"\n🎧 [Windows Server] 터틀봇 접속 대기 중... (Port: {PORT})")
    
    while not stop_event.is_set():
        try:
            # 터틀봇 접속 대기 (Blocking)
            conn, addr = server_socket.accept()
            turtlebot_conn = conn
            print(f"\n✅ [Windows Server] 터틀봇 연결됨! ({addr})")
            
            # 연결 유지용 루프 (끊어지면 감지하기 위함)
            while True:
                data = conn.recv(1024)
                if not data:
                    break
        except Exception as e:
            print(f"⚠️ [Server] 연결 끊김 또는 에러: {e}")
        finally:
            if turtlebot_conn:
                turtlebot_conn.close()
                turtlebot_conn = None
            print("🔄 [Server] 터틀봇 재접속 대기 중...")

def send_turtlebot_signal(signal_char):
    global turtlebot_conn
    print(f">> 터틀봇에게 신호 전송 시도: {signal_char}")
    
    if turtlebot_conn is None:
        print("!! 실패: 터틀봇이 아직 연결되지 않았습니다.")
        return

    try:
        # 이미 연결된 소켓으로 데이터 전송
        msg = str(signal_char) + "\n" 
        turtlebot_conn.sendall(msg.encode('utf-8'))
        print(f">> 전송 성공: {signal_char}")
    except Exception as e:
        print(f"!! 전송 실패 (연결 끊김?): {e}")
        turtlebot_conn = None

# ==========================================
# ▼ 로봇 제어 컨트롤러
# ==========================================
class LocalRobotController:
    def __init__(self):
        global dobot_device
        self.is_mission_busy = False
        self.total_stack_count = 0 
        self.device = None
        self.connect_dobot()
        dobot_device = self 

    def connect_dobot(self):
        global DOBOT_PORT
        try:
            if DOBOT_PORT is None:
                ports = list_ports.comports()
                for port in ports:
                    if "Silicon Labs" in port.description or "USB" in port.description:
                        DOBOT_PORT = port.device
                        break
            
            if DOBOT_PORT is None:
                print("!! 두봇 포트를 찾을 수 없습니다.")
                return

            print(f">> [1단계] 두봇 임시 연결 시도: {DOBOT_PORT}")
            temp_device = Dobot(port=DOBOT_PORT, verbose=False)
            
            print(">> ⚠️ 홈밍(Homing) 명령 전송...")
            msg = Message()
            msg.id = 31
            msg.ctrl = 0x03
            temp_device._send_command(msg)
            
            temp_device.close()
            
            print(">> 로봇이 원점으로 이동 중입니다. (20초 대기)")
            time.sleep(20) 
            
            print(">> [2단계] 두봇 재연결 (Clean Connection)...")
            self.device = Dobot(port=DOBOT_PORT, verbose=False)
            print(">> 두봇 연결 성공! (상태 초기화 완료)")

            self.device.speed(velocity=200, acceleration=200)
            self.move_to(HOME_POSE[0], HOME_POSE[1], HOME_POSE[2], HOME_POSE[3])

        except Exception as e:
            print(f"!! 두봇 연결 또는 홈밍 에러: {e}")
            self.device = None

    def move_to(self, x, y, z, r, wait=True):
        if not self.device or stop_event.is_set():
            return

        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.device.move_to(x, y, z, r, wait=wait)
                return 
            except AttributeError:
                print(f"⚠️ [통신 불안정] 이동 명령 재시도 중... ({attempt+1}/{max_retries})")
                time.sleep(0.1) 
            except Exception as e:
                print(f"!! [이동 에러] {e}")
                time.sleep(0.1)
        
        print("!! [치명적 오류] 3회 재시도 실패. 로봇이 응답하지 않습니다.")

    def set_suction(self, enable):
        if self.device and not stop_event.is_set():
            self.device.suck(enable)

    def calculate_best_fit(self, height):
        global stack_status
        best_zone = None
        min_remaining_space = float('inf')

        for zone_id in ['white_1', 'white_2', 'white_3', 'white_4']:
            current_h = stack_status[zone_id]
            predicted_h = current_h + height
            
            if predicted_h <= LIMIT_STACK_HEIGHT:
                remaining = LIMIT_STACK_HEIGHT - predicted_h
                if remaining < min_remaining_space:
                    min_remaining_space = remaining
                    best_zone = zone_id
        
        return best_zone

    def calculate_target_pos(self, color, height):
        global stack_status, EXPECTED_INVENTORY

        inv_key = get_inventory_key(color, height)
        count = int(EXPECTED_INVENTORY.get(inv_key, 0))
        
        if count <= 0:
            print(f"⚠️ [수량 초과] 반려(Reject) 구역으로 이동: {color} {height}mm")
            pos = DROP_ZONES['reject']
            target_z = FLOOR_Z + height + 5.0 
            return pos['x'], pos['y'], target_z, 'reject'

        # [수정] 컬러 블럭 적재 로직 개선 (Stacking 적용)
        if color in ['red', 'blue', 'yellow']:
            EXPECTED_INVENTORY[color] = max(0, count - 1)
            pos = DROP_ZONES[color]
            
            # 현재 구역의 쌓인 높이 가져오기
            current_stack_h = stack_status[color]
            
            # 목표 Z = 바닥 + 이미 쌓인 높이 + 새 큐브 높이 + 여유분
            target_z = FLOOR_Z + current_stack_h + height + 5.0 
            
            # 높이 업데이트 (누적)
            stack_status[color] += height
            
            return pos['x'], pos['y'], target_z, color

        elif color == 'white':
            best_zone = self.calculate_best_fit(height)
            if best_zone:
                EXPECTED_INVENTORY[inv_key] = max(0, count - 1)
                pos = DROP_ZONES[best_zone]
                target_z = FLOOR_Z + stack_status[best_zone] + height + 5.0
                stack_status[best_zone] += height
                return pos['x'], pos['y'], target_z, best_zone
            else:
                print(f"!! 적재 공간 부족 (Best Fit 실패). Reject.")
                pos = DROP_ZONES['reject']
                target_z = FLOOR_Z + height + 5.0
                return pos['x'], pos['y'], target_z, 'reject'
        else:
            pos = DROP_ZONES['reject']
            target_z = FLOOR_Z + height + 5.0
            return pos['x'], pos['y'], target_z, 'reject'


    def execute_mission(self, start_rx, start_ry, raw_obj_h, pick_r, obj_color):
        if self.is_mission_busy: return
        self.is_mission_busy = True
        
        try:
            mission_start_time = time.time()
            snapped_h = find_closest_height(raw_obj_h)
            
            target_x, target_y, target_z, zone_name = self.calculate_target_pos(obj_color, snapped_h)

            pred_rx = start_rx + (V_X * INTERCEPT_TIME)
            pred_ry = start_ry + (V_Y * INTERCEPT_TIME)
            pick_z = snapped_h - 10.0 
            
            print(f'>>> 감지: [{obj_color}] {snapped_h}mm -> 목표: {zone_name} (Z:{target_z:.1f})')

            # 1. 접근
            self.move_to(pred_rx, pred_ry, pick_z + 20.0, pick_r)

            elapsed = time.time() - mission_start_time
            wait_time = INTERCEPT_TIME - elapsed
            if wait_time > 0: time.sleep(wait_time-0.9)
            
            # 2. 집기
            self.set_suction(True)
            time.sleep(1.0)
            self.move_to(pred_rx, pred_ry, pick_z-3.0, pick_r) 
            time.sleep(0.2) 
            self.move_to(pred_rx, pred_ry, SAFE_Z_HEIGHT, pick_r) 

            if zone_name in ['red', 'blue', 'yellow']:
                print(f">> {zone_name} 진입: 충돌 방지 경유지(X:180) 경유")
                self.move_to(150.0, target_y, SAFE_Z_HEIGHT, 0.0)

            # 3. 이동 및 적재 (각도 보정)
            calc_r = math.degrees(math.atan2(target_y, target_x))
            final_r = calc_r 

            self.move_to(target_x, target_y, SAFE_Z_HEIGHT, final_r) 
            self.move_to(target_x, target_y, target_z, final_r)      
            
            self.set_suction(False) # 놓기
            time.sleep(0.5)
            
            self.move_to(target_x, target_y, SAFE_Z_HEIGHT, 0.0) 

            if zone_name in ['red', 'blue', 'yellow']:
                print(f">> {zone_name} 복귀: 충돌 방지 경유지(X:180 -> Center) 경유")
                self.move_to(180.0, target_y, SAFE_Z_HEIGHT, 0.0)
                self.move_to(150.0, 0.0, SAFE_Z_HEIGHT, 0.0)

            # 4. 웹 UI 업데이트
            socket_data = {
                'type': 'accepted' if zone_name != 'reject' else 'rejected',
                'class': obj_color,
                'height': float(snapped_h) / 10.0,  
                'row': 0, 'col': 0, 'y_start': 0
            }
            if 'white' in zone_name:
                zone_num = int(zone_name.split('_')[1])
                row = 1 if zone_num in [1, 3] else 2
                col = 2 if zone_num in [1, 2] else 1
                current_stack_bottom = stack_status[zone_name] - snapped_h
                socket_data.update({
                    'type': 'accepted', 
                    'row': row, 'col': col, 
                    'y_start': current_stack_bottom / 10.0 
                })
            elif zone_name == 'overflow':
                current_stack_bottom = stack_status['overflow'] - snapped_h
                socket_data.update({
                    'type': 'accepted', 
                    'row': 1, 'col': 0, 
                    'y_start': current_stack_bottom / 10.0 
                })
            elif zone_name == 'reject':
                socket_data['type'] = 'rejected'
            else:
                socket_data['type'] = 'color_cube'
                socket_data['color'] = obj_color
                socket_data['size'] = snapped_h / 10.0 

            socketio.emit('item_event', socket_data)

            # =======================================================
            # 5. 종료 체크 및 멀티 신호 전송 (A, B, C 순차 전송)
            # =======================================================
            if MAX_STACK_COUNT > 0:
                if zone_name != 'reject':
                    self.total_stack_count += 1
                
                print(f"📦 진행 상황: {self.total_stack_count} / {MAX_STACK_COUNT}")
                
                if self.total_stack_count >= MAX_STACK_COUNT: 
                    print('>>> [미션 달성] 터틀봇 출발 신호 전송 시작!')
                    
                    if MISSION_SIGNALS:
                        for sig in MISSION_SIGNALS:
                            send_turtlebot_signal(sig)
                            # 신호 간 충돌 방지를 위한 대기
                            time.sleep(1.0) 
                    else:
                        print(">> 색상 큐브 없음. (기본 완료 처리는 하지만 신호는 없음)")

                    self.total_stack_count = 0 
            
            # 6. 홈 복귀
            self.move_to(HOME_POSE[0], HOME_POSE[1], HOME_POSE[2], HOME_POSE[3])

        except Exception as e:
            print(f"미션 에러: {e}")
            traceback.print_exc()
        finally:
            self.is_mission_busy = False

# ==========================================
# ▼ 비전 루프
# ==========================================
def control_loop(controller):
    global output_frame, lock
    save_dir = "debug_frames"
    if not os.path.exists(save_dir): os.makedirs(save_dir)

    pipeline = rs.pipeline()
    config = rs.config()
    config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
    config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
    
    try:
        profile = pipeline.start(config)
    except Exception as e:
        print(f"카메라 에러: {e}")
        return

    align = rs.align(rs.stream.color)
    intrinsics = profile.get_stream(rs.stream.color).as_video_stream_profile().get_intrinsics()
    depth_scale = profile.get_device().first_depth_sensor().get_depth_scale()

    print(">> 비전 센서 가동 시작")
    is_triggered = False
    frame_count = 0

    try:
        while not stop_event.is_set():
            frames = pipeline.wait_for_frames(timeout_ms=2000)
            if not frames: continue

            raw_color_frame = frames.get_color_frame()
            if not raw_color_frame: continue
            
            display_image = np.asanyarray(raw_color_frame.get_data()).copy()
            aligned_frames = align.process(frames)
            aligned_depth_frame = aligned_frames.get_depth_frame()
            
            if aligned_depth_frame:
                depth_mm = np.asanyarray(aligned_depth_frame.get_data()) * depth_scale * 1000
                
                cv2.rectangle(display_image, (ROI_X_START, ROI_Y_START), (ROI_X_END, ROI_Y_END), (255, 0, 0), 2)
                cv2.line(display_image, (TRIGGER_X, ROI_Y_START), (TRIGGER_X, ROI_Y_END), (0, 0, 255), 2)
                
                mask = np.where((depth_mm > 0) & (GROUND_DISTANCE_MM - depth_mm >= THRESHOLD_HEIGHT), 255, 0).astype(np.uint8)
                mask[:, :ROI_X_START] = 0; mask[:, ROI_X_END:] = 0
                mask[:ROI_Y_START, :] = 0; mask[ROI_Y_END:] = 0

                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                obj_detected = False

                for cnt in contours:
                    if cv2.contourArea(cnt) > 1500:
                        obj_detected = True
                        rect = cv2.minAreaRect(cnt)
                        (cx_float, cy_float), (w, h), angle = rect
                        cx, cy = int(cx_float), int(cy_float)

                        roi_margin = 10
                        roi_x1 = max(0, cx - int(w/2) + roi_margin)
                        roi_y1 = max(0, cy - int(h/2) + roi_margin)
                        roi_x2 = min(640, cx + int(w/2) - roi_margin)
                        roi_y2 = min(480, cy + int(h/2) - roi_margin)
                        
                        detected_class = "white"
                        if roi_x2 > roi_x1 and roi_y2 > roi_y1:
                            roi_img = display_image[roi_y1:roi_y2, roi_x1:roi_x2]
                            detected_class = determine_color(roi_img)

                        box = np.intp(cv2.boxPoints(rect))
                        cv2.drawContours(display_image, [box], 0, (0, 255, 0), 2)
                        cv2.putText(display_image, f"{detected_class}", (cx, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

                        if (MAX_STACK_COUNT > 0) and (not is_triggered) and (abs(cx - TRIGGER_X) < 10) and (not controller.is_mission_busy):
                            if controller.device is None: continue

                            dist_val = aligned_depth_frame.get_distance(cx, cy)
                            if dist_val > 0:
                                point = rs.rs2_deproject_pixel_to_point(intrinsics, [cx, cy], dist_val)
                                tx, ty, tz = [p * 1000 for p in point]
                                oh = GROUND_DISTANCE_MM - tz
                                rx, ry = transform_to_robot(tx, ty, oh)
                                pick_r = get_object_angle(rect) + np.degrees(THETA)
                                
                                threading.Thread(target=controller.execute_mission, 
                                                 args=(rx, ry, oh, pick_r, detected_class)).start()
                                is_triggered = True
                
                if not obj_detected: is_triggered = False

            frame_count += 1
            if frame_count % 30 == 0:
                cv2.imwrite(os.path.join(save_dir, f"frame_{frame_count:05d}.jpg"), display_image)

            with lock:
                output_frame = display_image.copy()

    except Exception as e:
        traceback.print_exc()
    finally:
        pipeline.stop()
        if controller.device: controller.device.close()

def main():
    # 1. TCP 서버 스레드 시작 (터틀봇 접속 대기)
    server_thread = threading.Thread(target=start_tcp_server, daemon=True)
    server_thread.start()

    # 2. 로봇 컨트롤러
    controller = LocalRobotController()
    control_thread = threading.Thread(target=control_loop, args=(controller,))
    control_thread.start()
    
    # 3. Flask 서버
    flask_thread = threading.Thread(
        target=socketio.run, 
        args=(app,), 
        kwargs={'host':'0.0.0.0', 'port':5000, 'debug':False, 'allow_unsafe_werkzeug':True}, 
        daemon=True
    )
    flask_thread.start()
    print(">> 시스템 실행 중 (웹페이지에서 '시뮬레이션 시작'을 눌러주세요)")

    try:
        while control_thread.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        stop_event.set()
        control_thread.join()
        sys.exit(0)

if __name__ == '__main__':
    main()