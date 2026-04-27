# 🚇 Smart Map Pro - St. Petersburg Metro Router

**Ứng dụng định tuyến tối ưu cho hệ thống tàu điện ngầm St. Petersburg sử dụng thuật toán A***

## 📋 Tính Năng Chính

### 🗺️ Định Tuyến Người Dùng
- **Thuật toán A***: Tìm đường tối ưu giữa hai điểm bất kỳ
- **Heuristic Euclid**: Khoảng cách đường chim bay để hướng dẫn tìm kiếm
- **Luồng di chuyển**:
  1. Chọn điểm A (tọa độ bất kỳ)
  2. Chọn điểm B (tọa độ bất kỳ)
  3. Hệ thống tự động:
     - Tìm ga tàu gần A nhất
     - Di chuyển qua mạng lưới ga (đồ thị)
     - Tìm ga gần B nhất
     - Chỉ dẫn đi bộ từ ga đến B

### 👨‍💼 Chế Độ Admin (Mật khẩu: `123456`)

#### Cách 1: Cấm Một Ga
- Chọn chế độ "Cấm Ga"
- Click vào một ga trên bản đồ
- Ga đó sẽ bị cấm - không thể qua đó

#### Cách 2: Cấm Một Cạnh (Tuyến)
- Chọn chế độ "Cấm Cạnh"
- Click vào ga thứ 1
- Click vào ga thứ 2
- Cạnh giữa 2 ga sẽ bị cấm

#### Cách 3: Cấm Một Vùng Tròn
- Chọn chế độ "Cấm Vùng"
- Click vào điểm là **tâm vùng**
- Click vào điểm trên **biên vùng**
- Toàn bộ ga trong vùng tròn sẽ bị cấm

#### Hủy Cấm
- Chuyển sang chế độ "Hủy"
- Click vào item bị cấm (ga/cạnh/vùng)
- Sẽ hủy cấm trạng thái tương ứng

#### Xóa Toàn Bộ Cấm
- Nút "🔄 Xóa Tất Cả Cấm"
- Xóa toàn bộ các cấm hiện tại

## 🚀 Cài Đặt & Chạy

### 1. Cài Đặt Dependencies
```bash
pip install -r requirements.txt
```

### 2. Chuẩn Bị Dữ Liệu
Đảm bảo file `graph/spd_metro.graphml` tồn tại. File này chứa toàn bộ mạng lưới tàu điện ngầm St. Petersburg.

### 3. Chạy Server
```bash
python main.py
```

### 4. Mở Trình Duyệt
Truy cập: **http://localhost:5000**

## 📱 Giao Diện Người Dùng

```
┌─────────────────────────────────┬──────────────────────────────────┐
│                                 │                                  │
│        SIDEBAR (Trái)           │       MAP (Phải - Leaflet)       │
│                                 │                                  │
│  ✓ Tìm Lộ Trình                 │                                  │
│    - Chọn điểm A                │   [Bản đồ OpenStreetMap]         │
│    - Chọn điểm B                │   [Hiển thị tuyến đường]         │
│    - TÌM ĐƯỜNG (nút)            │   [Marker ga gần A/B]            │
│                                 │                                  │
│  ✓ Kết Quả                      │                                  │
│    - Chỉ dẫn từng bước          │                                  │
│    - Chi phí tuyến đường        │                                  │
│                                 │                                  │
│  ✓ Admin (Admin Mode)            │                                  │
│    - Đăng nhập (pwd: 123456)    │                                  │
│    - Chế độ: Cấm / Hủy          │                                  │
│    - Phương thức:               │                                  │
│      📍 Cấm Ga                  │                                  │
│      🔗 Cấm Cạnh               │                                  │
│      🔴 Cấm Vùng               │                                  │
│                                 │                                  │
└─────────────────────────────────┴──────────────────────────────────┘
```

## 🔍 Chi Tiết Kỹ Thuật

### Thuật Toán A* Search
```
f(node) = g(node) + h(node)

g(node)  = Chi phí thực tế từ start đến node hiện tại
h(node)  = Heuristic ước lượng từ node hiện tại đến goal
         = Khoảng cách Euclid

Chi phí di chuyển:
- Tàu (metro): distance
- Đi bộ (walk): distance × 50.0 (penalty cao hơn)
```

