from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
from shapely.geometry import Polygon
from shapely.geometry.point import Point

from ultralytics import YOLO
from ultralytics.utils.files import increment_path
from ultralytics.utils.plotting import Annotator, colors

import firebase_admin
from firebase_admin import credentials
from firebase_admin import storage as firebase_storage
from google.cloud import storage
from firebase_admin import firestore

# 追蹤路線歷史
track_history = defaultdict(list)

cred = credentials.Certificate("code/firebase/key.json")
firebase_admin.initialize_app(cred, {
    'storageBucket': 'parking-test-f9490.appspot.com'
})

# 取得 bucket 名稱
bucket_name = firebase_storage.bucket().name

# 上傳資料到 Firebase Storage
def upload_storage(bucket_name, source_file_name, destination_blob_name):
    # 使用專案 ID 初始化 Google Cloud Storage 用戶端
    storage_client = storage.Client.from_service_account_json('code/firebase/key.json')

    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    # 上傳檔案
    blob.upload_from_filename(source_file_name)

    print(f"File {source_file_name} uploaded to {destination_blob_name}.")

# 上傳資料到 Firebase Storage
# def upload_firestore():

def run(
    weights="./models/v6.pt",  # model 檔案的路徑
    source="./Khare_testvideo_01.mp4",  # 影片來源檔路徑
    source_name="Khare_testvideo_01",   # 用來設定上傳到 firebase 資料夾的名稱
    device="0",  # 使用設備，"0" -> GPU
    view_img=True,  # 顯示影像
    save_img=True,  # 保存影像(影片)
    exist_ok=False,
    classes=[0],  # 要檢測的類別(car)
    line_thickness=2,  # 框線的寬度
    track_thickness=2,  # 追蹤線的寬度
    region_thickness=2,  # 區域線的寬度
    stationary_threshold=5,  # 判定車輛靜止的閾值
    save_interval_seconds=5,  # 保存圖片的時間間隔(秒)
    resize_factor=0.5  # 圖片縮放比例
):
    vid_frame_count = 0  # 記錄當前經過的幀數

    # 檢查影片來源路徑是否存在
    if not Path(source).exists():
        raise FileNotFoundError(f"Source path '{source}' does not exist.")

    # 設置模型
    model = YOLO(f"{weights}")
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
            "polygon": Polygon([(0, 0), (frame_width, 0), (frame_width, frame_height), (0, frame_height)]),  # 全屏
            "counts": 0,
            "dragging": False,
            "region_color": (255, 42, 4),  # BGR 值
            "text_color": (255, 255, 255),  # 區域文字顏色
        },
    ]

    # 資料儲存設置
    save_dir = increment_path(Path("./code/ultralytics_rc_output") / "exp", exist_ok)
    save_dir.mkdir(parents=True, exist_ok=True)

    # 影片儲存設置
    video_writer = cv2.VideoWriter(str(save_dir / f"{Path(source).stem}.mp4"), fourcc, fps, (frame_width, frame_height))

    # 用於保存個別幀畫面的目錄
    frames_dir = save_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    # 處理影片的每一幀
    while videocapture.isOpened():
        # 從影片中讀取一幀
        success, frame = videocapture.read()
        if not success:
            break
        vid_frame_count += 1

        # 進行物件偵測和追蹤
        # persist：記住前一幀中已經偵測到的物件，並在後續幀中嘗試繼續追蹤這些物件
        results = model.track(frame, persist=True, classes=classes)

        if results[0].boxes.id is not None:
            boxes = results[0].boxes.xyxy.cpu() # 偵測到的物件的邊界框座標
            track_ids = results[0].boxes.id.int().cpu().tolist()    # 偵測到的物件的唯一追蹤 ID
            clss = results[0].boxes.cls.cpu().tolist()  # 偵測到的物件的類別索引

            annotator = Annotator(frame, line_width=line_thickness, example=str(names))

            for box, track_id, cls in zip(boxes, track_ids, clss):
                # 在影像上繪製邊界框和標籤
                annotator.box_label(box, str(names[cls]), color=colors(cls, True))

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

        # 繪製計數區域
        for region in counting_regions:
            region_label = str(region["counts"])
            region_color = region["region_color"]
            region_text_color = region["text_color"]

            # 將區域的多邊形座標轉換為 NumPy 數組(方便後續用 OpenCV 繪製多邊形)
            polygon_coords = np.array(region["polygon"].exterior.coords, dtype=np.int32)

            # 繪製多邊形
            cv2.polylines(frame, [polygon_coords], isClosed=True, color=region_color, thickness=region_thickness)

            # 在左上角顯示車子數量標籤
            text_x, text_y = 10, 30
            
            # 
            text_size, _ = cv2.getTextSize(
                region_label, cv2.FONT_HERSHEY_SIMPLEX, fontScale=0.7, thickness=line_thickness
            )
            cv2.rectangle(
                frame,
                (text_x - 5, text_y - text_size[1] - 5),
                (text_x + text_size[0] + 5, text_y + 5),
                region_color,
                -1,
            )
            cv2.putText(
                frame, region_label, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, region_text_color, line_thickness
            )

        # 顯示處理後的影像
        if view_img:
            if vid_frame_count == 1:
                cv2.namedWindow("Ultralytics YOLOv8 Region Counter Movable")
            cv2.imshow("Ultralytics YOLOv8 Region Counter Movable", frame)

        if save_img:
            # 保存影像
            video_writer.write(frame)

            # 每隔 'save_frame_interval' 幀保存當前幀
            if vid_frame_count % save_frame_interval == 0:
                # 調整幀大小
                resized_frame = cv2.resize(frame, (0, 0), fx=resize_factor, fy=resize_factor)
                frame_filename = frames_dir / f"frame_{vid_frame_count:04d}.jpg"
                cv2.imwrite(str(frame_filename), resized_frame)
                upload_storage(bucket_name, frame_filename, f"yolov8/{source_name}/images/frame_{vid_frame_count:04d}.jpg")

        for region in counting_regions:  # 重新初始化每個區域的計數
            region["counts"] = 0

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    del vid_frame_count
    video_writer.release()
    videocapture.release()
    cv2.destroyAllWindows()

def main():
    """主函數。"""
    run()

if __name__ == "__main__":
    main()
