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
from flask import session


def generate_map(map_id, owner_id, rows):
    
    load_dotenv()
    
    if rows == []:
        m = folium.Map(location=(30, 10), zoom_start=3)

    else:
        all_stops, driving_stops, other_stops = load_from_fb_format(rows)
        
        # Create map centered on the first location
        coords = all_stops.get_all_coords()
        start = np.mean(coords, axis=0)
        m = folium.Map(location=start, zoom_start=8)

        # Set up google maps
        gmaps_key = os.environ.get('GOOGLE_MAPS_KEY', '')
        gmaps = googlemaps.Client(key=gmaps_key)

        # Add pins
        if driving_stops.places != {}:
            add_pin(m, driving_stops)

        if other_stops.places != {}:
            add_pin(m, other_stops)

        # Drives
        gmaps_ids = driving_stops.get_all_gmapsids()
        plot_drives(m, driving_stops, gmaps_ids, coords)

    tf = tempfile.NamedTemporaryFile(prefix=f"map_{map_id}_", suffix=".html", delete=False)
    tf_no_buttons = tempfile.NamedTemporaryFile(prefix=f"map_{map_id}_no_buttons_", suffix=".html", delete=False)
    
    m.save(tf.name)
    m.save(tf_no_buttons.name)

    session['last_map_path'] = tf_no_buttons.name

    fb_config = {
        "apiKey": os.environ.get('FIREBASE_API_KEY'),
        "authDomain": os.environ.get('FIREBASE_AUTH_DOMAIN'),
        "projectId": os.environ.get('FIREBASE_PROJECT_ID'),
        "storageBucket": os.environ.get('FIREBASE_STORAGE_BUCKET'),
        "messagingSenderId": os.environ.get('FIREBASE_MESSAGING_SENDER_ID'),
        "appId": os.environ.get('FIREBASE_APP_ID')
    }

    insert_sidebar(tf_no_buttons.name, map_id, owner_id, firebase_config=fb_config)
    insert_sidebar(tf.name, map_id, owner_id, firebase_config=fb_config)

    buttons = [
        ("Add Marker", f"/add_marker?map_id={map_id}"),
        ("View Locations", "/stops"),
        ("Collaborators", "/collaborate"),
        ('Download map', '/download_current_map'),
        ("See All Roadtrips", "/roadtrips"),
        ("Sign out", "/sign_out")
    ]
    insert_buttons(tf.name, buttons)
    
    tf.close()
    
    return tf


if __name__ == '__main__':
    location = 'France'
    generate_map(location)