#!/usr/bin/env python3
"""微信视频号 → Whisper 字幕，一键流水线。

输入方式（四选一）:
    1. --input-file       本地视频/音频文件，完全离线，不需要任何凭证（零风险）
    2. --video-url        直接给定播放地址（抓包/代理工具拿到），完全不走解析接口（零风险）
    3. --har              从抓包文件（HAR 或纯文本 URL 列表）里自动提取播放地址（零风险）
    4. YUANBAO_COOKIE     本机直跑解析链路：元宝 get_parse_result → 微信 get_feed_info
                          （无需自建服务，但会使用你的元宝账号，存在账号风险）
       或 WECHAT_VIDEO_API_URL / WECHAT_VIDEO_API_TOKEN   指向你自己部署的解析接口

用法:
    python3 transcribe.py <微信视频号链接> [--model base|small|medium] [--output-dir ./]

示例:
    python3 transcribe.py "https://weixin.qq.com/sph/Ap5KZZrF3F"
    python3 transcribe.py "https://weixin.qq.com/sph/Ap5KZZrF3F" --model medium --output-dir ./subtitles
    python3 transcribe.py "https://weixin.qq.com/sph/Ap5KZZrF3F" --resolve-only
    python3 transcribe.py --input-file ./video.mp4 --output-dir ./subtitles
    python3 transcribe.py --video-url "https://finder.video.qq.com/....mp4" --output-dir ./subtitles
    python3 transcribe.py --har capture.har --output-dir ./subtitles

中文输出默认为简体：脚本会自动给 Whisper 加一句普通话提示词（--initial-prompt 可覆盖或关闭），
否则 Whisper 经常输出繁体。--language 默认 Chinese，可改成其它语言。

环境变量:
    YUANBAO_COOKIE          元宝 Web 端 Cookie；设定后本机直跑解析，不需要自建服务
    WECHAT_VIDEO_API_URL    自建解析接口地址（公共默认地址已停用）
    WECHAT_VIDEO_API_TOKEN  解析接口访问凭证，以 Authorization: Bearer 发送
    WECHAT_VIDEO_PROXY      解析与下载请求使用的 HTTP 代理（curl 亦遵循 https_proxy）
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse


def run(cmd: list[str], cwd: str | None = None, timeout: int = 600) -> subprocess.CompletedProcess:
    """Run a command and return the result, raising on failure."""
    print(f"  → {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        sys.stderr.write(f"  ✗ 失败 (exit {result.returncode}):\n{result.stderr}\n")
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")
    return result


def ensure_tool(name: str, install_hint: str) -> None:
    """Check that a CLI tool is available, print hint if not."""
    if subprocess.run(["which", name], capture_output=True).returncode != 0:
        sys.stderr.write(f"✗ 缺少依赖：{name}\n  安装：{install_hint}\n")
        sys.exit(1)


def provider_message(data: object) -> str:
    """Extract a human-readable reason from a provider error payload, if any."""
    if not isinstance(data, dict):
        return ""
    for key in ("error", "errMsg", "message", "msg"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            text = value.get("title") or value.get("content") or value.get("msg")
            if isinstance(text, str) and text.strip():
                return text.strip()
    return ""


def nested_video_url(node: object) -> str:
    """Look for a playable URL in a WeChat feedInfo-style node."""
    if not isinstance(node, dict):
        return ""
    for key in ("h264VideoInfo", "h265VideoInfo"):
        media = node.get(key)
        if isinstance(media, dict) and media.get("videoUrl"):
            return str(media["videoUrl"])
    flat = node.get("videoUrl")
    return str(flat) if flat else ""


def normalize_profile(data: dict) -> dict:
    """Accept the legacy flat response and the current nested WeChat response."""
    if not isinstance(data, dict):
        raise RuntimeError(f"解析接口响应格式不兼容（顶层为 {type(data).__name__}）")
    if data.get("video_url"):
        return data
    payload = data.get("data", data)
    while isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        payload = payload["data"]
    if not isinstance(payload, dict):
        raise RuntimeError(f"解析接口响应格式不兼容（data 为 {type(payload).__name__}）")
    feed = payload.get("feedInfo")
    video_url = nested_video_url(feed) or nested_video_url(payload)
    if not video_url:
        detail = provider_message(payload) or provider_message(data)
        if detail:
            raise RuntimeError(f"解析接口未返回播放地址：{detail}")
        raise RuntimeError("解析接口未返回视频播放地址；标题和封面不代表视频可下载。"
                           "可使用 --input-file 转写已下载的本地视频。")
    feed = feed if isinstance(feed, dict) else {}
    author_info = payload.get("authorInfo")
    author = author_info.get("nickname") if isinstance(author_info, dict) else None
    return {
        "video_url": video_url,
        "title": feed.get("description") or payload.get("title") or data.get("title") or "未知",
        "author": author or payload.get("author") or data.get("author") or "未知",
    }


AUTH_HINT = (
    "该访问凭证需要服务方签发；如果这是已停用的公共地址，请改用零风险方式："
    "--input-file（转写本地视频）、--video-url（已有播放地址）或 --har（从抓包文件提取直链）；"
    "也可以自备元宝 Cookie 走本机直跑（设置 YUANBAO_COOKIE）。"
)


def proxy_args() -> list[str]:
    """Honor an explicit proxy override on top of curl's own *_proxy env vars."""
    proxy = os.environ.get("WECHAT_VIDEO_PROXY", "").strip()
    if not proxy:
        return []
    if "\n" in proxy or "\r" in proxy:
        raise RuntimeError("代理地址含非法换行符")
    return ["--proxy", proxy]


