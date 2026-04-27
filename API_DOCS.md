# 📡 API Documentation - Smart Map Pro

## 🔗 Base URL
```
http://localhost:5000
```

---

## 📍 Public APIs

### 1. GET `/api/graph-data`
**Lấy toàn bộ dữ liệu đồ thị (nodes, edges, cấm hiện tại)**

#### Request
```http
GET /api/graph-data HTTP/1.1
Host: localhost:5000
```

#### Response (200 OK)
```json
{
  "nodes": [
    {
      "id": "node_12345",
      "lat": 59.9311,
      "lng": 30.3609,
      "name": "Nevskiy Prospekt",
      "type": "station"
    }
  ],
  "edges": [
    {
      "from": "node_1",
      "to": "node_2"
    }
  ],
  "forbidden_nodes": ["node_blocked_1"],
  "forbidden_edges": ["node_1-node_2"],
  "forbidden_zones": [
    {
      "center_lat": 59.93,
      "center_lng": 30.36,
      "radius": 0.005
    }
  ]
}
```

#### JavaScript Example
```javascript
fetch('/api/graph-data')
  .then(res => res.json())
  .then(data => {
    console.log(`Loaded ${data.nodes.length} nodes`);
    console.log(`Forbidden nodes: ${data.forbidden_nodes.length}`);
  });
```

---

### 2. POST `/api/find-path`
**Tìm lộ trình từ điểm A đến điểm B**

#### Request
```http
POST /api/find-path HTTP/1.1
Host: localhost:5000
Content-Type: application/json

{
  "pointA": {
    "lat": 59.9311,
    "lng": 30.3609
  },
  "pointB": {
    "lat": 59.9370,
    "lng": 30.3690
  }
}
```

#### Response (200 OK)
```json
{
  "path": ["node_1", "node_2", "node_3", "node_4"],
  "steps": [
    {
      "type": "walk_to_station",
      "station": "Nevskiy Prospekt",
      "lat": 59.9311,
      "lng": 30.3609
    },
    {
      "type": "metro",
      "from": "Nevskiy Prospekt",
      "to": "Gostinyy Dvor",
      "lat": 59.9340,
      "lng": 30.3656,
      "distance": 0.45
    },
    {
      "type": "exit_station",
      "station": "Gostinyy Dvor",
      "lat": 59.9370,
      "lng": 30.3690
    }
  ],
  "cost": 2.5,
  "start_station": "node_1",
  "end_station": "node_3"
}
```

#### Response (404 Not Found)
```json
{
  "error": "No path found"
}
```

#### JavaScript Example
```javascript
const findPath = async (pointA, pointB) => {
  const response = await fetch('/api/find-path', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pointA, pointB })
  });
  
  if (!response.ok) {
    console.error('Path not found');
    return null;
  }
  
  const result = await response.json();
  console.log(`Found path with ${result.steps.length} steps`);
  console.log(`Cost: ${result.cost}`);
  return result;
};

// Usage
findPath(
  { lat: 59.93, lng: 30.36 },
  { lat: 59.94, lng: 30.37 }
);
```

---

## 🔐 Admin APIs

### Authentication
Tất cả admin endpoints yêu cầu:
```json
{
  "password": "123456"
}
```

---

### 3. POST `/api/admin/login`
**Đăng nhập admin**

#### Request
```http
POST /api/admin/login HTTP/1.1
Host: localhost:5000
Content-Type: application/json

{
  "password": "123456"
}
```

#### Response - Success (200 OK)
```json
{
  "success": true,
  "message": "Login successful"
}
```

#### Response - Failure (401 Unauthorized)
```json
{
  "success": false,
  "message": "Invalid password"
}
```

---

### 4. POST `/api/admin/block-node`
**Cấm một ga**

#### Request
```http
POST /api/admin/block-node HTTP/1.1
Host: localhost:5000
Content-Type: application/json

{
  "node_id": "node_12345",
  "password": "123456"
}
```

#### Response (200 OK)
```json
{
  "success": true,
  "node": "node_12345"
}
```

