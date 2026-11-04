# Ship Anyway

A small task companion for people who get stuck starting or finishing: two-minute starts, optional focus sessions, saved next steps, and a short “I’m stuck” flow.

Live: https://abc18267.github.io/ship-anyway/

## Using it

- Name one tiny action and choose **Start 2 minutes**. Continue into a focus session, finish the task, or stop when you need to.
- **More options** contains the definition of done, focus duration, optional movement, and planning for today or tomorrow.
- **Save my place** keeps your original start history and an optional next-step note. **Resume for 2 minutes** brings that note back.
- **I’m stuck** offers a smaller step, a stopping point, or a break. The timer pauses while a dialog is open; cancelling resumes it unless you had already paused it.
- Focus sessions allow one specific five-minute revision. Meeting the definition of done, saving a next step, and taking a break remain available.
- Follow-ups are optional, appear after 24 hours, and can be postponed or skipped. Weekly statistics are on their own tab.
- A small illustrated companion gives a brief nod when you start, holds a bookmark when you save your place, and celebrates finishing once. It stays still while you work. **Setup → Companion appearance** offers gentle animation, still characters, or off; the device’s reduced-motion preference always suppresses character animation. The SVG artwork is included in the page and needs no image downloads.
- Choose **Mint buddy**, **Honey bear**, **Lavender owl**, or **Little sprout** from the illustrated picker in Setup. Every character has the same gentle reactions and motion controls.
- **Setup → Timer sound** offers Soft chime, Warm bell, Raindrops, Gentle rise, or Silent, with volume control and a preview button. Sounds are synthesized in the browser, need no downloads, and play once when a timer ends. Previews replace any sound already playing. Character, sound, and volume choices are included in backups.
- Older tasks are folded away. **Set aside** is reversible through **Bring back**.

## Data and privacy

This is one static HTML page with no build or application server. Task data is stored in this browser’s localStorage under `shipanyway.v1`. Existing v1 data remains compatible. There is no account or cross-device sync, no automatic removal of old tasks, and no analytics.

Use **Setup → Download backup** to keep a JSON copy. **Restore backup** validates the file and previews the replacement before confirmation. Confirmation downloads the current work before replacing it; a running session in a backup is restored paused. Backups contain your task titles, history, and personal notes: keep them somewhere private.

Storage failures produce a persistent warning with a backup button. Unreadable existing data is protected from overwriting and can be downloaded separately. Export cannot recover information already removed by older app versions or browser data clearing.

Voice input is optional and has a notice before first use. The browser may send audio to its speech recognition provider; recognition is not guaranteed to work offline or in every browser. In browsers that support on-device speech recognition, Talk offers an English language-pack check and optional download. Selecting on-device voice sets `processLocally` and never silently switches back to online recognition. Network and microphone errors have a recovery dialog. The Talk button remains visible in unsupported browsers and explains how to move to a supported browser.

The app loads fonts from Google Fonts, with system-font fallbacks.

## Development and verification

Open `index.html`, or serve this directory with `python -m http.server 8000` and visit `http://localhost:8000`. GitHub Pages deploys the repository root from `main`.

Browser regression tests use Python Playwright:

```sh
python -m pip install -r tests/requirements.txt
python -m playwright install chromium
python -m unittest discover -s tests -v
```

The tests start a temporary localhost server and isolated browser contexts, then close them. They exercise starting, timer expiry, interruptions, rescue flows, legacy data, backups, storage failures, and responsive layout. They do not use a real microphone or send audio to a recognition provider.
