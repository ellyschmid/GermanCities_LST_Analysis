# GermanCities_LST_Analysis
Google Earth Engine LST, NDVI, Landcover and Population Analysis of Biggest Cities in Germany.
> This Project uses the Google Earth Engine API in Python to calculate LST and NDVI Timeseries-Data from Modis and Landsat for the largest cities in Germany.
> Additionally information of the Landcover and Population is added.
## Files in Input_Folder 
* Bevölkerungstabelle: Zensus bases Population information of Germany from 2022
* VG250_GEM: Shapefile containing the Administrative Boundaries of Germany (Gemeinden)
* filtered_cities: fildered cities in Germany based on the "Bevölkerungstabelle" and "VG250_GEM" . Includes cities with a Population > 50.000 in Germany.
* zensus2022_1km: population grid of germany based on the zensus 2022 in 1 km resolution
* zensus2022_100m: population grid of germany based on the zensus 2022 in 100 m resolution
* additionally, the "Urban Green Raster Germany 2018" was used for Lancover Information. Available: https://zenodo.org/records/5842521
## Scripts: 
* Zensus_Cities: Filters first the Bevölkerungstabelle for Germany for cities with a Population above 50.000 inhabitants. In a Second step, the VG250_GEM Shapefile is filtered based on the selected cities from the "Bevölkerungstabelle".
* GEE_LST_Modis:
> The Script utilises the GEE-API in python. It needs to be intialized within a project in GEE. All the necsessary Inputs need to be uploaded to the Project assets in GEE. The Input requires the shapefile of the selected city boundaries, the Zensus raster (1 km) and the urban green raster. First, the Script creates a buffer of 5 km around each city extent. The Modis collection is loaded and the aggregated Mean, Max, Median and Standard Deviation of LST and NDVI is calculated for the selected time period. The Landcover raster is clipped with the city extents to save computation time and the fraction of each Landcover class for each pixel within the buffered city extents is estimated. All rasters are reprojected to the scale and projection of the zensus raster to insure alignment of the pixels. Also, the Zensus raster is added to the collection. The values within the city extents and the buffer extent are sampled and saved in a feature collection. Finally, the location and calculated features for each pixel within the city and buffer extents are calculated and exported in a csv-file. In the Result a column indicates if a pixel is in the original city extent with a 0 and a 1 if the pixel is located in the buffered zone. 
* GEE_LST_Landsat:
> The Script Uses the same approach as in the previous script, but for the Landsat-Collection and the Zenusu raster in 100 m resolution for a higher resolution result. Due to the high computational time of the analysis the processing is built in a loop to create a csv file for each city that is going to be exported to the drive. This reduces the computational time. After the Export, the folder can be downloaded and the csv combined.
* Filter_Dublicates: The Script takes the CSV Result of the aggregated values for each pixel for the selected cities and filters out double entries from pixels that might be overlapping due to the buffered zone around the cities.
* Merge_CSVs: loads all the CSVs from the downloaded folder containing the analysis using the Landsat collection. The Script concatenates the CSVs to one file and filters for dublicates based on the coordinates. 
