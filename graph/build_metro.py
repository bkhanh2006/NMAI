import json
import networkx as nx
import pandas as pd
import geopandas as gpd
import osmnx as ox

from shapely.geometry import LineString, MultiLineString
from shapely.ops import linemerge, substring
# Sử dụng union_all thay vì unary_union theo khuyến cáo mới
try:
    from shapely.ops import union_all
except ImportError:
    from shapely.ops import unary_union as union_all

from pyproj import Transformer

# ============================================================
# 1. CẤU HÌNH (LỌC TRIỆT ĐỂ)
# ============================================================
PLACE_NAME = "Saint Petersburg, Russia"
OUT_METRO = r"C:\Users\LENOVO\Documents\GitHub\NMAI\graph\spd_metro.graphml"

CRS_WGS84 = "EPSG:4326"
CRS_METERS = "EPSG:32636"

# Khoảng cách bắt ray và chuyển tuyến
MAX_DIST_TO_LINE = 500 
TRANSFER_DIST = 200 
TRAIN_SPEED = 1000

ox.settings.use_cache = True

# ============================================================
# 2. HÀM HỖ TRỢ
# ============================================================
to_wgs84 = Transformer.from_crs(CRS_METERS, CRS_WGS84, always_xy=True)

def edge_geom_to_json(line):
    coords = [[to_wgs84.transform(x, y)[1], to_wgs84.transform(x, y)[0]] for x, y in line.coords]
    return json.dumps(coords)

# ============================================================
# 3. LẤY & LỌC DATA (CHỈ LẤY METRO THỰC SỰ)
# ============================================================
print("--- Đang tải dữ liệu Metro (Đã lọc ga tàu hỏa) ---")

# CHỈ lấy những gì là SUBWAY
tags_st = {"station": "subway", "subway": "yes"}
gdf_st = ox.features_from_place(PLACE_NAME, tags=tags_st)

# Lọc bỏ các ga entrance (lối vào) và platform rác
mask = (gdf_st["station"] == "subway") | (gdf_st["subway"] == "yes")
gdf_st = gdf_st[mask].copy()

gdf_st["geometry"] = gdf_st.geometry.centroid
gdf_st_m = gdf_st.to_crs(CRS_METERS)
gdf_st_m["final_name"] = gdf_st_m["name:en"].fillna(gdf_st_m["name"])

# Gom ga theo tên (Mỗi ga 1 điểm duy nhất)
stations_data = []
for name, group in gdf_st_m.groupby("final_name"):
    if pd.isna(name): continue
    stations_data.append({
        "sid": f"st_{len(stations_data)}",
        "name": str(name),
        "geom": union_all(list(group.geometry)).centroid
    })
df_final_st = gpd.GeoDataFrame(stations_data, geometry="geom", crs=CRS_METERS)

# ============================================================
# 4. XÂY DỰNG ĐỒ THỊ
# ============================================================
G = nx.Graph(crs=CRS_WGS84)
for _, row in df_final_st.iterrows():
    p = to_wgs84.transform(row.geom.x, row.geom.y)
    G.add_node(row["sid"], lat=p[1], lng=p[0], name=row["name"], type="station")

# NỐI CẠNH THEO ĐƯỜNG RAY
print("--- Đang kết nối mạng lưới ---")
lines = ox.features_from_place(PLACE_NAME, tags={"railway": "subway"})
lines = lines[lines.geometry.geom_type.isin(["LineString", "MultiLineString"])].to_crs(CRS_METERS)

# Dán tất cả các mẩu ray rời rạc lại thành các đường dài nhất có thể
unified_rail = union_all(list(lines.geometry))
merged_rail = linemerge(unified_rail)

# Chuyển về list các đoạn để xử lý
if isinstance(merged_rail, LineString):
    segments = [merged_rail]
elif isinstance(merged_rail, MultiLineString):
    segments = list(merged_rail.geoms)
else:
    segments = []

for rail in segments:
    near = []
    for _, st in df_final_st.iterrows():
        d = st.geom.distance(rail)
        if d <= MAX_DIST_TO_LINE:
            near.append((rail.project(st.geom), st["sid"]))
    
    near.sort(key=lambda x: x[0])
    # Loại bỏ ga lặp lại trong chuỗi
    seq = [near[i] for i in range(len(near)) if i == 0 or near[i][1] != near[i-1][1]]
    
    for (p1, u), (p2, v) in zip(seq[:-1], seq[1:]):
        if u != v:
            seg = substring(rail, p1, p2)
            if seg.length > 10:
                # Nếu đã có cạnh, chỉ cập nhật nếu cạnh mới ngắn hơn
                if G.has_edge(u, v):
                    if seg.length < G[u][v]['length']:
                        G[u][v].update({"length": round(seg.length, 2), "geometry_coords": edge_geom_to_json(seg)})
                else:
                    G.add_edge(u, v, length=round(seg.length, 2), 
                               geometry_coords=edge_geom_to_json(seg), type="metro")

# NỐI CẠNH TRUNG CHUYỂN (Chống ga cô lập)
for i, st1 in df_final_st.iterrows():
    for j, st2 in df_final_st.iterrows():
        if i >= j: continue
        dist = st1.geom.distance(st2.geom)
        if dist <= TRANSFER_DIST:
            if not G.has_edge(st1["sid"], st2["sid"]):
                line = LineString([st1.geom, st2.geom])
                G.add_edge(st1["sid"], st2["sid"], length=round(dist, 2),
                           geometry_coords=edge_geom_to_json(line), type="transfer")

# ============================================================
# 5. XUẤT FILE & KIỂM TRA
# ============================================================
nx.write_graphml(G, OUT_METRO)
isolates = list(nx.isolates(G))
print(f"\nKẾT QUẢ FINAL: {G.number_of_nodes()} ga, {G.number_of_edges()} cạnh.")
if isolates:
    print(f"Danh sách {len(isolates)} ga vẫn cô lập: {[G.nodes[n]['name'] for n in isolates]}")
else:
    print("Tuyệt vời! Toàn bộ các ga đã được kết nối thông suốt.")