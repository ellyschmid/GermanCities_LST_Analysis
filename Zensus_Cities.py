import geopandas as gpd
import pandas as pd

# ----------------------------
# 1. Filter cities by Administrative Boundaries and amount of Citizens
# ----------------------------
# Load the CSV file
csv_path = r"Zensus.csv"
df = pd.read_csv(csv_path)  # Try 'latin1' if UTF-8 fails

df = df[df["Regionalebene Bevölkerung"].str.contains(r"\bGemeinde\b", case=False, na=False)]

# Filter cities with population > 50,000
filtered_df = df[df["Bevölkerung22"] > 50000]

# Extract the list of city names
city_names = filtered_df["Name"].unique()

# ----------------------------
# 2. Filter city extents for matching city names
# ----------------------------
# Load the shapefile
shapefile_path = r"Shapefile_Zensus2022\EPSG_25832\VG250_GEM.shp"
gdf = gpd.read_file(shapefile_path)

# Check the projection of the shapefile
print(f"Projection of the shapefile: {gdf.crs}")

# Filter shapefile to keep only cities in the filtered list
filtered_gdf = gdf[gdf["GEN"].isin(city_names)]

# Get the number of unique cities after removing duplicates
unique_cities_count = filtered_gdf["GEN"].nunique()
print(f"Number of unique cities after removing duplicates: {unique_cities_count}")

# Check for duplicates in the "GEN" column
duplicates = filtered_gdf[filtered_gdf["GEN"].duplicated()]


filtered_gdf = filtered_gdf.drop_duplicates(subset="GEN")
filtered_gdf = filtered_gdf.to_crs(epsg=25832)

# Save the filtered shapefile
output_path = r"filtered_cities.shp" # Replace with path
filtered_gdf.to_file(output_path)

print(f"Filtered shapefile saved at {output_path}")
