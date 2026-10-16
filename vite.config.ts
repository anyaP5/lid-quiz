import { defineConfig } from 'vite';

export default defineConfig({
  // Must match the GitHub repo name: the site is served at
  // https://<username>.github.io/<repo-name>/
  // Change this if you name the repo something other than "lid-quiz".
  base: '/lid-quiz/',

  server: {
    // Makes the dev server reachable from other devices on your Wi-Fi,
    // so you can test on your iPhone while developing.
    host: true,
  },
});
