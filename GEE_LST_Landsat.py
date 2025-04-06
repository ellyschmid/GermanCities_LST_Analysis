import ee
import geemap
import time
import re
import unidecode

# Authenticate and initialize GEE
ee.Authenticate()
ee.Initialize(project='braided-gist-417812') # Change to own project in GEE

# -----------------------------
# 1. USER INPUTS
# -----------------------------
shapefile_path = "projects/braided-gist-417812/assets/filtered_cities" # change to acutal path of the assets in GEE
zensus_path = "projects/braided-gist-417812/assets/zensus2022_100m"
landcover_path = "projects/braided-gist-417812/assets/ugr2018_germany"

# change to desired period
start_year = 2014
end_year = 2024
buffer_distance = 5000  # meters

# Load datasets
cities = ee.FeatureCollection(shapefile_path)
zensus = ee.Image(zensus_path)
landcover = ee.Image(landcover_path)

# Projection and scale from census
zensus_proj = zensus.projection()
zensus_scale = zensus_proj.nominalScale()

landsat_sensors = [
    "LANDSAT/LC08/C02/T1_L2",
    "LANDSAT/LE07/C02/T1_L2",
    "LANDSAT/LT05/C02/T1_L2"
]

# -----------------------------
#Functions
# -----------------------------

def mask_landsat_clouds(image):
    qa = image.select("QA_PIXEL")
    cloud_mask = qa.bitwiseAnd(1 << 3).eq(0)
    return image.updateMask(cloud_mask)

def compute_ndvi(img, sensor):
    nir = img.select("SR_B5") if 'LC08' in sensor else img.select("SR_B4")
    red = img.select("SR_B4") if 'LC08' in sensor else img.select("SR_B3")
    ndvi = nir.subtract(red).divide(nir.add(red)).rename("NDVI")
    return img.addBands(ndvi)

def compute_lst(img, sensor):
    if 'LC08' in sensor:
        thermal = img.select("ST_B10").multiply(0.00341802).add(149)
    else:
        thermal = img.select("ST_B6").multiply(0.00341802).add(149)
    lst = thermal.subtract(273.15).rename("LST")
    return img.addBands(lst)

# load landsat collection
def get_landsat_collection(year, sensor, geometry):
    start_date = f"{year}-06-01"                                # change day and month if needed for different period
    end_date = f"{year}-08-31"
    collection = (ee.ImageCollection(sensor)
                  .filterDate(start_date, end_date)
                  .filterBounds(geometry)
                  .map(mask_landsat_clouds)
                  .map(lambda img: compute_ndvi(img, sensor))
                  .map(lambda img: compute_lst(img, sensor)))
    return collection

def calculate_stats(img_collection, stat_name):
    return ee.Image.cat([
        img_collection.mean().rename(f"{stat_name}_Mean"),
        img_collection.median().rename(f"{stat_name}_Median"),
        img_collection.max().rename(f"{stat_name}_Max"),
        img_collection.reduce(ee.Reducer.stdDev()).rename(f"{stat_name}_Std")
    ])

def calculate_landcover_fractions(landcover_img, geometry, proj, scale):
    landcover_classes = [1, 2, 3, 4, 5, 6, 7, 8]
    clipped = landcover_img.clip(geometry)
    fractions = []
    for c in landcover_classes:
        mask = clipped.eq(c)
        fraction = (mask.reduceResolution(reducer=ee.Reducer.mean(), bestEffort=True)
                         .reproject(crs=proj, scale=scale)
                         .rename(f"LC_{c}_Frac"))
        fractions.append(fraction)
    return ee.Image.cat(fractions)

def clean_city_name(city_name):
    name = unidecode.unidecode(city_name)  # e.g., München → Muenchen
    name = re.sub(r'\W+', '_', name)       # Replace non-word chars with _
    return name[:90]                       # Truncate to stay under 100 char limit

def export_city_data(city_feat):
    city_name = city_feat.get("GEN").getInfo()
    city_id = clean_city_name(city_name)
    print(f"Export started for {city_name}")

    # Geometry & buffer
    city_geom = city_feat.geometry()
    buffer_geom = city_geom.buffer(buffer_distance).difference(city_geom)
    all_geom = city_geom.union(buffer_geom)

    # Get LST/NDVI
    lst_collection = ee.ImageCollection([])
    ndvi_collection = ee.ImageCollection([])

    for year in range(start_year, end_year + 1):
        for sensor in landsat_sensors:
            collection = get_landsat_collection(year, sensor, all_geom)
            lst_collection = lst_collection.merge(collection.select("LST"))
            ndvi_collection = ndvi_collection.merge(collection.select("NDVI"))

    # Compute stats
    lst_stats = calculate_stats(lst_collection, "LST")
    ndvi_stats = calculate_stats(ndvi_collection, "NDVI")
    landcover_frac = calculate_landcover_fractions(landcover, all_geom, zensus_proj, 100)
    image = ee.Image.cat(lst_stats, ndvi_stats, landcover_frac, zensus.select("b1").rename("Zensus"))

    # Define features
    def set_info(geom, is_buffer):
        return ee.Feature(geom, {
            "City": city_name,
            "Buffer_Indicator": int(is_buffer)
        })

    city_feature = set_info(city_geom, False)
    buffer_feature = set_info(buffer_geom, True)

    sample = image.sampleRegions(
        collection=ee.FeatureCollection([city_feature, buffer_feature]),
        scale=100,
        properties=["City", "Buffer_Indicator"],
        geometries=True
    )

    # Add coordinates
    def add_coords(feat):
        coords = feat.geometry().centroid().coordinates()
        feat = feat.set("Longitude", coords.get(0))
        feat = feat.set("Latitude", coords.get(1))
        return feat

    sample = sample.map(add_coords)

    # Export
    task = ee.batch.Export.table.toDrive(
        collection=sample,
        description=f"Export_{city_id}",
        fileNamePrefix=f"CityData_{city_id}",
        folder="Per_City_CSVs",
        fileFormat="CSV"
    )
    task.start()


# -----------------------------
# Run for all cities
# -----------------------------
city_list = cities.toList(cities.size())

for i in range(ee.Number(city_list.size()).getInfo()):
    try:
        feature = ee.Feature(city_list.get(i))
        export_city_data(feature)
        time.sleep(1)  # Avoid flooding API
    except Exception as e:
        print(f"❌ Failed for city index {i}: {e}")
