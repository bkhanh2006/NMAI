#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Smart Map Pro - St. Petersburg Metro Route Optimizer
A* Pathfinding with Admin Blocking System
"""

import json
import os
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
WALK_NODE_IDS = []
WALK_NODE_COORDS = []
WALK_NODES_API = []
WALK_KDTREE = None
WALK_COORD_BY_ID = {}
STATION_TO_WALK_NODE = {}
WALK_NODE_TO_STATIONS = {}
METRO_COMPONENT_INDEX = {}
APP_STATE_FILE = 'graph/cache/app_state.json'

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

# ============================================================================
# GRAPH LOADING
# ============================================================================

def load_graph_with_coordinates():
    """Load metro graph and walk graph, then link metro stations to nearest walk nodes."""
    global NODES_DICT, EDGES_LIST, WALK_GRAPH, WALK_NODE_IDS, WALK_NODE_COORDS
    global WALK_NODES_API, WALK_KDTREE, WALK_COORD_BY_ID, STATION_TO_WALK_NODE, WALK_NODE_TO_STATIONS, METRO_COMPONENT_INDEX

    metro_path = 'graph/spd_metro.graphml'
    walk_path = 'graph/spd_walk.graphml'
    if not os.path.exists(metro_path) or not os.path.exists(walk_path):
        print(f"Error: missing graph files. metro={os.path.exists(metro_path)} walk={os.path.exists(walk_path)}")
        return False

    try:
        metro_graph = nx.read_graphml(metro_path)
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

        print(
            f"Loaded metro: {len(NODES_DICT)} nodes/{len(EDGES_LIST)} edges | "
            f"walk: {len(WALK_NODE_IDS)} nodes | station links: {len(STATION_TO_WALK_NODE)}"
        )
        return True

    except Exception as e:
        print(f"Error loading graph: {e}")
        return False

# ============================================================================
# COMPLETE ROUTING LOGIC
# ============================================================================

def find_3_nearest_station_nodes(lat, lng, n=3):
    """Find n nearest metro station nodes to a coordinate"""
    if not NODES_DICT:
        return []
    
    nodes_with_dist = []
    for node_id, node in NODES_DICT.items():
        if node.get('type') != 'station':
            continue
        dist = euclidean_distance(lat, lng, node['lat'], node['lng'])
        nodes_with_dist.append((dist, node_id))
    
    nodes_with_dist.sort()
    return [node_id for _, node_id in nodes_with_dist[:n]]


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


def dijkstra_to_nearest_station_walk_node(source_walk_node, station_walk_nodes):
    """Run Dijkstra on walk graph from source to the nearest station-linked walk node."""
    if WALK_GRAPH is None or source_walk_node is None or not station_walk_nodes:
        return None, float('inf'), []

    dist = {source_walk_node: 0.0}
    parent = {}
    visited = set()
    heap = [(0.0, source_walk_node)]

    while heap:
        cur_dist, cur = heapq.heappop(heap)
        if cur in visited:
            continue
        visited.add(cur)

        if cur in station_walk_nodes:
            path = [cur]
            while cur in parent:
                cur = parent[cur]
                path.append(cur)
            path.reverse()
            return path[-1], cur_dist, path

        for _, nxt, edge_data in WALK_GRAPH.out_edges(cur, data=True):
            weight = float(edge_data.get('time') or edge_data.get('length') or 1.0)
            nd = cur_dist + weight
            if nd < dist.get(nxt, float('inf')):
                dist[nxt] = nd
                parent[nxt] = cur
                heapq.heappush(heap, (nd, nxt))

    return None, float('inf'), []


def dijkstra_to_k_station_walk_nodes(source_walk_node, station_walk_nodes, k=6):
    """Run Dijkstra on walk graph and return up to k nearest station-linked walk nodes."""
    if WALK_GRAPH is None or source_walk_node is None or not station_walk_nodes:
        return []

    dist = {source_walk_node: 0.0}
    parent = {}
    visited = set()
    heap = [(0.0, source_walk_node)]
    found = []

    while heap and len(found) < k:
        cur_dist, cur = heapq.heappop(heap)
        if cur in visited:
            continue
        visited.add(cur)

        if cur in station_walk_nodes:
            path = [cur]
            p = cur
            while p in parent:
                p = parent[p]
                path.append(p)
            path.reverse()
            found.append((cur, cur_dist, path))

        for _, nxt, edge_data in WALK_GRAPH.out_edges(cur, data=True):
            weight = float(edge_data.get('time') or edge_data.get('length') or 1.0)
            nd = cur_dist + weight
            if nd < dist.get(nxt, float('inf')):
                dist[nxt] = nd
                parent[nxt] = cur
                heapq.heappush(heap, (nd, nxt))

    return found


def pick_station_from_walk_node(walk_node_id, point_lat, point_lng):
    """Pick the most suitable metro station mapped to a walk node."""
    station_ids = WALK_NODE_TO_STATIONS.get(walk_node_id, [])
    if not station_ids:
        return None
    return min(
        station_ids,
        key=lambda sid: euclidean_distance(point_lat, point_lng, NODES_DICT[sid]['lat'], NODES_DICT[sid]['lng'])
    )


def walk_path_to_coords(walk_path):
    """Convert walk-node path to coordinate list for frontend rendering."""
    coords = []
    for node_id in walk_path:
        pos = WALK_COORD_BY_ID.get(node_id)
        if pos is None:
            continue
        coords.append({'lat': pos[0], 'lng': pos[1]})
    return coords

def find_complete_path(point_a, point_b, forbidden_nodes, forbidden_edges, forbidden_zones):
    """
    Find complete path from point A to point B
    Flow: A → nearest station → traverse metro → nearest station to B → B
    """
    source_walk_a = find_nearest_walk_node(point_a['lat'], point_a['lng'])
    source_walk_b = find_nearest_walk_node(point_b['lat'], point_b['lng'])
    station_walk_nodes = set(WALK_NODE_TO_STATIONS.keys())

    best_result = None
    best_walk_total = float('inf')
    best_metro_cost = float('inf')

    # Expand search radius progressively to avoid false no-path when nearest stations
    # belong to disconnected metro components.
    for k in (8, 20, 60):
        start_candidates = dijkstra_to_k_station_walk_nodes(source_walk_a, station_walk_nodes, k=k)
        end_candidates = dijkstra_to_k_station_walk_nodes(source_walk_b, station_walk_nodes, k=k)
        if not start_candidates or not end_candidates:
            continue

        start_station_candidates = []
        for start_walk_station_node, walk_cost_a, walk_path_a in start_candidates:
            start_station = pick_station_from_walk_node(start_walk_station_node, point_a['lat'], point_a['lng'])
            if start_station is None or start_station in forbidden_nodes:
                continue
            start_station_candidates.append((start_station, walk_cost_a, walk_path_a))

        end_station_candidates = []
        for end_walk_station_node, walk_cost_b, walk_path_b in end_candidates:
            end_station = pick_station_from_walk_node(end_walk_station_node, point_b['lat'], point_b['lng'])
            if end_station is None or end_station in forbidden_nodes:
                continue
            end_station_candidates.append((end_station, walk_cost_b, walk_path_b))

        if not start_station_candidates or not end_station_candidates:
            continue

        # Only evaluate pairs in the same connected component of metro graph.
        has_component_overlap = False
        for start_station, walk_cost_a, walk_path_a in start_station_candidates:
            start_comp = METRO_COMPONENT_INDEX.get(start_station)
            if start_comp is None:
                continue
            for end_station, walk_cost_b, walk_path_b in end_station_candidates:
                if METRO_COMPONENT_INDEX.get(end_station) != start_comp:
                    continue
                has_component_overlap = True

                metro_path = a_star_pathfinding(
                    start_station,
                    end_station,
                    NODES_DICT,
                    forbidden_nodes,
                    forbidden_edges,
                    forbidden_zones
                )
                if not metro_path:
                    continue

                metro_cost = 0.0
                for i in range(len(metro_path) - 1):
                    curr = NODES_DICT[metro_path[i]]
                    nxt = NODES_DICT[metro_path[i + 1]]
                    metro_cost += euclidean_distance(curr['lat'], curr['lng'], nxt['lat'], nxt['lng'])

                walk_total = walk_cost_a + walk_cost_b
                # Prioritize nearest access stations by walking distance first,
                # then use metro distance as a tie-breaker.
                if (walk_total < best_walk_total) or (
                    walk_total == best_walk_total and metro_cost < best_metro_cost
                ):
                    best_walk_total = walk_total
                    best_metro_cost = metro_cost
                    best_result = {
                        'start_station': start_station,
                        'end_station': end_station,
                        'metro_path': metro_path,
                        'walk_cost_a': walk_cost_a,
                        'walk_cost_b': walk_cost_b,
                        'walk_path_a_coords': walk_path_to_coords(walk_path_a),
                        'walk_path_b_coords': walk_path_to_coords(walk_path_b),
                        'total_cost': walk_total + metro_cost
                    }

        if best_result is not None:
            return best_result
        if has_component_overlap:
            break

    return best_result

def generate_steps(complete_path_result, point_a, point_b):
    """Generate a simplified station-only route sequence"""
    if not complete_path_result:
        return []
    
    seen = set()
    steps = []
    metro_path = complete_path_result['metro_path']
    for node_id in metro_path:
        station_name = NODES_DICT[node_id]['name']
        if station_name not in seen:
            seen.add(station_name)
            steps.append({'station': station_name})
    return steps

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
        
        # Build response
        path = result['metro_path']
        steps = generate_steps(result, point_a, point_b)
        
        return jsonify({
            'path': path,
            'steps': steps,
            'distance': len(path),
            'walk_path_a': result.get('walk_path_a_coords', []),
            'walk_path_b': result.get('walk_path_b_coords', [])
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
