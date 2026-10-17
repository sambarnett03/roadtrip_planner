import os
import re
from pathlib import Path
import unittest
from unittest.mock import patch

import folium
from flask import Flask
from Utility.classes import Place, RoadTrip
from Utility.plotting_functions import add_pin, add_drive_controls, add_route_segment, add_trip_summary


class MapHoverTests(unittest.TestCase):
    def test_all_marker_types_get_their_document_ids_and_drive_state(self):
        trip = RoadTrip()
        for number, drive, kind in [(1, 'y', 'poi'), (2, 'n', 'poi'), (3, 'n', 'sleep')]:
            trip.places[str(number)] = Place(number, 'Stop', 'Description', 'blue', drive,
                                             kind, str(number), lat=51.5, lng=-0.1)
        m = folium.Map(location=[51.5, -0.1])
        markers = add_pin(m, trip, {'1': 'first-doc', '2': 'second-doc', '3': 'third-doc'})
        self.assertEqual([stop['doc_id'] for stop in markers], ['first-doc', 'second-doc', 'third-doc'])
        self.assertEqual([stop['included'] for stop in markers], [True, False, False])
        add_drive_controls(m, markers, 'trip', 'owner', can_edit=False)
        html = m.get_root().render()
        self.assertIn('"can_edit": false', html)
        self.assertIn('"third-doc"', html)
        self.assertIn('function attachDriveControls(', html)
        self.assertIn('"autoPan": false', html)
        self.assertLess(html.index('.bindPopup('), html.index('attachDriveControls(map_'))

    def test_each_route_leg_has_hover_and_click_details(self):
        m = folium.Map(location=[51.5, -0.1])
        add_route_segment(m, [[51.5, -0.1], [51.51, -0.08]], '4.2 km', '12 mins')
        add_route_segment(m, [[51.51, -0.08], [51.52, -0.07]], '7 km', '5 mins')
        html = m.get_root().render()
        self.assertEqual(html.count('.bindTooltip('), 2)
        self.assertEqual(html.count('.bindPopup('), 2)
        for text in ['4.2 km', '12 mins', '7 km', '5 mins']:
            self.assertEqual(html.count(text), 2)

    def test_trip_summary_is_a_map_control_below_the_zoom_buttons(self):
        # A Leaflet control in the zoom buttons' corner stacks under them instead of
        # covering them (the old fixed-position box hid the +/- buttons).
        m = folium.Map(location=[51.5, -0.1])
        add_trip_summary(m, 2 * 3600 + 11 * 60, 185_000)
        html = m.get_root().render()
        self.assertIn("L.control({ position: 'topleft' })", html)
        self.assertIn('2 h 11 min \\u0026middot; 185 km', html)
        empty = folium.Map(location=[51.5, -0.1])
        add_trip_summary(empty, 0, 0)
        self.assertNotIn('trip-summary', empty.get_root().render())

    def test_generate_map_embeds_controls_in_online_and_download_versions(self):
        with patch.dict(os.environ, {'GOOGLE_MAPS_KEY': 'AIza' + 'x' * 35}):
            from make_map import generate_map
        rows = [{'_doc_id': 'firestore-stop', 'id': 1, 'name': 'Stop', 'desc': '',
                 'colour': 'blue', 'drive': 'n', 'place_type': 'sleep', 'nickname': 'Stop',
                 'gmaps_id': 'fake-place', 'lat': 51.5, 'lng': -0.1, 'link_titles': '', 'links': ''}]
        app = Flask(__name__)
        app.secret_key = 'test-secret'
        with app.test_request_context(), patch('make_map.googlemaps.Client'), patch('make_map.plot_drives'):
            from flask import session
            result = generate_map('trip', 'owner', rows, can_edit=False)
            downloaded_path = Path(session['last_map_path'])
            online_path = Path(result.name)
            try:
                for path in (downloaded_path, online_path):
                    html = path.read_text()
                    self.assertIn('doc_id: "firestore-stop"', html)
                    self.assertIn('"can_edit": false', html)
                    self.assertIn("window.location.protocol === 'file:'", html)
                    # Downloaded copies swap OSM's tiles (blocked from file://) for OpenFreeMap.
                    self.assertIn('useOfflineBasemap(map_', html)
                    # Each folium save re-adds the tile layer at the end of the script;
                    # saving twice put OSM back after the swap in the download copy.
                    tile = re.search(r'var (tile_layer_\w+) = L\.tileLayer', html).group(1)
                    self.assertEqual(html.count(tile + '.addTo('), 1)
            finally:
                online_path.unlink()
                downloaded_path.unlink()


if __name__ == '__main__':
    unittest.main()
