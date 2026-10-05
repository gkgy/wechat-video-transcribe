# 微信视频号下载 + Whisper 语音转文字

> 一键提取微信视频号视频并生成 SRT 字幕 + 纯文本逐字稿

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)

> [!IMPORTANT]
> 自 2026-10-05 起，默认第三方解析接口已启用访问控制，匿名请求返回 `HTTP 401`。链接解析需要设置 `WECHAT_VIDEO_API_TOKEN`（服务方签发的凭证），详见文末「解析接口与限制」。
> 没有凭证时仍可用 `--input-file` 转写本地视频，见下方说明。

---

## 功能

一条命令完成微信视频号视频的全自动语音转文字流水线：

1. 解析微信视频号分享链接，获取真实视频地址（需服务方凭证）
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
# 0. 配置解析接口凭证（必需，见「解析接口与限制」；无凭证则只能转写本地文件）
export WECHAT_VIDEO_API_TOKEN="<服务方签发的凭证>"

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
# 1. 解析链接获取真实视频 URL（需要服务方签发的访问凭证，见下方“解析接口与限制”）
curl -s -X POST "https://sph.litao.workers.dev/api/fetch_video_profile" \
  -H "Content-Type: application/json" \
  -H "User-Agent: Mozilla/5.0 ..." \
  -H "Authorization: Bearer <凭证>" \
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

第三方解析服务 `sph.litao.workers.dev` 已启用访问控制：匿名请求返回 `HTTP 401 {"error":"unauthorized"}`。因此**链接解析必须提供服务方签发的访问凭证**，否则只能使用 `--input-file` 转写已下载的本地文件。本项目不绕过、不破解任何鉴权。

### 配置

```bash
# 服务方签发的访问凭证；脚本以 Authorization: Bearer 发送，不写文件、不打印到日志
export WECHAT_VIDEO_API_TOKEN="<你的凭证>"

# 可选：改用自建或第三方便携接口
export WECHAT_VIDEO_API_URL="https://your-endpoint/api/fetch_video_profile"

# 可选：解析与下载走代理（curl 自身也遵循 https_proxy / ALL_PROXY）
export WECHAT_VIDEO_PROXY="http://127.0.0.1:10808"
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

### 实测结论

| 检查项 | 结果 |
|--------|------|
| 直连 `sph.litao.workers.dev` | 连接超时，需经代理 |
| 经本机 HTTP 代理访问 | `HTTP 401 {"error":"unauthorized"}` |
| 微信短链信息接口 `get_feed_info` | 匿名至多返回作者/描述/封面等元数据；本次复测直接返回 `HTTP 401 permission verification failed`，始终没有播放地址 |
| 用返回的 `dynamicExportId` 作为 `exportId` 查询视频信息 | `permission verification failed` |
| 完整下载 + 转写 | **未验证**：缺少有效凭证，测试机也未安装 `ffmpeg` / `whisper` |

结论：**解析链路在拿到服务方凭证前无法恢复**；本次发布的是经过审查的兼容性补丁、鉴权支持与错误处理改进，离线转写入口（`--input-file`）始终可用。

## License

MIT
