#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Standalone debug viewer for metro stations and station-to-station connections.
This file is independent from main.py and can be deleted safely.
"""

import os
import ast
import json
import networkx as nx
from flask import Flask, jsonify, render_template_string

app = Flask(__name__)

METRO_GRAPH_PATH = os.path.join("graph", "spd_metro.graphml")


def _to_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def _normalize_coords(node_data):
    # Metro graph is expected to already store geographic coords.
    lat = _to_float(node_data.get("lat", node_data.get("y", 0.0)))
    lng = _to_float(node_data.get("lng", node_data.get("x", 0.0)))

    # If lat/lng appear swapped, fix conservatively.
    if abs(lat) > 90 and abs(lng) <= 90:
        lat, lng = lng, lat

    return lat, lng


def _parse_geometry_coords(value):
    if value is None:
        return []

    parsed = value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
        except Exception:
            try:
                parsed = ast.literal_eval(text)
            except Exception:
                return []

    if not isinstance(parsed, (list, tuple)):
        return []

    coords = []
    for item in parsed:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        lat = _to_float(item[0], None)
        lng = _to_float(item[1], None)
        if lat is None or lng is None:
            continue

        # Fix likely swapped coords.
        if abs(lat) > 90 and abs(lng) <= 90:
            lat, lng = lng, lat

        # Keep only plausible geographic coordinates.
        if abs(lat) <= 90 and abs(lng) <= 180:
            coords.append([lat, lng])

    return coords


def load_metro_graph_payload():
    if not os.path.exists(METRO_GRAPH_PATH):
        raise FileNotFoundError(f"Missing metro graph: {METRO_GRAPH_PATH}")

    graph = nx.read_graphml(METRO_GRAPH_PATH)

    nodes = []
    node_lookup = {}
    station_shape_keys = {"geometry", "geom", "wkt", "shape", "polygon", "coordinates"}
    station_nodes_with_shape = 0
    for node_id, data in graph.nodes(data=True):
        lat, lng = _normalize_coords(data)
        if any(k.lower() in station_shape_keys or "geom" in k.lower() or "wkt" in k.lower() for k in data.keys()):
            station_nodes_with_shape += 1
        node = {
            "id": str(node_id),
            "name": str(data.get("name", node_id)),
            "lat": lat,
            "lng": lng,
            "type": str(data.get("type", "station")),
        }
        nodes.append(node)
        node_lookup[str(node_id)] = node

    edges = []
    edge_with_geometry_attr = 0
    edge_with_geometry_parsed = 0
    edge_with_shape_points_gt2 = 0
    for u, v, data in graph.edges(data=True):
        u_id = str(u)
        v_id = str(v)
        if u_id not in node_lookup or v_id not in node_lookup:
            continue

        if data.get("geometry_coords") is not None:
            edge_with_geometry_attr += 1
        geometry_coords = _parse_geometry_coords(data.get("geometry_coords"))
        if len(geometry_coords) >= 2:
            edge_with_geometry_parsed += 1
        if len(geometry_coords) > 2:
            edge_with_shape_points_gt2 += 1
        if len(geometry_coords) < 2:
            geometry_coords = [
                [node_lookup[u_id]["lat"], node_lookup[u_id]["lng"]],
                [node_lookup[v_id]["lat"], node_lookup[v_id]["lng"]],
            ]

        edges.append(
            {
                "from": u_id,
                "to": v_id,
                "type": str(data.get("type", "metro")),
                "line": str(data.get("line", "")),
                "coords": geometry_coords,
                "geometry_point_count": len(geometry_coords),
            }
        )

    lat_values = [n["lat"] for n in nodes] or [59.93]
    lng_values = [n["lng"] for n in nodes] or [30.33]

    return {
        "stats": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "edges_with_geometry_attr": edge_with_geometry_attr,
            "edges_with_geometry_parsed": edge_with_geometry_parsed,
            "edges_with_shape_points_gt2": edge_with_shape_points_gt2,
            "station_nodes_with_shape": station_nodes_with_shape,
            "lat_min": min(lat_values),
            "lat_max": max(lat_values),
            "lng_min": min(lng_values),
            "lng_max": max(lng_values),
        },
        "nodes": nodes,
        "edges": edges,
    }


@app.route("/api/debug/metro")
def api_debug_metro():
    payload = load_metro_graph_payload()
    return jsonify(payload), 200


@app.route("/")
def debug_map_page():
    html = """