#### JavaScript Example
```javascript
const blockNode = async (nodeId) => {
  const response = await fetch('/api/admin/block-node', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      node_id: nodeId,
      password: '123456'
    })
  });
  
  if (!response.ok) {
    console.error('Failed to block node');
    return;
  }
  
  const result = await response.json();
  console.log(`✓ Blocked node: ${result.node}`);
};
```

---

### 5. POST `/api/admin/unblock-node`
**Hủy cấm một ga**

#### Request
```http
POST /api/admin/unblock-node HTTP/1.1
Host: localhost:5000
Content-Type: application/json

{
  "node_id": "node_12345",
  "password": "123456"
}
```

#### Response (200 OK)
```json
{
  "success": true,
  "node": "node_12345"
}
```

---

### 6. POST `/api/admin/block-edge`
**Cấm một cạnh (tuyến kết nối)**

#### Request
```http
POST /api/admin/block-edge HTTP/1.1
Host: localhost:5000
Content-Type: application/json

{
  "node1": "node_1",
  "node2": "node_2",
  "password": "123456"
}
```

#### Response (200 OK)
```json
{
  "success": true,
  "edge": "node_1-node_2"
}
```

#### Note
- Thứ tự node không quan trọng: `(A→B)` = `(B→A)`
- Hệ thống tự động sắp xếp: `edge_key = sorted([node1, node2]).join('-')`

---

### 7. POST `/api/admin/unblock-edge`
**Hủy cấm một cạnh**

#### Request
```http
POST /api/admin/unblock-edge HTTP/1.1
Host: localhost:5000
Content-Type: application/json

{
  "node1": "node_1",
  "node2": "node_2",
  "password": "123456"
}
```

#### Response (200 OK)
```json
{
  "success": true,
  "edge": "node_1-node_2"
}
```

---

### 8. POST `/api/admin/block-zone`
**Cấm một vùng tròn**

#### Request
```http
POST /api/admin/block-zone HTTP/1.1
Host: localhost:5000
Content-Type: application/json

{
  "center_lat": 59.9311,
  "center_lng": 30.3609,
  "radius": 0.005,
  "password": "123456"
}
```

#### Response (200 OK)
```json
{
  "success": true,
  "zone": {
    "center_lat": 59.9311,
    "center_lng": 30.3609,
    "radius": 0.005
  }
}
```

#### Parameters
- `center_lat`: Vĩ độ tâm vùng (latitude)
- `center_lng`: Kinh độ tâm vùng (longitude)
- `radius`: Bán kính vùng (độ/latitude, ~111km mỗi độ)

#### Conversion
```
1 độ = ~111 km
0.01 độ = ~1.1 km
0.001 độ = ~111 m
```

---

### 9. POST `/api/admin/unblock-zone`
**Hủy cấm một vùng**

#### Request
```http
POST /api/admin/unblock-zone HTTP/1.1
Host: localhost:5000
Content-Type: application/json

{
  "index": 0,
  "password": "123456"
}
```

#### Response (200 OK)
```json
{
  "success": true,
  "zone": {
    "center_lat": 59.9311,
    "center_lng": 30.3609,
    "radius": 0.005
  }
}
```

#### Parameters
- `index`: Chỉ mục vùng trong danh sách (bắt đầu từ 0)

---

### 10. POST `/api/admin/reset`
**Xóa tất cả cấm**

#### Request
```http
POST /api/admin/reset HTTP/1.1
Host: localhost:5000
Content-Type: application/json

{
  "password": "123456"
}
```

#### Response (200 OK)
```json
{
  "success": true,
  "message": "All restrictions removed"
}
```

#### Note
- Xóa toàn bộ nodes bị cấm
- Xóa toàn bộ edges bị cấm
- Xóa toàn bộ zones bị cấm
- Trạng thái được lưu vào `app_state.json`

---

## 🔄 Complete Workflow Example

### Scenario: Tìm lộ trình và cấm ga

