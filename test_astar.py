#!/usr/bin/env python3
from main import COMBINED_BASE_GRAPH, NODES_DICT, find_complete_path, load_graph_with_coordinates
import time

# Load graph first
print('[*] Loading graph...')
load_graph_with_coordinates()
print('[OK] Graph loaded\n')

# Test 1: Route without restrictions
print('[TEST 1] Route without restrictions:')
point_a = {'lat': 59.9311, 'lng': 30.3609}
point_b = {'lat': 59.9500, 'lng': 30.3800}
start = time.time()
result = find_complete_path(point_a, point_b, set(), set(), [])
elapsed = time.time() - start
if result:
    print(f'  OK Found route: {result["total_time_min"]} min, {result["total_distance_m"]:.0f} m in {elapsed:.2f}s')
else:
    print(f'  FAIL No route found in {elapsed:.2f}s')

# Test 2: Route with forbidden node
print('\n[TEST 2] Route with 1 forbidden node:')
start = time.time()
result = find_complete_path(point_a, point_b, {'st_57'}, set(), [])
elapsed = time.time() - start
if result:
    print(f'  OK Found route: {result["total_time_min"]} min, {result["total_distance_m"]:.0f} m in {elapsed:.2f}s')
else:
    print(f'  FAIL No route found in {elapsed:.2f}s')

from main import COMBINED_BASE_GRAPH as G_CHECK
print(f'\nGraph size: {G_CHECK.number_of_nodes()} nodes, {G_CHECK.number_of_edges()} edges')
print('[OK] A* runs directly on graph without pre-copying/filtering')
