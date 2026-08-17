-- Depends on 02_reference_data.sql having populated postnumbers.
BEGIN;

CREATE TEMP TABLE seed_person ON COMMIT DROP AS
WITH bergen_codes AS (
  SELECT id, ROW_NUMBER() OVER (ORDER BY postnummer) AS rn
  FROM postnumbers
  WHERE UPPER(poststed) = 'BERGEN'
),
bergen_count AS (
  SELECT COUNT(*) AS cnt FROM bergen_codes
),
oslo_codes AS (
  SELECT id, ROW_NUMBER() OVER (ORDER BY postnummer) AS rn
  FROM postnumbers
  WHERE UPPER(poststed) = 'OSLO'
),
oslo_count AS (
  SELECT COUNT(*) AS cnt FROM oslo_codes
),
other_weighted_codes AS (
  SELECT
    p.id,
    ROW_NUMBER() OVER (ORDER BY p.postnummer, gs.n) AS rn
  FROM postnumbers AS p
  CROSS JOIN LATERAL generate_series(
    1,
    CASE
      WHEN UPPER(p.poststed) IN (
        'TRONDHEIM', 'STAVANGER', 'DRAMMEN', 'KRISTIANSAND',
        'TROMSØ', 'FREDRIKSTAD', 'SANDNES', 'SKIEN', 'ÅLESUND', 'BODØ'
      ) THEN 10
      WHEN UPPER(p.fylke) IN ('AKERSHUS', 'ROGALAND', 'VESTLAND', 'TRØNDELAG') THEN 3
      ELSE 1
    END
  ) AS gs(n)
  WHERE UPPER(p.poststed) NOT IN ('BERGEN', 'OSLO')
),
other_count AS (
  SELECT COUNT(*) AS cnt FROM other_weighted_codes
),
-- Fixed split: persons 1-126 Bergen, 127-145 Oslo, the rest spread over a
-- population-weighted pool. The multipliers only need to look unclustered.
developer_locations AS (
  SELECT
    g AS person_idx,
    CASE
      WHEN g <= 126 THEN (
        SELECT bc.id
        FROM bergen_codes AS bc
        CROSS JOIN bergen_count AS bcount
        WHERE bc.rn = ((g - 1) % bcount.cnt) + 1
      )
      WHEN g <= 145 THEN (
        SELECT oc.id
        FROM oslo_codes AS oc
        CROSS JOIN oslo_count AS ocount
        WHERE oc.rn = ((g - 127) % ocount.cnt) + 1
      )
      ELSE (
        SELECT owc.id
        FROM other_weighted_codes AS owc
        CROSS JOIN other_count AS xcount
        WHERE owc.rn = (((g * 7919) + (g * g * 17)) % xcount.cnt) + 1
      )
    END AS post_number_id
  FROM generate_series(1, 300) AS g
),
pools AS (
  SELECT
    ARRAY[
      'Liam','Olivia','Noah','Emma','Oliver','Ava','Elijah','Sophia','Mateo','Mia',
      'Lucas','Amelia','Levi','Harper','Ethan','Evelyn','Aiden','Abigail','Logan','Emily',
      'James','Ella','Mason','Elizabeth','Benjamin','Camila','Jacob','Luna','Michael','Sofia'
    ] AS first_names,
    ARRAY[
      'Hansen','Johansen','Olsen','Larsen','Andersen','Pedersen','Nilsen','Kristiansen','Jensen','Karlsen',
      'Johnsen','Pettersen','Eriksen','Berg','Haugen','Hagen','Johannessen','Andreassen','Jacobsen','Dahl',
      'Jorgensen','Henriksen','Lund','Halvorsen','Sorensen','Jakobsen','Moen','Gundersen','Iversen','Strand'
    ] AS last_names,
    ARRAY[
      'Innovasjonveien','Kodegata','Datastien','Skyveien','Algoritmebakken','Plattformallmenningen',
      'API-plassen','Testlabben','Deployveien','Sprintstien','Mikrotjenesteveien','Kernelbakken'
    ] AS streets
),
base AS (
  SELECT
    g AS person_idx,
    ((g - 1) % 8) + 1 AS profile_idx,
    dl.post_number_id,
    pl.first_names[((g - 1) % array_length(pl.first_names, 1)) + 1] AS first_name,
    pl.last_names[((g - 1) % array_length(pl.last_names, 1)) + 1] AS last_name,
    pl.streets[((g - 1) % array_length(pl.streets, 1)) + 1] AS street_name,
    (100 + g)::TEXT AS street_number
  FROM generate_series(1, 300) AS g
  CROSS JOIN pools AS pl
  JOIN developer_locations AS dl ON dl.person_idx = g
)
SELECT
  person_idx,
  first_name,
  last_name,
  LOWER(first_name || '.' || last_name || person_idx || '@example.com') AS email_address,
  street_name,
  street_number,
  post_number_id,
  CASE profile_idx
    WHEN 1 THEN CONCAT('Backend engineer with ', 3 + (person_idx % 7), ' years building Python microservices and resilient APIs.')
    WHEN 2 THEN CONCAT('Frontend engineer with ', 2 + (person_idx % 6), ' years building accessible React applications and design systems.')
    WHEN 3 THEN CONCAT('Data engineer with ', 4 + (person_idx % 8), ' years designing ETL pipelines and analytics platforms.')
    WHEN 4 THEN CONCAT('DevOps engineer with ', 5 + (person_idx % 7), ' years automating cloud infrastructure and delivery pipelines.')
    WHEN 5 THEN CONCAT('Mobile engineer with ', 2 + (person_idx % 5), ' years creating cross-platform apps and offline-first features.')
    WHEN 6 THEN CONCAT('Security-focused engineer with ', 4 + (person_idx % 6), ' years in threat modeling, secure coding, and incident response.')
    WHEN 7 THEN CONCAT('QA automation engineer with ', 3 + (person_idx % 7), ' years building test frameworks and release quality gates.')
    ELSE CONCAT('Full-stack engineer with ', 3 + (person_idx % 9), ' years delivering product features from UI to production operations.')
  END AS short_description,
  CASE profile_idx
    WHEN 1 THEN ARRAY['Python', 'FastAPI', 'PostgreSQL', 'Redis', 'Docker']::TEXT[]
    WHEN 2 THEN ARRAY['TypeScript', 'React', 'Vite', 'CSS', 'Playwright']::TEXT[]
    WHEN 3 THEN ARRAY['Python', 'dbt', 'Airflow', 'DuckDB', 'Spark']::TEXT[]
    WHEN 4 THEN ARRAY['Terraform', 'Kubernetes', 'GitHub Actions', 'Prometheus', 'Grafana']::TEXT[]
    WHEN 5 THEN ARRAY['Flutter', 'Dart', 'Firebase', 'SQLite', 'REST']::TEXT[]
    WHEN 6 THEN ARRAY['Go', 'OWASP', 'SAST', 'SIEM', 'IAM']::TEXT[]
    WHEN 7 THEN ARRAY['Python', 'Pytest', 'Selenium', 'Cypress', 'Testcontainers']::TEXT[]
    ELSE ARRAY['TypeScript', 'Node.js', 'PostgreSQL', 'Docker', 'AWS']::TEXT[]
  END AS technologies,
  CASE profile_idx
    WHEN 1 THEN ARRAY[
      CONCAT('Designed event-driven billing API for tenant group #', person_idx),
      CONCAT('Improved service p95 latency by 35% for backend domain #', person_idx)
    ]::TEXT[]
    WHEN 2 THEN ARRAY[
      CONCAT('Built reusable component library adopted by squad #', person_idx),
      CONCAT('Migrated legacy SPA to React with SSR for portal #', person_idx)
    ]::TEXT[]
    WHEN 3 THEN ARRAY[
      CONCAT('Implemented batch and streaming ETL for data product #', person_idx),
      CONCAT('Created quality checks reducing bad records by 42% for pipeline #', person_idx)
    ]::TEXT[]
    WHEN 4 THEN ARRAY[
      CONCAT('Automated multi-env deployment platform for service #', person_idx),
      CONCAT('Set up observability stack and SLO dashboards for cluster #', person_idx)
    ]::TEXT[]
    WHEN 5 THEN ARRAY[
      CONCAT('Delivered cross-platform mobile app feature set for release #', person_idx),
      CONCAT('Implemented offline sync workflow for field users cohort #', person_idx)
    ]::TEXT[]
    WHEN 6 THEN ARRAY[
      CONCAT('Led security hardening and threat assessments for platform #', person_idx),
      CONCAT('Implemented secrets rotation and policy checks for environment #', person_idx)
    ]::TEXT[]
    WHEN 7 THEN ARRAY[
      CONCAT('Built test automation suite covering regression pack #', person_idx),
      CONCAT('Introduced flaky-test quarantine process for pipeline #', person_idx)
    ]::TEXT[]
    ELSE ARRAY[
      CONCAT('Delivered end-to-end feature stream for product line #', person_idx),
      CONCAT('Implemented cost optimization and autoscaling for workload #', person_idx)
    ]::TEXT[]
  END AS project_descriptions
