# -*- coding: utf-8 -*-
"""
region.py
Class for region, esentially the master model
"""
import engine
import protocol_pb2 as proto
import city
import Image
import base64, math
import StringIO
import users

class Region(engine.Entity):
    def __init__(self):
        self.accept("generateRegion", self.generate)
        self.accept("newCityRequest", self.newCity)
        self.accept("sendGameState", self.sendGameState)
        self.name = "Region"
        # Dict to use cityid as quick lookup
        self.cities = {}
        # Arbatary city limit. End user can set this
        self.city_limit = 32
        self.tiles = []
        self.terrainTextureDB = {}
        self.width= 0
        self.height = 0

    #def generate(self, hightMapPath=None, colorMapPath=None, cityMapPath=None, terrainTextureDB=None):
    def generate(self, name, heightmap):
        """
        Generates region
        heightmap is a string for grayscale bitmap for heigh
        TODO: Heightmap should be an image object instead
        colormap is color bitmap for terrain texture
        terrainTextureDB is data on texture to use for color map
        """
        self.heightmap = heightmap
        heightmapBuffer = StringIO.StringIO(self.heightmap)
        heightmapImage = Image.open(heightmapBuffer)
        self.width, self.height = heightmapImage.size
        # Image is 1 px more than number of tiles
        self.width -= 1
        self.height -= 1
        self.name = name
        # Generate the simulation tiles
        tileid = 0
        for x in range(self.width):
            for y in range(self.height):
                tile = Tile(tileid, coords=(x,y))
                self.tiles.append(tile)
                tileid+= 1
        print "Region created with", len(self.tiles), "tiles."
        
        # Other generations such as initial roads, etc, is done here
        self.sendGameState()
    
    def sendGameState(self):
        '''Sends game state. Requires full simulation pause while in progress.
        In this region package tiles are sent by changes in city id. No other data needs to be sent until a city is activated.
        '''
        messenger.send("setServerState", [1])
        container = proto.Container()
        container.gameState.name = self.name
        container.gameState.heightmap = base64.b64encode(self.heightmap)
        # Used to check for change
        tilecityid = -1
        for tile in self.tiles:
            if tile.cityid != tilecityid:
                tilecityid = tile.cityid
                t = container.gameState.tiles.add()
                t.id = tile.id
                t.positionx = tile.coords[0]
                t.positiony = tile.coords[1]
                t.cityid = tile.cityid
        
        for id, city in self.cities:
            c = container.gameState.cities.add()
            c.id = id
        
        messenger.send("broadcastData", [container])
        # TODO: Create method to return to previous server state after we finished sending
    
    def getCityTiles(self, cityid):
        '''Returns tiles for a particular city.'''
        # Itterate, yuck and slow. Thankfully this should only be called when a city loads
        cityTiles = []
        for tile in self.tiles:
            if tile.cityid is cityid:
                cityTiles.append(tile)
        return cityTiles
    
    def getTile(self, x, y):
        '''Returns tile by coordinate. Thankfully smart enough to find a way to not iterate'''
        value = y * self.width + x
        return self.tiles[value]
    
    def loadCity(self, cityKey, playerName, password=""):
        """
        loads a city based on cityKey
        """
        self.cities[cityKey].login(playerName, password="")
    
    def newCity(self, peer, info):
        '''Checks to make sure city location is valid. If so we establish city!'''
        for x in range(0, 32):
            for y in range(0,32):
                tile = self.getTile(info.positionx+x, info.positiony+y)
                if tile.cityid:
                    container = proto.Container()
                    container.newCityResponse.type = 0
                    container.newCityResponse.message = "A city already claims tile " + str(info.positionx+x, info.positiony+y)
                    messenger.send("sendData", [peer, container])
        
        # Grab next free id. If we are at region city limit then no build!
        cityids = self.cities.keys()
        cityid = 0
        for n in range(0, self.city_limit):
            if n not in cityids:
                cityid = n
                break
        else:
            container = proto.Container()
            container.newCityResponse.type = 0
            container.newCityResponse.message = "This region has reached its max limit of  " + str(self.city_limit) + " cities."
            messenger.send("sendData", [peer, container])
        
        # Passed the test! Time to found!
        user = users.getNameFromPeer(peer)
        newcity = city.City(info.name, cityid, mayor = user)
        self.cities[cityid] = newcity
        
        for x in range(0, 32):
            for y in range(0,32):
                tile = self.getTile(info.positionx+x, info.positiony+y)
                tile.cityid = cityid
        
        container = proto.Container()
        container.newCityResponse.type = 1
        messenger.send("sendData", [peer, container])
        print info.name, "founded!"
        
        container = proto.Container()
        container.newCity.id = cityid
        container.newCity.name = info.name
        container.newCity.mayor = user
        container.newCity.population = newcity.population
        container.newCity.money = newcity.money
        messenger.send("broadcastData", [container])


class Tile(object):
    """
    Basic tile in simulation. Stores stuff
    """
    def __init__(self, id, cityid=0, coords = (0,0)):
        """
        id: id number of tile
        cityid: id number of the city that owns the tile.
        """
        # TODO: Make thread safe
        self.id = id
        self.cityid = cityid
        self.coords = coords