import type { Run } from './types';

// Bump the version suffix if the shape of `Run` ever changes,
// so old saved data is ignored instead of breaking the app.
const STORAGE_KEY = 'lid-quiz.run.v1';

/**
 * Load the saved run, or null if there is none.
 * The saved run is thrown away if it refers to question ids that no longer exist
 * (for example after the questions file changed).
 */
export function loadRun(knownIds: Set<string>): Run | null {
  try {
    const text = localStorage.getItem(STORAGE_KEY);
    if (!text) return null;

    const run = JSON.parse(text) as Run;
    if (!Array.isArray(run.order) || typeof run.position !== 'number') return null;
    if (!run.order.every((id) => knownIds.has(id))) return null;

    return run;
  } catch {
    // Broken JSON or storage not available: just start fresh.
    return null;
  }
}

export function saveRun(run: Run): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(run));
  } catch {
    // Storage full or blocked: the app still works, progress just isn't saved.
  }
}

export function clearRun(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Nothing to do.
  }
}
