# Smart Map Pro — Multimodal Route Finder

Ứng dụng Flask + Leaflet để tìm đường đa phương thức (đi bộ + metro) trên đồ thị thành phố.

Key points:
- Vùng cấm (zone) cấm cả đi bộ và metro.
- Cấm một cạnh (edge) sẽ cấm tất cả các ga trên đoạn tuyến đó.
- Backend lưu bán kính vùng dưới dạng mét (`radius_m`) và so sánh bằng khoảng cách Haversine.

---

## Quickstart

1. Cài dependencies:

```bash
pip install -r requirements.txt
```

2. Chuẩn bị dữ liệu: đặt các file đồ thị trong `graph/` (ví dụ `graph/spd_metro.graphml`).

3. Chạy server:

```bash
python main.py
```

4. Mở GUI: http://localhost:5000

---

## Hành vi cấm (Important)

- Zone: toàn bộ khu vực hình tròn bị cấm cho mọi phương thức (walking & metro). Backend so sánh bằng mét; frontend gửi bán kính dạng delta-degrees nhưng server sẽ chuyển sang `radius_m`.
- Edge: khi admin chặn một cạnh, hệ thống sẽ xây dựng tuyến metro tương ứng và đánh dấu tất cả ga trên tuyến đó là `forbidden_nodes` — nghĩa là không thể đi qua các ga này.

---

## API (tóm tắt)

Public:
- `GET /api/graph-data` — trả về nodes, edges, forbidden_*
- `POST /api/find-path` — body: `{ "pointA": {lat,lng}, "pointB": {lat,lng} }` → trả `path_nodes`, `metro_segments`, `walk_segments`, `steps`, `total_distance_m`, `total_time_min`.

Admin (password mặc định `123456` — thay đổi trong `main.py` nếu cần):
- `POST /api/admin/login` — {password}
- `POST /api/admin/block-node` — {node_id, password}
- `POST /api/admin/unblock-node` — {node_id, password}
- `POST /api/admin/block-edge` — {node1, node2, password}
- `POST /api/admin/unblock-edge` — {node1, node2, password}
- `POST /api/admin/block-zone` — {center_lat, center_lng, radius, [boundary_lat, boundary_lng], password}
- `POST /api/admin/unblock-zone` — {center_lat, center_lng, radius, password}
- `POST /api/admin/reset` — {scope: all|nodes|edges|zones, password}

Notes:
- When posting `block-zone`, if you include `boundary_lat/boundary_lng` the server computes exact `radius_m` from that boundary point. Otherwise it converts the provided `radius` (assumed as delta-degrees) into meters by multiplying ~111000.

---

## Troubleshooting

- Nếu server báo lỗi thiếu graph files: kiểm tra `graph/spd_metro.graphml` và `graph/spd_walk.graphml`.
- Nếu đường vẫn hiển thị sau khi cấm: refresh trang (frontend bôi cũ có thể còn route cũ); hệ thống đã xóa route cũ khi reload dữ liệu.
- Nếu route trả về mặc định và vẫn đi vào vùng cấm: đảm bảo server đang chạy phiên bản mới (restart server sau thay đổi code).

---

## Development notes

- Entry point: `main.py` — chứa load graph, xây dựng `COMBINED_BASE_GRAPH`, A* pathfinding và các API.
- Frontend: `index.html` — Leaflet map + admin UI.
- Forbidden state: `AppState` (in-memory) with `forbidden_nodes`, `forbidden_edges`, `forbidden_edge_routes`, `forbidden_zones`. No long-term persistence (cache/ app_state.json used for debugging only).

---

## Contributing ideas

- Improve heuristics for mixed-mode routing.
- Add auth for admin endpoints.
- Add unit tests for geometry/on-zone checks.

---

License: (add your preferred license)

Contact / Maintainer: repository owner
