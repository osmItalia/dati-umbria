#!/bin/bash
prev="1"
url1="http://geo.umbriaterritorio.it/ArcGIS/rest/services/Public/ECOGRAFICO_CATASTALE1_WGS84/MapServer/0/query?geometry=&geometryType=esriGeometryEnvelope&inSR=&spatialRel=esriSpatialRelIntersects&relationParam=&objectIds=&where=+OBJECTID%3E%3D"
url2="+and+OBJECTID%3C%3D"
url3="&time=&returnCountOnly=false&returnIdsOnly=false&returnGeometry=true&maxAllowableOffset=&outSR=&outFields=*&f=pjson"
for i in `seq 1000 1000 200000`
do
	url=$url1$prev$url2$i$url3
	echo "generate shapefile from record $prev to record $i"
	prev=$i
	ogr2ogr $i.shp "$url" OGRGeoJSON
done
echo "merging shape files"
for f in `ls *.shp` 
do 
	ogr2ogr -update -append civici_umbria.shp $f  -f "ESRI Shapefile" -nln civici_umbria
done

