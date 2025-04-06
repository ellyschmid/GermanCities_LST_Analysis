import pandas as pd
import os
import glob

# Set the folder where your CSVs are stored (after download)
csv_folder = r"C:\Users\ellys\Downloads\Per_City_CSVs"  # actual file path
output_path = r"C:\Users\ellys\Downloads\Per_City_CSVs\LST_NDVI_Landcover_Modis.csv"

# Get all CSV files in the folder
all_csv_files = glob.glob(os.path.join(csv_folder, "*.csv"))

# Read and combine
df_list = [pd.read_csv(f) for f in all_csv_files]
combined_df = pd.concat(df_list, ignore_index=True)

# Optional: Remove duplicates or sort
#combined_df = combined_df.sort_values(by=["City", "Latitude", "Longitude"])
combined_df = combined_df.drop_duplicates(subset=['Latitude', 'Longitude'])

# Save combined CSV
combined_df.to_csv(output_path, index=False)
print(f"✅ Combined {len(all_csv_files)} files into: {output_path}")
