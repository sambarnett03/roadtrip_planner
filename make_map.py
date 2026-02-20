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


def generate_map(map_id, rows):
    
    load_dotenv()
    
    if rows == []:
        m = folium.Map(location=(30, 10), zoom_start=3)

    else:
        stops, pois, parking = load_from_fb_format(rows)

        print(stops.places_by_id)
        print(stops.places)
        
    
        
        # Add colour to Place instances based on overnight or no
        add_colours(stops)
            
        # Create map centered on the first location
        coords = stops.get_all_coords()
        start = np.mean(coords, axis=0)
        m = folium.Map(location=start, zoom_start=8)

        # Set up google maps
        gmaps_key = os.environ.get('GOOGLE_MAPS_KEY', '')
        gmaps = googlemaps.Client(key=gmaps_key)

        # Add pins
        if parking.places != {}:
            add_pin(m, parking)
            
        if stops.places != {}:
            add_pin(m, stops)
         
        if pois.places != {}:
            add_pin(m, pois)
           

        # Drives
        gmaps_ids = stops.get_all_gmapsids()
        plot_drives(m, stops, gmaps_ids, coords)

    tf = tempfile.NamedTemporaryFile(prefix=f"map_{map_id}_", suffix=".html", delete=False)
    
    m.save(tf.name)
    

    buttons = [
        ("Add Marker", f"/add_marker?map_id={map_id}"),
        ("View Locations", "/stops"),
        ("Collaborators", "/collaborate"),
        ("See All Roadtrips", "/roadtrips"),
        ("Sign out", "/sign_out")
    ]
    insert_buttons(tf.name, buttons)
    
    tf.close()
    
    return tf


if __name__ == '__main__':
    location = 'France'
    generate_map(location)