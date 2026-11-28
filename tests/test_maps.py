import json
import unittest
from unittest.mock import Mock, patch

from sqlalchemy import text

from backend.app import create_app
from backend.database import db


class MapEndpointsTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "GOOGLE_MAPS_API_KEY": "test-only",
        })
        self.client = self.app.test_client()
        with self.app.app_context(), db.engine.begin() as connection:
            self.addCleanup(db.engine.dispose)
            for statement in (
                "CREATE TABLE pickup_locations (id INTEGER, name TEXT, address TEXT, latitude REAL, longitude REAL)",
                "CREATE TABLE shuttles (id INTEGER, latitude REAL, longitude REAL)",
                "CREATE TABLE shuttle_routes (id INTEGER, shuttle_id INTEGER, pickup_location_id INTEGER)",
                "CREATE TABLE route_stops (id INTEGER, shuttle_route_id INTEGER, name TEXT, latitude REAL, longitude REAL, stop_order INTEGER)",
                "INSERT INTO pickup_locations VALUES (1,'Hub','Hub Rd',37,-122),(2,'Other','Main St',38,-120)",
                "INSERT INTO shuttles VALUES (3,36,-121)",
                "INSERT INTO shuttle_routes VALUES (4,3,1),(5,3,2)",
                "INSERT INTO route_stops VALUES (11,4,'B',37.2,-122,2),(10,4,'A',37.1,-122,1),(12,4,'Office',37.3,-122,3),(13,5,'Office',37.3,-122,1)",
            ):
                connection.execute(text(statement))
        patcher = patch("backend.services.google_maps.HTTPSConnection")
        self.https = patcher.start()
        self.addCleanup(patcher.stop)
        self.connection = self.https.return_value

    @staticmethod
    def response(data, status=200):
        response = Mock(status=status)
        response.read.return_value = json.dumps(data).encode()
        return response

    def test_directions(self):
        self.connection.getresponse.return_value = self.response({"routes": [{"duration": "180s"}]})
        response = self.client.post("/api/map/hubs/1/directions", json={"origin": "1 Main St", "travelMode": "TRANSIT"})
        self.assertEqual(response.json, {"routes": [{"duration": "180s"}]})
        self.https.assert_called_with("routes.googleapis.com", timeout=8)
        args, kwargs = self.connection.request.call_args
        self.assertEqual(args, ("POST", "/directions/v2:computeRoutes"))
        body = json.loads(kwargs["body"])
        self.assertEqual(body["origin"], {"address": "1 Main St"})
        self.assertEqual(body["destination"]["location"]["latLng"], {"latitude": 37, "longitude": -122})
        self.assertEqual(body["travelMode"], "TRANSIT")
        self.assertEqual(body["languageCode"], "en-US")
        self.assertEqual(body["units"], "METRIC")
        self.assertNotIn("routingPreference", body)
        self.assertEqual(kwargs["headers"]["X-Goog-Api-Key"], "test-only")
        self.assertIn("routes.legs.steps.transitDetails", kwargs["headers"]["X-Goog-FieldMask"])

    def test_nearby_search(self):
        self.connection.getresponse.return_value = self.response({})
        response = self.client.get("/api/map/hubs/1/nearby?category=parking")
        self.assertEqual(response.json, {"places": []})
        self.https.assert_called_with("places.googleapis.com", timeout=8)
        args, kwargs = self.connection.request.call_args
        self.assertEqual(args, ("POST", "/v1/places:searchNearby"))
        body = json.loads(kwargs["body"])
        self.assertEqual(body["includedTypes"], ["parking", "park_and_ride"])
        self.assertEqual(body["locationRestriction"]["circle"]["radius"], 1000)
        self.assertIn("places.parkingOptions", kwargs["headers"]["X-Goog-FieldMask"])

    def test_nearest_and_validation(self):
        response = self.client.post("/api/map/hubs/nearest", json={"lat": 38, "lng": -120})
        self.assertEqual(response.json["hub"]["id"], "2")
        self.assertEqual(response.json["distanceKm"], 0)
        for origin in (None, {"lat": False, "lng": 0}, {"lat": 0, "lng": 181}, "  "):
            self.assertEqual(self.client.post("/api/map/hubs/1/directions", json={"origin": origin}).status_code, 400)
        self.assertEqual(self.client.get("/api/map/hubs/1/nearby?category=invalid").status_code, 400)
        self.assertEqual(self.client.get("/api/map/routes/7/eta").status_code, 404)
        self.https.assert_not_called()

    def test_eta_from_stored_position(self):
        self.connection.getresponse.return_value = self.response({"routes": [{"duration": "900s"}]})
        response = self.client.get("/api/map/routes/4/eta")
        self.assertEqual(response.json["routes"][0]["duration"], "900s")
        body = json.loads(self.connection.request.call_args.kwargs["body"])
        self.assertEqual(body["routingPreference"], "TRAFFIC_AWARE")
        self.assertEqual(body["origin"]["location"]["latLng"], {"latitude": 36, "longitude": -121})

    def test_route_comparison(self):
        self.connection.getresponse.side_effect = [
            self.response({"routes": [{"duration": "600s"}]}),
            self.response({"routes": [{"duration": "510s", "optimizedIntermediateWaypointIndex": [1, 0]}]}),
        ]
        options = self.client.get("/api/map/routes/4/options").json["options"]
        self.assertEqual([s["name"] for s in options[0]["stops"]], ["Hub", "A", "B", "Office"])
        self.assertEqual([s["name"] for s in options[1]["stops"]], ["Hub", "B", "A", "Office"])
        req = self.connection.request.call_args.kwargs
        self.assertTrue(json.loads(req["body"])["optimizeWaypointOrder"])
        self.assertIn("routes.optimizedIntermediateWaypointIndex", req["headers"]["X-Goog-FieldMask"])

    def test_two_stop_route_gets_alternatives(self):
        self.connection.getresponse.return_value = self.response({"routes": [{"duration": "300s"}, {"duration": "310s"}]})
        options = self.client.get("/api/map/routes/5/options").json["options"]
        self.assertEqual([o["kind"] for o in options], ["scheduled", "alternative"])
        self.assertTrue(json.loads(self.connection.request.call_args.kwargs["body"])["computeAlternativeRoutes"])
        self.connection.request.assert_called_once()

    def test_partial_comparison(self):
        self.connection.getresponse.side_effect = [
            self.response({"routes": [{"duration": "600s"}]}), self.response({}, status=429),
        ]
        response = self.client.get("/api/map/routes/4/options")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json["options"]), 1)
        self.assertIn("optimized", response.json["errors"])

    def test_missing_key_and_upstream_errors(self):
        path = "/api/map/routes/4/eta"
        self.connection.getresponse.return_value = self.response({"error": "test-only"}, status=403)
        response = self.client.get(path)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(b"test-only", response.data)
        self.connection.getresponse.side_effect = TimeoutError()
        self.assertEqual(self.client.get(path).status_code, 504)
        self.app.config["GOOGLE_MAPS_API_KEY"] = ""
        self.https.reset_mock()
        self.assertEqual(self.client.get(path).status_code, 503)
        self.https.assert_not_called()

    def test_dashboard_and_assets(self):
        self.app.config["GOOGLE_MAPS_API_KEY"] = ""
        self.assertEqual(self.client.get("/healthz").json, {"status": "ok"})
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Your commute, connected.", response.data)
        self.assertIn(b'novalidate', response.data)
        for path in ("/static/dashboard.js", "/static/dashboard.css", "/static/vendor/leaflet.js", "/static/vendor/leaflet.css"):
            with self.client.get(path) as asset:
                self.assertEqual(asset.status_code, 200)
        self.https.assert_not_called()

    def test_network_capacity_and_ordered_stops(self):
        with self.app.app_context(), db.engine.begin() as connection:
            for statement in (
                "ALTER TABLE pickup_locations ADD COLUMN type TEXT DEFAULT 'BUS_STOP'",
                "ALTER TABLE pickup_locations ADD COLUMN parking_notes TEXT",
                "ALTER TABLE pickup_locations ADD COLUMN bike_parking_notes TEXT",
                "ALTER TABLE shuttle_routes ADD COLUMN departure_time TEXT DEFAULT '07:30:00'",
                "ALTER TABLE shuttle_routes ADD COLUMN arrival_time TEXT DEFAULT '08:25:00'",
                "ALTER TABLE shuttles ADD COLUMN capacity INTEGER DEFAULT 24",
                "CREATE TABLE employees (id INTEGER, shuttle_route_id INTEGER)",
                "INSERT INTO employees VALUES (1,4)",
            ):
                connection.execute(text(statement))
        response = self.client.get("/api/map/network")
        self.assertEqual(response.status_code, 200)
        route = next(item for item in response.json["routes"] if item["id"] == "4")
        self.assertEqual((route["capacity"], route["riders"]), (24, 1))
        self.assertEqual([stop["name"] for stop in route["stops"]], ["A", "B", "Office"])
        self.assertEqual(self.client.get("/api/map/shuttles").json["shuttles"][0]["id"], "3")

    def test_directions_modes_and_empty_results(self):
        self.connection.getresponse.return_value = self.response({})
        for mode in ("WALK", "BICYCLE", "TRANSIT", "DRIVE"):
            result = self.client.post("/api/map/hubs/1/directions", json={"origin": "  1 Main St  ", "travelMode": mode})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json, {"routes": []})
            body = json.loads(self.connection.request.call_args.kwargs["body"])
            self.assertEqual(body["origin"], {"address": "1 Main St"})
            self.assertEqual(body.get("routingPreference"), "TRAFFIC_AWARE" if mode == "DRIVE" else None)
        self.assertEqual(self.client.post("/api/map/hubs/1/directions", json={"origin": "X", "travelMode": "FLY"}).status_code, 400)
        self.assertEqual(self.client.post("/api/map/hubs/999/directions", json={"origin": "X"}).status_code, 404)
