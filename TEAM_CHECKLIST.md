# ShuttleScope team checklist

Status as of November 27, 2026. Checked items are implemented; live Google integration still needs the setup and verification below.

## Implemented

- [x] Flask API and PostgreSQL database schema.
- [x] Docker setup and optional sample shuttle network.
- [x] Commuter dashboard with selectable pickup hubs and an interactive network map.
- [x] Shuttle schedules, ordered stops, capacity and assigned-rider counts.
- [x] Last-reported shuttle positions on the map.
- [x] Nearest-hub lookup using browser location or manual coordinates.
- [x] Directions form with a starting address and Walk, Bike, Transit and Drive modes.
- [x] Directions travel time, distance, instructions, warnings and Google Maps navigation link.
- [x] Optional embedded Google route map with a separate browser key.
- [x] Directions validation, loading, empty-route, error and retry states; stale requests cancelled on input/hub changes.
- [x] Automated checks for maps, directions, and the user model (Google requests mocked).
- [x] User model with employee-role default and salted password hashing/verification.
- [x] Employee signup, email/password login, logout and signed-in header.
- [x] Additive email migration, unique normalized emails, CSRF protection and login/signup rate limits.

## Implemented backend features still needing dashboard controls

- [ ] Connect shuttle ETA endpoint to the dashboard. ETA currently uses a stored position.
- [ ] Add nearby parking, transit, cafe and restaurant results.
- [ ] Add scheduled versus optimized route comparison.

## Setup and verification still needed

- [ ] Each teammate: apply `002_user_email.sql`, set private `SESSION_SECRET` in ignored `.env.local`, then rebuild/recreate the API.
- [ ] Before public deployment: HTTPS/secure cookies and shared rate-limit storage.

- [ ] Configure the server Google Routes key in ignored `.env.local`.
- [ ] Configure a separate browser-restricted Maps JavaScript key for the embedded route map.
- [ ] Verify real directions, times, instructions and map rendering with Google enabled. No live Google success response has been verified yet.
- [ ] Extend browser checks to successful live routes. Form validation, missing-key recovery, keyboard mode selection, hub switching and responsive layouts have been checked.
- [ ] Update Jenkins to run application tests; its current job checks the README and archives source.
- [ ] Provide public deployment, provider-required terms/privacy pages, and production configuration if deploying publicly.

## Features not implemented

- [ ] Email verification, password reset and revocable server-side sessions for account recovery/all-device logout.

- [ ] Admin authorization and account provisioning.
- [ ] Employee pickup-hub and shuttle-route assignment.
- [ ] Admin screens and APIs to manage hubs, shuttles, schedules and stops.
- [ ] Seat booking/cancellation and capacity enforcement, if the team chooses a booking workflow.
- [ ] GPS position updates with timestamps; current positions are stored coordinates, not live tracking.
- [ ] Favorite locations and saved/frequent trips.
- [ ] Full origin-to-destination planning with departure/arrival preferences, transfers and cost comparison from the original proposal.

Available seats currently means shuttle capacity minus assigned employees. It is not a reservation guarantee. Schedule times do not yet define operating dates or a service calendar.