```javascript
// 1. Tìm lộ trình từ A đến B
const result = await fetch('/api/find-path', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    pointA: { lat: 59.93, lng: 30.36 },
    pointB: { lat: 59.94, lng: 30.37 }
  })
}).then(r => r.json());

console.log('Path:', result.path);
// Output: ["node_1", "node_2", "node_3"]

// 2. Admin login
const login = await fetch('/api/admin/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ password: '123456' })
}).then(r => r.json());

console.log(login.success); // true

// 3. Block node_2
const block = await fetch('/api/admin/block-node', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    node_id: 'node_2',
    password: '123456'
  })
}).then(r => r.json());

console.log('Blocked:', block.node);

// 4. Tìm lộ trình lại (sẽ khác)
const result2 = await fetch('/api/find-path', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    pointA: { lat: 59.93, lng: 30.36 },
    pointB: { lat: 59.94, lng: 30.37 }
  })
}).then(r => r.json());

console.log('New path:', result2.path);
// Output: ["node_1", "node_4", "node_5", "node_3"]
// node_2 bị bỏ qua vì bị cấm
```

---

## ⚠️ Error Handling

### 400 Bad Request
```json
{
  "error": "Missing coordinates"
}
```
**Nguyên nhân:** Thiếu tham số hoặc tham số không hợp lệ

### 401 Unauthorized
```json
{
  "error": "Unauthorized"
}
```
**Nguyên nhân:** Mật khẩu sai hoặc không có quyền

### 404 Not Found
```json
{
  "error": "No path found"
}
```
**Nguyên nhân:** Không tìm thấy lộ trình (quá nhiều cấm, v.v.)

### 500 Internal Server Error
```json
{
  "error": "Graph not loaded"
}
```
**Nguyên nhân:** Lỗi server (file không tìm thấy, v.v.)

---

## 📊 Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad Request |
| 401 | Unauthorized |
| 404 | Not Found |
| 500 | Internal Server Error |

---

## 🧪 Testing with cURL

### Test find-path
```bash
curl -X POST http://localhost:5000/api/find-path \
  -H "Content-Type: application/json" \
  -d '{
    "pointA": {"lat": 59.93, "lng": 30.36},
    "pointB": {"lat": 59.94, "lng": 30.37}
  }'
```

### Test block-node
```bash
curl -X POST http://localhost:5000/api/admin/block-node \
  -H "Content-Type: application/json" \
  -d '{
    "node_id": "node_12345",
    "password": "123456"
  }'
```

### Test block-zone
```bash
curl -X POST http://localhost:5000/api/admin/block-zone \
  -H "Content-Type: application/json" \
  -d '{
    "center_lat": 59.9311,
    "center_lng": 30.3609,
    "radius": 0.005,
    "password": "123456"
  }'
```

---

## 📝 Response Data Structure

### Node Object
```json
{
  "id": "node_12345",
  "lat": 59.9311,
  "lng": 30.3609,
  "name": "Nevskiy Prospekt",
  "type": "station"
}
```

### Edge Object
```json
{
  "from": "node_1",
  "to": "node_2"
}
```

### Step Object
```json
{
  "type": "metro",  // "walk_to_station", "exit_station", "metro"
  "from": "Station A",
  "to": "Station B",
  "lat": 59.934,
  "lng": 30.366,
  "distance": 0.45
}
```

### Zone Object
```json
{
  "center_lat": 59.9311,
  "center_lng": 30.3609,
  "radius": 0.005
}
```

---

## 🚀 Performance Tips

1. **Cache graph data**: Gọi `/api/graph-data` một lần khi khởi động
2. **Batch requests**: Gửi nhiều block request cùng lúc
3. **Connection pooling**: Tái sử dụng HTTP connections
4. **Error recovery**: Implement retry logic cho thất bại

---

## 📚 Additional Resources

- [README.md](README.md) - Hướng dẫn tổng quan
- [ADMIN_GUIDE.md](ADMIN_GUIDE.md) - Chi tiết chế độ admin
- [main.py](main.py) - Source code server
- [index.html](index.html) - Source code frontend

---

**Last Updated:** 2024
**Version:** 1.0
