---
name: wechat-video-transcribe
description: 微信视频号视频下载 + 语音转文字（Whisper）。提取微信视频号（Channels）视频并生成 SRT 字幕和纯文本转录。触发词：微信视频号、视频字幕提取、语音转文字、Whisper转写、提取视频中的文字、视频转逐字稿。
---

# 微信视频号下载 + Whisper 转写

## 概述

完整的微信视频号视频字幕提取流水线：解析分享链接 → 下载视频 → 提取音频 → Whisper 语音转文字 → 输出 SRT 字幕文件 + 纯文本逐字稿。

## 依赖

执行前确认以下工具可用：
- `curl` — 下载视频
- `ffmpeg` — 提取音频
- `whisper` CLI — 语音识别（`pip install openai-whisper` 后自动安装）

## 工作流

### Step 1：解析视频号链接，获取真实视频 URL

```bash
curl -s -X POST "https://sph.litao.workers.dev/api/fetch_video_profile" \
  -H "Content-Type: application/json" \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" \
  -d '{"url": "<微信视频号分享链接>"}'
```

返回 JSON 中包含 `video_url`、`title`、`author` 等字段。提取 `video_url` 供下一步使用。

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
python3 scripts/transcribe.py <微信视频号链接> [--model base|small|medium]
```
