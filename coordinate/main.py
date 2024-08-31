
import cv2
from ultralytics import YOLO

# 載入 YOLOv8 模型
model_path = r'C:\Users\HUANG\runs\detect\train11\weights\best.pt'
model = YOLO(model_path)

# 定義座標字典
coordinates = {
    'A': (46.5, 0), 'B': (46.5, 70), 'C': (46.5, 140), 'D': (46.5, 210), 'E': (46.5, 280),
    'F': (46.5, 350), 'L': (46.5, 400), 'Q': (116.5, 400), 'P': (186.5, 400), 'K': (256.5, 400),
    'U': (326.5, 400), 'V': (396.5, 400), 'W': (466.5, 400), 'X': (536.5, 400), 'Y': (606.5, 400),
    'Z': (668.5, 400), 'e': (668.5, 350), 'h': (668.5, 280), 'm': (668.5, 210), 'n': (668.5, 140),
    'g': (676.5, 55), 't': (606.5, 55), 'y': (536.5, 55), 'lungu': (466.5, 55), 'duomianti': (396.5, 55),
    'r': (326.5, 55), 'yuanzhu': (256.5, 55), 'yuanzhui': (186.5, 55), '4': (116.5, 55)
}

# 讀取影像
image_path = (r'C:\Users\HUANG\Desktop\A.jpg')
image = cv2.imread(image_path)

# 使用模型進行推論
results = model(image)

# 獲取標籤名稱的映射
names = model.names

# 確認模型標籤ID對應的標籤名稱
print(f"Model labels: {names}")

# 從結果中獲取標籤和座標
for result in results:
    for box in result.boxes:
        x1, y1, x2, y2 = box.xyxy[0].tolist()  # 取得邊界框座標
        label_id = int(box.cls[0])  # 取得標籤ID
        label_name = names[label_id]  # 取得標籤名稱
        coordinate = coordinates.get(label_name)  # 根據標籤名稱取得座標

        if coordinate:
            print(f"Label: {label_name}, Coordinate: {coordinate}")
        else:
            print(f"Label: {label_name} does not have a coordinate.")