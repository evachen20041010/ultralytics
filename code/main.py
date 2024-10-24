from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
from shapely.geometry import Polygon, Point

from ultralytics import YOLO
from ultralytics.utils.files import increment_path
from ultralytics.utils.plotting import Annotator, colors

import firebase_admin
from firebase_admin import credentials, storage as firebase_storage, firestore
from google.cloud import storage

import multiprocessing as mp
from multiprocessing import Manager

import json
from ultralytics import solutions

# 追蹤路線歷史
track_history = defaultdict(list)

# Firebase 初始化
cred = credentials.Certificate("code/firebase/parking-test_key.json")
firebase_admin.initialize_app(cred, {
    'storageBucket': 'parking-test-f9490.appspot.com'
})

# 取得 bucket 名稱
bucket_name = firebase_storage.bucket().name

# 上傳資料到 Google Cloud Storage
def upload_storage(bucket_name, source_file_name, destination_blob_name):
    # 使用專案 ID 初始化 Storage 用戶端
    storage_client = storage.Client.from_service_account_json('code/firebase/parking-test_key.json')
    
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(source_file_name) # 上傳檔案
    print(f"File {source_file_name} uploaded to {destination_blob_name}.")

# 上傳資料到 Cloud Firestore
def upload_firestore(parking_name, area_name, total_space, occupied_space, empty_space, max_empty_space, min_empty_space, assigned_space_id):
    db = firestore.client()
    doc_ref = db.collection(parking_name).document(area_name)
    data = {
        "total_space": total_space, 
        "occupied_space": occupied_space, 
        "empty_space": empty_space, 
        "max_empty_space": max_empty_space, 
        "min_empty_space": min_empty_space
    }
    if assigned_space_id:
        data["assigned_space_id"] = assigned_space_id
    doc_ref.set(data)

    print(f"total_space={total_space}, occupied_space={occupied_space}, empty_space={empty_space}, max_empty_space={max_empty_space}, min_empty_space={min_empty_space}, assigned_space_id={assigned_space_id}")
    print(f"Data uploaded to {parking_name}/{area_name}.")

# 取得空車位 ID
def get_empty_space_ids(json_data, occupied_polygons):
    empty_space_ids = []
    for spot in json_data:
        # 將座標轉換為多邊形（Polygon）物件
        spot_polygon = Polygon(spot["points"])

        # 根據實際情況調整緩衝區大小
        buffer_size = 0.1

        # spot_polygon.intersects(occupied_polygon) 判斷車位的多邊形是否與任何已被佔用的車位（occupied_polygons）發生相交
        if not any(spot_polygon.buffer(buffer_size).intersects(occupied_polygon.buffer(buffer_size)) for occupied_polygon in occupied_polygons):
            empty_space_ids.append(spot["id"])
    
    return empty_space_ids

# 分配車位 ID
def assign_parking_space(empty_space_ids):
    if empty_space_ids:
        assigned_id = empty_space_ids[0]
        empty_space_ids.remove(assigned_id)
        return assigned_id
    return None

