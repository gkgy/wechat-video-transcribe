---
name: wechat-video-transcribe
description: 微信视频号视频下载 + 语音转文字（Whisper）。提取微信视频号（Channels）视频并生成 SRT 字幕和纯文本转录。公共解析接口已停用：**优先用零风险路径**（--input-file / --video-url / --har，都不需要账号凭证）；其次才是用用户自己的元宝 Cookie 本机直跑或自建 Worker（有元宝账号封号风险，务必先告知）。触发词：微信视频号、视频字幕提取、语音转文字、Whisper转写、提取视频中的文字、视频转逐字稿。
---

# 微信视频号下载 + Whisper 转写

## 概述

完整的微信视频号视频字幕提取流水线：解析分享链接 → 下载视频 → 提取音频 → Whisper 语音转文字 → 输出 SRT 字幕文件 + 纯文本逐字稿。

## 依赖

执行前确认以下工具可用：
- `curl` — 调用解析接口并下载视频
- `ffmpeg` — 提取音频
- `whisper` CLI — 语音识别（`pip install openai-whisper` 后自动安装）

## 前提：默认公共解析接口已停用，按**风险从低到高**选路径

**默认调用的公共解析服务 `sph.litao.workers.dev` 已经不能用了。** 该地址属于上游项目 [`ltaoo/wx_channels_download`](https://github.com/ltaoo/wx_channels_download)，其依赖的元宝账号被封停后，作者给 Worker 加了凭证校验，匿名请求一律返回 `HTTP 401 {"error":"unauthorized"}`。凭证由部署者自己设定，第三方拿不到，**公开地址不会自行恢复，这个 401 也绕不过去**。

### 先判断要不要动用户的账号（决定走哪条路）

有两条路**完全不碰账号凭证，零风险，应当优先推荐**；另有两条要用用户的元宝账号，**有封号风险**。

**零风险（优先推荐）**

1. `--input-file <本地视频>` — 视频已在本机（用户自己录屏/下载/授权导出）
2. `--video-url <直链>` — 用户已有 `finder.video.qq.com` 的播放地址
3. `--har <抓包文件>` — 用户用代理工具（Charles / mitmproxy 等）抓到 HAR 或 URL 列表，脚本自动挑出直链

**有账号风险（必须先讲风险再动手）**

4. 本机直跑：`YUANBAO_COOKIE` + 无自建服务
   ```bash
   export YUANBAO_COOKIE="<元宝 Web 端 Cookie>"
   python3 scripts/transcribe.py "<分享链接>" --resolve-only   # 先验证
   ```
   链路：元宝 `get_parse_result` → 取 `data.wx_export_id` 与 `data.playable_url` 里的 `token`/`eid` → 微信 `get_feed_info`（`{baseReq:{generalToken}, exportId}`）→ `feedInfo.h264VideoInfo.videoUrl`。
5. 自建 Worker：用户按上游 `wx_video_download deploy sph` 部署，填 `cloudflare.accountId` / `apiToken` / `sphWorkerName` / `sphCookie` / `sphCredential`，再把 `WECHAT_VIDEO_API_URL` + `WECHAT_VIDEO_API_TOKEN` 指过去。

### 账号风险必须如实讲清（用户会问）

- **风险落在元宝账号，不是微信/QQ。** 元宝隐私政策：同一手机号注册过混元系产品则账号关联，但「各产品可分别进行账号注销或封号等账号处置」。所以元宝被封不必然牵连微信，但登录授权来自微信/QQ，关联风险无法排除。
- **上游为什么被封？** 它把 Cookie 放在公开服务上，一个账号服务大量陌生人。触发条件是**异常流量规模**，不是"用了这个接口"本身；本机低频自用风险更低，**但不是零**。
- **Cookie 就是登录凭证**（`hy_user`、`hy_token`），泄漏等于账号被接管。
- 同类项目 [`ucmao/media-parser`](https://github.com/ucmao/media-parser) 的建议是「**强烈建议使用闲置小号进行配置**」。
- 因此涉及路径 4/5 时，**建议用户用小号、只本机低频用、绝不分享 Cookie、绝不做成公开服务**。用户如果表示不想承担风险，就直接改推零风险路径。

其它约定：

- **不要尝试绕过鉴权**（改请求头、伪造 token、伪造微信环境、抓别人的凭证都不行）。
- 不要建议用 yt-dlp：官方 yt-dlp 没有视频号提取器。
- **不要建议"用普通浏览器打开分享页抓包"**：官方分享页的取流逻辑被 `ti === Ma.WECHAT` 包住，只在微信环境（有 `WeixinJSBridge`）执行，普通浏览器进不去那个分支。要抓包得在微信客户端环境里抓。
- 需要代理时设置 `WECHAT_VIDEO_PROXY`（curl 本身也遵循 `https_proxy` / `ALL_PROXY`）。
- 拿到标题、作者或封面**不代表**视频可下载，务必确认响应里有播放地址。

## 工作流

### Step 1：拿到视频（四条路，按风险排序）

> 默认地址 `sph.litao.workers.dev` 已停用（401）。**优先走零风险的 1a**；只有用户明确接受元宝账号风险时才用 1b。

**1a. 零风险（不需要任何凭证）**

```bash
# 视频已在本机
python3 scripts/transcribe.py --input-file ./video.mp4 --output-dir ./subtitles

# 已经从抓包文件拿到直链（HAR 或纯文本 URL 列表，脚本自动挑选并列出候选）
python3 scripts/transcribe.py --har ./capture.har --output-dir ./subtitles

# 手上直接就有播放地址
python3 scripts/transcribe.py --video-url "https://finder.video.qq.com/....mp4" --output-dir ./subtitles
```

**1b. 本机直跑解析（⚠️ 会使用用户的元宝账号）**

脚本设了 `YUANBAO_COOKIE` 会自动走元宝 → 微信两步链路，不用手工发请求。下面是手动等价命令。

```bash
# 第一步：元宝解析，拿 data.wx_export_id 与 data.playable_url
curl -s -X POST "https://yuanbao.tencent.com/api/weixin/get_parse_result" \
  -H "Content-Type: application/json" \
  -H "Cookie: <用户的元宝 Cookie>" \
  -d '{"type":"video_channel_url","url":"<微信视频号分享链接>","scene":1}'

# 第二步：从 playable_url 的 query 取 token / eid（没有 eid 就用 wx_export_id）
curl -s -X POST "https://channels.weixin.qq.com/finder-preview/api/feed/get_feed_info" \
  -H "Content-Type: application/json" \
  -H "Origin: https://channels.weixin.qq.com" \
  -d '{"baseReq":{"generalToken":"<token>"},"exportId":"<eid>"}'
# → data.feedInfo.h264VideoInfo.videoUrl
```

**1c. 用户自建的 Worker**

```bash
curl -s -X POST "https://<用户的 worker>/api/fetch_video_profile" \
  -H "Content-Type: application/json" \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" \
  -H "Authorization: Bearer <WECHAT_VIDEO_API_TOKEN>" \
  -d '{"url": "<微信视频号分享链接>"}'
```

播放地址字段随服务版本变化，需同时兼容：

- 旧版（扁平）：顶层 `video_url`
- 新版（嵌套）：`data.feedInfo.h264VideoInfo.videoUrl` / `h265VideoInfo.videoUrl` / `feedInfo.videoUrl`

常见分享链接格式：
- `https://weixin.qq.com/sph/XXXXX`
- `https://channels.weixin.qq.com/finder-preview/pages/sph?id=XXXXX`

### Step 2：下载视频

```bash
curl -L -o video.mp4 \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" \
  -H "Referer: https://channels.weixin.qq.com/" \
  "<video_url>"
```

**重要**：必须带 `Referer` 和 `User-Agent` 头，否则 CDN 会拒绝请求。

### Step 3：提取音频（16kHz 单声道 WAV）

```bash
ffmpeg -i video.mp4 -vn -acodec pcm_s16le -ar 16000 -ac 1 audio.wav
```

### Step 4：Whisper 转写

```bash
whisper audio.wav --language Chinese --model base --output_format srt --output_dir .
```

模型选择（准确率与速度权衡）：

| 模型 | 速度 | 中文准确率 | 适用场景 |
|------|------|-----------|----------|
| `tiny` | 极快 | ~85% | 快速预览 |
| `base` | 快 | ~90% | 日常转录 |
| `small` | 中 | ~93% | 需要更高准确率 |
| `medium` | 慢 | ~95% | 正式文稿 |

默认使用 `base`。对质量要求高时升级到 `small` 或 `medium`。

### Step 5：生成纯文本逐字稿

```bash
awk 'NR%4==3' audio.srt > transcript.txt
```

## 输出

- `audio.srt` — 带时间轴的字幕文件，可在任意视频播放器中加载
- `transcript.txt` — 纯文本逐字稿（基于 SRT 提取）

## 快捷脚本

也可以直接用捆绑的 Python 脚本一键完成全流程：

```bash
# 全流程：解析 → 下载 → 提取音频 → Whisper 转写
python3 scripts/transcribe.py <微信视频号链接> [--model base|small|medium] [--output-dir ./]

# 只验证解析是否可用，不下载也不加载 Whisper
python3 scripts/transcribe.py <微信视频号链接> --resolve-only

# 零风险：从抓包文件（HAR 或纯文本 URL 列表）提取直链后跑全流程
python3 scripts/transcribe.py --har ./capture.har --output-dir ./subtitles

# 零风险：直接给定播放地址，跳过所有解析
python3 scripts/transcribe.py --video-url "https://finder.video.qq.com/....mp4" --output-dir ./subtitles

# 零风险：转写已下载到本地的视频/音频
python3 scripts/transcribe.py --input-file ./video.mp4 --output-dir ./subtitles

# 本机直跑解析（需要用户自己的元宝 Cookie，⚠️ 有账号风险）
export YUANBAO_COOKIE="<元宝 Web 端 Cookie>"

# 解析与下载走代理
export WECHAT_VIDEO_PROXY="http://127.0.0.1:<你的代理端口>"
```

`链接 / --input-file / --video-url / --har` 四选一，同时给多个会被拒绝。解析优先级：设了 `YUANBAO_COOKIE` 走本机链路，否则走 `WECHAT_VIDEO_API_URL`。

`--har` 会给候选地址打分（`video.qq.com` 域名、`video/*` MIME、`.mp4` 后缀）并**列出候选**；只有分片流（`.m4s` / `.ts`）或出现多个同权重候选时，它会**拒绝乱猜**并让用户改用 `--video-url` 指定。

脚本会区分并明确报出：HTTP 401/403（鉴权）、网络超时/连接失败、非 JSON 响应、其他非 2xx 状态、以及 2xx 但缺少播放地址；本机链路还会单独提示「元宝 Cookie 失效」和「微信拒绝（回显 `permission verification failed` 等原因）」。凭证与 Cookie 一律经标准输入传给 curl，不会出现在命令行、进程列表或日志里。下载失败（链接过期等）通过 `curl --fail` 直接报错，不会把错误页存成视频文件；即使 curl 返回 0，脚本也会检查落盘文件是否为空。

## 已知限制（2026-10-05 实测）

- 匿名调用 `sph.litao.workers.dev` 返回 `HTTP 401`，本机直连该域名还会超时，需要代理。
- **官方公共解析已经封了，不是脚本故障**：该项目依赖的元宝账号被封，作者在 [issue #495](https://github.com/ltaoo/wx_channels_download/issues/495)（2026-08-13）宣布「后续会增加凭证校验」，其 `deploy sph` 文档要求注入 `ACCESS_CREDENTIAL` 作为访问凭证（认证失败 401 / 未配置 503）。凭证由部署者自己设定，第三方拿不到，公开地址不会恢复。
- 微信 `get_feed_info` 无 `generalToken` 时返回 `HTTP 401 permission verification failed`。
- **普通浏览器抓不到播放地址**：官方分享页 JS 里取流那段被 `ti === Ma.WECHAT` 包住，只在微信环境（存在 `WeixinJSBridge`）执行；分享页 HTML 只是约 2.6 KB 的空壳 SPA。要抓包得在微信客户端环境里抓，然后走 `--har` / `--video-url`。
- 元宝 `get_parse_result` 国内直连可用（约 0.15 s），匿名调用返回 `HTTP 401`。
- 官方 yt-dlp **没有**视频号提取器，不要建议这条路径。
- 测试覆盖：响应与错误场景 14/14、端到端 3/3、本机直跑链路 19/19、`--har` 12/12（均为 mock/桩测试）。**本机直跑与自建 Worker 的「真机全链路」未验证**（测试环境没有元宝 Cookie，也没装 `ffmpeg`/`whisper`）。对外说明时必须如实标注这一点。

## 解析不可用时怎么办

按「前提」里的顺序走，**先零风险、后动账号**，且**不要尝试绕过鉴权**（改请求头、伪造 token、伪造微信环境、拿别人的凭证都不行）：

1. **零风险** → 让用户把视频弄到本地用 `--input-file`，或抓包后用 `--har` / `--video-url`。这条路不需要任何凭证。
2. **要全自动、且用户接受风险** → 用户用小号从浏览器（已登录元宝）F12 复制 Cookie，设 `YUANBAO_COOKIE`，先 `--resolve-only` 验证；提醒用小号、别分享、别做成公开服务。
3. **想要多设备共用** → 自建 Worker（`wx_video_download deploy sph`），配置项同上；账号风险与第 2 条相同，且一旦分享地址给别人就复现了上游被封的场景。

无论走哪条，Cookie 约 1 个月过期、元宝账号有被限制的风险，都要如实告知用户。
