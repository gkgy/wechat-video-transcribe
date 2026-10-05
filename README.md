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
> 想继续解析链接，有三条路，**按省事程度排序**：
>
> 1. **本机直跑解析**（最省事，不用部署任何服务）——设好 `YUANBAO_COOKIE` 即可，见 [方案一](#方案一本机直跑解析最省事)。
> 2. **自己部署一个查询 Worker**——见 [方案二](#方案二自建-cloudflare-查询-worker)。
> 3. **绕开解析**——自己拿到播放地址用 `--video-url`，或把视频落到本地用 `--input-file`，见 [方案三](#方案三完全绕开解析)。
>
> 本仓库**不绕过、不破解任何鉴权**，所有方案都使用你自己的账号凭证。

---

## 功能

一条命令完成微信视频号视频的全自动语音转文字流水线：

1. 解析微信视频号分享链接，获取真实视频地址（**公共接口已停用**，用你自己的元宝 Cookie 本机直跑，或自建 Worker，见文末）
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
# macOS
brew install curl ffmpeg

# 安装 Whisper
pip install openai-whisper
```

## 快速开始

```bash
# 0. 配置解析方式（三选一，详见文末「三条替代方案」）
#    最省事：本机直跑，只需要你自己的元宝登录 Cookie
export YUANBAO_COOKIE="<你的元宝 Web 端 Cookie>"
#    或者：指向你自己部署的解析 Worker
# export WECHAT_VIDEO_API_URL="https://<你的 worker>/api/fetch_video_profile"
# export WECHAT_VIDEO_API_TOKEN="<你设定的凭证>"
#    都不配也能用：--video-url 直链 / --input-file 本地文件，不需要任何凭证

# 一行命令生成字幕和逐字稿
python3 scripts/transcribe.py "https://weixin.qq.com/sph/Ap5KZZrF3F"

# 指定模型（更高的准确率）
python3 scripts/transcribe.py "https://weixin.qq.com/sph/Ap5KZZrF3F" --model medium

# 指定输出目录
python3 scripts/transcribe.py "https://weixin.qq.com/sph/Ap5KZZrF3F" --output-dir ./subtitles

# 只测试解析是否可用（不下载、不加载 Whisper）
python3 scripts/transcribe.py "https://weixin.qq.com/sph/Ap5KZZrF3F" --resolve-only

# 直接给定播放地址（自己抓包/开发者工具拿到），跳过所有解析，不需要凭证
python3 scripts/transcribe.py --video-url "https://finder.video.qq.com/....mp4" --output-dir ./subtitles

# 转写已下载到本地的视频，不依赖解析服务
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

## 手动工作流

如果你想要更精细的控制，也可以分步执行：

```bash
# 1a. 解析链接（方案一：本机直跑，用自己的元宝 Cookie）
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

# 1b. 解析链接（方案二：你自建的 Worker）
curl -s -X POST "https://<你的 worker>/api/fetch_video_profile" \
  -H "Content-Type: application/json" \
  -H "User-Agent: Mozilla/5.0 ..." \
  -H "Authorization: Bearer <你设定的凭证>" \
  -d '{"url":"<视频号链接>"}'

# 1c. 方案三：自己抓包拿到直链，跳过解析

# 2. 下载视频
curl -L -o video.mp4 \
  -H "User-Agent: Mozilla/5.0 ... Chrome/120.0.0.0 Safari/537.36" \
  -H "Referer: https://channels.weixin.qq.com/" \
  "<video_url>"

# 3. 提取音频
ffmpeg -i video.mp4 -vn -acodec pcm_s16le -ar 16000 -ac 1 audio.wav

# 4. Whisper 转写
whisper audio.wav --language Chinese --model base --output_format srt --output_dir .

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

本项目默认调用的第三方解析服务 `sph.litao.workers.dev` **已停止对外开放**：上游账号被封后启用了凭证校验，匿名请求返回 `HTTP 401 {"error":"unauthorized"}`，公开地址不会自行恢复。替代方案见下一节（共三种）。本项目不绕过、不破解任何鉴权。

### 配置

```bash
# 方案一：本机直跑解析（推荐，不需要任何自建服务）
export YUANBAO_COOKIE="<你的元宝 Web 端 Cookie>"

# 方案二：自建查询 Worker 的地址与凭证
export WECHAT_VIDEO_API_URL="https://your-worker.workers.dev/api/fetch_video_profile"
export WECHAT_VIDEO_API_TOKEN="<你在部署 Worker 时设定的凭证>"

# 可选：解析与下载走代理（curl 自身也遵循 https_proxy / ALL_PROXY）
export WECHAT_VIDEO_PROXY="http://127.0.0.1:<你的代理端口>"
```

### 常用命令

```bash
# 只验证解析，不加载 Whisper
python3 scripts/transcribe.py "https://weixin.qq.com/sph/A4waITx8sO" --resolve-only

# 直接给定播放地址（自己抓包拿到），跳过所有解析
python3 scripts/transcribe.py --video-url "https://finder.video.qq.com/....mp4" --output-dir ./subtitles

# 已下载的视频/音频离线转写，完全不依赖解析服务
python3 scripts/transcribe.py --input-file /path/to/video.mp4 --output-dir ./subtitles
```

### 响应兼容

脚本同时接受两种响应结构：

| 版本 | 播放地址位置 |
|------|------|
| 旧版（扁平） | 顶层 `video_url` |
| 新版（嵌套） | `data.feedInfo.h264VideoInfo.videoUrl`、`h265VideoInfo.videoUrl` 或 `feedInfo.videoUrl` |

错误分支彼此区分：HTTP 401/403（鉴权失败，附带服务方返回的原因）、网络超时或连接失败、非 JSON 响应、其他非 2xx 状态、以及 HTTP 2xx 但缺少播放地址。**拿到标题、作者或封面不等于视频可下载。**

### 官方公共解析已停用：三条替代方案

**结论先说：上游那个公开解析服务已经封了，用不了，也不会自己恢复。** 下面三条路按省事程度排序，第一条最省事。本项目无法、也不打算通过其他方式取回公开地址的访问权。

这个 `401` 不是偶发故障，是上游**主动加的访问控制**：

- `sph.litao.workers.dev` 是上游开源项目 [`ltaoo/wx_channels_download`](https://github.com/ltaoo/wx_channels_download) 的 `sph` Cloudflare Worker 的公开部署。
- 上游作者在 [issue #495](https://github.com/ltaoo/wx_channels_download/issues/495)（2026-08-13）说明：该服务依赖的**元宝账号被封禁**，「后续会增加凭证校验功能」。
- 上游部署文档（`deploy sph`）要求注入 `ACCESS_CREDENTIAL` 作为「页面及 API 的访问凭证」，**认证失败返回 401，未配置返回 503**；支持 `Authorization: Bearer <凭证>` 与 Basic Auth `wxchannels:<凭证>`。凭证由**部署者自己设定**，第三方无从获取。

顺带说明：**这个 401 是绕不过去的**。微信官方分享页自己也是带着登录 token 去查的（`get_feed_info` 需要 `generalToken`），外部浏览器裸访问同样拿不到播放地址——不是换个请求头就能解决。

---

### 方案一：本机直跑解析（最省事）

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

> ⚠️ 两点提醒：Cookie 约 1 个月过期，过期后重新复制即可（脚本会明确提示 Cookie 失效）；上游那个公开服务正是因为元宝账号被封才停的，**用它意味着你的元宝账号承担同样的风险**，请自行判断并遵守服务条款。

---

### 方案二：自建 Cloudflare 查询 Worker

比方案一多一层部署，好处是不依赖本机 Cookie 文件、可以给其他设备共用。

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

> ⚠️ 上游明确提示：**仅自己使用，不要对外提供**。

---

### 方案三：完全绕开解析

不需要任何凭证和账号，代价是要手动拿到直链或视频文件。

**3a. 已经有播放地址 → `--video-url`**

从抓包 / 开发者工具 / 浏览器 Network 里拿到 `finder.video.qq.com` 的 `.mp4` 地址，直接交给脚本：

```bash
python3 scripts/transcribe.py --video-url "https://finder.video.qq.com/....mp4" --output-dir ./subtitles
```

**3b. 视频已经落到本地 → `--input-file`**

用 [`ltaoo/wx_channels_download`](https://github.com/ltaoo/wx_channels_download) 的上游客户端（微信 PC 端视频号页面会出现下载按钮），或其它抓包工具把视频存下来：

```bash
python3 scripts/transcribe.py --input-file ./video.mp4 --output-dir ./subtitles
```

**别试 yt-dlp**：官方 yt-dlp **没有**视频号提取器——播放地址只在微信 App 内通过 `WeixinJSBridge` 下发，网页不暴露，所以 `yt-dlp <分享链接>` 走不通。

### 实测结论

| 检查项 | 结果 |
|--------|------|
| 直连 `sph.litao.workers.dev` | 连接超时，需经代理 |
| 经本机 HTTP 代理访问 | `HTTP 401 {"error":"unauthorized"}` |
| 公开部署是否还会恢复 | **不会**：上游元宝账号被封后已加凭证校验，凭证由部署者自设，第三方拿不到（上游 issue #495 + 部署文档） |
| 微信短链信息接口 `get_feed_info` | 匿名请求（无 `generalToken`）一律 `HTTP 401 permission verification failed`，拿不到任何数据 |
| 微信官方分享页自身 | 也是带登录 token 去查（JS 里 `getFeedInfo({baseReq:{generalToken: token}})`），外部浏览器裸访问同样无播放地址 |
| 元宝 `get_parse_result` | 域名国内直连可用（约 0.15 s）；匿名调用返回 `HTTP 401 {"error":{"code":"20000"}}`，需要登录态 |
| 本机直跑链路（方案一） | 代码已内置，18 项 mock 场景测试通过（含 token/eid 提取、Cookie 失效提示、Cookie 不泄漏、微信拒绝回显）；**真机链路未验证**（测试环境无元宝 Cookie） |
| `--video-url` / `--input-file`（方案三） | 端到端通过（桩 ffmpeg/whisper） |
| 完整下载 + 转写 | 方案一/二的**真机全链路均未验证**（缺凭证），测试机也未安装 `ffmpeg` / `whisper` |

结论：**官方公共解析已停用，这是服务方的设计而非脚本故障，且绕不过去**。三条替代路径都已写清，脚本对三种输入方式都支持；`--video-url` 与 `--input-file` 完全不需要任何凭证，本机直跑链路只需要你自己的元宝 Cookie。

## License

MIT
