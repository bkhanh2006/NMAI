import osmnx as ox
import networkx as nx
from loader import gdf_stations, metro_lines
def build_complete_graph(graph_path, gdf_stations, metro_lines):
    print("--- Bắt đầu xây dựng đồ thị ---")
    
    # 1. Load và Project đồ thị
    G = ox.load_graphml(graph_path)
    G = ox.projection.project_graph(G)
    
    # 2. Project các GeoDataFrame sang cùng hệ tọa độ với G (đơn vị mét)
    target_crs = G.graph['crs']
    gdf_stations = gdf_stations.to_crs(target_crs)
    metro_lines = metro_lines.to_crs(target_crs)
    
    # 3. Gán trọng số đường bộ (Lớp Walk)
    walk_speed = 5000 / 60 
    for u, v, data in G.edges(data=True):
        data['time'] = data.get('length', 100) / walk_speed
        data['type'] = 'walk'
        data['is_active'] = True

    # 4. Cấy thông tin ga vào node
    print("Đang cấy thông tin ga...")
    for _, station in gdf_stations.iterrows():
        nearest_node = ox.nearest_nodes(G, station.geometry.x, station.geometry.y)
        G.nodes[nearest_node].update({
            'is_metro_station': 'True',
            'type': 'station',
            'name': station.get('name', 'Unknown')
        })
    # Gắn type='walk' cho các node khác
    for node_id, data in G.nodes(data=True):
        if data.get('type') not in ('station', 'walk'):
            data['type'] = 'walk'
    
    # 5. Tích hợp Metro (Lớp Metro) - LẶP TRÊN METRO_LINES (GeoDataFrame)
    print("Đang tích hợp tuyến Metro...")
    train_speed = 60000 / 60 
    
    for _, row in metro_lines.iterrows():
        geom = row.geometry
        if geom.geom_type == 'LineString':
            # Tìm node gần nhất với điểm đầu và cuối đường ray
            node_start = ox.nearest_nodes(G, geom.coords[0][0], geom.coords[0][1])
            node_end = ox.nearest_nodes(G, geom.coords[-1][0], geom.coords[-1][1])
            
            # Thêm cạnh metro vào đồ thị
            G.add_edge(node_start, node_end, 
                       time=geom.length/train_speed, 
                       type='metro', 
                       is_active=True)
            
    print("Hoàn tất!")
    return G

# --- CHẠY ---
# Lưu ý: Bạn cần có biến metro_lines từ bước trước
G_final = build_complete_graph(r'C:\Users\LENOVO\Documents\GitHub\NMAI\graph\spd_walk.graphml.xml', gdf_stations, metro_lines)
ox.save_graphml(G_final, filepath=r'C:\Users\LENOVO\Documents\GitHub\NMAI\graph\spd_metro.graphml')
