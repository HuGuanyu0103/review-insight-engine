"""Rich-based CLI for the 商品评论洞察引擎.

Provides commands:
  run       — Full pipeline end-to-end
  ask       — RAG Q&A
  report    — Generate report from existing extractions
  validate  — Golden dataset validation
  serve     — Start FastAPI server
"""

import json
import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint

# Ensure src/ is on the path when running as script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

console = Console()


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
@click.pass_context
def cli(ctx, verbose):
    """商品评论洞察引擎 (User Voice AI) — 电商评论智能分析工具"""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    setup_logging(verbose)


@cli.command()
@click.option("--input", "-i", required=True, help="Input CSV file path", type=click.Path(exists=True))
@click.option("--output-dir", "-o", default="./outputs/", help="Output directory")
@click.option("--no-llm", is_flag=True, help="Disable LLM (rule-based extraction only, for testing)")
@click.option("--map-cols", "-m", default=None, help="Column mapping: old1=new1,old2=new2 (e.g. review_text=review_content)")
def run(input, output_dir, no_llm, map_cols):
    """Run the full pipeline end-to-end (parse → filter → map → reduce → rag → report)."""
    from src.pipeline.orchestrator import Pipeline

    # Parse column mapping
    column_mapping = {}
    if map_cols:
        for pair in map_cols.split(","):
            old, new = pair.strip().split("=")
            column_mapping[old.strip()] = new.strip()

    console.print(Panel.fit(
        "[bold blue]商品评论洞察引擎[/bold blue]\n"
        f"输入: {input}\n"
        f"输出: {output_dir}\n"
        f"LLM: {'禁用 (规则模式)' if no_llm else '启用'}\n"
        f"列映射: {column_mapping if column_mapping else '无'}",
        title="Pipeline Starting",
    ))

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Running pipeline...", total=None)

        pipeline = Pipeline(
            input_path=input,
            output_dir=output_dir,
            use_llm=not no_llm,
            column_mapping=column_mapping,
        )
        summary = pipeline.run()

        progress.update(task, completed=True, description="[green]Pipeline complete!")

    # Print summary
    table = Table(title="Pipeline Summary")
    table.add_column("Stage", style="cyan")
    table.add_column("Metric", style="magenta")
    table.add_column("Value", style="green")

    table.add_row("Parse", "Reviews parsed", str(summary.get("parsed", 0)))
    table.add_row("Filter", "Reviews kept", str(summary.get("kept", 0)))
    table.add_row("Filter", "Reviews filtered", str(summary.get("filtered", 0)))
    table.add_row("Map", "Extractions", str(summary.get("extracted", 0)))
    table.add_row("Map", "HITL queue", str(summary.get("hitl", 0)))
    table.add_row("Report", "Summary", str(summary.get("report", "")))
    table.add_row("RAG", "Documents indexed", str(summary.get("rag_docs", 0)))

    console.print(table)
    console.print(f"\n[bold]输出目录:[/bold] {Path(output_dir).resolve()}")
    console.print(f"  📊 报告: {output_dir}/reports/insight_report.json")
    console.print(f"  📋 结构化数据: {output_dir}/structured/extracted.json")
    console.print(f"  🔍 向量库: {output_dir}/vectordb/")
    console.print(f"  ⚠️  HITL队列: {output_dir}/hitl/hitl_queue.csv")