def fetch_video_profile(video_url: str) -> dict:
    """Resolve with an optional provider credential, without logging secrets."""
    print("\n📡 解析视频链接…")
    endpoint = os.environ.get("WECHAT_VIDEO_API_URL", "https://sph.litao.workers.dev/api/fetch_video_profile")
    credential = os.environ.get("WECHAT_VIDEO_API_TOKEN", "").strip()
    headers = "Content-Type: application/json\nUser-Agent: Mozilla/5.0\n"
    if credential:
        if "\n" in credential or "\r" in credential:
            raise RuntimeError("访问凭证含非法换行符")
        headers += "Authorization: Bearer " + credential + "\n"
    try:
        result = subprocess.run(
            ["curl", "-sS", "--connect-timeout", "10", "--max-time", "30",
             "--write-out", "\n%{http_code}", *proxy_args(), "-X", "POST", endpoint,
             "-H", "@-", "--data-raw", json.dumps({"url": video_url})],
            input=headers, capture_output=True, text=True, timeout=35,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("未找到 curl，请先安装 curl") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("解析接口超时，请检查网络或代理") from exc
    if result.returncode:
        raise RuntimeError(f"无法连接解析接口（curl {result.returncode}），请检查网络或代理")
    body, _, status = result.stdout.rpartition("\n")
    if not status.strip().isdigit():
        raise RuntimeError("解析接口返回了无法识别的响应")
    status = status.strip()
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        if status in ("401", "403"):
            raise RuntimeError(f"解析接口拒绝访问（HTTP {status}）。{AUTH_HINT}")
        raise RuntimeError(f"解析接口返回非 JSON 数据（HTTP {status}）")
    detail = provider_message(data)
    if status in ("401", "403"):
        suffix = f"：{detail}" if detail else ""
        raise RuntimeError(f"解析接口拒绝访问（HTTP {status}）{suffix}。{AUTH_HINT}")
    if not status.startswith("2"):
        raise RuntimeError(f"解析接口 HTTP {status}" + (f"：{detail}" if detail else ""))
    profile = normalize_profile(data)
    print(f"  标题: {profile.get('title') or '未知'}")
    print(f"  作者: {profile.get('author') or '未知'}")
    return profile


# --- 本机直跑解析（不需要任何自建服务，只需自己的元宝 Cookie） ---------------

YUANBAO_PARSE_URL = "https://yuanbao.tencent.com/api/weixin/get_parse_result"
FEED_INFO_URL = "https://channels.weixin.qq.com/finder-preview/api/feed/get_feed_info"
FEED_INFO_ORIGIN = "https://channels.weixin.qq.com"
BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def curl_post_json(url: str, payload: dict, header_lines: str) -> tuple[object, str]:
    """POST JSON via curl, header block passed on stdin. Returns (parsed_data, status).

    Headers travel on stdin (curl -H @-) so credentials never show up in the process
    list, in printed commands, or in error messages.
    """
    try:
        result = subprocess.run(
            ["curl", "-sS", "--connect-timeout", "10", "--max-time", "30",
             "--write-out", "\n%{http_code}", *proxy_args(), "-X", "POST", url,
             "-H", "@-", "--data-raw", json.dumps(payload)],
            input=header_lines, capture_output=True, text=True, timeout=35,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("未找到 curl，请先安装 curl") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("请求超时，请检查网络或代理") from exc
    if result.returncode:
        raise RuntimeError(f"无法连接 {url.split('/')[2]}（curl {result.returncode}），请检查网络或代理")
    body, _, status = result.stdout.rpartition("\n")
    status = status.strip()
    if not status.isdigit():
        raise RuntimeError("接口返回了无法识别的响应")
    try:
        return json.loads(body), status
    except json.JSONDecodeError:
        raise RuntimeError(f"接口返回非 JSON 数据（HTTP {status}）")


def playable_url_token_and_eid(playable_url: str) -> tuple[str, str]:
    """Pull generalToken / exportId out of the playable_url query string."""
    try:
        query = parse_qs(urlparse(playable_url).query)
    except ValueError:
        return "", ""
    token = (query.get("token") or [""])[0]
    eid = (query.get("eid") or [""])[0]
    return token, eid


def resolve_locally(share_url: str, cookie: str) -> dict:
    """Resolve on this machine: yuanbao parse → WeChat get_feed_info. No self-hosted service."""
    print("\n📡 本机直跑解析（元宝 → 微信）…")
    if "\n" in cookie or "\r" in cookie:
        raise RuntimeError("元宝 Cookie 含非法换行符")
    data, status = curl_post_json(
        YUANBAO_PARSE_URL,
        {"type": "video_channel_url", "url": share_url, "scene": 1},
        f"Cookie: {cookie}\n"
        "Accept: application/json, text/plain, */*\n"
        "Content-Type: application/json\n"
        "Origin: https://yuanbao.tencent.com\n"
        "Referer: https://yuanbao.tencent.com/\n"
        f"User-Agent: {BROWSER_UA}\n",
    )
    if status in ("401", "403"):
        raise RuntimeError(f"元宝拒绝访问（HTTP {status}）：Cookie 无效或已过期，请重新登录 "
                           "https://yuanbao.tencent.com/ 后更新 YUANBAO_COOKIE。")
    if not status.startswith("2"):
        raise RuntimeError(f"元宝接口 HTTP {status}" + (f"：{provider_message(data)}" if provider_message(data) else ""))
    parse_data = data.get("data") if isinstance(data, dict) else None
    if not isinstance(parse_data, dict):
        raise RuntimeError("元宝响应缺少 data 字段，解析失败")
    export_id = str(parse_data.get("wx_export_id") or "")
    general_token, playable_eid = playable_url_token_and_eid(str(parse_data.get("playable_url") or ""))
    export_id = playable_eid or export_id
    if not export_id:
        raise RuntimeError("元宝未返回 exportId，无法继续解析")
    print(f"  exportId: {export_id}")

    print("  → 查询视频信息…")
    feed, status = curl_post_json(
        FEED_INFO_URL,
        {"baseReq": {"generalToken": general_token}, "exportId": export_id},
        "Accept: application/json, text/plain, */*\n"
        "Content-Type: application/json\n"
        f"Origin: {FEED_INFO_ORIGIN}\n"
        f"Referer: {FEED_INFO_ORIGIN}/\n"
        f"User-Agent: {BROWSER_UA}\n",
    )
    detail = provider_message(feed)
    if status in ("401", "403") or (isinstance(feed, dict) and feed.get("errCode")):
        raise RuntimeError("微信拒绝了这次查询"
                           + (f"：{detail}" if detail else f"（HTTP {status}）")
                           + "。通常是元宝返回的 token 失效或该视频不允许外部播放。")
    if not status.startswith("2"):
        raise RuntimeError(f"微信接口 HTTP {status}" + (f"：{detail}" if detail else ""))
    profile = normalize_profile(feed)
    print(f"  标题: {profile.get('title') or '未知'}")
    print(f"  作者: {profile.get('author') or '未知'}")
    return profile


def download_video(video_url: str, output_path: str) -> None:
    """Download the video file from CDN."""
    print("\n⬇️  下载视频…")
    try:
        run([
            "curl", "--fail", "-L", "-o", output_path, *proxy_args(),
            "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "-H", "Referer: https://channels.weixin.qq.com/",
            video_url,
        ], timeout=600)
    except RuntimeError as exc:
        raise RuntimeError("视频下载失败：链接可能已过期或需要重新解析（curl 已启用 --fail）") from exc
    if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        raise RuntimeError("视频下载失败：没有拿到文件内容，链接可能已过期或需要重新解析")
    size_mb = os.path.getsize(output_path) / 1024 / 1024
    print(f"  已保存: {output_path} ({size_mb:.1f} MB)")


def extract_audio(video_path: str, audio_path: str) -> None:
    """Extract 16kHz mono WAV from video."""
    print(f"\n🎵 提取音频…")
    run([
        "ffmpeg", "-y",
        "-i", video_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        audio_path,
    ])
    print(f"  已保存: {audio_path}")


SIMPLIFIED_HINT = "以下是普通话的句子。"


def transcribe(audio_path: str, model: str, output_dir: str,
               language: str = "Chinese", initial_prompt: str | None = None) -> None:
    """Run Whisper CLI to generate SRT."""
    print(f"\n🎙️  Whisper 转写中（模型: {model}）…")
    cmd = [
        "whisper", audio_path,
        "--language", language,
        "--model", model,
        "--output_format", "srt",
        "--output_dir", output_dir,
    ]
    if initial_prompt:
        cmd += ["--initial_prompt", initial_prompt]
    run(cmd, timeout=1800)
    print(f"  字幕已保存到 {output_dir}/")


def extract_plain_text(srt_path: str, text_path: str) -> None:
    """Extract every 3rd line of every 4-line block from SRT -> plain text."""
    lines = Path(srt_path).read_text(encoding="utf-8").splitlines()
    texts = [lines[i] for i in range(2, len(lines), 4)]
    Path(text_path).write_text("\n".join(texts), encoding="utf-8")
    print(f"  逐字稿已保存: {text_path}")


def resolve(share_url: str) -> dict:
    """Pick a resolver: local yuanbao chain when a cookie is present, else the API endpoint."""
    cookie = os.environ.get("YUANBAO_COOKIE", "").strip()
    if cookie:
        return resolve_locally(share_url, cookie)
    return fetch_video_profile(share_url)


# --- 零风险路径：从抓包文件里提取播放地址（不使用任何账号凭证） -------------

SEGMENT_SUFFIXES = (".m4s", ".ts")
URL_PATTERN = re.compile(r"https?://[^\s\"'<>\\]+")


def _looks_like_segment(url: str, mime: str) -> bool:
    """MSE/HLS segment rather than a whole file — not downloadable on its own."""
    if "iso.segment" in mime.lower():
        return True
    return urlparse(url).path.lower().endswith(SEGMENT_SUFFIXES)


def _score_candidate(url: str, mime: str) -> int:
    host = urlparse(url).netloc.lower()
    low = url.lower()
    score = 0
    if "video.qq.com" in host:
        score += 3
    if mime.lower().startswith("video/"):
        score += 3
    if low.endswith(".mp4") or ".mp4?" in low or ".mp4#" in low:
        score += 3
    return score


def _collect_urls(har_path: Path) -> list[tuple[str, str]]:
    """Return (url, mime) pairs from a HAR export, or from a plain URL list."""
    raw = har_path.read_text(encoding="utf-8", errors="replace")
    try:
        har = json.loads(raw)
    except json.JSONDecodeError:
        return [(u, "") for u in URL_PATTERN.findall(raw)]
    entries = ((har or {}).get("log") or {}).get("entries") or []
    found: list[tuple[str, str]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        request = entry.get("request")
        url = request.get("url") if isinstance(request, dict) else None
        if not isinstance(url, str) or not url.lower().startswith(("http://", "https://")):
            continue
        response = entry.get("response")
        mime = ""
        if isinstance(response, dict):
            mime = str(response.get("mimeType") or "")
        found.append((url, mime))
    return found


def resolve_from_har(har_path: Path) -> str:
    """Extract a playable URL from a capture file without touching any account credential."""
    print(f"\n🔎 从抓包文件提取播放地址：{har_path}")
    try:
        entries = _collect_urls(har_path)
    except OSError as exc:
        raise RuntimeError(f"无法读取抓包文件：{exc}") from exc
    if not entries:
        raise RuntimeError("抓包文件里没有找到任何 URL。")
    whole: list[tuple[int, str]] = []
    segments = 0
    for url, mime in entries:
        if _looks_like_segment(url, mime):
            segments += 1
            continue
        score = _score_candidate(url, mime)
        if score:
            whole.append((score, url))
    ranked: dict[str, int] = {}
    for score, url in whole:
        ranked[url] = max(ranked.get(url, 0), score)
    candidates = sorted(((s, u) for u, s in ranked.items()), key=lambda item: (-item[0], item[1]))
    for score, url in candidates[:5]:
        print(f"  候选[{score}] {url}")
    if not candidates:
        hint = "只看到分片流（MSE/HLS），无法直接下载整段视频。" if segments else "没有识别到视频地址。"
        raise RuntimeError(
            f"{hint}注意：用普通浏览器打开分享页拿不到地址——官方页面的取流逻辑只在微信环境内执行"
            "（JS 里判断 WeixinJSBridge 环境后才调 getFeedInfo）。建议改用 --input-file 转写"
            "已经下载到本地的视频，或在微信 PC 客户端/手机端抓包后再用 --har。"
        )
    best_score, best = candidates[0]
    if best_score < 3:
        raise RuntimeError("候选地址可信度不足，无法确定是否为完整视频。请从上面的列表挑一个"
                           "并用 --video-url 指定。")
    if len(candidates) > 1 and candidates[1][0] == best_score:
        raise RuntimeError("抓包文件里有多个同权重候选，无法自动判断。请从上面的列表挑一个，"
                           "改用 --video-url 指定。")
    print(f"  选用: {best}")
    return best


def main():
    parser = argparse.ArgumentParser(description="微信视频号 → 语音转文字")
    parser.add_argument("url", nargs="?", help="微信视频号分享链接")
    parser.add_argument("--input-file", type=Path, help="转写本地视频或音频，跳过链接解析")
    parser.add_argument("--video-url", help="直接给定视频播放地址（自己抓包/开发者工具获取），跳过解析")
    parser.add_argument("--har", type=Path,
                        help="从抓包文件提取播放地址：浏览器/代理导出的 HAR，或纯文本 URL 列表（零风险）")
    parser.add_argument("--resolve-only", action="store_true", help="仅验证链接解析，不下载或转写")
    parser.add_argument("--model", default="base", choices=["tiny", "base", "small", "medium"],
                        help="Whisper 模型大小 (默认: base)")
    parser.add_argument("--language", default="Chinese",
                        help="Whisper 识别语言 (默认: Chinese)")
    parser.add_argument("--initial-prompt", default=None,
                        help="Whisper 提示词。中文默认用「以下是普通话的句子。」以避免输出繁体；"
                             "传空字符串可关闭")
    parser.add_argument("--output-dir", default="./", help="输出目录 (默认: ./)")
    args = parser.parse_args()

    sources = [bool(args.url), bool(args.input_file), bool(args.video_url), bool(args.har)]
    if sum(sources) != 1:
        parser.error("请提供分享链接、--input-file、--video-url 或 --har，四选一")
    if args.resolve_only:
        if not args.url:
            parser.error("--resolve-only 需要分享链接")
        resolve(args.url)
        return
    if args.input_file and not args.input_file.is_file():
        parser.error("本地输入文件不存在")
    if args.har and not args.har.is_file():
        parser.error("抓包文件不存在")

    # Pre-flight checks
    ensure_tool("curl", "brew install curl")
    ensure_tool("ffmpeg", "brew install ffmpeg")
    ensure_tool("whisper", "pip install openai-whisper")

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Whisper 默认会用繁体输出中文；给一句普通话提示词可强制简体并改善标点。
    initial_prompt = args.initial_prompt
    if initial_prompt is None:
        initial_prompt = SIMPLIFIED_HINT if args.language.strip().lower() in (
            "chinese", "zh", "mandarin", "zh-cn", "cmn") else ""

    with tempfile.TemporaryDirectory() as tmpdir:
        video_path = os.path.join(tmpdir, "video.mp4")
        audio_path = os.path.join(tmpdir, "audio.wav")

        # Step 1: Get a video file — local path, a direct URL, or resolve then download
        if args.input_file:
            video_path = str(args.input_file.resolve())
        else:
            if args.video_url:
                video_url = args.video_url
            elif args.har:
                video_url = resolve_from_har(args.har)
            else:
                video_url = resolve(args.url)["video_url"]
            # Step 2: Download
            download_video(video_url, video_path)

        # Step 3: Extract audio
        extract_audio(video_path, audio_path)

        # Step 4: Transcribe
        transcribe(audio_path, args.model, str(output_dir), args.language, initial_prompt)

        # Step 5: Plain text
        srt_file = output_dir / "audio.srt"
        if srt_file.exists():
            extract_plain_text(str(srt_file), str(output_dir / "transcript.txt"))

    print(f"\n✅ 完成！")
    print(f"  字幕:  {output_dir / 'audio.srt'}")
    print(f"  文本:  {output_dir / 'transcript.txt'}")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        sys.stderr.write(f"✗ {exc}\n")
        sys.exit(1)