# 分區域辨識最多最少空車位
def save_quadrant_images(frame, save_dir, vid_frame_count, parking_name, area_name, upload_firebase):
    # 取得圖片的尺寸
    h, w = frame.shape[:2]

    # 計算每個區域的寬高
    quadrant_h, quadrant_w = h // 2, w // 2

    # 分割圖片
    quadrants = [
        frame[0:quadrant_h, 0:quadrant_w],         # top-left
        frame[0:quadrant_h, quadrant_w:w],         # top-right
        frame[quadrant_h:h, 0:quadrant_w],         # bottom-left
        frame[quadrant_h:h, quadrant_w:w]          # bottom-right
    ]

    # 定義紅色的範圍（HSV顏色空間）
    lower_red = np.array([0, 100, 100])
    upper_red = np.array([10, 255, 255])

    # 用來記錄每個區塊的紅色框框數量
    red_counts = []

    # 儲存每個分割後的圖片
    for i, quadrant in enumerate(quadrants, start=1):
        # 儲存每個分割後的圖片
        quadrant_filename = save_dir / "frames_four" / f"frame_{vid_frame_count}_{i}.jpg"
        cv2.imwrite(str(quadrant_filename), quadrant)

        # 檢測紅色框框數量
        hsv_image = cv2.cvtColor(quadrant, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv_image, lower_red, upper_red)
        red_area = cv2.countNonZero(mask)
        red_counts.append(red_area)

        # 上傳資料到 Firebase
        if upload_firebase:
            upload_storage(bucket_name, str(quadrant_filename), f"{parking_name}/{area_name}/frames_four/frame_{vid_frame_count}_{i}.jpg")
    
    # 比較紅色框框的數量
    max_red_count = max(red_counts)
    min_index = red_counts.index(max_red_count) + 1  # 1-based index

    # 找到紅色框框最少的區塊
    min_red_count = min(red_counts)
    max_index = red_counts.index(min_red_count) + 1  # 1-based index

    # 輸出最多與最少結果
    print(f"Red boxes count for each quadrant: {red_counts}")
    print(f"Quadrant with most red boxes is: Top-Left (1), Top-Right (2), Bottom-Left (3), Bottom-Right (4) => Quadrant {max_index}")
    print(f"Quadrant with least red boxes is: Top-Left (1), Top-Right (2), Bottom-Left (3), Bottom-Right (4) => Quadrant {min_index}")

    return max_index, min_index