@cli.command()
@click.option("--question", "-q", required=True, help="Natural language question to ask")
@click.option("--n-results", "-n", default=10, help="Number of reviews to retrieve")
@click.option("--vectordb-path", "-v", default=None, help="Vector store path (default: from settings)")
def ask(question, n_results, vectordb_path):
    """Ask a question against the RAG vector store."""
    from src.rag.qa_engine import QAEngine
    from src.rag.vector_store import VectorStore

    console.print(f"[bold]🔍 问题:[/bold] {question}\n")

    with Progress(SpinnerColumn(), TextColumn("检索中..."), console=console) as progress:
        task = progress.add_task("", total=None)
        vs = VectorStore(persist_path=vectordb_path) if vectordb_path else VectorStore()
        engine = QAEngine(vector_store=vs)
        result = engine.ask(question, n_results=n_results)
        progress.update(task, completed=True)

    # Answer
    console.print(Panel(result["answer"], title="[bold green]Answer[/bold green]"))

    # Citations
    if result["citations"]:
        console.print(f"\n[bold]📎 引用评论 ({result['retrieved_count']}条):[/bold]")
        for c in result["citations"]:
            console.print(
                f"  [[{c['index']}]] [cyan]{c['review_id']}[/cyan] "
                f"({c.get('sentiment', '')} | {c.get('category', '')})\n"
                f"       {c['content'][:120]}..."
            )


@cli.command()
@click.option("--extractions", "-e", required=True, help="Path to extracted.json", type=click.Path(exists=True))
@click.option("--output", "-o", default="./outputs/reports/insight_report.json", help="Output report path")
def report(extractions, output):
    """Generate a report from existing extraction results (skip Map phase)."""
    from src.models.extraction import ExtractedReview
    from src.report.generator import generate_report

    with open(extractions, encoding="utf-8") as f:
        data = json.load(f)

    extractions_list = [ExtractedReview(**item) for item in data]

    # Build minimal lookup from extraction data
    reviews_lookup = {
        e.review_id: {"review_content": e.core_issue_summary}
        for e in extractions_list
    }

    report_obj = generate_report(extractions_list, reviews_lookup, use_llm=False)

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(report_obj.model_dump(), f, ensure_ascii=False, indent=2, default=str)

    console.print(f"[green]✅ 报告已生成:[/green] {output}")
    console.print(f"  健康度: {report_obj.executive_summary.health_score}%")
    console.print(f"  Top 问题: {len(report_obj.pain_points.top_pain_points)} 项")
    console.print(f"  改进建议: {len(report_obj.recommendations)} 条")


@cli.command()
@click.option("--golden", "-g", required=True, help="Golden dataset CSV path", type=click.Path(exists=True))
@click.option("--output-dir", "-o", default="./outputs/", help="Output directory")
def validate(golden, output_dir):
    """Run golden dataset validation — verify pipeline accuracy."""
    from src.pipeline.orchestrator import Pipeline
    import pandas as pd

    console.print(Panel.fit(
        "[bold yellow]Golden Dataset Validation[/bold yellow]\n"
        f"基准数据: {golden}",
        title="Validation",
    ))

    # Load golden dataset
    df = pd.read_csv(golden, dtype=str, encoding="utf-8-sig")

    console.print(f"基准样本数: {len(df)}")
    console.print(f"预期列: {list(df.columns)}")

    # For now, validate structure
    required_cols = ["review_id", "review_content", "expected_sentiment", "expected_category", "expected_urgency"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        console.print(f"[red]❌ 缺少列: {missing}[/red]")
        return

    console.print("[green]✅ Golden dataset 结构验证通过[/green]")
    console.print("\n[bold]提示:[/bold] 完整的准确率验证需要运行 pipeline 并与预期值比对。")
    console.print("请确保已配置 DeepSeek API Key 后运行:")
    console.print(f"  [cyan]uv run uvoice run --input {golden} --output-dir {output_dir}[/cyan]")


@cli.command()
@click.option("--port", "-p", default=8000, help="Server port")
@click.option("--host", "-h", default="0.0.0.0", help="Server host")
def serve(port, host):
    """Start the FastAPI server."""
    import uvicorn

    console.print(Panel.fit(
        f"[bold]API Server[/bold]\n"
        f"地址: http://{host}:{port}\n"
        f"文档: http://{host}:{port}/docs",
        title="Starting Server",
    ))
    uvicorn.run(
        "src.delivery.api:app",
        host=host,
        port=port,
        reload=True,
        log_level="info",
    )


def main():
    """Entry point for the CLI."""
    cli(obj={})


if __name__ == "__main__":
    main()
