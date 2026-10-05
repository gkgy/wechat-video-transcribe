# 微信视频号下载 + Whisper 语音转文字

> 一键提取微信视频号视频并生成 SRT 字幕 + 纯文本逐字稿

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)

> [!IMPORTANT]
> ### 默认的公共解析接口已经不能用了，需要的人请自己建查询 Worker
>
> 本项目默认调用的公共解析地址 `sph.litao.workers.dev` 属于上游开源项目 [`ltaoo/wx_channels_download`](https://github.com/ltaoo/wx_channels_download)。该服务依赖的元宝账号**已被封停**，作者已给 `sph` Worker 加上访问凭证校验——现在匿名请求一律返回 `HTTP 401 {"error":"unauthorized"}`。
>
> **凭证由部署者自己设定，第三方拿不到，所以这个公开地址不会自己恢复，等也没用。**
>
> 想继续解析链接，**只有一条路：自己部署一个属于你自己的查询 Worker** → 见 [官方公共解析已停用：自建自己的查询 Worker](#官方公共解析已停用自建自己的查询-worker)。
>
> 不想自建？用上游客户端把视频下载到本地，再用 `--input-file` 离线转写，同样能出字幕，且不需要任何凭证。
>
> 本仓库**不绕过、不破解任何鉴权**。

---

## 功能

一条命令完成微信视频号视频的全自动语音转文字流水线：

1. 解析微信视频号分享链接，获取真实视频地址（**公共接口已停用，需自建查询 Worker，见文末说明**）
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
# 0. 配置解析接口（公共接口已停用，需自建查询 Worker；无凭证则只能转写本地文件）
export WECHAT_VIDEO_API_URL="https://<你的 worker>/api/fetch_video_profile"
export WECHAT_VIDEO_API_TOKEN="<你设定的凭证>"

# 一行命令生成字幕和逐字稿
python3 scripts/transcribe.py "https://weixin.qq.com/sph/Ap5KZZrF3F"

# 指定模型（更高的准确率）
python3 scripts/transcribe.py "https://weixin.qq.com/sph/Ap5KZZrF3F" --model medium

# 指定输出目录
python3 scripts/transcribe.py "https://weixin.qq.com/sph/Ap5KZZrF3F" --output-dir ./subtitles

# 只测试解析是否可用（不下载、不加载 Whisper）
python3 scripts/transcribe.py "https://weixin.qq.com/sph/Ap5KZZrF3F" --resolve-only

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
# 1. 解析链接获取真实视频 URL（公共接口已停用，需换成你自建 Worker 的地址）
curl -s -X POST "https://<你的 worker>/api/fetch_video_profile" \
  -H "Content-Type: application/json" \
  -H "User-Agent: Mozilla/5.0 ..." \
  -H "Authorization: Bearer <你设定的凭证>" \
  -d '{"url": "<视频号链接>"}'

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

本项目默认调用的第三方解析服务 `sph.litao.workers.dev` **已停止对外开放**：上游账号被封后启用了凭证校验，匿名请求返回 `HTTP 401 {"error":"unauthorized"}`，公开地址不会自行恢复。因此**链接解析必须指向你自己部署的查询 Worker**（见下一节）；没有 Worker 就只使用 `--input-file` 转写已下载的本地文件。本项目不绕过、不破解任何鉴权。

### 配置

```bash
# 自建查询 Worker 的地址（默认值已不可用，必须替换）
export WECHAT_VIDEO_API_URL="https://your-worker.workers.dev/api/fetch_video_profile"

# 你自己在部署 Worker 时设定的访问凭证；脚本以 Authorization: Bearer 发送，不写文件、不打印到日志
export WECHAT_VIDEO_API_TOKEN="<你的凭证>"

# 可选：解析与下载走代理（curl 自身也遵循 https_proxy / ALL_PROXY）
export WECHAT_VIDEO_PROXY="http://127.0.0.1:<你的代理端口>"
```

### 常用命令

```bash
# 只验证解析，不加载 Whisper
python3 scripts/transcribe.py "https://weixin.qq.com/sph/A4waITx8sO" --resolve-only

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

### 官方公共解析已停用：自建自己的查询 Worker

**结论先说：官方（上游公开部署）的那个解析服务已经封了，用不了；谁需要解析链接，谁就得自己建一个查询 Worker。** 本项目无法、也不打算通过其他方式取回公开地址的访问权。

#### 为什么封了

`sph.litao.workers.dev` 是上游开源项目 [`ltaoo/wx_channels_download`](https://github.com/ltaoo/wx_channels_download) 的 `sph` Cloudflare Worker 的公开部署。这个 `401` 不是偶发故障，而是上游**主动加的访问控制**：

- 上游作者在 [issue #495](https://github.com/ltaoo/wx_channels_download/issues/495)（2026-08-13）说明：该服务依赖的**元宝账号被封禁**，「后续会增加凭证校验功能」。
- 上游部署文档（`deploy sph`）要求注入 `ACCESS_CREDENTIAL` 环境变量作为「页面及 API 的访问凭证」，**认证失败返回 401，未配置返回 503**；支持 `Authorization: Bearer <凭证>` 与 Basic Auth `wxchannels:<凭证>` 两种方式。
- 凭证由**部署者自己设定**，第三方无从获取。所以这个公开地址不会自己恢复。

#### 自己建一个（唯一可自动化的路径）

前提：一个 Cloudflare 账号，以及登录 [yuanbao.tencent.com](https://yuanbao.tencent.com/) 后取到的 Web cookie。

1. 安装上游 CLI（见 [`ltaoo/wx_channels_download`](https://github.com/ltaoo/wx_channels_download) 的文档）。
2. 在配置里填这几项：

   | 配置项 | 说明 |
   |--------|------|
   | `cloudflare.accountId` | Cloudflare 账号 ID |
   | `cloudflare.apiToken` | 具备 Workers 读写权限的 API Token |
   | `cloudflare.sphWorkerName` | 自定义 Worker 名称 |
   | `cloudflare.sphCookie` | 登录元宝后的 Web 端 cookie（约 1 个月过期，需要定期更新） |
   | `cloudflare.sphCredential` | **你自己设定的**访问凭证 |

3. 执行部署：

   ```bash
   wx_video_download deploy sph
   ```

4. 部署完成后，把本项目指到你的 Worker：

   ```bash
   export WECHAT_VIDEO_API_URL="https://<sphWorkerName>.<subdomain>.workers.dev/api/fetch_video_profile"
   export WECHAT_VIDEO_API_TOKEN="<你设定的 sphCredential>"
   python3 scripts/transcribe.py "https://weixin.qq.com/sph/AOVsoW8dBI" --resolve-only
   ```

   能打印出标题/作者就说明通了，去掉 `--resolve-only` 即可跑完整下载 + 转写（脚本本身无需任何改动）。

> ⚠️ 上游明确提示：**仅自己使用，不要对外提供**。元宝 cookie 有被限制或封禁的风险，这是你自己账号的风险，请自行判断，并遵守微信与元宝的服务条款。

#### 不想建 Worker：本地下载 + 离线转写

用上游客户端在本机（微信 PC 端视频号页面）把视频下载下来，再交给本项目转写。这条路径不碰 cookie，也不需要任何凭证，代价是每次要手动点一下下载。

```bash
python3 scripts/transcribe.py --input-file ./video.mp4 --output-dir ./subtitles
```

### 实测结论

| 检查项 | 结果 |
|--------|------|
| 直连 `sph.litao.workers.dev` | 连接超时，需经代理 |
| 经本机 HTTP 代理访问 | `HTTP 401 {"error":"unauthorized"}` |
| 公开部署是否还会恢复 | **不会**：上游元宝账号被封后已加凭证校验，凭证由部署者自设，第三方拿不到（上游 issue #495 + 部署文档） |
| 微信短链信息接口 `get_feed_info` | 匿名至多返回作者/描述/封面等元数据；本次复测直接返回 `HTTP 401 permission verification failed`，始终没有播放地址 |
| 用返回的 `dynamicExportId` 作为 `exportId` 查询视频信息 | `permission verification failed` |
| 完整下载 + 转写 | **未验证**：本机未自建 Worker、缺少有效凭证，测试机也未安装 `ffmpeg` / `whisper` |

结论：**官方公共解析已停用，这是服务方的设计而非脚本故障**。要恢复自动化解析，请按上一节自建查询 Worker，再把 `WECHAT_VIDEO_API_URL` / `WECHAT_VIDEO_API_TOKEN` 指向它；脚本无需改动。离线转写入口（`--input-file`）始终可用。

## License

MIT
