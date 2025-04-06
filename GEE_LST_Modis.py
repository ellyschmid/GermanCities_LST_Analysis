import ee
import geemap
import time

# Authenticate and initialize Google Earth Engine
ee.Authenticate()
ee.Initialize(project='braided-gist-417812')  # Replace with your actual file path

# ----------------------------
# 1. USER INPUTS
# ----------------------------
shapefile_path = "projects/braided-gist-417812/assets/filtered_cities"  # Replace with your actual file path
zensus_path = "projects/braided-gist-417812/assets/zensus2022_1km"
landcover_path = "projects/braided-gist-417812/assets/ugr2018_germany"

# selected period 
start_year = 2014
end_year = 2024

# Load datasets
cities = ee.FeatureCollection(shapefile_path)
#city_list = ee.List(cities.toList(100))  # Convert to list (adjust number if needed) # only for testing 
#test_city = ee.FeatureCollection([city_list.get(0), city_list.get(1)], city_list.get(2))  # Select cities by index

# load datasets
zensus = ee.Image(zensus_path)
landcover = ee.Image(landcover_path)

# Get CRS & scale from census data
zensus_proj = zensus.projection()
zensus_scale = zensus_proj.nominalScale()

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

# Ensure landcover is in the same projection as Census
city_bounds = buffered_cities.geometry().bounds()
landcover_clipped = landcover.clip(city_bounds)
landcover = landcover.reproject(crs=zensus_proj, scale=zensus_scale)


# ----------------------------
# 3. FUNCTIONS FOR PROCESSING
# ----------------------------
# change month and day as needed
def get_summer_lst(year):
    start_date, end_date = f"{year}-06-01", f"{year}-08-31"               # change day and month if needed
    lst_collection = (ee.ImageCollection("MODIS/061/MOD11A2")
                      .filterDate(start_date, end_date)
                      .select("LST_Day_1km")
                      .map(lambda img: img.multiply(0.02).subtract(273.15)))
    return lst_collection.map(lambda img: img.reproject(crs=zensus_proj, scale=zensus_scale))


def get_summer_ndvi(year):
    start_date, end_date = f"{year}-06-01", f"{year}-08-31"                # change day and month if needed
    def compute_ndvi(img):
        red, nir = img.select("Nadir_Reflectance_Band1"), img.select("Nadir_Reflectance_Band2")
        return img.addBands(nir.subtract(red).divide(nir.add(red)).rename("NDVI")).select("NDVI")
    ndvi_collection = (ee.ImageCollection("MODIS/006/MCD43A4")
                       .filterDate(start_date, end_date)
                       .map(compute_ndvi))
    return ndvi_collection.map(lambda img: img.reproject(crs=zensus_proj, scale=zensus_scale))


def calculate_landcover_fractions(class_value):
    """Computes fraction of a specific land cover class in each 1km pixel."""
    class_mask = landcover_clipped.eq(class_value)
    class_fraction = class_mask.reduceResolution(
        reducer=ee.Reducer.mean(), bestEffort=True
    ).reproject(crs=zensus_proj, scale=zensus_scale)
    return class_fraction.rename(f"LC_{class_value}_Frac")


landcover_classes = [1, 2, 3, 4, 5, 6, 7, 8]
landcover_fractions = [calculate_landcover_fractions(c) for c in landcover_classes]
landcover_final = ee.Image.cat(landcover_fractions)

# ----------------------------
# 4. LOAD & AGGREGATE DATA
# ----------------------------
lst_collection, ndvi_collection = ee.ImageCollection([]), ee.ImageCollection([])
for year in range(start_year, end_year + 1):
    lst_collection = lst_collection.merge(get_summer_lst(year))
    ndvi_collection = ndvi_collection.merge(get_summer_ndvi(year))


def calculate_stats(img_collection, stat_name):
    return ee.Image.cat([
        img_collection.mean().rename(stat_name + "_Mean"),
        img_collection.median().rename(stat_name + "_Median"),
        img_collection.max().rename(stat_name + "_Max"),
        img_collection.reduce(ee.Reducer.stdDev()).rename(stat_name + "_Std")
    ])


lst_stats, ndvi_stats = calculate_stats(lst_collection, "LST"), calculate_stats(ndvi_collection, "NDVI")
final_image = ee.Image.cat(lst_stats, ndvi_stats, landcover_final).reproject(crs=zensus_proj, scale=zensus_scale)
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
    scale=zensus_scale,
    properties=['City', 'Buffer_Indicator'],
    geometries=True
)

# Sample buffer area with city names preserved
sampled_buffer = final_image_with_population.sampleRegions(
    collection=buffered_cities,  # Use the buffered cities with correct city names
    scale=zensus_scale,
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
    description="LST_NDVI_Landcover_Modis",
    fileNamePrefix="LST_NDVI_Landcover_Modis",
    fileFormat="CSV"
)
task.start()
print("Export task started!")

