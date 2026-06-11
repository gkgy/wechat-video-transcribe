#!/usr/bin/env python3
"""微信视频号 → Whisper 字幕，一键流水线。

用法:
    python3 transcribe.py <微信视频号链接> [--model base|small|medium] [--output-dir ./]

示例:
    python3 transcribe.py "https://weixin.qq.com/sph/Ap5KZZrF3F"
    python3 transcribe.py "https://weixin.qq.com/sph/Ap5KZZrF3F" --model medium --output-dir ./subtitles
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


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


def fetch_video_profile(video_url: str) -> dict:
    """POST to sph.litao.workers.dev to resolve a WeChat Channels link."""
    print(f"\n📡 解析视频链接…")
    result = subprocess.run(
        [
            "curl", "-s", "-X", "POST",
            "https://sph.litao.workers.dev/api/fetch_video_profile",
            "-H", "Content-Type: application/json",
            "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "-d", json.dumps({"url": video_url}),
        ],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0 or not result.stdout.strip():
        sys.stderr.write("✗ 无法解析视频链接（API 无响应）\n")
        sys.exit(1)
    data = json.loads(result.stdout)
    if not data.get("video_url"):
        sys.stderr.write(f"✗ API 返回数据异常: {json.dumps(data, ensure_ascii=False)}\n")
        sys.exit(1)
    print(f"  标题: {data.get('title', '未知')}")
    print(f"  作者: {data.get('author', '未知')}")
    return data


def download_video(video_url: str, output_path: str) -> None:
    """Download the video file from CDN."""
    print(f"\n⬇️  下载视频…")
    run([
        "curl", "-L", "-o", output_path,
        "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "-H", "Referer: https://channels.weixin.qq.com/",
        video_url,
    ], timeout=600)
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


def transcribe(audio_path: str, model: str, output_dir: str) -> None:
    """Run Whisper CLI to generate SRT."""
    print(f"\n🎙️  Whisper 转写中（模型: {model}）…")
    run([
        "whisper", audio_path,
        "--language", "Chinese",
        "--model", model,
        "--output_format", "srt",
        "--output_dir", output_dir,
    ], timeout=1800)
    print(f"  字幕已保存到 {output_dir}/")


def extract_plain_text(srt_path: str, text_path: str) -> None:
    """Extract every 3rd line of every 4-line block from SRT -> plain text."""
    lines = Path(srt_path).read_text(encoding="utf-8").splitlines()
    texts = [lines[i] for i in range(2, len(lines), 4)]
    Path(text_path).write_text("\n".join(texts), encoding="utf-8")
    print(f"  逐字稿已保存: {text_path}")


def main():
    parser = argparse.ArgumentParser(description="微信视频号 → 语音转文字")
    parser.add_argument("url", help="微信视频号分享链接")
    parser.add_argument("--model", default="base", choices=["tiny", "base", "small", "medium"],
                        help="Whisper 模型大小 (默认: base)")
    parser.add_argument("--output-dir", default="./", help="输出目录 (默认: ./)")
    args = parser.parse_args()

    # Pre-flight checks
    ensure_tool("curl", "brew install curl")
    ensure_tool("ffmpeg", "brew install ffmpeg")
    ensure_tool("whisper", "pip install openai-whisper")

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        video_path = os.path.join(tmpdir, "video.mp4")
        audio_path = os.path.join(tmpdir, "audio.wav")

        # Step 1: Resolve link
        profile = fetch_video_profile(args.url)

        # Step 2: Download
        download_video(profile["video_url"], video_path)

        # Step 3: Extract audio
        extract_audio(video_path, audio_path)

        # Step 4: Transcribe
        transcribe(audio_path, args.model, str(output_dir))

        # Step 5: Plain text
        srt_file = output_dir / "audio.srt"
        if srt_file.exists():
            extract_plain_text(str(srt_file), str(output_dir / "transcript.txt"))

    print(f"\n✅ 完成！")
    print(f"  字幕:  {output_dir / 'audio.srt'}")
    print(f"  文本:  {output_dir / 'transcript.txt'}")


if __name__ == "__main__":
    main()
