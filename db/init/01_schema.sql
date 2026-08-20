-- Runs via docker-entrypoint-initdb.d, which executes db/init/*.sql in lexical
-- filename order and only when the postgres-data volume is empty.
-- Rebuild from scratch: docker compose down -v && docker compose up -d

BEGIN;

-- Needed for the EXCLUDE USING gist constraint on assignments (date-range overlap).
CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE postnumbers (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
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
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  street_name TEXT NOT NULL,
  street_number TEXT NOT NULL,
  post_number_id BIGINT NOT NULL REFERENCES postnumbers(id)
);

CREATE TABLE person (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  first_name TEXT NOT NULL,
  last_name TEXT NOT NULL,
  email_address TEXT NOT NULL UNIQUE,
  address_id BIGINT NOT NULL REFERENCES address(id) ON DELETE CASCADE,
  short_description TEXT NOT NULL
);

CREATE TABLE clients (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  address_id BIGINT NOT NULL UNIQUE REFERENCES address(id) ON DELETE RESTRICT,
  org_number TEXT NOT NULL UNIQUE,
  contact_email TEXT,
  industry TEXT,
  notes TEXT,
  CONSTRAINT chk_client_org_number_format CHECK (org_number ~ '^[0-9]{9}$')
);

-- Technology lookup: shared by assignment_technology so names stay consistent
-- (e.g. no "Python" vs "python" drift) and can be referenced by FK.
CREATE TABLE technology (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name TEXT NOT NULL UNIQUE
);

CREATE TABLE assignments (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  developer_id BIGINT NOT NULL REFERENCES person(id) ON DELETE CASCADE,
  start_date DATE NOT NULL,
  end_date DATE NOT NULL,
  assignment_description TEXT NOT NULL,
  role TEXT NOT NULL,
  CONSTRAINT chk_assignment_dates CHECK (end_date >= start_date),
  CONSTRAINT chk_assignment_max_3y CHECK (end_date <= (start_date + INTERVAL '3 years')),
  CONSTRAINT chk_assignment_role CHECK (role IN (
    'Frontend Developer', 'Backend Developer', 'Full-Stack Developer',
    'Mobile Developer', 'Data Engineer', 'DevOps Engineer', 'QA Engineer',
    'Security Engineer', 'Team Lead', 'Scrum Master', 'Product Owner',
    'Solution Architect'
  )),
  -- A developer cannot be booked on two overlapping assignments at once.
  CONSTRAINT excl_assignment_no_overlap EXCLUDE USING gist (
    developer_id WITH =,
    daterange(start_date, end_date, '[]') WITH &&
  )
);

-- Many-to-many: technologies actually used on a given assignment, which is
-- what the consultant_technology_experience view (04_views.sql) aggregates over.
CREATE TABLE assignment_technology (
  assignment_id BIGINT NOT NULL REFERENCES assignments(id) ON DELETE CASCADE,
  technology_id BIGINT NOT NULL REFERENCES technology(id) ON DELETE RESTRICT,
  PRIMARY KEY (assignment_id, technology_id)
);

CREATE INDEX idx_assignment_technology_technology_id ON assignment_technology(technology_id);

COMMIT;
