import { useEffect, useId, useState, type PointerEvent } from "react";

export type Grain = "day" | "week" | "month";
export type PlotPoint = { date: string; value: number | null };
const dayMs = 86_400_000;

export function formatDate(value: string | null) {
  return value ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeZone: "UTC" })
    .format(new Date(value.slice(0, 10) + "T00:00:00Z")) : "Unavailable";
}

export function formatNumber(value: number | null, digits = 2) {
  return value === null ? "Unavailable" : new Intl.NumberFormat(undefined, { maximumFractionDigits: digits }).format(value);
}

export function DataTable({ headings, rows }: { headings: string[]; rows: string[][] }) {
  if (!rows.length) return <p className="empty-panel">No rows match this selection.</p>;
  return <div className="table-wrap" tabIndex={0} role="region" aria-label={headings.join(", ")}><table>
    <thead><tr>{headings.map((heading) => <th scope="col" key={heading}>{heading}</th>)}</tr></thead>
    <tbody>{rows.map((row, index) => <tr key={index}>{row.map((cell, column) => <td key={column}>{cell}</td>)}</tr>)}</tbody>
  </table></div>;
}

export function useRequest<T>(load: (() => Promise<T>) | null, key: string) {
  const [result, setResult] = useState<{ key: string; data: T | null; error: string | null }>({ key: "", data: null, error: null });
  useEffect(() => {
    if (!load) return;
    let active = true;
    void load().then((data) => {
      if (active) setResult({ key, data, error: null });
    }).catch((error: Error) => {
      if (active) setResult({ key, data: null, error: error.message });
    });
    return () => { active = false; };
  }, [key]); // The key identifies the complete request, including profile revision.
  const current = load && result.key === key;
  return { data: current ? result.data : null, error: current ? result.error : null, loading: Boolean(load && !current) };
}

export function RequestStatus({ loading, error }: { loading: boolean; error: string | null }) {
  if (loading) return <p role="status" className="notice">Loading local data…</p>;
  if (error) return <p role="alert" className="notice error">{error}</p>;
  return null;
}

export function LineChart({ points, label, unit = "", grain = "day", domain }: {
  points: PlotPoint[]; label: string; unit?: string; grain?: Grain; domain?: [string, string];
}) {
  const id = useId();
  const [active, setActive] = useState<number | null>(null);
  const valid = points.filter((point): point is { date: string; value: number } => point.value !== null && Number.isFinite(point.value));
  if (!valid.length) return <p className="empty-panel">No compatible values in this period.</p>;
  const values = valid.map(({ value }) => value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const padding = min === max ? Math.max(Math.abs(min) * .05, .1) : (max - min) * .12;
  const bottom = min - padding;
  const top = max + padding;
  const first = Math.min(Date.parse(domain?.[0] ?? points[0].date), Date.parse(points[0].date));
  const last = Math.max(Date.parse(domain?.[1] ?? points.at(-1)!.date), Date.parse(points.at(-1)!.date));
  const x = (instant: number) => last === first ? 300 : 10 + 580 * (instant - first) / (last - first);
  const y = (value: number) => 158 - 150 * (value - bottom) / (top - bottom);
  let previous = NaN;
  const path = valid.map(({ date, value }) => {
    const instant = Date.parse(date);
    const previousDate = new Date(previous);
    const contiguous = grain === "month"
      ? Date.UTC(previousDate.getUTCFullYear(), previousDate.getUTCMonth() + 1, 1) === instant
      : instant - previous === dayMs * (grain === "week" ? 7 : 1);
    previous = instant;
    const position = `${x(instant)},${y(value)}`;
    return contiguous ? `L${position}` : `M${position}h.01M${position}`;
  }).join(" ");
  const index = Math.min(active ?? valid.length - 1, valid.length - 1);
  const selected = valid[index];
  const selectedX = x(Date.parse(selected.date));
  const pointerMove = (event: PointerEvent<SVGSVGElement>) => {
    const bounds = event.currentTarget.getBoundingClientRect();
    const position = (event.clientX - bounds.left) * 600 / bounds.width;
    const instant = first + (last - first) * (position - 10) / 580;
    let lo = 0;
    let hi = valid.length - 1;
    while (lo < hi) {
      const mid = Math.floor((lo + hi) / 2);
      if (Date.parse(valid[mid].date) < instant) lo = mid + 1;
      else hi = mid;
    }
    setActive(lo > 0 && Math.abs(Date.parse(valid[lo - 1].date) - instant) <= Math.abs(Date.parse(valid[lo].date) - instant) ? lo - 1 : lo);
  };
  return <figure className="trend-chart" aria-label={label}>
    <figcaption className="chart-readout"><strong>{formatNumber(selected.value)} {unit}</strong><span>{formatDate(selected.date)}</span></figcaption>
    <div className="chart-body">
      <div className="chart-labels" aria-hidden="true">{[top, (top + bottom) / 2, bottom].map((n) => <span key={n}>{formatNumber(n, 1)}</span>)}</div>
      <svg viewBox="0 0 600 166" preserveAspectRatio="none" role="img" aria-label={`${label}. Observed range ${formatNumber(min)} to ${formatNumber(max)} ${unit}.`} onPointerMove={pointerMove}>
        {[8, 83, 158].map((level) => <line key={level} x1="0" x2="600" y1={level} y2={level} className="chart-gridline" />)}
        <path d={path} className="chart-line" />
        {valid.length <= 180 && valid.map(({ date, value }) => <circle key={date} cx={x(Date.parse(date))} cy={y(value)} r="2.5" className="chart-dot" />)}
        <line x1={selectedX} x2={selectedX} y1={8} y2={158} className="chart-cursor" />
        <circle cx={selectedX} cy={y(selected.value)} r="5" className="chart-focus" />
      </svg>
    </div>
    <div className="chart-dates"><span>{formatDate(new Date(first).toISOString())}</span><span>{formatDate(new Date(last).toISOString())}</span></div>
    {valid.length > 1 && <div className="chart-scrubber">
      <label htmlFor={id}>Inspect date</label>
      <input id={id} type="range" min="0" max={valid.length - 1} value={index} onChange={(event) => setActive(Number(event.target.value))}
        aria-valuetext={`${formatDate(selected.date)}, ${formatNumber(selected.value)} ${unit}`} />
    </div>}
  </figure>;
}
