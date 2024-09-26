from ultralytics import YOLO

# 訓練好的模型
model = YOLO('models/v6.pt')

# 驗證目標
results = model.predict(source = 'Khare_testvideo_03.mp4', show = True)

# 儲存驗證結果
# results = model.predict(source = 'datasets/coco8_4/test/images', save = True)