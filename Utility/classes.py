
class Place:
    def __init__(self, id, name, desc, colour, drive, place_type, nickname, gmaps_id=None, lat=None, lng=None, link_titles='n', links='n'):
        self.id = id
        self.name = name
        self.desc = desc
        self.colour = colour
        self.drive = drive
        self.place_type = place_type
        if nickname == '': name = nickname
        self.nickname = nickname

        self.gmaps_id = gmaps_id
        self.lat = lat 
        self.lng = lng
        self.link_titles = link_titles
        self.links = links

    def __repr__(self):
        return f"Place({self.id}, {self.nickname}, {self.name}, {self.desc}, {self.place_type}, {self.drive}, {self.gmaps_id}, {self.lat}, {self.lng}, {self.colour})"
    
    def to_list(self):
        return [self.id, self.nickname, self.name, self.desc, self.place_type, self.drive, self.link_titles, self.links, self.colour]
    
    def to_dict(self):
        return {'id':self.id, 'nickname':self.nickname, 'name':self.name, 'desc':self.desc, 'place_type':self.place_type, 'drive':self.drive, 'gmaps_id':self.gmaps_id, 'lat':self.lat, 'lng':self.lng, 'colour':self.colour, 'link titles':self.link_titles, 'links':self.links}
    
    def add_geo_data(self, gmaps_id, lat, lng):
        self.gmaps_id = gmaps_id
        self.lat = lat
        self.lng = lng
        
    def add_colour(self, colour):
        self.colour = colour
        
    def add_links(self, link_titles, links):
        if type(link_titles) != list:
            link_titles = [link_titles]
            links = [links]
        self.link_titles = link_titles
        self.links = links
        


class RoadTrip:
    def __init__(self):
        self.places = {}  # key: name, value: Place instance
        self.places_by_id = {}

    def add_place(self, id, name, desc, colour, place_type, drive, nickname=None, gmaps_id=None, lat=None, lng=None, link_titles='n', links='n'):
        if nickname == None: nickname = name
        place = Place(id, name, desc, colour, place_type, drive, nickname, gmaps_id, lat, lng, link_titles, links)
        self.places[nickname] = place
        self.places_by_id[id] = place

    def get_place(self, tag):
        if type(tag) == int:
            return self.places_by_id.get(tag)
        else:
            return self.places.get(tag)
       

    def get_all_descs(self):
        return [place.desc for place in self.places.values()]
    
    def get_all_ids(self):
        return [place.id for place in self.places.values()]
    
    def get_all_gmapsids(self):
        return [place.gmaps_id for place in self.places.values()]
    
    def get_all_coords(self):
        return [[float(place.lat), float(place.lng)] for place in self.places.values()]
    
    def add_links_to_place(self, tag, link_titles, links):        
        if type(link_titles) != list:
            link_titles = [link_titles]
            links = [links] 
            
        if type(tag) == int:
            place = self.places_by_id.get(tag)
        else:
            place = self.places.get(tag)
        place.add_links(link_titles, links)
        
    
 
 
 