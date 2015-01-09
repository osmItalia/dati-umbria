from arcrestapi import ArcGIS
geoportal='http://geo.umbriaterritorio.it/ArcGIS/rest/services'
arcgis = ArcGIS(geoportal)
arcgis.discover()
for l in arcgis.layers:
	url = l['url']
	name= l['name']
	print name
	print url
	if l['querable']:
		arcgis.download(url,"dati_umbria.sqlite",name)

