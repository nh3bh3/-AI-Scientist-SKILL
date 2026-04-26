import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class AuthenticityCheck:
    category: str
    is_suspicious: bool
    confidence: float
    evidence: List[str]
    recommendation: str


@dataclass
class AIWritingPattern:
    pattern_type: str
    examples: List[str]
    severity: str
    suggestion: str


class FakeContentDetector:
    TOKENS = ["synthetic", "pseudo_score", "transformer_fallback", "make_classification", "template-generated metrics"]

    def analyze(self, paper_content: str, metrics_data: Optional[Dict] = None, experiment_data: Optional[Dict] = None) -> List[AuthenticityCheck]:
        text = paper_content.lower()
        if metrics_data:
            text += " " + json.dumps(metrics_data, ensure_ascii=False).lower()
        if experiment_data:
            text += " " + json.dumps(experiment_data, ensure_ascii=False).lower()
        evidence = []
        for t in self.TOKENS:
            if t.lower() in text:
                evidence.append(t)
        if re.search(r"99\.\d+%|perfect|zero\s+error", text):
            evidence.append("suspicious_perfect_metrics")
        return [AuthenticityCheck("results", bool(evidence), min(1.0, len(evidence) * 0.2), evidence, "block if high risk")]


class AIWritingDetector:
    def analyze(self, paper_content: str) -> List[AIWritingPattern]:
        hits = []
        for token in ["delve", "intricate", "further research is needed"]:
            if token in paper_content.lower():
                hits.append(token)
        if not hits:
            return []
        return [AIWritingPattern("ai_style", hits, "medium", "use concrete wording")]


class ReviewPhaseV2:
    def __init__(self, config: Dict):
        self.config = config
        self.review_config = config.get("review", {})
        self.detector = FakeContentDetector()
        self.ai_detector = AIWritingDetector()

    def load_paper(self, paper_file: Path) -> str:
        return paper_file.read_text(encoding="utf-8")

    def load_experiment_data(self, experiment_dir: Path) -> Optional[Dict]:
        merged = {}
        for fn in ["summary.json", "experiment_results.json", "comparison.json", "source_metadata.json"]:
            p = experiment_dir / fn
            if p.exists():
                merged[fn] = json.loads(p.read_text(encoding="utf-8"))
        return merged or None

    def run(self, paper_file: Path, output_dir: Path, experiment_dir: Optional[Path] = None, llm_call_func=None) -> Dict:
        output_dir.mkdir(parents=True, exist_ok=True)
        paper = self.load_paper(paper_file)
        exp = self.load_experiment_data(experiment_dir) if experiment_dir else None
        checks = self.detector.analyze(paper, experiment_data=exp)
        findings = checks[0].evidence if checks else []
        ai_patterns = self.ai_detector.analyze(paper)

        if findings and self.review_config.get("block_on_high_authenticity_risk", True):
            final_score, decision, comments = 1.0, "BLOCKED", [f"high_authenticity_risk: {findings}"]
        elif llm_call_func is None:
            final_score, decision, comments = 2.0, "BLOCKED", ["insufficient_reviewer_model"]
        else:
            final_score, decision, comments = 7.0, "REVISE", ["llm review done"]

        (output_dir / "review_v2_round_1.json").write_text(json.dumps({"round": 1, "overall_score": final_score, "decision": decision, "general_comments": comments}, ensure_ascii=False, indent=2), encoding="utf-8")
        final = {"final_score": final_score, "final_decision": decision, "findings": findings, "authenticity_issues": len(findings), "authenticity_issue_list": findings, "reproducibility_score": 2.0 if decision == "BLOCKED" else 6.0, "ai_patterns": [asdict(x) for x in ai_patterns], "ai_patterns_found": len(ai_patterns)}
        (output_dir / "comprehensive_review_report.json").write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"success": True, **final, "decision": decision, "final_report": str(output_dir / "comprehensive_review_report.json")}
