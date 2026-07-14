# Metric methodology

## Methodology contract

Every metric published by the analyzer must document:

1. Apple Health record type or source table.
2. Accepted source units and canonical display unit.
3. Aggregation method and local-day boundary.
4. Treatment of duplicate and overlapping observations.
5. Minimum data requirements.
6. Known source, device, and interpretation limitations.
7. Whether the result is a raw fact, descriptive statistic, heuristic, or forecast.

## Current metric catalog

The machine-readable catalogue lives in `apple_health_dashboard/services/metrics.py`. It currently covers activity, heart, body, sleep, nutrition, mobility, symptoms, and other common record types. The catalogue is the source of UI labels and should become the source of API documentation and validation rules.

## Interpretation policy

- Raw facts such as a recorded heart rate are labelled as observations.
- Descriptive metrics such as a seven-day average state the window and aggregation.
- Heuristics such as readiness require an explanation of inputs, weights, missing-data behavior, and validation status.
- Correlation views display sample size, time window, uncertainty, and a non-causation warning.
- Forecasts are opt-in, show uncertainty, and are never framed as clinical prediction.

## Initial migration priority

1. Steps, walking and running distance, active energy, exercise time, and stand time.
2. Resting heart rate, heart-rate variability, walking heart rate, and cardio fitness.
3. Sleep duration, stages, midpoint, and regularity.
4. Workout duration, distance, energy, sport type, and training load.
5. Weight, body composition, nutrition, mobility, and symptoms.

Advanced metrics only move into the new UI after their method and test coverage meet this contract.
