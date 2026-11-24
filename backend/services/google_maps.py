import json
from http.client import HTTPException, HTTPSConnection

from flask import current_app
from werkzeug.exceptions import BadGateway, GatewayTimeout, ServiceUnavailable


ROUTE_FIELDS = "routes.duration,routes.distanceMeters,routes.polyline,routes.viewport,routes.warnings"
PLACE_TYPES = {
    "parking": ["parking", "park_and_ride"],
    "transit": ["transit_station", "bus_stop", "train_station", "subway_station", "light_rail_station"],
    "cafe": ["cafe"],
    "restaurant": ["restaurant"],
}


def google_post(host, path, body, fields, result_key):
    key = current_app.config["GOOGLE_MAPS_API_KEY"]
    if not key:
        raise ServiceUnavailable("Google Maps is not configured.")
    connection = HTTPSConnection(host, timeout=8)
    try:
        connection.request("POST", path, body=json.dumps(body), headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": key,
            "X-Goog-FieldMask": fields,
        })
        response = connection.getresponse()
        if response.status in (401, 403, 429):
            raise ServiceUnavailable("Google Maps access or quota is unavailable.")
        if response.status != 200:
            raise BadGateway("Google Maps could not complete the request.")
        data = json.loads(response.read())
    except TimeoutError:
        raise GatewayTimeout("Google Maps timed out.") from None
    except (OSError, HTTPException, ValueError):
        raise BadGateway("Invalid or unavailable Google Maps response.") from None
    finally:
        connection.close()

    # Google omits empty repeated fields when no route or place matches.
    items = data.get(result_key, []) if isinstance(data, dict) else None
    if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
        raise BadGateway("Invalid Google Maps response.")
    return items


def waypoint(position):
    if isinstance(position, str):
        return {"address": position}
    return {"location": {"latLng": {"latitude": position["lat"], "longitude": position["lng"]}}}


def compute_routes(origin, destination, mode="DRIVE", *, intermediate=(), optimize=False,
                   alternatives=False, steps=False):
    body = {"origin": waypoint(origin), "destination": waypoint(destination), "travelMode": mode}
    fields = ROUTE_FIELDS
    if mode == "DRIVE":
        body["routingPreference"] = "TRAFFIC_AWARE"
    if intermediate:
        body["intermediates"] = [waypoint(stop) for stop in intermediate]
    if alternatives:
        body["computeAlternativeRoutes"] = True
    if optimize:
        body["optimizeWaypointOrder"] = True
        fields += ",routes.optimizedIntermediateWaypointIndex"
    if steps:
        fields += ",routes.legs.steps.navigationInstruction,routes.legs.steps.transitDetails,routes.legs.steps.travelMode"
    return google_post("routes.googleapis.com", "/directions/v2:computeRoutes", body, fields, "routes")


def nearby_places(center, category):
    body = {
        "includedTypes": PLACE_TYPES[category],
        "maxResultCount": 8,
        "rankPreference": "DISTANCE",
        "locationRestriction": {"circle": {
            "center": {"latitude": center["lat"], "longitude": center["lng"]}, "radius": 1000,
        }},
    }
    fields = "places.id,places.displayName,places.location,places.formattedAddress,places.googleMapsUri,places.attributions"
    if category == "parking":
        fields += ",places.parkingOptions"
    return google_post("places.googleapis.com", "/v1/places:searchNearby", body, fields, "places")
