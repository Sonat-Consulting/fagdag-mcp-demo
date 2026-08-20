-- Depends on 01_schema.sql (tables) and 03_demo_data.sql (assignment data).
BEGIN;

-- Per-consultant years of experience per technology, summed across every
-- assignment where that technology was used. E.g. a consultant who worked
-- 2 years on Rust+Python then 3 years on Python-only shows ~2y Rust, ~5y Python.
-- Note: overlapping assignment date ranges for the same technology would be
-- double-counted here; the excl_assignment_no_overlap constraint on
-- assignments prevents that for a single developer.
CREATE OR REPLACE VIEW consultant_technology_experience AS
SELECT
  p.id AS person_id,
  p.first_name,
  p.last_name,
  t.name AS technology,
  ROUND(
    SUM(a.end_date - a.start_date) / 365.25,
    1
  ) AS years_experience
FROM person AS p
JOIN assignments AS a ON a.developer_id = p.id
JOIN assignment_technology AS at ON at.assignment_id = a.id
JOIN technology AS t ON t.id = at.technology_id
GROUP BY p.id, p.first_name, p.last_name, t.name;

-- One row per consultant: their assignment active today (if any), plus
-- whether they're currently assigned or available. LEFT JOIN stays 1:1
-- because excl_assignment_no_overlap forbids two active assignments at once.
CREATE OR REPLACE VIEW consultant_current_assignment AS
SELECT
  p.id AS person_id,
  p.first_name,
  p.last_name,
  a.client_id,
  a.start_date,
  a.end_date,
  (a.end_date - CURRENT_DATE) AS remaining_days,
  (a.id IS NOT NULL) AS is_assigned
FROM person AS p
LEFT JOIN assignments AS a
  ON a.developer_id = p.id
 AND CURRENT_DATE BETWEEN a.start_date AND a.end_date;

COMMIT;
