from ultralytics import YOLO

model = YOLO('models/yolov8x.pt')

# 用程式碼執行時，workers 要改成0
model.train(data = 'yaml/coco8_6.yaml', workers = 0, epochs = 50, batch = 16)