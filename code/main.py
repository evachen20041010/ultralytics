from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
from shapely.geometry import Polygon
from shapely.geometry.point import Point

from ultralytics import YOLO
from ultralytics.utils.files import increment_path
from ultralytics.utils.plotting import Annotator, colors

# 追蹤路線歷史
track_history = defaultdict(list)

def run(
    weights="./models/v6.pt",  # model 檔案的路徑
    source="./Khare_testvideo_01.mp4",  # 影片來源檔路徑
    device="0",  # 使用設備，"0" -> GPU
    view_img=True,  # 顯示影像
    save_img=True,  # 保存影像(影片)
    exist_ok=False,
    classes=[0],  # 要檢測的類別(car)
    line_thickness=2,  # 框線的寬度
    track_thickness=2,  # 追蹤線的寬度
    region_thickness=2,  # 區域線的寬度
    stationary_threshold=5,  # 判定車輛靜止的閾值
    save_frame_interval=30,  # 保存圖片的幀間隔
    resize_factor=0.5  # 圖片縮放比例
):
    vid_frame_count = 0  # 記錄當前幀數

    # 檢查來源路徑是否存在
    if not Path(source).exists():
        raise FileNotFoundError(f"Source path '{source}' does not exist.")

    # 設置模型
    model = YOLO(f"{weights}")
    model.to("cuda") if device == "0" else model.to("cpu")

    # 提取類別名稱
    names = model.model.names

    # 視訊設置
    videocapture = cv2.VideoCapture(source)
    frame_width, frame_height = int(videocapture.get(3)), int(videocapture.get(4))
    fps, fourcc = int(videocapture.get(5)), cv2.VideoWriter_fourcc(*"mp4v")

    # 定義計數區域為整個幀
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

    # 輸出設置
    save_dir = increment_path(Path("./code/ultralytics_rc_output") / "exp", exist_ok)
    save_dir.mkdir(parents=True, exist_ok=True)
    video_writer = cv2.VideoWriter(str(save_dir / f"{Path(source).stem}.mp4"), fourcc, fps, (frame_width, frame_height))

    # 用於保存個別幀的目錄
    frames_dir = save_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    # 迭代視訊幀
    while videocapture.isOpened():
        success, frame = videocapture.read()
        if not success:
            break
        vid_frame_count += 1

        # 提取結果
        results = model.track(frame, persist=True, classes=classes)

        if results[0].boxes.id is not None:
            boxes = results[0].boxes.xyxy.cpu()
            track_ids = results[0].boxes.id.int().cpu().tolist()
            clss = results[0].boxes.cls.cpu().tolist()

            annotator = Annotator(frame, line_width=line_thickness, example=str(names))

            for box, track_id, cls in zip(boxes, track_ids, clss):
                annotator.box_label(box, str(names[cls]), color=colors(cls, True))
                bbox_center = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2  # Bbox 中心

                track = track_history[track_id]  # 追蹤線繪製
                track.append((float(bbox_center[0]), float(bbox_center[1])))
                if len(track) > 30:
                    track.pop(0)
                points = np.hstack(track).astype(np.int32).reshape((-1, 1, 2))
                cv2.polylines(frame, [points], isClosed=False, color=colors(cls, True), thickness=track_thickness)

                # 檢查是否靜止
                if len(track) > 1:
                    movement = np.linalg.norm(np.array(track[-1]) - np.array(track[0]))
                    if movement < stationary_threshold:
                        # 檢查檢測是否在區域內
                        for region in counting_regions:
                            if region["polygon"].contains(Point((bbox_center[0], bbox_center[1]))):
                                region["counts"] += 1

        # 繪製區域（多邊形/矩形）
        for region in counting_regions:
            region_label = str(region["counts"])
            region_color = region["region_color"]
            region_text_color = region["text_color"]

            polygon_coords = np.array(region["polygon"].exterior.coords, dtype=np.int32)

            # 繪製多邊形
            cv2.polylines(frame, [polygon_coords], isClosed=True, color=region_color, thickness=region_thickness)

            # 在左上角顯示區域標籤
            text_x, text_y = 10, 30  # 文字位置
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

        if view_img:
            if vid_frame_count == 1:
                cv2.namedWindow("Ultralytics YOLOv8 Region Counter Movable")
            cv2.imshow("Ultralytics YOLOv8 Region Counter Movable", frame)

        if save_img:
            video_writer.write(frame)

            # 每隔 'save_frame_interval' 幀保存當前幀
            if vid_frame_count % save_frame_interval == 0:
                # 調整幀大小
                resized_frame = cv2.resize(frame, (0, 0), fx=resize_factor, fy=resize_factor)
                frame_filename = frames_dir / f"frame_{vid_frame_count:04d}.jpg"
                cv2.imwrite(str(frame_filename), resized_frame)

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
