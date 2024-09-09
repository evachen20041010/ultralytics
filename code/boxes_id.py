import json

def add_unique_ids_to_json(input_file, output_file):
    with open(input_file, 'r') as f:
        data = json.load(f)
    
    updated_data = []
    
    for index, item in enumerate(data):
        # 生成唯一 ID，格式為 A-01, A-02, A-03, 依此類推
        unique_id = f"A-{str(index + 1).zfill(2)}"
        
        # 將 ID 和原始的 points 組合
        updated_item = {
            "id": unique_id,
            "points": item["points"]
        }
        updated_data.append(updated_item)
    
    with open(output_file, 'w') as f:
        json.dump(updated_data, f, indent=4)
    
    print(f"Updated JSON saved to {output_file}")

# 設定檔案路徑
input_json_path = 'code/boxes_json/istockphoto_02.json'
output_json_path = 'code/boxes_json/istockphoto_02_id.json'

# 執行函數以添加 ID
add_unique_ids_to_json(input_json_path, output_json_path)
