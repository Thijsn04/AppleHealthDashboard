import { useEffect, useRef, useState } from "react";
import {
  Activity, ArrowRight, BarChart3, CircleHelp, Dumbbell, Footprints, HeartPulse,
  LayoutDashboard, LockKeyhole, Moon, Scale, Sun, Upload, Watch,
} from "lucide-react";
import { Link, NavLink, Route, Routes, useLocation, useParams } from "react-router-dom";

import {
  confirmImport, discardImport, getAvailableTypes, getMetricSeries, getOverview, getRings,
  getSleepSummary, getWorkoutSummary, previewImport, type AvailableType, type ImportPreview, type Overview,
} from "./api";
import demoUrl from "./demo.xml?url";
import { Explorer } from "./Explorer";
import { DataTable, formatDate, formatNumber, LineChart, RequestStatus, useRequest } from "./ui";

const nav = [
  { to: "/", label: "Overview", icon: LayoutDashboard },
  { to: "/metrics/activity", label: "Activity", icon: Footprints },
  { to: "/metrics/heart", label: "Heart", icon: HeartPulse },
  { to: "/sleep", label: "Sleep", icon: Moon },
  { to: "/workouts", label: "Workouts", icon: Dumbbell },
  { to: "/metrics/body", label: "Body", icon: Scale },
  { to: "/rings", label: "Activity rings", icon: Watch },
  { to: "/explore", label: "Data Explorer", icon: BarChart3 },
  { to: "/settings", label: "Privacy", icon: LockKeyhole },
];

const categories: Record<string, string> = {
  activity: "Activity", heart: "Heart", body: "Body", nutrition: "Nutrition", mobility: "Mobility",
  respiratory: "Respiratory", symptoms: "Symptoms", environment: "Environment", mind: "Mind", other: "Other",
};

function PageHeading({ title, description, children }: { title: string; description: string; children?: React.ReactNode }) {
  return <header className="page-heading">
    <div><h1>{title}</h1><p>{description}</p></div>{children}
  </header>;
}

function Stat({ label, value, note, icon: Icon }: {
  label: string; value: string; note?: string; icon?: typeof Activity;
}) {
  return <article className="panel stat-card">
    <div className="stat-label">{Icon && <span className="stat-icon"><Icon size={17} aria-hidden="true" /></span>}{label}</div>
    <strong>{value}</strong>
    {note && <span>{note}</span>}
  </article>;
}

function OverviewPage({ overview, types, revision, onImport, onDemo, busy }: {
  overview: Overview; types: AvailableType[]; revision: number; onImport: () => void; onDemo: () => void; busy: boolean;
}) {
  const [selected, setSelected] = useState("");
  const chartable = types.filter((type) => type.chartable);
  const trend = chartable.find((type) => type.record_type === selected)
    ?? chartable.find((type) => type.record_type === "HKQuantityTypeIdentifierStepCount") ?? chartable[0];
  const end = trend?.last_day;
  const start = end && new Date(Date.parse(end) - 29 * 86_400_000).toISOString().slice(0, 10);
  const series = useRequest(trend ? () => getMetricSeries(trend.record_type, { start, end }) : null, `${revision}-${trend?.record_type}`);
  const sources = new Set(types.flatMap((type) => type.sources).filter(Boolean)).size;
  const starts = types.map((type) => type.first_day).sort();
  const ends = types.map((type) => type.last_day).sort();
  return <div className="workspace">
    <PageHeading title="Health overview" description={overview.has_data ? "Explore patterns across your Apple Health history." : "A private workspace for your Apple Health history."}>
      <span className="status-chip"><LockKeyhole size={14} aria-hidden="true" /> On this device</span>
    </PageHeading>
    {!overview.has_data ? <section className="welcome panel">
      <span className="welcome-icon"><Activity size={32} aria-hidden="true" /></span>
      <h2>Start with an Apple Health export</h2>
      <p>Choose the ZIP or XML from Apple Health. Review its contents before adding observations, workouts, and activity rings to your local profile.</p>
      <div className="actions"><button className="button primary" disabled={busy} onClick={onImport}><Upload size={17} aria-hidden="true" /> Import export</button>
        <button className="button subtle" disabled={busy} onClick={onDemo}>Try synthetic demo <ArrowRight size={16} aria-hidden="true" /></button></div>
    </section> : <>
      <section className="stats" aria-label="Profile totals">
        <Stat label="Observations" value={formatNumber(overview.record_count, 0)} note={`${types.length} exported types`} icon={Activity} />
        <Stat label="Workouts" value={formatNumber(overview.workout_count, 0)} note="Imported session records" icon={Dumbbell} />
        <Stat label="Activity rings" value={formatNumber(overview.ring_day_count, 0)} note="Days with summaries" icon={Watch} />
        <Stat label="Record sources" value={formatNumber(sources, 0)} note="Named export sources" icon={BarChart3} />
      </section>
      <div className="overview-grid">
        <section className="panel overview-trend">
          <header className="panel-heading"><div><h2>Recent trend</h2><p>30 days through {end ? formatDate(end) : "the latest observation"}</p></div>
            {trend && <label className="inline-field"><span className="sr-only">Overview metric</span><select value={trend.record_type} onChange={(e) => setSelected(e.target.value)}>
              {chartable.map((type) => <option key={type.record_type} value={type.record_type}>{type.label}</option>)}</select></label>}
          </header>
          <RequestStatus {...series} />
          {series.data && trend && <LineChart key={trend.record_type} points={series.data.points} label={trend.label} unit={series.data.points[0]?.unit ?? ""} />}
          {!trend && <p className="empty-panel">There are no compatible numeric metrics in this export.</p>}
          <Link className="text-link" to="/explore">Open Data Explorer <ArrowRight size={16} aria-hidden="true" /></Link>
        </section>
        <section className="panel coverage-panel">
          <header className="panel-heading"><div><h2>Data coverage</h2><p>{types.length ? `${formatDate(starts[0])} to ${formatDate(ends.at(-1)!)}` : "Observation dates unavailable"}</p></div></header>
          <ul className="coverage-list">
            {Object.entries(overview.category_counts).sort((a, b) => b[1] - a[1]).slice(0, 7).map(([name, count]) => {
              const slug = Object.keys(categories).find((key) => categories[key] === name);
              return <li key={name}><div><Link to={slug ? `/metrics/${slug}` : "/explore"}>{name}</Link><span>{formatNumber(count, 0)}</span></div>
                <progress value={count} max={overview.record_count} aria-label={`${name} share of observations`} /></li>;
            })}
          </ul>
          {!overview.record_count && <p className="muted">This export contains summaries without individual observations.</p>}
        </section>
      </div>
    </>}
  </div>;
}

