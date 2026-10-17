import folium
import ast
from pathlib import Path
from branca.element import MacroElement, Template

def numbered_pin_html(number, color):
    return f"""
    <div style="
        position: relative;
        width: 30px;
        height: 30px;
        background: {color};
        color: white;
        border-radius: 50% 50% 50% 0;
        transform: rotate(-45deg);
        text-align: center;
        line-height: 30px;
        font-weight: bold;
    ">
        <div style="
            transform: rotate(45deg);
            font-size: 14px;
        ">
            {number}
        </div>
    </div>
    """
    
    
def add_route_segment(map_obj, locations, distance, duration, color="blue", weight=3, opacity=0.8):
    folium.PolyLine(
        locations=locations,
        color=color,
        weight=4,
        opacity=opacity,
        popup=folium.Popup(popup_for_drives(distance, duration), max_width=300),
        tooltip=folium.Tooltip(popup_for_drives(distance, duration), sticky=True)
    ).add_to(map_obj)



def popup_for_places(location_name, link_titles, links, description):
    html_lines = [f"<b>{location_name}</b><br>"]
    
    if link_titles != '':
        html_lines += [f"{link_name}: <a href='{link}' target='_blank'>{link}</a><br>" for link_name, link in zip(link_titles, links)]
        
    html_lines += [f'{description}']
    html_content = "<br>".join(html_lines)  # Add line breaks
    return html_content


def popup_for_drives(distance, duration):
    html_lines = f'<b>Duration</b>: {duration} <br> <b>Distance</b>: {distance}'
    return html_lines


def _format_duration(total_seconds):
    total_minutes = int(round(total_seconds / 60))
    hours, minutes = divmod(total_minutes, 60)
    if hours and minutes:
        return f"{hours} h {minutes} min"
    if hours:
        return f"{hours} h"
    return f"{minutes} min"


def add_trip_summary(m, total_seconds, total_meters):
    """Whole-journey driving totals, as a map control in the top-left corner.
    Being a Leaflet control, it stacks below the zoom buttons instead of covering them."""
    if total_seconds <= 0:
        return

    summary = MacroElement()
    summary._name = "TripSummary"
    summary.html = (
        '<div style="font-weight: bold; color: #007BFF; margin-bottom: 2px;">Total drive</div>'
        f'{_format_duration(total_seconds)} &middot; {total_meters / 1000:,.0f} km'
    )
    summary._template = Template("""
        {% macro script(this, kwargs) %}
        (function () {
          var summary = L.control({ position: 'topleft' });
          summary.onAdd = function () {
            var box = L.DomUtil.create('div', 'trip-summary');
            box.id = 'trip-summary';
            box.style.cssText = 'background:white;padding:10px 14px;border-radius:8px;' +
              'box-shadow:0 2px 6px rgba(0,0,0,0.25);font:13px/1.4 Arial,sans-serif;color:#333';
            box.innerHTML = {{ this.html | tojson }};
            L.DomEvent.disableClickPropagation(box);
            return box;
          };
          summary.addTo({{ this._parent.get_name() }});
        })();
        {% endmacro %}
    """)
    m.add_child(summary)



def add_pin(m, trip, stop_doc_ids=None):
    markers = []
    stop_doc_ids = stop_doc_ids or {}

    for (i, place) in enumerate(trip.places.values()):
        if place.drive == 'y':
            marker = folium.Marker(
                location=[place.lat, place.lng],
                popup=folium.Popup(popup_for_places(place.nickname, place.link_titles, place.links, place.desc), max_width=300, auto_pan=False),
                icon=folium.DivIcon(html=numbered_pin_html(i + 1, place.colour), icon_size=(30, 30), icon_anchor=(15, 30))
            ).add_to(m)

        else:
            if place.place_type == 'sleep':
                icon = folium.Icon(icon="fa-solid fa-bed", prefix="fa", color=place.colour)
            else:
                # Default to a POI marker for any unknown/blank type.
                icon = folium.Icon(icon="info-sign", prefix="glyphicon", color=place.colour)

            marker = folium.Marker(
                location=[place.lat, place.lng],
                popup=folium.Popup(popup_for_places(place.nickname, place.link_titles, place.links, place.desc), max_width=300, auto_pan=False),
                icon=icon
            ).add_to(m)

        markers.append({"marker": marker, "doc_id": stop_doc_ids.get(str(place.id)),
                        "included": place.drive == "y"})
    return markers


def add_drive_controls(m, markers, map_id, owner_id, can_edit=True):
    """Enable marker hover panels and drive editing after all markers are rendered."""
    controls = MacroElement()
    controls._name = "DriveControls"
    controls.markers = markers
    controls.context = {"map_id": map_id, "owner_id": owner_id, "can_edit": can_edit}
    controls.script = (Path(__file__).resolve().parent.parent /
                       "static/js/map_drive_controls.js").read_text(encoding="utf-8")
    controls._template = Template("""
        {% macro script(this, kwargs) %}
        {{ this.script | safe }}
        attachDriveControls({{ this._parent.get_name() }}, [
          {% for stop in this.markers %}
          {marker: {{ stop.marker.get_name() }}, doc_id: {{ stop.doc_id | tojson }},
           included: {{ stop.included | tojson }}},
          {% endfor %}
        ], {{ this.context | tojson }});
        {% endmacro %}
    """)
    m.add_child(controls)


def add_offline_basemap(m):
    """When a downloaded map is opened from disk, swap the OpenStreetMap tiles
    (blocked there: no Referer) for OpenFreeMap. Online maps are unaffected."""
    basemap = MacroElement()
    basemap._name = "OfflineBasemap"
    basemap.script = (Path(__file__).resolve().parent.parent /
                      "static/js/offline_basemap.js").read_text(encoding="utf-8")
    basemap._template = Template("""
        {% macro script(this, kwargs) %}
        {{ this.script | safe }}
        useOfflineBasemap({{ this._parent.get_name() }});
        {% endmacro %}
    """)
    m.add_child(basemap)
