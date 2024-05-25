import cv2
from ultralytics import YOLO, solutions

model = YOLO("models/v6.pt")
cap = cv2.VideoCapture("Khare_testvideo_03.mp4")
assert cap.isOpened(), "Error reading video file"

# 獲取影片的寬度（w）、高度（h）和幀率（fps）
w, h, fps = (int(cap.get(x)) for x in (cv2.CAP_PROP_FRAME_WIDTH, cv2.CAP_PROP_FRAME_HEIGHT, cv2.CAP_PROP_FPS))

# 四邊形區域，用於計數物體(左下, 右下, 右上, 左上)
# region_points = [(20, 500), (1200, 500), (1200, 200), (20, 200)]
# region_points = [(0, h ), (w, h), (w, 0), (0, 0)]
line_points = [(0 + 100, h - 100 ), (w - 100, h - 100), (w - 100, 0 + 100), (0 + 100, 0 + 100)]

# 要計數的物體類別，人（0）、汽車（2）和摩托車（3）
classes_to_count = [0, 2, 3]

# 將處理後的影像寫入新的影片檔案
video_writer = cv2.VideoWriter("object_counting_output.avi", cv2.VideoWriter_fourcc(*'mp4v'), fps, (w, h))

# Init Object Counter
counter = solutions.ObjectCounter(
    view_img = True,  # 顯示影像
    reg_pts = line_points,  # 設定計數區域點
    classes_names = model.names,  # 設定物體類別名稱
    draw_tracks = True,    # 畫出物體的追蹤軌跡
    line_thickness = 2  # 邊界框的線寬
)

# 逐幀處理影片
while cap.isOpened():
    success, im0 = cap.read()

    if not success:
        print("Video frame is empty or video processing has been successfully completed.")
        break

    # 使用 YOLO 模型追蹤物體，返回追蹤結果 tracks，並指定只檢測指定類別的物體
    tracks = model.track(im0, persist=True, show=False, classes=classes_to_count)

    # 使用 counter.start_counting 在影像中計數物體並更新影像 im0
    im0 = counter.start_counting(im0, tracks)
    video_writer.write(im0)

# 釋放
cap.release()
video_writer.release()
cv2.destroyAllWindows()