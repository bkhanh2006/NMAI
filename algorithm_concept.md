# Smart Map Pro - Ý tưởng & Thuật toán (Algorithm Concept)

## 1. Tổng quan
Cốt lõi của Smart Map Pro là thuật toán tìm đường **A* (A-Star)** đa phương thức, được tinh chỉnh để tìm được một con đường kết hợp tối ưu nhất giữa đi bộ trên bề mặt lãnh thổ và sử dụng các tuyến tàu điện ngầm quanh thành phố St. Petersburg.

## 2. Quá trình Xây dựng Đồ thị (COMBINED_BASE_GRAPH)
Khi hệ thống máy chủ khởi động, nó hợp nhất các đồ thị thành một mảng mạng lưới ảo liền mạch (COMBINED_BASE_GRAPH) dùng để tìm đường:
- **Đồ thị Đi bộ (Walk Graph):** Lưới đường đi bộ được nạp từ file spd_walk.graphml, phân bổ từng ngã rẽ và các vỉa hè dưới dạng tọa độ latitude & longitude.
- **Đồ thị Tàu điện (Metro Graph):** Thu thập dữ liệu từ spd_metro.graphml, ghi nhận các ga tàu và đường hầm nối.
- **Xây dựng Liên kết (Transfers):** Làm sao để máy tính nhận diện lúc nào hành khách từ phố xuống ga ngầm? Hệ thống tích hợp thuật toán tìm kiếm khoảng lân cận gần nhất (KD-Tree thông qua module scipy.spatial.cKDTree). Với mỗi điểm ga metro, thuật toán tạo một đoạn thẳng vô hình gán nối nhà ga này với nút lưới đường bộ gần nhất (gọi là cầu nối chuyển tiếp).

## 3. Hoạt động Thuật toán tìm kiếm A*
Dự án vận hành trên biến thể cơ bản nhưng tối giản tối ưu nhất trong lý thuyết đồ thị:
- **Khởi tạo và Biểu diễn trạng thái:** Để người dùng chọn bản đồ tự do, thuật toán sinh ra tạm thời 2 nút tọa độ giả __point_a__ và __point_b__. Nó cũng dùng KD-Tree để kéo 6 móc vô hình từ vị trí chọn nối đến 6 nút đường phố hợp lệ gần đó nhất để tạo trạm lên bờ.
- **Hàm Chi phí $g(n)$:** Đo lường phí "Thời gian di chuyển". Do vận tốc chênh lệch (Đi bộ: 4.8 km/h, đi Tàu: 36.0 km/h), khoảng cách vật lý của từng cung đoạn được chia cho tiêu chuẩn này để tạo hệ số thời gian (Phút). Mục tiêu là *Tối thiểu hóa Thời gian đi*.
- **Hàm Heuristic $h(n)$:** Khoảng ước lượng lý tưởng nhất từ vị trí dò hiện tại đến __point_b__. Smart Map áp dụng công thức *Khoảng cách Haversine* (Độ cong khoảng cách mặt cầu trái đất) của điểm n đến đích, sau đó chia cho 36 km/h. Vì kết quả mang ra của phương thức này luôn thấp hơn thời gian thật, hàm heuristic này cam kết *tính toàn vẹn tuyệt đối (Admissible)* - luôn luôn tìm ra con đường tốt nhất.

## 4. Cơ chế Cản trở Không gian (Admin Dynamic Constraints)
Trong quá trình vòng lặp mở của thuật toán A* phân trần đỉnh tiếp cận lân cận, bộ kiểm tra (validation) trực tiếp chặn đứng những phương án sau:
- **Cấm Ga (Forbidden Nodes):** Kiểm tra xem ga metro có lọt vào mảng cách ly orbidden_nodes.
- **Cấm Cạnh (Forbidden Edges):** Tránh những đường tiếp cận cầu nối (u, v) trực tiếp vướng rào cản.
- **Cấm Khu Vực Rộng (Forbidden Zones):** Hệ thống xét tọa độ tâm và bán kính adius_m: 
  - Toàn bộ Điểm đi bộ và Ga đếm khoảng cách có nhỏ hơn mức bán kính quy quét bị đánh rớt.
  - Các đoạn Cạnh đường (Edge) sẽ bị tính theo phép chiếu điểm hình học Euclid (geometric Euclidean projection) từ tâm vào đoạn nối để chặn nếu đường ấy đâm xuyên qua vùng nguy hiểm. 

Thuật toán của tự động linh hoạt rẽ đi nhánh tối ưu tiếp theo nhờ nguyên lý loại trừ này rỗng mà không cần phải compile lại source code.
