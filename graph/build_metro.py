import os
import json
import itertools
import osmnx as ox
import networkx as nx
import pandas as pd
from shapely.ops import substring, linemerge
from pyproj import Transformer
from shapely.geometry import LineString, Point

# ============================================================
# 1. CẤU HÌNH
# ============================================================
PLACE_NAME = "Saint Petersburg, Russia"
CRS_METERS = "EPSG:32636"
CRS_WGS84 = "EPSG:4326"
OUT_METRO = os.path.join("graph", "spd_metro.graphml")

TRAIN_SPEED = 1000  # Vận tốc tàu (m/phút)
WALK_SPEED = 60     # Vận tốc đi bộ trung chuyển (m/phút)

ox.settings.use_cache = True
to_wgs84 = Transformer.from_crs(CRS_METERS, CRS_WGS84, always_xy=True)

BANNED_STATIONS = ["Броневая"]

def edge_to_leaflet_coords(segment):
    if segment.geom_type == 'MultiLineString':
        segment = linemerge(segment)
        if segment.geom_type == 'MultiLineString':
            segment = max(segment.geoms, key=lambda x: x.length)
    return json.dumps([[to_wgs84.transform(x, y)[1], to_wgs84.transform(x, y)[0]] for x, y in segment.coords])

# ============================================================
# 2. LẤY & LỌC DỮ LIỆU
# ============================================================
print("--- Đang tải dữ liệu Metro ---")
stations = ox.features_from_place(PLACE_NAME, tags={"station": "subway"}).to_crs(CRS_METERS)
tracks = ox.features_from_place(PLACE_NAME, tags={"railway": "subway"}).to_crs(CRS_METERS)

inactive_tags = ['construction', 'proposed', 'planned', 'under_construction', 'disused', 'abandoned']
if 'status' in stations.columns:
    stations = stations[~stations['status'].isin(inactive_tags)]
if 'status' in tracks.columns:
    tracks = tracks[~tracks['status'].isin(inactive_tags)]

# Lọc chặn các đường ray kỹ thuật, nhánh phụ
if 'service' in tracks.columns:
    tracks = tracks[tracks['service'].isnull() | (tracks['service'] == 'no')]
if 'usage' in tracks.columns:
    tracks = tracks[tracks['usage'].isnull() | (tracks['usage'] == 'main')]

tracks = tracks[tracks.geometry.type.isin(["LineString", "MultiLineString"])]

print("--- Đang xử lý hình học (Merge Tracks) ---")
merged_tracks = linemerge(tracks.geometry.tolist())
lines = list(merged_tracks.geoms) if merged_tracks.geom_type == 'MultiLineString' else [merged_tracks]

# ============================================================
# 3. XỬ LÝ GA (NODES)
# ============================================================
stations['final_name'] = stations['name:en'].fillna(stations.get('name', 'Unknown'))

pattern = '|'.join(BANNED_STATIONS)
stations = stations[~stations['final_name'].str.contains(pattern, case=False, na=False)]

st_nodes = stations.groupby('final_name')['geometry'].apply(lambda g: g.union_all().centroid).reset_index()

G = nx.Graph(crs=CRS_WGS84) 
for idx, row in st_nodes.iterrows():
    lng, lat = to_wgs84.transform(row.geometry.x, row.geometry.y)
    G.add_node(str(idx), name=str(row['final_name']), lat=lat, lng=lng, x=lng, y=lat)

