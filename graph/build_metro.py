import json
import networkx as nx
import pandas as pd
import geopandas as gpd
import osmnx as ox

from shapely.geometry import LineString, MultiLineString
from shapely.ops import unary_union, linemerge, substring
from pyproj import Transformer

# ============================================================
# 1. CẤU HÌNH
# ============================================================
PLACE_NAME = "Saint Petersburg, Russia"
OUT_METRO = r"C:\Users\LENOVO\Documents\GitHub\NMAI\graph\spd_metro.graphml"

CRS_WGS84 = "EPSG:4326"
CRS_METERS = "EPSG:32636"

# Tăng khoảng cách tìm kiếm để đảm bảo ga không bị "tuột" khỏi ray
MAX_DIST_TO_LINE = 500 
TRAIN_SPEED = 1000 # mét/phút (~60km/h)

ox.settings.use_cache = True
ox.settings.log_console = False

# ============================================================
# 2. HÀM HỖ TRỢ
# ============================================================
to_wgs84 = Transformer.from_crs(CRS_METERS, CRS_WGS84, always_xy=True)

def edge_geometry_to_leaflet_coords(line_segment):
    coords = [[to_wgs84.transform(x, y)[1], to_wgs84.transform(x, y)[0]] for x, y in line_segment.coords]
    return json.dumps(coords)

# ============================================================
# 3. LẤY & LÀM SẠCH DATA
# ============================================================
print("--- Đang tải dữ liệu Metro ---")

# Lấy ga và gộp theo tên (Mỗi ga 1 điểm đại diện)
station_tags = {"station": "subway", "railway": "station"}
stations_raw = ox.features_from_place(PLACE_NAME, tags=station_tags)
mask = (stations_raw["railway"] == "station") & (stations_raw["station"] == "subway")
stations = stations_raw[mask].copy()
stations["geometry"] = stations.geometry.apply(lambda g: g.centroid if g.geom_type != "Point" else g)
stations_m = stations.to_crs(CRS_METERS)
stations_m["final_name"] = stations_m["name:en"].fillna(stations_m["name"])

merged_rows = []
for name, group in stations_m.groupby("final_name"):
    if pd.isna(name): continue
    merged_rows.append({
        "station_id": f"st_{len(merged_rows)}",
        "name": str(name),
        "geometry": unary_union(list(group.geometry)).centroid
    })

stations_merged_m = gpd.GeoDataFrame(merged_rows, geometry="geometry", crs=CRS_METERS)
stations_merged = stations_merged_m.to_crs(CRS_WGS84)

# Lấy đường ray và gộp theo Tuyến (Line)
metro_lines = ox.features_from_place(PLACE_NAME, tags={"railway": "subway"})
metro_lines = metro_lines[metro_lines.geometry.geom_type.isin(["LineString", "MultiLineString"])].copy()
metro_lines = metro_lines.to_crs(CRS_METERS)

# Gom các đoạn ray nhỏ thành các Line lớn dựa trên tên hoặc tham chiếu (ref)
# Nếu không có tên, gộp chung vào một nhóm 'unnamed' để xử lý
metro_lines["line_id"] = metro_lines["name"].fillna(metro_lines.get("ref", "unnamed"))

# ============================================================
# 4. XÂY DỰNG ĐỒ THỊ VỚI LOGIC NỐI MỚI
# ============================================================
G = nx.Graph(crs=CRS_WGS84)

for _, row in stations_merged.iterrows():
    G.add_node(row["station_id"], lat=row.geometry.y, lng=row.geometry.x, name=row["name"])

print("--- Đang kết nối mạng lưới theo tuyến ---")

for line_id, group in metro_lines.groupby("line_id"):
    # Hợp nhất tất cả các đoạn ray của cùng một tuyến thành một khối hình học duy nhất
    combined_line = unary_union(list(group.geometry))
    
    # Thử làm mượt và nối các đoạn ray bị hở
    try:
        merged_line = linemerge(combined_line)
    except:
        merged_line = combined_line

    # Xử lý từng đoạn LineString sau khi gộp
    lines_to_process = [merged_line] if isinstance(merged_line, LineString) else merged_line.geoms
    
    for single_line in lines_to_process:
        near = []
        for _, st in stations_merged_m.iterrows():
            dist = st.geometry.distance(single_line)
            if dist <= MAX_DIST_TO_LINE:
                # Chiếu ga lên đường ray để biết thứ tự
                near.append((single_line.project(st.geometry), st["station_id"]))
        
        # Sắp xếp ga theo trình tự chạy của đường ray
        near.sort(key=lambda x: x[0])
        
        # Loại bỏ các điểm trùng lặp liên tiếp
        sequence = []
        for i in range(len(near)):
            if i == 0 or near[i][1] != near[i-1][1]:
                sequence.append(near[i])
        
        # Tạo cạnh nối các ga liên tiếp
        for (p1, u), (p2, v) in zip(sequence[:-1], sequence[1:]):
            if u != v:
                seg = substring(single_line, p1, p2)
                # Nếu cạnh đã tồn tại (do tuyến khác vẽ), chỉ cập nhật thông tin
                if G.has_edge(u, v):
                    continue 
                
                G.add_edge(u, v, 
                           length=round(seg.length, 2), 
                           time=round(seg.length/TRAIN_SPEED, 2),
                           geometry_coords=edge_geometry_to_leaflet_coords(seg),
                           line=str(line_id))

# ============================================================
# 5. XUẤT FILE
# ============================================================
nx.write_graphml(G, OUT_METRO)
print(f"Hoàn tất! Đã nối được {G.number_of_edges()} cạnh.")