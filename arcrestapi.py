# -*- coding: utf-8 -*-
"""
Created on Tue Dec 30 15:11:49 2014

@author: Maurizio Napolitano <napo@fbk.eu>
"""

from bs4 import BeautifulSoup
import requests
import sqlite3

class ArcGIS:
    """
    A class that can download a layer from a map in an 
    ArcGIS web service and convert it to something useful,
    like GeoJSON.

    Usage:

    >>> import arcgis
    >>> source = "http://services.arcgis.com/P3ePLMYs2RVChkJx/ArcGIS/rest/services/USA_Congressional_Districts/FeatureServer"
    >>> arc = arcgis.ArcGIS(source)
    >>> layer_id = 0
    >>> shapes = arc.get(layer_id, "STATE_ABBR='IN'")

    This assumes you've inspected your ArcGIS services endpoint to know what to look for.
    ArcGIS DOES publish json files enumerating the endpoints you can query, so autodiscovery
    could be possible further down the line.

    """
    def __init__(self, url):
        self.url=url
        self._geom_parsers = {
            'esriGeometryPoint': self._parse_esri_point,
            'esriGeometryMultipoint': self._parse_esri_multipoint,
            'esriGeometryPolyline': self._parse_esri_polyline,
            'esriGeometryPolygon': self._parse_esri_polygon
        }      
        self.typefields = {
            'esriFieldTypeString': 'string',
            'esriFieldTypeInteger': 'integer',
            'esriFieldTypeSmallInteger': 'integer',
            'esriFieldTypeDouble': 'real',
            'esriFieldTypeSingle': 'real',
            'esriFieldTypeDate': 'timestamp',
            'esriFieldTypeOID': 'integer'
        }   
        self.layers = []
        self.discoverd = False

    def _parse_esri_point(self, geom):
        return {
            "type": "Point",
            "coordinates": [
                geom.get('x'),
                geom.get('y')
            ]
        }

    def _parse_esri_multipoint(self, geom):
        return {
            "type": "MultiPoint",
            "coordinates": geom.get('points')
        }

    def _parse_esri_polyline(self, geom):
        return {
            "type": "MultiLineString",
            "coordinates": geom.get('paths')
        }    

    def _parse_esri_polygon(self, geom):
        return {
            "type": "Polygon",
            "coordinates": geom.get('rings')
        }
 
    def _determine_geom_parser(self, type):
        return self._geom_parsers.get(type)

    def esri_to_geojson(self, obj, geom_parser):
        return {
            "type": "Feature",
            "properties": obj.get('attributes'),
            "geometry": geom_parser(obj.get('geometry'))
        }

    def _addlayers(self,url,response):
        services=response.get('services')
        folders=response.get('folders')
        if services is not None:
            if len(services) > 0:
                self._discoverservices(url,services)
        if folders is not None:
            if len(folders) > 0:
                self._discoverfolders(url,folders)
    
    def _discoverservices(self,url,services):
        for service in services:
            if service['type']=='MapServer':
                name = service['name'].split("/")
                urllayers = url + "/" +  name.pop() + "/MapServer/layers"
                layers = requests.get(urllayers,params={'f': 'pjson'}).json()
                if len(layers) > 0:
                    for layer in layers['layers']:                            
                            if (layer['type']=='Feature Layer'):
                                layerurl = urllayers.replace('layers','')+str(layer['id'])
                                #layerurl = url + "/" +  name.pop() + str(layer['id'])
                                if self.querable(layerurl):
                                    datalayer = {}
                                    if (layer['type']=='Feature Layer'):
                                        datalayer['url']=layerurl
                                        datalayer['name']=layer['name']
                                        datalayer['folder']=url.replace(self.url,"")
                                        datalayer['properties']=layer
                                        self.layers.append(datalayer)

    def _discoverfolders(self,url,folders):
        for folder in folders:
            furl = urljoin(url,folder)
            response = requests.get(furl,params={'f': 'pjson'}).json()
            self._addlayers(furl,response)
            
    def discover(self):
        self.discoverd = True
        response = requests.get(urljoin(self.url),params={'f': 'pjson'}).json()
        self.currentversion = response['currentVersion']
        self._addlayers(self.url,response)

    def querable(self,url):
        q = False
        links = BeautifulSoup(requests.get(url).text).findAll("a")
        for l in links:
            if l.getText()=='Query':
                q = True
                break
        return q

    def countfeatures(self,url):
        url = url + "/query"
        params={}
        params['where']='1=1'
        params['f']='pjson'
        params['returnCountOnly']='true'
        return int(requests.get(url,params=params).json()['count'])
    
    def download(self,url,dbout):
        name = requests.get(url,params={'f':'pjson'}).json()['name']
        name = name.replace("-","_")
        name = name.replace(" ","_")
        name = name.replace("__","_")
        url = url + "/query"
        alldata = []
        for obj in range (1,self.countfeatures(url),1000):
            left=obj
            right=obj+999
            where = "OBJECTID>=%s and OBJECTID<=%s" % (left,right)
            params={}
            params['where']=where
            params['f']='pjson'    
            params['returnGeometry']='true'
            data = requests.get(url,params=params).json()
            alldata.append(data)
        self._insertdata(name,alldata,dbout)
    
    def writedata(self,dbout):
        conn = sqlite3.connect(dbout) 
        conn.enable_load_extension(True)
        cur = conn.cursor()
        cur.execute("SELECT load_extension('mod_spatialite');")
        cur.execute("SELECT InitSpatialMetadata();")
    
    def _createtable(self,name,fields):
        create="CREATE TABLE IF NOT EXISTS "+ name +" ("
        for field in fields:
            create += field['name']+' '+self.typefields[field['type']] + ','
        create=create.rstrip(",")
        create+=");"
        return create
        
    def _addgeometrycolumn(self,name,data):
        sql = "SELECT AddGeometryColumn('%s','geometry', %s, '%s','XY');" % (name,data[0]['spatialReference']['wkid'],data[0]['geometryType'].replace('esriGeometry',''))
        return sql
            
    def _insertdata(self,name,data,dbout):
        if (data[0].has_key("geometryType")):
            srid = str(data[0]["spatialReference"]["wkid"])
            geomtype = data[0]["geometryType"].replace("esriGeometry","")
            create = self._createtable(name,data[0]["fields"])
            add = self._addgeometrycolumn(name,data)
            con=sqlite3.connect(dbout)        
            con.enable_load_extension(True)
            cur = con.cursor()
            cur.execute('SELECT load_extension("mod_spatialite")');
            cur.execute('SELECT InitSpatialMetadata();')
            cur.execute(create)
            cur.execute(add)
            cur.execute('BEGIN;')
            for d in data:
                geometries=[]
                features=d["features"]
                for f in features:
                    sql = ""
                    sql1="INSERT INTO %s (" % name
                    sql2 = ""
                    sql3 = ""
                    if (geomtype.upper() == 'POLYGON'): 
                        rings=[]
                        coordinates = f["geometry"]["rings"]
                        for points in coordinates:
                            strring = ''
                            for ring in points:
                                 strring+='%s %s,' % (tuple(ring))
                            strring = strring.rstrip(",")
                            rings.append(strring)
                        geometry='GeometryFromText("'+geomtype+'('
                        for ring in rings:
                            geometry +='(%s)' % ring
                        geometry += ')",%s)' % srid
                        geometries.append(geometry)

                    if (geomtype.upper() == "POLYLINE"):
                        paths=[]
                        coordinates = f["geometry"]["paths"]
                        for points in coordinates:
                            strring = ''
                            for path in points:
                                 strring+='%s %s,' % (tuple(path))
                            strring = strring.rstrip(",")
                            paths.append(strring)
                        geometry='GeometryFromText("LINESTRING('
                        for ring in paths:
                            geometry +='('+ ring+')'
                        geometry += ')",%s)' % srid
                        geometries.append(geometry)                        
                        
                    if (geomtype.upper() == "POINT"):
                        x = f["geometry"]["x"]
                        y = f["geometry"]["y"]
                        geometry="GeometryFromText('POINT(%s %s)',%s)" % (x,y,srid)
                        
                    for field in f["attributes"].items():
                        sql2 +='"%s",' % field[0]
                        v = field[1]
                        if isinstance(v, unicode):
                            v=v.replace('"','')
                        sql3+='"%s",' % v
                    sql2+='"geometry") VALUES ('
                    sql3+=geometry+');'
                    sql = sql1+sql2+sql3
                    cur.execute(sql)
            #cur.execute('COMMIT;')        
            con.commit()
        
        
    def isarcgisrest(self,url):
        isrest=True
        if (url.find('ArcGIS/rest')==-1):
            isrest=False
        return isrest

def urljoin(*args):
    """
    There's probably a better way of handling this.
    """
    return "/".join(map(lambda x: str(x).rstrip('/'), args))
