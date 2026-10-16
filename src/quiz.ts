import type { Mode, Question, Run } from './types';

/** Start a new run over the given questions. */
export function createRun(questions: Question[], mode: Mode): Run {
  const ids = questions.map((q) => q.id);
  return {
    mode,
    order: mode === 'shuffle' ? shuffle(ids) : ids,
    position: 0,
    selected: null,
    correctCount: 0,
    wrongCount: 0,
  };
}

export function currentQuestionId(run: Run): string {
  return run.order[run.position];
}

/** Record the user's answer for the current question. Ignored if already answered. */
export function answerCurrent(run: Run, choice: number, correctIndex: number): void {
  if (run.selected !== null) return;
  run.selected = choice;
  if (choice === correctIndex) {
    run.correctCount++;
  } else {
    run.wrongCount++;
  }
}

/** Move on to the next question (only after the current one was answered). */
export function goToNext(run: Run): void {
  if (run.selected === null) return;
  run.position++;
  run.selected = null;
}

export function isFinished(run: Run): boolean {
  return run.position >= run.order.length;
}

/** How many questions have been answered in this run. */
export function doneCount(run: Run): number {
  return run.correctCount + run.wrongCount;
}

/** Fisher–Yates shuffle: returns a new array in random order, every order equally likely. */
function shuffle<T>(items: T[]): T[] {
  const result = [...items];
  for (let i = result.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [result[i], result[j]] = [result[j], result[i]];
  }
  return result;
}
