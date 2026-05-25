# scripts/generate_water_polygons.py
import osmnx as ox
import geopandas as gpd

bbox = (29.4000, 59.5000, 31.0000, 60.3000)  # (minx, miny, maxx, maxy) = (W, S, E, N)
tags = {
    'natural': ['water', 'bay', 'strait'],
    'water': True,
    'waterway': ['river', 'riverbank', 'canal', 'stream'],
    'landuse': ['reservoir', 'basin'],
}
gdf = ox.features_from_bbox(bbox=bbox, tags=tags)
gdf = gdf[gdf.geometry.type.isin(['Polygon', 'MultiPolygon'])]
gdf = gdf[['geometry']].reset_index(drop=True)
gdf.to_file('graph/water_polygons.geojson', driver='GeoJSON')
print(f"Wrote {len(gdf)} water polygons.")