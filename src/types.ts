/** One question from the catalog (see src/data/questions.json). */
export interface Question {
  id: string;
  question: string;
  /** Always 4 answer options. */
  options: string[];
  /** Index (0–3) of the correct option, or null if not filled in yet (such questions are skipped). */
  correct: number | null;
  /** Bundesland, only for state-specific questions. */
  state?: string;
  /** File name in public/images/, for questions with a picture above the answers. */
  image?: string;
  /** Photo credit shown under the image. */
  imageCredit?: string;
  /** 4 file names in public/images/, for questions whose answers are pictures ("Bild 1–4"). */
  optionImages?: string[];
}

export type Mode = 'shuffle' | 'sequential';

/** Everything we need to remember about the current run. Saved to localStorage. */
export interface Run {
  mode: Mode;
  /** Question ids in the order they will be asked. Each id appears exactly once. */
  order: string[];
  /** Index into `order` of the question currently on screen. */
  position: number;
  /** Option the user picked for the current question, or null if not answered yet. */
  selected: number | null;
  correctCount: number;
  wrongCount: number;
}
