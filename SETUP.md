# One-time setup

Everything is free. Keys go only into GitHub's encrypted Secrets, never into a file or a chat.
Claude guides each step one screen at a time.

## A. GitHub
1. Repo `growtharcco-sudo/the-last-mistake-studio`, Public (done), Claude GitHub app has access (done).
2. Repo -> Settings -> Pages -> Source *Deploy from a branch* -> `media` / `(root)` -> Save.
   Check: https://growtharcco-sudo.github.io/the-last-mistake-studio/ shows the channel page.

## B. Instagram key (never expires): reuse the existing Meta system user and app
1. @thelastmistakefiles is a Professional account linked to a Facebook Page "The Last Mistake".
2. business.facebook.com -> the same Business portfolio as the other channels -> add the new Page and the new
   Instagram account as assets.
3. Settings -> Users -> System users -> (the existing system user) -> Assign assets: the new Page and Instagram
   account, Full control.
4. Generate new token -> the same app -> expiration **Never** -> permissions `instagram_basic`,
   `instagram_content_publish`, `pages_show_list`, `pages_read_engagement` -> that is `IG_TOKEN` (starts with EAA).
5. `IG_USER_ID`: leave it out at first and run **Actions -> Check keys**: it prints the ID to use.

## C. YouTube key: reuse the Google Cloud project and OAuth client, NEW refresh token for THIS channel
1. Download the existing OAuth client JSON (Desktop app) from console.cloud.google.com -> Credentials.
   Add the scope `.../auth/youtube` next to `youtube.upload` on the consent screen (used to delete the deep check's
   test video and set thumbnails), and add https://growtharcco-sudo.github.io/the-last-mistake-studio/ if asked for a home page.
2. On a laptop: `pip3 install google-auth-oauthlib`, then
   `python3 tools/get_youtube_token.py ~/Downloads/client_secret_XXXX.json`. At sign-in choose the
   **The Last Mistake** channel (@thelastmistakefiles). It prints `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`.
   Uploads go PUBLIC directly, with the "altered or synthetic content" disclosure on.

## D. Secrets
Repo -> Settings -> Secrets and variables -> Actions -> New repository secret, one each:
`IG_TOKEN`, `IG_USER_ID`, `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`.
Paste only the value (if a label or spaces slip in, the code cleans them).

## E. Test (posts nothing publicly)
1. Actions -> **Check keys** -> Run workflow: prints the Instagram username and YouTube channel name and IDs.
2. Actions -> **Deep check** -> Run workflow: Instagram processes a test Reel without publishing it; YouTube gets an
   UNLISTED test upload that is checked (stays unlisted = public uploads work), given the thumbnail, then deleted.
3. One real end-to-end post (a `test` slot Reel), then the daily task is switched on.

## F. Scheduled task (Claude)
ONE cloud task, "The Last Mistake daily", runs `ROUTINE.md` section A every day at about 2:30 PM IST.
It needs "Skip all approvals" (Automatically approve) on and no connectors it doesn't use.
