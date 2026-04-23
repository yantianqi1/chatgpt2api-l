export type ComicTaskStatus =
  | "queued"
  | "running"
  | "completed"
  | "completed_with_errors"
  | "failed";

export type ComicProjectSummary = {
  id: string;
  title: string;
  source_text: string;
  style_prompt: string;
  created_at: string;
  updated_at: string;
};

export type ComicCharacterProfile = {
  id: string;
  project_id: string;
  name: string;
  description: string;
  appearance: string;
  personality: string;
};

export type ComicChapter = {
  id: string;
  project_id: string;
  title: string;
  source_text: string;
  summary: string;
  order: number;
};

export type ComicAsset = {
  id: string;
  scene_id: string;
  relative_path: string;
  prompt: string;
  created_at: string;
};

export type ComicScene = {
  id: string;
  project_id: string;
  chapter_id: string;
  title: string;
  description: string;
  prompt: string;
  character_ids: string[];
  order: number;
  assets: ComicAsset[];
};

export type ComicTask = {
  id: string;
  project_id: string;
  kind: string;
  status: ComicTaskStatus;
  target_id: string;
  input_payload: Record<string, unknown>;
  result_payload: Record<string, unknown> | null;
  error: string | null;
  created_at: string;
  updated_at: string;
  progress: number;
};

export type ComicProjectSnapshot = {
  project: ComicProjectSummary;
  characters: ComicCharacterProfile[];
  chapters: ComicChapter[];
  scenes: ComicScene[];
  tasks: ComicTask[];
};

export type ComicTaskTriggerResponse = {
  task_id: string;
  status: ComicTaskStatus;
};

export type ComicProjectCreateInput = {
  title: string;
  source_text: string;
  style_prompt: string;
};

export type ComicProjectUpdateInput = Partial<ComicProjectCreateInput>;

export type ComicImportInput = {
  source_text: string;
  import_mode?: string;
};

export type ComicCharactersSaveInput = {
  characters: Array<{
    id: string;
    name: string;
    description?: string;
    appearance?: string;
    personality?: string;
  }>;
};

export type ComicChapterSaveInput = {
  title: string;
  source_text: string;
  summary: string;
  order: number;
};

export type ComicSceneSaveInput = {
  chapter_id: string;
  title: string;
  description: string;
  prompt: string;
  character_ids: string[];
  order: number;
  assets: ComicAsset[];
};
