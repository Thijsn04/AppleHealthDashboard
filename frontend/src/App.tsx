import { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  ArrowRight,
  Bot,
  Database,
  HeartPulse,
  LockKeyhole,
  Moon,
  Settings,
  ShieldCheck,
  Upload,
  UserRound
} from "lucide-react";
import { Link, NavLink, Route, Routes, useParams } from "react-router-dom";

import {
  confirmImport,
  getAvailableTypes,
  getHealth,
  getMetricSeries,
  getOverview,
  getRecords,
  getRings,
  getSleepSummary,
  getWorkoutSummary,
  previewImport,
  type AvailableType,
  type ImportPreview,
  type Overview,
  type RecordPage,
  type RingDay,
  type SleepSummary,
  type WorkoutSummary
} from "./api";

type LoadState = "loading" | "ready" | "error";
type ImportState = "idle" | "previewing" | "reviewing" | "importing" | "error";

const navigation = [
  { to: "/", label: "Overview", icon: Activity, end: true },
  { to: "/metrics/activity", label: "Activity", icon: Activity },
  { to: "/metrics/heart", label: "Heart", icon: HeartPulse },
  { to: "/sleep", label: "Sleep", icon: Moon },
  { to: "/workouts", label: "Workouts", icon: Activity },
  { to: "/metrics/body", label: "Body", icon: Activity },
  { to: "/metrics/nutrition", label: "Nutrition", icon: Activity },
  { to: "/metrics/mobility", label: "Mobility", icon: Activity },
  { to: "/metrics/symptoms", label: "Symptoms", icon: Activity },
  { to: "/explore", label: "Explore", icon: Database },
  { to: "/settings", label: "Settings", icon: Settings }
];

const categoryNames: Record<string, string> = {
  activity: "Activity", heart: "Heart", body: "Body", nutrition: "Nutrition", mobility: "Mobility",
  respiratory: "Respiratory", symptoms: "Symptoms", environment: "Environment", mind: "Mind", other: "Other"
};

function formatDate(value: string | null): string {
  if (!value) return "Not imported";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(value));
}

function formatNumber(value: number | null, maximumFractionDigits = 1): string {
  if (value === null) return "No data";
  return new Intl.NumberFormat(undefined, { maximumFractionDigits }).format(value);
}

