"""Console reporter for eval reports."""

from evals.runner import EvalReport


def print_report(report: EvalReport) -> None:
    passed = sum(1 for r in report.results if r.passed)
    total = len(report.results)
    print(f"[{report.dataset}] {passed}/{total} passed ({report.pass_rate:.0%})")
    for r in report.results:
        mark = "PASS" if r.passed else "FAIL"
        line = f"  {mark} {r.case_id}"
        if not r.passed and r.reason:
            line += f" — {r.reason}"
        print(line)
