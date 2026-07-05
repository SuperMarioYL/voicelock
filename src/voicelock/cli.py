"""voicelock CLI — 去AI味 for 小红书 正文.

Subcommands:
  fingerprint     learn your account-voice fingerprint from your own 发布历史
  voice-distance  score how close a draft is to your account voice (0..1)
  audit           flag 爆款体 slop regions + slop score (no rewrite)
  rewrite         regenerate flagged regions in your voice + before/after diff
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from . import __version__
from .config import resolve_backend, voice_path
from .models import VoiceProfile
from .rewriter import rewrite as run_rewrite
from .slop_detector import detect
from .voiceprint import (
    build_profile,
    load_profile,
    save_profile,
    voice_consistency,
)

app = typer.Typer(
    name="voicelock",
    help="去AI味 for 小红书 正文 — learn your voice, flag 爆款体, rewrite in your voice.",
    add_completion=False,
    no_args_is_help=True,
)
console = Console()


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _read_source(path_or_text: str) -> str:
    """Accept either a file path or inline text."""
    p = Path(path_or_text)
    if p.exists() and p.is_file():
        return p.read_text(encoding="utf-8")
    return path_or_text


def _load_profile_or_none(account: str) -> Optional[VoiceProfile]:
    path = voice_path(account)
    if path.exists():
        try:
            return load_profile(path)
        except Exception as exc:  # pragma: no cover - defensive
            console.print(f"[yellow]无法读取声线指纹 {path}: {exc}[/yellow]")
    return None


def _slop_color(score: float) -> str:
    if score >= 60:
        return "bold red"
    if score >= 30:
        return "yellow"
    return "green"


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #
@app.command()
def fingerprint(
    corpus: str = typer.Option(
        ..., "--corpus", "-c", help="你的历史笔记正文（文件路径或直接粘贴文本，多篇用空行分隔）"
    ),
    account: str = typer.Option("default", "--account", "-a", help="账号标识（多账号时区分）"),
) -> None:
    """从你自己的发布历史学习『账号声线指纹』，保存为你拥有的资产。"""
    text = _read_source(corpus)
    if not text.strip():
        console.print("[red]语料为空。请提供你的历史笔记正文。[/red]")
        raise typer.Exit(code=1)

    profile = build_profile(text, account_id=account)
    path = save_profile(profile, voice_path(account))

    table = Table(title=f"账号声线指纹 · {account}", show_header=True, header_style="bold cyan")
    table.add_column("维度", style="cyan", no_wrap=True)
    table.add_column("值")
    table.add_row("笔记数 / 字数", f"{profile.n_posts} 篇 / {profile.n_chars} 字")
    table.add_row("词汇多样度 (TTR)", f"{profile.lexical_diversity:.3f}")
    table.add_row(
        "句长 mean/std/p90",
        f"{profile.sentence_length.mean:.1f} / {profile.sentence_length.std:.1f} / {profile.sentence_length.p90:.0f}",
    )
    table.add_row("emoji 密度 (每100字)", f"{profile.emoji_per_100_chars:.2f}")
    table.add_row(
        "标点节奏 ！/？/～",
        f"{profile.exclaim_ratio:.2f} / {profile.question_ratio:.2f} / {profile.wave_ratio:.2f}",
    )
    table.add_row("开头习惯", "、".join(profile.opener_hooks[:5]) or "—")
    table.add_row("签名高频词", "、".join(profile.high_freq_tokens[:10]) or "—")
    console.print(table)
    console.print(f"[green]✓[/green] 声线指纹已保存: [bold]{path}[/bold]")


@app.command(name="voice-distance")
def voice_distance_cmd(
    draft: str = typer.Argument(..., help="草稿文本（文件路径或直接粘贴）"),
    account: str = typer.Option("default", "--account", "-a", help="账号标识"),
) -> None:
    """打印草稿与你账号声线的一致性分数 (0..1，越高越像你)。"""
    profile = _load_profile_or_none(account)
    if profile is None:
        console.print(
            "[red]未找到声线指纹。请先运行[/red] [bold]voicelock fingerprint --corpus my-posts.txt[/bold]"
        )
        raise typer.Exit(code=1)
    text = _read_source(draft)
    vc = voice_consistency(profile, text)
    color = "green" if vc >= 0.7 else ("yellow" if vc >= 0.45 else "red")
    console.print(
        Panel(
            f"声线一致性 (voice-consistency): [{color} bold]{vc:.2f}[/{color} bold]\n"
            f"（1.00 = 和你自己的正文难以区分；0 = 完全不像）",
            title=f"voice-distance · {account}",
            border_style=color,
        )
    )


@app.command()
def audit(
    draft: str = typer.Argument(..., help="AI 副驾生成的草稿（文件路径或直接粘贴）"),
    account: str = typer.Option("default", "--account", "-a", help="账号标识（可选）"),
) -> None:
    """检测草稿里的『爆款体 / 一眼AI』slop 区域，打印标注视图 + slop 分数。"""
    profile = _load_profile_or_none(account)
    text = _read_source(draft)
    result = detect(text, profile)

    color = _slop_color(result.slop_score)
    header = Text()
    header.append("slop 分数 ", style="bold")
    header.append(f"{result.slop_score:.0f}/100", style=color)
    if result.voice_consistency is not None:
        header.append(f"    声线一致性 {result.voice_consistency:.2f}", style="cyan")
    console.print(Panel(header, title="voicelock audit", border_style=color))

    if not result.regions:
        console.print("[green]✓ 未检测到明显爆款体区域。[/green]")
        return

    table = Table(show_header=True, header_style="bold red")
    table.add_column("#", justify="right", width=3)
    table.add_column("类型", style="magenta", no_wrap=True)
    table.add_column("分", justify="right", width=4)
    table.add_column("句子 / 命中原因")
    for r in result.regions:
        table.add_row(
            str(r.sentence_idx),
            r.slop_type,
            f"{r.score:.0f}",
            f"[red]{r.text}[/red]\n[dim]{r.reason}[/dim]",
        )
    console.print(table)


@app.command()
def rewrite(
    draft: str = typer.Argument(..., help="AI 副驾生成的草稿（文件路径或直接粘贴）"),
    account: str = typer.Option("default", "--account", "-a", help="账号标识（可选）"),
    backend: Optional[str] = typer.Option(
        None, "--backend", "-b", help="mock (离线默认) 或 llm (需 VOICELOCK_API_KEY)"
    ),
    iters: int = typer.Option(2, "--iters", help="每个 slop 区域的最大重写次数"),
) -> None:
    """把每个爆款体区域『用你自己的声线』重写，打印 before/after diff + slop 分数变化。"""
    profile = _load_profile_or_none(account)
    text = _read_source(draft)
    cfg = resolve_backend(backend)

    result = run_rewrite(text, profile, backend_cfg=cfg, max_iters=iters)

    before_color = _slop_color(result.slop_before)
    after_color = _slop_color(result.slop_after)

    summary = Text()
    summary.append("slop  ", style="bold")
    summary.append(f"{result.slop_before:.0f}", style=before_color)
    summary.append(" → ", style="dim")
    summary.append(f"{result.slop_after:.0f}", style=after_color)
    summary.append(f"   backend={result.backend}", style="dim")
    if result.voice_consistency_after is not None:
        summary.append(
            f"   声线一致性 {result.voice_consistency_after:.2f}", style="cyan"
        )
    console.print(Panel(summary, title="voicelock rewrite", border_style=after_color))

    if result.per_region:
        for r in result.per_region:
            table = Table(show_header=False, box=None, pad_edge=False)
            table.add_column(style="dim", no_wrap=True, width=8)
            table.add_column()
            table.add_row("before", f"[red]{r['before']}[/red]")
            table.add_row("after", f"[green]{r['after']}[/green]")
            table.add_row(
                "slop",
                f"{r['region_slop_before']:.0f} → {r['region_slop_after']:.0f}"
                f"  ({r['slop_type']}, ×{r['iterations']})",
            )
            console.print(table)
            console.print()
    else:
        console.print("[green]✓ 未检测到需要重写的爆款体区域。[/green]")

    console.print(Panel(result.after, title="改写后正文 (去AI味)", border_style="green"))


@app.command()
def version() -> None:
    """打印 voicelock 版本。"""
    console.print(f"voicelock {__version__}")


def main() -> None:  # pragma: no cover - console-script shim
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
