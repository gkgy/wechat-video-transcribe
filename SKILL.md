---
name: wechat-video-transcribe
description: 微信视频号视频下载 + 语音转文字（Whisper）。提取微信视频号（Channels）视频并生成 SRT 字幕和纯文本转录。链接解析需服务方访问凭证，无凭证时可用 --input-file 转写本地视频。触发词：微信视频号、视频字幕提取、语音转文字、Whisper转写、提取视频中的文字、视频转逐字稿。
---

# 微信视频号下载 + Whisper 转写

## 概述

完整的微信视频号视频字幕提取流水线：解析分享链接 → 下载视频 → 提取音频 → Whisper 语音转文字 → 输出 SRT 字幕文件 + 纯文本逐字稿。

## 依赖

执行前确认以下工具可用：
- `curl` — 调用解析接口并下载视频
- `ffmpeg` — 提取音频
- `whisper` CLI — 语音识别（`pip install openai-whisper` 后自动安装）

## 前提：解析接口需要访问凭证

自 2026-10-05 起，默认第三方解析服务 `sph.litao.workers.dev` 已启用访问控制，匿名请求返回 `HTTP 401 {"error":"unauthorized"}`。

- 链接解析**必须**提供服务方签发的凭证，通过 `WECHAT_VIDEO_API_TOKEN` 注入（脚本以 `Authorization: Bearer` 发送，不写文件、不打印到日志）。
- 无凭证时不要尝试绕过鉴权：改用 `--input-file` 转写用户已下载的本地视频，或告知用户需要向服务方申请凭证。
- 需要代理时设置 `WECHAT_VIDEO_PROXY`（curl 本身也遵循 `https_proxy` / `ALL_PROXY`）。
- 拿到标题、作者或封面**不代表**视频可下载，务必确认响应里有播放地址。

## 工作流

### Step 1：解析视频号链接，获取真实视频 URL

```bash
curl -s -X POST "https://sph.litao.workers.dev/api/fetch_video_profile" \
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

# 转写已下载到本地的视频/音频，不依赖解析服务（无凭证时的可用路径）
python3 scripts/transcribe.py --input-file ./video.mp4 --output-dir ./subtitles

# 解析与下载走代理
export WECHAT_VIDEO_PROXY="http://127.0.0.1:10808"
```

脚本会区分并明确报出：HTTP 401/403（鉴权）、网络超时/连接失败、非 JSON 响应、其他非 2xx 状态、以及 2xx 但缺少播放地址。下载失败（链接过期等）通过 `curl --fail` 直接报错，不会把错误页存成视频文件。

## 已知限制（2026-10-05 实测）

- 匿名调用 `sph.litao.workers.dev` 返回 `HTTP 401`，本机直连该域名还会超时，需要代理。
- **这个 401 是上游的设计，不是脚本故障**：该项目依赖的元宝账号被封，作者在 [issue #495](https://github.com/ltaoo/wx_channels_download/issues/495)（2026-08-13）宣布「后续会增加凭证校验」，其 `deploy sph` 文档要求注入 `ACCESS_CREDENTIAL` 作为访问凭证（认证失败 401 / 未配置 503）。凭证由部署者自己设定，第三方拿不到。
- 微信短链信息接口 `channels.weixin.qq.com/finder-preview/api/feed/get_feed_info` 匿名至多给出作者、描述、封面，没有播放地址；本次复测直接返回 `permission verification failed`。用其中的 `dynamicExportId` 当 `exportId` 再查同样失败。
- 因此**完整下载 + 转写链路在用户自备凭证前不可用**，不要对外声称已恢复。

## 凭证拿不到时怎么办

按用户的实际需求二选一，不要尝试绕过鉴权：

1. **要自动化解析** → 让用户按上游文档自建自己的 `sph` Worker（`wx_video_download deploy sph`，需要 Cloudflare 账号 + 元宝 Web cookie），拿到 `sphCredential` 后设置 `WECHAT_VIDEO_API_URL` 与 `WECHAT_VIDEO_API_TOKEN`，再用 `--resolve-only` 验证。提醒上游「仅自己使用」的警告与 cookie 被限制的风险。
2. **只需一次转写** → 让用户用上游客户端把视频下载到本地，再用 `--input-file` 转写，这条路径不依赖任何凭证。
