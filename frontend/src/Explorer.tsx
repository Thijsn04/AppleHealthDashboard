import { useState } from "react";
import { Download } from "lucide-react";

import { getMetricSeries, getRecords, type AvailableType, type Filters, type MetricSeries, type RecordPage } from "./api";
import { DataTable, formatDate, formatNumber, LineChart, RequestStatus, useRequest, type Grain } from "./ui";

function downloadSeries(series: MetricSeries) {
  const csv = ["date,value,unit,samples", ...series.points.map((p) => [p.date, p.value, p.unit ?? "", p.sample_count].join(","))];
  const url = URL.createObjectURL(new Blob([csv.join("\r\n")], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = "apple-health-series.csv";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function MetricChart({ type, series, domain }: { type: AvailableType; series: MetricSeries; domain: [string, string] }) {
  const unit = series.points[0]?.unit ?? "";
  const method = { sum: "Total", mean: "Sample mean", last: "Latest observation" }[series.aggregation];
  return <section className="panel metric-panel">
    <header className="panel-heading"><div><h2>{type.label}</h2><p>{method} per {series.grain} · {series.points.length.toLocaleString()} observed {series.grain}s</p></div>
      {series.points.length > 0 && <button type="button" className="button subtle" onClick={() => downloadSeries(series)}><Download size={16} aria-hidden="true" /> CSV</button>}
    </header>
    <LineChart key={series.points[0]?.date} points={series.points} label={type.label} unit={unit} grain={series.grain} domain={domain} />
    <details className="method">
      <summary>Method and contributing records</summary>
      <p>Uses the source and device with the most compatible samples for each recorded calendar day. Exact equivalent observations are counted once. Totals also skip overlapping intervals within that source.</p>
      <p>{series.sources.map((source) => source ?? "Unknown source").join(", ") || "No contributing source"}. {series.excluded_samples.toLocaleString()} observations excluded. {series.legacy_samples > 0 && `${series.legacy_samples.toLocaleString()} legacy observations lack export offsets.`}</p>
      <PointTable series={series} />
    </details>
  </section>;
}

function PointTable({ series }: { series: MetricSeries }) {
  const [page, setPage] = useState(0);
  const newest = series.points.slice().reverse();
  const start = page * 25;
  return <>
    <DataTable headings={["Period start", "Value", "Samples"]} rows={newest.slice(start, start + 25).map((p) => [
      formatDate(p.date), `${formatNumber(p.value)} ${p.unit ?? ""}`, p.sample_count.toLocaleString(),
    ])} />
    {newest.length > 25 && <Pagination page={page} pageCount={Math.ceil(newest.length / 25)} change={setPage} />}
  </>;
}

function Pagination({ page, pageCount, change }: { page: number; pageCount: number; change: (next: number) => void }) {
  return <div className="pagination">
    <button type="button" className="button subtle" disabled={page === 0} onClick={() => change(page - 1)}>Previous</button>
    <span aria-live="polite">Page {page + 1} of {pageCount}</span>
    <button type="button" className="button subtle" disabled={page + 1 >= pageCount} onClick={() => change(page + 1)}>Next</button>
  </div>;
}

function Distribution({ series }: { series: MetricSeries }) {
  const values = series.points.map((point) => point.value).sort((a, b) => a - b);
  if (!values.length) return null;
  const min = values[0];
  const max = values.at(-1)!;
  const quantile = (fraction: number) => {
    const index = (values.length - 1) * fraction;
    const left = Math.floor(index);
    return values[left] + (values[Math.ceil(index)] - values[left]) * (index - left);
  };
  const median = quantile(.5);
  const q1 = quantile(.25);
  const q3 = quantile(.75);
  const iqr = q3 - q1;
  const flagged = values.length >= 8 && iqr > 0
    ? values.filter((value) => value < q1 - 1.5 * iqr || value > q3 + 1.5 * iqr).length
    : null;
  const bins = min === max ? 1 : Math.min(10, Math.ceil(Math.sqrt(values.length)));
  const width = (max - min) / bins;
  const counts = Array<number>(bins).fill(0);
  for (const value of values) counts[width === 0 ? 0 : Math.min(bins - 1, Math.floor((value - min) / width))]++;
  const highest = Math.max(...counts);
  const unit = series.points[0]?.unit ?? "";
  return <section className="panel">
    <header className="panel-heading"><div><h2>Distribution</h2><p>{values.length.toLocaleString()} observed {series.grain}s · Median {formatNumber(median)} {unit}</p></div></header>
    <div className="histogram" aria-hidden="true">
      {counts.map((count, index) => <div key={index} style={{ height: `${count * 100 / highest}%` }} title={`${count} observed periods`} />)}
    </div>
    <div className="chart-dates"><span>{formatNumber(min)} {unit}</span><span>{formatNumber(max)} {unit}</span></div>
    <details className="method"><summary>Frequency table</summary>
      {flagged !== null && <p>{flagged} periods fall outside the 1.5× interquartile range fences. These values stay in the distribution.</p>}
      <DataTable headings={["Lower bound", "Upper bound", "Periods"]} rows={counts.map((count, i) => [
      formatNumber(min + width * i, 4), formatNumber(i + 1 === bins ? max : min + width * (i + 1), 4), String(count),
    ])} /></details>
  </section>;
}

function Correlation({ left, right }: { left: MetricSeries; right: MetricSeries }) {
  const rightValues = new Map(right.points.map((p) => [p.date, p.value]));
  const pairs = left.points.flatMap((p) => {
    const value = rightValues.get(p.date);
    return value === undefined ? [] : [[p.value, value]];
  });
  const size = pairs.length;
  const xMean = pairs.reduce((total, [x]) => total + x, 0) / size;
  const yMean = pairs.reduce((total, [, y]) => total + y, 0) / size;
  let xx = 0;
  let yy = 0;
  let xy = 0;
  for (const [x, y] of pairs) {
    xx += (x - xMean) ** 2;
    yy += (y - yMean) ** 2;
    xy += (x - xMean) * (y - yMean);
  }
  const coefficient = size >= 14 && xx > 0 && yy > 0 ? Math.max(-1, Math.min(1, xy / Math.sqrt(xx * yy))) : null;
  return <section className="panel correlation">
    <div><h2>Paired comparison</h2><p>{size} shared daily observations</p></div>
    {coefficient === null ? <p>Pearson correlation needs at least 14 shared dates and variation in both metrics.</p> :
      <><strong>{formatNumber(coefficient)} <small>Pearson r</small></strong><p>Descriptive association for this selection. Shared trends and timing can affect the result. Correlation does not establish causation.</p></>}
  </section>;
}

function Observations({ data, changePage }: { data: RecordPage; changePage: (page: number) => void }) {
  return <section className="panel">
    <header className="panel-heading"><div><h2>Source observations</h2><p>{data.total.toLocaleString()} matching records</p></div></header>
    <DataTable headings={["Type", "Start timestamp", "End timestamp", "Recorded value", "Source / device"]} rows={data.items.map((item) => [
      item.record_type.replace(/^HK(?:Quantity|Category|Correlation)TypeIdentifier/, "").replace(/([a-z])([A-Z])/g, "$1 $2"),
      item.start_at.replace("T", " ") + (item.legacy_timestamp ? " (legacy offset unknown)" : ""),
      item.end_at.replace("T", " "),
      item.value === null ? item.value_str ?? "Unavailable" : `${item.value} ${item.unit ?? ""}`,
      [item.source_name ?? "Unknown source", item.source_version, item.device].filter(Boolean).join(" · "),
    ])} />
    {data.total > data.limit && <Pagination page={Math.floor(data.offset / data.limit)} pageCount={Math.ceil(data.total / data.limit)} change={changePage} />}
  </section>;
}

export function Explorer({ types, revision, category }: { types: AvailableType[]; revision: number; category?: string }) {
  const [selected, setSelected] = useState<string | null>(null);
  const [comparison, setComparison] = useState("");
  const [source, setSource] = useState("");
  const [grain, setGrain] = useState<Grain>("day");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [page, setPage] = useState(0);
  const visible = category ? types.filter((type) => type.category === category) : types;
  const selectedType = visible.find((type) => type.record_type === selected)
    ?? (selected === "" ? undefined : visible.find((type) => type.chartable) ?? visible[0]);
  const comparedType = types.find((type) => type.record_type === comparison && type.record_type !== selectedType?.record_type && type.chartable);
  const defaultEnd = selectedType?.last_day ?? types.reduce((last, type) => type.last_day > last ? type.last_day : last, "");
  const defaultStart = defaultEnd ? new Date(Date.parse(defaultEnd) - 89 * 86_400_000).toISOString().slice(0, 10) : "";
  const from = start || defaultStart;
  const to = end || defaultEnd;
  const rangeValid = Boolean(from && to && from <= to && Date.parse(to) - Date.parse(from) < 3650 * 86_400_000);
  const firstBucket = new Date(Date.parse(from));
  if (grain === "week") firstBucket.setUTCDate(firstBucket.getUTCDate() - ((firstBucket.getUTCDay() + 6) % 7));
  if (grain === "month") firstBucket.setUTCDate(1);
  const domain: [string, string] = [rangeValid ? firstBucket.toISOString().slice(0, 10) : from, to];
  const filters: Filters = { start: from, end: to, grain, source: source === "unknown" ? "" : source.slice(7) || undefined };
  const key = JSON.stringify([revision, selectedType?.record_type, comparedType?.record_type, filters]);
  const series = useRequest(rangeValid && selectedType?.chartable ? () => getMetricSeries(selectedType.record_type, filters) : null, key);
  const compare = useRequest(rangeValid && comparedType ? () => getMetricSeries(comparedType.record_type, { start: from, end: to, grain }) : null, key);
  const observations = useRequest(!category && rangeValid ? () => getRecords(selectedType?.record_type, page * 50, {
    start: from, end: to, source: filters.source,
  }) : null, key + page);
  return <div className="workspace">
    {visible.length === 0 ? <p className="empty-panel">No {category ? category.toLowerCase() + " " : ""}observations are available. Import an export to begin.</p> : <>
      <section className="panel filter-panel" aria-label="Analysis filters">
        <div className="filter-grid">
          <label>Metric<select value={selectedType?.record_type ?? ""} onChange={(event) => {
            setSelected(event.target.value); setSource(""); setPage(0);
          }}>
            {!category && <option value="">All observations</option>}
            {visible.map((type) => <option key={type.record_type} value={type.record_type}>{type.label}</option>)}
          </select></label>
          <label>Source<select value={source} onChange={(event) => { setSource(event.target.value); setPage(0); }}>
            <option value="">Automatic</option>
            {selectedType?.sources.map((name) => <option key={name ?? ""} value={name === null ? "unknown" : `source:${name}`}>{name ?? "Unknown source"}</option>)}
          </select></label>
          {!category && <label>Compare with<select value={comparedType?.record_type ?? ""} onChange={(event) => setComparison(event.target.value)} disabled={!selectedType?.chartable}>
            <option value="">None</option>
            {types.filter((type) => type.chartable && type.record_type !== selectedType?.record_type).map((type) => <option key={type.record_type} value={type.record_type}>{type.label}</option>)}
          </select></label>}
          <label>Group by<select value={grain} onChange={(event) => setGrain(event.target.value as Grain)}>
            <option value="day">Day</option><option value="week">Week</option><option value="month">Month</option>
          </select></label>
          <label>From<input type="date" value={from} onChange={(event) => { setStart(event.target.value); setPage(0); }} /></label>
          <label>Through<input type="date" value={to} onChange={(event) => { setEnd(event.target.value); setPage(0); }} /></label>
        </div>
        {selectedType && <p className="coverage">{selectedType.count.toLocaleString()} recorded observations · {formatDate(selectedType.first_day)} to {formatDate(selectedType.last_day)}</p>}
        {!rangeValid && <p className="notice error" role="alert">Choose an ordered range of up to 3,650 days.</p>}
      </section>
      <RequestStatus {...series} />
      <RequestStatus {...compare} />
      {selectedType && !selectedType.chartable && <p className="empty-panel">This type is available for source inspection. A numeric trend method is unavailable.</p>}
      {series.data && selectedType && <div className="workspace-columns">
        <MetricChart key={key} type={selectedType} series={series.data} domain={domain} />
        <Distribution series={series.data} />
      </div>}
      {series.data && compare.data && comparedType && <>
        <MetricChart key={`comparison-${key}`} type={comparedType} series={compare.data} domain={domain} />
        {grain === "day" && <Correlation left={series.data} right={compare.data} />}
      </>}
      <RequestStatus {...observations} />
      {observations.data && <Observations data={observations.data} changePage={setPage} />}
    </>}
  </div>;
}