# ============================================================
# 4. XỬ LÝ TUYẾN (EDGES) - [CHỐNG RẼ NHÁNH TẠI TRẠM TRUNG CHUYỂN]
# ============================================================
print("--- Đang kết nối mạng lưới ---")
for line in lines:
    near_st = []
    for idx, row in st_nodes.iterrows():
        dist = line.distance(row.geometry)
        if dist < 250: # Tăng tầm nhìn tìm ga lân cận
            near_st.append({
                'id': str(idx),
                'pos': line.project(row.geometry),
                'dist': dist
            })
    
    if len(near_st) < 2: 
        continue
        
    near_st.sort(key=lambda x: x['pos'])
    
    filtered_st = []
    current_group = [near_st[0]]
    
    # [FIX CỐT LÕI]: Tăng kích thước bao phủ của 1 cụm lên 350m
    for i in range(1, len(near_st)):
        if near_st[i]['pos'] - current_group[0]['pos'] < 350:
            current_group.append(near_st[i])
        else:
            best_st = min(current_group, key=lambda x: x['dist'])
            filtered_st.append(best_st)
            current_group = [near_st[i]]
            
    if current_group:
        best_st = min(current_group, key=lambda x: x['dist'])
        filtered_st.append(best_st)
            
    for i in range(len(filtered_st) - 1):
        u, v = filtered_st[i]['id'], filtered_st[i+1]['id']
        start_pos, end_pos = filtered_st[i]['pos'], filtered_st[i+1]['pos']
        
        if u != v and not G.has_edge(u, v):
            segment = substring(line, start_pos, end_pos)
            
            coords = list(segment.coords)
            u_geom = st_nodes.loc[int(u), 'geometry']
            v_geom = st_nodes.loc[int(v), 'geometry']
            
            # Ép nét vẽ dính chặt vào nút đại diện
            if Point(coords[0]).distance(u_geom) < Point(coords[-1]).distance(u_geom):
                coords.insert(0, (u_geom.x, u_geom.y))
                coords.append((v_geom.x, v_geom.y))
            else:
                coords.insert(0, (v_geom.x, v_geom.y))
                coords.append((u_geom.x, u_geom.y))
                
            visual_segment = LineString(coords)
            length = round(segment.length, 2)
            
            G.add_edge(
                u, v, length=length, time=round(length / TRAIN_SPEED, 2), speed=TRAIN_SPEED,
                transfer=False, geometry_coords=edge_to_leaflet_coords(visual_segment)
            )

# ============================================================
# 5. LIÊN THÔNG GA ĐI BỘ (TRANSFER EDGES)
# ============================================================
for u, v in itertools.combinations(G.nodes, 2):
    if not G.has_edge(u, v):
        u_idx, v_idx = int(u), int(v)
        dist = st_nodes.loc[u_idx, 'geometry'].distance(st_nodes.loc[v_idx, 'geometry'])
        
        if dist < 300: 
            length = round(dist, 2)
            transfer_line = LineString([st_nodes.loc[u_idx, 'geometry'], st_nodes.loc[v_idx, 'geometry']])
            G.add_edge(
                u, v, length=length, time=round(length / WALK_SPEED, 2), speed=WALK_SPEED,
                transfer=True, geometry_coords=edge_to_leaflet_coords(transfer_line)
            )

# ============================================================
# 6. AUTO-FIX (BẢO HIỂM CHO A*)
# ============================================================
components = list(nx.connected_components(G))
if len(components) > 1:
    print(f"[*] CẢNH BÁO: Đang vá lỗi liên thông cho {len(components)} cụm...")
    components.sort(key=len, reverse=True)
    main_comp = components[0]
    
    for i in range(1, len(components)):
        small_comp = components[i]
        min_dist = float('inf')
        best_pair = None
        
        for u in small_comp:
            for v in main_comp:
                dist = st_nodes.loc[int(u), 'geometry'].distance(st_nodes.loc[int(v), 'geometry'])
                if dist < min_dist:
                    min_dist = dist
                    best_pair = (u, v)
                    
        if best_pair:
            u, v = best_pair
            length = round(min_dist, 2)
            fix_line = LineString([st_nodes.loc[int(u), 'geometry'], st_nodes.loc[int(v), 'geometry']])
            G.add_edge(
                u, v, length=length, time=round(length / TRAIN_SPEED, 2), speed=TRAIN_SPEED,
                transfer=True, geometry_coords=edge_to_leaflet_coords(fix_line), note="auto_fixed"
            )
            main_comp.update(small_comp)

# ============================================================
# 7. XUẤT FILE
# ============================================================
os.makedirs("graph", exist_ok=True)
nx.write_graphml(G, OUT_METRO)

print(f"Hoàn tất! Đồ thị liên thông vững chắc gồm {G.number_of_nodes()} ga và {G.number_of_edges()} cạnh.")