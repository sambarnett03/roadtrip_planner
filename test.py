a = [{'desc': 'descriptiontest', 'link titles': None, 'lng': 12.4822025, 'links': None, 'inc_drive': 'y', 'nickname': '', 'lat': 41.8967068, 'name': 'Rome', 'gmaps_id': 'ChIJu46S-ZZhLxMROG5lkwZ3D7k', 'colour': None, 'id': 1, 'on': 'y'}, {'inc_drive': 'y', 'links': None, 'link titles': None, 'desc': 'saav', 'lng': 12.3159547, 'nickname': '', 'lat': 45.440379, 'name': 'Venice', 'gmaps_id': 'ChIJiT3W8dqxfkcRLxCSvfDGo3s', 'colour': None, 'id': 1, 'on': 'y'}]


for row in a:
    print(row)
    print('----------------------')

    if row['inc_drive'] == 'y':
        print('ya')