def process_video(
        source, 
        parking_name, 
        area_name, 
        weights, 
        device, 
        view_img, 
        save_img, 
        upload_firebase, 
        exist_ok, 
        classes, 
        track_thickness, 
        region_thickness,  
        save_interval_seconds, 
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
    management = solutions.ParkingManagement(weights, margin=1, occupied_region_color=(0, 0, 255), available_region_color=(0, 255, 0))

    # 從JSON文件中提取車位的邊界框數據
    polygon_json_path = Path("./code/boxes_json") / f"{area_name}_id.json"
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
            boxes = results[0].boxes.xyxy.cpu().tolist()    # 偵測到的物件的邊界框座標
            track_ids = results[0].boxes.id.int().cpu().tolist()    # 偵測到的物件的唯一追蹤 ID
            clss = results[0].boxes.cls.cpu().tolist()  # 偵測到的物件的類別索引

            # 將邊界框轉換為多邊形
            # occupied_polygons = [Polygon([(box[0], box[1]), (box[2], box[1]), (box[2], box[3]), (box[0], box[3])]) for box in boxes]

            # 更新空車位 IDs
            # empty_space_ids = get_empty_space_ids(json_data, occupied_polygons)
            # print(empty_space_ids)

            # 處理檢測結果並更新停車區域狀態，回傳已占用車位數量
            management.process_data(json_data, frame, boxes, clss)

            # 取出空車位、已被使用車位數量
            occupied_space = management.labels_dict['Occupancy']    # 已占用車位
            empty_space = management.labels_dict['Available']   # 空車位
            total_space = occupied_space + empty_space
            print(f"{area_name} Occupied: {occupied_space}, Empty: {empty_space}, Total: {total_space}")

            # empty_space_ids = management.empty_space_ids
            empty_space_ids = []
            print(empty_space_ids)

            # annotator = Annotator(frame, line_width=line_thickness, example=str(names))

            # 繪製物件的邊界框和標籤
            for box, track_id, cls in zip(boxes, track_ids, clss):
                # 計算邊界框中心點
                bbox_center = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2  # Bbox 中心
                
                # 將當前邊界框中心的座標追加到追蹤歷史中
                track = track_history[track_id]
                track.append((float(bbox_center[0]), float(bbox_center[1])))

                # 追蹤歷史中最多只保留最近的 30 個座標點
                if len(track) > 30:
                    track.pop(0)

                # 在調用 np.hstack 之前確保 track_history[cls] 不為空
                if track_history[cls]:
                    # 將追蹤歷史中的座標轉換為繪製多邊形所需的格式
                    points = np.hstack(track_history[cls]).astype(np.int32).reshape((-1, 1, 2))

                    # 繪製追蹤線
                    cv2.polylines(frame, [points], isClosed=False, color=colors(cls, True), thickness=track_thickness)

        # 繪製計數區域，更新車位資訊
        for region in counting_regions:
            # 提取計算範圍的頂點座標
            # 將區域的多邊形座標轉換為 NumPy 數組(方便後續用 OpenCV 繪製多邊形)
            points = np.array(region["polygon"].exterior.coords, dtype=np.int32)

            # 繪製計算範圍
            cv2.polylines(frame, [points], isClosed=True, color=region["region_color"], thickness=region_thickness)
            cv2.putText(frame, f"{region['name']}: {region['counts']}", (points[0][0], points[0][1] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, region["text_color"], 2)

        # 保存影像
        if save_img:
            video_writer.write(frame)
        
        # 每隔 'save_frame_interval' 幀保存當前幀
        if vid_frame_count % save_frame_interval == 0:
            filename = frames_dir / f"frame_{vid_frame_count}.jpg"
            cv2.imwrite(str(filename), frame)

            # 保存分割後的圖片
            max_empty_space, min_empty_space = save_quadrant_images(frame, save_dir, vid_frame_count, parking_name, area_name, upload_firebase)

            # 上傳資料到 Firebase
            if upload_firebase:
                upload_storage(bucket_name, filename, f"{parking_name}/{area_name}/frames/frame_{vid_frame_count}.jpg")
                
                # 分配車位 ID
                assigned_space_id = assign_parking_space(empty_space_ids)

                upload_firestore(parking_name, area_name, total_space, occupied_space, empty_space, max_empty_space, min_empty_space, assigned_space_id)
        
        # 顯示處理後的影像
        if view_img:
            cv2.imshow(str(source), frame)
            if cv2.waitKey(1) == ord("q"):   # 點擊 q 鍵退出
                break

    # 清理
    videocapture.release()
    video_writer.release()
    if view_img:
        cv2.destroyAllWindows()
        
    print(f"Process video saved to: {save_dir}")

def main():
    # 要辨識的影片、停車場資料夾名稱、區塊資料夾名稱、區塊車位總數量
    video_sources = [
        ("./video/istockphoto_01.mp4", "istockphoto", "istockphoto_01"),
        ("./video/istockphoto_02.mp4", "istockphoto", "istockphoto_02"),
    ]

    # 設定參數
    weights = "./models/v9.pt"  # model 檔案的路徑
    device = "0"    # 使用設備，"0" -> GPU
    view_img = True # 顯示影像
    save_img = True # 保存影像(影片)
    upload_firebase = True  # 儲存資料到 Firebase
    exist_ok = True    # 設置為 False 會創建新的遞增目錄名稱
    classes = [0]   # 要檢測的類別(car)
    track_thickness = 2 # 追蹤線的寬度
    region_thickness = 2    # 區域線的寬度
    save_interval_seconds = 5   # 保存圖片的時間間隔(秒)

    # 建立一個包含多個進程的處理池 (Pool)，每個影片來源對應一個進程
    # (with -> 處理池使用完後會自動關閉，釋放資源)
    with mp.Pool(processes=len(video_sources)) as pool:
        # 將函數應用於參數的序列，允許將多個參數傳遞給函數
        pool.starmap(
            process_video,  # 要並行運行的函數
            # 要傳遞給 process_video 函數的參數
            [(
            source, 
            parking_name, 
            area_name, 
            weights, device, 
            view_img, 
            save_img, 
            upload_firebase, 
            exist_ok, classes, 
            track_thickness, 
            region_thickness,  
            save_interval_seconds
            ) for source, parking_name, area_name in video_sources]
        )
        # source(影像位置)、parking_name(停車場名稱)、area_name(區域名稱)

if __name__ == "__main__":
    main()
