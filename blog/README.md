# Blog

Articles on AI, served by GitHub Pages at `/blog/` on this site. Every push to `main` redeploys the site.

## Layout

- `index.html`: the list of posts. Add a new `<li>` at the top of the list for each post.
- `blog.css`: shared styles for the list and the posts. Fonts come from the site's `stylesheet.css`.
- `post-template.html`: the pandoc template every post is built with.
- One folder per post, for example `job-matching/`:
  - `article.md`: the source. Front matter sets `title`, `subtitle` and `date`. Math uses `$...$` inline and `$$...$$` for display.
  - `index.html`: the built page. Do not edit it by hand.
  - figures (`.svg`) and a `files/` folder for PDFs and code.

## Adding a post

1. Create a folder, `blog/<slug>/`, with an `article.md`.
2. Build the page from inside that folder:

   ```
   pandoc article.md -s --template ../post-template.html \
     --mathjax=https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml-full.js \
     --wrap=none -o index.html
   ```

3. Add the post to `blog/index.html`, then commit and push.
