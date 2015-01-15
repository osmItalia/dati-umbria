# dati-umbria
Fortemente ispirato da questo blog post http://blog.spaziogis.it/2014/12/29/take-the-best-use-the-rest/ ora è possibile scaricare dati dal servizio della Regione Umbria (e non solo)

### download_civici_umbria.sh 

si tratta di uno script bash che si appoggia a ogr2ogr che scarica i numeri civici della Regione Umbria proiettati in WGS84 in un file .shp

Il file in output al 29/12/2014 è disponibile qui
https://dl.dropboxusercontent.com/u/1969597/civici_umbria.zip

### download_dati_umbria.py 
lo script python si collega al servizio ArcGIS rest API della Regione Umbria e scarica tutti i layer vettoriali disponibili in un file spatialite.

Il risultato a 15/01/2015 è un file da 1.7Gb disponibile qui
http://bit.ly/1ATIyPC

dal file poi è possibile convertire qualsiasi layer in esso contenuto usando spatialite_gui o qgis o ogr2ogr
Un esempio con  ogr2ogr per i fabbricati in wgs84 (nome tabella 'fabbricati60')
```
ogr2ogr -f "ESRI Shapefile" fabbricati.shp dati_umbria.sqlite fabbricati60
```

## immagini
![fabbricati ](https://raw.githubusercontent.com/osmItalia/dati-umbria/master/img/fabbricato_umbria_wgs84.png)


