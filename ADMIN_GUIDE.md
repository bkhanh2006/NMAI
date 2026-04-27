# 👨‍💼 Admin Features - Hướng Dẫn Chi Tiết

## 🔐 Đăng Nhập Admin

### Bước 1: Nhập Mật Khẩu
- Tìm ô "Đăng Nhập Admin" ở cuối sidebar
- Nhập mật khẩu: `123456`
- Nhấn nút "Vào"

### Bước 2: Kích Hoạt Chế Độ Admin
Khi đăng nhập thành công:
- Hiển thị: **✓ ADMIN MODE** (màu xanh)
- Nút "Thoát" để đăng xuất
- 2 chế độ: **CẤM** / **HỦY**
- 3 phương thức cấm

---

## 🚫 Các Tính Năng Cấm

### 1️⃣ Cấm Một Ga (Block Station)

**Mục đích:** Ngừng hoạt động một ga tàu điện ngầm

**Cách sử dụng:**
```
1. Chọn chế độ: CẤM
2. Chọn phương thức: 📍 Cấm Ga
3. Đợi thông báo: "📍 Click vào 1 ga để cấm"
4. Click trực tiếp trên bản đồ tại vị trí ga cần cấm
5. Xác nhận cấm: "✓ Đã cấm ga: [Station Name]"
```

**Ví dụ:**
```
Ban quản lý metro phát hiện ga Nevskiy Prospekt có sự cố.
→ Click vào ga đó trên bản đồ
→ Ga bị cấm, tuyến đường sẽ tự động tránh ga này
```

**Tác dụng:**
- Ga không thể được chọn làm điểm đi/đến
- Mọi lộ trình A* sẽ tránh ga này
- Dữ liệu được lưu vào `graph/cache/app_state.json`

---

### 2️⃣ Cấm Một Cạnh (Block Edge/Line)

**Mục đích:** Cấm tuyến kết nối giữa 2 ga (bảo trì đường ray, v.v.)

**Cách sử dụng:**
```
1. Chọn chế độ: CẤM
2. Chọn phương thức: 🔗 Cấm Cạnh
3. Đợi thông báo: "🔗 Click vào 2 ga để cấm cạnh giữa chúng"
4. Click vào ga thứ 1
   → Thông báo: "Chọn 1 ga khác để cấm cạnh. Ga 1: [Station A]"
5. Click vào ga thứ 2
   → Xác nhận: "✓ Đã cấm cạnh: [Station A] ↔ [Station B]"
```

**Ví dụ:**
```
Đoạn đường từ "Nevskiy Prospekt" đến "Gostinyy Dvor" đang bảo trì.
→ Click vào "Nevskiy Prospekt"
→ Click vào "Gostinyy Dvor"
→ Đường kết nối bị cấm, tàu không thể di chuyển trực tiếp giữa 2 ga này
→ Hệ thống tìm tuyến đường khác qua các ga lân cận
```

**Tác dụng:**
- Cạnh cụ thể không thể được sử dụng trong lộ trình
- Nếu chỉ có 1 cạnh giữa 2 ga, chúng trở nên không kết nối
- Chi phí tuyến đường có thể tăng do phải đi đường vòng

---

### 3️⃣ Cấm Một Vùng Tròn (Block Zone)

**Mục đích:** Cấm toàn bộ ga trong một khu vực (địa chấn, tai nạn lớn, v.v.)

**Cách sử dụng:**
```
1. Chọn chế độ: CẤM
2. Chọn phương thức: 🔴 Cấm Vùng
3. Đợi thông báo: "🔴 Click 2 điểm: tâm vùng, rồi điểm trên biên"
4. Click điểm thứ 1 (TÂM VÙNG)
   → Bản đồ hiển thị điểm đó bằng ⭕
5. Click điểm thứ 2 (BIÊN VÙNG)
   → Bản đồ vẽ vòng tròn
   → Xác nhận: "✓ Đã cấm vùng với bán kính [X]km"
```

**Ví dụ:**
```
Khu vực trung tâm thành phố bị cấm do sự kiện đặc biệt.
- Tâm vùng: Cung Điện Mùa Đông (59.9390, 30.3156)
- Bán kính: 2km

→ Click vào Cung Điện
→ Click vào điểm cách 2km
→ Toàn bộ ga trong vòng tròn này bị cấm
→ Tuyến đường sẽ tìm vòng quanh vùng cấm
```

**Tác dụng:**
- Tất cả ga nằm trong vòng tròn bị cấm
- Hệ thống tự động tránh vùng này trong A*
- Bán kính tính bằng độ (latitude/longitude), sau được chuyển sang mét

**Công thức tính:**
```
Bán kính (độ) = distance từ tâm đến biên
Khoảng cách ≈ bán kính × 111 km
```

---

## ❌ Hủy Cấm (Unblock)

**Mục đích:** Loại bỏ các cấm đã đặt (hết sự cố, hết bảo trì, v.v.)

