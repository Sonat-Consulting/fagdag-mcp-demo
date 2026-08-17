-- Runs via docker-entrypoint-initdb.d, which executes db/init/*.sql in lexical
-- filename order and only when the postgres-data volume is empty.
-- Rebuild from scratch: docker compose down -v && docker compose up -d

BEGIN;

CREATE TABLE postnumbers (
  id BIGSERIAL PRIMARY KEY,
  postnummer INTEGER NOT NULL UNIQUE,
  poststed TEXT NOT NULL,
  fylkekode INTEGER,
  fylke TEXT,
  kommunekode INTEGER,
  kommune TEXT,
  postnummerkategorikode TEXT,
  postnummerkategori TEXT,
  latitude DOUBLE PRECISION,
  longitude DOUBLE PRECISION
);

CREATE TABLE address (
  id BIGSERIAL PRIMARY KEY,
  street_name TEXT NOT NULL,
  street_number TEXT NOT NULL,
  post_number_id BIGINT NOT NULL REFERENCES postnumbers(id)
);

CREATE TABLE person (
  id BIGSERIAL PRIMARY KEY,
  first_name TEXT NOT NULL,
  last_name TEXT NOT NULL,
  email_address TEXT NOT NULL UNIQUE,
  address_id BIGINT NOT NULL REFERENCES address(id) ON DELETE CASCADE,
  short_description TEXT NOT NULL,
  technologies TEXT[] NOT NULL DEFAULT '{}',
  project_descriptions TEXT[] NOT NULL DEFAULT '{}'
);

CREATE TABLE clients (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  address_id BIGINT NOT NULL UNIQUE REFERENCES address(id) ON DELETE RESTRICT,
  org_number TEXT,
  contact_email TEXT,
  industry TEXT,
  notes TEXT
);

CREATE TABLE assignments (
  id BIGSERIAL PRIMARY KEY,
  client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  developer_id BIGINT NOT NULL REFERENCES person(id) ON DELETE CASCADE,
  start_date DATE NOT NULL,
  end_date DATE NOT NULL,
  assignment_description TEXT NOT NULL,
  CONSTRAINT chk_assignment_dates CHECK (end_date >= start_date),
  CONSTRAINT chk_assignment_max_3y CHECK (end_date <= (start_date + INTERVAL '3 years'))
);

COMMIT;
