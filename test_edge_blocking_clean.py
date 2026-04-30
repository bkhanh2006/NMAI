#!/usr/bin/env python3
"""Test script to verify edge endpoint blocking implementation"""

import requests
import json

# Get graph data to find two stations
response = requests.get('http://localhost:5000/api/graph-data')
data = response.json()

# Get first two stations
stations = data['station_nodes'][:2]
print(f'Testing edge blocking between:')
print(f'  Station 1: {stations[0]["name"]} (ID: {stations[0]["id"]})')
print(f'  Station 2: {stations[1]["name"]} (ID: {stations[1]["id"]})')

# Test 1: Block the edge (with password in the request body)
print(f'\n--- TEST 1: Blocking edge ---')
block_data = {
    'node1': stations[0]['id'],
    'node2': stations[1]['id'],
    'password': '123456'
}
block_response = requests.post('http://localhost:5000/api/admin/block-edge', json=block_data)
print(f'Block response: {json.dumps(block_response.json(), indent=2)}')

# Get updated graph to check forbidden_nodes
updated = requests.get('http://localhost:5000/api/graph-data').json()
print(f'\nForbidden nodes after blocking edge: {updated["forbidden_nodes"]}')
print(f'Forbidden edges count: {len(updated["forbidden_edges"])}')
print(f'Expected nodes to be blocked: {stations[0]["id"]} and {stations[1]["id"]}')

# Check if the endpoint stations are now forbidden
node1_forbidden = stations[0]['id'] in updated['forbidden_nodes']
node2_forbidden = stations[1]['id'] in updated['forbidden_nodes']

print(f'\n--- VERIFICATION ---')
print(f'Station 1 ({stations[0]["id"]}) forbidden: {node1_forbidden}')
print(f'Station 2 ({stations[1]["id"]}) forbidden: {node2_forbidden}')

if node1_forbidden and node2_forbidden:
    print('\n[SUCCESS] Both endpoint stations are now forbidden!')
else:
    print('\n[FAIL] Endpoint stations not correctly forbidden')
    print(f'  Expected both to be in forbidden_nodes')
    print(f'  Actual forbidden_nodes: {updated["forbidden_nodes"]}')

# Test 2: Test unblocking edge
print(f'\n--- TEST 2: Unblocking edge ---')
unblock_data = {
    'node1': stations[0]['id'],
    'node2': stations[1]['id'],
    'password': '123456'
}
unblock_response = requests.post('http://localhost:5000/api/admin/unblock-edge', json=unblock_data)
print(f'Unblock response: {json.dumps(unblock_response.json(), indent=2)}')

# Verify nodes are removed from forbidden_nodes
updated2 = requests.get('http://localhost:5000/api/graph-data').json()
print(f'\nForbidden nodes after unblocking edge: {updated2["forbidden_nodes"]}')

if stations[0]['id'] not in updated2['forbidden_nodes'] and stations[1]['id'] not in updated2['forbidden_nodes']:
    print('[SUCCESS] Endpoint stations correctly removed from forbidden_nodes!')
else:
    print('[FAIL] Endpoint stations still in forbidden_nodes after unblocking')

# Test 3: Test multiple edges with shared endpoint
print(f'\n--- TEST 3: Multiple edges with shared endpoint ---')
# Get a third station to create another edge sharing an endpoint
station3 = data['station_nodes'][2] if len(data['station_nodes']) > 2 else None
if station3:
    print(f'Testing edges with shared endpoint:')
    print(f'  Edge 1: {stations[0]["id"]} -> {stations[1]["id"]}')
    print(f'  Edge 2: {stations[0]["id"]} -> {station3["id"]}')
    
    # Block first edge
    block1 = requests.post('http://localhost:5000/api/admin/block-edge', 
        json={'node1': stations[0]['id'], 'node2': stations[1]['id'], 'password': '123456'})
    
    # Block second edge (shares endpoint 0)
    block2 = requests.post('http://localhost:5000/api/admin/block-edge',
        json={'node1': stations[0]['id'], 'node2': station3['id'], 'password': '123456'})
    
    updated3 = requests.get('http://localhost:5000/api/graph-data').json()
    print(f'\nForbidden nodes after blocking both edges: {updated3["forbidden_nodes"]}')
    
    # Unblock first edge
    unblock1 = requests.post('http://localhost:5000/api/admin/unblock-edge',
        json={'node1': stations[0]['id'], 'node2': stations[1]['id'], 'password': '123456'})
    
    updated4 = requests.get('http://localhost:5000/api/graph-data').json()
    print(f'After unblocking first edge: {updated4["forbidden_nodes"]}')
    
    if stations[0]['id'] in updated4['forbidden_nodes']:
        print('[SUCCESS] Endpoint correctly kept forbidden (other edge still blocks it)')
    else:
        print('[FAIL] Endpoint removed but other edge still blocks it')
    
    # Unblock second edge
    unblock2 = requests.post('http://localhost:5000/api/admin/unblock-edge',
        json={'node1': stations[0]['id'], 'node2': station3['id'], 'password': '123456'})
    
    updated5 = requests.get('http://localhost:5000/api/graph-data').json()
    print(f'After unblocking second edge: {updated5["forbidden_nodes"]}')
    
    if stations[0]['id'] not in updated5['forbidden_nodes']:
        print('[SUCCESS] Endpoint now removed (no edges block it)')
    else:
        print('[FAIL] Endpoint still forbidden')

print('\n--- TEST COMPLETE ---')
