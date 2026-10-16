# LiD Quiz

Personal practice app for the German "Leben in Deutschland" test.
Vite + TypeScript, plain DOM, runs as a Home Screen web app on iPhone.

## Project layout

```
index.html                 page shell + iPhone Home Screen meta tags
public/                    copied as-is into the build (manifest, icons, images/)
src/main.ts                screens (HTML strings) + tap handling
src/quiz.ts                quiz logic: new run, answer, next, shuffle
src/storage.ts             save/load progress in localStorage
src/types.ts               Question and Run types
src/data/questions.json    the question catalog
```

## Run locally

```
npm install      # once
npm run dev
```

Open the URL Vite prints (e.g. http://localhost:5173/lid-quiz/).
To test on your iPhone, open the "Network" URL it prints (same Wi-Fi needed).

## Questions format

```json
{
  "id": "55",
  "question": "Was zeigt dieses Bild?",
  "options": ["…", "…", "…", "…"],
  "image": "055.jpg",
  "imageCredit": "© Deutscher Bundestag/Achim Melde",
  "correct": 0
}
```

- `correct`: index 0–3, or `null` = not filled in yet (the app skips these questions).
- `image` + `imageCredit`: optional picture above the answers.
- `optionImages`: optional, 4 file names when the answers themselves are pictures ("Bild 1–4").
- `state`: `"NRW"` for the state questions.

Images live in `public/images/`.

## Regenerating the questions

`src/data/questions.json` and `public/images/` are generated from the BAMF catalog PDF;
correct answers come from the LpB flashcards PDF (matched by text, since they're from 2017).

```
pip install pymupdf
python tools/convert_catalog.py gesamtfragenkatalog-lebenindeutschland.pdf Test_Lernkarten_Beilage_zum_Kursbuch.pdf
```

Check `tools/review.txt` afterwards. Answers the flashcards can't provide are in
`MANUAL_ANSWERS` at the top of the script; NRW answers go in `STATE_ANSWERS`.
**Re-running overwrites questions.json**, so answers typed directly into the JSON are lost on a re-run.

## Deploy to GitHub Pages

1. Create a GitHub repo named `lid-quiz` (if you pick another name, change `base` in `vite.config.ts`).
2. Push this folder to the `main` branch. Commit `package-lock.json` too, because the workflow needs it.
3. On GitHub: Settings → Pages → Source: **GitHub Actions**.
4. After the workflow finishes, open `https://<username>.github.io/lid-quiz/` in Safari → Share → **Add to Home Screen**.
