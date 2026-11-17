"""Istanbul yol agini BIR KEZ indirip yollar.gpkg olarak kaydeder.

Sonra:  python osm_test.py traffic_density_202306.csv --n 20 --roads yollar.gpkg

Kullanim:
    pip install pyrosm
    python prepare_roads.py                      # pyrosm'un hazir Istanbul dosyasini indirir
    python prepare_roads.py turkey-latest.osm.pbf  # elinde Geofabrik pbf varsa, onu kirpar
"""
import sys
from pyrosm import OSM, get_data

# Istanbul'u kapsayan kutu (minx, miny, maxx, maxy) - IBB hucreleri bunun icinde
BBOX = [27.9, 40.7, 29.9, 41.4]

if len(sys.argv) > 1:
    pbf = sys.argv[1]
    osm = OSM(pbf, bounding_box=BBOX)
else:
    pbf = get_data("Istanbul")   # hazir sehir dosyasini indirir (BBBike/Geofabrik)
    osm = OSM(pbf)

print("dosya:", pbf)
roads = osm.get_network(network_type="driving", extra_attributes=["lanes", "maxspeed", "ref", "tunnel", "bridge"])
print("yol parcasi:", len(roads))
print("highway tipleri:\n", roads["highway"].value_counts().head(12).to_string())
roads.to_file("yollar.gpkg", driver="GPKG")
print("kaydedildi: yollar.gpkg")
