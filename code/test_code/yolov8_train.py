from ultralytics import YOLO

model = YOLO('models/v9.pt')

# 用程式碼執行時，workers 要改成0
model.train(data = 'coco8_5.yaml', workers = 0, epochs = 50, batch = 16)