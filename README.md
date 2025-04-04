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
* Zensus_Cities: Filters first the Bevölkerungstabelle for Germany for cities with a Population above 50.000 inhabitants. The VG250_GEM Shapefile based on the selected cities from the "Bevölkerungstabelle". 
