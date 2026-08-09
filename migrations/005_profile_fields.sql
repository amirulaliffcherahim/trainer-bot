-- 005: extended athlete profile fields (age, VO2 max, heart-rate baselines).
-- NULL = "n/a" (hard-to-attain values stay unset).

ALTER TABLE athlete_profile ADD COLUMN age INTEGER;
ALTER TABLE athlete_profile ADD COLUMN vo2_max REAL;
ALTER TABLE athlete_profile ADD COLUMN max_bpm INTEGER;
ALTER TABLE athlete_profile ADD COLUMN resting_bpm INTEGER;