**Cách sử dụng:**
```
1. Chọn chế độ: HỦY
2. Chọn phương thức (Node / Edge / Zone)
3. Thông báo: "📍 Click vào ga bị cấm để hủy" (hoặc cạnh/vùng)
4. Click vào item bị cấm
5. Xác nhận: "✓ Hủy cấm ga: [Station Name]"
```

**Ví dụ:**
```
Ga Nevskiy Prospekt đã sửa xong.
→ Chế độ HỦY + 📍 Cấm Ga
→ Click vào ga đó
→ Ga được mở lại, có thể sử dụng bình thường
```

---

## 🔄 Xóa Tất Cả Cấm

**Nút:** 🔄 Xóa Tất Cả Cấm

**Tác dụng:**
- Xóa toàn bộ ga bị cấm
- Xóa toàn bộ cạnh bị cấm
- Xóa toàn bộ vùng cấm
- Trả về trạng thái bình thường

**Chú ý:**
- Hệ thống sẽ yêu cầu xác nhận: "Xóa tất cả cấm?"
- Không thể hoàn tác sau khi xác nhận

---

## 📊 Quản Lý Trạng Thái

### Lưu Trữ
- Tất cả cấm được tự động lưu vào: `graph/cache/app_state.json`
- Format:
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

### Khôi Phục
- Khi server khởi động, trạng thái sẽ được tự động khôi phục
- Dữ liệu cấm được giữ ngay cả khi tắt server

### Kiểm Tra Trạng Thái Hiện Tại
- Gọi API: `GET /api/graph-data`
- Trả về danh sách:
  - `forbidden_nodes`: Tất cả ga bị cấm
  - `forbidden_edges`: Tất cả cạnh bị cấm
  - `forbidden_zones`: Tất cả vùng cấm

---

## 🔒 Bảo Mật

### Mật Khẩu
- **Mặc định:** `123456`
- **Vị trí:** `main.py`, hàm `admin_login()`
- **Cách đổi:** Sửa password trong code

### Quyền Hạn
- Chỉ admin mới có quyền cấm/hủy
- Mọi thay đổi đều lưu log trong `app_state.json`

---

## ⚠️ Những Điểm Cần Lưu Ý

### 1. Cấm Quá Nhiều Ga
- Nếu cấm quá nhiều, có thể không tìm được lộ trình
- Hệ thống trả về lỗi: "Không tìm thấy lộ trình"

### 2. Cấm Cạnh Quan Trọng
- Nếu cấm tất cả cạnh của một ga, ga đó trở nên cô lập
- Không thể qua ga này

### 3. Vùng Cấm Giao Nhau
- Nếu có nhiều vùng cấm giao nhau, ga sẽ bị cấm nếu nằm trong BẤT KỲ vùng nào

### 4. Tính Toán Bán Kính Vùng
- Bán kính = độ (latitude/longitude)
- 1 độ ≈ 111 km trên Trái Đất
- 0.01 độ ≈ 1.1 km
- 0.001 độ ≈ 111 mét

---

## 🧪 Kiểm Thử

### Test Cấm Ga
```
1. Tìm lộ trình A → B (trước cấm)
2. Admin cấm 1 ga trên tuyến đường
3. Tìm lộ trình lại (sẽ khác hoặc lỗi)
4. Kiểm tra file app_state.json
```

### Test Vùng Cấm
```
1. Chọn tâm và biên vùng gần nhau (trong 100m)
2. Tìm lộ trình qua vùng này
3. Hệ thống phải tránh vùng
4. Xóa vùng cấm, tìm lộ trình lại
```

---

## 💡 Gợi Ý Sử Dụng

### Bảo Trì Thường Xuyên
```
1. Mỗi tuần thứ 2 bảo trì ga Nevskiy Prospekt
   → Admin cấm ga từ 22:00 - 06:00 hôm sau
   → Sau đó hủy cấm

2. Bảo trì cạnh giữa 2 ga
   → Cấm cạnh (không cấm ga)
   → Người dùng vẫn có thể dùng ga, nhưng phải đi vòng
```

### Sự Cố Đột Ngột
```
1. Phát hiện vụ nổ ở khu vực Central
   → Cấm vùng tròn với bán kính 5km
   → Tất cả ga trong vùng bị cấm
   → Tuyến đường tự động reroute

2. Sửa xong → Xóa vùng cấm
```

---

## 📞 Hỗ Trợ

### Lỗi Thường Gặp

**Q: Không thể cấm ga?**
- A: Kiểm tra đã đăng nhập admin chưa
- A: Kiểm tra mật khẩu có đúng không

**Q: Bản đồ không hiển thị cấm?**
- A: Refresh trang (F5)
- A: Kiểm tra JavaScript console

**Q: Không tìm được lộ trình?**
- A: Có thể quá nhiều cấm
- A: Kiểm tra điểm A/B có hợp lệ không

---

Chúc bạn sử dụng Smart Map Pro hiệu quả! 🚇✨
