export type MeetingStatus =
  | 'uploaded'
  | 'transcribing'
  | 'diarizing'
  | 'summarizing'
  | 'completed'
  | 'failed'

export interface Meeting {
  id: string
  title: string
  status: MeetingStatus | string
  original_filename: string
  duration_seconds: number | null
  created_at: string
  updated_at: string
  transcript_id: string | null
  summary_id: string | null
  error_message: string | null
}

export interface Speaker {
  id: string
  label: string
  display_name: string | null
}

export interface Utterance {
  id: string
  start: number
  end: number
  text: string
  speaker: Speaker | null
  confidence: number | null
}

export interface Transcript {
  id: string
  meeting_id: string
  language: string
  utterances: Utterance[]
  speakers: Speaker[]
}

export interface Decision {
  id: string
  description: string
  related_utterance_ids: string[]
}

export interface ActionItem {
  id: string
  description: string
  owner: string | null
  due_date: string | null
  status: string
  related_utterance_ids: string[]
}

export interface Summary {
  id: string
  meeting_id: string
  overview: string
  key_points: string[]
  decisions: Decision[]
  action_items: ActionItem[]
  generated_by_model: string
  generated_at: string
}

export interface KnowledgeHit {
  chunk_id: string
  meeting_id: string
  text: string
  score: number
  source_utterance_ids: string[]
}

export interface DependencyStatus {
  name: string
  available: boolean
  hint: string
}

export interface ModelStatus {
  key: string
  role: string
  model_id: string
  loaded: boolean
  ready: boolean
  downloading: boolean
  source: string
  progress_percent: number
  progress_message: string
  recent_logs: string[]
  status: string
  hint: string
}

export interface AsrOptionStatus {
  backend: string
  label: string
  model_id: string
  model_path: string
  ready: boolean
  source: string
  configured: boolean
  active: boolean
  download_command: string
  hint: string
}

export interface SystemStatus {
  platform: string
  all_ready: boolean
  configured_asr_backend: string
  active_asr_backend: string
  dependencies: DependencyStatus[]
  models: ModelStatus[]
  asr_options: AsrOptionStatus[]
}