function useRequest<T>(request: () => Promise<T>, dependencies: unknown[]) {
  const [state, setState] = useState<LoadState>("loading");
  const [data, setData] = useState<T | null>(null);
  useEffect(() => {
    let active = true;
    setState("loading");
    void request().then((result) => {
      if (active) { setData(result); setState("ready"); }
    }).catch(() => { if (active) setState("error"); });
    return () => { active = false; };
  // The caller owns the dependency list for an endpoint request.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, dependencies);
  return { state, data };
}

function InlineStatus({ state, empty = "No exported data is available for this view yet." }: { state: LoadState; empty?: string }) {
  if (state === "loading") return <p className="muted" aria-live="polite">Loading local analytics...</p>;
  if (state === "error") return <p className="notice error">{empty}</p>;
  return null;
}

function LineChart({ points, valueKey = "value", label }: { points: Array<{ date: string } & Record<string, unknown>>; valueKey?: string; label: string }) {
  const values = points.map((point) => Number(point[valueKey])).filter(Number.isFinite);
  if (!values.length) return <div className="empty-chart">No compatible measurements in this period.</div>;
  const width = 720;
  const height = 220;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const coordinates = points.map((point, index) => {
    const value = Number(point[valueKey]);
    const x = points.length === 1 ? width / 2 : (index / (points.length - 1)) * width;
    const y = height - ((value - min) / range) * (height - 32) - 16;
    return `${x},${y}`;
  }).join(" ");
  return (
    <figure className="chart" aria-label={label}>
      <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" role="img" aria-label={`${label}. Values range from ${formatNumber(min)} to ${formatNumber(max)}.`}>
        <line x1="0" y1={height - 16} x2={width} y2={height - 16} className="chart-axis" />
        <polyline points={coordinates} className="chart-line" />
      </svg>
      <figcaption><span>{formatDate(points[0].date)}</span><span>{formatDate(points[points.length - 1].date)}</span></figcaption>
    </figure>
  );
}

function OverviewPage({ overview, onImport }: { overview: Overview; onImport: () => void }) {
  const modules = [
    { label: "Activity", detail: "Steps, distance, energy, rings, and training load.", path: "/metrics/activity", icon: Activity },
    { label: "Heart", detail: "Heart rate, HRV, cardio fitness, and respiratory trends.", path: "/metrics/heart", icon: HeartPulse },
    { label: "Sleep", detail: "Duration, stages, schedule consistency, and recovery context.", path: "/sleep", icon: Moon },
    { label: "Explore", detail: "Search, filter, inspect, and verify source data you own.", path: "/explore", icon: Database }
  ];
  return <>
    <section className="hero-panel">
      <div>
        <span className="hero-icon"><ShieldCheck size={20} aria-hidden="true" /></span>
        <h2>{overview.has_data ? "Your latest health overview" : "Start with a private import"}</h2>
        <p>{overview.has_data ? `Your local profile contains ${overview.record_count.toLocaleString()} observations through ${formatDate(overview.last_record_at)}.` : "Import an Apple Health export to create a local profile. Your source file stays on this device."}</p>
      </div>
      <button className="primary-action" type="button" onClick={onImport}><Upload size={18} aria-hidden="true" /> Import export <ArrowRight size={16} aria-hidden="true" /></button>
    </section>
    <section className="stat-grid" aria-label="Profile summary">
      <article className="stat-card"><span>Observations</span><strong>{overview.record_count.toLocaleString()}</strong></article>
      <article className="stat-card"><span>Workouts</span><strong>{overview.workout_count.toLocaleString()}</strong></article>
      <article className="stat-card"><span>Ring days</span><strong>{overview.ring_day_count.toLocaleString()}</strong></article>
      <article className="stat-card"><span>First record</span><strong>{formatDate(overview.first_record_at)}</strong></article>
    </section>
    <section className="section-heading"><div><p className="eyebrow">Analyze with context</p><h2>Built around the questions that matter.</h2></div><span className="method-note">Methods and limitations are always visible.</span></section>
    <section className="module-grid">
      {modules.map(({ label, detail, path, icon: Icon }) => <article className="module-card" key={label}><Icon size={22} aria-hidden="true" /><h3>{label}</h3><p>{detail}</p><Link to={path}>Open {label} <ArrowRight size={15} aria-hidden="true" /></Link></article>)}
    </section>
  </>;
}

function MetricPage({ types }: { types: AvailableType[] }) {
  const { category = "activity" } = useParams();
  const name = categoryNames[category] ?? "Other";
  const categoryTypes = useMemo(() => types.filter((item) => item.category === name), [name, types]);
  const [selected, setSelected] = useState<string>("");
  useEffect(() => { setSelected(categoryTypes[0]?.record_type ?? ""); }, [category, categoryTypes]);
  const series = useRequest(() => getMetricSeries(selected), [selected]);
  return <section className="page-stack">
    <div className="page-intro"><p className="eyebrow">{name} metrics</p><h2>{name} trends from your local export</h2><p>Choose a metric to inspect its daily aggregation. The method follows the documented metric catalog.</p></div>
    {!categoryTypes.length && <section className="empty-panel">No {name.toLowerCase()} measurements are present in this import. The Explorer still lets you inspect every exported type.</section>}
    {categoryTypes.length > 0 && <>
      <label className="field-label">Metric<select value={selected} onChange={(event) => setSelected(event.target.value)}>{categoryTypes.map((item) => <option key={item.record_type} value={item.record_type}>{friendlyMetric(item.record_type)} ({item.count.toLocaleString()})</option>)}</select></label>
      <InlineStatus state={series.state} />
      {series.data && <section className="analysis-card"><div className="card-header"><div><h3>{friendlyMetric(series.data.record_type)}</h3><p>{series.data.aggregation} aggregation by local calendar day</p></div><span>{series.data.points.length} days</span></div><LineChart points={series.data.points} label={`${friendlyMetric(series.data.record_type)} trend`} /><DataTable headings={["Date", "Value", "Samples"]} rows={series.data.points.slice(-10).reverse().map((point) => [formatDate(point.date), `${formatNumber(point.value)} ${point.unit ?? ""}`, point.sample_count.toLocaleString()])} /></section>}
    </>}
  </section>;
}

function SleepPage() {
  const result = useRequest(getSleepSummary, []);
  const data = result.data;
  return <section className="page-stack"><div className="page-intro"><p className="eyebrow">Sleep</p><h2>Nightly sleep, separated from time in bed.</h2><p>Only Apple Health intervals labelled as asleep are included in the primary duration trend.</p></div><InlineStatus state={result.state} />{data && <><section className="stat-grid compact"><article className="stat-card"><span>Average sleep</span><strong>{formatNumber(data.average_hours)} h</strong></article><article className="stat-card"><span>Nights logged</span><strong>{data.night_count}</strong></article></section><section className="analysis-card"><div className="card-header"><h3>Nightly duration</h3><span>Hours asleep</span></div><LineChart points={data.nightly.map((point) => ({ ...point, value: point.hours, unit: "h", sample_count: 1 }))} label="Nightly sleep duration" /></section><DataTable headings={["Stage", "Hours"]} rows={data.stages.map((stage) => [stage.label, formatNumber(stage.hours)])} /></>}</section>;
}

function WorkoutsPage() {
  const result = useRequest(getWorkoutSummary, []);
  const data = result.data;
  return <section className="page-stack"><div className="page-intro"><p className="eyebrow">Workouts</p><h2>Training volume with the source details intact.</h2><p>Totals are based on explicitly exported workout sessions for the last 365 days.</p></div><InlineStatus state={result.state} />{data && <><section className="stat-grid compact"><article className="stat-card"><span>Sessions</span><strong>{data.total_workouts}</strong></article><article className="stat-card"><span>Duration</span><strong>{formatNumber(data.total_duration_hours)} h</strong></article><article className="stat-card"><span>Distance</span><strong>{formatNumber(data.total_distance_km)} km</strong></article><article className="stat-card"><span>Energy</span><strong>{formatNumber(data.total_energy_kcal, 0)} kcal</strong></article></section><section className="analysis-card"><div className="card-header"><h3>Weekly training volume</h3><span>Hours</span></div><LineChart points={data.weekly.map((point) => ({ ...point, value: point.duration_hours, unit: "h", sample_count: point.count }))} label="Weekly workout duration" /></section><DataTable headings={["Workout type", "Sessions", "Hours"]} rows={data.by_type.map((item) => [item.label, item.count.toString(), formatNumber(item.duration_hours)])} /></>}</section>;
}

function RingsPage() {
  const result = useRequest(getRings, []);
  return <section className="page-stack"><div className="page-intro"><p className="eyebrow">Activity rings</p><h2>Ring progress from Apple Activity summaries.</h2><p>Ring values are available only when the selected export contains ActivitySummary entries.</p></div><InlineStatus state={result.state} />{result.data && <RingsContent data={result.data} />}</section>;
}

function RingsContent({ data }: { data: RingDay[] }) {
  if (!data.length) return <section className="empty-panel">No Activity ring summaries are available in this export.</section>;
  const points = data.map((item) => ({ date: item.date, value: item.active_energy_kcal ?? 0, unit: "kcal", sample_count: 1 }));
  return <section className="analysis-card"><div className="card-header"><h3>Active energy</h3><span>Last 90 days</span></div><LineChart points={points} label="Daily active energy" /><DataTable headings={["Date", "Move", "Exercise", "Stand"]} rows={data.slice(-10).reverse().map((item) => [formatDate(item.date), `${formatNumber(item.active_energy_kcal, 0)} / ${formatNumber(item.active_energy_goal_kcal, 0)} kcal`, `${formatNumber(item.exercise_minutes, 0)} / ${formatNumber(item.exercise_goal_minutes, 0)} min`, `${formatNumber(item.stand_hours, 0)} / ${formatNumber(item.stand_goal_hours, 0)} h`])} /></section>;
}

function ExplorerPage({ types }: { types: AvailableType[] }) {
  const [selected, setSelected] = useState("");
  const [offset, setOffset] = useState(0);
  useEffect(() => { setOffset(0); }, [selected]);
  const records = useRequest(() => getRecords(selected || undefined, offset), [selected, offset]);
  return <section className="page-stack"><div className="page-intro"><p className="eyebrow">Explorer</p><h2>Inspect source observations with a bounded, local-only browser.</h2><p>Raw records are paginated and shown only after you open this view.</p></div><label className="field-label">Record type<select value={selected} onChange={(event) => setSelected(event.target.value)}><option value="">All exported types</option>{types.map((item) => <option key={item.record_type} value={item.record_type}>{friendlyMetric(item.record_type)} ({item.count.toLocaleString()})</option>)}</select></label><InlineStatus state={records.state} />{records.data && <RecordTable data={records.data} onPrevious={() => setOffset(Math.max(0, offset - records.data!.limit))} onNext={() => setOffset(offset + records.data!.limit)} />}</section>;
}

function RecordTable({ data, onPrevious, onNext }: { data: RecordPage; onPrevious: () => void; onNext: () => void }) {
  return <section className="analysis-card"><div className="card-header"><div><h3>Source records</h3><p>{data.total.toLocaleString()} records match this filter</p></div><span>Page {Math.floor(data.offset / data.limit) + 1}</span></div><DataTable headings={["Type", "Start", "Value", "Source"]} rows={data.items.map((item) => [friendlyMetric(item.record_type), formatDate(item.start_at), item.value !== null ? `${formatNumber(item.value)} ${item.unit ?? ""}` : item.value_str ?? "No value", item.source_name ?? "Unknown"])} /><div className="pagination"><button className="secondary-action" disabled={data.offset === 0} onClick={onPrevious}>Previous</button><button className="secondary-action" disabled={data.offset + data.limit >= data.total} onClick={onNext}>Next</button></div></section>;
}

function SettingsPage({ overview }: { overview: Overview }) {
  return <section className="page-stack"><div className="page-intro"><p className="eyebrow">Settings and privacy</p><h2>Your analysis stays under your control.</h2><p>The current build is local-only. It does not require an account or send Apple Health exports to a hosted service.</p></div><section className="analysis-card"><DataTable headings={["Setting", "Current value"]} rows={[["Network mode", "Local-only"], ["Database", overview.database_path], ["Imported observations", overview.record_count.toLocaleString()], ["Medical status", "Not a medical device or diagnostic tool"]]} /></section><section className="empty-panel"><Bot size={20} aria-hidden="true" /><div><strong>Assistant migration note</strong><p>The legacy cloud-backed health chat is intentionally not carried into the new frontend. A future assistant must be opt-in, transparent about every external request, and safe for private health data.</p></div></section></section>;
}

function DataTable({ headings, rows }: { headings: string[]; rows: string[][] }) {
  if (!rows.length) return <section className="empty-panel">No data is available for this selection.</section>;
  return <div className="table-wrap"><table><thead><tr>{headings.map((heading) => <th key={heading}>{heading}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={`${row.join("-")}-${index}`}>{row.map((value, cellIndex) => <td key={`${value}-${cellIndex}`}>{value}</td>)}</tr>)}</tbody></table></div>;
}

function friendlyMetric(recordType: string): string {
  return recordType.replace(/^HK(?:Quantity|Category|Correlation|Characteristic)TypeIdentifier/, "").replace(/([a-z])([A-Z])/g, "$1 $2");
}

export function App() {
  const [state, setState] = useState<LoadState>("loading");
  const [overview, setOverview] = useState<Overview | null>(null);
  const [types, setTypes] = useState<AvailableType[]>([]);
  const [importState, setImportState] = useState<ImportState>("idle");
  const [stagedImport, setStagedImport] = useState<ImportPreview | null>(null);
  const [importMessage, setImportMessage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const reload = async () => { await getHealth(); const [nextOverview, nextTypes] = await Promise.all([getOverview(), getAvailableTypes().catch(() => [])]); setOverview(nextOverview); setTypes(nextTypes); };
  useEffect(() => { void reload().then(() => setState("ready")).catch(() => setState("error")); }, []);
  async function selectExport(file: File | undefined) { if (!file) return; setImportState("previewing"); setImportMessage(null); try { setStagedImport(await previewImport(file)); setImportState("reviewing"); } catch (error) { setImportState("error"); setImportMessage(error instanceof Error ? error.message : "The selected export could not be inspected."); } }
  async function importExport() { if (!stagedImport) return; setImportState("importing"); setImportMessage(null); try { const result = await confirmImport(stagedImport.ticket_id); await reload(); setImportMessage(`${result.records_inserted.toLocaleString()} new observations imported locally.`); setStagedImport(null); setImportState("idle"); } catch (error) { setImportState("error"); setImportMessage(error instanceof Error ? error.message : "The export could not be imported safely."); } }
  return <div className="app-shell"><aside className="sidebar" aria-label="Primary navigation"><Link className="brand" to="/"><span className="brand-mark"><HeartPulse size={20} aria-hidden="true" /></span><span>Apple Health Analyzer</span></Link><nav>{navigation.map(({ to, label, icon: Icon, end }) => <NavLink className={({ isActive }) => isActive ? "nav-link active" : "nav-link"} to={to} end={end} key={to}><Icon size={16} aria-hidden="true" /> {label}</NavLink>)}<NavLink className={({ isActive }) => isActive ? "nav-link active" : "nav-link"} to="/rings">Rings</NavLink></nav><div className="sidebar-footer"><span className="local-status"><LockKeyhole size={14} aria-hidden="true" /> Local-only</span><a href="/api/docs">API documentation</a></div></aside><main className="content"><header className="topbar"><div><p className="eyebrow">Your health data, under your control</p><h1>Clear signals, honest context.</h1></div><button className="profile-button" type="button"><UserRound size={18} aria-hidden="true" /> Default profile</button></header>{state === "loading" && <section className="notice">Loading local profile...</section>}{state === "error" && <section className="notice error">The local API is unavailable. Start it with <code>apple-health serve</code> and refresh this page.</section>}{state === "ready" && overview && <><input ref={fileInputRef} className="visually-hidden" accept=".xml,.zip,application/xml,application/zip" type="file" onChange={(event) => void selectExport(event.target.files?.[0])} />{importState === "previewing" && <section className="notice">Inspecting your export locally...</section>}{importState === "importing" && <section className="notice">Importing your export locally. This can take a few minutes for large histories.</section>}{importState === "error" && importMessage && <section className="notice error">{importMessage}</section>}{importState === "reviewing" && stagedImport && <section className="import-review"><div><p className="eyebrow">Review local import</p><h2>Ready to import {stagedImport.file_name}</h2><p>{stagedImport.record_count.toLocaleString()} observations, {stagedImport.workout_count.toLocaleString()} workouts, and {stagedImport.record_type_count.toLocaleString()} record types were found. The file is staged only on this device.</p></div><div className="import-actions"><button className="secondary-action" type="button" onClick={() => { setStagedImport(null); setImportState("idle"); }}>Cancel</button><button className="primary-action" type="button" onClick={() => void importExport()}>Confirm local import <ArrowRight size={16} aria-hidden="true" /></button></div></section>}{importMessage && importState === "idle" && <section className="notice success">{importMessage}</section>}<Routes><Route path="/" element={<OverviewPage overview={overview} onImport={() => fileInputRef.current?.click()} />} /><Route path="/metrics/:category" element={<MetricPage types={types} />} /><Route path="/sleep" element={<SleepPage />} /><Route path="/workouts" element={<WorkoutsPage />} /><Route path="/rings" element={<RingsPage />} /><Route path="/explore" element={<ExplorerPage types={types} />} /><Route path="/settings" element={<SettingsPage overview={overview} />} /><Route path="*" element={<OverviewPage overview={overview} onImport={() => fileInputRef.current?.click()} />} /></Routes></>}</main></div>;
}