FROM base;

INSERT INTO address (street_name, street_number, post_number_id)
SELECT street_name, street_number, post_number_id
FROM seed_person
ORDER BY person_idx;

INSERT INTO person (
  first_name,
  last_name,
  email_address,
  address_id,
  short_description,
  technologies,
  project_descriptions
)
SELECT
  s.first_name,
  s.last_name,
  s.email_address,
  a.id,
  s.short_description,
  s.technologies,
  s.project_descriptions
FROM seed_person AS s
JOIN address AS a
  ON a.street_name = s.street_name
 AND a.street_number = s.street_number;

WITH client_name_seed AS (
  SELECT ARRAY[
    'Nordic Dynamics','Fjord Analytics','Aurora Systems','Polar Networks','Summit Tech',
    'Blue Harbor Logistics','Arctic Data Works','Northwave Commerce','Granite Health',
    'Skylab Robotics','Signal Forge','Cloud Fjell','Atlas Security','Deepfjord Energy',
    'Metro Platform Co','Riverline Retail','Coreflow Finance','Brightpath Media',
    'Pioneer Mobility','Edgepoint Manufacturing'
  ] AS arr
),
new_client_addresses AS (
  INSERT INTO address (street_name, street_number, post_number_id)
  SELECT
    'Klientveien' AS street_name,
    (400 + g)::TEXT AS street_number,
    (
      SELECT id
      FROM postnumbers
      ORDER BY (((g * 7919) + id) % 104729)
      LIMIT 1
    ) AS post_number_id
  FROM generate_series(1, 220) AS g
  RETURNING id
),
client_address_indexed AS (
  SELECT id AS address_id, ROW_NUMBER() OVER (ORDER BY id) AS rn
  FROM new_client_addresses
)
INSERT INTO clients (
  name,
  address_id,
  org_number,
  contact_email,
  industry,
  notes
)
SELECT
  CONCAT(
    (SELECT arr[((g - 1) % array_length(arr, 1)) + 1] FROM client_name_seed),
    ' ',
    g
  ) AS name,
  cai.address_id,
  CONCAT('NO9', LPAD(g::TEXT, 8, '0')) AS org_number,
  CONCAT('contact', g, '@client.example.com') AS contact_email,
  CASE ((g - 1) % 6) + 1
    WHEN 1 THEN 'Finance'
    WHEN 2 THEN 'Energy'
    WHEN 3 THEN 'Healthcare'
    WHEN 4 THEN 'Retail'
    WHEN 5 THEN 'Public Sector'
    ELSE 'Manufacturing'
  END AS industry,
  CONCAT('Primary account tier ', ((g - 1) % 4) + 1) AS notes
