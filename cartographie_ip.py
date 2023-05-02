# coding: utf-8
import json
import requests
import ipaddress
import os
import folium

class LocalisationNotFound(Exception): pass

class Place:
    def __init__(self, nom:str, latitude:float, longitude:float, polygons:list=None, polygon_type:str=None):
        self.nom = nom
        self.longitude = float(longitude)
        self.latitude = float(latitude)
        self.coord = [self.latitude, self.longitude]
        self.set_polygons([] if polygons is None else polygons)
        self.polygon_type = polygon_type

    def set_polygons(self, polygons:list):
        self.polygons = polygons
        self.nb_polygons = len(polygons)
        self.nb_points = sum(len(polygon) for polygon in self.polygons)

    def __str__(self):
        res = f'Nom: \"{self.nom}\" | Latitude: {self.latitude} | Longitude: {self.longitude}'
        if self.polygons:
            res += f'| Polygones: {self.nb_polygons} | Points: {self.nb_points}'
        return res

class Localisation:
    openstreetmap_url = "https://nominatim.openstreetmap.org/search.php"
    geolocation_url = "https://geolocation-db.com/json/"

    def __init__(self, nom:str='', with_polygons:bool=False, zoom:int=18):
        if nom != '':
            query = f"?q={nom}" \
                    f"&polygon_geojson={int(with_polygons)}" \
                    f"&format=json" \
                    f"&zoom={zoom}"
            response = requests.get(Localisation.openstreetmap_url + query).json()

            # On enregistre la réponse dans un json, pour debugger
            with open('data/last_country.json', 'w', encoding='utf-8') as file:
                json.dump(response, file, indent=4)

            self.places = Localisation.format_places(response, with_polygons)
            self.nb_places = len(self.places)

    @staticmethod
    def format_places(responses:list, with_polygons:bool=False)->list[Place]:
        """ Méthode qui normalise les polygones de la réponse pour cette classe """
        places = []
        for response in responses:
            place = Place(response['display_name'], response['lat'], response['lon'])

            if not with_polygons:
                places.append(place)
                continue

            place.polygon_type = response['geojson']['type']
            geojson_data = response['geojson']['coordinates']
            if place.polygon_type == 'MultiPolygon':
                place.set_polygons([
                    [(point[1], point[0]) for point in polygon[0]]
                    for polygon in geojson_data
                ])
            elif place.polygon_type in ['Polygon', 'LineString']:
                place.set_polygons([[
                    (point[1], point[0])
                    for point in geojson_data[0]
                ]])
            elif place.polygon_type == 'Point':
                place.set_polygons([[(geojson_data[1], geojson_data[0])]])
            else:
                raise TypeError(f"Le type {place.polygon_type} est inconnu")
            places.append(place)

        return places

    @staticmethod
    def get_by_ip(ip:str):
        request_url = Localisation.geolocation_url + ip
        response = requests.get(request_url)
        content = response.json()
        if content['country_code'] == 'Not found':
            raise LocalisationNotFound(f"La localisation de l'IP {ip} est un échec")
        name = content['city'] if content['city'] is not None else content['country_name']
        return Localisation(name)

    def __str__(self):
        return '\n'.join(place.__str__() for place in self.places)

if __name__ == '__main__':
    url = input("Insérez un domaine:\n")
    # Récupération des adresses IP

    print("-------  Récupération des adresses IP -------")
    command = f"tracert -d -4 {url}"
    adresses = []
    for elem in os.popen(command):
        res = elem.strip().split(" ")[-1]
        try:
            ipaddress.ip_network(res)
            adresses.append(res)
            print(res)
        except ValueError: continue

    # Sauvegarde de la première localisation
    prevLocalisation = Localisation("Polytech Annecy")

    # Initialisation de la carte folium
    traceroute_map = folium.Map()

    # Initialisation de l'opacité des lignes de la carte
    # Les lignes sont de plus en plus foncés en s'approchant de la cible
    opacity = 0.1
    opacityInc = 1/len(adresses)


    # Rechercher de la localisation de chaque IP
    print("\n------- Recherche des localisations -------")
    for placeNumber, ip in enumerate(adresses):
        # Màj de la nouvelle localisation
        firstPrevPlace = prevLocalisation.places[0]

        try:
            newLocalisation = Localisation.get_by_ip(ip)
        except LocalisationNotFound as ex:
            print(f"{ip} n'a pas été trouvé")
            folium.Marker(
                firstPrevPlace.coord,
                popup=f"{placeNumber} : {ip} n'a pas été trouvé",
                icon=folium.Icon(color="black", icon="info-sign"),
                draggable=True
            ).add_to(traceroute_map)
            continue

        firstNewPlace = newLocalisation.places[0]

        print(f"{ip}, {newLocalisation.nb_places} places trouvés, {firstNewPlace.nb_polygons} polygones dans la première place")

        # Ajout de la ligne reliant prevLoc et newLoc sur la carte
        opacity += opacityInc
        folium.PolyLine(
            [firstPrevPlace.coord, firstNewPlace.coord],
            color="red",
            opacity=opacity
        ).add_to(traceroute_map)

        # Ajout d'un marker à newLoc
        folium.Marker(
            firstNewPlace.coord,
            popup=f"{placeNumber} : {firstNewPlace.nom.split(',')[0]}",
            icon=folium.Icon(color="red", icon="info-sign"),
            draggable=True
        ).add_to(traceroute_map)

        # Màj de l'ancienne localisation
        prevLocalisation = newLocalisation

    # Affichage de la carte
    traceroute_map.show_in_browser()