function MetricPage({ types, revision }: { types: AvailableType[]; revision: number }) {
  const { category = "activity" } = useParams();
  const name = categories[category] ?? "Other";
  return <div className="workspace"><PageHeading title={name} description="Explore exported measurements by source and calendar period." />
    <Explorer key={category} types={types} revision={revision} category={name} /></div>;
}

function SleepPage({ revision }: { revision: number }) {
  const result = useRequest(getSleepSummary, `sleep-${revision}`);
  const data = result.data;
  return <div className="workspace"><PageHeading title="Sleep" description="Recorded time asleep, grouped by the day each continuous episode ended." />
    <RequestStatus {...result} />
    {data && <>
      <section className="stats compact"><Stat label="Average on observed days" value={data.average_hours === null ? "Unavailable" : `${formatNumber(data.average_hours)} h`} icon={Moon} /><Stat label="Observed days" value={String(data.night_count)} /></section>
      <section className="panel"><header className="panel-heading"><div><h2>Time asleep</h2><p>90 days through the latest recorded sleep</p></div></header>
        <LineChart points={data.nightly.map((p) => ({ date: p.date, value: p.hours }))} label="Daily time asleep" unit="h" />
        <details className="method"><summary>How sleep is counted</summary><p>Overlapping asleep intervals count once. Only segments with one reported specific stage contribute to stage totals. Unspecified or conflicting stages can leave the stage totals below overall sleep duration.</p></details>
      </section>
      <section className="panel"><h2>Recorded stages</h2><DataTable headings={["Stage", "Hours"]} rows={data.stages.map((p) => [p.label, formatNumber(p.hours)])} /></section>
    </>}
  </div>;
}

function WorkoutsPage({ revision }: { revision: number }) {
  const result = useRequest(getWorkoutSummary, `workouts-${revision}`);
  const data = result.data;
  const quantity = (value: number | null, unit: string) => value === null ? "Unavailable" : `${formatNumber(value)} ${unit}`;
  return <div className="workspace"><PageHeading title="Workouts" description="Reported session totals for the year through your latest workout." />
    <RequestStatus {...result} />
    {data && <>
      <section className="stats"><Stat label="Sessions" value={formatNumber(data.total_workouts, 0)} icon={Dumbbell} /><Stat label="Duration" value={quantity(data.total_duration_hours, "h")} /><Stat label="Distance" value={quantity(data.total_distance_km, "km")} /><Stat label="Energy" value={quantity(data.total_energy_kcal, "kcal")} /></section>
      <section className="panel"><header className="panel-heading"><div><h2>Weekly duration</h2><p>Reported values with compatible units</p></div></header>
        <LineChart points={data.weekly.map((p) => ({ date: p.date, value: p.duration_hours }))} label="Weekly reported workout duration" unit="h" grain="week" /></section>
      <section className="panel"><h2>Workout types</h2><DataTable headings={["Workout type", "Sessions", "Hours"]} rows={data.by_type.map((p) => [p.label, String(p.count), formatNumber(p.duration_hours)])} /></section>
      <section className="panel"><h2>Recent sessions</h2><DataTable headings={["Date", "Type", "Source", "Duration", "Distance", "Energy", "Average HR"]} rows={data.sessions.map((session) => [
        formatDate(session.start), session.label, session.source ?? "Unknown source", quantity(session.hours, "h"),
        quantity(session.km, "km"), quantity(session.kcal, "kcal"), quantity(session.bpm, "bpm"),
      ])} /></section>
    </>}
  </div>;
}