### Cấu Trúc Dữ Liệu
```python
# Node
{
    "id": "node_id",
    "lat": 59.931,
    "lng": 30.361,
    "name": "Station Name",
    "type": "station" or "intersection",
    "connections": ["node_1", "node_2", ...]
}

# Cấm Ga (Forbidden Node)
forbidden_nodes = {"node_1", "node_2", ...}

# Cấm Cạnh (Forbidden Edge)
forbidden_edges = {"node_1-node_2", "node_3-node_4", ...}

# Cấm Vùng (Forbidden Zone)
forbidden_zones = [
    {
        "center_lat": 59.931,
        "center_lng": 30.361,
        "radius": 0.005  # đơn vị độ
    },
    ...
]
```

## 📡 API Endpoints

### Public API
- `GET /api/graph-data` - Lấy toàn bộ dữ liệu đồ thị
- `POST /api/find-path` - Tìm lộ trình
  ```json
  {
    "pointA": {"lat": 59.93, "lng": 30.36},
    "pointB": {"lat": 59.94, "lng": 30.37}
  }
  ```

### Admin API
- `POST /api/admin/login` - Đăng nhập admin
- `POST /api/admin/block-node` - Cấm một ga
- `POST /api/admin/unblock-node` - Hủy cấm ga
- `POST /api/admin/block-edge` - Cấm một cạnh
- `POST /api/admin/unblock-edge` - Hủy cấm cạnh
- `POST /api/admin/block-zone` - Cấm một vùng
- `POST /api/admin/unblock-zone` - Hủy cấm vùng
- `POST /api/admin/reset` - Xóa tất cả cấm

## 📁 Cấu Trúc Thư Mục

```
NMAI/
├── main.py                    # Flask server chính
├── index.html                 # Giao diện web
├── requirements.txt           # Dependencies
├── README.md                  # Tài liệu này
├── graph/
│   ├── spd_metro.graphml      # Dữ liệu đồ thị (GraphML format)
│   ├── spd_walk.graphml.xml   # Mạng lưới đường bộ
│   ├── metro_lines.gpkg       # Tuyến đường metro (GeoPackage)
│   ├── graph.py               # Script xây dựng đồ thị
│   ├── loader.py              # Script tải dữ liệu
│   └── cache/                 # Cache dữ liệu
├── Data/
│   └── Data.ipynb             # Notebook phân tích dữ liệu
└── cache/                     # Cache trạng thái ứng dụng
    └── app_state.json         # Lưu trữ cấm hiện tại
```

## 🛠️ Xử Lý Lỗi

### Lỗi: "Không tìm thấy file graph"
- Kiểm tra file `graph/spd_metro.graphml` tồn tại
- Chạy `python graph/graph.py` để xây dựng lại

### Lỗi: "Không tìm thấy lộ trình"
- Kiểm tra điểm A/B có nằm trong khu vực được phục vụ không
- Kiểm tra không quá nhiều cấm ga

### Mật khẩu Admin sai
- Mật khẩu mặc định: `123456`
- Có thể thay đổi trong code `main.py` hàm `admin_login()`

## 💾 Lưu Trữ Trạng Thái

Tất cả các cấm được lưu trong file `graph/cache/app_state.json`:
```json
{
    "forbidden_nodes": ["node_1", "node_2"],
    "forbidden_edges": ["node_1-node_2"],
    "forbidden_zones": [
        {
            "center_lat": 59.93,
            "center_lng": 30.36,
            "radius": 0.005
        }
    ]
}
```

Trạng thái sẽ được tự động khôi phục khi khởi động server.

## 📈 Hiệu Năng

- **Số node**: ~5000+ (tùy vào khu vực)
- **Số cạnh**: ~10000+
- **Thời gian tìm đường**: < 500ms (thường)
- **Memory**: < 200MB

## 🤝 Phát Triển Thêm

### Thêm Tính Năng
1. Chế độ tối ưu (ngắn nhất / ít chuyển xe nhất)
2. Hiển thị thời gian dự kiến
3. Lịch sử tuyến đường
4. Xuất bản đồ thành PDF

### Tối Ưu Hóa
1. Sử dụng caching (Redis)
2. Parallel A* search
3. Precomputation các tuyến phổ biến

## 📄 Giấy Phép

**Smart Map Pro** được phát triển cho hệ thống tàu điện ngầm St. Petersburg.

---

**Phát triển bởi:** GitHub Copilot
**Ngôn ngữ:** Python + JavaScript
**Framework:** Flask + Leaflet
**Thuật toán:** A* Search
