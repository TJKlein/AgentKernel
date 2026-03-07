"""Report generation for benchmark results."""

from typing import Dict, List, Any
import json
from pathlib import Path

from .tasks.schema import BenchmarkMetrics, TaskResult

class ReportGenerator:
    """Generates visual and persistent reports for benchmarks."""
    
    @staticmethod
    def markdown_report(metrics: BenchmarkMetrics, backend: str, results: List[TaskResult], approach: str = "ptc") -> str:
        """Generate an agent-focused markdown report for a single backend."""
        lines = []
        
        # Title with approach indication
        if approach == "both":
            lines.append(f"# PTC-Bench: Dual Approach Report ({backend.upper()})")
            lines.append("")
            lines.append("*Comparing Programmatic Tool Calling (PTC) vs Function Calling (FC) on the same tasks*")
        elif approach == "function_calling":
            lines.append(f"# PTC-Bench: Function Calling Report ({backend.upper()})")
            lines.append("")
            lines.append("*Evaluating traditional JSON tool calling approach*")
        else:
            lines.append(f"# PTC-Bench: Programmatic Tool Calling Report ({backend.upper()})")
            lines.append("")
            lines.append("*Evaluating code-first tool calling approach*")
        
        lines.append("")
        
        # Show approach breakdown if both were run
        if approach == "both" and metrics.approach_breakdown and len(metrics.approach_breakdown) >= 2:
            lines.append(ReportGenerator.approach_comparison_report(metrics))
            lines.append("")
            lines.append("---")
            lines.append("")
        
        # Agent-Focused Summary
        lines.append("## Agent Performance Summary")
        lines.append(f"- **Task Success Rate**: {metrics.pass_rate*100:.1f}% ({metrics.passed_tasks}/{metrics.attempted_tasks} attempted, {metrics.skipped_tasks} skipped)")
        lines.append(f"- **Avg Time-to-Success**: {metrics.avg_time_to_success:.2f}s (includes LLM generation)")
        lines.append(f"- **Avg Iterations Needed**: {metrics.avg_iterations:.1f}")
        if metrics.avg_llm_generation_time > 0:
            lines.append(f"- **Avg LLM Generation Time**: {metrics.avg_llm_generation_time:.2f}s")
        lines.append(f"- **Execution Time (substrate)**: {metrics.avg_execution_time:.2f}s")
        lines.append(f"- **P95 Execution Time**: {metrics.p95_execution_time:.2f}s")
        if metrics.error_count > 0 or metrics.timeout_count > 0:
            lines.append(f"- **Errors/Timeouts**: {metrics.error_count} / {metrics.timeout_count}")
        
        # Show cost if available
        if metrics.total_cost > 0:
            lines.append(f"- **Total Cost**: ${metrics.total_cost:.4f} (avg ${metrics.avg_cost:.4f} per task)")
        
        lines.append("")
        
        # Category Breakdown (Agent-focused)
        lines.append("## Category Breakdown (Agent Success Rates)")
        lines.append("| Category | Tasks | Success | Skipped | Success Rate | Avg TTS |")
        lines.append("|----------|-------|---------|---------|--------------|---------|")
        for cat, data in metrics.category_breakdown.items():
            rate = data['pass_rate'] * 100
            lines.append(f"| {cat} | {data['total']} | {data['passed']} | {data['skipped']} | {rate:.1f}% | {data['avg_time']:.2f}s |")
        lines.append("")
        lines.append("*Success Rate = % of tasks where agent-generated code passed validation*")
        lines.append("")
        
        # Difficulty Breakdown
        lines.append("## Difficulty Breakdown")
        lines.append("| Difficulty | Total | Passed | Skipped | Pass Rate | Avg Time |")
        lines.append("|------------|-------|--------|---------|-----------|----------|")
        for diff, data in metrics.difficulty_breakdown.items():
            rate = data['pass_rate'] * 100
            lines.append(f"| {diff} | {data['total']} | {data['passed']} | {data['skipped']} | {rate:.1f}% | {data['avg_time']:.2f}s |")
        lines.append("")
        
        # Failed/Skipped Details (Agent-focused)
        failures = [r for r in results if not r.success and not r.skipped]
        if failures:
            lines.append("## Agent Task Failures")
            lines.append("")
            lines.append("Tasks where the LLM-generated code failed validation or execution:")
            lines.append("")
            for f in failures[:10]: # limit to 10
                reason = f.error if f.error else f.validation.get("error", "Unknown")
                error_type = "Execution" if "runtime" in str(reason).lower() else "Validation"
                lines.append(f"- **{f.task_id}** ({f.category}): [{error_type}] {str(reason)[:60]}...")
            if len(failures) > 10:
                lines.append(f"- *...and {len(failures) - 10} more.*")
            lines.append("")
                
        return "\n".join(lines)
        
    @staticmethod
    def save_report(report_str: str, path: str):
        """Save a report to a file."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(report_str, encoding="utf-8")
    
    @staticmethod
    def approach_comparison_report(metrics: BenchmarkMetrics) -> str:
        """Generate a PTC vs Function Calling comparison report.
        
        This is the core report for PTC-Bench showing empirical comparison
        between Programmatic Tool Calling (code-first) and traditional
        Function Calling (JSON-first).
        """
        lines = []
        lines.append("# PTC-Bench: PTC vs Function Calling Comparison")
        lines.append("")
        lines.append("*Empirical comparison of Programmatic Tool Calling vs traditional Function Calling*")
        lines.append("")
        
        # Check if we have approach breakdown
        if not metrics.approach_breakdown or len(metrics.approach_breakdown) < 2:
            lines.append("## Note")
            lines.append("")
            lines.append("Run with `--approach both` to see PTC vs FC comparison on the same tasks.")
            lines.append("")
            return "\n".join(lines)
        
        # Extract PTC and FC data
        ptc_data = metrics.approach_breakdown.get('ptc', {})
        fc_data = metrics.approach_breakdown.get('function_calling', {})
        
        if not ptc_data or not fc_data:
            lines.append("## Note")
            lines.append("")
            lines.append("Both PTC and FC approaches must be run for comparison.")
            lines.append("Current results only show: " + ", ".join(metrics.approach_breakdown.keys()))
            lines.append("")
            return "\n".join(lines)
        
        # Summary table
        lines.append("## Summary Comparison")
        lines.append("")
        lines.append("| Metric | Function Calling (FC) | Programmatic Tool Calling (PTC) | Winner |")
        lines.append("|--------|----------------------|--------------------------------|--------|")
        
        # Pass rate
        fc_pass = fc_data.get('pass_rate', 0) * 100
        ptc_pass = ptc_data.get('pass_rate', 0) * 100
        winner_pass = "PTC" if ptc_pass > fc_pass else "FC" if fc_pass > ptc_pass else "Tie"
        lines.append(f"| Success Rate | {fc_pass:.1f}% | {ptc_pass:.1f}% | **{winner_pass}** |")
        
        # Execution time
        fc_time = fc_data.get('avg_time', 0)
        ptc_time = ptc_data.get('avg_time', 0)
        if ptc_time > 0 and fc_time > 0:
            speedup = fc_time / ptc_time
            winner_time = "PTC" if ptc_time < fc_time else "FC"
            lines.append(f"| Avg Time | {fc_time:.2f}s | {ptc_time:.2f}s | **{winner_time}** ({speedup:.2f}x) |")
        
        # Cost (if available)
        fc_cost = fc_data.get('avg_cost', 0)
        ptc_cost = ptc_data.get('avg_cost', 0)
        if fc_cost > 0 or ptc_cost > 0:
            if ptc_cost > 0 and fc_cost > 0:
                cost_ratio = fc_cost / ptc_cost
                winner_cost = "PTC" if ptc_cost < fc_cost else "FC"
                lines.append(f"| Avg Cost | ${fc_cost:.4f} | ${ptc_cost:.4f} | **{winner_cost}** ({cost_ratio:.1f}x cheaper) |")
        
        # LLM calls (FC-specific)
        fc_llm_calls = fc_data.get('avg_llm_calls', 0)
        ptc_llm_calls = ptc_data.get('avg_llm_calls', 0)
        if fc_llm_calls > 0:
            lines.append(f"| Avg LLM Calls | {fc_llm_calls:.1f} | {ptc_llm_calls:.1f} | - |")
        
        # Tool calls (FC-specific)
        fc_tool_calls = fc_data.get('avg_tool_calls', 0)
        ptc_tool_calls = ptc_data.get('avg_tool_calls', 0)
        if fc_tool_calls > 0:
            lines.append(f"| Avg Tool Calls | {fc_tool_calls:.1f} | {ptc_tool_calls:.1f} | - |")
        
        # Retries
        fc_retries = fc_data.get('avg_retries', 0)
        ptc_retries = ptc_data.get('avg_retries', 0)
        winner_retries = "PTC" if ptc_retries < fc_retries else "FC" if fc_retries < ptc_retries else "Tie"
        lines.append(f"| Avg Retries | {fc_retries:.1f} | {ptc_retries:.1f} | **{winner_retries}** |")
        
        lines.append("")
        
        # Key findings
        lines.append("## Key Findings")
        lines.append("")
        
        findings = []
        if ptc_pass > fc_pass + 5:
            findings.append(f"- **PTC has higher success rate**: +{ptc_pass - fc_pass:.1f} percentage points")
        elif fc_pass > ptc_pass + 5:
            findings.append(f"- **FC has higher success rate**: +{fc_pass - ptc_pass:.1f} percentage points")
        
        if ptc_time > 0 and fc_time > 0:
            if ptc_time < fc_time * 0.8:
                speedup = fc_time / ptc_time
                findings.append(f"- **PTC is faster**: {speedup:.1f}x speedup for multi-step workflows")
            elif fc_time < ptc_time * 0.8:
                slowdown = ptc_time / fc_time
                findings.append(f"- **FC is faster**: {slowdown:.1f}x faster for simple tasks")
        
        if fc_cost > 0 and ptc_cost > 0 and ptc_cost < fc_cost * 0.8:
            savings = (fc_cost - ptc_cost) / fc_cost * 100
            findings.append(f"- **PTC is more cost-effective**: {savings:.0f}% cheaper ({fc_cost/ptc_cost:.1f}x)")
        
        if ptc_retries < fc_retries * 0.8:
            findings.append(f"- **PTC handles errors better**: Fewer retries needed ({fc_retries:.1f} vs {ptc_retries:.1f})")
        
        if not findings:
            findings.append("- Results are close between both approaches for the tested tasks")
        
        for finding in findings:
            lines.append(finding)
        
        lines.append("")
        
        # TL;DR
        lines.append("## TL;DR")
        lines.append("")
        
        # Determine overall winner based on task characteristics
        if ptc_time > fc_time * 1.2:
            lines.append("- **For simple tasks**: FC wins (lower latency, no sandbox overhead)")
            lines.append("- **For complex workflows**: Test with `--approach both` on multi-step tasks")
        elif ptc_pass > fc_pass and ptc_time < fc_time:
            lines.append("- **PTC wins for these tasks**: Faster AND more reliable")
        elif fc_pass > ptc_pass and fc_time < ptc_time:
            lines.append("- **FC wins for these tasks**: Faster AND more reliable")
        else:
            lines.append("- **Trade-offs exist**: Choose based on your specific requirements")
        
        lines.append("")
        lines.append("Run `python -m benchmarks run --approach both --categories ptc` for a full comparison.")
        lines.append("")
        
        return "\n".join(lines)

    @staticmethod
    def comparison_matrix(control_metrics: BenchmarkMetrics, control_name: str, test_metrics: BenchmarkMetrics, test_name: str, format: str = "markdown") -> str:
        """Generate a comparison matrix between two backends."""
        lines = []
        
        # Calculate deltas
        speedup = control_metrics.avg_execution_time / test_metrics.avg_execution_time if test_metrics.avg_execution_time > 0 else 0
        pass_diff = test_metrics.pass_rate - control_metrics.pass_rate
        
        if format == "latex":
            lines.append(f"% Benchmark Comparison: {control_name.upper()} vs {test_name.upper()}")
            lines.append(r"\begin{table}[h]")
            lines.append(r"\centering")
            lines.append(r"\begin{tabular}{l c c c}")
            lines.append(r"\toprule")
            lines.append(f"\\textbf{{Metric}} & \\textbf{{{control_name.title()}}} & \\textbf{{{test_name.title()}}} & \\textbf{{Delta}} \\\\")
            lines.append(r"\midrule")
            lines.append(f"Pass Rate & {control_metrics.pass_rate*100:.1f}\\% & {test_metrics.pass_rate*100:.1f}\\% & {pass_diff*100:+.1f} ppt \\\\")
            lines.append(f"Avg Time & {control_metrics.avg_execution_time:.3f}s & {test_metrics.avg_execution_time:.3f}s & {speedup:.2f}x speedup \\\\")
            lines.append(f"P95 Time & {control_metrics.p95_execution_time:.3f}s & {test_metrics.p95_execution_time:.3f}s & - \\\\")
            lines.append(r"\bottomrule")
            lines.append(r"\end{tabular}")
            lines.append(f"\\caption{{Performance comparison between {control_name} and {test_name}.}}")
            lines.append(r"\end{table}")
            
        elif format == "csv":
            lines.append("Metric,Control,Test,Delta")
            lines.append(f"Pass Rate,{control_metrics.pass_rate*100:.1f}%,{test_metrics.pass_rate*100:.1f}%,{pass_diff*100:+.1f} ppt")
            lines.append(f"Avg Time (s),{control_metrics.avg_execution_time:.3f},{test_metrics.avg_execution_time:.3f},{speedup:.2f}x speedup")
            lines.append(f"P95 Time (s),{control_metrics.p95_execution_time:.3f},{test_metrics.p95_execution_time:.3f},-")
            
            lines.append("")
            lines.append("Category,Control Pass,Test Pass,Control Time,Test Time")
            for cat in control_metrics.category_breakdown.keys():
                c_data = control_metrics.category_breakdown.get(cat, {'pass_rate': 0, 'avg_time': 0})
                t_data = test_metrics.category_breakdown.get(cat, {'pass_rate': 0, 'avg_time': 0})
                lines.append(f"{cat},{c_data['pass_rate']*100:.1f}%,{t_data['pass_rate']*100:.1f}%,{c_data['avg_time']:.3f},{t_data['avg_time']:.3f}")
                
        else:
            # Markdown
            lines.append(f"# Comparison Matrix: `{control_name}` vs `{test_name}`")
            lines.append("")
            lines.append(f"**Speedup:** `{speedup:.2f}x` | **Pass Rate Delta:** `{pass_diff*100:+.1f} ppt`")
            lines.append("")
            lines.append("| Metric | Control | Test | Delta |")
            lines.append("|---|---|---|---|")
            lines.append(f"| Pass Rate | {control_metrics.pass_rate*100:.1f}% | {test_metrics.pass_rate*100:.1f}% | {pass_diff*100:+.1f} ppt |")
            lines.append(f"| Avg Time  | {control_metrics.avg_execution_time:.3f}s | {test_metrics.avg_execution_time:.3f}s | {speedup:.2f}x speedup |")
            lines.append(f"| P95 Time  | {control_metrics.p95_execution_time:.3f}s | {test_metrics.p95_execution_time:.3f}s | - |")
            lines.append("")
            lines.append("### Category Breakdown Comparison")
            lines.append("| Category | Control Pass | Test Pass | Control Time | Test Time |")
            lines.append("|---|---|---|---|---|")
            for cat in control_metrics.category_breakdown.keys():
                c_data = control_metrics.category_breakdown.get(cat, {'pass_rate': 0, 'avg_time': 0})
                t_data = test_metrics.category_breakdown.get(cat, {'pass_rate': 0, 'avg_time': 0})
                lines.append(f"| {cat.title()} | {c_data['pass_rate']*100:.1f}% | {t_data['pass_rate']*100:.1f}% | {c_data['avg_time']:.3f}s | {t_data['avg_time']:.3f}s |")
                
        return "\n".join(lines)
