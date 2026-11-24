from math import asin, cos, radians, sin, sqrt

from flask import Blueprint, current_app, request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from werkzeug.exceptions import BadGateway, BadRequest, HTTPException, NotFound, UnprocessableEntity

from backend.database import db
from backend.services import google_maps


maps_api = Blueprint("maps", __name__, url_prefix="/api/map")


def rows(sql, **params):
    return db.session.execute(text(sql), params).mappings()


def point(row):
    return {"lat": float(row["latitude"]), "lng": float(row["longitude"])}


@maps_api.errorhandler(SQLAlchemyError)
def data_unavailable(error):
    db.session.rollback()
    current_app.logger.error("Map database read failed (%s)", type(error).__name__)
    return {"error": "Shuttle data is unavailable. Check the database connection and schema."}, 503


@maps_api.get("/network")
def network():
    hubs = [
        {
            "id": str(row["id"]), "name": row["name"], "type": row["type"],
            "address": row["address"], "position": point(row),
            "parking": row["parking_notes"], "bikeParking": row["bike_parking_notes"],
        }
        for row in rows("""
            SELECT id, type, name, address, latitude, longitude, parking_notes, bike_parking_notes
            FROM pickup_locations ORDER BY name, id
        """)
    ]
    routes = {}
    for row in rows("""
        SELECT r.id, r.shuttle_id, r.pickup_location_id, r.departure_time, r.arrival_time,
               s.capacity, (SELECT COUNT(*) FROM employees e WHERE e.shuttle_route_id = r.id) AS riders,
               t.id AS stop_id, t.name, t.latitude, t.longitude
        FROM shuttle_routes r
        JOIN shuttles s ON s.id = r.shuttle_id
        LEFT JOIN route_stops t ON t.shuttle_route_id = r.id
        ORDER BY r.departure_time, r.id, t.stop_order
    """):
        route_id = str(row["id"])
        if route_id not in routes:
            routes[route_id] = {
                "id": route_id, "hubId": str(row["pickup_location_id"]),
                "shuttleId": str(row["shuttle_id"]), "capacity": row["capacity"],
                "riders": row["riders"], "departure": str(row["departure_time"]),
                "arrival": str(row["arrival_time"]), "stops": [],
            }
        if row["stop_id"] is not None:
            routes[route_id]["stops"].append({"name": row["name"], "position": point(row)})
    return {"hubs": hubs, "routes": list(routes.values())}


@maps_api.get("/shuttles")
def shuttles():
    return {"shuttles": [
        {"id": str(row["id"]), "position": point(row)}
        for row in rows("SELECT id, latitude, longitude FROM shuttles ORDER BY id")
    ]}, 200, {"Cache-Control": "no-store"}


@maps_api.errorhandler(HTTPException)
def api_error(error):
    return {"error": error.description}, error.code


def json_body():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise BadRequest("Expected a JSON object.")
    return body


def coordinates(value):
    if not isinstance(value, dict):
        raise BadRequest("Expected coordinates with lat and lng.")
    for name, limit in (("lat", 90), ("lng", 180)):
        number = value.get(name)
        if type(number) not in (int, float) or not -limit <= number <= limit:
            raise BadRequest(f"{name} must be a number between {-limit} and {limit}.")
    return {"lat": value["lat"], "lng": value["lng"]}


def hub_position(hub_id):
    hub = rows("SELECT latitude, longitude FROM pickup_locations WHERE id = :id", id=hub_id).first()
    if hub is None:
        raise NotFound("Pickup hub not found.")
    return point(hub)


def distance_km(origin, target):
    lat1, lat2 = radians(origin["lat"]), radians(target["lat"])
    half_lng = radians(target["lng"] - origin["lng"]) / 2
    h = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin(half_lng) ** 2
    return 12742 * asin(sqrt(min(1, h)))


@maps_api.post("/hubs/nearest")
def nearest_hub():
    origin = coordinates(json_body())
    hubs = rows("SELECT id, name, address, latitude, longitude FROM pickup_locations ORDER BY id")
    nearest = min(hubs, key=lambda hub: distance_km(origin, point(hub)), default=None)
    if nearest is None:
        raise NotFound("No pickup hubs are configured.")
    position = point(nearest)
    return {"hub": {"id": str(nearest["id"]), "name": nearest["name"], "address": nearest["address"],
                    "position": position}, "distanceKm": distance_km(origin, position)}


