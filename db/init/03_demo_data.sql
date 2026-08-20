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
  END AS short_description
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
  short_description
)
SELECT
  s.first_name,
  s.last_name,
  s.email_address,
  a.id,
  s.short_description
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
  CONCAT('9', LPAD(g::TEXT, 8, '0')) AS org_number,
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

-- Technology pools and the "primary developer role" per profile_idx (same
-- 1-8 grouping used for seed_person). Reused below to pick per-assignment
-- technology subsets and to weight assignment roles toward developer roles.
CREATE TEMP TABLE profile_pool ON COMMIT DROP AS
SELECT * FROM (VALUES
  (1, ARRAY['Python','FastAPI','Django','PostgreSQL','Redis','Docker','gRPC','Celery']::TEXT[], 'Backend Developer', ARRAY['billing platform','payments API','order management system']::TEXT[]),
  (2, ARRAY['TypeScript','React','Vue','Vite','CSS','GraphQL','Playwright','Next.js']::TEXT[], 'Frontend Developer', ARRAY['customer portal','internal design system','self-service dashboard']::TEXT[]),
  (3, ARRAY['Python','dbt','Airflow','DuckDB','Spark','Snowflake','Kafka','BigQuery']::TEXT[], 'Data Engineer', ARRAY['data platform','analytics pipeline','reporting warehouse']::TEXT[]),
  (4, ARRAY['Terraform','Kubernetes','GitHub Actions','Prometheus','Grafana','AWS','Azure','Helm']::TEXT[], 'DevOps Engineer', ARRAY['deployment platform','cloud infrastructure','observability stack']::TEXT[]),
  (5, ARRAY['Flutter','Dart','Firebase','SQLite','REST','Kotlin','Swift','GraphQL']::TEXT[], 'Mobile Developer', ARRAY['mobile app','field service app','offline-first companion app']::TEXT[]),
  (6, ARRAY['Go','Rust','OWASP','SAST','SIEM','IAM','Vault','TLS']::TEXT[], 'Security Engineer', ARRAY['identity and access platform','security monitoring system','secrets management service']::TEXT[]),
  (7, ARRAY['Python','Pytest','Selenium','Cypress','Testcontainers','Playwright','JUnit','Postman']::TEXT[], 'QA Engineer', ARRAY['test automation platform','release quality gate','regression test suite']::TEXT[]),
  (8, ARRAY['TypeScript','Node.js','PostgreSQL','Docker','AWS','React','GraphQL','Rust']::TEXT[], 'Full-Stack Developer', ARRAY['product platform','self-service application','internal tooling suite']::TEXT[])
) AS t(profile_idx, tech_pool, developer_role, domain_nouns);

INSERT INTO technology (name)
SELECT DISTINCT unnest(tech_pool) FROM profile_pool
ON CONFLICT (name) DO NOTHING;