function RingsPage({ revision }: { revision: number }) {
  const result = useRequest(getRings, `rings-${revision}`);
  return <div className="workspace"><PageHeading title="Activity rings" description="Apple Activity summaries for the 90 days through your latest ring day." />
    <RequestStatus {...result} />
    {result.data && <section className="panel"><header className="panel-heading"><div><h2>Move energy</h2><p>Recorded summaries</p></div></header>
      <LineChart points={result.data.map((p) => ({ date: p.date, value: p.active_energy_kcal }))} label="Move energy" unit="kcal" />
      <DataTable headings={["Date", "Move (kcal)", "Exercise (min)", "Stand (h)"]} rows={result.data.slice().reverse().map((p) => [
        formatDate(p.date), `${formatNumber(p.active_energy_kcal)} / ${formatNumber(p.active_energy_goal_kcal)}`,
        `${formatNumber(p.exercise_minutes)} / ${formatNumber(p.exercise_goal_minutes)}`,
        `${formatNumber(p.stand_hours)} / ${formatNumber(p.stand_goal_hours)}`,
      ])} />
    </section>}
  </div>;
}

function SettingsPage({ overview }: { overview: Overview }) {
  return <div className="workspace"><PageHeading title="Privacy" description="Manage the files that power your local analysis." />
    <section className="panel privacy-panel"><h2>Profile storage</h2><p>Imported observations and source metadata stay in a DuckDB file on this computer.</p>
      <code>{overview.database_path}</code>
      <h2>Remove local data</h2><p>Stop the app, then run <code>python -m apple_health_dashboard.cli clear --yes</code> from the directory where you started it. This removes the database, write-ahead log and staged previews. Keep a separate copy of any export you want to retain.</p>
      <h2>Temporary exports</h2><p>Previews expire after 30 minutes. Cancelling a preview removes its staged copy. An unexpected shutdown can leave staging files on disk until you clear them.</p>
    </section>
  </div>;
}

type ImportState = { status: "idle" | "previewing" | "importing"; message?: string }
  | { status: "reviewing"; preview: ImportPreview } | { status: "error"; message: string };

