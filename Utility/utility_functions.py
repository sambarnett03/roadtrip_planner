import googlemaps
import os
import csv
import sys
import polyline
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Utility.classes import *
from Utility.plotting_functions import *

from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)
gmaps_key = os.environ.get('GOOGLE_MAPS_KEY', '')
gmaps = googlemaps.Client(key=gmaps_key)



def get_place_id(place_name): 
    result = gmaps.find_place(
        input=place_name,
        input_type='textquery',
        fields=['place_id', 'geometry']
    )
    
    candidates = result.get('candidates', [])
    if not candidates:
        raise Exception(f"No place found for '{place_name}'")
    
    location = candidates[0]['geometry']['location']
    lat = location['lat']
    lng = location['lng']

    return candidates[0]['place_id'], lat, lng


def write_to_csv(trip, filename):
    csv_filename = os.path.join(os.getcwd(), filename)

    with open(csv_filename, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["Location ID", "Nickname", "Name", 'Description', 'Overnight', "Include Drive", 'Link Titles', 'Links', "Gmaps ID", "Latitude", "Longitude"])  # header

        for place in trip.places.values():
            loc_id, lat, lng = get_place_id(place.name)
            place.add_geo_data(loc_id, lat, lng)
            if loc_id:  
                writer.writerow(place.to_list() + [loc_id, lat, lng])
                
                
                
                
                

def add_colours(stops):
    for place in stops.places.values():
        if place.on == 'n': place.add_colour('blue')
        else: place.add_colour('black')
    return

    
    
def get_distance(loc_ids, i, mode='driving'):
    if i == 'final':
        i = -1
        j = 0
    else:
        j = i + 1
    origin_id = loc_ids[i]
    destination_id = loc_ids[j]
    
    result = gmaps.distance_matrix(
        origins=[f'place_id:{origin_id}'],
        destinations=[f'place_id:{destination_id}'],
        mode='driving',
        units='metric'
    )

    if result['rows'][0]['elements'][0]['status'] == 'ZERO_RESULTS':
        duration = 'na'
        distance = 'na'
        
    else:
        duration = result['rows'][0]['elements'][0]['duration']['text']
        distance = result['rows'][0]['elements'][0]['distance']['text']
        
    directions = gmaps.directions(
        origin=f"place_id:{origin_id}",
        destination=f"place_id:{destination_id}",
        mode="driving")
        
    if directions:
        # Extract and decode the route polyline
        route_polyline = directions[0]['overview_polyline']['points']
        decoded_route = polyline.decode(route_polyline)
        route_type = "actual"
    else:
        decoded_route = 'failed'
    
    return distance, duration, decoded_route


    
    
def plot_drives(m, stops, gmaps_ids, coords):
    for i in range(len(stops.places.values())):
        if i + 1 < len(stops.places.keys()):
            distance, duration, decoded_route = get_distance(gmaps_ids, i)
            if decoded_route == 'failed':
                add_route_segment(m, [coords[i], coords[i+1]], distance, duration)
            else:
                add_route_segment(m, decoded_route, distance, duration)
            
        else:
            distance, duration, decoded_route = get_distance(gmaps_ids, 'final')
            if decoded_route == 'failed':
                add_route_segment(m, [coords[i], coords[i+1]], distance, duration)
            else:
                add_route_segment(m, decoded_route, distance, duration)
        
    return
    
    
    

def load_from_fb_format(rows):
    stops = RoadTrip()
    pois = RoadTrip()
    parking = RoadTrip()
    for row in rows:
        if row['inc_drive'] == 'y':
            print('nickname', row['nickname'])
            stops.add_place(int(row["id"]), row["name"], row["desc"], row['on'], row['inc_drive'], row['nickname'], row['gmaps_id'], row['lat'], row['lng'], row['link titles'], row['links'])
        elif row['inc_drive'] == 'p':
            parking.add_place(int(row["id"]), row["name"], row["desc"], row['on'], row['inc_drive'], row['nickname'], row['gmaps_id'], row['lat'], row['lng'], row['link titles'], row['links'])
        else:
            pois.add_place(int(row["id"]), row["name"], row["desc"], row['on'], row['inc_drive'], row['nickname'], row['gmaps_id'], row['lat'], row['lng'], row['link titles'], row['links'])
            
    return stops, pois, parking 
    
    
def load_trip_from_csv(filename):
    trip = RoadTrip()
    with open(filename, 'r', encoding="cp1252") as f:
        reader = csv.DictReader(f)
        for row in reader:
            trip.add_place(int(row["Location ID"]), row["Name"], row["Description"], row['Overnight'], row['Include Drive'], row['Nickname'], row['Gmaps ID'], row['Latitude'], row['Longitude'], row['Link Titles'], row['Links'])

    return trip
