ALTER TABLE pickup_locations
    ADD COLUMN IF NOT EXISTS parking_notes TEXT,
    ADD COLUMN IF NOT EXISTS bike_parking_notes TEXT;
