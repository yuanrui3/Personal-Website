# 阴燃 · The Slow Fire — reading site

A static site with no build step: `index.html` loads `toc.json` and the chapter fragments in `txt/` with `fetch`, and the figures from `img/`.

## Publish on GitHub Pages

1. Create a public repository (for example `slowfire`) and put the contents of this folder at its root, including the hidden `.nojekyll` file.
2. Commit and push to `main`.
3. In the repository: **Settings → Pages → Build and deployment → Source: Deploy from a branch**, branch `main`, folder `/ (root)`. Save.
4. The site appears at `https://<username>.github.io/<repository>/` within a minute or two.

Notes for whoever publishes this:
- Do not rename or move `txt/`, `img/` or `toc.json`; the page fetches them by relative path.
- Opening `index.html` straight from disk (file://) will not load chapters, because browsers block `fetch` there. Test with a local server instead: `python3 -m http.server` in this folder, then open http://localhost:8000.
- Pages are addressed by hash, for example `#v1-01`, `#v2-44`, `#jx`, `#guide`, `#preface`, `#mag-2`, `#afterword`.
- The notes switch (注释) and language choice are remembered in the reader's browser via localStorage.
- Fonts come from Google Fonts; everything else is in this folder.

Contents: preface (zh/en); Volume One 《阴燃》 chapters 1–22 and Volume Two 《余烬》 23–44 (zh/en, with switchable notes on the Chinese); the sequel 《焦线》 (zh, with notes); 《阴燃》导读 (zh); and *Second Look*, a fictional magazine companion (en).
