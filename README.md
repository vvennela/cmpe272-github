# ShuttleScope commuter dashboard

Open `http://localhost:5000/` after starting the stack. The dashboard uses the existing Flask API for pickup hubs, schedules, ordered stops, seat availability, stored shuttle positions, and nearest-hub lookup. No Google API key is needed for these features. Leaflet 1.9.4 is vendored with its license; the geographic background loads OpenStreetMap tiles and requires internet access.

Choose a hub to update the map and schedule. Use **Find my nearest hub** for a one-time browser location request, or expand **Use coordinates instead**. Coordinates are not persisted. Dashed map lines indicate stop order, not driving directions; positions are last reported and have no freshness timestamp. Seat availability is capacity minus assigned riders, not a booking guarantee. Schedule times are shown in Pacific time without implying dates of service.

Start with `docker compose up --build -d`. On an empty database, load the optional sample network with:

```sh
docker compose exec -T postgres sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < database/example_network.sql
```

The sample loader skips existing networks. It creates two hubs, one shuttle and a route with three stops. If port 5000 is occupied, use an ignored Compose override to map another host port (for example `127.0.0.1:5272:5000`); keep the API container port at 5000.

Install `backend/requirements.txt`, then run `python -m unittest discover -s tests -v`. Check the dashboard script with `node --check backend/static/dashboard.js`. There is no frontend build step. See `DESIGN.md` for UI ownership and behavior.

## Employee accounts

Visit `/signup` to create an employee account and `/login` to log in. Accounts use a name, email, address and password. Email is matched case-insensitively; passwords allow 15–128 characters without composition rules. Signup logs the user in and both flows return to the dashboard. The header shows the account name and a POST-only logout action. The network dashboard remains available without an account. Signup never grants admin access.

For existing databases, apply the additive migration before using accounts:

```sh
docker compose exec -T postgres sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < database/migrations/002_user_email.sql
```

Fresh databases get the email column and unique index from `schema.sql`. Existing users keep `NULL` emails until an administrator provisions their login address; this release does not silently assign login identities to old records. The migration can be run again safely.

Set `SESSION_SECRET` in ignored `.env.local` to a private random value. Generate one locally with `python3 -c 'import secrets; print(secrets.token_hex(32))'`, paste it into that file, and do not commit or share it. The old `SECRET_KEY` in tracked `.env` is deliberately not used for account sessions. Missing `SESSION_SECRET` disables accounts with a setup message while the public dashboard still works. Each teammate needs their own local secret.

Run `docker compose up --build -d` after installing this change (use your existing port override if needed). Recreate the API after changing `.env.local`. New runtime dependencies are installed by Docker or `pip install -r backend/requirements.txt`.

Sessions expire after eight hours and use HttpOnly, SameSite=Lax cookies. All account writes require CSRF tokens. Signup and login are limited to five POST attempts per minute per client IP. Rate limits use in-memory storage for local development. Before a multi-worker/public deployment, configure shared rate-limit storage and its driver, HTTPS, `SESSION_COOKIE_SECURE=true`, and a private stable `SESSION_SECRET`. Login does not verify email ownership; email verification, password reset, admin provisioning and immediate server-side revocation of signed session cookies remain future work. See `AUTH.md` for the account contract.

## Directions to a pickup hub

Select a hub, enter a starting address in **Directions to your hub**, choose Walk/Bike/Transit/Drive, and click **Get directions**. The dashboard displays estimated travel time, distance, instructions, warnings and a Google Maps navigation link. Changing the hub, address or mode clears the previous trip. The existing network map continues to show scheduled shuttle stops.

In the ignored `.env.local`, set `GOOGLE_MAPS_API_KEY` to your server key with Routes API enabled. To also draw the returned route inside the dashboard, set **a separate** `GOOGLE_MAPS_BROWSER_API_KEY` with Maps JavaScript API enabled, HTTP-referrer restrictions for your actual localhost/production URLs, and API restrictions to Maps JavaScript API. The browser key is intentionally public; never reuse the server key. Restart/recreate the API after changing environment variables. Without the browser key, text directions still work and the Google Maps link opens the map. Without the server key, directions show a setup message while the rest of the dashboard works.

Google routes must be displayed on Google maps, so their geometry is never drawn on the OpenStreetMap network layer. Provider requirements: https://developers.google.com/maps/documentation/routes/policies. Google content is not saved in the database or browser storage. Public deployment also needs the provider-required public terms and privacy policies.

Frontend interaction tests: `npm ci`, then `npm run test:ui` (Node 22+). They mock Google and the API, so no credentials or billable requests are needed. Backend tests remain `python -m unittest discover -s tests -v`.

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
