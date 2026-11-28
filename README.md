# ShuttleScope commuter dashboard

Open `http://localhost:5000/` after starting the stack. The dashboard uses the existing Flask API for pickup hubs, schedules, ordered stops, seat availability, stored shuttle positions, and nearest-hub lookup. No Google API key is needed for these features. Leaflet 1.9.4 is vendored with its license; the geographic background loads OpenStreetMap tiles and requires internet access.

Choose a hub to update the map and schedule. Use **Find my nearest hub** for a one-time browser location request, or expand **Use coordinates instead**. Coordinates are not persisted. Dashed map lines indicate stop order, not driving directions; positions are last reported and have no freshness timestamp. Seat availability is capacity minus assigned riders, not a booking guarantee. Schedule times are shown in Pacific time without implying dates of service.

Start with `docker compose up --build -d`. On an empty database, load the optional sample network with:

```sh
docker compose exec -T postgres sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < database/example_network.sql
```

The sample loader skips existing networks. It creates two hubs, one shuttle and a route with three stops. If port 5000 is occupied, use an ignored Compose override to map another host port (for example `127.0.0.1:5272:5000`); keep the API container port at 5000.

Install `backend/requirements.txt`, then run `python -m unittest discover -s tests -v`. Check the dashboard script with `node --check backend/static/dashboard.js`. There is no frontend build step. See `DESIGN.md` for UI ownership and behavior.

## Maps API

Flask reads hubs, schedules, ordered stops, and last-reported shuttle coordinates from PostgreSQL. It calls Google Routes API and Places API (New) using a server key. Put `GOOGLE_MAPS_API_KEY` in the ignored `.env.local` file and enable those two APIs for the key.

Start the API with `docker compose up --build -d` (Compose 2.24+). The default base URL is `http://localhost:5000/api/map`. For a database volume created with the original schema, run the additive migration:

```sh
docker compose exec -T postgres sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < database/migrations/001_hub_access.sql
```

| Method | Path under `/api/map` | Input and result |
| --- | --- | --- |
| GET | `/network` | Hub details, scheduled times, ordered stops, capacities and assigned rider counts. |
| GET | `/shuttles` | Last reported positions. |
| POST | `/hubs/nearest` | JSON coordinates such as `{"lat":37.37,"lng":-122.03}`. Returns the nearest hub by straight-line distance in km. |
| POST | `/hubs/<id>/directions` | JSON `origin` (address or lat/lng object) and optional `travelMode` (`WALK` by default, `BICYCLE`, `TRANSIT`, or `DRIVE`). Returns routes with distances, durations, polylines and steps. |
| GET | `/hubs/<id>/nearby?category=parking` | Up to eight places within 1 km. Categories are `parking` (default), `transit`, `cafe`, and `restaurant`. Includes attributions and available parking details. |
| GET | `/routes/<id>/eta` | Direct driving time from the assigned shuttle's stored position to the pickup hub, using current traffic. |
| GET | `/routes/<id>/options` | Driving previews with fixed endpoints. Requests alternate paths for two stops and compares scheduled and optimized order for two or more intermediate stops. Returns each option's stop order without editing the schedule. |

Directions and ETA return a `routes` array in Google Routes REST format, with durations such as `"480s"`. Nearby search returns a `places` array. Empty arrays indicate no matches. Route comparison returns `options` and an `errors` object if only part of the comparison succeeded. Missing hubs or routes return 404. Google-dependent requests return 503 when the key is missing.

Run `python -m unittest discover -s tests` after installing `backend/requirements.txt`.

## Original project proposal

# Transportation coordination:
- Coordinating modes of transportations when commuting
- For example someone wanting to take bart then take the bus would have to check bart schedule see what time to depart, then check and figure out which bus to take and what time it arrives.

## Proposed Solution:
- Transportation planning system that allows user to enter location A, Location B, starting time, desired arrival time. The system combines different transportation methods and shows the user the best path they’ll have to take based on their preference / cost.


## Features could be:
User account, favorite locations, frequent trips…

## Transportation modes:
Bart, Bus, Car, Walking, Rideshare

Example use cases:
- the user entering the system, set location A to “X bart station”, set location B to “Y bart station”, then the app figures out which trains you’ll transfer at , as well as which bus you’ll be taking right after you arrive.
- showing options to filter for your preferred transit: driving your own vehicle, willing to pay for parking, not willing to bike uphill, etc.
- app shows option to drive to caltrain station, pay for parking, take train to city, bus to destination, etc.


## Jenkins CI

See [Jenkins setup](jenkins/README.md) for the `jenkinsJob` push-build setup.
