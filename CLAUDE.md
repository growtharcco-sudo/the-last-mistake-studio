# The Last Mistake studio

This repo makes and posts two Reels a day for The Last Mistake (Instagram and YouTube @thelastmistakefiles).
For every run, follow `ROUTINE.md` step by step. Never post directly: queue it, and GitHub Actions posts at `post_at`.
Hard rules:
- Write a brief and build the spec with `pipeline/kit.py`. Never hand-write scene coordinates or edit specs by hand.
- Check a Reel with `make_reel.py --sheet` and read only that one sheet.png, not single stills.
- Every fact from a reputable source fetched the same day; every number in `math`, checked in Python.
- No em dashes or en dashes. Instagram caption ends with a real question, then exactly 5 hashtags including
  #thelastmistake. YouTube description has a Sources list and 3 hashtags including #Shorts.
- Voice is Kokoro am_michael (clean, no echo). Instagram AI label and YouTube synthetic-content disclosure stay on.
- Full quality: 1080x1920, 30 fps, CRF 16. Never lower quality to save time or file size.
- Do not change the look (fx.py, engine.py drawing) unless James asks.
- If James replies "skip", create `queue/<id>/SKIP`, commit and push.
- Never put tokens or passwords in files or chat: they live only in GitHub Secrets.
