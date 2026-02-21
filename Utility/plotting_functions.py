import folium
import ast

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
        popup=folium.Popup(popup_for_drives(distance, duration), max_width=300)
    ).add_to(map_obj)



def popup_for_places(location_name, link_titles, links, description):
    html_lines = [f"<b>{location_name}</b><br>"]
    link_titles = 'n'
    links = 'n'
    
    if link_titles != 'n':
        link_titles = ast.literal_eval(link_titles)
        links = ast.literal_eval(links)
        html_lines += [f"{link_name}: <a href='{link}' target='_blank'>{link}</a><br>" for link_name, link in zip(link_titles, links)]
        
    html_lines += [f'{description}']
    html_content = "<br>".join(html_lines)  # Add line breaks
    return html_content


def popup_for_drives(distance, duration):
    html_lines = f'<b>Duration</b>: {duration} <br> <b>Distance</b>: {distance}'
    return html_lines



def add_pin(m, trip):

    for (i, place) in enumerate(trip.places.values()):
        if place.drive == 'y':
            folium.Marker(
                location=[place.lat, place.lng],
                popup=folium.Popup(popup_for_places(place.nickname, place.link_titles, place.links, place.desc), max_width=300),
                icon=folium.DivIcon(html=numbered_pin_html(i + 1, place.colour), icon_size=(30, 30), icon_anchor=(15, 30))
            ).add_to(m)

        else:
            if place.place_type == 'poi':
                icon = folium.Icon(icon="info-sign", prefix="glyphicon", color=place.colour)

            if place.place_type == 'sleep':
                icon = folium.Icon(icon="fa-solid fa-bed", prefix="fa", color=place.colour)

            folium.Marker(
                location=[place.lat, place.lng],
                popup=folium.Popup(popup_for_places(place.nickname, place.link_titles, place.links, place.desc), max_width=300),
                icon=icon
            ).add_to(m)
            


    # keys = list(trip.places.keys())
    # symbol = trip.get_place(keys[0]).inc_drive
    
    # if symbol == 'y':
    #     for i, place in enumerate(trip.places.values()):
    #         folium.Marker(
    #             location=[place.lat, place.lng],
    #             popup=folium.Popup(popup_for_places(place.nickname, place.link_titles, place.links, place.desc), max_width=300),
    #             icon=folium.DivIcon(html=numbered_pin_html(i + 1, place.colour), icon_size=(30, 30), icon_anchor=(15, 30))
    #     ).add_to(m)
            
    # else:
    #     if symbol == 'n':
    #         icon = folium.Icon(icon="info-sign", prefix="glyphicon")
            
    #     else: # symbol=='p'
    #         icon = folium.DivIcon(html=numbered_pin_html('p', '#58AADE'), icon_size=(30, 30), icon_anchor=(15, 30))
            
    #     for i, place in enumerate(trip.places.values()):
    #         folium.Marker(
    #             location=[place.lat, place.lng],
    #             popup=folium.Popup(popup_for_places(place.nickname, place.link_titles, place.links, place.desc), max_width=300),
    #             icon=icon
    #     ).add_to(m)

                
        