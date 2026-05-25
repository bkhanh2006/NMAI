#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Smart Map Pro - St. Petersburg Metro Route Optimizer
A* Pathfinding with Admin Blocking System (Optimized Version)
"""

import json
import os
import ast
from math import sqrt, radians, sin, cos, atan2
import heapq
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import networkx as nx
from pyproj import Transformer
try:
    from scipy.spatial import cKDTree
except Exception:
    cKDTree = None

# ============================================================================
# KHỞI TẠO VÀ CÁC BIẾN TOÀN CỤC
# ============================================================================

app = Flask(__name__)
CORS(app)

NODES_DICT = {}  
EDGES_LIST = []  
WALK_GRAPH = None
METRO_GRAPH = None
WALK_NODE_IDS = []
WALK_NODE_COORDS = []
WALK_NODES_API = []
WALK_KDTREE = None
WALK_COORD_BY_ID = {}
STATION_TO_WALK_NODE = {}
COMBINED_BASE_GRAPH = None

WALK_SPEED_KMH = 4.8
METRO_SPEED_KMH = 36.0
MAX_SPEED_KMH_FOR_HEURISTIC = max(WALK_SPEED_KMH, METRO_SPEED_KMH)
ST_PETERSBURG_BBOX = {
    'min_lat': 59.5000,
    'max_lat': 60.3000,
    'min_lng': 29.4000,
    'max_lng': 31.0000
}

# ============================================================================
# TIỆN ÍCH - HEURISTIC VÀ KHOẢNG CÁCH
# ============================================================================

# Hàm kiểm tra xem tọa độ có nằm trong khu vực St. Petersburg hay không, giúp lọc sớm các yêu cầu không hợp lệ.
def is_in_st_petersburg(lat, lng):
    return (ST_PETERSBURG_BBOX['min_lat'] <= float(lat) <= ST_PETERSBURG_BBOX['max_lat']) and \
           (ST_PETERSBURG_BBOX['min_lng'] <= float(lng) <= ST_PETERSBURG_BBOX['max_lng'])

# Hàm tính khoảng cách Haversine giữa hai điểm địa lý, được sử dụng làm heuristic trong thuật toán A*.
def haversine_distance(lat1, lng1, lat2, lng2):
    R = 6371.0 
    lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlng/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

# Quy đổi khoảng cách (theo đơn vị mét) sang thời gian di chuyển (theo đơn vị phút)
def meters_to_minutes(distance_m, speed_kmh):
    if speed_kmh <= 0: return 0.0
    return (distance_m / 1000.0) / speed_kmh * 60.0

# Trích xuất và kiểm tra tính hợp lệ danh sách các điểm tọa độ từ dữ liệu JSON/String.
def parse_geometry_coords(value):
    if not value: return []
    parsed = value
    if isinstance(value, str):
        try: parsed = ast.literal_eval(value.strip())
        except Exception: return []
    if not isinstance(parsed, (list, tuple)): return []
    
    coords = []
    for item in parsed:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            lat, lng = float(item[0]), float(item[1])
            if abs(lat) > 90 and abs(lng) <= 90: lat, lng = lng, lat
            if abs(lat) <= 90 and abs(lng) <= 180: coords.append([lat, lng])
    return coords

# Hàm kiểm tra xem một cạnh có cắt qua bất kỳ vùng cấm nào không, bằng cách chiếu điểm gần nhất từ tâm vùng cấm lên đoạn thẳng của cạnh.
def edge_intersects_forbidden_zone(graph, u, v, forbidden_zones):
    """Tối ưu hóa: Thuật toán chiếu điểm lên đoạn thẳng để tìm khoảng cách ngắn nhất đến tâm vùng cấm"""
    if not forbidden_zones: return False

    # Lấy tọa độ của cạnh
    if hasattr(graph, 'nodes') and u in graph and v in graph[u]:
        coords = graph[u][v].get('geometry_coords') or [[graph.nodes[u]['lat'], graph.nodes[u]['lng']], [graph.nodes[v]['lat'], graph.nodes[v]['lng']]]
    else:
        coords = [[graph[u]['lat'], graph[u]['lng']], [graph[v]['lat'], graph[v]['lng']]]
    
    if len(coords) < 2: return False

    R = 6371000.0 
    deg2rad = 3.141592653589793 / 180.0

    for zone in forbidden_zones:
        center_lat, center_lng = zone['center_lat'], zone['center_lng']
        radius_m = float(zone.get('radius_m', zone.get('radius', 0.0) * 111000.0))
        cos_lat = cos(radians(center_lat))

        for (start_lat, start_lng), (end_lat, end_lng) in zip(coords[:-1], coords[1:]):
            # Quy đổi hệ tọa độ x,y theo mét so với tâm
            x1 = (start_lng - center_lng) * deg2rad * R * cos_lat
            y1 = (start_lat - center_lat) * deg2rad * R
            x2 = (end_lng - center_lng) * deg2rad * R * cos_lat
            y2 = (end_lat - center_lat) * deg2rad * R

            dx, dy = x2 - x1, y2 - y1
            denom = dx * dx + dy * dy
            
            if denom == 0: dist_m = sqrt(x1 * x1 + y1 * y1)
            else:
                t = max(0.0, min(1.0, -(x1 * dx + y1 * dy) / denom))
                near_x, near_y = x1 + t * dx, y1 + t * dy
                dist_m = sqrt(near_x * near_x + near_y * near_y)

            if dist_m <= radius_m: return True
    return False

# Hàm trích xuất tên hiển thị của một node, ưu tiên trường 'name' nếu có, nếu không sẽ trả về ID của node đó.
def node_name(node_id, node_data):
    if node_id in ('__point_a__', '__point_b__'): return 'Điểm A' if node_id == '__point_a__' else 'Điểm B'
    return node_data.get('name') or node_id

# Hàm xác định phương tiện di chuyển (phương thức vận chuyển) của một cạnh dựa vào thuộc tính 'mode' hoặc 'type', mặc định trả về 'walk' nếu không có thông tin.
def get_edge_mode(edge_data):
    return str(edge_data.get('mode', edge_data.get('type', 'walk'))).lower()

# ============================================================================
# THUẬT TOÁN TÌM ĐƯỜNG A*
# ============================================================================

def a_star_on_graph(graph, start_id, end_id, forbidden_nodes=None, forbidden_edges=None, forbidden_zones=None):
    """A* tinh gọn: các cạnh bị cấm đã có time=inf nên không cần kiểm tra trong vòng lặp."""
    if start_id not in graph or end_id not in graph: return None, float('inf')

    end_lat, end_lng = graph.nodes[end_id]['lat'], graph.nodes[end_id]['lng']
    def heuristic_min(n_id):
        dist_km = haversine_distance(graph.nodes[n_id]['lat'], graph.nodes[n_id]['lng'], end_lat, end_lng)
        return (dist_km / MAX_SPEED_KMH_FOR_HEURISTIC) * 60.0

    open_set = [(heuristic_min(start_id), 0, start_id)]
    came_from, g_score = {}, {start_id: 0.0}
    counter = 1

    while open_set:
        _, _, current = heapq.heappop(open_set)
        if current == end_id:
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.append(start_id)
            return path[::-1], g_score[end_id]

        for neighbor in graph.neighbors(current):
            edge_time = float(graph[current][neighbor].get('time', 0.0))
            # Bỏ qua sớm các cạnh bị chặn (time=inf) để không lãng phí heap.
            if edge_time == float('inf'): continue

            tentative_g = g_score[current] + edge_time
            if tentative_g < g_score.get(neighbor, float('inf')):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                heapq.heappush(open_set, (tentative_g + heuristic_min(neighbor), counter, neighbor))
                counter += 1

    return None, float('inf')

# ============================================================================
# TẢI ĐỒ THỊ VÀ XÂY DỰNG TUYẾN ĐƯỜNG
# ============================================================================

# Hàm load dữ liệu đồ thị từ 2 files graphml (metro và đường đi bộ).
# Đồng thời liên kết các ga metro gần với các đường đi bộ, sau đó tạo
# thành MỘT đồ thị tổ hợp DUY NHẤT để A* tính toán dễ dàng.
def load_graph_with_coordinates():
    global NODES_DICT, EDGES_LIST, WALK_GRAPH, METRO_GRAPH, WALK_NODE_IDS, WALK_NODE_COORDS
    global WALK_NODES_API, WALK_KDTREE, WALK_COORD_BY_ID, STATION_TO_WALK_NODE, COMBINED_BASE_GRAPH

    metro_path, walk_path = 'graph/spd_metro.graphml', 'graph/spd_walk.graphml'
    if not os.path.exists(metro_path) or not os.path.exists(walk_path): return False

    METRO_GRAPH = nx.read_graphml(metro_path)
    WALK_GRAPH = nx.read_graphml(walk_path)
    utm36_to_wgs84 = Transformer.from_crs("EPSG:32636", "EPSG:4326", always_xy=True)

    def norm_coords(raw_x, raw_y, raw_lat=None, raw_lng=None):
        if raw_lat and raw_lng: return float(raw_lat), float(raw_lng)
        x, y = float(raw_x), float(raw_y)
        if -180 <= x <= 180 and -90 <= y <= 90: return y, x
        return utm36_to_wgs84.transform(x, y)[::-1] # return lat, lon

    # 1. Phân tích dữ liệu Metro
    for node_id, data in METRO_GRAPH.nodes(data=True):
        lat, lng = norm_coords(data.get('x', 0), data.get('y', 0), data.get('lat'), data.get('lng'))
        NODES_DICT[node_id] = {
            'id': node_id, 'lat': lat, 'lng': lng, 
            'name': data.get('name', node_id), 
            'type': 'station' if str(data.get('is_metro_station', '')).lower() in ('true', '1', 'yes') or not data.get('type') else data.get('type'),
            'connections': []
        }

    for u, v, data in METRO_GRAPH.edges(data=True):
        geom = parse_geometry_coords(data.get('geometry_coords')) or [[NODES_DICT[u]['lat'], NODES_DICT[u]['lng']], [NODES_DICT[v]['lat'], NODES_DICT[v]['lng']]]
        EDGES_LIST.append({'from': u, 'to': v, 'type': data.get('type', 'metro'), 'line': data.get('line', ''), 'geometry_coords': geom})
        if v not in NODES_DICT[u]['connections']: NODES_DICT[u]['connections'].append(v)
        if u not in NODES_DICT[v]['connections']: NODES_DICT[v]['connections'].append(u)

    # 2. Phân tích dữ liệu Đi bộ
    for node_id, data in WALK_GRAPH.nodes(data=True):
        lat, lng = norm_coords(data.get('x', 0), data.get('y', 0))
        WALK_NODE_IDS.append(node_id)
        WALK_NODE_COORDS.append((lat, lng))
        WALK_COORD_BY_ID[node_id] = (lat, lng)
        WALK_NODES_API.append({'id': node_id, 'lat': lat, 'lng': lng, 'name': data.get('name', ''), 'type': 'walk'})

    if cKDTree: WALK_KDTREE = cKDTree([(lng, lat) for lat, lng in WALK_NODE_COORDS])

    # 3. Liên kết các Trạm với các Nút Đi bộ
    for s_id, s_data in NODES_DICT.items():
        if s_data.get('type') != 'station': continue
        if WALK_KDTREE:
            _, idx = WALK_KDTREE.query((s_data['lng'], s_data['lat']), k=1)
            STATION_TO_WALK_NODE[s_id] = WALK_NODE_IDS[int(idx)]

    # 4. Xây dựng Đồ thị Kết hợp
    COMBINED_BASE_GRAPH = nx.Graph()
    for n_id, data in NODES_DICT.items():
        COMBINED_BASE_GRAPH.add_node(n_id, id=n_id, lat=data['lat'], lng=data['lng'], name=data['name'], type=data['type'])
    for n_id, (lat, lng) in WALK_COORD_BY_ID.items():
        if n_id not in COMBINED_BASE_GRAPH:
            COMBINED_BASE_GRAPH.add_node(n_id, id=n_id, lat=lat, lng=lng, name=f"walk_{n_id}", type='walk')
            
    for u, v, d in WALK_GRAPH.edges(data=True):
        if u in COMBINED_BASE_GRAPH and v in COMBINED_BASE_GRAPH:
            dist = float(d.get('length', haversine_distance(COMBINED_BASE_GRAPH.nodes[u]['lat'], COMBINED_BASE_GRAPH.nodes[u]['lng'], COMBINED_BASE_GRAPH.nodes[v]['lat'], COMBINED_BASE_GRAPH.nodes[v]['lng']) * 1000.0))
            t = meters_to_minutes(dist, WALK_SPEED_KMH)
            COMBINED_BASE_GRAPH.add_edge(u, v, mode='walk', type='walk', time=t, base_time=t, length=dist)

    for u, v, d in METRO_GRAPH.edges(data=True):
        if u in COMBINED_BASE_GRAPH and v in COMBINED_BASE_GRAPH:
            dist = float(d.get('length', haversine_distance(COMBINED_BASE_GRAPH.nodes[u]['lat'], COMBINED_BASE_GRAPH.nodes[u]['lng'], COMBINED_BASE_GRAPH.nodes[v]['lat'], COMBINED_BASE_GRAPH.nodes[v]['lng']) * 1000.0))
            t = meters_to_minutes(dist, METRO_SPEED_KMH)
            COMBINED_BASE_GRAPH.add_edge(u, v, mode='metro', type='metro', time=t, base_time=t, length=dist, geometry_coords=parse_geometry_coords(d.get('geometry_coords')))

    for s_id, w_id in STATION_TO_WALK_NODE.items():
        if s_id in COMBINED_BASE_GRAPH and w_id in COMBINED_BASE_GRAPH:
            dist = haversine_distance(COMBINED_BASE_GRAPH.nodes[s_id]['lat'], COMBINED_BASE_GRAPH.nodes[s_id]['lng'], COMBINED_BASE_GRAPH.nodes[w_id]['lat'], COMBINED_BASE_GRAPH.nodes[w_id]['lng']) * 1000.0
            t = meters_to_minutes(dist, WALK_SPEED_KMH)
            COMBINED_BASE_GRAPH.add_edge(s_id, w_id, mode='walk', type='walk_transfer', time=t, base_time=t, length=dist)

    return True

# Kiểm tra và đảo ngược danh sách các toạ độ nếu điểm đầu cấu trúc hình học không phải điểm gần cấu trúc được truyền. Giúp hiển thị lộ trình vẽ liền mạch trên bản đồ.
def orient_edge_coords(coords, start_lat, start_lng):
    if not coords: return []
    if (coords[-1][0] - start_lat)**2 + (coords[-1][1] - start_lng)**2 < (coords[0][0] - start_lat)**2 + (coords[0][1] - start_lng)**2:
        return list(reversed(coords))
    return coords

# Giữ nguyên logic chia chặng gốc của Frontend.
# Phân tích một chuỗi các nodes kết quả do A* trả về thành các đoạn hành trình nhằm dễ dàng visualize cho frontend.
def build_route_segments(graph, path):
    segments = []
    if not path or len(path) < 2: return segments
    current = None

    for u, v in zip(path[:-1], path[1:]):
        edge_data = graph[u][v]
        mode = get_edge_mode(edge_data)
        coords = orient_edge_coords(edge_data.get('geometry_coords') or [[graph.nodes[u]['lat'], graph.nodes[u]['lng']], [graph.nodes[v]['lat'], graph.nodes[v]['lng']]], graph.nodes[u]['lat'], graph.nodes[u]['lng'])

        if current is None or current['mode'] != mode:
            current = {
                'mode': mode, 'from_id': u, 'to_id': v, 
                'from_name': node_name(u, graph.nodes[u]), 'to_name': node_name(v, graph.nodes[v]),
                'node_ids': [u, v], 'coords': list(coords), 
                'time_min': float(edge_data.get('time', 0.0)), 'distance_m': float(edge_data.get('length', 0.0))
            }
            segments.append(current)
            continue

        current['to_id'] = v
        current['to_name'] = node_name(v, graph.nodes[v])
        current['node_ids'].append(v)
        current['time_min'] += float(edge_data.get('time', 0.0))
        current['distance_m'] += float(edge_data.get('length', 0.0))
        if current['coords'] and coords:
            if current['coords'][-1] == coords[0]: current['coords'].extend(coords[1:])
            else: current['coords'].extend(coords)

    return segments

# Chuyển đổi từng segment lớn thành các "chỉ dẫn đường đi - steps" cặn kẽ hơn để ứng dụng front-end in ra danh sách text cho người dùng đọc.
def build_detailed_steps(graph, segments):
    steps = []
    for idx, seg in enumerate(segments, start=1):
        if seg['mode'] == 'metro' and len(seg['node_ids']) > 2:
            for m_idx, (u, v) in enumerate(zip(seg['node_ids'][:-1], seg['node_ids'][1:]), start=1):
                steps.append({
                    'mode': 'metro', 'title': f"Chặng {idx}.{m_idx}: Đi metro từ {node_name(u, graph.nodes[u])} đến {node_name(v, graph.nodes[v])}",
                    'from': node_name(u, graph.nodes[u]), 'to': node_name(v, graph.nodes[v]),
                    'time_min': round(float(graph[u][v].get('time', 0.0)), 2), 'distance_m': round(float(graph[u][v].get('length', 0.0)), 1),
                    'stations': [node_name(u, graph.nodes[u]), node_name(v, graph.nodes[v])]
                })
        else:
            stations = list(dict.fromkeys([node_name(n, graph.nodes[n]) for n in seg['node_ids'] if graph.nodes[n].get('type') == 'station']))
            title = f"Chặng {idx}: Đi {'metro' if seg['mode'] == 'metro' else 'bộ'} từ {seg['from_name']} đến {seg['to_name']}"
            steps.append({
                'mode': seg['mode'], 'title': title, 'from': seg['from_name'], 'to': seg['to_name'],
                'time_min': round(seg['time_min'], 2), 'distance_m': round(seg['distance_m'], 1), 'stations': stations
            })
    return steps

# Hàm tổng hợp ghép điểm Khởi điểm (A) và điểm Đích (B) vào đồ thị tổ hợp tạm thời (tương thích cho A*). Tạo các "cạnh tiếp cận" tới tuyến đường đi bộ lân cận nhất rồi gọi A* xử lý, sau cùng kết xuất chi tiết hành trình.
def find_complete_path(point_a, point_b, forbidden_nodes, forbidden_edges, forbidden_zones):
    if not COMBINED_BASE_GRAPH: return None

    # Kiểm tra điểm bắt đầu/kết thúc so với các khu vực bị cấm
    for zone in forbidden_zones:
        rm = float(zone.get('radius_m', 0))
        if haversine_distance(point_a['lat'], point_a['lng'], zone['center_lat'], zone['center_lng']) * 1000 <= rm: return None
        if haversine_distance(point_b['lat'], point_b['lng'], zone['center_lat'], zone['center_lng']) * 1000 <= rm: return None

    graph = COMBINED_BASE_GRAPH.copy()
    graph.add_node('__point_a__', id='__point_a__', lat=point_a['lat'], lng=point_a['lng'], name='Điểm A', type='point')
    graph.add_node('__point_b__', id='__point_b__', lat=point_b['lat'], lng=point_b['lng'], name='Điểm B', type='point')

    def link_virtual_node(v_id, point):
        nearest = []
        if WALK_KDTREE:
            _, indices = WALK_KDTREE.query((point['lng'], point['lat']), k=6)
            # Xử lý an toàn tương thích với cả numpy array và giá trị đơn
            if hasattr(indices, '__iter__'):
                nearest = [WALK_NODE_IDS[int(i)] for i in indices]
            else:
                nearest = [WALK_NODE_IDS[int(indices)]]
                
        for w_id in nearest:
            if w_id not in graph: continue
            dist = haversine_distance(point['lat'], point['lng'], graph.nodes[w_id]['lat'], graph.nodes[w_id]['lng']) * 1000
            graph.add_edge(v_id, w_id, mode='walk', type='walk_access', time=meters_to_minutes(dist, WALK_SPEED_KMH), length=dist, geometry_coords=[[point['lat'], point['lng']], [graph.nodes[w_id]['lat'], graph.nodes[w_id]['lng']]])
    
    link_virtual_node('__point_a__', point_a)
    link_virtual_node('__point_b__', point_b)

    path, total_time = a_star_on_graph(graph, '__point_a__', '__point_b__', forbidden_nodes, forbidden_edges, forbidden_zones)
    if not path: return None

    segments = build_route_segments(graph, path)
    return {
        'path_nodes': path,
        'station_path': [n for n in path if n in NODES_DICT and NODES_DICT[n].get('type') == 'station'],
        'segments': segments,
        'walk_segments': [seg['coords'] for seg in segments if seg['mode'] != 'metro'],
        'metro_segments': [seg['coords'] for seg in segments if seg['mode'] == 'metro'],
        'steps': build_detailed_steps(graph, segments),
        'total_time_min': round(total_time, 2),
        'total_distance_m': round(sum(s['distance_m'] for s in segments), 1)
    }

# ============================================================================
# QUẢN LÝ TRẠNG THÁI
# ============================================================================

class AppState:
    """
    Quản lý trạng thái cấm. Thay vì để A* kiểm tra runtime, các block sẽ
    đặt time=inf trực tiếp trên COMBINED_BASE_GRAPH; unblock khôi phục về base_time.
    Các tập hợp dưới đây vẫn được duy trì cho endpoint /api/graph-data
    (frontend cần để vẽ marker/vùng đỏ), nhưng không còn ảnh hưởng đến A*.
    """
    def __init__(self):
        self.forbidden_nodes = set()
        self.forbidden_edges = set()      # Tập các cặp (u, v) đã được set inf bởi block_edge/block_node
        self.forbidden_edge_routes = []
        self.forbidden_zones = []

    # --- Tiện ích nội bộ: thao tác inf-weight trên COMBINED_BASE_GRAPH ---
    def _set_edge_inf(self, u, v):
        if COMBINED_BASE_GRAPH is not None and COMBINED_BASE_GRAPH.has_edge(u, v):
            COMBINED_BASE_GRAPH[u][v]['time'] = float('inf')

    def _restore_edge(self, u, v):
        if COMBINED_BASE_GRAPH is not None and COMBINED_BASE_GRAPH.has_edge(u, v):
            base = COMBINED_BASE_GRAPH[u][v].get('base_time')
            if base is not None:
                COMBINED_BASE_GRAPH[u][v]['time'] = float(base)

    def _edges_in_zone(self, zone):
        """Liệt kê các cạnh của COMBINED_BASE_GRAPH bị cắt bởi vùng cấm."""
        affected = []
        if COMBINED_BASE_GRAPH is None: return affected
        for u, v in COMBINED_BASE_GRAPH.edges():
            if edge_intersects_forbidden_zone(COMBINED_BASE_GRAPH, u, v, [zone]):
                affected.append((u, v))
        return affected

    def _is_edge_still_blocked(self, u, v):
        """Kiểm tra một cạnh có còn bị chặn bởi block khác sau khi unblock một nguồn."""
        if (u, v) in self.forbidden_edges or (v, u) in self.forbidden_edges: return True
        if u in self.forbidden_nodes or v in self.forbidden_nodes: return True
        for z in self.forbidden_zones:
            if edge_intersects_forbidden_zone(COMBINED_BASE_GRAPH, u, v, [z]): return True
        return False

    # --- Block / Unblock node ---
    def block_node(self, node_id):
        self.forbidden_nodes.add(node_id)
        if COMBINED_BASE_GRAPH is not None and node_id in COMBINED_BASE_GRAPH:
            for nb in COMBINED_BASE_GRAPH.neighbors(node_id):
                self._set_edge_inf(node_id, nb)

    def unblock_node(self, node_id):
        self.forbidden_nodes.discard(node_id)
        if COMBINED_BASE_GRAPH is not None and node_id in COMBINED_BASE_GRAPH:
            for nb in COMBINED_BASE_GRAPH.neighbors(node_id):
                if not self._is_edge_still_blocked(node_id, nb):
                    self._restore_edge(node_id, nb)

    # --- Block / Unblock edge ---
    def block_edge(self, node1, node2):
        # Trường hợp 1: cạnh đi bộ thông thường (không nằm trong METRO_GRAPH)
        if not METRO_GRAPH or node1 not in METRO_GRAPH or node2 not in METRO_GRAPH:
            self.forbidden_edges.update([(node1, node2), (node2, node1)])
            self._set_edge_inf(node1, node2)
            return

        # Trường hợp 2: cạnh metro - chặn toàn bộ chuỗi cạnh giữa hai trạm
        try: path = nx.shortest_path(METRO_GRAPH, node1, node2, weight='length')
        except: path = [node1, node2]

        # Tái tạo mảng geometry_coords để Frontend vẽ đường màu đỏ nối các ga
        geom_coords = []
        for u, v in zip(path[:-1], path[1:]):
            edge_data = METRO_GRAPH[u][v]
            coords = parse_geometry_coords(edge_data.get('geometry_coords')) or [[METRO_GRAPH.nodes[u]['lat'], METRO_GRAPH.nodes[u]['lng']], [METRO_GRAPH.nodes[v]['lat'], METRO_GRAPH.nodes[v]['lng']]]
            coords = orient_edge_coords(coords, METRO_GRAPH.nodes[u]['lat'], METRO_GRAPH.nodes[u]['lng'])
            if geom_coords and coords and geom_coords[-1] == coords[0]:
                geom_coords.extend(coords[1:])
            else:
                geom_coords.extend(coords)

        route = {
            'start': node1,
            'end': node2,
            'path': path,
            'segments': [[u, v] for u, v in zip(path[:-1], path[1:])],
            'geometry_coords': geom_coords
        }

        for u, v in route['segments']:
            self.forbidden_edges.update([(u, v), (v, u)])
            self._set_edge_inf(u, v)

        self.forbidden_edge_routes = [r for r in self.forbidden_edge_routes if not (r.get('start') in (node1, node2) and r.get('end') in (node1, node2))]
        self.forbidden_edge_routes.append(route)

    def unblock_edge(self, node1, node2):
        rem_routes, keep_routes = [], []
        for r in self.forbidden_edge_routes:
            if r['start'] in (node1, node2) and r['end'] in (node1, node2): rem_routes.append(r)
            else: keep_routes.append(r)

        if rem_routes:
            for r in rem_routes:
                for u, v in r.get('segments', []):
                    self.forbidden_edges.difference_update([(u, v), (v, u)])
                    if not self._is_edge_still_blocked(u, v):
                        self._restore_edge(u, v)
        else:
            self.forbidden_edges.difference_update([(node1, node2), (node2, node1)])
            if not self._is_edge_still_blocked(node1, node2):
                self._restore_edge(node1, node2)
        self.forbidden_edge_routes = keep_routes

    # --- Block / Unblock zone ---
    def block_zone(self, center_lat, center_lng, radius, boundary_lat=None, boundary_lng=None):
        zone = {'center_lat': float(center_lat), 'center_lng': float(center_lng), 'radius': radius}
        if boundary_lat is not None and boundary_lng is not None:
            zone['radius_m'] = haversine_distance(zone['center_lat'], zone['center_lng'], float(boundary_lat), float(boundary_lng)) * 1000.0
        else:
            try: zone['radius_m'] = float(radius) * 111000.0
            except: zone['radius_m'] = 0.0
        self.forbidden_zones.append(zone)
        # Đặt inf cho tất cả cạnh bị vùng cấm cắt qua
        for u, v in self._edges_in_zone(zone):
            self._set_edge_inf(u, v)

    def unblock_zone(self, center_lat, center_lng, radius):
        removed = [z for z in self.forbidden_zones if (abs(z['center_lat'] - center_lat) < 1e-6 and abs(z['center_lng'] - center_lng) < 1e-6 and abs(z.get('radius', 0.0) - radius) < 1e-6)]
        self.forbidden_zones = [z for z in self.forbidden_zones if z not in removed]
        # Với mỗi cạnh từng bị vùng này chặn, kiểm tra còn nguồn block nào khác không
        for zone in removed:
            for u, v in self._edges_in_zone(zone):
                if not self._is_edge_still_blocked(u, v):
                    self._restore_edge(u, v)

    # --- Reset ---
    def _restore_all_edges(self):
        if COMBINED_BASE_GRAPH is None: return
        for u, v, d in COMBINED_BASE_GRAPH.edges(data=True):
            base = d.get('base_time')
            if base is not None: d['time'] = float(base)

    def _reapply_all_blocks(self):
        """Sau khi clear một phạm vi, áp lại các block còn lại lên trọng số."""
        if COMBINED_BASE_GRAPH is None: return
        for n in self.forbidden_nodes:
            if n in COMBINED_BASE_GRAPH:
                for nb in COMBINED_BASE_GRAPH.neighbors(n):
                    self._set_edge_inf(n, nb)
        for u, v in self.forbidden_edges:
            self._set_edge_inf(u, v)
        for z in self.forbidden_zones:
            for u, v in self._edges_in_zone(z):
                self._set_edge_inf(u, v)

    def reset_all(self):
        self.forbidden_nodes = set()
        self.forbidden_edges = set()
        self.forbidden_edge_routes = []
        self.forbidden_zones = []
        self._restore_all_edges()

    def reset_nodes(self):
        self.forbidden_nodes = set()
        self._restore_all_edges()
        self._reapply_all_blocks()

    def reset_edges(self):
        self.forbidden_edges, self.forbidden_edge_routes = set(), []
        self._restore_all_edges()
        self._reapply_all_blocks()

    def reset_zones(self):
        self.forbidden_zones = []
        self._restore_all_edges()
        self._reapply_all_blocks()

app_state = AppState()

# ============================================================================
# REST API ENDPOINTS
# ============================================================================

@app.route('/')
def serve_index(): return send_file('index.html', mimetype='text/html')

@app.route('/api/graph-data', methods=['GET'])
def get_graph_data():
    if not NODES_DICT: return jsonify({'error': 'Graph not loaded', 'nodes': [], 'station_nodes': [], 'walk_nodes': [], 'edges': []}), 200
    
    nodes, station_nodes = [], []
    for n_id, n in NODES_DICT.items():
        data = {'id': n_id, 'lat': n['lat'], 'lng': n['lng'], 'name': n.get('name', ''), 'type': n.get('type', 'walk')}
        nodes.append(data)
        if data['type'] == 'station': station_nodes.append(data)
        
    return jsonify({
        'nodes': nodes, 'station_nodes': station_nodes, 'walk_nodes': WALK_NODES_API, 'edges': EDGES_LIST,
        'forbidden_nodes': list(app_state.forbidden_nodes), 'forbidden_edges': [list(e) for e in app_state.forbidden_edges],
        'forbidden_edge_routes': app_state.forbidden_edge_routes, 'forbidden_zones': app_state.forbidden_zones
    }), 200

@app.route('/api/validate-point', methods=['POST'])
def validate_point():
    data = request.get_json()
    lat = data.get('lat')
    lng = data.get('lng')
    
    if lat is None or lng is None:
        return jsonify({'error': 'Missing coordinates'}), 400

    if not is_in_st_petersburg(lat, lng):
        return jsonify({'error': 'Tọa độ không hợp lệ, ngoài thành phố St. Petersburg'}), 400

    if WALK_KDTREE:
        _, idx = WALK_KDTREE.query((lng, lat), k=1)
        node_id = WALK_NODE_IDS[int(idx)]
        node_coord = WALK_COORD_BY_ID[node_id]
        dist_m = haversine_distance(lat, lng, node_coord[0], node_coord[1]) * 1000

        if dist_m > 500:
            return jsonify({'error': 'Khu vực không thể di chuyển tới (cách điểm đi bộ gần nhất > 500m). Các vùng trên biển, sông hồ hoặc quá xa đường xá không thể chọn.'}), 400
            
    return jsonify({'success': True}), 200

@app.route('/api/find-path', methods=['POST'])
def find_path():
    data = request.get_json()
    pointA = data.get('pointA')
    pointB = data.get('pointB')
    
    if not pointA or not pointB: 
        return jsonify({'error': 'Missing points'}), 400
    
    # --- THÊM LOGIC KIỂM TRA TỌA ĐỘ TẠI ĐÂY ---
    if not is_in_st_petersburg(pointA['lat'], pointA['lng']) or \
       not is_in_st_petersburg(pointB['lat'], pointB['lng']):
        return jsonify({'error': 'Tọa độ không hợp lệ, ngoài thành phố St. Petersburg'}), 400
    # ------------------------------------------

    res = find_complete_path(pointA, pointB, app_state.forbidden_nodes, app_state.forbidden_edges, app_state.forbidden_zones)
    if not res: 
        return jsonify({'error': 'No path found'}), 404
    
    return jsonify({
        'path': res.get('station_path', []), 'path_nodes': res.get('path_nodes', []),
        'steps': res.get('steps', []), 'segments': res.get('segments', []),
        'walk_segments': res.get('walk_segments', []), 'metro_segments': res.get('metro_segments', []),
        'total_time_min': res.get('total_time_min', 0.0), 'total_distance_m': res.get('total_distance_m', 0.0),
        'distance': len(res.get('path_nodes', []))
    }), 200

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    if request.get_json().get('password') == '123456': return jsonify({'success': True}), 200
    return jsonify({'error': 'Invalid password'}), 401

@app.route('/api/admin/block-node', methods=['POST'])
def block_node():
    data = request.get_json()
    if data.get('password') != '123456': return jsonify({'error': 'Unauthorized'}), 401
    app_state.block_node(data.get('node_id'))
    return jsonify({'success': True, 'blocked_node': data.get('node_id')}), 200

@app.route('/api/admin/unblock-node', methods=['POST'])
def unblock_node_api():
    data = request.get_json()
    if data.get('password') != '123456': return jsonify({'error': 'Unauthorized'}), 401
    app_state.unblock_node(data.get('node_id'))
    return jsonify({'success': True, 'unblocked_node': data.get('node_id')}), 200

@app.route('/api/admin/block-edge', methods=['POST'])
def block_edge():
    data = request.get_json()
    if data.get('password') != '123456': return jsonify({'error': 'Unauthorized'}), 401
    app_state.block_edge(data.get('node1'), data.get('node2'))
    return jsonify({'success': True, 'blocked_edge': [data.get('node1'), data.get('node2')]}), 200

@app.route('/api/admin/unblock-edge', methods=['POST'])
def unblock_edge_api():
    data = request.get_json()
    if data.get('password') != '123456': return jsonify({'error': 'Unauthorized'}), 401
    app_state.unblock_edge(data.get('node1'), data.get('node2'))
    return jsonify({'success': True, 'unblocked_edge': [data.get('node1'), data.get('node2')]}), 200

@app.route('/api/admin/block-zone', methods=['POST'])
def block_zone():
    data = request.get_json()
    if data.get('password') != '123456': return jsonify({'error': 'Unauthorized'}), 401
    if None in (data.get('center_lat'), data.get('center_lng'), data.get('radius')): return jsonify({'error': 'Missing zone data'}), 400
    app_state.block_zone(data.get('center_lat'), data.get('center_lng'), data.get('radius'), data.get('boundary_lat'), data.get('boundary_lng'))
    return jsonify({'success': True, 'blocked_zone': {'center': [data['center_lat'], data['center_lng']], 'radius': data['radius']}}), 200

@app.route('/api/admin/unblock-zone', methods=['POST'])
def unblock_zone_api():
    data = request.get_json()
    if data.get('password') != '123456': return jsonify({'error': 'Unauthorized'}), 401
    if None in (data.get('center_lat'), data.get('center_lng'), data.get('radius')): return jsonify({'error': 'Missing zone data'}), 400
    app_state.unblock_zone(data.get('center_lat'), data.get('center_lng'), data.get('radius'))
    return jsonify({'success': True, 'unblocked_zone': {'center': [data['center_lat'], data['center_lng']], 'radius': data['radius']}}), 200

@app.route('/api/admin/reset', methods=['POST'])
def reset_state():
    data = request.get_json()
    if data.get('password') != '123456': return jsonify({'error': 'Unauthorized'}), 401
    scope = data.get('scope', 'all')
    if scope == 'nodes': app_state.reset_nodes()
    elif scope == 'edges': app_state.reset_edges()
    elif scope == 'zones': app_state.reset_zones()
    else: app_state.reset_all()
    return jsonify({'success': True, 'message': f'{scope} blocks reset', 'scope': scope}), 200

if __name__ == '__main__':
    print("[*] Loading St. Petersburg Metro graph...")
    load_graph_with_coordinates()
    print(f"[✓] Starting Flask server on http://localhost:5000")
    app.run(debug=False, host='0.0.0.0', port=5000)