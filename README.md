# Smart Map Pro — Trợ lý Tìm đường Đa phương thức

Ứng dụng tìm đường kết hợp linh hoạt giữa **Đi bộ** và **Tàu điện ngầm (Metro)** tại khu vực St. Petersburg. Hệ thống được xây dựng bằng Python (Flask + thư viện xử lý đồ thị NetworkX) cho Backend và giao diện bản đồ trực quan bằng JavaScript (Leaflet.js + TailwindCSS) ở Frontend.

---

## 🌟 Các tính năng chính

- **Định tuyến Đa phương thức:** Thuật toán A* (A-Star) tự động tính toán chuỗi chặng đi tối ưu nhất về thời gian, kết hợp mượt mà giữa các đoạn đi bộ trên phố và quá trình bắt chuyến di chuyển bằng tàu điện ngầm.
- **Mô phỏng sự cố theo Thời gian thực (Admin Mode):** Giao diện quản trị viên cho phép giả lập các khu vực tắc đường, thiên tai hoặc nhà ga ngừng hoạt động một cách linh hoạt mà không cần khởi động lại ứng dụng:
  - **🔴 Cấm Vùng (Zone Blocking):** Khoanh vùng khu vực chịu ảnh hưởng theo bán kính. Mọi thao tác đi qua khu vực này (kể cả trên mặt đất lẫn ngầm) đều bị buộc phải chuyển hướng đi vòng.
  - **🔗 Cấm Cạnh (Edge Blocking):** Chặn cụ thể tuyến đường di chuyển giữa hai ga metro nối tiếp nhau (mô phỏng đường ray bảo trì).
  - **📍 Cấm Ga/Điểm (Node Blocking):** Đóng cửa hoàn toàn một nhà ga nhất định (mô phỏng cháy nổ hoặc sửa chữa ga).
- **Xử lý Bộ nhớ Tại chỗ (In-Memory Tracking):** Các lệnh thay đổi cấu trúc đồ thị được Backend lưu cục bộ trên RAM (thông qua class `AppState`). Không yêu cầu database phức tạp, giúp thuật toán phản hồi mượt mà và cực nhanh.

---

## 🚀 Hướng dẫn Cài đặt & Khởi chạy

1. **Cài đặt các thư viện cần thiết:**
   `ash
   pip install -r requirements.txt
   `

2. **Chuẩn bị dữ liệu (Graph Data):** Đảm bảo các file mô tả mạng lưới bản đồ đã được đặt chuẩn xác trong thư mục `graph/`:
   - `graph/spd_metro.graphml` (Dữ liệu mạng lưới tàu điện)
   - `graph/spd_walk.graphml` (Dữ liệu mạng lưới đường đi bộ)

3. **Khởi chạy Máy chủ (Server):**
   `ash
   python main.py
   `

4. **Sử dụng Ứng dụng:**
   Mở trình duyệt web của bạn và truy cập địa chỉ: http://localhost:5000

---

## 📖 Hướng dẫn Sử dụng Chi tiết

### 1. Dành cho Người dùng (Tìm đường)
- **Bước 1:** Ngay khi mở bản đồ, bảng điều khiển mặc định yêu cầu bạn chọn điểm xuất phát. Hãy **click chuột trái** vào một vị trí cụ thể trên bản đồ làm **Điểm A**.
- **Bước 2:** Tiếp tục **click chuột trái** vào vị trí đích đến để tạo **Điểm B**.
- **Bước 3:** Bấm nút **"TÌM ĐƯỜNG"** màu xanh.
- **Bước 4:** Lộ trình sẽ xuất hiện (Đoạn màu cam là đoạn đi bộ, các đoạn màu khác là line Metro theo từng chặng). Bảng bên trái sẽ hiển thị chi tiết khoảng cách, thời gian và chỉ dẫn từng chặng phân tầng rõ ràng.
- *Tip:* Bạn có thể bật chức năng tùy chọn "Hiện tất cả ga" để dễ dàng thấy hệ thống đường ngầm trên nền đồ thị.

### 2. Dành cho Quản trị viên (Kiểm thử mô phỏng sự cố)
- **Đăng nhập:** Cuộn xuống góc dưới cùng bên thanh menu trái, nhập mật khẩu admin (Mặc định: `123456`) và ấn "Vào".
- **Sử dụng Chế độ Cấm (Block Mode):**
  - **Cấm Ga:** Nhấn vào "📍 Cấm Ga", đảm bảo nút "CẤM" màu đỏ phía trên đang được chọn, sau đó nhấp vào ga metro mà bạn muốn đóng cửa trên bản đồ (nhân vật sẽ tránh ga này).
  - **Cấm Cạnh:** Nhấn vào "🔗 Cấm Cạnh", bật "Hiện tất cả ga" để dễ nhìn. Trình tự làm: click đúp ga đầu tiên, sau đó click ga kế tiếp, đường link bị cấm sẽ hiện màu đỏ đậm báo hiệu mất kết nối.
  - **Cấm Vùng:** Nhấn "🔴 Cấm Vùng", nhấp điểm đầu tiên để chọn tâm vùng cấm, kéo thả và nhấp điểm thứ hai tạo bán kính. Một vòng tròn đánh dấu vùng cấm sẽ xuất hiện trên bản đồ.
- **Gỡ bỏ Cấm (Unblock Mode):**
  - Để gỡ đối tượng độc lập: Đổi tab sang "HỦY" (màu xanh lá thẫm) ở trên cùng. Tương tự như trên, sau đó click lại vào ga, cạnh, hoặc vùng cấm hiện hữu để giải phóng nó.
  - Chức năng tiện ích: Bạn có thể chọn "Xóa tất cả điểm/cạnh/vùng..." trên bảng menu bằng các nút dọn dẹp màu nhanh gọn.

---

## 📂 Cấu trúc Dự án
Để tìm hiểu sâu hơn về kỹ thuật và logic thuật toán đằng sau Smart Map Pro, vui lòng tham khảo các tài liệu phân tích kỹ thuật của dự án:
- [Ý Tưởng Thuật Toán (algorithm_concept.md)](algorithm_concept.md) - Giải thích cụ thể cách thuật toán A-Star đa phương thức hoạt động với hai lớp mạng lưới đan tầng.
- [Kiến trúc Phần Mềm (software_architecture.md)](software_architecture.md) - Các chi tiết kỹ thuật về luồng giao tiếp giữa SPA (Leaflet) và máy chủ Python (Flask).
