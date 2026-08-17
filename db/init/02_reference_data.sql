BEGIN;

-- Columns from Postnummer_med_koordinater_utf8.csv (UTF-8, comma-delimited).
-- Source has separate lat/long for street addresses and PO boxes; we COALESCE them.
-- postnummerkategori has no equivalent in this file; the column will be NULL.
CREATE TEMP TABLE dim_postnummer_raw (
  "Postnummer" TEXT,
  "Poststedsnavn" TEXT,
  "Kategori" TEXT,
  "Primærkommunenummer" TEXT,
  "Primærkommunenavn" TEXT,
  "Primærfylkenummer" TEXT,
  "Primærfylke" TEXT,
  "X_gateadresser" TEXT,
  "Y_gateadresser" TEXT,
  "X_postbokser" TEXT,
  "Y_postbokser" TEXT,
  "Latitude_gateadresser" TEXT,
  "Longitude_gateadresser" TEXT,
  "Latitude_postbokser" TEXT,
  "Longitude_postbokser" TEXT
) ON COMMIT DROP;

-- Server-side read of the ./reference_data:/reference_data:ro mount in docker-compose.yml.
-- Running this script from a client outside the container will fail to find the path.
COPY dim_postnummer_raw
FROM '/reference_data/Postnummer_med_koordinater_utf8.csv'
WITH (FORMAT csv, DELIMITER ',', HEADER true);

-- DISTINCT ON collapses source rows that share a postnummer but differ elsewhere,
-- which would otherwise violate the UNIQUE constraint and abort initialisation.
INSERT INTO postnumbers (
  postnummer,
  poststed,
  fylkekode,
  fylke,
  kommunekode,
  kommune,
  postnummerkategorikode,
  postnummerkategori,
  latitude,
  longitude
)
SELECT DISTINCT ON (CAST(TRIM("Postnummer") AS INTEGER))
  CAST(TRIM("Postnummer") AS INTEGER) AS postnummer,
  TRIM("Poststedsnavn") AS poststed,
  CASE
    WHEN TRIM("Primærfylkenummer") ~ '^[0-9]+$' THEN CAST(TRIM("Primærfylkenummer") AS INTEGER)
  END AS fylkekode,
  NULLIF(TRIM("Primærfylke"), '') AS fylke,
  CASE
    WHEN TRIM("Primærkommunenummer") ~ '^[0-9]+$' THEN CAST(TRIM("Primærkommunenummer") AS INTEGER)
  END AS kommunekode,
  NULLIF(TRIM("Primærkommunenavn"), '') AS kommune,
  NULLIF(TRIM("Kategori"), '') AS postnummerkategorikode,
  NULL AS postnummerkategori,
  CASE
    WHEN NULLIF(TRIM("Latitude_gateadresser"), '') IS NOT NULL
      THEN CAST(TRIM("Latitude_gateadresser") AS DOUBLE PRECISION)
    WHEN NULLIF(TRIM("Latitude_postbokser"), '') IS NOT NULL
      THEN CAST(TRIM("Latitude_postbokser") AS DOUBLE PRECISION)
  END AS latitude,
  CASE
    WHEN NULLIF(TRIM("Longitude_gateadresser"), '') IS NOT NULL
      THEN CAST(TRIM("Longitude_gateadresser") AS DOUBLE PRECISION)
    WHEN NULLIF(TRIM("Longitude_postbokser"), '') IS NOT NULL
      THEN CAST(TRIM("Longitude_postbokser") AS DOUBLE PRECISION)
  END AS longitude
FROM dim_postnummer_raw
WHERE TRIM("Postnummer") ~ '^[0-9]{4}$'
ORDER BY CAST(TRIM("Postnummer") AS INTEGER), TRIM("Poststedsnavn")
ON CONFLICT (postnummer) DO NOTHING;

COMMIT;
