**简体中文** | [English](README.en.md)

# 微信视频号下载 + Whisper 语音转文字

> 一键提取微信视频号视频并生成 SRT 字幕 + 纯文本逐字稿

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)

> [!IMPORTANT]
> ### 默认的公共解析接口已经不能用了
>
> 本项目默认调用的公共解析地址 `sph.litao.workers.dev` 属于上游开源项目 [`ltaoo/wx_channels_download`](https://github.com/ltaoo/wx_channels_download)。该服务依赖的元宝账号**已被封停**，作者已给 `sph` Worker 加上访问凭证校验——现在匿名请求一律返回 `HTTP 401 {"error":"unauthorized"}`。
>
> **凭证由部署者自己设定，第三方拿不到，所以这个公开地址不会自己恢复，等也没用。**
>
> 想继续拿到视频，有三类做法，**按风险从低到高**排：
>
> 1. **完全离线零风险**——用 `--input-file` 转写本地视频、用 `--video-url` 指定直链、或用 `--har` 从抓包文件自动提取直链。**不碰任何账号凭证**，见 [方案 A](#方案-a完全离线零风险)。
> 2. **本机直跑解析**——设好 `YUANBAO_COOKIE`，不需要部署任何服务，但**会使用你的元宝账号，存在封号风险**，见 [方案 B](#方案-b本机直跑解析)。
> 3. **自建一个查询 Worker**——见 [方案 C](#方案-c自建-cloudflare-查询-worker)。
>
> **封号风险到底落在谁头上、值不值得用，见 [先说风险](#先说风险用不用你自己的账号是分水岭)。** 本仓库**不绕过、不破解任何鉴权**，所有联网方案都使用你自己的账号凭证。

---

## 功能

一条命令完成微信视频号视频的全自动语音转文字流水线：

1. 解析微信视频号分享链接，获取真实视频地址（**公共接口已停用**；零风险做法见方案 A，用账号的做法见方案 B/C，均在文末）
2. 下载视频（带 Referer 绕过 CDN 限制）
3. 提取 16kHz 单声道 WAV 音频
4. OpenAI Whisper 中文语音转写
5. 输出 **SRT 字幕文件** + **纯文本逐字稿**

## 效果展示

| 输入 | 输出 |
|------|------|
| 微信视频号分享链接 | `audio.srt` — 带时间轴的字幕文件 |
| 例如：`https://weixin.qq.com/sph/Ap5KZZrF3F` | `transcript.txt` — 纯文本逐字稿 |

## 安装

### 依赖

- **Python 3.9+**
- **curl** — 调用解析接口并下载视频
- **ffmpeg** — 提取音频
- **openai-whisper** — 语音识别

> 仅使用 `--resolve-only` 验证解析时，只需要 Python + curl。

### 一键安装

```bash
# macOS（Homebrew）
brew install curl ffmpeg
pip install openai-whisper
```

没有 Homebrew，或不想装 Homebrew 时，可以用 pip 拿到一份完整的 ffmpeg 二进制：

```bash
python3 -m venv ~/.venv/wvt && source ~/.venv/wvt/bin/activate
pip install openai-whisper imageio-ffmpeg

# 把 imageio-ffmpeg 自带的 ffmpeg 接入 PATH（~/.local/bin 需已在 PATH 中）
ln -sf "$(python -c 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())')" ~/.local/bin/ffmpeg
```

这样装出来的 ffmpeg 是完整构建（含 libx264 / libmp3lame），本项目用到的 `mp4 → 16kHz 单声道 wav` 完全够用。
whisper 会连带装 PyTorch，磁盘占用约 1 GB；模型文件首次运行自动下载（base 约 145 MB，small 约 460 MB，medium 约 1.5 GB）。

### 中文输出说明

Whisper 在处理中文时**默认经常输出繁体**。脚本已默认给 Whisper 加一句普通话提示词，强制简体并改善标点；需要覆盖或关闭：

```bash
# 自定义提示词（例如带专有名词，可显著提升这些词的识别率）
python3 scripts/transcribe.py --input-file ./video.mp4 --initial-prompt "以下是普通话的句子。关键词：动力保障、离心冷水机组。"

# 关闭提示词（恢复 Whisper 原生行为，可能输出繁体）
python3 scripts/transcribe.py --input-file ./video.mp4 --initial-prompt ""

# 非中文内容
python3 scripts/transcribe.py --input-file ./video.mp4 --language English
```

## 快速开始

```bash
# 0. 配置解析方式（可选，详见文末「可选方案总览」）
#    零风险：什么都不用配，用 --input-file / --video-url / --har 三选一
#    有账号风险：本机直跑，只需要你自己的元宝登录 Cookie（建议用闲置小号）
export YUANBAO_COOKIE="<你的元宝 Web 端 Cookie>"
#    或者：指向你自己部署的解析 Worker
# export WECHAT_VIDEO_API_URL="https://<你的 worker>/api/fetch_video_profile"
# export WECHAT_VIDEO_API_TOKEN="<你设定的凭证>"

# 一行命令生成字幕和逐字稿
python3 scripts/transcribe.py "https://weixin.qq.com/sph/Ap5KZZrF3F"

# 指定模型（更高的准确率）
python3 scripts/transcribe.py "https://weixin.qq.com/sph/Ap5KZZrF3F" --model medium

# 指定输出目录
python3 scripts/transcribe.py "https://weixin.qq.com/sph/Ap5KZZrF3F" --output-dir ./subtitles

# 只测试解析是否可用（不下载、不加载 Whisper）
python3 scripts/transcribe.py "https://weixin.qq.com/sph/Ap5KZZrF3F" --resolve-only

# 零风险入口：直接给定播放地址（抓包拿到），跳过所有解析，不需要凭证
python3 scripts/transcribe.py --video-url "https://finder.video.qq.com/....mp4" --output-dir ./subtitles

# 零风险入口：从抓包文件（HAR 或纯文本 URL 列表）自动提取直链
python3 scripts/transcribe.py --har ./capture.har --output-dir ./subtitles

# 零风险入口：转写已下载到本地的视频/音频
python3 scripts/transcribe.py --input-file ./video.mp4 --output-dir ./subtitles
```

## 支持的链接格式

- `https://weixin.qq.com/sph/XXXXX`
- `https://channels.weixin.qq.com/finder-preview/pages/sph?id=XXXXX`

## Whisper 模型选择

| 模型 | 速度 | 中文准确率 | 适用场景 |
|------|------|-----------|----------|
| `tiny` | 极快 | ~85% | 快速预览 |
| `base` | 快 | ~90% | 日常转录 **(默认)** |
| `small` | 中 | ~93% | 需要更高准确率 |
| `medium` | 慢 | ~95% | 正式文稿 |

```bash
# 默认使用 base
python3 scripts/transcribe.py "<链接>"

# 精确度优先
python3 scripts/transcribe.py "<链接>" --model medium
```

实测对比（同一段中文语音，2026-10-05）：`base` 会把「语音」听成「与音」、漏掉结尾短句；`small` 把「语音」正确识别，但仍有同音字错误。**对准确率有要求就用 `small` 起步**；`base` 适合快速预览。

## 手动工作流

如果你想要更精细的控制，也可以分步执行：

```bash
# 1a. 解析链接（方案 B：本机直跑，用自己的元宝 Cookie —— 有账号风险）
curl -s -X POST "https://yuanbao.tencent.com/api/weixin/get_parse_result" \
  -H "Content-Type: application/json" \
  -H "Cookie: <你的元宝 Cookie>" \
  -d '{"type":"video_channel_url","url":"<视频号链接>","scene":1}'
# → 从 data.playable_url 的 query 里取 token / eid（没有 eid 就用 data.wx_export_id）
curl -s -X POST "https://channels.weixin.qq.com/finder-preview/api/feed/get_feed_info" \
  -H "Content-Type: application/json" \
  -H "Origin: https://channels.weixin.qq.com" \
  -d '{"baseReq":{"generalToken":"<token>"},"exportId":"<eid>"}'
# → data.feedInfo.h264VideoInfo.videoUrl 就是播放地址

# 1b. 解析链接（方案 C：你自建的 Worker —— 账号风险同方案 B）
curl -s -X POST "https://<你的 worker>/api/fetch_video_profile" \
  -H "Content-Type: application/json" \
  -H "User-Agent: Mozilla/5.0 ..." \
  -H "Authorization: Bearer <你设定的凭证>" \
  -d '{"url":"<视频号链接>"}'

# 1c. 方案 A：零凭证。从抓包文件自动提取直链，或直接指定地址/本地文件
python3 scripts/transcribe.py --har ./capture.har --output-dir ./subtitles
python3 scripts/transcribe.py --video-url "https://finder.video.qq.com/....mp4" --output-dir ./subtitles
python3 scripts/transcribe.py --input-file ./video.mp4 --output-dir ./subtitles

# 2. 下载视频
curl -L -o video.mp4 \
  -H "User-Agent: Mozilla/5.0 ... Chrome/120.0.0.0 Safari/537.36" \
  -H "Referer: https://channels.weixin.qq.com/" \
  "<video_url>"

# 3. 提取音频
ffmpeg -i video.mp4 -vn -acodec pcm_s16le -ar 16000 -ac 1 audio.wav

# 4. Whisper 转写（--initial_prompt 用于强制简体中文，可选）
whisper audio.wav --language Chinese --model base --output_format srt --output_dir . \
  --initial_prompt "以下是普通话的句子。"

# 5. 提取纯文本
awk 'NR%4==3' audio.srt > transcript.txt
```

## 输出文件

| 文件 | 说明 |
|------|------|
| `audio.srt` | 标准 SRT 字幕文件，可在 VLC、IINA 等播放器中加载 |
| `transcript.txt` | 纯文本逐字稿，方便复制粘贴和二次编辑 |

## 技术细节

- 视频下载时必须携带 `Referer: https://channels.weixin.qq.com/` 头，否则微信 CDN 会拒绝请求
- 音频提取为 16kHz 单声道 PCM WAV，这是 Whisper 的最佳输入格式
- 视频文件在临时目录处理，完成后自动清理，不占用磁盘空间

## 作为 WorkBuddy Skill 使用

本项目同时也是 [WorkBuddy](https://www.codebuddy.cn) 的 AI Skill。安装后，直接用自然语言让 AI 帮你提取视频号字幕：

```
帮我把这个视频号的字幕提取出来：https://weixin.qq.com/sph/XXXXX
```

安装方式：将 `SKILL.md` 放入 `~/.workbuddy/skills/wechat-video-transcribe/` 目录。

## 解析接口与限制（2026-10-05 实测）

本项目默认调用的第三方解析服务 `sph.litao.workers.dev` **已停止对外开放**：上游账号被封后启用了凭证校验，匿名请求返回 `HTTP 401 {"error":"unauthorized"}`，公开地址不会自行恢复。替代方案见下一节，**按风险从低到高排**。本项目不绕过、不破解任何鉴权。

### 配置

```bash
# 方案 A：零风险，不需要任何配置，用 --input-file / --video-url / --har

# 方案 B：本机直跑解析（⚠️ 使用你的元宝账号，建议用闲置小号）
export YUANBAO_COOKIE="<你的元宝 Web 端 Cookie>"

# 方案 C：自建查询 Worker 的地址与凭证（⚠️ 账号风险同方案 B）
export WECHAT_VIDEO_API_URL="https://your-worker.workers.dev/api/fetch_video_profile"
export WECHAT_VIDEO_API_TOKEN="<你在部署 Worker 时设定的凭证>"

# 可选：解析与下载走代理（curl 自身也遵循 https_proxy / ALL_PROXY）
export WECHAT_VIDEO_PROXY="http://127.0.0.1:<你的代理端口>"
```

### 常用命令

```bash
# 只验证解析，不加载 Whisper
python3 scripts/transcribe.py "https://weixin.qq.com/sph/A4waITx8sO" --resolve-only

# 零风险：从抓包文件提取直链后跑全流程
python3 scripts/transcribe.py --har ./capture.har --output-dir ./subtitles

# 零风险：直接给定播放地址，跳过所有解析
python3 scripts/transcribe.py --video-url "https://finder.video.qq.com/....mp4" --output-dir ./subtitles

# 零风险：已下载的视频/音频离线转写，完全不依赖解析服务
python3 scripts/transcribe.py --input-file /path/to/video.mp4 --output-dir ./subtitles
```

### 响应兼容

脚本同时接受两种响应结构：

| 版本 | 播放地址位置 |
|------|------|
| 旧版（扁平） | 顶层 `video_url` |
| 新版（嵌套） | `data.feedInfo.h264VideoInfo.videoUrl`、`h265VideoInfo.videoUrl` 或 `feedInfo.videoUrl` |

错误分支彼此区分：HTTP 401/403（鉴权失败，附带服务方返回的原因）、网络超时或连接失败、非 JSON 响应、其他非 2xx 状态、以及 HTTP 2xx 但缺少播放地址。**拿到标题、作者或封面不等于视频可下载。**

### 官方公共解析已停用：可选方案总览

**结论先说：上游那个公开解析服务已经封了，用不了，也不会自己恢复。** 本项目无法、也不打算通过其他方式取回公开地址的访问权。

这个 `401` 不是偶发故障，是上游**主动加的访问控制**：

- `sph.litao.workers.dev` 是上游开源项目 [`ltaoo/wx_channels_download`](https://github.com/ltaoo/wx_channels_download) 的 `sph` Cloudflare Worker 的公开部署。
- 上游作者在 [issue #495](https://github.com/ltaoo/wx_channels_download/issues/495)（2026-08-13）说明：该服务依赖的**元宝账号被封禁**，「后续会增加凭证校验功能」。
- 上游部署文档（`deploy sph`）要求注入 `ACCESS_CREDENTIAL` 作为「页面及 API 的访问凭证」，**认证失败返回 401，未配置返回 503**；支持 `Authorization: Bearer <凭证>` 与 Basic Auth `wxchannels:<凭证>`。凭证由**部署者自己设定**，第三方无从获取。

顺带说明：**这个 401 是绕不过去的**。微信官方分享页自己也是带着登录 token 去查的（`get_feed_info` 需要 `generalToken`），而且那段取流逻辑**只在微信环境内执行**（见 [关于「用浏览器抓包」](#关于用浏览器抓包为什么在普通浏览器里抓不到)）——不是换个请求头就能解决。

### 先说风险：用不用你自己的账号，是分水岭

| | 方案 | 需要什么 | 账号风险 | 能自动化吗 |
|---|---|---|---|---|
| ⭐ | A. 完全离线 | 什么都不用 | **无** | 半自动（需先拿到视频文件或直链） |
| ⚠️ | B. 本机直跑 | 你的元宝 Cookie | **有**，落在元宝账号 | 全自动 |
| ⚠️ | C. 自建 Worker | Cloudflare + 你的元宝 Cookie | **有**，同 B（且暴露面更大） | 全自动 |

**风险具体是什么，说清楚：**

1. **风险落在元宝账号上，不是你的微信/QQ。** 元宝隐私政策写的是：同一手机号注册过混元系产品则账号关联，但「**各产品可分别进行账号注销或封号等账号处置**」。所以元宝被封**不一定**牵连微信，但因为登录授权来自微信/QQ，关联风险无法完全排除——**别拿主号试**。
2. **上游为什么被封？因为它把 Cookie 放到了公开服务上，一个账号服务大量陌生人。** 触发条件是**异常流量规模**，不是"用了这个接口"本身。本机低频自用（每天几条）风险显著更低，**但不是零**。
3. **Cookie 就是登录凭证**（`hy_user`、`hy_token`），一旦泄漏等于账号被接管。所以：不要提交到仓库、不要发给任何人、不要部署成公开服务。
4. 同类项目 [`ucmao/media-parser`](https://github.com/ucmao/media-parser) 的文档给了同样的建议：`YUANBAO_COOKIE` 属于个人账号登录隐私凭证，「**强烈建议使用闲置小号**进行配置」。

**如果你决定用 B/C，建议这么做：**

- 用**闲置小号**登录元宝（不要用主号），只在小号上承担风险。
- 只在**本机低频**使用，绝不做成公开服务、绝不分享 Cookie。
- 用完可以在元宝里**退出登录**让该 Cookie 失效，需要时再重新登录复制。
- 心里有数：Cookie 约 1 个月过期，脚本会明确提示失效，重登即可。

**如果你不想承担任何账号风险**，直接看方案 A —— 它不需要任何凭证。

---

### 方案 A：完全离线零风险

不碰任何账号凭证，代价是要想办法把视频弄到本地或拿到直链。三种入口，脚本都支持：

**A1. 视频已经落到本地 → `--input-file`**

用任何合法方式拿到视频文件（微信 PC 客户端配上游 [`ltaoo/wx_channels_download`](https://github.com/ltaoo/wx_channels_download) 会出现下载按钮、手机端录屏、作者本人授权导出等），直接转写：

```bash
python3 scripts/transcribe.py --input-file ./video.mp4 --output-dir ./subtitles
```

**A2. 已经有播放地址 → `--video-url`**

```bash
python3 scripts/transcribe.py --video-url "https://finder.video.qq.com/....mp4" --output-dir ./subtitles
```

**A3. 有抓包文件 → `--har`（自动提取直链）**

用 Charles / mitmproxy / Proxifier 之类的代理工具抓包，导出 HAR（或直接把抓到的 URL 列表存成文本），交给脚本自动挑出视频地址：

```bash
python3 scripts/transcribe.py --har ./capture.har --output-dir ./subtitles
```

脚本会给候选地址打分（`video.qq.com` 域名、`video/*` MIME、`.mp4` 后缀），列出候选再选用；**如果只有分片流（`.m4s` / `.ts`）或出现多个同权重候选，它会拒绝乱猜并让你手动用 `--video-url` 指定**，不会静默挑一个错的。

**别试 yt-dlp**：官方 yt-dlp **没有**视频号提取器，`yt-dlp <分享链接>` 走不通。

### 关于「用浏览器抓包」：为什么在普通浏览器里抓不到

网上有些教程说"把链接发给元宝网页版 → 点卡片 → 浏览器播放 → 用插件嗅探地址"。**这条在普通浏览器里走不通**，我们从官方分享页的 JS 里确认了原因：

```js
const ti = Ba(), { noRedirect: ai } = xe();
if (ti === Ma.WECHAT && !ai) {          // ← 只有微信环境才进这个分支
  const n = se().token || Xa("token") || "";
  return o ? (await Ka.getFeedInfo({ baseReq: { generalToken: n }, ... })).data.sceneInfo : void 0
}
```

- 取播放数据的代码**被包在 `ti === Ma.WECHAT` 判断里**，即只有微信内置环境（存在 `WeixinJSBridge`）才会执行；普通浏览器走的是「跳转/提示去微信打开」的分支。
- 拿到页面 HTML 也没用：分享页是约 2.6 KB 的空壳 SPA，数据全靠 JS 拉。
- 所以**想抓包，得在微信客户端那个环境里抓**（微信 PC 客户端 + 代理工具最顺手），抓到的结果用 `--har` 或 `--video-url` 交给脚本。

---

### 方案 B：本机直跑解析

> ⚠️ **这一节会用到你的元宝账号。动手前请先读 [先说风险](#先说风险用不用你自己的账号是分水岭)，并且按那里的建议用闲置小号。**

上游 Worker 的核心其实就是三个 HTTP 请求，**不需要 Cloudflare，在本机直接跑就行**，只要你有自己的元宝登录 Cookie：

| 步骤 | 请求 |
|------|------|
| ① | `POST https://yuanbao.tencent.com/api/weixin/get_parse_result`，body `{"type":"video_channel_url","url":"<分享链接>","scene":1}`，带 `Cookie: <你的元宝 Cookie>` |
| ② | 从返回的 `data.playable_url` 里取出 `token`（→ generalToken）与 `eid`（→ exportId）；没有 `eid` 时回退 `data.wx_export_id` |
| ③ | `POST https://channels.weixin.qq.com/finder-preview/api/feed/get_feed_info`，body `{"baseReq":{"generalToken":"<token>"},"exportId":"<eid>"}` → `data.feedInfo.h264VideoInfo.videoUrl` |

脚本已内置这条链路，设一个环境变量即可：

```bash
# 浏览器打开 https://yuanbao.tencent.com/ 登录，F12 → Network → 复制请求头里完整的 Cookie 值
export YUANBAO_COOKIE="<你的元宝 Cookie>"

python3 scripts/transcribe.py "https://weixin.qq.com/sph/AOVsoW8dBI" --resolve-only   # 先验证解析
python3 scripts/transcribe.py "https://weixin.qq.com/sph/AOVsoW8dBI"                  # 再跑全流程
```

设了 `YUANBAO_COOKIE` 后脚本自动走本机链路，不再访问 `WECHAT_VIDEO_API_URL`。Cookie 通过标准输入传给 curl，不会出现在命令行、进程列表或日志里。

> ⚠️ 三点提醒：Cookie 约 1 个月过期，过期后重新复制即可（脚本会明确提示 Cookie 失效）；上游那个公开服务正是因为元宝账号被封才停的，**用它意味着你的元宝账号承担同样的风险**；所以**请用闲置小号**，不要用主号。

---

### 方案 C：自建 Cloudflare 查询 Worker

比方案 B 多一层部署，好处是不依赖本机 Cookie 文件、可以给其他设备共用。**注意：账号风险与方案 B 完全相同**，而且一旦你把这个 Worker 的地址和凭证分享给别人，就复现了上游被封的那个场景（一个账号服务大量陌生人）。

前提：一个 Cloudflare 账号 + 登录元宝后取到的 Web cookie。

1. 安装上游 CLI（见 [`ltaoo/wx_channels_download`](https://github.com/ltaoo/wx_channels_download) 文档）。
2. 配置里填这几项：

   | 配置项 | 说明 |
   |--------|------|
   | `cloudflare.accountId` | Cloudflare 账号 ID |
   | `cloudflare.apiToken` | 具备 Workers 读写权限的 API Token |
   | `cloudflare.sphWorkerName` | 自定义 Worker 名称 |
   | `cloudflare.sphCookie` | 登录元宝后的 Web 端 cookie（约 1 个月过期） |
   | `cloudflare.sphCredential` | **你自己设定的**访问凭证 |

3. 部署：

   ```bash
   wx_video_download deploy sph
   ```

4. 把本项目指过去：

   ```bash
   export WECHAT_VIDEO_API_URL="https://<sphWorkerName>.<subdomain>.workers.dev/api/fetch_video_profile"
   export WECHAT_VIDEO_API_TOKEN="<你设定的 sphCredential>"
   python3 scripts/transcribe.py "https://weixin.qq.com/sph/AOVsoW8dBI" --resolve-only
   ```

   能打印出标题/作者就说明通了，去掉 `--resolve-only` 即可跑完整流程。

> ⚠️ 上游明确提示：**仅自己使用，不要对外提供**。公开地址一旦传播开，就等于重现上游被封的那个场景。

---

### 实测结论

| 检查项 | 结果 |
|--------|------|
| 直连 `sph.litao.workers.dev` | 连接超时，需经代理 |
| 经本机 HTTP 代理访问 | `HTTP 401 {"error":"unauthorized"}` |
| 公开部署是否还会恢复 | **不会**：上游元宝账号被封后已加凭证校验，凭证由部署者自设，第三方拿不到（上游 issue #495 + 部署文档） |
| 微信短链信息接口 `get_feed_info` | 匿名请求（无 `generalToken`）一律 `HTTP 401 permission verification failed`，拿不到任何数据 |
| 微信官方分享页自身 | 取流逻辑被 `ti === Ma.WECHAT` 包住（读自官方 `feed.*.js`），**只有微信环境才执行**；普通浏览器抓不到播放地址 |
| 元宝 `get_parse_result` | 域名国内直连可用（约 0.15 s）；匿名调用返回 `HTTP 401`，需要登录态 |
| 本机直跑链路（方案 B） | 代码已内置，19 项 mock 场景测试通过（含 token/eid 提取、Cookie 失效提示、Cookie 不泄漏、微信拒绝回显、多来源互斥）；**真机链路未验证**（测试环境无元宝 Cookie） |
| `--har`（方案 A3） | 12 项场景测试通过：分片中挑出完整 mp4、仅分片时拒绝并提示、多候选时拒绝乱选、纯文本 URL 列表、端到端产出 SRT+逐字稿且不访问任何解析接口 |
| `--video-url` / `--input-file`（方案 A） | 端到端通过（桩 ffmpeg/whisper） |
| **下载 → 提取音频 → Whisper 转写（真机）** | **已验证通过**（2026-10-05，macOS arm64）：ffmpeg 7.1 完整构建 + openai-whisper 20250625（torch 2.14.1），用本机 TTS 生成的 9 秒中文语音 mp4 跑完整流程，正常产出 `audio.srt` 与 `transcript.txt` |
| 中文输出简繁 | Whisper 原生输出**繁体**；脚本默认加普通话提示词后输出简体（`--initial-prompt ""` 可关闭，实测两种行为均符合预期） |
| 完整下载 + 转写（方案 B/C） | **真机未验证**：缺元宝 Cookie / 自建 Worker 凭证。转写后半段（ffmpeg + Whisper）已验证，未验证的只剩「拿到播放地址」这一步 |

结论：**官方公共解析已停用，这是服务方的设计而非脚本故障，且绕不过去**。方案 A（`--input-file` / `--video-url` / `--har`）完全不需要任何账号凭证，零风险；方案 B/C 只需要你自己的元宝 Cookie，代价是**你自己的元宝账号承担封号风险**——这也是上游那个服务倒掉的原因。

## License

MIT
