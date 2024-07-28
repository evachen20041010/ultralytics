from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
from shapely.geometry import Polygon, Point

from ultralytics import YOLO
from ultralytics.utils.files import increment_path
from ultralytics.utils.plotting import Annotator, colors

import multiprocessing as mp

import json
from ultralytics import solutions

# 追蹤路線歷史
track_history = defaultdict(list)

def process_video(
        source, 
        parking_name, 
        area_name, 
        total_space, 
        weights, 
        device, 
        view_img, 
        save_img, 
        upload_firebase, 
        exist_ok, 
        classes, 
        line_thickness, 
        track_thickness, 
        region_thickness, 
        stationary_threshold, 
        save_interval_seconds, 
        resize_factor
    ):
    vid_frame_count = 0 # 記錄當前經過的幀數
    occupied_space = 0  # 已被使用車位數量
    empty_space = 0 # 空車位數量

    # 檢查影片來源路徑是否存在
    if not Path(source).exists():
        raise FileNotFoundError(f"Source path '{source}' does not exist.")

    # 設置模型
    model = YOLO(weights)
    model.to("cuda") if device == "0" else model.to("cpu")
    names = model.model.names   # 提取類別名稱

    # 影片設置
    videocapture = cv2.VideoCapture(source)
    frame_width, frame_height = int(videocapture.get(3)), int(videocapture.get(4))
    fps, fourcc = int(videocapture.get(5)), cv2.VideoWriter_fourcc(*"mp4v")

    # 計算每多少幀保存一次圖片(例影片是 29畫面/秒：29 * 設定的秒數 = 每辨識多少次圖片才上傳)
    save_frame_interval = int(fps * save_interval_seconds)

    # 定義計數區域
    counting_regions = [
        {
            "name": "YOLOv8 Polygon Region",
            "polygon": Polygon([(0, 0), (frame_width, 0), (frame_width, frame_height), (0, frame_height)]),
            "counts": 0,
            "dragging": False,
            "region_color": (255, 42, 4),   # BGR 值
            "text_color": (255, 255, 255),  # 區域文字顏色
        },
    ]

    # 資料儲存設置
    save_dir = increment_path(Path("./code/ultralytics_rc_output") / f"{area_name}", exist_ok)
    save_dir.mkdir(parents=True, exist_ok=True)

    # 影片儲存設置
    video_writer = cv2.VideoWriter(str(save_dir / f"{Path(source).stem}.mp4"), fourcc, fps, (frame_width, frame_height))
    
    # 用於保存個別幀畫面的目錄
    frames_dir = save_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    # 初始化停車管理系統
    management = solutions.ParkingManagement(weights, margin=1)

    # 從JSON文件中提取車位的邊界框數據
    polygon_json_path = Path("./code/boxes_json") / f"{area_name}.json"
    with open(polygon_json_path, 'r') as f:
        json_data = json.load(f)

    # 處理影片的每一幀
    while videocapture.isOpened():
        # 從影片中讀取一幀
        success, frame = videocapture.read()
        if not success:
            break
        vid_frame_count += 1

        # 進行物件偵測和追蹤
        # persist：記住前一幀中已經偵測到的物件，並在後續幀中嘗試繼續追蹤這些物件
        results = management.model.track(frame, persist=True, classes=classes)

        if results[0].boxes.id is not None:
            boxes = results[0].boxes.xyxy.cpu().tolist()    # 提取邊界框坐標
            track_ids = results[0].boxes.id.int().cpu().tolist()    # 偵測到的物件的唯一追蹤 ID
            clss = results[0].boxes.cls.cpu().tolist()  # 提取車輛類別
            management.process_data(json_data, frame, boxes, clss)    # 處理檢測結果並更新停車區域狀態

            # annotator = Annotator(frame, line_width=line_thickness, example=str(names))

            for box, track_id, cls in zip(boxes, track_ids, clss):
                # 在影像上繪製邊界框和標籤
                # annotator.box_label(box, str(names[cls]), color=colors(cls, True))

                # 計算邊界框中心點
                bbox_center = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2  # Bbox 中心

                # 指定 track_id 的追蹤歷史座標
                track = track_history[track_id]

                # 將當前邊界框中心的座標追加到追蹤歷史中
                track.append((float(bbox_center[0]), float(bbox_center[1])))

                # 追蹤歷史中最多只保留最近的 30 個座標點
                if len(track) > 30:
                    track.pop(0)

                # 將追蹤歷史中的座標轉換為繪製多邊形所需的格式
                points = np.hstack(track).astype(np.int32).reshape((-1, 1, 2))

                # 繪製追蹤線
                cv2.polylines(frame, [points], isClosed=False, color=colors(cls, True), thickness=track_thickness)
                
                # 判斷車輛是否靜止（即至少有兩個座標點）
                if len(track) > 1:
                    # 計算兩點之間的歐幾里得距離（即直線距離）(求範數)
                    movement = np.linalg.norm(np.array(track[-1]) - np.array(track[0]))

                    # 車輛移動距離小於靜止閾值，則判定為靜止並增加計數
                    if movement < stationary_threshold:
                        for region in counting_regions:
                            # 檢查車輛的中心點是否位於計算範圍內
                            if region["polygon"].contains(Point((bbox_center[0], bbox_center[1]))):
                                region["counts"] += 1

        # 繪製計數區域，更新車位資訊
        for region in counting_regions:
            # 提取計算範圍的頂點座標
            # 將區域的多邊形座標轉換為 NumPy 數組(方便後續用 OpenCV 繪製多邊形)
            points = np.array(region["polygon"].exterior.coords, dtype=np.int32)

            # 繪製計算範圍
            cv2.polylines(frame, [points], isClosed=True, color=region["region_color"], thickness=region_thickness)
            cv2.putText(frame, f"{region['name']}: {region['counts']}", (points[0][0], points[0][1] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, region["text_color"], 2)

        if save_img:   # 保存結果
            video_writer.write(frame)
        
        if vid_frame_count % save_frame_interval == 0:
            filename = frames_dir / f"frame_{vid_frame_count}.jpg"
            cv2.imwrite(str(filename), frame)
            
            # 更新車位狀態
            # empty_space, occupied_space = management.status()
            
        if view_img:  # 瀏覽結果
            cv2.imshow(str(source), frame)
            if cv2.waitKey(1) == ord("q"):   # 點擊 q 鍵退出
                break

    # 清理
    videocapture.release()
    video_writer.release()
    if view_img:
        cv2.destroyAllWindows()
        
    print(f"Process video saved to: {save_dir}")

# 設定參數
source = "./video/istockphoto_01.mp4"
parking_name = "istockphoto"
area_name = "istockphoto_01"
total_space = 100
weights = "./models/v6.pt"
device = "0"  # 使用 GPU
view_img = True
save_img = True
upload_firebase = False
exist_ok = True
classes = [0]  # 替換成你感興趣的類別
line_thickness = 2
track_thickness = 2
region_thickness = 2
stationary_threshold = 5
save_interval_seconds = 5
resize_factor = 0.5

# 執行影片處理
process_video(
    source, 
    parking_name, 
    area_name, 
    total_space, 
    weights, 
    device, 
    view_img, 
    save_img, 
    upload_firebase, 
    exist_ok, 
    classes, 
    line_thickness, 
    track_thickness, 
    region_thickness, 
    stationary_threshold, 
    save_interval_seconds, 
    resize_factor
)
