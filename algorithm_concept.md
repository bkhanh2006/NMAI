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
- **Cấm Khu Vực Rộng (Forbidden Zones):** Hệ thống xét tọa độ tâm và bán kính 
adius_m: 
  - Toàn bộ Điểm đi bộ và Ga đếm khoảng cách có nhỏ hơn mức bán kính quy quét bị đánh rớt.
  - Các đoạn Cạnh đường (Edge) sẽ bị tính theo phép chiếu điểm hình học Euclid (geometric Euclidean projection) từ tâm vào đoạn nối để chặn nếu đường ấy đâm xuyên qua vùng nguy hiểm. 

Thuật toán của tự động linh hoạt rẽ đi nhánh tối ưu tiếp theo nhờ nguyên lý loại trừ này rỗng mà không cần phải compile lại source code.

## 5. Phân rã Kiến trúc & Luồng xử lý chi tiết

### 5.1. `main.py` (Trái tim của hệ thống định tuyến)
**Ý tưởng:** 
Đây là máy chủ backend (API server) thực hiện nhiệm vụ thiết lập bản đồ tổng và tìm đường đi (Routing). Nó hợp nhất bản đồ mặt đất (đi bộ) và bản đồ ngầm (tàu điện) thành một mạng lưới xuyên suốt. Dựa theo truy vấn của người dùng, nó sử dụng thuật toán trí tuệ nhân tạo (A* Search) tìm ra lộ trình tiêu tốn "Ít thời gian nhất", đồng thời có khả năng "né" các khu vực hoặc nhà ga bị đánh dấu cấm một cách tự động.

**Các bước thực hiện:**
1. **Nạp và Hợp nhất Đồ thị (Graph Loading & Merging):** Tải file đồ thị đi bộ (`spd_walk.graphml`) và tàu điện (`spd_metro.graphml`). Sử dụng cấu trúc dữ liệu không gian KD-Tree để tìm các điểm đi bộ trên phố nằm gần các nhà ga nhất. Cuối cùng, tạo ra các "cạnh chuyển tiếp" (thang máy/lối xuống) để nối đồ thị đi bộ và đồ thị metro tạo thành một hệ thống liên lạc duy nhất (`COMBINED_BASE_GRAPH`).
2. **Khởi tạo Truy vấn (Tạo Nút A và B):** Khi người dùng chọn 2 tọa độ bất kỳ làm điểm đi và đến, hệ thống dùng KD-Tree để chiếu tọa độ đó vào 6 điểm đi bộ gần nhất trên mạng lưới thực tế, gán tên là điểm `__point_a__` và `__point_b__`.
3. **Tiến hành tìm đường bằng Thuật toán A*:** 
   - **G-score (Chi phí thực tế):** Tính bằng Khoảng cách (km) chia cho Vận tốc (4.8km/h đối với đi bộ, 36km/h đối với tàu). 
   - **H-score (Heuristic):** Tính khoảng cách chim bay (Haversine Distance) từ điểm đang xét thẳng đến đích.
4. **Cơ chế kiểm soát vùng cấm (Admin Blocks):** Trong quá trình đồ thị duyệt các nút lân cận, nếu nút (hoặc đường cắt qua) nằm trong danh sách cấm hoặc "vùng nguy hiểm" (tính toán bằng hình học chiếu Euclidean), thuật toán sẽ thẳng tay loại trừ và tự động bẻ nhánh, tìm con đường tối ưu thứ hai tiếp theo để lách qua.

### 5.2. `build_metro.py` (Xây dựng đồ thị Tàu điện ngầm)
**Ý tưởng:** 
Khai thác dữ liệu hệ thống Tàu điện ngầm của St. Petersburg từ bản đồ mã nguồn mở để tạo ra một biểu đồ mạng lưới (nodes và edges), đo lường quãng đường giữa các bến nhằm phục vụ việc chạy thuật toán ở `main.py`.

**Các bước thực hiện:**
1. **Truy xuất dữ liệu:** Tải về các điểm là nhà ga (chứa thẻ `station: subway`) và các đường ray hầm nối (chứa thẻ `railway: subway`) từ thư viện OpenStreetMap (khu vực Sankt-Peterburg). Bỏ qua các tuyến tàu đang xây hoặc bỏ hoang.
2. **Xử lý Nhà ga (Nodes):** Tính toán điểm trung tâm (centroid) của toàn bộ khuôn viên nhà ga để lấy kinh độ/vĩ độ chính xác, đồng thời áp dụng lưới lọc chặn những nhà ga sai lệch hoặc không được phép sử dụng. Những nhà ga này trở thành các "Đỉnh" của đồ thị.
3. **Liên kết tuyến đường (Edges):** Nối các đoạn ray gãy khúc lại thành một tuyến ray liền mạch. Rà dọc theo tuyến ray để xem các nhà ga nào gần đường ray dưới 250m, thiết lập thuật toán gộp những ga của cùng một trạm chuyển tuyến nằm quá sát nhau thành một điểm (bằng hệ số chiếu nhóm 350m). Cuối cùng nối chúng lại theo thứ tự để tạo ra các "Cạnh" mạng lưới và gán vận tốc tiêu chuẩn cho Tàu điện.
4. **Đóng gói file:** Lưu đồ thị hoàn thiện xuất dưới định dạng `spd_metro.graphml`.

### 5.3. `build_walk.py` (Xây dựng đồ thị Đi bộ mặt đất)
**Ý tưởng:** 
Rút trích các khung đường bộ, vỉa hè dành cho người đi bộ của toàn bộ thành phố. Sau đó "tinh gọn" hóa nó để không làm nặng hệ thống thuật toán, nhưng vẫn phải đảm bảo chuẩn định dạng để tích hợp tương thích hoàn toàn với file `main.py`.

**Các bước thực hiện:**
1. **Truy xuất dữ liệu:** Download toàn bộ mạng lưới bộ hành OpenStreetMap thông qua module OSMnx.
2. **Tinh chỉnh không gian & Giảm tải (Pruning & Consolidation):** Lưới đường bộ có rất nhiều nút bị trùng lặp tại giao lộ, hệ thống hợp nhất chúng trong sai số 15 mét vào làm 1. Nếu có hai lối đi song song nối giữa hai trạm, tự động xóa lối dài hơn và chỉ giữ bản gốc ngắn nhất. Xóa toàn bộ metadata thừa (tên đường, số làn, ánh sáng, độ dốc...) để file đồ thị nhẹ đi nhiều lần.
3. **Chuẩn hóa Thông số:** Chi phí trọng số trên mỗi con đường được gán dựa trên vận tốc đi bộ.
4. **Phòng ngừa Xung đột ID:** Thêm tiền tố `"w_"` (nghĩa là walk) vào ID của toàn bộ các điểm giao đi bộ. Bước này cốt yếu để khi `main.py` chập hai đồ thị lại, các ID ga Tàu điện ngầm (dạng số) không bị trùng đè lên các ID gốc của lưới đường bộ, tránh làm đứt rãy mạng lưới.
5. **Đóng gói file:** Xuất đồ thị hoàn thiện ra file `spd_walk.graphml`.

