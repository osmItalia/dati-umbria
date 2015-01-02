from arcrestapi import ArcGIS
geoportal='http://geo.umbriaterritorio.it/ArcGIS/rest/services'
arcgis = ArcGIS(geoportal)
arcgis.discover()
for l in arcgis.layers:
    url = l['url']
    print l['name']
    print url
    arcgis.download(url,"dati_umbria.sqlite")

