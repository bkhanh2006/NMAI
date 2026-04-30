# Edge Endpoint Blocking Implementation Summary

## Date Implemented
April 28, 2026

## User Requirement
Vietnamese clarification provided by user:
- **Forbidden zones**: "vùng cấm là vùng mà đi bộ hay đi tàu đều không thể động đến đó"
  - Translation: "A forbidden zone is where you cannot walk or take metro"
  - Status: ✓ Already implemented via edge geometry intersection checks
  
- **Forbidden edges**: "cạnh cấm thì nó sẽ cấm tất cả các ga và đường trong cạnh đó kể cả đó là 2 ga ở biên"
  - Translation: "A forbidden edge blocks all stations and paths in that edge, INCLUDING the 2 endpoint stations"
  - Status: ✓ NEWLY IMPLEMENTED

## Changes Made

### File: main.py

#### 1. Modified `AppState.block_edge()` method (line ~950)
**What changed:**
- Added code to mark both endpoint stations as forbidden when an edge is blocked
- Now: `self.forbidden_nodes.add(node1)` and `self.forbidden_nodes.add(node2)`

**Before:**
```python
def block_edge(self, node1, node2):
    """Block an edge"""
    route = build_metro_edge_route(node1, node2)
    # ... blocked edge path ...
    # (no endpoint blocking)
```

**After:**
```python
def block_edge(self, node1, node2):
    """Block an edge and its endpoint stations"""
    route = build_metro_edge_route(node1, node2)
    # ... blocked edge path ...
    
    # Block the 2 endpoint stations as per user requirement:
    # "cấm tất cả các ga và đường trong cạnh đó kể cả đó là 2 ga ở biên"
    self.forbidden_nodes.add(node1)
    self.forbidden_nodes.add(node2)
```

#### 2. Modified `AppState.unblock_edge()` method (line ~915)
**What changed:**
- Added smart logic to remove endpoint stations from forbidden_nodes
- BUT only if no other blocked edges have those stations as endpoints
- This prevents accidentally unblocking a station that's blocked by another edge

**New code:**
```python
# Remove endpoint stations from forbidden_nodes ONLY if no other edges block them
for endpoint in [node1, node2]:
    # Check if any remaining forbidden edge has this node as an endpoint
    other_edge_blocks_endpoint = any(
        route['start'] == endpoint or route['end'] == endpoint
        for route in self.forbidden_edge_routes
    )
    if not other_edge_blocks_endpoint:
        self.forbidden_nodes.discard(endpoint)
```

## Test Results

### Test File: test_edge_blocking_clean.py
**Run on:** April 28, 2026, 18:23 UTC

#### TEST 1: Blocking Edge
```
Stations tested:
  - Station 1: Admiralteyskaya (ID: 0)
  - Station 2: Akademicheskaya (ID: 1)

Result:
  - Block response: success: true
  - Forbidden nodes after blocking: ['0', '1']
  - [SUCCESS] Both endpoint stations are now forbidden!
```

#### TEST 2: Unblocking Edge
```
Result:
  - Unblock response: success: true
  - Forbidden nodes after unblocking: []
  - [SUCCESS] Endpoint stations correctly removed!
```

#### TEST 3: Multiple Edges with Shared Endpoint
```
Scenario:
  - Edge 1: Station 0 -> Station 1
  - Edge 2: Station 0 -> Station 2
  (Station 0 is shared)

Result:
  - After blocking both edges: Forbidden nodes = ['0', '1', '2']
  - After unblocking first edge: Forbidden nodes = ['0', '2']
    [SUCCESS] Endpoint kept forbidden (other edge still blocks it)
  - After unblocking second edge: Forbidden nodes = []
    [SUCCESS] Endpoint now removed (no edges block it)
```

## Verification
✓ Edge endpoints are added to forbidden_nodes when edge is blocked
✓ Edge endpoints are removed from forbidden_nodes when edge is unblocked
✓ Smart removal logic: doesn't unblock endpoints if other edges still block them
✓ All API calls successful (HTTP 200)
✓ Multiple edge scenarios handled correctly

## Semantic Alignment
The implementation now correctly reflects the user's requirements:
- **Zones**: Block both walk and metro paths (via geometry intersection checks)
  - ✓ Implemented and tested previously
- **Edges**: Block the edge path PLUS the two endpoint stations
  - ✓ NEWLY IMPLEMENTED AND TESTED

## Impact
- Users can now block edges and automatically prevent routing through those endpoints
- The system prevents accidentally unblocking endpoints when another edge still needs them blocked
- Matches the user's stated intent: "cấp tất cả các ga và đường trong cạnh đó kể cả đó là 2 ga ở biên"

## API Endpoints
All existing endpoints continue to work:
- `/api/admin/block-edge` - Now blocks edge + endpoints
- `/api/admin/unblock-edge` - Smartly removes endpoint blocking
- `/api/admin/block-node` - Unchanged
- `/api/admin/unblock-node` - Unchanged
- `/api/admin/block-zone` - Unchanged
- `/api/admin/unblock-zone` - Unchanged

## Server Status
✓ Flask server running at http://localhost:5000
✓ All graph data loaded (74 metro stations, 417,703 walk nodes)
✓ Ready for UI testing
