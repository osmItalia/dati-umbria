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
    A class to inspect a ArcGIS web service and convert a layer
    in a spatialite database
    
    Usage:

    >>> from arcrestapi import ArcGIS
    >>> source = "http://geo.umbriaterritorio.it/ArcGIS/rest/services"
    >>> arcgis = ArcGIS(source)
    >>> arcgis.discover() 
    >>> for layer in arcgis.layers:
    >>>    if layer['querable']:
    >>>         url=layer['url']
    >>>         name=layer['name']
    >>>         arcgis.download(url,"dati_umbria.sqlite",name) 
    
    this class inspired by 
    https://github.com/Schwanksta/python-arcgis-rest-query

    """
    def __init__(self, url):
        self.url=url    
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

    def _addlayers(self,url,response):
        services=response.get('services')
        folders=response.get('folders')
        if services is not None:
            if len(services) > 0:
                self._discoverservices(url,services)
        if folders is not None:
            if len(folders) > 0:
                self._discoverfolders(url,folders)
    
    def _replaceduplicate(self,name):
        k = 1
        names = []
        name = self._cleanname(name)
        nwname = name
        for l in self.layers:
            names.append(l['name'])
        while (nwname in names):
            for n in names:
                if n==nwname:
                    nwname=name+str(k)			
                else:
                    k=k+1  
        name = nwname
        return name
        
    def _discoverservices(self,url,services):
        for service in services:
            if service['type']=='MapServer':
                name = service['name'].split("/")
                urllayers = url + "/" +  name.pop() + "/MapServer/layers"
                layers = requests.get(urllayers,params={'f': 'pjson'}).json()
                if len(layers) > 0:
                    for layer in layers['layers']:                            
                        layerurl = urllayers.replace('layers','')+str(layer['id'])
                        datalayer = {}
                        datalayer['url']=layerurl
                        datalayer['name']=self._replaceduplicate(layer['name'])
                        datalayer['folder']=url.replace(self.url,"")
                        datalayer['properties']=layer
                        datalayer['querable']=self.querable(layerurl)
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

    def _cleanname(self,name):
        name = name.strip()
        name = name.replace("-","_")
        name = name.replace("  "," ")
        name = name.replace(" ","_")
        name = name.replace("__","_")
        name = name.replace(")","")
        name = name.replace("(","")
        name = name.replace("__","_")
        name = name.replace(",","")
        name = name.replace(";","")
        name = name.replace(",","")
        name = name.lower()
        return name
        
    def download(self,url,dbout,name=None,left=None,right=None):
        if name is None:
            name = requests.get(url,params={'f':'pjson'}).json()['name']
            name = self._cleanname(name)
        url = url + "/query"
        alldata = []
        totalrecords = self.countfeatures(url)
        if totalrecords == 1:
            totalrecords = 2
        if (left is None and right is None):
            for obj in range (1,totalrecords,1000):
                left=obj
                right=obj+999
                where = "OBJECTID>=%s and OBJECTID<=%s" % (left,right)
                params={}
                params['where']=where
                params['f']='pjson'    
                params['returnGeometry']='true'
                data = requests.get(url,params=params).json()
                alldata.append(data)
        else:
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
            field = self._cleanname(field)
            create += field['name']+' '+self.typefields[field['type']] + ','
        create=create.rstrip(",")
        create+=");"
        return create
        
    def _addgeometrycolumn(self,name,data):
        srid = data[0]['spatialReference']['wkid']
        geometrytype = data[0]['geometryType'].replace('esriGeometry','')
        if geometrytype.upper() == "POLYLINE":
            geometrytype = "LineString"
        sql = "SELECT AddGeometryColumn('%s','geometry', %s, '%s','XY');" % (name,srid,geometrytype)
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
                            geometry += ring
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
    return "/".join(map(lambda x: str(x).rstrip('/'), args))
