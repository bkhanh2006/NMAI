#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Standalone debug viewer for spd_metro_last.graphml.
It filters metro nodes/edges and visualizes them on a map.
This file is independent from the main app and can be deleted safely.
"""

import os
import networkx as nx
from flask import Flask, jsonify, render_template_string

app = Flask(__name__)

GRAPH_PATH = os.path.join("graph", "spd_metro_last.graphml")


def _to_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def _to_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "metro"}


def _normalize_coords(node_data):
    lat = _to_float(node_data.get("lat", node_data.get("y", 0.0)))
    lng = _to_float(node_data.get("lng", node_data.get("x", 0.0)))

    # Fix likely swapped coordinates.
    if abs(lat) > 90 and abs(lng) <= 90:
        lat, lng = lng, lat

    return lat, lng


def _is_metro_node(data):
    node_type = str(data.get("type", "")).strip().lower()
    mode = str(data.get("mode", "")).strip().lower()
    transport = str(data.get("transport", "")).strip().lower()
    is_station = _to_bool(data.get("is_metro_station"))

    if is_station:
        return True
    if node_type in {"metro", "station", "metro_station"}:
        return True
    if mode == "metro" or transport == "metro":
        return True
    return False


def _is_metro_edge(data):
    edge_type = str(data.get("type", "")).strip().lower()
    mode = str(data.get("mode", "")).strip().lower()
    transport = str(data.get("transport", "")).strip().lower()
    line = str(data.get("line", "")).strip()

    if edge_type == "metro":
        return True
    if mode == "metro" or transport == "metro":
        return True
    # In many metro exports, metro edges carry line info.
    if line:
        return True
    return False


def load_metro_filtered_payload():
    if not os.path.exists(GRAPH_PATH):
        raise FileNotFoundError(f"Missing graph file: {GRAPH_PATH}")

    graph = nx.read_graphml(GRAPH_PATH)

    metro_node_ids = set()
    for node_id, node_data in graph.nodes(data=True):
        if _is_metro_node(node_data):
            metro_node_ids.add(str(node_id))

    metro_edges_raw = []
    for u, v, edge_data in graph.edges(data=True):
        if _is_metro_edge(edge_data):
            u_id = str(u)
            v_id = str(v)
            metro_edges_raw.append((u_id, v_id, edge_data))
            metro_node_ids.add(u_id)
            metro_node_ids.add(v_id)

    nodes = []
    node_lookup = {}
    for node_id, node_data in graph.nodes(data=True):
        sid = str(node_id)
        if sid not in metro_node_ids:
            continue
        lat, lng = _normalize_coords(node_data)
        node = {
            "id": sid,
            "name": str(node_data.get("name", sid)),
            "lat": lat,
            "lng": lng,
            "type": str(node_data.get("type", "")),
            "is_metro_station": _to_bool(node_data.get("is_metro_station")),
        }
        nodes.append(node)
        node_lookup[sid] = node

    edges = []
    for u_id, v_id, edge_data in metro_edges_raw:
        if u_id not in node_lookup or v_id not in node_lookup:
            continue
        edges.append(
            {
                "from": u_id,
                "to": v_id,
                "type": str(edge_data.get("type", "")),
                "line": str(edge_data.get("line", "")),
                "length": _to_float(edge_data.get("length", 0.0)),
                "coords": [
                    [node_lookup[u_id]["lat"], node_lookup[u_id]["lng"]],
                    [node_lookup[v_id]["lat"], node_lookup[v_id]["lng"]],
                ],
            }
        )

    lat_values = [n["lat"] for n in nodes] or [59.93]
    lng_values = [n["lng"] for n in nodes] or [30.33]

    return {
        "stats": {
            "source_file": GRAPH_PATH,
            "raw_node_count": graph.number_of_nodes(),
            "raw_edge_count": graph.number_of_edges(),
            "metro_node_count": len(nodes),
            "metro_edge_count": len(edges),
            "lat_min": min(lat_values),
            "lat_max": max(lat_values),
            "lng_min": min(lng_values),
            "lng_max": max(lng_values),
        },
        "nodes": nodes,
        "edges": edges,
    }


@app.route("/api/debug/metro-last")
def api_debug_metro_last():
    payload = load_metro_filtered_payload()
    return jsonify(payload), 200


@app.route("/")
def debug_map_page():
    html = """