-- 2% of developers get no assignment, a further 1% get two, the rest exactly one.
CREATE TEMP TABLE seed_assignment ON COMMIT DROP AS
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
    gs.n AS assignment_no,
    ((dc.developer_id - 1) % 8) + 1 AS profile_idx
  FROM developer_counts AS dc
  JOIN LATERAL generate_series(1, dc.assignment_count) AS gs(n) ON true
),
client_indexed AS (
  SELECT id AS client_id, ROW_NUMBER() OVER (ORDER BY id) AS rn
  FROM clients
),
client_count AS (
  SELECT COUNT(*) AS cnt FROM clients
),
-- Assignment 1's dates depend only on developer_id; assignment 2 (the ~1%
-- with two assignments) always starts strictly after assignment 1 ends, so
-- the two ranges can never overlap and never trip excl_assignment_no_overlap.
-- 97% of assignment-1 rows are "active" (anchored around CURRENT_DATE, so
-- today falls within [base_start, base_end] and base_end is within a year
-- out); combined with the 2% of developers with no assignment at all, that
-- yields ~95% of all consultants showing as currently assigned.
assignment_flags AS (
  SELECT
    ea.developer_id,
    ea.assignment_no,
    ea.profile_idx,
    ((ea.developer_id * 31) % 100) < 97 AS is_active,
    (((ea.developer_id * 7) % 600) + 30) AS duration_days,
    ((ea.developer_id * 17) % 365) AS future_gap_days,
    (((ea.developer_id * 13) % 400) + 30) AS past_gap_days,
    (((ea.developer_id * 3) % 60) + 1) AS gap_days,
    -- capped one day short of the smallest possible 3-year span (Feb-29 edge case)
    (((ea.developer_id * 7 + 22) % 1064) + 30) AS second_duration_days
  FROM expanded_assignments AS ea
),
assignment_dates AS (
  SELECT
    af.developer_id,
    af.assignment_no,
    af.profile_idx,
    af.gap_days,
    af.second_duration_days,
    CASE
      WHEN af.is_active THEN CURRENT_DATE - af.duration_days * INTERVAL '1 day'
      ELSE (CURRENT_DATE - af.past_gap_days * INTERVAL '1 day') - af.duration_days * INTERVAL '1 day'
    END AS base_start,
    CASE
      WHEN af.is_active THEN CURRENT_DATE + af.future_gap_days * INTERVAL '1 day'
      ELSE CURRENT_DATE - af.past_gap_days * INTERVAL '1 day'
    END AS base_end
  FROM assignment_flags AS af
)
SELECT
  ad.developer_id,
  ad.assignment_no,
  ci.client_id,
  c.name AS client_name,
  pp.developer_role,
  pp.tech_pool[
    (((ad.developer_id * 5 + ad.assignment_no * 3) % 6) + 1)
    :
    (((ad.developer_id * 5 + ad.assignment_no * 3) % 6) + 1 + (1 + ((ad.developer_id + ad.assignment_no) % 2)))
  ] AS assignment_technologies,
  pp.domain_nouns[(((ad.developer_id * 3 + ad.assignment_no) % array_length(pp.domain_nouns, 1)) + 1)] AS domain_noun,
  CASE WHEN ad.assignment_no = 1 THEN ad.base_start ELSE ad.base_end + ad.gap_days * INTERVAL '1 day' END AS start_date,
  CASE
    WHEN ad.assignment_no = 1 THEN ad.base_end
    ELSE ad.base_end + ad.gap_days * INTERVAL '1 day' + ad.second_duration_days * INTERVAL '1 day'
  END AS end_date,
  -- ~80% of assignments keep the developer's own specialty role; the rest
  -- get a leadership role, so the overall mix stays majority-developer.
  CASE
    WHEN ((ad.developer_id * 17 + ad.assignment_no * 23) % 100) < 80 THEN pp.developer_role
    ELSE (ARRAY['Team Lead', 'Scrum Master', 'Product Owner', 'Solution Architect'])
      [(((ad.developer_id * 19 + ad.assignment_no * 31) % 4) + 1)]
  END AS role
FROM assignment_dates AS ad
CROSS JOIN client_count AS cc
JOIN client_indexed AS ci
  ON ci.rn = (((ad.developer_id * 37 + ad.assignment_no * 17) % cc.cnt) + 1)
JOIN clients AS c ON c.id = ci.client_id
JOIN profile_pool AS pp ON pp.profile_idx = ad.profile_idx;

INSERT INTO assignments (
  client_id,
  developer_id,
  start_date,
  end_date,
  assignment_description,
  role
)
SELECT
  client_id,
  developer_id,
  start_date,
  end_date,
  CONCAT(
    CASE WHEN assignment_no = 2 THEN 'Extend' ELSE 'Develop' END,
    ' a ', domain_noun, ' for ', client_name,
    ' using ', array_to_string(assignment_technologies, ', '), '.'
  ) AS assignment_description,
  role
FROM seed_assignment;

-- Single source of truth for the tech subset (seed_assignment, computed once
-- above); joined back on (developer_id, start_date), unique per developer
-- since assignment 2's start_date is always after assignment 1's end_date.
INSERT INTO assignment_technology (assignment_id, technology_id)
SELECT DISTINCT a.id, tech.id
FROM assignments AS a
JOIN seed_assignment AS sa
  ON sa.developer_id = a.developer_id AND sa.start_date = a.start_date
JOIN technology AS tech ON tech.name = ANY (sa.assignment_technologies);

CREATE INDEX IF NOT EXISTS idx_address_post_number_id ON address(post_number_id);
CREATE INDEX IF NOT EXISTS idx_person_name ON person(last_name, first_name);
CREATE INDEX IF NOT EXISTS idx_assignments_developer_id ON assignments(developer_id);
CREATE INDEX IF NOT EXISTS idx_assignments_client_id ON assignments(client_id);
CREATE INDEX IF NOT EXISTS idx_assignments_start_date ON assignments(start_date);

COMMIT;

ANALYZE;