<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Metro Debug Viewer</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    :root {
      --bg: #0b1020;
      --panel: #141b34;
      --text: #e9eefc;
      --muted: #9db0df;
      --metro: #0e6efc;
      --edge: #ff8a00;
      --ok: #2ecc71;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      display: grid;
      grid-template-columns: 340px 1fr;
      height: 100vh;
    }
    #sidebar {
      background: linear-gradient(180deg, #121a33, #0f162d);
      border-right: 1px solid #24345f;
      padding: 16px;
      overflow: auto;
    }
    h1 {
      margin: 0 0 8px;
      font-size: 20px;
      font-weight: 800;
      letter-spacing: 0.3px;
    }
    .sub {
      margin: 0 0 14px;
      color: var(--muted);
      font-size: 13px;
    }
    .card {
      border: 1px solid #2a3e71;
      border-radius: 12px;
      padding: 12px;
      margin-bottom: 12px;
      background: rgba(23, 35, 67, 0.65);
    }
    .stat {
      display: flex;
      justify-content: space-between;
      padding: 6px 0;
      border-bottom: 1px dashed #2a3e71;
      font-size: 13px;
    }
    .stat:last-child { border-bottom: 0; }
    .controls label {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 14px;
      margin: 6px 0;
      cursor: pointer;
    }
    .legend {
      display: grid;
      grid-template-columns: 14px 1fr;
      gap: 8px;
      align-items: center;
      margin: 8px 0;
      font-size: 13px;
      color: var(--muted);
    }
    .dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
    }
    .line {
      height: 4px;
      border-radius: 2px;
    }
    #map { width: 100%; height: 100%; }
    .ok {
      color: var(--ok);
      font-size: 12px;
      margin-top: 8px;
    }
    code {
      background: #0f152b;
      border: 1px solid #2a3e71;
      border-radius: 6px;
      padding: 2px 6px;
      color: #cdd9ff;
      font-size: 12px;
    }
  </style>
