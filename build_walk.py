import math
import os

import networkx as nx
import osmnx as ox


# ---------------------------------------------------------------------------
# 1. CẤU HÌNH & HÀM HỖ TRỢ
# ---------------------------------------------------------------------------

PLACE_NAME = "Saint Petersburg, Russia"
OUT_WALK = r"C:\Users\LENOVO\Documents\GitHub\NMAI\graph\spd_walk.graphml"

WALK_SPEED_M_PER_MIN = 5000.0 / 60.0

# Tiền tố áp dụng cho mọi ID để tránh trùng lặp mới metro 
WALK_NODE_PREFIX = "w_"

# Các thẻ OSM làm tăng kích thước file nhưng không được main.py sử dụng.
EDGE_TAGS_TO_DROP = (
    "osmid", "name", "ref", "highway", "maxspeed", "service", "access",
    "area", "landuse", "width", "est_width", "lanes", "bridge", "tunnel",
    "junction", "oneway", "reversed", "from", "to", "surface", "smoothness",
    "sidewalk", "foot", "bicycle", "lit", "tracktype", "incline",
)
NODE_TAGS_TO_DROP = (
    "osmid", "osmid_original", "highway", "ref", "street_count", "junction",
)

ox.settings.use_cache = True
ox.settings.log_console = True
ox.settings.timeout = 300



# Các hàm hỗ trợ

# Hàm tính khoảng cách Haversine giữa 2 điểm WGS84, trả về mét
def _haversine_m(lat1, lng1, lat2, lng2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))

# Hàm gộp các cạnh song song giữa cùng 2 nút, giữ lại cạnh có độ dài nhỏ nhất
def _collapse_parallel_edges(graph):
    g = graph.copy()

    best_edge_per_pair = {}     
    edges_to_remove = []

    for u, v, k, data in g.edges(keys=True, data=True):
        pair = tuple(sorted((str(u), str(v))))
        length = float(data.get("length", 0.0)) or 0.0

        if pair not in best_edge_per_pair:
            best_edge_per_pair[pair] = (length, u, v, k)
            continue

        prev_length, pu, pv, pk = best_edge_per_pair[pair]
        if length < prev_length:
            edges_to_remove.append((pu, pv, pk))
            best_edge_per_pair[pair] = (length, u, v, k)
        else:
            edges_to_remove.append((u, v, k))

    for u, v, k in edges_to_remove:
        if g.has_edge(u, v, key=k):
            g.remove_edge(u, v, key=k)

    return g

#Hàm loại bỏ các thẻ không cần thiết khỏi dữ liệu đồ thị, giúp giảm kích thước file khi lưu dưới dạng GraphML.
def _drop_tags(graph):
    for _, data in graph.nodes(data=True):
        for tag in NODE_TAGS_TO_DROP:
            data.pop(tag, None)

    if graph.is_multigraph():
        for _, _, _, data in graph.edges(keys=True, data=True):
            for tag in EDGE_TAGS_TO_DROP:
                data.pop(tag, None)
    else:
        for _, _, data in graph.edges(data=True):
            for tag in EDGE_TAGS_TO_DROP:
                data.pop(tag, None)

#Ép kiểu các thuộc tính dạng mảng/danh sách thành string để tương thích với GraphML
def _stringify_attr_values(graph):
    for _, data in graph.nodes(data=True):
        for key, val in list(data.items()):
            if isinstance(val, (list, dict, tuple, set)):
                data[key] = str(val)

    if graph.is_multigraph():
        for _, _, _, data in graph.edges(keys=True, data=True):
            for key, val in list(data.items()):
                if isinstance(val, (list, dict, tuple, set)):
                    data[key] = str(val)
    else:
        for _, _, data in graph.edges(data=True):
            for key, val in list(data.items()):
                if isinstance(val, (list, dict, tuple, set)):
                    data[key] = str(val)

#Xóa bỏ các nút có tọa độ lỗi hoặc chưa chuyển đổi về hệ kinh-vĩ độ [-180, 180], [-90, 90] để tránh làm sai lệch thuật toán tìm kiếm không gian (KD-Tree).
def _prune_invalid_wgs84_nodes(graph):
    bad = []
    for node_id, data in graph.nodes(data=True):
        try:
            x = float(data.get("x"))
            y = float(data.get("y"))
        except (TypeError, ValueError):
            bad.append(node_id)
            continue

        if not (-180.0 <= x <= 180.0 and -90.0 <= y <= 90.0):
            bad.append(node_id)

    if bad:
        graph.remove_nodes_from(bad)

    return len(bad)

# Hàm thêm namespace vào ID node để tránh trùng lặp với build_metro.py
def _namespace_node_ids(graph, prefix=WALK_NODE_PREFIX):
    mapping = {n: f"{prefix}{n}" for n in graph.nodes}
    return nx.relabel_nodes(graph, mapping, copy=True)


# ---------------------------------------------------------------------------
# 2. XÂY DỰNG ĐỒ THỊ ĐI BỘ
# ---------------------------------------------------------------------------

