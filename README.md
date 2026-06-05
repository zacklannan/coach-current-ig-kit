# Coach Current — Instagram Kit

Pull your Instagram performance data into a clean **export**, then let AI analyze it.
Built for the Coach Current community.

> Works on **Mac and Windows.** Mac users double-click the `.command` files; Windows
> users double-click the `.bat` files. Everything else is identical.

## How it works

1. **Stand it up** — download this folder, run setup (`setup.command` on Mac,
   `setup.bat` on Windows). It asks for your two Meta credentials right in the window
   and saves them for you (your SOP / the seminar walks you through getting them).
2. **Export** — run it (`run.command` on Mac, `run.bat` on Windows). It writes your
   data to an `export/` folder: `account-summary.md`, `posts.csv`, `audience.csv`,
   `stories.csv`, `comments.csv`.
3. **Analyze** — open this folder as a **Cowork project**. The `social-analyst`
   skill is already inside it. Ask it to analyze the export and it returns a
   prioritized content strategy — what's working, what to change, when to post, and
   content ideas grounded in your real numbers (plus current trends).

That's the whole loop: **stand up → export → drop into Cowork → analyze.**

## Setup

1. Download this folder (GitHub: green **Code → Download ZIP**, then unzip).
2. Run setup:
   - **Mac:** double-click **`setup.command`** (first time, macOS may block it — right-click → Open → Open).
   - **Windows:** double-click **`setup.bat`** (if you don't have Python, install it from python.org and tick **"Add Python to PATH"**).
3. When it asks, paste your two values and press Enter:
   - **App Secret** — from your Meta app (Instagram product → API setup)
   - **Token** — the "Generate token" button
   It saves them for you — no files to find or edit.
4. Run the export:
   - **Mac:** double-click **`run.command`**
   - **Windows:** double-click **`run.bat`**

> Prefer to edit the file yourself? You still can: the values live in `.env`
> (a hidden file — in Finder press **Cmd+Shift+.** to show it).

> Getting the Meta credentials (the app, tester role, token) is covered in the SOP
> and the done-with-you seminar. This kit just turns those credentials into an export.

## Updating your credentials later

Tokens expire (~60 days), and if you add a permission you'll need a fresh token. To
update: **run setup again** (`setup.command` on Mac, `setup.bat` on Windows) and paste
the new value(s) when asked (leave a line blank to keep the existing one). It
automatically clears the old saved token so the new one takes effect. No file editing.

## Set up your Cowork project (one time)

So the AI sounds like *you* and points at *your* offer:

1. **Fill in `brand-profile.md`** — your niche, ideal customer, voice, offers, content
   pillars, and call to action. This is what turns generic advice into on-brand content.
2. **Paste the project instructions** — copy the block in `project-instructions.md`
   into your Cowork project's instructions field. It tells the AI to use your profile
   and the skill every time.

## Using the export in Cowork

Open this folder as a project in Cowork. The skill in `skills/social-analyst/` loads
automatically, and it reads your `brand-profile.md`. Then say: *"Analyze my Instagram
export and give me a prioritized plan and content ideas for the next two weeks."* Or
*"Write me 5 posts for this week based on what's working."*

## Optional extras

- **Comments:** add the `instagram_business_manage_comments` permission to your app,
  then set `ENABLE_COMMENTS=true` in `.env` (and regenerate your token so it includes
  the new permission).
- **Stories:** on by default, but Stories vanish from the API after 24h — run the kit
  the same day you post Stories to capture them.

## Notes

- You can only export accounts **you own**.
- Your `.env` holds your token — keep it private. It's gitignored automatically.
- The `history/` folder snapshots your follower count each run, so trends build up
  over time even though Instagram only keeps ~30 days.

## What's in here

```
setup.command / run.command   double-click launchers (Mac)
setup.bat / run.bat           double-click launchers (Windows)
ig_export.py                  the export script (one file)
save_creds.py                 helper the launchers use to save your creds
.env.example                  credentials template
brand-profile.md              fill in: your niche, customer, voice, offers
project-instructions.md       paste into your Cowork project's instructions
skills/social-analyst/        the analysis skill (for Cowork)
export/                       generated: your export files
history/                      generated: follower snapshots over time
```
