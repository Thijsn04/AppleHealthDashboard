import type { Grain } from "./ui";

export type HealthStatus = {
  status: string;
  version: string;
  network_mode: string;
};

export type Overview = {
  has_data: boolean;
  database_path: string;
  record_count: number;
  workout_count: number;
  ring_day_count: number;
  first_record_at: string | null;
  last_record_at: string | null;
  category_counts: Record<string, number>;
};

export type ImportPreview = {
  ticket_id: string;
  file_name: string;
  source_size_bytes: number;
  extracted_from_zip: boolean;
  record_count: number;
  workout_count: number;
  activity_summary_count: number;
  record_type_count: number;
  earliest_start: string | null;
  latest_end: string | null;
};

export type ImportResult = {
  entries_skipped: number;
  records_inserted: number;
  record_metadata_inserted: number;
  activity_summaries_inserted: number;
  workouts_inserted: number;
  workout_metadata_inserted: number;
};

export type AvailableType = {
  record_type: string;
  label: string;
  category: string;
  count: number;
  chartable: boolean;
  sources: (string | null)[];
  numeric_count: number;
  first_day: string;
  last_day: string;
  first_record_at: string | null;
  last_record_at: string | null;
  unit: string | null;
};

export type SeriesPoint = { date: string; value: number; unit: string | null; sample_count: number };
export type MetricSeries = {
  record_type: string; aggregation: string; grain: Grain; points: SeriesPoint[];
  excluded_samples: number; legacy_samples: number; sources: (string | null)[];
};
export type Filters = { start?: string; end?: string; grain?: Grain; source?: string };
export type SleepSummary = {
  average_hours: number | null;
  night_count: number;
  nightly: { date: string; hours: number }[];
  stages: { label: string; hours: number }[];
};
export type WorkoutSummary = {
  total_workouts: number;
  total_duration_hours: number | null;
  total_distance_km: number | null;
  total_energy_kcal: number | null;
  weekly: { date: string; count: number; duration_hours: number | null }[];
  by_type: { label: string; count: number; duration_hours: number | null }[];
  sessions: { start: string; label: string; source: string | null; hours: number | null; km: number | null; kcal: number | null; bpm: number | null }[];
};
export type RingDay = {
  date: string;
  active_energy_kcal: number | null;
  active_energy_goal_kcal: number | null;
  exercise_minutes: number | null;
  exercise_goal_minutes: number | null;
  stand_hours: number | null;
  stand_goal_hours: number | null;
};
export type RecordPage = {
  total: number;
  offset: number;
  limit: number;
  items: { record_type: string; start_at: string; end_at: string; source_name: string | null; unit: string | null; value: number | null; value_str: string | null; device: string | null; source_version: string | null; legacy_timestamp: boolean }[];
};

async function request<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null;
    throw new Error(body?.detail ?? "The local analyzer service could not complete this request.");
  }
  return response.json() as Promise<T>;
}

export const getHealth = () => request<HealthStatus>("/api/v1/health");
export const getOverview = () => request<Overview>("/api/v1/overview");
export const getAvailableTypes = () => request<AvailableType[]>("/api/v1/analytics/types");
function query(filters: Filters) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined) params.set(key, value);
  }
  return params;
}

export const getMetricSeries = (recordType: string, filters: Filters = {}) =>
  request<MetricSeries>(`/api/v1/analytics/metrics/${encodeURIComponent(recordType)}/series?${query(filters)}`);
export const getSleepSummary = () => request<SleepSummary>("/api/v1/analytics/sleep");
export const getWorkoutSummary = () => request<WorkoutSummary>("/api/v1/analytics/workouts");
export const getRings = () => request<RingDay[]>("/api/v1/analytics/rings");
export const getRecords = (recordType: string | undefined, offset = 0, filters: Filters = {}) => {
  const search = query(filters);
  search.set("offset", String(offset));
  search.set("limit", "50");
  if (recordType) search.set("record_type", recordType);
  return request<RecordPage>(`/api/v1/analytics/records?${search}`);
};

export async function discardImport(ticketId: string) {
  const response = await fetch(`/api/v1/imports/${encodeURIComponent(ticketId)}`, { method: "DELETE" });
  if (!response.ok) throw new Error("The preview could not be discarded. It expires automatically.");
}

export async function previewImport(file: File): Promise<ImportPreview> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch("/api/v1/imports/preview", { method: "POST", body: formData });
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null;
    throw new Error(body?.detail ?? "The selected export could not be inspected.");
  }
  return response.json() as Promise<ImportPreview>;
}

export async function confirmImport(ticketId: string): Promise<ImportResult> {
  const response = await fetch("/api/v1/imports", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticket_id: ticketId })
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null;
    throw new Error(body?.detail ?? "The export could not be imported safely.");
  }
  return response.json() as Promise<ImportResult>;
}