export function App() {
  const [revision, setRevision] = useState(0);
  const [stage, setStage] = useState<ImportState>({ status: "idle" });
  const [theme, setTheme] = useState(() => localStorage.getItem("health-theme") ?? "system");
  const input = useRef<HTMLInputElement>(null);
  const location = useLocation();
  const [menu, setMenu] = useState(false);

  useEffect(() => { document.documentElement.dataset.theme = theme; localStorage.setItem("health-theme", theme); }, [theme]);
  useEffect(() => { setMenu(false); }, [location.pathname]);
  const profile = useRequest(async () => {
    const overview = await getOverview();
    return { overview, types: overview.has_data && overview.record_count ? await getAvailableTypes() : [] };
  }, String(revision));
  const busy = stage.status === "previewing" || stage.status === "importing" || stage.status === "reviewing";
  const select = async (file: File) => {
    setStage({ status: "previewing" });
    try { setStage({ status: "reviewing", preview: await previewImport(file) }); }
    catch (error) { setStage({ status: "error", message: (error as Error).message }); }
  };
  const demo = async () => {
    setStage({ status: "previewing" });
    try {
      const response = await fetch(demoUrl);
      if (!response.ok) throw new Error("The synthetic demo could not be opened.");
      await select(new File([await response.blob()], "synthetic-demo.xml", { type: "application/xml" }));
    } catch (error) { setStage({ status: "error", message: (error as Error).message }); }
  };
  const confirm = async (ticket: string) => {
    setStage({ status: "importing" });
    try {
      const result = await confirmImport(ticket);
      setRevision((value) => value + 1);
      const message = `${formatNumber(result.records_inserted, 0)} observations, ${result.workouts_inserted} workouts and ${result.activity_summaries_inserted} ring days added.`;
      setStage({ status: "idle", message: result.entries_skipped ? `${message} ${result.entries_skipped} incomplete entries skipped.` : message });
    } catch (error) { setStage({ status: "error", message: (error as Error).message }); }
  };
  const cancel = async (ticket: string) => {
    setStage({ status: "idle" });
    try { await discardImport(ticket); }
    catch (error) { setStage({ status: "error", message: (error as Error).message }); }
  };
  const openImport = () => input.current?.click();

  return <div className="shell">
    <a className="skip-link" href="#workspace">Skip to content</a>
    <aside className="sidebar">
      <div className="sidebar-top"><Link to="/" className="brand"><span><Activity size={21} aria-hidden="true" /></span><div>Health Analyzer<small>APPLE HEALTH WORKSPACE</small></div></Link>
        <button className="button subtle mobile-nav" aria-expanded={menu} aria-controls="workspace-nav" onClick={() => setMenu(!menu)}>Menu</button></div>
      <nav id="workspace-nav" className={menu ? "nav is-open" : "nav"} aria-label="Workspace">
        {nav.map(({ to, label, icon: Icon }) => <NavLink key={to} to={to} end={to === "/"}><Icon size={18} aria-hidden="true" />{label}</NavLink>)}
      </nav>
      <div className="sidebar-bottom"><LockKeyhole size={15} aria-hidden="true" /> Local storage</div>
    </aside>
    <div className="main-shell">
      <header className="toolbar">
        <span>Workspace</span>
        <div className="actions">
          <label className="theme-picker">{theme === "dark" ? <Moon size={16} aria-hidden="true" /> : <Sun size={16} aria-hidden="true" />}<span className="sr-only">Theme</span>
            <select value={theme} onChange={(e) => setTheme(e.target.value)}><option value="system">System</option><option value="light">Light</option><option value="dark">Dark</option></select></label>
          <button type="button" className="button primary" onClick={openImport} disabled={busy}><Upload size={16} aria-hidden="true" /> Import export</button>
        </div>
      </header>
      <main id="workspace" className="main" tabIndex={-1}>
        <input ref={input} type="file" className="sr-only" tabIndex={-1} aria-label="Select Apple Health export" accept=".xml,.zip,application/xml,application/zip" onChange={(event) => {
          const file = event.target.files?.[0];
          event.target.value = "";
          if (file) void select(file);
        }} />
        {stage.status === "previewing" && <p role="status" className="notice">Inspecting your export…</p>}
        {stage.status === "importing" && <p role="status" className="notice">Importing locally. Large exports may take several minutes.</p>}
        {stage.status === "error" && <p role="alert" className="notice error">{stage.message}</p>}
        {stage.status === "idle" && stage.message && <p role="status" className="notice">{stage.message}</p>}
        {stage.status === "reviewing" && <section className="panel import-review" aria-labelledby="review-heading">
          <div><h2 id="review-heading">Review import</h2><p>{stage.preview.file_name}</p><p>{formatNumber(stage.preview.record_count, 0)} observations · {stage.preview.workout_count} workouts · {stage.preview.activity_summary_count} ring days</p></div>
          <div className="actions"><button className="button subtle" onClick={() => void cancel(stage.preview.ticket_id)}>Cancel</button><button className="button primary" onClick={() => void confirm(stage.preview.ticket_id)}>Confirm import <ArrowRight size={16} aria-hidden="true" /></button></div>
        </section>}
        <RequestStatus {...profile} />
        {profile.error && <button className="button subtle" onClick={() => setRevision((value) => value + 1)}>Retry local connection</button>}
        {profile.data && <Routes>
          <Route index element={<OverviewPage {...profile.data} revision={revision} onImport={openImport} onDemo={() => void demo()} busy={busy} />} />
          <Route path="metrics/:category" element={<MetricPage types={profile.data.types} revision={revision} />} />
          <Route path="sleep" element={profile.data.overview.has_data ? <SleepPage revision={revision} /> : <EmptyPage title="Sleep" />} />
          <Route path="workouts" element={profile.data.overview.has_data ? <WorkoutsPage revision={revision} /> : <EmptyPage title="Workouts" />} />
          <Route path="rings" element={profile.data.overview.has_data ? <RingsPage revision={revision} /> : <EmptyPage title="Activity rings" />} />
          <Route path="explore" element={<div className="workspace"><PageHeading title="Data Explorer" description="Compare trends, inspect source observations, and export your selected series." />
            <Explorer types={profile.data.types} revision={revision} /></div>} />
          <Route path="settings" element={<SettingsPage overview={profile.data.overview} />} />
          <Route path="*" element={<EmptyPage title="Page unavailable" />} />
        </Routes>}
      </main>
    </div>
  </div>;
}

function EmptyPage({ title }: { title: string }) {
  return <div className="workspace"><PageHeading title={title} description="Open the overview to import or inspect your profile." />
    <Link className="text-link" to="/"><CircleHelp size={17} aria-hidden="true" /> Open overview</Link></div>;
}
