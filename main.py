#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Smart Map Pro - St. Petersburg Metro Route Optimizer
A* Pathfinding with Admin Blocking System
"""

import json
import os
import ast
from math import sqrt, radians, sin, cos, atan2
import heapq
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import networkx as nx
from pyproj import Transformer
try:
    from scipy.spatial import cKDTree
except Exception:
    cKDTree = None

# ============================================================================
# INITIALIZATION
# ============================================================================

app = Flask(__name__)
CORS(app)

# Global variables
NODES_DICT = {}  # {node_id: {id, lat, lng, name, type, connections: [...]}}
EDGES_LIST = []  # List of edges for API
WALK_GRAPH = None
METRO_GRAPH = None
WALK_NODE_IDS = []
WALK_NODE_COORDS = []
WALK_NODES_API = []
WALK_KDTREE = None
WALK_COORD_BY_ID = {}
STATION_TO_WALK_NODE = {}
WALK_NODE_TO_STATIONS = {}
METRO_COMPONENT_INDEX = {}
COMBINED_BASE_GRAPH = None
APP_STATE_FILE = 'graph/cache/app_state.json'

WALK_SPEED_KMH = 4.8
METRO_SPEED_KMH = 36.0
MAX_SPEED_KMH_FOR_HEURISTIC = max(WALK_SPEED_KMH, METRO_SPEED_KMH)

# ============================================================================
# UTILITIES - HEURISTIC & DISTANCE
# ============================================================================

def euclidean_distance(lat1, lng1, lat2, lng2):
    """Calculate Euclidean distance between two coordinates (in degrees)"""
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    return sqrt(dlat * dlat + dlng * dlng)

def haversine_distance(lat1, lng1, lat2, lng2):
    """Calculate haversine distance in km"""
    R = 6371  # Earth radius in km
    lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlng/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c


def meters_to_minutes(distance_m, speed_kmh):
    if speed_kmh <= 0:
        return 0.0
    return (distance_m / 1000.0) / speed_kmh * 60.0


def parse_geometry_coords(value):
    if value is None:
        return []

    parsed = value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except Exception:
            try:
                parsed = ast.literal_eval(raw)
            except Exception:
                return []

    if not isinstance(parsed, (list, tuple)):
        return []

    coords = []
    for item in parsed:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        try:
            lat = float(item[0])
            lng = float(item[1])
        except Exception:
            continue

        if abs(lat) > 90 and abs(lng) <= 90:
            lat, lng = lng, lat
        if abs(lat) <= 90 and abs(lng) <= 180:
            coords.append([lat, lng])

    return coords


def node_name(node_id, node_data):
    if node_id == '__point_a__':
        return 'Điểm A'
    if node_id == '__point_b__':
        return 'Điểm B'
    return node_data.get('name') or node_id


def get_edge_mode(edge_data):
    mode = str(edge_data.get('mode', '')).lower()
    if mode:
        return mode
    edge_type = str(edge_data.get('type', '')).lower()
    if edge_type == 'metro':
        return 'metro'
    return 'walk'


def edge_time_minutes(edge_data, fallback_distance_m=0.0):
    time_val = edge_data.get('time')
    if time_val is not None:
        try:
            t = float(time_val)
            if t > 0:
                return t
        except Exception:
            pass

    length_val = edge_data.get('length')
    dist_m = fallback_distance_m
    if length_val is not None:
        try:
            dist_m = float(length_val)
        except Exception:
            pass

    mode = get_edge_mode(edge_data)
    speed = METRO_SPEED_KMH if mode == 'metro' else WALK_SPEED_KMH
    return meters_to_minutes(max(0.0, dist_m), speed)

# ============================================================================
# A* PATHFINDING ALGORITHM
# ============================================================================

def a_star_pathfinding(start_id, end_id, nodes_dict, forbidden_nodes, forbidden_edges, forbidden_zones):
    """
    A* pathfinding algorithm
    Returns path as list of node IDs, or None if no path exists
    """
    if start_id not in nodes_dict or end_id not in nodes_dict:
        return None
    
    start_node = nodes_dict[start_id]
    end_node = nodes_dict[end_id]
    
    # Priority queue: (f_score, counter, node_id)
    open_set = [(0, 0, start_id)]
    came_from = {}
    g_score = {start_id: 0}
    h_score = euclidean_distance(start_node['lat'], start_node['lng'],
                                  end_node['lat'], end_node['lng'])
    f_score = {start_id: h_score}
    counter = 1
    
    while open_set:
        current_f, _, current_id = heapq.heappop(open_set)
        
        if current_id == end_id:
            # Reconstruct path
            path = [current_id]
            while current_id in came_from:
                current_id = came_from[current_id]
                path.append(current_id)
            return path[::-1]
        
        current_node = nodes_dict[current_id]
        
        # Check if node is forbidden
        if current_id in forbidden_nodes:
            continue
        
        # Check if in forbidden zone
        in_forbidden_zone = False
        for zone in forbidden_zones:
            dist_to_zone = euclidean_distance(
                current_node['lat'], current_node['lng'],
                zone['center_lat'], zone['center_lng']
            )
            if dist_to_zone <= zone['radius']:
                in_forbidden_zone = True
                break
        if in_forbidden_zone:
            continue
        
        # Explore neighbors
        for neighbor_id in current_node['connections']:
            if neighbor_id in forbidden_nodes:
                continue
            
            # Check if edge is forbidden
            if (current_id, neighbor_id) in forbidden_edges or \
               (neighbor_id, current_id) in forbidden_edges:
                continue
            
            neighbor_node = nodes_dict[neighbor_id]
            
            # Cost = Euclidean distance (metro travel)
            edge_cost = euclidean_distance(
                current_node['lat'], current_node['lng'],
                neighbor_node['lat'], neighbor_node['lng']
            )
            
            tentative_g = g_score[current_id] + edge_cost
            
            if neighbor_id not in g_score or tentative_g < g_score[neighbor_id]:
                came_from[neighbor_id] = current_id
                g_score[neighbor_id] = tentative_g
                h = euclidean_distance(neighbor_node['lat'], neighbor_node['lng'],
                                      end_node['lat'], end_node['lng'])
                f_score[neighbor_id] = tentative_g + h
                heapq.heappush(open_set, (f_score[neighbor_id], counter, neighbor_id))
                counter += 1
    
    return None


def a_star_on_graph(graph, start_id, end_id, forbidden_nodes=None, forbidden_edges=None, forbidden_zones=None):
    """A* on a weighted multimodal graph with dynamic forbidden checking.
    Returns (path, total_time_minutes).
    Checks forbidden status inline - no graph copying needed.
    """
    if start_id not in graph or end_id not in graph:
        return None, float('inf')

    forbidden_nodes = forbidden_nodes or set()
    forbidden_edges = forbidden_edges or set()
    forbidden_zones = forbidden_zones or []

    def is_node_forbidden(node_id):
        if node_id in forbidden_nodes:
            return True
        if forbidden_zones and node_id in graph:
            node_data = graph.nodes[node_id]
            for zone in forbidden_zones:
                dist = euclidean_distance(
                    node_data['lat'], node_data['lng'],
                    zone['center_lat'], zone['center_lng']
                )
                if dist <= zone['radius']:
                    return True
        return False

    def is_edge_forbidden(u, v):
        return (u, v) in forbidden_edges or (v, u) in forbidden_edges

    def heuristic_minutes(node_id):
        a = graph.nodes[node_id]
        b = graph.nodes[end_id]
        dist_km = haversine_distance(a['lat'], a['lng'], b['lat'], b['lng'])
        return (dist_km / MAX_SPEED_KMH_FOR_HEURISTIC) * 60.0

    if is_node_forbidden(start_id) or is_node_forbidden(end_id):
        return None, float('inf')

    open_set = [(heuristic_minutes(start_id), 0, start_id)]
    came_from = {}
    g_score = {start_id: 0.0}
    counter = 1

    while open_set:
        _, _, current = heapq.heappop(open_set)
        if current == end_id:
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            return path, g_score[end_id]

        for neighbor in graph.neighbors(current):
            if is_node_forbidden(neighbor) or is_edge_forbidden(current, neighbor):
                continue
            edge_data = graph[current][neighbor]
            tentative_g = g_score[current] + float(edge_data.get('time', 0.0))
            if tentative_g < g_score.get(neighbor, float('inf')):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f = tentative_g + heuristic_minutes(neighbor)
                heapq.heappush(open_set, (f, counter, neighbor))
                counter += 1

    return None, float('inf')

# ============================================================================
# GRAPH LOADING
# ============================================================================

def load_graph_with_coordinates():
    """Load metro graph and walk graph, then link metro stations to nearest walk nodes."""
    global NODES_DICT, EDGES_LIST, WALK_GRAPH, METRO_GRAPH, WALK_NODE_IDS, WALK_NODE_COORDS
    global WALK_NODES_API, WALK_KDTREE, WALK_COORD_BY_ID, STATION_TO_WALK_NODE, WALK_NODE_TO_STATIONS, METRO_COMPONENT_INDEX
    global COMBINED_BASE_GRAPH

    metro_path = 'graph/spd_metro.graphml'
    walk_path = 'graph/spd_walk.graphml'
    if not os.path.exists(metro_path) or not os.path.exists(walk_path):
        print(f"Error: missing graph files. metro={os.path.exists(metro_path)} walk={os.path.exists(walk_path)}")
        return False

    try:
        metro_graph = nx.read_graphml(metro_path)
        METRO_GRAPH = metro_graph
        WALK_GRAPH = nx.read_graphml(walk_path)
        utm36_to_wgs84 = Transformer.from_crs("EPSG:32636", "EPSG:4326", always_xy=True)

        def normalize_coords(raw_x, raw_y, raw_lat=None, raw_lng=None):
            if raw_lat is not None and raw_lng is not None:
                lat = float(raw_lat)
                lng = float(raw_lng)
                if -90 <= lat <= 90 and -180 <= lng <= 180:
                    return lat, lng

            x = float(raw_x)
            y = float(raw_y)
            if -180 <= x <= 180 and -90 <= y <= 90:
                return y, x

            lon, lat = utm36_to_wgs84.transform(x, y)
            return lat, lon

        NODES_DICT = {}
        EDGES_LIST = []
        STATION_TO_WALK_NODE = {}
        WALK_NODE_TO_STATIONS = {}

        for node_id, node_data in metro_graph.nodes(data=True):
            lat, lng = normalize_coords(
                node_data.get('x', 0),
                node_data.get('y', 0),
                node_data.get('lat'),
                node_data.get('lng')
            )
            node_type = node_data.get('type')
            if not node_type:
                if str(node_data.get('is_metro_station', '')).lower() in ('true', '1', 'yes'):
                    node_type = 'station'
                else:
                    node_type = 'walk'

            NODES_DICT[node_id] = {
                'id': node_id,
                'lat': lat,
                'lng': lng,
                'name': node_data.get('name', node_id),
                'type': node_type,
                'connections': []
            }

        for u, v, edge_data in metro_graph.edges(data=True):
            edge_type = edge_data.get('type', 'metro')
            NODES_DICT[u]['connections'].append(v)
            EDGES_LIST.append({'from': u, 'to': v, 'type': edge_type})
            if v not in NODES_DICT[u]['connections']:
                NODES_DICT[u]['connections'].append(v)
            if u not in NODES_DICT[v]['connections']:
                NODES_DICT[v]['connections'].append(u)

        metro_undirected = nx.Graph()
        for node_id in NODES_DICT:
            metro_undirected.add_node(node_id)
        for edge in EDGES_LIST:
            metro_undirected.add_edge(edge['from'], edge['to'])
        METRO_COMPONENT_INDEX = {}
        for idx, comp in enumerate(nx.connected_components(metro_undirected)):
            for node_id in comp:
                METRO_COMPONENT_INDEX[node_id] = idx

        WALK_NODE_IDS = []
        WALK_NODE_COORDS = []
        WALK_NODES_API = []
        WALK_COORD_BY_ID = {}
        for node_id, node_data in WALK_GRAPH.nodes(data=True):
            lat, lng = normalize_coords(node_data.get('x', 0), node_data.get('y', 0))
            WALK_NODE_IDS.append(node_id)
            WALK_NODE_COORDS.append((lat, lng))
            WALK_COORD_BY_ID[node_id] = (lat, lng)
            WALK_NODES_API.append({
                'id': node_id,
                'lat': lat,
                'lng': lng,
                'name': node_data.get('name', ''),
                'type': 'walk'
            })

        WALK_KDTREE = cKDTree([(lng, lat) for lat, lng in WALK_NODE_COORDS]) if cKDTree else None

        for station_id, station_data in NODES_DICT.items():
            if station_data.get('type') != 'station':
                continue
            nearest_walk_id = find_nearest_walk_node(station_data['lat'], station_data['lng'])
            if nearest_walk_id is None:
                continue
            STATION_TO_WALK_NODE[station_id] = nearest_walk_id
            WALK_NODE_TO_STATIONS.setdefault(nearest_walk_id, []).append(station_id)

        COMBINED_BASE_GRAPH = build_combined_base_graph()

        print(
            f"Loaded metro: {len(NODES_DICT)} nodes/{len(EDGES_LIST)} edges | "
            f"walk: {len(WALK_NODE_IDS)} nodes | station links: {len(STATION_TO_WALK_NODE)}"
        )
        return True

    except Exception as e:
        print(f"Error loading graph: {e}")
        return False


def build_combined_base_graph():
    """Build a base multimodal graph that includes walk + metro + station transfer edges."""
    graph = nx.Graph()

    for node_id, node_data in NODES_DICT.items():
        graph.add_node(
            node_id,
            id=node_id,
            lat=float(node_data['lat']),
            lng=float(node_data['lng']),
            name=node_data.get('name', node_id),
            type=node_data.get('type', 'station')
        )

    for node_id, (lat, lng) in WALK_COORD_BY_ID.items():
        if node_id in graph:
            continue
        graph.add_node(
            node_id,
            id=node_id,
            lat=float(lat),
            lng=float(lng),
            name=f"walk_{node_id}",
            type='walk'
        )

    if WALK_GRAPH is not None:
        for u, v, edge_data in WALK_GRAPH.edges(data=True):
            if u not in graph or v not in graph:
                continue
            a = graph.nodes[u]
            b = graph.nodes[v]
            fallback_len_m = haversine_distance(a['lat'], a['lng'], b['lat'], b['lng']) * 1000.0
            time_min = edge_time_minutes({'mode': 'walk', **dict(edge_data)}, fallback_len_m)
            length_m = float(edge_data.get('length', fallback_len_m) or fallback_len_m)
            graph.add_edge(
                u,
                v,
                mode='walk',
                type='walk',
                time=float(time_min),
                length=float(length_m)
            )

    if METRO_GRAPH is not None:
        for u, v, edge_data in METRO_GRAPH.edges(data=True):
            if u not in graph or v not in graph:
                continue
            a = graph.nodes[u]
            b = graph.nodes[v]
            fallback_len_m = haversine_distance(a['lat'], a['lng'], b['lat'], b['lng']) * 1000.0
            length_m = float(edge_data.get('length', fallback_len_m) or fallback_len_m)
            time_min = edge_time_minutes({'mode': 'metro', **dict(edge_data)}, length_m)
            geometry = parse_geometry_coords(edge_data.get('geometry_coords'))
            graph.add_edge(
                u,
                v,
                mode='metro',
                type='metro',
                line=edge_data.get('line', ''),
                geometry_coords=geometry,
                time=float(time_min),
                length=float(length_m)
            )

    for station_id, walk_id in STATION_TO_WALK_NODE.items():
        if station_id not in graph or walk_id not in graph:
            continue
        a = graph.nodes[station_id]
        b = graph.nodes[walk_id]
        dist_m = haversine_distance(a['lat'], a['lng'], b['lat'], b['lng']) * 1000.0
        graph.add_edge(
            station_id,
            walk_id,
            mode='walk',
            type='walk_transfer',
            time=meters_to_minutes(dist_m, WALK_SPEED_KMH),
            length=dist_m
        )

    return graph

# ============================================================================
# COMPLETE ROUTING LOGIC
# ============================================================================

def find_k_nearest_walk_nodes(lat, lng, k=5):
    """Find up to k nearest walk nodes to a coordinate."""
    if not WALK_NODE_IDS:
        return []

    if WALK_KDTREE is None:
        scored = []
        for node_id, (n_lat, n_lng) in WALK_COORD_BY_ID.items():
            dist_m = haversine_distance(lat, lng, n_lat, n_lng) * 1000.0
            scored.append((dist_m, node_id))
        scored.sort(key=lambda x: x[0])
        return [nid for _, nid in scored[:k]]

    kk = min(k, len(WALK_NODE_IDS))
    dists, indices = WALK_KDTREE.query((lng, lat), k=kk)
    if kk == 1:
        indices = [indices]
    return [WALK_NODE_IDS[int(i)] for i in indices]


def find_nearest_walk_node(lat, lng):
    """Find nearest walk-graph node to a coordinate."""
    if not WALK_NODE_IDS:
        return None

    if WALK_KDTREE is not None:
        _, idx = WALK_KDTREE.query((lng, lat), k=1)
        return WALK_NODE_IDS[int(idx)]

    best_idx = min(
        range(len(WALK_NODE_COORDS)),
        key=lambda i: (WALK_NODE_COORDS[i][0] - lat) ** 2 + (WALK_NODE_COORDS[i][1] - lng) ** 2
    )
    return WALK_NODE_IDS[best_idx]


def orient_edge_coords(coords, start_lat, start_lng):
    """Orient polyline to start near the given start coordinate."""
    if not coords:
        return []
    first = coords[0]
    last = coords[-1]
    d_first = (first[0] - start_lat) ** 2 + (first[1] - start_lng) ** 2
    d_last = (last[0] - start_lat) ** 2 + (last[1] - start_lng) ** 2
    if d_last < d_first:
        return list(reversed(coords))
    return coords


def build_route_segments(graph, path):
    """Convert node path into grouped walk/metro segments with geometry and timing."""
    segments = []
    if not path or len(path) < 2:
        return segments

    current = None

    for u, v in zip(path[:-1], path[1:]):
        edge_data = graph[u][v]
        mode = get_edge_mode(edge_data)
        u_node = graph.nodes[u]
        v_node = graph.nodes[v]

        coords = edge_data.get('geometry_coords')
        if not coords:
            coords = [[u_node['lat'], u_node['lng']], [v_node['lat'], v_node['lng']]
            ]
        coords = orient_edge_coords(coords, u_node['lat'], u_node['lng'])

        edge_time = float(edge_data.get('time', 0.0))
        edge_len = float(edge_data.get('length', 0.0))

        if current is None or current['mode'] != mode:
            current = {
                'mode': mode,
                'from_id': u,
                'to_id': v,
                'from_name': node_name(u, u_node),
                'to_name': node_name(v, v_node),
                'node_ids': [u, v],
                'coords': list(coords),
                'time_min': edge_time,
                'distance_m': edge_len,
            }
            segments.append(current)
            continue

        current['to_id'] = v
        current['to_name'] = node_name(v, v_node)
        current['node_ids'].append(v)
        current['time_min'] += edge_time
        current['distance_m'] += edge_len
        if current['coords'] and coords:
            if current['coords'][-1] == coords[0]:
                current['coords'].extend(coords[1:])
            else:
                current['coords'].extend(coords)

    return segments


def build_detailed_steps(graph, segments):
    steps = []
    for idx, seg in enumerate(segments, start=1):
        station_names = [
            node_name(node_id, graph.nodes[node_id])
            for node_id in seg['node_ids']
            if graph.nodes[node_id].get('type') == 'station'
        ]
        station_names = list(dict.fromkeys(station_names))

        if seg['mode'] == 'metro':
            title = f"Chặng {idx}: Đi metro từ {seg['from_name']} đến {seg['to_name']}"
        else:
            title = f"Chặng {idx}: Đi bộ từ {seg['from_name']} đến {seg['to_name']}"

        steps.append({
            'mode': seg['mode'],
            'title': title,
            'from': seg['from_name'],
            'to': seg['to_name'],
            'time_min': round(seg['time_min'], 2),
            'distance_m': round(seg['distance_m'], 1),
            'stations': station_names
        })
    return steps


def find_complete_path(point_a, point_b, forbidden_nodes, forbidden_edges, forbidden_zones):
    """Run unified A* from A to B on the combined walk+metro graph.
    Now passes forbidden items as dynamic parameters instead of copying graph.
    """
    if COMBINED_BASE_GRAPH is None:
        return None

    # Check if start/end points are in forbidden zones
    for zone in forbidden_zones:
        dist_a = euclidean_distance(
            point_a['lat'], point_a['lng'],
            zone['center_lat'], zone['center_lng']
        )
        if dist_a <= zone['radius']:
            return None
        dist_b = euclidean_distance(
            point_b['lat'], point_b['lng'],
            zone['center_lat'], zone['center_lng']
        )
        if dist_b <= zone['radius']:
            return None

    # Create temporary graph with virtual A/B points
    graph = COMBINED_BASE_GRAPH.copy()
    graph.add_node('__point_a__', id='__point_a__', lat=point_a['lat'], lng=point_a['lng'], name='Điểm A', type='point')
    graph.add_node('__point_b__', id='__point_b__', lat=point_b['lat'], lng=point_b['lng'], name='Điểm B', type='point')

    nearest_a = find_k_nearest_walk_nodes(point_a['lat'], point_a['lng'], k=6)
    nearest_b = find_k_nearest_walk_nodes(point_b['lat'], point_b['lng'], k=6)
    if not nearest_a or not nearest_b:
        return None

    for walk_id in nearest_a:
        if walk_id not in graph:
            continue
        walk_node = graph.nodes[walk_id]
        dist_m = haversine_distance(point_a['lat'], point_a['lng'], walk_node['lat'], walk_node['lng']) * 1000.0
        graph.add_edge(
            '__point_a__',
            walk_id,
            mode='walk',
            type='walk_access',
            time=meters_to_minutes(dist_m, WALK_SPEED_KMH),
            length=dist_m,
            geometry_coords=[[point_a['lat'], point_a['lng']], [walk_node['lat'], walk_node['lng']]]
        )

    for walk_id in nearest_b:
        if walk_id not in graph:
            continue
        walk_node = graph.nodes[walk_id]
        dist_m = haversine_distance(point_b['lat'], point_b['lng'], walk_node['lat'], walk_node['lng']) * 1000.0
        graph.add_edge(
            '__point_b__',
            walk_id,
            mode='walk',
            type='walk_access',
            time=meters_to_minutes(dist_m, WALK_SPEED_KMH),
            length=dist_m,
            geometry_coords=[[point_b['lat'], point_b['lng']], [walk_node['lat'], walk_node['lng']]]
        )

    # Pass forbidden items as parameters - A* checks inline
    path, total_time = a_star_on_graph(
        graph, '__point_a__', '__point_b__',
        forbidden_nodes=forbidden_nodes,
        forbidden_edges=forbidden_edges,
        forbidden_zones=forbidden_zones
    )
    if not path:
        return None

    segments = build_route_segments(graph, path)
    steps = build_detailed_steps(graph, segments)

    walk_segments = [seg['coords'] for seg in segments if seg['mode'] != 'metro']
    metro_segments = [seg['coords'] for seg in segments if seg['mode'] == 'metro']
    station_path = [
        node_id for node_id in path
        if node_id in NODES_DICT and NODES_DICT[node_id].get('type') == 'station'
    ]
    total_distance = sum(seg['distance_m'] for seg in segments)

    return {
        'path_nodes': path,
        'station_path': station_path,
        'segments': segments,
        'walk_segments': walk_segments,
        'metro_segments': metro_segments,
        'steps': steps,
        'total_time_min': round(total_time, 2),
        'total_distance_m': round(total_distance, 1)
    }

# ============================================================================
# STATE MANAGEMENT
# ============================================================================

class AppState:
    """Manage application state (forbidden nodes/edges/zones)"""
    
    def __init__(self):
        self.forbidden_nodes = set()
        self.forbidden_edges = set()
        self.forbidden_zones = []
        self.load_state()
    
    def load_state(self):
        """Load state from JSON file"""
        if os.path.exists(APP_STATE_FILE):
            try:
                with open(APP_STATE_FILE, 'r') as f:
                    data = json.load(f)
                    self.forbidden_nodes = set(data.get('forbidden_nodes', []))
                    self.forbidden_edges = set(tuple(e) for e in data.get('forbidden_edges', []))
                    self.forbidden_zones = data.get('forbidden_zones', [])
            except:
                pass
    
    def save_state(self):
        """Save state to JSON file"""
        os.makedirs(os.path.dirname(APP_STATE_FILE), exist_ok=True)
        with open(APP_STATE_FILE, 'w') as f:
            data = {
                'forbidden_nodes': list(self.forbidden_nodes),
                'forbidden_edges': [list(e) for e in self.forbidden_edges],
                'forbidden_zones': self.forbidden_zones,
                'saved_at': datetime.now().isoformat()
            }
            json.dump(data, f, indent=2)
    
    def block_node(self, node_id):
        """Block a node"""
        self.forbidden_nodes.add(node_id)
        self.save_state()
    
    def unblock_node(self, node_id):
        """Unblock a node"""
        self.forbidden_nodes.discard(node_id)
        self.save_state()
    
    def block_edge(self, node1, node2):
        """Block an edge"""
        self.forbidden_edges.add((node1, node2))
        self.forbidden_edges.add((node2, node1))
        self.save_state()
    
    def unblock_edge(self, node1, node2):
        """Unblock an edge"""
        self.forbidden_edges.discard((node1, node2))
        self.forbidden_edges.discard((node2, node1))
        self.save_state()
    
    def block_zone(self, center_lat, center_lng, radius):
        """Block a zone"""
        self.forbidden_zones.append({
            'center_lat': center_lat,
            'center_lng': center_lng,
            'radius': radius
        })
        self.save_state()
    
    def reset_all(self):
        """Reset all blocks"""
        self.forbidden_nodes = set()
        self.forbidden_edges = set()
        self.forbidden_zones = []
        self.save_state()

# Create app state instance
app_state = AppState()

# ============================================================================
# REST API ENDPOINTS
# ============================================================================

@app.route('/')
def serve_index():
    """Serve index.html with proper MIME type"""
    return send_file('index.html', mimetype='text/html')

@app.route('/api/graph-data', methods=['GET'])
def get_graph_data():
    """API: Get graph data (nodes + edges)"""
    if not NODES_DICT:
        return jsonify({
            'error': 'Graph not loaded',
            'nodes': [],
            'station_nodes': [],
            'walk_nodes': [],
            'edges': []
        }), 200
    
    nodes = []
    station_nodes = []
    walk_nodes = []
    for node_id, node in NODES_DICT.items():
        node_data = {
            'id': node_id,
            'lat': node['lat'],
            'lng': node['lng'],
            'name': node.get('name', ''),
            'type': node.get('type', 'walk')
        }
        nodes.append(node_data)
        if node_data['type'] == 'station':
            station_nodes.append(node_data)
        else:
            walk_nodes.append(node_data)

    # Walk nodes come from the dedicated walk graph and can be much larger than metro nodes.
    if WALK_NODES_API:
        walk_nodes = WALK_NODES_API
    
    return jsonify({
        'nodes': nodes,
        'station_nodes': station_nodes,
        'walk_nodes': walk_nodes,
        'edges': EDGES_LIST,
        'forbidden_nodes': list(app_state.forbidden_nodes),
        'forbidden_edges': [list(e) for e in app_state.forbidden_edges],
        'forbidden_zones': app_state.forbidden_zones
    }), 200


@app.route('/api/find-path', methods=['POST'])
def find_path():
    """API: Find path from point A to point B"""
    try:
        data = request.get_json()
        point_a = data.get('pointA', {})
        point_b = data.get('pointB', {})
        
        if not point_a or not point_b:
            return jsonify({'error': 'Missing points'}), 400
        
        result = find_complete_path(
            point_a, point_b,
            app_state.forbidden_nodes,
            app_state.forbidden_edges,
            app_state.forbidden_zones
        )
        
        if not result:
            return jsonify({'error': 'No path found'}), 404
        
        return jsonify({
            'path': result.get('station_path', []),
            'path_nodes': result.get('path_nodes', []),
            'steps': result.get('steps', []),
            'segments': result.get('segments', []),
            'walk_segments': result.get('walk_segments', []),
            'metro_segments': result.get('metro_segments', []),
            'total_time_min': result.get('total_time_min', 0.0),
            'total_distance_m': result.get('total_distance_m', 0.0),
            'distance': len(result.get('path_nodes', []))
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    """API: Admin login"""
    data = request.get_json()
    password = data.get('password', '')
    
    if password == '123456':
        return jsonify({'success': True}), 200
    else:
        return jsonify({'error': 'Invalid password'}), 401

@app.route('/api/admin/block-node', methods=['POST'])
def block_node():
    """API: Block a node"""
    data = request.get_json()
    node_id = data.get('node_id', '')
    password = data.get('password', '')
    
    if password != '123456':
        return jsonify({'error': 'Unauthorized'}), 401
    
    app_state.block_node(node_id)
    return jsonify({'success': True, 'blocked_node': node_id}), 200

@app.route('/api/admin/unblock-node', methods=['POST'])
def unblock_node():
    """API: Unblock a node"""
    data = request.get_json()
    node_id = data.get('node_id', '')
    password = data.get('password', '')
    
    if password != '123456':
        return jsonify({'error': 'Unauthorized'}), 401
    
    app_state.unblock_node(node_id)
    return jsonify({'success': True, 'unblocked_node': node_id}), 200

@app.route('/api/admin/block-edge', methods=['POST'])
def block_edge():
    """API: Block an edge"""
    data = request.get_json()
    node1 = data.get('node1', '')
    node2 = data.get('node2', '')
    password = data.get('password', '')
    
    if password != '123456':
        return jsonify({'error': 'Unauthorized'}), 401
    
    app_state.block_edge(node1, node2)
    return jsonify({'success': True, 'blocked_edge': [node1, node2]}), 200

@app.route('/api/admin/unblock-edge', methods=['POST'])
def unblock_edge():
    """API: Unblock an edge"""
    data = request.get_json()
    node1 = data.get('node1', '')
    node2 = data.get('node2', '')
    password = data.get('password', '')
    
    if password != '123456':
        return jsonify({'error': 'Unauthorized'}), 401
    
    app_state.unblock_edge(node1, node2)
    return jsonify({'success': True, 'unblocked_edge': [node1, node2]}), 200

@app.route('/api/admin/block-zone', methods=['POST'])
def block_zone():
    """API: Block a zone"""
    data = request.get_json()
    center_lat = data.get('center_lat')
    center_lng = data.get('center_lng')
    radius = data.get('radius')
    password = data.get('password', '')
    
    if password != '123456':
        return jsonify({'error': 'Unauthorized'}), 401
    
    if center_lat is None or center_lng is None or radius is None:
        return jsonify({'error': 'Missing zone data'}), 400
    
    app_state.block_zone(center_lat, center_lng, radius)
    return jsonify({'success': True, 'blocked_zone': {
        'center': [center_lat, center_lng],
        'radius': radius
    }}), 200

@app.route('/api/admin/reset', methods=['POST'])
def reset_state():
    """API: Reset all blocks"""
    data = request.get_json()
    password = data.get('password', '')
    
    if password != '123456':
        return jsonify({'error': 'Unauthorized'}), 401
    
    app_state.reset_all()
    return jsonify({'success': True, 'message': 'All blocks reset'}), 200

# ============================================================================
# APPLICATION STARTUP
# ============================================================================

if __name__ == '__main__':
    print("[*] Loading graph...")
    load_graph_with_coordinates()
    
    print(f"[✓] Starting Flask server...")
    print(f"[*] Open http://localhost:5000 in your browser")
    print(f"[*] Admin password: 123456")
    
    app.run(debug=False, host='0.0.0.0', port=5000)
