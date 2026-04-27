import osmnx as ox
import networkx as nx
from shapely.ops import unary_union
place_name = "Saint Petersburg, Russia"

# 1. Lấy vị trí các ga tàu (Points)
tags = {"railway": "station", "station": "subway"}
print("1")
gdf_stations = ox.features_from_place(place_name, tags=tags)

print("2")
# 2. Tạo vùng đệm (Buffer) quan.h các ga (ví dụ: bán kính 1km)
# Điều này giúp bạn chỉ lấy mạng lưới đường bộ xung quanh ga thay vì toàn thành phố
union_geom = unary_union(gdf_stations.geometry).buffer(0.01)# 0.01 độ tương đương ~1km
print("3")
# Sau khi đã có gdf_stations...

# 5. Tải thêm dữ liệu tuyến đường ray (Metro lines)
# Chúng ta sử dụng features_from_polygon để lấy metro_lines nằm trong cùng vùng với ga
metro_tags = {'railway': 'subway'}
print("Đang tải dữ liệu tuyến Metro...")
metro_lines = ox.features_from_polygon(union_geom, tags=metro_tags)

# 6. Kiểm tra dữ liệu (quan trọng)
print(f"Số lượng tuyến đường Metro tìm thấy: {len(metro_lines)}")

# Bạn có thể lưu lại để dùng trong file build
# (Lưu ý: GeoDataFrame không lưu được trực tiếp thành graphml, 
# nên ta lưu thành file gpkg - Geopackage chuẩn GIS)
metro_lines.to_file(r'C:\Users\LENOVO\Documents\GitHub\NMAI\graph\metro_lines.gpkg', driver='GPKG')
# 3. Tải đồ thị chỉ trong vùng đệm này
G = ox.graph_from_polygon(union_geom, network_type='walk')
print("4")
# 4. Lưu lại
ox.save_graphml(G, filepath=r'C:\Users\LENOVO\Documents\GitHub\NMAI\graph\spd_walk.graphml')