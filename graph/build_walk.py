#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_walk.py
Build an optimized pedestrian network for Saint Petersburg, Russia
and export it to graph/spd_walk.graphml in a format that is fully
compatible with the existing main.py routing logic.

Convention (must match main.py):
    node attribute 'x' = longitude (WGS84)
    node attribute 'y' = latitude  (WGS84)
    'lat' / 'lng' are also written explicitly for backward compatibility.

Pipeline:
  1. Download OSM walk network for Saint Petersburg.
  2. Consolidate intersections (15 m tolerance) to merge duplicate nodes.
  3. Prune any node whose coordinates leak out of WGS84 range.
  4. Collapse parallel edges between the same pair of nodes (keep the
     shortest one) while preserving the MultiGraph / MultiDiGraph type.
  5. Assign walking time and clean unused OSM metadata.
  6. Align coordinates so x=lng, y=lat, plus explicit lat/lng.
  7. Namespace every node ID with a "w_" prefix so that walk node IDs
     can never collide with the integer-string IDs that build_metro.py
     assigns to metro stations. Without this step, main.py silently
     drops every walk node whose ID matches a station ID, leaving the
     metro disconnected from the walk graph and forcing A* to walk
     everywhere.
  8. Save as GraphML.
"""

import math
import os

import networkx as nx
import osmnx as ox


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PLACE_NAME = "Saint Petersburg, Russia"
OUT_WALK = r"C:\Users\LENOVO\Documents\GitHub\NMAI\graph\spd_walk.graphml"

# Walking speed in metres per minute. 5000 m / 60 min == 5 km/h.
WALK_SPEED_M_PER_MIN = 5000.0 / 60.0

# Namespace prefix applied to every walk node ID right before saving.
# This guarantees no collisions with the small-integer-string IDs used
# by build_metro.py (e.g. "0", "1", ..., "80") for metro stations.
WALK_NODE_PREFIX = "w_"

# OSM tags that bloat the file size but are not used by main.py.
EDGE_TAGS_TO_DROP = (
    "osmid", "name", "ref", "highway", "maxspeed", "service", "access",
    "area", "landuse", "width", "est_width", "lanes", "bridge", "tunnel",
    "junction", "oneway", "reversed", "from", "to", "surface", "smoothness",
    "sidewalk", "foot", "bicycle", "lit", "tracktype", "incline",
)
NODE_TAGS_TO_DROP = (
    "osmid", "osmid_original", "highway", "ref", "street_count", "junction",
)


# ---------------------------------------------------------------------------
# OSMnx settings
# ---------------------------------------------------------------------------

ox.settings.use_cache = True
ox.settings.log_console = True
ox.settings.timeout = 300


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _haversine_m(lat1, lng1, lat2, lng2):
    """Great-circle distance between two WGS84 points, in metres."""
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _collapse_parallel_edges(graph):
    """
    Return a copy of `graph` in which, for every unordered pair of nodes
    (u, v), at most one edge survives -- the one with the smallest length.

    The returned graph keeps the SAME class as the input (MultiGraph /
    MultiDiGraph). OSMnx helpers require a Multi* graph, so we must NOT
    downgrade to nx.Graph here.
    """
    g = graph.copy()

    # Cast node IDs to strings before sorting; without it, mixed int/str
    # node IDs raise:
    #     TypeError: '<' not supported between instances of 'str' and 'int'
    best_edge_per_pair = {}     # pair -> (length, u, v, key)
    edges_to_remove = []

    for u, v, k, data in g.edges(keys=True, data=True):
        pair = tuple(sorted((str(u), str(v))))
        length = float(data.get("length", 0.0)) or 0.0

        if pair not in best_edge_per_pair:
            best_edge_per_pair[pair] = (length, u, v, k)
            continue

        prev_length, pu, pv, pk = best_edge_per_pair[pair]
        if length < prev_length:
            edges_to_remove.append((pu, pv, pk))
            best_edge_per_pair[pair] = (length, u, v, k)
        else:
            edges_to_remove.append((u, v, k))

    for u, v, k in edges_to_remove:
        if g.has_edge(u, v, key=k):
            g.remove_edge(u, v, key=k)

    return g


def _drop_tags(graph):
    """Remove unused OSM metadata to keep the GraphML compact."""
    for _, data in graph.nodes(data=True):
        for tag in NODE_TAGS_TO_DROP:
            data.pop(tag, None)

    if graph.is_multigraph():
        for _, _, _, data in graph.edges(keys=True, data=True):
            for tag in EDGE_TAGS_TO_DROP:
                data.pop(tag, None)
    else:
        for _, _, data in graph.edges(data=True):
            for tag in EDGE_TAGS_TO_DROP:
                data.pop(tag, None)


def _stringify_attr_values(graph):
    """
    GraphML can only serialize scalar attribute values. Convert any
    list / dict / tuple / set values to their str() so save_graphml does
    not crash on edges that still carry e.g. OSM `osmid` lists.
    """
    for _, data in graph.nodes(data=True):
        for key, val in list(data.items()):
            if isinstance(val, (list, dict, tuple, set)):
                data[key] = str(val)

    if graph.is_multigraph():
        for _, _, _, data in graph.edges(keys=True, data=True):
            for key, val in list(data.items()):
                if isinstance(val, (list, dict, tuple, set)):
                    data[key] = str(val)
    else:
        for _, _, data in graph.edges(data=True):
            for key, val in list(data.items()):
                if isinstance(val, (list, dict, tuple, set)):
                    data[key] = str(val)


def _prune_invalid_wgs84_nodes(graph):
    """
    Drop any node whose `x` is not in [-180, 180] or whose `y` is not in
    [-90, 90]. This guards against stale UTM coordinates that occasionally
    survive `consolidate_intersections(..., rebuild_graph=True)` and that
    would otherwise poison main.py's WALK_KDTREE.
    """
    bad = []
    for node_id, data in graph.nodes(data=True):
        try:
            x = float(data.get("x"))
            y = float(data.get("y"))
        except (TypeError, ValueError):
            bad.append(node_id)
            continue

        if not (-180.0 <= x <= 180.0 and -90.0 <= y <= 90.0):
            bad.append(node_id)

    if bad:
        graph.remove_nodes_from(bad)

    return len(bad)


def _namespace_node_ids(graph, prefix=WALK_NODE_PREFIX):
    """
    Relabel every node `n` to `f"{prefix}{n}"`. This is what eliminates
    the collision between walk node IDs (small integers from OSMnx after
    consolidation) and metro station IDs (small integer strings from
    build_metro.py's `str(idx)`). After this step it is impossible for
    main.py's combined graph to mix a station with a walk intersection
    just because they happen to share an ID like "12".
    """
    mapping = {n: f"{prefix}{n}" for n in graph.nodes}
    return nx.relabel_nodes(graph, mapping, copy=True)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main():
    print("--- Downloading walk graph for:", PLACE_NAME, "---")
    g_walk = ox.graph_from_place(
        PLACE_NAME,
        network_type="walk",
        simplify=True,
        retain_all=False,
    )
    print(f"    raw nodes={g_walk.number_of_nodes()}  edges={g_walk.number_of_edges()}")

    # -----------------------------------------------------------------------
    # Step 1: consolidate intersections to merge near-duplicate junctions.
    # -----------------------------------------------------------------------
    print("--- Consolidating intersections (tolerance=15 m) ---")
    g_proj = ox.project_graph(g_walk)
    g_proj = ox.consolidate_intersections(
        g_proj,
        tolerance=15,
        rebuild_graph=True,
        dead_ends=False,
    )
    g_walk = ox.project_graph(g_proj, to_crs="EPSG:4326")
    print(f"    after consolidation nodes={g_walk.number_of_nodes()}  edges={g_walk.number_of_edges()}")

    # -----------------------------------------------------------------------
    # Step 2: prune any node whose coordinates are not valid WGS84.
    # -----------------------------------------------------------------------
    n_bad = _prune_invalid_wgs84_nodes(g_walk)
    if n_bad:
        print(f"    pruned {n_bad} node(s) with invalid WGS84 coordinates")

    # -----------------------------------------------------------------------
    # Step 3: re-fill any missing/zero `length` from haversine.
    # -----------------------------------------------------------------------
    for u, v, _, data in g_walk.edges(keys=True, data=True):
        if "length" not in data or float(data.get("length", 0) or 0) <= 0:
            try:
                lat1, lng1 = float(g_walk.nodes[u]["y"]), float(g_walk.nodes[u]["x"])
                lat2, lng2 = float(g_walk.nodes[v]["y"]), float(g_walk.nodes[v]["x"])
                data["length"] = _haversine_m(lat1, lng1, lat2, lng2)
            except (KeyError, TypeError, ValueError):
                data["length"] = 0.0

    # -----------------------------------------------------------------------
    # Step 4: collapse parallel edges (keeps Multi* type).
    # -----------------------------------------------------------------------
    print("--- Collapsing parallel edges ---")
    before = g_walk.number_of_edges()
    g_walk = _collapse_parallel_edges(g_walk)
    print(f"    removed {before - g_walk.number_of_edges()} parallel edge(s)")

    # -----------------------------------------------------------------------
    # Step 5: assign walking time, node/edge types, drop unused tags.
    # -----------------------------------------------------------------------
    print("--- Assigning walk weights and cleaning metadata ---")
    if g_walk.is_multigraph():
        for u, v, k, data in g_walk.edges(keys=True, data=True):
            length = float(data.get("length", 0.0) or 0.0)
            data["length"] = length
            data["time"] = length / WALK_SPEED_M_PER_MIN if length > 0 else 0.0
            data["type"] = "walk"
            data["is_active"] = True
    else:
        for u, v, data in g_walk.edges(data=True):
            length = float(data.get("length", 0.0) or 0.0)
            data["length"] = length
            data["time"] = length / WALK_SPEED_M_PER_MIN if length > 0 else 0.0
            data["type"] = "walk"
            data["is_active"] = True

    for _, data in g_walk.nodes(data=True):
        data["type"] = "walk"
        data["is_metro_station"] = False

    _drop_tags(g_walk)

    # -----------------------------------------------------------------------
    # Step 6: explicit coordinate alignment for main.py compatibility.
    # -----------------------------------------------------------------------
    print("--- Aligning coordinates (x=lng, y=lat, plus lat/lng) ---")
    for _, data in g_walk.nodes(data=True):
        try:
            lng = float(data["x"])
            lat = float(data["y"])
        except (KeyError, TypeError, ValueError):
            continue

        data["x"] = float(lng)
        data["y"] = float(lat)
        data["lat"] = float(lat)
        data["lng"] = float(lng)

    # -----------------------------------------------------------------------
    # Step 7: namespace every walk node ID so it cannot collide with the
    # integer-string station IDs assigned by build_metro.py.
    # -----------------------------------------------------------------------
    print(f"--- Namespacing walk node IDs with prefix {WALK_NODE_PREFIX!r} ---")
    g_walk = _namespace_node_ids(g_walk, WALK_NODE_PREFIX)

    # -----------------------------------------------------------------------
    # Step 8: make all attribute values GraphML-serializable, then save.
    # -----------------------------------------------------------------------
    _stringify_attr_values(g_walk)

    print(f"Final walk graph: nodes={g_walk.number_of_nodes()}  edges={g_walk.number_of_edges()}")
    print("--- Saving:", OUT_WALK, "---")
    os.makedirs(os.path.dirname(OUT_WALK), exist_ok=True)
    ox.save_graphml(g_walk, filepath=OUT_WALK)
    print("Done:", OUT_WALK)


if __name__ == "__main__":
    main()