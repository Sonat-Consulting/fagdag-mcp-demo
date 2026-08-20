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

COMMIT;
