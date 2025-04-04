import ee
import geemap
import time

# Authenticate and initialize Google Earth Engine
ee.Authenticate()
ee.Initialize(project='braided-gist-417812')

# ----------------------------
# 1. USER INPUTS
# ----------------------------
shapefile_path = "projects/braided-gist-417812/assets/filtered_cities"
zensus_path = "projects/braided-gist-417812/assets/zensus2022_100m"
landcover_path = "projects/braided-gist-417812/assets/ugr2018_germany"

start_year = 2014
end_year = 2024

# Load datasets
cities = ee.FeatureCollection(shapefile_path)
#city_list = ee.List(cities.toList(100))  # Convert to list (adjust number if needed)
#test_city = ee.FeatureCollection([city_list.get(0), city_list.get(5)])  # Select cities by index

zensus = ee.Image(zensus_path)
landcover = ee.Image(landcover_path)

# Get CRS & scale from census data
zensus_proj = zensus.projection()
zensus_scale = zensus_proj.nominalScale()

# Ensure landcover is in the same projection as Census
city_bounds = cities.geometry().bounds()
landcover_clipped = landcover.clip(city_bounds)
landcover = landcover.reproject(crs=zensus_proj, scale=100)

# Landsat sensors
landsat_sensors = [
    "LANDSAT/LC08/C02/T1_L2",  # Landsat 8
    "LANDSAT/LE07/C02/T1_L2",  # Landsat 7
    "LANDSAT/LT05/C02/T1_L2"   # Landsat 5 (older years)
]

# ----------------------------
# 2. CREATE BUFFER & REMOVE OVERLAP
# ----------------------------
buffer_distance = 5000  # 5 km buffer


# Function to create a buffer for each city while keeping the city name
def create_buffer(feature):
    buffer_geom = feature.geometry().buffer(buffer_distance)
    buffer_geom_without_city = buffer_geom.difference(feature.geometry())  # Remove original city area
    return ee.Feature(buffer_geom_without_city).set({
        "City": feature.get("GEN"),  # Keep city name
        "Buffer_Indicator": 1
    })


# Apply the function to each city individually
buffered_cities = cities.map(create_buffer)

# Merge all buffer areas into a single geometry
merged_buffers = buffered_cities.union().geometry()

# Ensure no overlapping pixels: Remove the original city areas from the buffers
buffer_only = merged_buffers.difference(cities.geometry())


# ----------------------------
# 2. FUNCTIONS FOR PROCESSING
# ----------------------------
def mask_landsat_clouds(image):
    """Applies cloud mask using the QA_PIXEL band"""
    qa = image.select("QA_PIXEL")
    cloud_mask = qa.bitwiseAnd(1 << 3).eq(0)  # Cloud bit
    return image.updateMask(cloud_mask)


def get_landsat_collection(year, sensor):
    """Fetches Landsat images, applies cloud mask, and calculates LST & NDVI."""
    start_date, end_date = f"{year}-06-01", f"{year}-08-31"
    collection = (ee.ImageCollection(sensor)
                  .filterDate(start_date, end_date)
                  .filterBounds(city_bounds)
                  .map(mask_landsat_clouds))

    def compute_ndvi(img):
        nir = img.select("SR_B5") if 'LC08' in sensor else img.select("SR_B4")
        red = img.select("SR_B4") if 'LC08' in sensor else img.select("SR_B3")
        ndvi = nir.subtract(red).divide(nir.add(red)).rename("NDVI")
        return img.addBands(ndvi)

    def compute_lst(img):
        if 'LC08' in sensor:
            thermal = img.select("ST_B10").multiply(0.00341802).add(149)  # Convert to Kelvin
        else:
            thermal = img.select("ST_B6").multiply(0.00341802).add(149)  # Convert to Kelvin for Landsat 5 & 7
        lst = thermal.subtract(273.15).rename("LST")  # Convert to Celsius
        return img.addBands(lst)

    return collection.map(compute_ndvi).map(compute_lst)