def main():
    print("--- Downloading walk graph for:", PLACE_NAME, "---")
    g_walk = ox.graph_from_place(
        PLACE_NAME,
        network_type="walk",
        simplify=True,
        retain_all=False,
    )
    print(f"    raw nodes={g_walk.number_of_nodes()}  edges={g_walk.number_of_edges()}")

    # -----------------------------------------------------------------------
    # Bước 1: củng cố các ngã tư để gộp các nút giao gần như trùng lặp.
    # -----------------------------------------------------------------------
    print("--- Consolidating intersections (tolerance=15 m) ---")
    g_proj = ox.project_graph(g_walk)
    g_proj = ox.consolidate_intersections(
        g_proj,
        tolerance=15,
        rebuild_graph=True,
        dead_ends=False,
    )
    g_walk = ox.project_graph(g_proj, to_crs="EPSG:4326")
    print(f"    after consolidation nodes={g_walk.number_of_nodes()}  edges={g_walk.number_of_edges()}")

    # -----------------------------------------------------------------------
    # Bước 2: loại bỏ bất kỳ node nào có tọa độ không hợp lệ theo chuẩn WGS84.
    # -----------------------------------------------------------------------
    n_bad = _prune_invalid_wgs84_nodes(g_walk)
    if n_bad:
        print(f"    pruned {n_bad} node(s) with invalid WGS84 coordinates")

    # -----------------------------------------------------------------------
    # Bước 3: điền lại bất kỳ 'length' nào bị thiếu/bằng 0 từ công thức haversine.
    # -----------------------------------------------------------------------
    for u, v, _, data in g_walk.edges(keys=True, data=True):
        if "length" not in data or float(data.get("length", 0) or 0) <= 0:
            try:
                lat1, lng1 = float(g_walk.nodes[u]["y"]), float(g_walk.nodes[u]["x"])
                lat2, lng2 = float(g_walk.nodes[v]["y"]), float(g_walk.nodes[v]["x"])
                data["length"] = _haversine_m(lat1, lng1, lat2, lng2)
            except (KeyError, TypeError, ValueError):
                data["length"] = 0.0

    # -----------------------------------------------------------------------
    # Bước 4: thu gọn các cạnh song song (giữ loại đồ thị Multi*).
    # -----------------------------------------------------------------------
    print("--- Collapsing parallel edges ---")
    before = g_walk.number_of_edges()
    g_walk = _collapse_parallel_edges(g_walk)
    print(f"    removed {before - g_walk.number_of_edges()} parallel edge(s)")

    # -----------------------------------------------------------------------
    # Bước 5: gán thời gian đi bộ, loại node/cạnh, xóa các thẻ không sử dụng.
    # -----------------------------------------------------------------------
    print("--- Assigning walk weights and cleaning metadata ---")
    if g_walk.is_multigraph():
        for u, v, k, data in g_walk.edges(keys=True, data=True):
            length = float(data.get("length", 0.0) or 0.0)
            data["length"] = length
            data["time"] = length / WALK_SPEED_M_PER_MIN if length > 0 else 0.0
            data["type"] = "walk"
            data["is_active"] = True
    else:
        for u, v, data in g_walk.edges(data=True):
            length = float(data.get("length", 0.0) or 0.0)
            data["length"] = length
            data["time"] = length / WALK_SPEED_M_PER_MIN if length > 0 else 0.0
            data["type"] = "walk"
            data["is_active"] = True

    for _, data in g_walk.nodes(data=True):
        data["type"] = "walk"
        data["is_metro_station"] = False

    # Bước 5b: Bảo toàn hình học của cạnh dưới dạng danh sách [lat, lng] để vẽ trên bản đồ.
    print("--- Preserving edge geometries as [lat, lng] lists ---")
    from shapely.geometry import LineString
    for u, v, k, data in g_walk.edges(keys=True, data=True):
        geom = data.get("geometry")
        if isinstance(geom, LineString):
            # Shapely stores as (x=lng, y=lat); convert to [lat, lng] for the frontend.
            data["geometry_coords"] = [[pt[1], pt[0]] for pt in geom.coords]
        else:
            # Cạnh thẳng - chỉ có 2 đầu nút.
            data["geometry_coords"] = [
                [float(g_walk.nodes[u]["y"]), float(g_walk.nodes[u]["x"])],
                [float(g_walk.nodes[v]["y"]), float(g_walk.nodes[v]["x"])],
            ]
        # Drop the shapely object so GraphML can serialize.
        data.pop("geometry", None)

    _drop_tags(g_walk)

    # -----------------------------------------------------------------------
    # Bước 6: căn chỉnh tọa độ rõ ràng để tương thích với main.py (x=lng, y=lat).
    # -----------------------------------------------------------------------
    print("--- Aligning coordinates (x=lng, y=lat, plus lat/lng) ---")
    for _, data in g_walk.nodes(data=True):
        try:
            lng = float(data["x"])
            lat = float(data["y"])
        except (KeyError, TypeError, ValueError):
            continue

        data["x"] = float(lng)
        data["y"] = float(lat)
        data["lat"] = float(lat)
        data["lng"] = float(lng)

    # -----------------------------------------------------------------------
    # Bước 7: thêm namespace cho mọi ID node đi bộ để nó không thể xung đột
    # với các ID trạm chuỗi số nguyên do build_metro.py chỉ định.
    # -----------------------------------------------------------------------
    print(f"--- Namespacing walk node IDs with prefix {WALK_NODE_PREFIX!r} ---")
    g_walk = _namespace_node_ids(g_walk, WALK_NODE_PREFIX)

    # -----------------------------------------------------------------------
    # Bước 8: chuyển mọi giá trị thuộc tính thành định dạng chuẩn để có thể lưu dưới dạng GraphML.
    # -----------------------------------------------------------------------
    _stringify_attr_values(g_walk)

    print(f"Final walk graph: nodes={g_walk.number_of_nodes()}  edges={g_walk.number_of_edges()}")
    print("--- Saving:", OUT_WALK, "---")
    os.makedirs(os.path.dirname(OUT_WALK), exist_ok=True)
    ox.save_graphml(g_walk, filepath=OUT_WALK)
    print("Done:", OUT_WALK)


if __name__ == "__main__":
    main()