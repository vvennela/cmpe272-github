-- Optional local example. Only populate an empty network.
DO $$
DECLARE
    vehicle bigint;
    hub bigint;
    trip bigint;
BEGIN
    LOCK TABLE shuttles, pickup_locations IN SHARE ROW EXCLUSIVE MODE;
    IF EXISTS (SELECT FROM shuttles) OR EXISTS (SELECT FROM pickup_locations) THEN
        RAISE NOTICE 'Existing network found. Skipping sample data.';
        RETURN;
    END IF;
    INSERT INTO shuttles (capacity, latitude, longitude)
    VALUES (24, 37.3686, -122.0363) RETURNING id INTO vehicle;
    INSERT INTO pickup_locations (type, name, address, latitude, longitude)
    VALUES ('BUS_STOP', 'Sunnyvale Transit Center', '121 W Evelyn Ave, Sunnyvale, CA', 37.3781, -122.0307)
    RETURNING id INTO hub;
    INSERT INTO pickup_locations (type, name, address, latitude, longitude)
    VALUES ('BART', 'Berryessa / North San José', '1620 Berryessa Rd, San Jose, CA', 37.3684, -121.8746);
    INSERT INTO shuttle_routes (shuttle_id, pickup_location_id, departure_time, arrival_time, route_type)
    VALUES (vehicle, hub, '07:30', '08:25', 'BUS') RETURNING id INTO trip;
    INSERT INTO route_stops (shuttle_route_id, name, address, latitude, longitude, stop_order) VALUES
        (trip, 'Lawrence Station', '137 San Zeno Way, Sunnyvale, CA', 37.3708, -121.9970, 1),
        (trip, 'Santa Clara Station', '1001 Railroad Ave, Santa Clara, CA', 37.3532, -121.9364, 2),
        (trip, 'San José office', '4th St and San Fernando St, San Jose, CA', 37.3361, -121.8856, 3);
END $$;
