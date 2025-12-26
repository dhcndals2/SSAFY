import cv2
import pyrealsense2 as rs
import numpy as np
from ultralytics import YOLO
import time

# ==========================================
# [설정] 사용자 정의 영역
# ==========================================
# 파일 경로 앞에 'r'을 붙여 경로 오류 방지
model_path = r"C:\Users\SSAFY\Desktop\ai_venv\pjtyolo\runs\obb\cube_obb_result\weights\best.pt"

# 인식 신뢰도 (0.5 이상만 감지)
conf_threshold = 0.5

# 리얼센스 해상도 및 FPS
IMG_WIDTH = 640
IMG_HEIGHT = 480
FPS = 30

# [중요] 사다리꼴 ROI (컨베이어 벨트 영역) 좌표 설정
# 순서: [좌측하단, 우측하단, 우측상단, 좌측상단]
# 카메라 화면을 보면서 이 좌표들을 실제 환경에 맞게 조절해야 합니다.
ROI_POINTS = np.array([
    [0, 400],  # 좌측 하단
    [500, 400],  # 우측 하단
    [500, 200],  # 우측 상단 (멀리 있는 쪽)
    [0, 200]   # 좌측 상단 (멀리 있는 쪽)
], dtype=np.int32)
# ==========================================

def is_inside_roi(x, y, roi_points):
    """
    중심점(x, y)이 ROI 다각형 안에 있는지 확인
    """
    result = cv2.pointPolygonTest(roi_points, (x, y), False)
    return result >= 0

def draw_rotated_rect(img, box_tensor, cls_name, conf, angle_deg):
    """
    YOLO OBB 결과를 화면에 그리는 함수
    """
    # 1. 바운딩 박스 좌표 추출
    x, y, w, h, rot = box_tensor.xywhr[0].cpu().numpy()
    
    # 2. 회전된 사각형의 4개 꼭짓점 계산
    rect = ((x, y), (w, h), np.degrees(rot))
    box = cv2.boxPoints(rect)
    
    # [수정됨] np.int0 대신 astype(int) 사용 (NumPy 최신 버전 호환)
    box = box.astype(int)

    # 3. 박스 그리기 (초록색)
    cv2.drawContours(img, [box], 0, (0, 255, 0), 2)

    # 4. 중심점 그리기
    cx, cy = int(x), int(y)
    cv2.circle(img, (cx, cy), 5, (0, 0, 255), -1)

    # 5. 텍스트 정보 표시
    label = f"{cls_name} {conf:.2f}"
    angle_text = f"Angle: {angle_deg:.1f} deg"
    
    cv2.putText(img, label, (box[1][0], box[1][1] - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    cv2.putText(img, angle_text, (box[1][0], box[1][1] - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (50, 100, 255), 2)


def main():
    print("--- YOLOv8 OBB with ROI Limit & Angle Display ---")

    # 1. 모델 로드
    try:
        model = YOLO(model_path)
    except Exception as e:
        print(f"Error loading model: {e}")
        return

    # 2. 리얼센스 설정
    pipeline = rs.pipeline()
    config = rs.config()
    pipeline_wrapper = rs.pipeline_wrapper(pipeline)
    try:
        pipeline_profile = config.resolve(pipeline_wrapper)
    except Exception as e:
        print(f"RealSense not found: {e}")
        return

    config.enable_stream(rs.stream.color, IMG_WIDTH, IMG_HEIGHT, rs.format.bgr8, FPS)
    pipeline.start(config)
    
    print("Press 'q' to exit.")

    prev_time = 0

    try:
        while True:
            frames = pipeline.wait_for_frames()
            color_frame = frames.get_color_frame()
            if not color_frame: continue

            color_image = np.asanyarray(color_frame.get_data())

            # [시각화] ROI 영역(사다리꼴)을 파란색 선으로 그리기
            cv2.polylines(color_image, [ROI_POINTS], isClosed=True, color=(255, 0, 0), thickness=2)

            # 3. YOLO 추론 (conf=0.5 설정)
            results = model(color_image, stream=True, conf=conf_threshold, verbose=False)

            for r in results:
                if r.obb is None:
                    continue

                for box in r.obb:
                    x, y, w, h, rot_rad = box.xywhr[0].cpu().numpy()
                    conf = float(box.conf[0])
                    cls_id = int(box.cls[0])
                    cls_name = model.names[cls_id]
                    
                    rot_deg = np.degrees(rot_rad)

                    # [핵심] 중심점이 ROI 안에 있을 때만 표시
                    if is_inside_roi(x, y, ROI_POINTS):
                        draw_rotated_rect(color_image, box, cls_name, conf, rot_deg)
                        print(f"[{cls_name}] Conf: {conf:.2f} | Pos: ({x:.1f}, {y:.1f}) | Angle: {rot_deg:.1f}°")
            
            # 4. FPS 표시
            curr_time = time.time()
            fps = 1 / (curr_time - prev_time) if (curr_time - prev_time) > 0 else 0
            prev_time = curr_time
            
            cv2.putText(color_image, f"FPS: {fps:.1f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(color_image, "ROI Active", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)

            cv2.imshow('YOLOv8 OBB - ROI Limited', color_image)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    except Exception as e:
        print(f"Error: {e}")
    finally:
        pipeline.stop()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()