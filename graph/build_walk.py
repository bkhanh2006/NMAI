import osmnx as ox

place_name = "Saint Petersburg, Russia"

OUT_WALK = r"C:\Users\LENOVO\Documents\GitHub\NMAI\graph\spd_walk.graphml"

ox.settings.use_cache = True
ox.settings.log_console = True
ox.settings.timeout = 180

print("--- Đang tải walk graph ---")

# Lấy mạng đường phù hợp cho đi bộ
G_walk = ox.graph_from_place(
    place_name,
    network_type="walk",
    simplify=True,
    retain_all=False
)

print("--- Gán trọng số walk ---")

walk_speed = 5000 / 60  # mét/phút

for u, v, k, data in G_walk.edges(keys=True, data=True):
    length = float(data.get("length", 1))
    data["time"] = length / walk_speed
    data["type"] = "walk"
    data["is_active"] = True

for node_id, data in G_walk.nodes(data=True):
    data["type"] = "walk"
    data["is_metro_station"] = False

print("Walk nodes:", G_walk.number_of_nodes())
print("Walk edges:", G_walk.number_of_edges())

print("--- Đang lưu spd_walk.graphml ---")
ox.save_graphml(G_walk, filepath=OUT_WALK)

print("Hoàn tất:", OUT_WALK)