[简体中文](README.md) | **English**

# WeChat Channels download + Whisper transcription

> Extract WeChat Channels videos and generate SRT subtitles plus a plain-text transcript.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)

> [!IMPORTANT]
> ### The default public resolver is no longer available
>
> As documented in the project's **2026-10-05 checks**, the default endpoint, `sph.litao.workers.dev`, is a public deployment of upstream [`ltaoo/wx_channels_download`](https://github.com/ltaoo/wx_channels_download). Its Yuanbao account was suspended, and the author added credential checks to the `sph` Worker. Anonymous requests returned `HTTP 401 {"error":"unauthorized"}`.
>
> The deployment owner sets the credential; third parties cannot obtain it simply by waiting for the public URL to recover.
>
> Three alternatives, ordered by account exposure:
>
> 1. **No account credentials:** transcribe local media with `--input-file`, supply a direct URL with `--video-url`, or extract a URL from captured traffic with `--har`. See [Option A](#option-a-no-account-credentials).
> 2. **Local resolution:** set `YUANBAO_COOKIE`. No deployed service is needed, but your Yuanbao account is used and may be suspended. See [Option B](#option-b-local-resolution).
> 3. **Self-hosted resolver Worker:** see [Option C](#option-c-self-hosted-cloudflare-resolver-worker).
>
> Read [account risks](#account-risks) before choosing B or C. This repository does not bypass authentication; account-based options use your own credentials.

---

## Features

One command runs the transcription pipeline:

1. Resolve a WeChat Channels share link to a playback URL. The public endpoint is unavailable; use A for credential-free inputs or B / C for account-based resolution.
2. Download the video with the required Referer header.
3. Extract 16 kHz mono WAV audio.
4. Transcribe Chinese speech with OpenAI Whisper.
5. Write **SRT subtitles** and a **plain-text transcript**.

## Example output

| Input | Output |
| --- | --- |
| WeChat Channels share link | `audio.srt` — timestamped subtitles |
| Example: `https://weixin.qq.com/sph/Ap5KZZrF3F` | `transcript.txt` — plain-text transcript |

## Installation

### Dependencies

- **Python 3.9+**
- **curl** — resolver requests and video downloads
- **ffmpeg** — audio extraction
- **openai-whisper** — speech recognition

Using only `--resolve-only` requires Python and curl.

### Quick installation

```bash
# macOS with Homebrew
brew install curl ffmpeg
pip install openai-whisper
```

Without Homebrew, pip can supply a full ffmpeg binary:

```bash
python3 -m venv ~/.venv/wvt && source ~/.venv/wvt/bin/activate
pip install openai-whisper imageio-ffmpeg

# ~/.local/bin must already be on PATH
ln -sf "$(python -c 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())')" ~/.local/bin/ffmpeg
```

That ffmpeg build includes libx264 / libmp3lame and supports this project's MP4-to-16-kHz-mono-WAV conversion. Whisper also installs PyTorch, requiring roughly 1 GB of disk space. Models download on first use: base about 145 MB, small about 460 MB, and medium about 1.5 GB.

### Chinese output

Whisper often outputs Traditional Chinese by default. The script supplies a Mandarin initial prompt intended to encourage Simplified Chinese and improve punctuation. Override or disable it as follows:

```bash
# Custom prompt with specialist terms
python3 scripts/transcribe.py --input-file ./video.mp4 --initial-prompt "以下是普通话的句子。关键词：动力保障、离心冷水机组。"

# Disable the prompt; native output may be Traditional Chinese
python3 scripts/transcribe.py --input-file ./video.mp4 --initial-prompt ""

# Non-Chinese content
python3 scripts/transcribe.py --input-file ./video.mp4 --language English
```

## Quick start

```bash
# Optional resolver configuration; see the alternatives below.
# No credentials: use --input-file, --video-url, or --har.
# Account-based local resolution: use your own Yuanbao cookie,
# preferably from a spare account.
export YUANBAO_COOKIE="<your Yuanbao web cookie>"
# Or point to your own deployed Worker:
# export WECHAT_VIDEO_API_URL="https://<your-worker>/api/fetch_video_profile"
# export WECHAT_VIDEO_API_TOKEN="<your configured credential>"

# Generate subtitles and a transcript
python3 scripts/transcribe.py "https://weixin.qq.com/sph/Ap5KZZrF3F"

# Select a larger model
python3 scripts/transcribe.py "https://weixin.qq.com/sph/Ap5KZZrF3F" --model medium

# Choose the output directory
python3 scripts/transcribe.py "https://weixin.qq.com/sph/Ap5KZZrF3F" --output-dir ./subtitles

# Test resolution without downloading or loading Whisper
python3 scripts/transcribe.py "https://weixin.qq.com/sph/Ap5KZZrF3F" --resolve-only

# Supply a direct playback URL, skipping resolution
python3 scripts/transcribe.py --video-url "https://finder.video.qq.com/....mp4" --output-dir ./subtitles

# Extract a direct URL from a HAR or plain-text URL list
python3 scripts/transcribe.py --har ./capture.har --output-dir ./subtitles

# Transcribe an existing local video or audio file
python3 scripts/transcribe.py --input-file ./video.mp4 --output-dir ./subtitles
```

## Supported share-link formats

- `https://weixin.qq.com/sph/XXXXX`
- `https://channels.weixin.qq.com/finder-preview/pages/sph?id=XXXXX`

## Whisper model selection

The following figures are the original README's approximate guidance, not a general accuracy benchmark.

| Model | Speed | Approximate Chinese accuracy | Intended use |
| --- | --- | --- | --- |
| `tiny` | Very fast | ~85% | Quick preview |
| `base` | Fast | ~90% | Everyday transcription **(default)** |
| `small` | Moderate | ~93% | Higher accuracy |
| `medium` | Slow | ~95% | Formal transcripts |

```bash
# Default: base
python3 scripts/transcribe.py "<share-link>"

# Prioritize accuracy
python3 scripts/transcribe.py "<share-link>" --model medium
```

In a comparison on the same Chinese speech sample on 2026-10-05, `base` misheard “语音” as “与音” and omitted a short ending phrase. `small` recognized “语音” correctly but still made homophone errors. Start with **small** when accuracy matters; base suits a quick preview.

## Manual workflow

For finer control, run the stages separately:

```bash
# 1a. Local resolution (Option B; uses your Yuanbao account)
curl -s -X POST "https://yuanbao.tencent.com/api/weixin/get_parse_result" \
  -H "Content-Type: application/json" \
  -H "Cookie: <your Yuanbao cookie>" \
  -d '{"type":"video_channel_url","url":"<share-link>","scene":1}'
# Read token / eid from the query in data.playable_url.
# If eid is absent, use data.wx_export_id.
curl -s -X POST "https://channels.weixin.qq.com/finder-preview/api/feed/get_feed_info" \
  -H "Content-Type: application/json" \
  -H "Origin: https://channels.weixin.qq.com" \
  -d '{"baseReq":{"generalToken":"<token>"},"exportId":"<eid>"}'
# Playback URL: data.feedInfo.h264VideoInfo.videoUrl

# 1b. Your self-hosted Worker (Option C; same account risks as B)
curl -s -X POST "https://<your-worker>/api/fetch_video_profile" \
  -H "Content-Type: application/json" \
  -H "User-Agent: Mozilla/5.0 ..." \
  -H "Authorization: Bearer <your configured credential>" \
  -d '{"url":"<share-link>"}'

# 1c. Credential-free inputs (Option A)
python3 scripts/transcribe.py --har ./capture.har --output-dir ./subtitles
python3 scripts/transcribe.py --video-url "https://finder.video.qq.com/....mp4" --output-dir ./subtitles
python3 scripts/transcribe.py --input-file ./video.mp4 --output-dir ./subtitles

# 2. Download
curl -L -o video.mp4 \
  -H "User-Agent: Mozilla/5.0 ... Chrome/120.0.0.0 Safari/537.36" \
  -H "Referer: https://channels.weixin.qq.com/" \
  "<video_url>"

# 3. Extract audio
ffmpeg -i video.mp4 -vn -acodec pcm_s16le -ar 16000 -ac 1 audio.wav

# 4. Transcribe; the initial prompt encourages Simplified Chinese
whisper audio.wav --language Chinese --model base --output_format srt --output_dir . \
  --initial_prompt "以下是普通话的句子。"

# 5. Extract plain text
awk 'NR%4==3' audio.srt > transcript.txt
```

## Output files

| File | Description |
| --- | --- |
| `audio.srt` | Standard SRT subtitles, loadable in VLC, IINA, and other players |
| `transcript.txt` | Plain text for copying and further editing |

## Technical notes

- Video downloads require `Referer: https://channels.weixin.qq.com/`; otherwise the WeChat CDN may reject the request.
- Audio is extracted as 16 kHz mono PCM WAV for Whisper.
- Video files are processed in a temporary directory and cleaned up afterward.

## Use as a WorkBuddy skill

This project is also an AI skill for [WorkBuddy](https://www.codebuddy.cn). After installation, ask in natural language:

```text
Extract subtitles from this WeChat Channels video:
https://weixin.qq.com/sph/XXXXX
```

Install `SKILL.md` into `~/.workbuddy/skills/wechat-video-transcribe/`.

## Resolver API and limitations: checks recorded on 2026-10-05

The default third-party service, `sph.litao.workers.dev`, stopped accepting public access. After its upstream account was suspended, credential checks were enabled; anonymous requests returned `HTTP 401 {"error":"unauthorized"}`. The public URL is not expected to recover by itself. The alternatives below are ordered by account exposure. This project does not bypass authentication.

### Configuration

```bash
# A: no configuration for --input-file / --video-url / --har

# B: local resolution with your Yuanbao account; prefer a spare account
export YUANBAO_COOKIE="<your Yuanbao web cookie>"

# C: your own Worker URL and credential; same account risks as B
export WECHAT_VIDEO_API_URL="https://your-worker.workers.dev/api/fetch_video_profile"
export WECHAT_VIDEO_API_TOKEN="<credential configured when deploying the Worker>"

# Optional proxy; curl also honors https_proxy / ALL_PROXY
export WECHAT_VIDEO_PROXY="http://127.0.0.1:<your-proxy-port>"
```

### Common commands

```bash
# Verify resolution without loading Whisper
python3 scripts/transcribe.py "https://weixin.qq.com/sph/A4waITx8sO" --resolve-only

# Extract a direct URL from captured traffic, then transcribe
python3 scripts/transcribe.py --har ./capture.har --output-dir ./subtitles

# Supply a direct URL
python3 scripts/transcribe.py --video-url "https://finder.video.qq.com/....mp4" --output-dir ./subtitles

# Local media: no resolver dependency
python3 scripts/transcribe.py --input-file /path/to/video.mp4 --output-dir ./subtitles
```

### Response compatibility

The script accepts both response formats:

| Format | Playback URL location |
| --- | --- |
| Older flat response | Top-level `video_url` |
| Newer nested response | `data.feedInfo.h264VideoInfo.videoUrl`, `h265VideoInfo.videoUrl`, or `feedInfo.videoUrl` |

Errors are distinguished: HTTP 401 / 403 authentication failure with the service's reason, timeout or connection failure, non-JSON responses, other non-2xx statuses, and successful HTTP responses with no playback URL. **A title, author, or cover image does not prove the video can be downloaded.**

### Why the public resolver stopped

The endpoint was the `sph` Cloudflare Worker deployment from [`ltaoo/wx_channels_download`](https://github.com/ltaoo/wx_channels_download). In [issue #495](https://github.com/ltaoo/wx_channels_download/issues/495), dated 2026-08-13, the upstream author reported that the Yuanbao account had been suspended and that credential validation would be added.

The upstream `deploy sph` documentation requires an `ACCESS_CREDENTIAL` for page and API access. Authentication failure returns 401; an unconfigured credential returns 503. Supported methods include `Authorization: Bearer <credential>` and Basic Auth `wxchannels:<credential>`. The deployment owner sets that credential.

Changing request headers does not remove this access control. WeChat's own `get_feed_info` call also needs a `generalToken`, and the inspected share-page playback logic runs only in a WeChat environment. See [browser capture](#browser-capture-why-an-ordinary-browser-does-not-expose-the-stream).

### Account risks

| | Option | Requirements | Account exposure | Automation |
| --- | --- | --- | --- | --- |
| ⭐ | A. Credential-free inputs | Local file, direct URL, or capture file | No account used by the transcription entry point | Partly manual: obtain the input first |
| ⚠️ | B. Local resolution | Your Yuanbao cookie | Yuanbao account risk | Automatic |
| ⚠️ | C. Self-hosted Worker | Cloudflare + your Yuanbao cookie | Same as B, with a larger exposure surface | Automatic |

The Chinese README describes A as “zero risk”; here that refers specifically to avoiding account credentials in the transcription entry point. Obtaining or sharing source files and captured traffic still requires care.

1. **The directly exposed account is Yuanbao.** The README's privacy-policy review notes that products may associate accounts registered with the same phone number while handling deletion or suspension separately. A Yuanbao suspension does not necessarily suspend WeChat, but association risk cannot be completely ruled out because sign-in may use WeChat / QQ. Avoid testing with your main account.
2. **Upstream used one account's cookie in a public service for many strangers.** The README attributes the suspension to abnormal traffic scale rather than merely calling the endpoint. Low-frequency local use may reduce exposure, but does not eliminate it.
3. **Cookies are login credentials**, including `hy_user` and `hy_token`. A leak can compromise the account. Do not commit them, send them to others, or expose them through a public service.
4. Similar project [`ucmao/media-parser`](https://github.com/ucmao/media-parser) also treats `YUANBAO_COOKIE` as private account data and recommends a spare account.

If you choose B or C, use a spare account, keep use local and infrequent, and never share the cookie or run an open public service. Signing out of Yuanbao can invalidate the cookie. The README estimates a cookie lifetime of about one month; when it expires, the script reports the failure so you can sign in again.

If you do not want account-based resolution, use A.

---

### Option A: no account credentials

You must first obtain a local video or a direct playback URL.

**A1. Local media → `--input-file`**

Use media obtained through an authorized route, such as a WeChat PC client with upstream [`ltaoo/wx_channels_download`](https://github.com/ltaoo/wx_channels_download), a phone screen recording, or an author-authorized export:

```bash
python3 scripts/transcribe.py --input-file ./video.mp4 --output-dir ./subtitles
```

**A2. Direct playback URL → `--video-url`**

```bash
python3 scripts/transcribe.py --video-url "https://finder.video.qq.com/....mp4" --output-dir ./subtitles
```

**A3. Captured traffic → `--har`**

Export HAR using a proxy / traffic-capture tool such as Charles, mitmproxy, or Proxifier, or save captured URLs as plain text. The script selects a video URL:

```bash
python3 scripts/transcribe.py --har ./capture.har --output-dir ./subtitles
```

Candidates are scored by `video.qq.com` domain, `video/*` MIME type, and `.mp4` extension. If only segmented streams (`.m4s` / `.ts`) are available or multiple candidates tie, the script refuses to guess and asks you to specify `--video-url`.

The README's checks found no WeChat Channels extractor in official yt-dlp; `yt-dlp <share-link>` was not a working route.

### Browser capture: why an ordinary browser does not expose the stream

Some tutorials suggest sending a link to Yuanbao's web app, clicking the card, then sniffing playback in a browser. The project's inspection of the official share-page JavaScript found:

```js
const ti = Ba(), { noRedirect: ai } = xe();
if (ti === Ma.WECHAT && !ai) {
  const n = se().token || Xa("token") || "";
  return o ? (await Ka.getFeedInfo({ baseReq: { generalToken: n }, ... })).data.sceneInfo : void 0
}
```

The playback-data request is guarded by `ti === Ma.WECHAT`, requiring the WeChat environment with `WeixinJSBridge`. An ordinary browser takes a redirect / open-in-WeChat route instead. The inspected HTML was an approximately 2.6 KB SPA shell; JavaScript fetches the data.

Capture must therefore occur in the environment actually playing the video, such as the WeChat PC client with a proxy tool. Pass the resulting URL or capture file to `--video-url` or `--har`.

---

### Option B: local resolution

> ⚠️ This uses your Yuanbao account. Read [account risks](#account-risks) first and prefer a spare account.

The upstream Worker's core flow consists of HTTP requests and can run locally without Cloudflare, using your own Yuanbao login cookie:

| Step | Request |
| --- | --- |
| 1 | `POST https://yuanbao.tencent.com/api/weixin/get_parse_result` with body `{"type":"video_channel_url","url":"<share-link>","scene":1}` and `Cookie: <your Yuanbao cookie>` |
| 2 | Read `token` (generalToken) and `eid` (exportId) from `data.playable_url`; fall back to `data.wx_export_id` if eid is missing |
| 3 | `POST https://channels.weixin.qq.com/finder-preview/api/feed/get_feed_info` with body `{"baseReq":{"generalToken":"<token>"},"exportId":"<eid>"}`; read `data.feedInfo.h264VideoInfo.videoUrl` |

The script includes this chain. Configure one environment variable:

```bash
# Sign in at https://yuanbao.tencent.com/ in your browser.
# In Developer Tools → Network, copy the complete Cookie request-header value.
export YUANBAO_COOKIE="<your Yuanbao cookie>"

# Verify resolution first
python3 scripts/transcribe.py "https://weixin.qq.com/sph/AOVsoW8dBI" --resolve-only
# Then run the full pipeline
python3 scripts/transcribe.py "https://weixin.qq.com/sph/AOVsoW8dBI"
```

When `YUANBAO_COOKIE` is set, the script uses the local chain instead of `WECHAT_VIDEO_API_URL`. The cookie is passed to curl through standard input, not through command-line arguments, process listings, or logs.

Cookies may expire; the README estimates about one month. The script reports invalid cookies. The upstream service stopped following a Yuanbao suspension, so this option exposes your own Yuanbao account to that risk. Use a spare account.

---

### Option C: self-hosted Cloudflare resolver Worker

This adds deployment to option B but allows other devices to use the resolver without a local cookie file. Account risks are the same as B. Sharing the Worker URL and credential can recreate upstream's scenario of one account serving many strangers.

Requires a Cloudflare account and a Yuanbao web login cookie.

1. Install the upstream CLI following [`ltaoo/wx_channels_download`](https://github.com/ltaoo/wx_channels_download).
2. Configure:

   | Setting | Description |
   | --- | --- |
   | `cloudflare.accountId` | Cloudflare account ID |
   | `cloudflare.apiToken` | API token with Workers read / write access |
   | `cloudflare.sphWorkerName` | Worker name |
   | `cloudflare.sphCookie` | Yuanbao web cookie; the README estimates about one month of validity |
   | `cloudflare.sphCredential` | Access credential that you choose |

3. Deploy:

   ```bash
   wx_video_download deploy sph
   ```

4. Point this project to it:

   ```bash
   export WECHAT_VIDEO_API_URL="https://<sphWorkerName>.<subdomain>.workers.dev/api/fetch_video_profile"
   export WECHAT_VIDEO_API_TOKEN="<your configured sphCredential>"
   python3 scripts/transcribe.py "https://weixin.qq.com/sph/AOVsoW8dBI" --resolve-only
   ```

The original README uses title / author output as a basic connectivity signal; a usable playback URL is still required. Once resolution succeeds, remove `--resolve-only` to run the full pipeline.

> ⚠️ Upstream explicitly advises personal use only, not a public service. Publishing the endpoint and credential can recreate the conditions behind its account suspension.

---

### Recorded test results

These are historical project results from **2026-10-05**, not a fresh probe of upstream services.

| Check | Recorded result |
| --- | --- |
| Direct connection to `sph.litao.workers.dev` | Timed out; a proxy was needed |
| Through the local HTTP proxy | `HTTP 401 {"error":"unauthorized"}` |
| Public deployment recovery | Not expected without owner intervention: the Yuanbao account was suspended and owner-defined credential checks were added; see issue #495 and deployment docs |
| WeChat `get_feed_info` without `generalToken` | `HTTP 401 permission verification failed`; no playback data |
| Official share page | Playback logic guarded by `ti === Ma.WECHAT` in `feed.*.js`; ordinary browser did not expose the URL |
| Yuanbao `get_parse_result` | Domain reachable directly in about 0.15 s; anonymous calls returned HTTP 401 |
| Local chain, B | 19 mocked scenarios passed: token / eid extraction, expired-cookie errors, cookie redaction, WeChat error-echo handling, and mutually exclusive input sources. **Not verified with a real Yuanbao cookie** |
| `--har`, A3 | 12 scenarios passed: full MP4 selection among segments, refusal of segment-only input or tied candidates, plain-text URL lists, and end-to-end SRT / transcript output without resolver calls |
| `--video-url` / `--input-file`, A | End-to-end passed using stub ffmpeg / whisper |
| **Actual download → extraction → Whisper** | **Verified on macOS arm64**, using a full ffmpeg 7.1 build and openai-whisper 20250625 (torch 2.14.1). A nine-second Chinese TTS-generated MP4 produced `audio.srt` and `transcript.txt` |
| Chinese script | Native Whisper output was Traditional Chinese; the default Mandarin prompt yielded Simplified Chinese. `--initial-prompt ""` disabled the prompt as expected |
| Complete B / C download and transcription | **Not verified** without a Yuanbao cookie / self-hosted Worker credential. ffmpeg + Whisper were verified; obtaining the playback URL remains unverified |

The public resolver's authentication failure is an access-control decision rather than a transcription-script fault. Option A avoids account credentials. B / C require your own Yuanbao cookie and expose that account to suspension risk.

## License

MIT