# Initialize empty collections
lst_collection = ee.ImageCollection([])
ndvi_collection = ee.ImageCollection([])

# Loop through years and sensors only once per combination
for year in range(start_year, end_year + 1):
    for sensor in landsat_sensors:
        collection = get_landsat_collection(year, sensor)  # One call only
        lst_collection = lst_collection.merge(collection.select("LST"))
        ndvi_collection = ndvi_collection.merge(collection.select("NDVI"))


# Compute land cover fractions
def calculate_landcover_fractions(class_value):
    class_mask = landcover_clipped.eq(class_value)
    class_fraction = class_mask.reduceResolution(
        reducer=ee.Reducer.mean(), bestEffort=True
    ).reproject(crs=zensus_proj, scale=100
                )
    return class_fraction.rename(f"LC_{class_value}_Frac")


landcover_classes = [1, 2, 3, 4, 5, 6, 7, 8]
landcover_fractions = [calculate_landcover_fractions(c) for c in landcover_classes]
landcover_final = ee.Image.cat(landcover_fractions)


# Compute statistics
def calculate_stats(img_collection, stat_name):
    return ee.Image.cat([
        img_collection.mean().rename(stat_name + "_Mean"),
        img_collection.median().rename(stat_name + "_Median"),
        img_collection.max().rename(stat_name + "_Max"),
        img_collection.reduce(ee.Reducer.stdDev()).rename(stat_name + "_Std")
    ])


lst_stats, ndvi_stats = calculate_stats(lst_collection, "LST"), calculate_stats(ndvi_collection, "NDVI")
final_image = ee.Image.cat(lst_stats, ndvi_stats, landcover_final).reproject(crs=zensus_proj, scale=100)
final_image_with_population = final_image.addBands(zensus.select(['b1']).rename("Zensus"))


# ----------------------------
# 5. SAMPLE DATA & EXPORT
# ----------------------------
def extract_city_info(feature):
    return feature.set({"City": feature.get("GEN"), "Buffer_Indicator": 0})


def extract_buffer_info(feature):
    return feature.set({"City": "Buffer Area", "Buffer_Indicator": 1})


# Sample original city area
cities = cities.map(extract_city_info)

sampled_city = final_image_with_population.sampleRegions(
    collection=cities,
    scale=100,
    properties=['City', 'Buffer_Indicator'],
    geometries=True
)

# Sample buffer area with city names preserved
sampled_buffer = final_image_with_population.sampleRegions(
    collection=buffered_cities,  # Use the buffered cities with correct city names
    scale=100,
    properties=['City', 'Buffer_Indicator'],
    geometries=True
)

# Merge both datasets
sampled_final = sampled_city.merge(sampled_buffer)


def extract_coordinates(feature):
    coords = feature.geometry().coordinates()
    properties = {"Longitude": coords.get(0), "Latitude": coords.get(1),
                  "City": feature.get("City"),
                  "Buffer_Indicator": feature.get("Buffer_Indicator"),
                  "LST_Mean": feature.get("LST_Mean"), "LST_Median": feature.get("LST_Median"),
                  "LST_Max": feature.get("LST_Max"), "LST_Std": feature.get("LST_Std"),
                  "NDVI_Mean": feature.get("NDVI_Mean"), "NDVI_Median": feature.get("NDVI_Median"),
                  "NDVI_Max": feature.get("NDVI_Max"), "NDVI_Std": feature.get("NDVI_Std"),
                  "Zensus": feature.get("Zensus")}

    for lc in landcover_classes:
        properties[f"LC_{lc}_Frac"] = feature.get(f"LC_{lc}_Frac")
    return ee.Feature(None, properties)


sampled_final = sampled_final.map(extract_coordinates)

task = ee.batch.Export.table.toDrive(
    collection=sampled_final,
    description="LST_NDVI_Landcover_Landsat",
    fileNamePrefix="LST_NDVI_Landcover_Landsat",
    fileFormat="CSV"
)
task.start()

print("Export task started!")