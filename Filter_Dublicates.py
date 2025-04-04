import pandas as pd

# Step 1: Load the exported CSV
csv_path = r"LST_NDVI_Landcover_Modis.csv"  # Replace with your actual file path
df = pd.read_csv(csv_path)

# Step 2: Filter out duplicates based on Latitude and Longitude
df_unique = df.drop_duplicates(subset=['Latitude', 'Longitude'])

# Step 3:  Save the filtered data to a new CSV file
output_path = r"Summer_Modis.csv"  # Replace with your desired output path
df_unique.to_csv(output_path, index=False)
print(f"Filtered CSV saved to {output_path}")
