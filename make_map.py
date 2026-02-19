import folium
import os
import googlemaps
import numpy as np
import tempfile

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Utility.plotting_functions import *
from Utility.html_edits import *
from Utility.classes import Place, RoadTrip
from Utility.utility_functions import *

from dotenv import load_dotenv


def generate_map(g):
    
    load_dotenv()
    
    start_id, lat, long = get_place_id(g.current_map['name'])
    
    # csv_name = f'C:\\Users\\samba\\Documents\\Python Scripts\\flaskmap\\{location}\\{location}_places.csv'
    # stops, pois, parking = load_filtered_trip_from_csv(csv_name)

    # Add colour to Place instances based on overnight or no
    # add_colours(stops)
        
    # Create map centered on the first location
    # coords = stops.get_all_coords()
    # start = np.mean(coords, axis=0)
    m = folium.Map(location=(lat, long), zoom_start=8)

    # Set up google maps
    # gmaps_key = os.environ.get('GOOGLE_MAPS_KEY', '')
    # gmaps = googlemaps.Client(key=gmaps_key)

    # Add pins
    # if parking.places != {}:
    #     add_pin(m, parking)
        
    # if stops.places != {}:
    #     add_pin(m, stops)
        
    # if pois.places != {}:
    #     add_pin(m, pois)
        
    # Drives
    # gmaps_ids = stops.get_all_gmapsids()
    # plot_drives(m, stops, gmaps_ids, coords)

    # Save the map
    # map_name = f'C:\\Users\\samba\\Documents\\Python Scripts\\flaskmap\\{location}\\{location}_roadmap.html'
    # m.save(map_name)
    
    tf = tempfile.NamedTemporaryFile(prefix=f"map_{g.current_map['id']}_", suffix=".html", delete=False)
    
    m.save(tf.name)
    
    insert_sidebar(tf.name)

    buttons = [
        ("Add Marker", f"/add_marker?map_id={g.current_map['id']}"),
        ("View Locations", f"/table?map_id={'test'}"),
        ("Reload map", f"/reload?map_id={'test'}")
    ]
    insert_buttons(tf.name, buttons)
    
    tf.close()
    
    return tf


if __name__ == '__main__':
    location = 'France'
    generate_map(location)