# Metric methods

## Quantity series

The metric catalog defines the supported record types, canonical display units and aggregation methods. Converted values are query results. The source observations table retains recorded values, units and timestamps. For percent units, HealthKit fractions in the 0–1 range are displayed as 0–100 percent. Values outside that range are excluded from these aggregates. Incompatible units and non-finite values are omitted. Numeric records with no published method remain inspectable in the Explorer. [Apple HealthKit percent unit](https://developer.apple.com/documentation/healthkit/hkunit/percent%28%29).

1. Select a metric and an inclusive range of recorded calendar dates. New records use the original offset and legacy records use their stored date. Date ranges can be anchored to historical data, including exports older than today's calendar windows.
2. Within a source and device, collapse equivalent observations with the same start, end, normalized value and day. Per day, select the source/device with the most compatible unique samples, breaking ties by source and device names. A source filter limits eligible sources before this selection.
3. For sums, conservatively omit positive-length intervals starting before an earlier interval ends. Independent point samples can contribute. An interval is assigned to its start day, without proration. This can undercount chained overlaps and can differ from Apple Health's own source priorities.
4. Sum compatible observations for cumulative quantities, use an unweighted sample mean for measures such as resting heart rate, or use the latest observation for measures such as body mass. Weekly and monthly views apply the same method to accepted observations in the bucket. Weeks start Monday. A bucket at the edge of the chosen range can be partial. The sample count is the number of accepted candidates in the bucket, including candidates considered when selecting the latest value.

The method panel reports contributing source names, excluded samples and observations with legacy timestamps. Missing periods have no plotted value. Charts use elapsed calendar spacing and break across missing buckets. Raw values stay visible for inspection. The application applies no universal physiological range or outlier rule.

## Sleep

Only explicit asleep categories contribute. Overlapping and adjacent asleep intervals form one continuous episode. An episode contributes elapsed time to the calendar day on which it ends. This includes naps. Specific stage time counts where exactly one of Core, Deep, or REM is active. Generic asleep entries support duration and do not assign a stage. Conflicting stages remain unclassified. Legacy timestamps use their stored values until reimport, which can affect elapsed time around offset changes.

## Workouts and rings

Same-type overlapping workouts form one group for the summary. A session with more usable reported quantities is preferred according to duration, distance, and energy availability in that order, then by elapsed duration, source name, and hash. Quantities come from compatible legacy attributes or recognized workout statistics. Missing quantities remain absent. The session list shows the latest 20 selected sessions. Different activity types can overlap and are reported separately. Activity rings retain fractional values. Move energy uses kilocalories, converting explicitly labelled kilojoules or joules. Older summaries with no unit attribute use the export's conventional kcal representation.

## Distributions and comparisons

Distribution bins describe observed buckets in the selected aggregate series. The median weights each displayed bucket equally. With at least eight observations and a nonzero interquartile range, the distribution reports how many buckets fall more than 1.5 interquartile ranges beyond either quartile. Flagged buckets remain visible. The Pearson comparison uses shared dates from the two daily series, at least 14 pairs, and variation in both variables. There is no missing-value imputation, significance test, or adjustment for autocorrelation, sampling, or confounders. The result is descriptive. Correlation does not establish causation.
