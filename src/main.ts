import './style.css';
import allQuestions from './data/questions.json';
import type { Mode, Question, Run } from './types';
import { answerCurrent, createRun, currentQuestionId, doneCount, goToNext, isFinished } from './quiz';
import { clearRun, loadRun, saveRun } from './storage';

// Questions without a correct answer yet (correct: null) can't be graded, so they're left out.
// The `q is GradableQuestion` part tells TypeScript that after this filter, `correct` is always a number.
type GradableQuestion = Question & { correct: number };
const questions = (allQuestions as Question[]).filter((q): q is GradableQuestion => q.correct !== null);
const questionsById = new Map(questions.map((q) => [q.id, q]));

const app = document.querySelector<HTMLDivElement>('#app')!;
let run: Run | null = loadRun(new Set(questionsById.keys()));

const LETTERS = ['A', 'B', 'C', 'D'];

// ---------- Rendering ----------
// Each screen is a function that returns an HTML string.
// After every change we re-render the whole screen. That's simple and fast enough here.

function render(): void {
  if (!run) {
    app.innerHTML = startScreen();
  } else if (isFinished(run)) {
    app.innerHTML = finishedScreen(run);
  } else {
    app.innerHTML = questionScreen(run);
  }
}

function startScreen(): string {
  return `
    <main class="screen center">
      <h1>LiD Quiz</h1>
      <p class="muted">${questions.length} questions. Each one is asked once per run.</p>
      ${modeButtons()}
    </main>
  `;
}

function finishedScreen(run: Run): string {
  const total = run.order.length;
  const percent = total > 0 ? Math.round((run.correctCount / total) * 100) : 0;
  return `
    <main class="screen center">
      <h1>Run complete 🎉</h1>
      <p class="big-score">${percent}%</p>
      <p>
        <span class="ok">✓ ${run.correctCount} correct</span> ·
        <span class="bad">✗ ${run.wrongCount} wrong</span>
      </p>
      <p class="muted">Start a new run:</p>
      ${modeButtons()}
    </main>
  `;
}

function modeButtons(): string {
  return `
    <div class="stack">
      <button class="primary" data-action="start" data-mode="shuffle">🔀 Shuffle</button>
      <button class="secondary" data-action="start" data-mode="sequential">🔢 In order</button>
    </div>
  `;
}

function questionScreen(run: Run): string {
  const question = questionsById.get(currentQuestionId(run))!;
  const total = run.order.length;
  const done = doneCount(run);
  const answered = run.selected !== null;

  const options = question.options
    .map((text, i) => {
      let className = 'option';
      if (answered && i === question.correct) className += ' is-correct';
      else if (answered && i === run.selected) className += ' is-wrong';

      // Picture answers ("Bild 1–4") show the picture with the letter; text answers show the text.
      const content = question.optionImages
        ? `<img src="${imageUrl(question.optionImages[i])}" alt="${escapeHtml(text)}" />`
        : `<span>${escapeHtml(text)}</span>`;

      return `
        <button class="${className}" data-action="answer" data-index="${i}" ${answered ? 'disabled' : ''}>
          <span class="letter">${LETTERS[i]}</span>
          ${content}
        </button>
      `;
    })
    .join('');

  let feedback = '';
  if (answered) {
    feedback =
      run.selected === question.correct
        ? `<p class="feedback ok">✓ Richtig!</p>`
        : `<p class="feedback bad">✗ Falsch. Richtig ist ${LETTERS[question.correct]}.</p>`;
  }

  const credit = question.imageCredit ? `<p class="credit">${escapeHtml(question.imageCredit)}</p>` : '';
  const image = question.image
    ? `<img class="question-image" src="${imageUrl(question.image)}" alt="" />${credit}`
    : '';

  return `
    <header class="topbar">
      <div>
        <div><strong>${done} / ${total}</strong> done, ${total - done} left</div>
        <div class="small"><span class="ok">✓ ${run.correctCount}</span> · <span class="bad">✗ ${run.wrongCount}</span></div>
      </div>
      <button class="link" data-action="reset">New run</button>
    </header>
    <div class="progress"><div class="progress-fill" style="width: ${(done / total) * 100}%"></div></div>

    <main class="screen">
      <p class="muted small">Frage ${escapeHtml(question.id)}</p>
      <h2 class="question">${escapeHtml(question.question)}</h2>
      ${image}
      <div class="${question.optionImages ? 'picture-grid' : 'stack'}">${options}</div>
      ${feedback}
    </main>

    ${answered ? `<footer class="bottombar"><button class="primary" data-action="next">Next →</button></footer>` : ''}
  `;
}

/** Images live in public/images/. BASE_URL is "/lid-quiz/" (from vite.config.ts), so this works on GitHub Pages. */
function imageUrl(fileName: string): string {
  return `${import.meta.env.BASE_URL}images/${escapeHtml(fileName)}`;
}

/** Make text safe to put inside HTML (so a "<" in a question can't break the page). */
function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ---------- Handling taps ----------
// One click listener on the whole app ("event delegation"). Each button says what it does
// via its data-action attribute, so we don't need to re-attach listeners after re-rendering.

app.addEventListener('click', (event) => {
  const button = (event.target as HTMLElement).closest<HTMLButtonElement>('button[data-action]');
  if (!button) return;

  switch (button.dataset.action) {
    case 'start':
      run = createRun(questions, button.dataset.mode as Mode);
      break;

    case 'answer':
      if (run) {
        const question = questionsById.get(currentQuestionId(run))!;
        answerCurrent(run, Number(button.dataset.index), question.correct);
      }
      break;

    case 'next':
      if (run) goToNext(run);
      window.scrollTo(0, 0);
      break;

    case 'reset':
      if (!confirm('Start a new run? Your current progress will be lost.')) return;
      run = null;
      break;
  }

  if (run) saveRun(run);
  else clearRun();
  render();
});

render();
