# vmt

[![license](https://img.shields.io/github/license/antifield/vmt?style=flat&colorA=000000&colorB=000000)](LICENSE)
[![black](https://img.shields.io/badge/code%20style-black-000000?style=flat&colorA=000000&colorB=000000)](https://github.com/psf/black)

Transcribe and translate Discord voice messages.

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

| Command                            | Description                                                                          |
| ---------------------------------- | ------------------------------------------------------------------------------------ |
| `/transcribe [translate_to] [public]` | Transcribe the selected voice message, optionally translating it into another language |
| `/languages [public]`              | Browse all supported translation languages and their codes                           |
| `/help [public]`                   | Show usage instructions and the command reference                                    |

Responses are only visible to you by default; set `public: true` to post them to the channel.

## How it works

Voice messages are decoded with [pydub](https://github.com/jiaaro/pydub) (via FFmpeg), transcribed using Google Speech Recognition through [SpeechRecognition](https://github.com/Uberi/speech_recognition), and translated with the [DeepL API](https://developers.deepl.com/docs).

## Self-hosting

### 1. Create a Discord application

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and create a new application
2. Under **Installation → Installation Contexts**, enable both **User Install** and **Guild Install**
3. Under **Installation → Default Install Settings**, add the `applications.commands` scope to both install contexts
4. Under **Bot → Privileged Gateway Intents**, enable **Message Content Intent** (required to read voice message attachments)
5. Copy your bot token from the **Bot** page — you'll need it for the environment variables
6. Copy the install link from the **Installation** page to add the app to your account or server

### 2. Configure environment variables

| Variable                     | Description                                                                                              |
| ---------------------------- | -------------------------------------------------------------------------------------------------------- |
| `BOT_TOKEN`                  | Your Discord bot token from the [Developer Portal](https://discord.com/developers/applications)          |
| `DEEPL_API_KEY`              | Your [DeepL API](https://www.deepl.com/pro-api) key                                                      |
| `DEEPL_FREE_API`             | Set to `true` if using DeepL's free tier (it uses a separate endpoint, `api-free.deepl.com`); defaults to `false` |
| `MAX_VOICE_MESSAGE_DURATION` | Maximum voice message duration in seconds (default: `60`)                                                |

### 3. Deploy

#### Railway (recommended)

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/deploy/LBtckT?referralCode=antifield&utm_medium=integration&utm_source=template&utm_campaign=generic)

This repository deploys to [Railway](https://railway.com?referralCode=antifield) in one click and handles the FFmpeg installation automatically. Signing up through our link also grants you $20 in Railway credits.

#### Run locally

You'll need Python (developed against 3.13) and FFmpeg:

- **macOS:** `brew install ffmpeg`
- **Ubuntu/Debian:** `sudo apt-get install ffmpeg`
- **Windows:** download from [ffmpeg.org](https://ffmpeg.org/download.html), or `choco install ffmpeg` via [Chocolatey](https://chocolatey.org/)

```bash
git clone https://github.com/antifield/vmt.git
cd vmt

pip install -r requirements.txt

# copy env, fill in credentials
cp .env.example .env

python src/main.py
```

## License

[antifield/vmt](https://github.com/antifield/vmt) is licensed under the [GNU General Public License v3.0](LICENSE). Authored by [@dromzeh](https://dromzeh.dev/) <[marcel@antifield.com](mailto:marcel@antifield.com)>.

You must state all significant changes made to the original software, make the source code available to the public with credit to the original author, original source, and use the same license.

> © 2023–2026 Antifield LTD | Registered UK Company No. 15988228 | ICO Reference No. ZB857511
