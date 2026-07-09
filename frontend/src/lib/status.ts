export const STATUS_LABELS: Record<string, string> = {
  uploaded: '排队等待处理',
  transcribing: '转写中',
  diarizing: '说话人识别中',
  summarizing: '生成摘要中',
  completed: '已完成',
  failed: '处理失败',
}

export const STAGE_STEPS = [
  'uploaded',
  'transcribing',
  'diarizing',
  'summarizing',
  'completed',
] as const

export const STAGE_LABELS: Record<string, string> = {
  uploaded: '排队等待处理',
  transcribing: '正在转写语音（VibeVoice）',
  diarizing: '正在识别说话人（VibeVoice）',
  summarizing: '正在生成摘要',
  completed: '处理完成',
  failed: '处理失败',
}

export const STAGE_HINTS: Record<string, string> = {
  uploaded: '后台任务即将启动，请稍候…',
  transcribing: '正在用 VibeVoice 转写语音并标注说话人，长音频可能需要较长时间。',
  diarizing: 'VibeVoice 已在转写阶段标注说话人，正在推进处理状态。',
  summarizing: '正在通过 LLM API 生成会议摘要。',
}

export function isTerminalStatus(status: string): boolean {
  return status === 'completed' || status === 'failed'
}
