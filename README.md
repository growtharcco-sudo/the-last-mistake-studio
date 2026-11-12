# The Last Mistake studio

Detective case-file Reels and Shorts. Every case has a last mistake.

```
briefs/<id>.json  --pipeline/kit.py-->  specs/<id>.json  --pipeline/make_reel.py-->  queue/<id>/video.mp4
```

- `pipeline/kit.py`: brief -> spec from tested scene blocks + layout check (exits 1 on LAYOUT PROBLEMS)
- `pipeline/make_reel.py`: channel rule checks, voice, render. `--sheet` = one check image for the whole Reel
- `pipeline/engine.py`: renders both looks (Evidence Board, halftone dossier), sound effects, captions, cover
- `pipeline/voice.py`: Kokoro am_michael narration (model downloads once to ~/.cache/kokoro)
- `pipeline/fx.py`: the drawing blocks (cork, halftone, stamps, cards, string)
- `assets/fonts`: Anton, Special Elite, Courier Prime, Caveat (OFL) and Permanent Marker (Apache 2.0), from Google Fonts

- `poster/`: posting (GitHub Actions): `publish_due.py` posts queued Reels at `post_at` to YouTube and Instagram;
  videos are served from the `media` branch by GitHub Pages
- `tools/`: `check_keys.py`, `deep_check.py` (no public posts), `get_youtube_token.py`, `backfill_thumbnails.py`
- `pages/`: the public site (home, privacy, terms) shown on GitHub Pages

How to make a Reel: `ROUTINE.md`. One-time setup: `SETUP.md`.
