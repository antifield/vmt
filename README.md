<p align="center">
  <h1 align="center">vmt</h1>
  <p align="center">Transcribe and translate Discord voice messages.</p>
  <p align="center">
    <a href="https://discord.gg/noid"><img alt="Discord members" src="https://shieldcn.dev/discord/members/noid.svg?variant=secondary&size=xs" /></a>
    <a href="https://railway.com?referralCode=antifield"><img alt="Deployed on Railway" src="https://shieldcn.dev/badge/Deployed%20on-Railway.svg?logo=railway&variant=secondary&size=xs" /></a>
    <img alt="Made with love" src="https://shieldcn.dev/badge/made%20with-love.svg?logo=%E2%9D%A4%EF%B8%8F&variant=secondary&size=xs" />
    <a href="LICENSE"><img alt="License: GPL-3.0" src="https://shieldcn.dev/badge/license-GPL--3.0.svg?variant=secondary&size=xs" /></a>
  </p>
</p>

vmt is a Discord app that transcribes voice messages and optionally translates them into 30+ languages via [DeepL](https://www.deepl.com/). It works in servers, group chats, and DMs, and can be installed to a server or to your own account.

> [!NOTE]
> If you don't want to deploy or self-host, we run a free hosted instance that supports voice messages up to 3 minutes.
>
> [Add to Discord →](https://discord.com/oauth2/authorize?client_id=1434011906829455451)

## Usage

1. Right-click a voice message (long-press on mobile)
2. Select **Apps → Select Voice Message**
3. Run `/transcribe`, optionally passing a language to translate into

### Commands

| Command                               | Description                                                                             |
| ------------------------------------- | --------------------------------------------------------------------------------------- |
| `/transcribe [translate_to] [public]` | Transcribe the selected voice message, optionally translating it into another language |
| `/languages [public]`                 | Browse all supported translation languages and their codes                             |
| `/help [public]`                      | Show usage instructions and the command reference                                      |

Responses are only visible to you by default; set `public: true` to post them to the channel.

## How it works

Voice messages are decoded with [pydub](https://github.com/jiaaro/pydub) (via FFmpeg) and transcribed with [ElevenLabs Scribe](https://elevenlabs.io/speech-to-text) when an API key is configured, falling back to Google Speech Recognition through [SpeechRecognition](https://github.com/Uberi/speech_recognition) otherwise. Translations use the [DeepL API](https://developers.deepl.com/docs).

Every clip is checksummed and cached in a [libsql](https://github.com/tursodatabase/libsql) database (a local file by default, or [Turso](https://turso.tech/) remotely), so the same voice message is never transcribed twice — and cache hits never count against usage quotas. Optional per-user daily quotas (in seconds of audio) keep public instances abuse-proof.

## Repository layout

| Path       | Description                                        |
| ---------- | -------------------------------------------------- |
| `apps/bot` | The Discord bot — Python, managed with [uv](https://github.com/astral-sh/uv) |
| `apps/web` | [vmt.sh](https://vmt.sh) — Astro + React site      |

## Self-hosting

### 1. Create a Discord application

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and create a new application
2. Under **Installation → Installation Contexts**, enable both **User Install** and **Guild Install**
3. Under **Installation → Default Install Settings**, add the `applications.commands` scope to both install contexts
4. Under **Bot → Privileged Gateway Intents**, enable **Message Content Intent** (required to read voice message attachments)
5. Copy your bot token from the **Bot** page — you'll need it for the environment variables
6. Copy the install link from the **Installation** page to add the app to your account or server

### 2. Configure environment variables

| Variable                     | Description                                                                                                       |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `BOT_TOKEN`                  | Your Discord bot token from the [Developer Portal](https://discord.com/developers/applications)                    |
| `DEEPL_API_KEY`              | Your [DeepL API](https://www.deepl.com/pro-api) key                                                                |
| `DEEPL_FREE_API`             | Set to `true` if using DeepL's free tier (it uses a separate endpoint, `api-free.deepl.com`); defaults to `false`  |
| `ELEVENLABS_API_KEY`         | *Optional.* [ElevenLabs](https://elevenlabs.io/) key for Scribe transcription; unset falls back to free Google Speech Recognition |
| `TURSO_DATABASE_URL`         | *Optional.* Remote [Turso](https://turso.tech/) database URL; unset uses a local file at `data/vmt.db`             |
| `TURSO_AUTH_TOKEN`           | *Optional.* Auth token for the Turso database                                                                      |
| `DAILY_LIMIT_SECONDS`        | *Optional.* Per-user daily audio quota in seconds; unset means unlimited                                            |
| `MAX_VOICE_MESSAGE_DURATION` | Maximum voice message duration in seconds (default: `60`)                                                          |

### 3. Deploy

#### Docker (recommended)

```bash
git clone https://github.com/antifield/vmt.git
cd vmt

# copy env, fill in credentials
cp apps/bot/.env.example apps/bot/.env

docker compose up -d
```

The compose file persists the local database to `./data`.

#### Railway

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/deploy/LBtckT?referralCode=antifield&utm_medium=integration&utm_source=template&utm_campaign=generic)

This repository deploys to [Railway](https://railway.com?referralCode=antifield) in one click, with a volume mounted at `/app/data` so the local database survives redeploys. Signing up through our link also grants you $20 in Railway credits.

If you deploy to Railway manually instead of via the template, attach a volume at `/app/data` and set `RAILWAY_RUN_UID=0` (Railway mounts volumes as root, and the container runs as a non-root user). Setting `TURSO_DATABASE_URL` skips the need for a volume entirely.

#### Run locally

You'll need Python 3.13+, [uv](https://docs.astral.sh/uv/), and FFmpeg:

- **macOS:** `brew install ffmpeg`
- **Ubuntu/Debian:** `sudo apt-get install ffmpeg`
- **Windows:** download from [ffmpeg.org](https://ffmpeg.org/download.html), or `choco install ffmpeg` via [Chocolatey](https://chocolatey.org/)

```bash
git clone https://github.com/antifield/vmt.git
cd vmt/apps/bot

# copy env, fill in credentials
cp .env.example .env

uv run python -m vmt
```

## Website

The [vmt.sh](https://vmt.sh) site lives in `apps/web` (Astro + React + Tailwind):

```bash
cd apps/web
bun install
bun run dev
```

## License

[antifield/vmt](https://github.com/antifield/vmt) is licensed under the [GNU General Public License v3.0](LICENSE). Authored by [@dromzeh](https://dromzeh.dev/) <[marcel@antifield.com](mailto:marcel@antifield.com)>.

You must state all significant changes made to the original software, make the source code available to the public with credit to the original author, original source, and use the same license.

> © 2023–2026 Antifield LTD | Registered UK Company No. 15988228 | ICO Reference No. ZB857511
