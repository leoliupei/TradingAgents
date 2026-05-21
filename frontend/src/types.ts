export type RunStatus = "pending" | "running" | "completed" | "failed" | "canceled";

export interface RunSpec {
  ticker: string;
  analysis_date: string;
  analysts: string[];
  research_depth: number;
  llm_provider: string;
  quick_think_llm: string;
  deep_think_llm: string;
  output_language: string;
  asset_type: string;
  backend_url?: string | null;
  checkpoint_enabled: boolean;
  google_thinking_level?: string | null;
  openai_reasoning_effort?: string | null;
  anthropic_effort?: string | null;
}

export interface ReportMeta {
  section: string;
  size: number;
  updated_at: string;
  content?: string;
}

export interface RunInfo {
  id: string;
  status: RunStatus;
  ticker: string;
  analysis_date: string;
  asset_type: string;
  analysts: string[];
  llm_provider: string;
  quick_model: string;
  deep_model: string;
  research_depth: number;
  output_language: string;
  run_dir: string;
  pid?: number | null;
  error?: string | null;
  decision?: string | null;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  reports: Record<string, ReportMeta>;
  events?: RunEvent[];
  event_next?: number;
}

export interface RunEvent {
  _index?: number;
  run_id: string;
  type: string;
  timestamp: string;
  role?: string;
  content?: string;
  section?: string;
  size?: number;
  name?: string;
  args?: Record<string, unknown>;
  message?: string;
  traceback?: string;
  decision?: string;
  [key: string]: unknown;
}

export interface OptionItem {
  value: string;
  label: string;
}

export interface OptionsPayload {
  analysts: OptionItem[];
  providers: OptionItem[];
  report_sections: string[];
  defaults: {
    research_depth: number;
    llm_provider: string;
    quick_think_llm: string;
    deep_think_llm: string;
    output_language: string;
    analysis_date: string | null;
  };
}