<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Metro Last Debug Viewer</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    :root {
      --bg: #0f1627;
      --panel: #161f35;
      --text: #eef3ff;
      --muted: #a6b7de;
      --node: #25a4ff;
      --edge: #ff8a00;
      --ok: #31d17c;
      --danger: #ff6b6b;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", Arial, sans-serif;
      color: var(--text);
      background: radial-gradient(circle at top left, #1d2a48, #0c1221 60%);
      display: grid;
      grid-template-columns: 360px 1fr;
      height: 100vh;
    }
    #sidebar {
      border-right: 1px solid #2b3e69;
      background: linear-gradient(180deg, rgba(23, 34, 60, 0.95), rgba(14, 21, 40, 0.98));
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
      line-height: 1.45;
    }
    .card {
      border: 1px solid #2b3e69;
      border-radius: 12px;
      padding: 12px;
      margin-bottom: 12px;
      background: rgba(20, 31, 53, 0.65);
    }
    .stat {
      display: flex;
      justify-content: space-between;
      padding: 6px 0;
      border-bottom: 1px dashed #2b3e69;
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
    #status { font-size: 12px; margin-top: 8px; }
    .ok { color: var(--ok); }
    .err { color: var(--danger); }
    code {
      background: #0f152b;
      border: 1px solid #2a3e71;
      border-radius: 6px;
      padding: 2px 6px;
      color: #cdd9ff;
      font-size: 12px;
      word-break: break-all;
    }
  </style>
</head>
<body>
  <aside id="sidebar">
    <h1>Metro Last Debug Viewer</h1>
    <p class="sub">Đọc <b>spd_metro_last.graphml</b>, lọc node/cạnh metro và vẽ sơ đồ để kiểm tra dữ liệu.</p>

    <div class="card">
      <div class="stat"><span>Raw Nodes</span><strong id="raw-node-count">-</strong></div>
      <div class="stat"><span>Raw Edges</span><strong id="raw-edge-count">-</strong></div>
      <div class="stat"><span>Metro Nodes</span><strong id="metro-node-count">-</strong></div>
      <div class="stat"><span>Metro Edges</span><strong id="metro-edge-count">-</strong></div>
      <div class="stat"><span>Lat Range</span><strong id="lat-range">-</strong></div>
      <div class="stat"><span>Lng Range</span><strong id="lng-range">-</strong></div>
    </div>

    <div class="card controls">
      <label><input type="checkbox" id="toggle-stations" checked /> Hiện node metro</label>
      <label><input type="checkbox" id="toggle-edges" checked /> Hiện cạnh metro</label>
      <label><input type="checkbox" id="toggle-labels" /> Hiện tên ga</label>
      <div id="status" class="ok">Đang tải dữ liệu...</div>
    </div>

    <div class="card">
      <div class="legend"><div class="dot" style="background:#25a4ff"></div><div>Node metro</div></div>
      <div class="legend"><div class="line" style="background:#ff8a00"></div><div>Cạnh metro</div></div>
    </div>

    <div class="card" style="font-size:13px;color:var(--muted);line-height:1.45;">
      API: <code>/api/debug/metro-last</code><br/>
      Source: <code id="source-file">-</code>
    </div>
  </aside>

  <div id="map"></div>

  <script>
    const map = L.map('map').setView([59.93, 30.33], 11);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '© OpenStreetMap'
    }).addTo(map);

    const stationLayer = L.layerGroup().addTo(map);
    const edgeLayer = L.layerGroup().addTo(map);
    const labelLayer = L.layerGroup();

    function setStats(stats) {
      document.getElementById('raw-node-count').textContent = stats.raw_node_count;
      document.getElementById('raw-edge-count').textContent = stats.raw_edge_count;
      document.getElementById('metro-node-count').textContent = stats.metro_node_count;
      document.getElementById('metro-edge-count').textContent = stats.metro_edge_count;
      document.getElementById('lat-range').textContent = `${stats.lat_min.toFixed(4)} .. ${stats.lat_max.toFixed(4)}`;
      document.getElementById('lng-range').textContent = `${stats.lng_min.toFixed(4)} .. ${stats.lng_max.toFixed(4)}`;
      document.getElementById('source-file').textContent = stats.source_file;
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

    function setStatus(text, isError = false) {
      const el = document.getElementById('status');
      el.textContent = text;
      el.className = isError ? 'err' : 'ok';
    }

    async function loadDebugMap() {
      try {
        const res = await fetch('/api/debug/metro-last');
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        const data = await res.json();

        setStats(data.stats);
        stationLayer.clearLayers();
        edgeLayer.clearLayers();
        labelLayer.clearLayers();

        const bounds = [];

        for (const edge of data.edges) {
          const poly = L.polyline(edge.coords, {
            color: '#ff8a00',
            weight: 2,
            opacity: 0.68
          }).bindPopup(
            `<b>${edge.from}</b> ➜ <b>${edge.to}</b><br/>type: ${edge.type || '-'}<br/>line: ${edge.line || '-'}<br/>length: ${edge.length.toFixed(2)}`
          );
          edgeLayer.addLayer(poly);
        }

        for (const node of data.nodes) {
          const marker = L.circleMarker([node.lat, node.lng], {
            radius: 4,
            color: '#25a4ff',
            fillColor: '#25a4ff',
            fillOpacity: 0.92,
            weight: 1
          }).bindPopup(
            `<b>${node.name}</b><br/>ID: ${node.id}<br/>type: ${node.type || '-'}<br/>is_metro_station: ${node.is_metro_station}`
          );
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

        if (bounds.length > 0) {
          map.fitBounds(bounds, { padding: [20, 20] });
        }

        setStatus('Tải xong dữ liệu metro từ spd_metro_last.graphml');
      } catch (err) {
        setStatus(`Lỗi tải dữ liệu: ${err.message}`, true);
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
    print("[DEBUG] Metro-last viewer on http://127.0.0.1:5051")
    app.run(host="127.0.0.1", port=5051, debug=False)