FROM generate_series(1, 220) AS g
JOIN client_address_indexed AS cai ON cai.rn = g;

-- 2% of developers get no assignment, a further 1% get two, the rest exactly one.
WITH developer_ranked AS (
  SELECT id AS developer_id, ROW_NUMBER() OVER (ORDER BY id) AS rn
  FROM person
),
person_total AS (
  SELECT COUNT(*) AS cnt FROM person
),
developer_counts AS (
  SELECT
    dr.developer_id,
    CASE
      WHEN dr.rn <= CEIL(pt.cnt * 0.02) THEN 0
      WHEN dr.rn <= CEIL(pt.cnt * 0.02) + CEIL(pt.cnt * 0.01) THEN 2
      ELSE 1
    END AS assignment_count
  FROM developer_ranked AS dr
  CROSS JOIN person_total AS pt
),
expanded_assignments AS (
  SELECT
    dc.developer_id,
    gs.n AS assignment_no
  FROM developer_counts AS dc
  JOIN LATERAL generate_series(1, dc.assignment_count) AS gs(n) ON true
),
client_indexed AS (
  SELECT id AS client_id, ROW_NUMBER() OVER (ORDER BY id) AS rn
  FROM clients
),
client_count AS (
  SELECT COUNT(*) AS cnt FROM clients
)
INSERT INTO assignments (
  client_id,
  developer_id,
  start_date,
  end_date,
  assignment_description
)
SELECT
  ci.client_id,
  ea.developer_id,
  DATE '2022-01-01' + ((ea.developer_id * 13 + ea.assignment_no * 29) % 900) * INTERVAL '1 day' AS start_date,
  (
    DATE '2022-01-01' + ((ea.developer_id * 13 + ea.assignment_no * 29) % 900) * INTERVAL '1 day'
  ) + (((ea.developer_id * 7 + ea.assignment_no * 11) % 1065) + 30) * INTERVAL '1 day' AS end_date,
  CASE
    WHEN ea.assignment_no = 2 THEN CONCAT('Secondary advisory assignment for developer ', ea.developer_id)
    ELSE CONCAT('Primary delivery assignment for developer ', ea.developer_id)
  END AS assignment_description
FROM expanded_assignments AS ea
CROSS JOIN client_count AS cc
JOIN client_indexed AS ci
  ON ci.rn = (((ea.developer_id * 37 + ea.assignment_no * 17) % cc.cnt) + 1);

CREATE INDEX IF NOT EXISTS idx_address_post_number_id ON address(post_number_id);
CREATE INDEX IF NOT EXISTS idx_person_name ON person(last_name, first_name);
CREATE INDEX IF NOT EXISTS idx_assignments_developer_id ON assignments(developer_id);
CREATE INDEX IF NOT EXISTS idx_assignments_client_id ON assignments(client_id);
CREATE INDEX IF NOT EXISTS idx_assignments_start_date ON assignments(start_date);

COMMIT;

ANALYZE;