</head>
<body>
  <aside id="sidebar">
    <h1>Metro Debug Viewer</h1>
    <p class="sub">Sơ đồ ga và tuyến metro theo geometry thật (bản độc lập, có thể xóa).</p>

    <div class="card">
      <div class="stat"><span>Nodes</span><strong id="node-count">-</strong></div>
      <div class="stat"><span>Edges</span><strong id="edge-count">-</strong></div>
      <div class="stat"><span>Edges Có geometry_attr</span><strong id="edge-geom-attr">-</strong></div>
      <div class="stat"><span>Edges parse được geometry</span><strong id="edge-geom-parsed">-</strong></div>
      <div class="stat"><span>Edges có >2 điểm</span><strong id="edge-geom-curvy">-</strong></div>
      <div class="stat"><span>Ga có shape polygon</span><strong id="station-shape-count">-</strong></div>
      <div class="stat"><span>Lat Range</span><strong id="lat-range">-</strong></div>
      <div class="stat"><span>Lng Range</span><strong id="lng-range">-</strong></div>
    </div>

    <div class="card controls">
      <label><input type="checkbox" id="toggle-stations" checked /> Hiện ga</label>
      <label><input type="checkbox" id="toggle-edges" checked /> Hiện cạnh kết nối</label>
      <label><input type="checkbox" id="toggle-labels" /> Hiện tên ga</label>
      <p class="ok" id="status">Đang tải dữ liệu...</p>
    </div>

    <div class="card">
      <div class="legend"><div class="dot" style="background:#0e6efc"></div><div>Ga tàu điện</div></div>
      <div class="legend"><div class="line" style="background:#ff8a00"></div><div>Đường kết nối giữa ga</div></div>
    </div>

    <div class="card">
      <div style="font-size:13px; color:var(--muted); line-height:1.4;">
        API debug: <code>/api/debug/metro</code>
      </div>
    </div>
  </aside>

  <div id="map"></div>

  <script>
    const map = L.map('map').setView([59.93, 30.33], 11);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '© OpenStreetMap'
    }).addTo(map);

    let stationLayer = L.layerGroup().addTo(map);
    let edgeLayer = L.layerGroup().addTo(map);
    let labelLayer = L.layerGroup();

    function setStats(stats) {
      document.getElementById('node-count').textContent = stats.node_count;
      document.getElementById('edge-count').textContent = stats.edge_count;
      document.getElementById('edge-geom-attr').textContent = stats.edges_with_geometry_attr;
      document.getElementById('edge-geom-parsed').textContent = stats.edges_with_geometry_parsed;
      document.getElementById('edge-geom-curvy').textContent = stats.edges_with_shape_points_gt2;
      document.getElementById('station-shape-count').textContent = stats.station_nodes_with_shape;
      document.getElementById('lat-range').textContent = `${stats.lat_min.toFixed(4)} .. ${stats.lat_max.toFixed(4)}`;
      document.getElementById('lng-range').textContent = `${stats.lng_min.toFixed(4)} .. ${stats.lng_max.toFixed(4)}`;
    }

    function bindControls() {
      document.getElementById('toggle-stations').addEventListener('change', (e) => {
        if (e.target.checked) map.addLayer(stationLayer);
        else map.removeLayer(stationLayer);
      });
      document.getElementById('toggle-edges').addEventListener('change', (e) => {
        if (e.target.checked) map.addLayer(edgeLayer);
        else map.removeLayer(edgeLayer);
      });
      document.getElementById('toggle-labels').addEventListener('change', (e) => {
        if (e.target.checked) map.addLayer(labelLayer);
        else map.removeLayer(labelLayer);
      });
    }

    async function loadDebugMap() {
      try {
        const res = await fetch('/api/debug/metro');
        const data = await res.json();

        setStats(data.stats);
        stationLayer.clearLayers();
        edgeLayer.clearLayers();
        labelLayer.clearLayers();

        const bounds = [];

        for (const edge of data.edges) {
          const line = L.polyline(edge.coords, {
            color: '#ff8a00',
            weight: 2,
            opacity: 0.65
          }).bindPopup(
            `<b>${edge.from}</b> ➜ <b>${edge.to}</b><br/>line: ${edge.line || '-'}<br/>points: ${edge.geometry_point_count}`
          );
          edgeLayer.addLayer(line);
        }

        for (const node of data.nodes) {
          const marker = L.circleMarker([node.lat, node.lng], {
            radius: 4,
            color: '#0e6efc',
            fillColor: '#0e6efc',
            fillOpacity: 0.9,
            weight: 1
          }).bindPopup(`<b>${node.name}</b><br>ID: ${node.id}`);

          stationLayer.addLayer(marker);
          bounds.push([node.lat, node.lng]);

          const label = L.marker([node.lat, node.lng], {
            icon: L.divIcon({
              className: 'station-label',
              html: `<div style="font-size:10px;color:#dbe6ff;text-shadow:0 0 3px #000;white-space:nowrap">${node.name}</div>`
            })
          });
          labelLayer.addLayer(label);
        }

        if (bounds.length) {
          map.fitBounds(bounds, { padding: [20, 20] });
        }

        document.getElementById('status').textContent = 'Tải xong dữ liệu debug.';
      } catch (err) {
        document.getElementById('status').textContent = `Lỗi: ${err.message}`;
      }
    }

    bindControls();
    loadDebugMap();
  </script>
</body>
</html>
    """
    return render_template_string(html)


if __name__ == "__main__":
    print("[DEBUG] Metro viewer on http://127.0.0.1:5050")
    app.run(host="127.0.0.1", port=5050, debug=False)
