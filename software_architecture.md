# Smart Map Pro - Kiến trúc Phần mềm (Software Architecture)

## 1. Mô hình Hệ thống (System Paradigm)
Smart Map Pro vận hành theo quy chuẩn Client-Server Architecture:
- **Giao diện Người dùng - Client (Frontend):** Ứng dụng theo dạng Single Page Application (SPA), nghĩa là chỉ dùng trang HTML liền mạch thay đổi dữ liệu DOM. Cấu hình giao diện trên DOM bằng CSS (sử dụng thư viện TailwindCSS) và Vanilla JavaScript thuần trên file index.html.
- **Máy trạm Xử lý - Server (Backend):** Vận hành như thiết kế RESTful API từ ngôn ngữ Python kết hợp Web-framework Flask nhẹ gọn. Nắm vai trò xử lý bản đồ ảo và thực thi thuật toán A-Star.

## 2. Kiến trúc cụ thể Frontend (index.html)
Toàn bộ logic tương tác DOM đều độc lập gói trong tệp index.html:
- **Động cơ Bản đồ (Mapping Engine):** Gọi lớp thư viện **Leaflet.js**, nạp tile đồ họa trực quan từ máy chủ OpenStreetMap. Lớp điều hướng UI liên tục vẽ đa giác, đổ màu hành trình và hiển thị đối tượng không gian.
- **Công cụ Đồ họa (UI Framework):** Gắn cờ thuộc tính nhanh của **TailwindCSS** kèm với nhúng symbol "Lucide" tạo bộ control panel có cái nhìn hiện đại.
- **Quản trị Truyền Dữ liệu (State & Network):** Dựa hoàn toàn vào closure, local scope, và API Fetch mặc định của JS để trỏ ngầm API (như /api/graph-data, /api/find-path) thông báo từ Node backend mỗi khi người dùng có hành động chọn, cấm điểm.

## 3. Kiến trúc cụ thể Backend (main.py)
Mọi cơ cấu logic lõi nằm trọn bên trong tệp máy chủ main.py:
- **Module Mạng HTTP (API Engine):** Flask tổ chức định tuyến liên kết cùng thành phần lask_cors cung cấp dịch vụ xuyên suốt (tránh sự cố Policy chặn Web browser qua localhost).
- **Phân tách Đồ thị (Graph Parser):** Mô đun **NetworkX** chuyển phân nhánh .graphml thành đồ thị có hướng/ vô hướng tương thích toán học cho thuật toán ở python.
- **Tiện ích Toán Không gian (Geolocation Utilities):** 
  - **PyProj:** Công cụ chuyển đổi hình thái học tọa độ (Tọa độ UTM qua Kinh độ và Vĩ độ hình cầu kinh tuyến).
  - **Scipy (cKDTree):** Tốc lực hóa thời gian cho mô-đun tìm cấu trúc mạng hàng vạn điểm đi bộ của đô thị để nội suy lân cận gần nhất (Nearest neighbor index).
- **Đệm Trạng thái Admin (AppState):** Các lệnh Admin tương tác chặn Vùng/Cạnh/Nút không lưu qua Database (SQL/MongoDB) mà đính lưu cục bộ thẳng vào cờ class thể hiện tên AppState ngay trên bộ nhớ tiến trình (In-Memory Memory). Điều này là một sự hy sinh không lưu trữ dữ liệu vĩnh viễn bù lại tốc thuật toán không bị trượt 1 mili-giây delay mạng nào.

## 4. Băng chuyền Hoạt động Ứng dụng (Application Lifecycle)
1. **Khởi Động Nguồn:** Tệp Python parse các đồ thị graph/spd_metro & walk ra. Liên hợp tất cả nối lại tạo thành đối tượng biến hằng đẳng COMBINED_BASE_GRAPH.
2. **Nạp Client:** Khi Web nạp vào port hiện lên, HTML đè một lệnh /api/graph-data trả JSON để lấp đầy trạm trên layer của trình duyệt Leaflet.
3. **Mệnh Lệnh Ghi Đè (Chặn Đường):** Khi Quản trị viên tương tác gõ cấm, Admin Fetch gọi Post trực tiếp về Backend => Backend lấy và sửa danh sách List chặn trong AppState class ngay trên RAM (Real-time).
4. **Mệnh Lệnh Đọc Tuyến (Tính Lộ Trình):** Khi người dùng chấm tọa độ, Node sẽ găm điểm ảo để tìm trên đồ thị, hàm A* né danh sách trong AppState, phản hồi Array tọa độ chuỗi (Steps, Polylines) và frontend tự động render nó bằng polyline.