@maps_api.post("/hubs/<int:hub_id>/directions")
def pickup_directions(hub_id):
    body = json_body()
    mode = body.get("travelMode", "WALK")
    if mode not in ("WALK", "BICYCLE", "TRANSIT", "DRIVE"):
        raise BadRequest("travelMode must be WALK, BICYCLE, TRANSIT or DRIVE.")
    origin = body.get("origin")
    if isinstance(origin, str):
        origin = origin.strip()
        if not origin:
            raise BadRequest("Enter an origin address or coordinates.")
    else:
        origin = coordinates(origin)
    destination = hub_position(hub_id)
    db.session.remove()
    return {"routes": google_maps.compute_routes(origin, destination, mode, steps=True)}


@maps_api.get("/hubs/<int:hub_id>/nearby")
def nearby(hub_id):
    category = request.args.get("category", "parking")
    if category not in google_maps.PLACE_TYPES:
        raise BadRequest("category must be parking, transit, cafe or restaurant.")
    position = hub_position(hub_id)
    db.session.remove()
    return {"places": google_maps.nearby_places(position, category)}


@maps_api.get("/routes/<int:route_id>/eta")
def shuttle_eta(route_id):
    route = rows("""
        SELECT s.latitude, s.longitude, h.latitude AS hub_lat, h.longitude AS hub_lng
        FROM shuttle_routes r JOIN shuttles s ON s.id = r.shuttle_id
        JOIN pickup_locations h ON h.id = r.pickup_location_id WHERE r.id = :id
    """, id=route_id).first()
    if route is None:
        raise NotFound("Shuttle route not found.")
    db.session.remove()
    destination = {"lat": float(route["hub_lat"]), "lng": float(route["hub_lng"])}
    return {"routes": google_maps.compute_routes(point(route), destination)}


@maps_api.get("/routes/<int:route_id>/options")
def route_options(route_id):
    records = rows("""
        SELECT h.name AS hub_name, h.latitude AS hub_lat, h.longitude AS hub_lng,
               t.id, t.name, t.latitude, t.longitude
        FROM shuttle_routes r JOIN pickup_locations h ON h.id = r.pickup_location_id
        LEFT JOIN route_stops t ON t.shuttle_route_id = r.id
        WHERE r.id = :id ORDER BY t.stop_order
    """, id=route_id).all()
    if not records:
        raise NotFound("Shuttle route not found.")
    db.session.remove()
    hub = records[0]
    stops = [{"name": hub["hub_name"], "position": {"lat": float(hub["hub_lat"]), "lng": float(hub["hub_lng"])}}]
    stops.extend({"name": stop["name"], "position": point(stop)} for stop in records if stop["id"] is not None)
    if not 2 <= len(stops) <= 27:
        raise UnprocessableEntity("Route comparison needs 2 to 27 stops including endpoints.")

    origin, destination = stops[0]["position"], stops[-1]["position"]
    middle = [stop["position"] for stop in stops[1:-1]]
    options = []
    errors = {}
    variants = ["scheduled", "optimized"] if len(middle) >= 2 else ["scheduled"]
    for variant in variants:
        optimize = variant == "optimized"
        try:
            paths = google_maps.compute_routes(origin, destination, intermediate=middle,
                                               alternatives=not middle, optimize=optimize)
            for i, path in enumerate(paths):
                ordered = stops
                if optimize:
                    order = path.get("optimizedIntermediateWaypointIndex")
                    if (not isinstance(order, list) or not all(type(n) is int for n in order)
                            or sorted(order) != list(range(len(middle)))):
                        raise BadGateway("Google Maps returned an invalid stop order.")
                    ordered = [stops[0], *(stops[n + 1] for n in order), stops[-1]]
                options.append({"kind": "alternative" if i else variant, "stops": ordered, "route": path})
        except HTTPException as error:
            errors[variant] = error
    if not options and errors:
        raise next(iter(errors.values()))
    return {"options": options, "errors": {kind: err.description for kind, err in errors.items()}}
