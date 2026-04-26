import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Optional, Callable

from phases.ideation import IdeationPhase
from phases.experiment_v2 import ExperimentPhaseV2
from phases.writeup import WriteupPhase
from phases.review_v2 import ReviewPhaseV2


class AIResearchAssistant:
    def __init__(self, config_path: Optional[str] = None):
        self.config = self._load_config_static(config_path)
        self.llm_call_func: Optional[Callable] = None
        self.ideation = IdeationPhase(self.config)
        self.experiment = ExperimentPhaseV2(self.config)
        self.writeup = WriteupPhase(self.config)
        self.review = ReviewPhaseV2(self.config)

    @staticmethod
    def _load_config_static(config_path: Optional[str]) -> Dict:
        try:
            import yaml  # type: ignore
        except Exception:
            yaml = None
        target = Path(config_path) if config_path and Path(config_path).exists() else Path("config.yaml")
        if yaml and target.exists():
            return yaml.safe_load(target.read_text(encoding="utf-8"))
        return {
            "ideation": {"allow_mock": False, "require_keywords": True},
            "experiment": {"strict_dataset": True, "strict_baseline": False, "allow_synthetic_fallback": False, "github": {"zip_fallback": True}, "dataset": {"local_path": None}},
            "writeup": {"allow_draft_without_valid_experiment": False},
            "review": {"block_on_high_authenticity_risk": True},
            "search": {"enabled": True, "mode": "real"},
        }

    def set_llm_callback(self, callback: Callable):
        self.llm_call_func = callback

    def run_full_pipeline(self, topic_file: str, output_dir: str, idea_id: int = 1) -> Dict:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        res = {"phases": {}, "success": True, "blocking_errors": []}

        ideas_file = out / "ideas.json"
        r1 = self.ideation.run(Path(topic_file), ideas_file, self.llm_call_func)
        res["phases"]["ideation"] = r1
        if not r1.get("success"):
            res["success"] = False
            res["blocking_errors"].append("ideation_failed")
            (out / "pipeline_record.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
            return res

        exp_dir = out / "experiment"
        r2 = self.experiment.run(ideas_file, idea_id, exp_dir, self.llm_call_func)
        res["phases"]["experiment"] = r2
        res["blocking_errors"].extend(r2.get("blocking_errors", []))
        if (not r2.get("success")) or (not r2.get("valid_for_writeup", False)):
            res["success"] = False
            (out / "pipeline_record.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
            return res

        summary_file = exp_dir / "summary.json"
        r3 = self.writeup.run(ideas_file, idea_id, summary_file, exp_dir, self.llm_call_func)
        res["phases"]["writeup"] = r3
        if not r3.get("valid_for_paper", False):
            res["success"] = False
            res["blocking_errors"].append("invalid_for_writeup_or_paper")
            (out / "pipeline_record.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
            return res

        paper_file = Path(r3.get("paper_file"))
        r4 = self.review.run(paper_file, out / "review", exp_dir, self.llm_call_func)
        res["phases"]["review"] = r4
        (out / "pipeline_record.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        return res


def mock_llm_call(prompt: str, model: str = "gpt-4o") -> str:
    return json.dumps({"ideas": [{"id": 1, "title": "mock_mode=true", "hypothesis": "mock", "method": "mock", "keywords": ["mock"]}]}, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["full", "ideation", "experiment", "writeup", "review"], default="full")
    parser.add_argument("--topic")
    parser.add_argument("--ideas")
    parser.add_argument("--idea-id", type=int, default=1)
    parser.add_argument("--summary")
    parser.add_argument("--paper")
    parser.add_argument("--experiment-dir")
    parser.add_argument("--output", "-o", default="./research_output")
    parser.add_argument("--config", "-c", default="config.yaml")
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--allow-draft-writeup", action="store_true")
    parser.add_argument("--local-dataset")
    parser.add_argument("--strict-dataset", dest="strict_dataset", action="store_true")
    parser.add_argument("--no-strict-dataset", dest="strict_dataset", action="store_false")
    parser.add_argument("--strict-baseline", dest="strict_baseline", action="store_true")
    parser.add_argument("--no-strict-baseline", dest="strict_baseline", action="store_false")
    parser.add_argument("--offline", action="store_true")
    parser.set_defaults(strict_dataset=None, strict_baseline=None)
    args = parser.parse_args()

    assistant = AIResearchAssistant(args.config)
    if args.strict:
        assistant.config.setdefault("experiment", {})["strict_dataset"] = True
        assistant.config.setdefault("experiment", {})["strict_baseline"] = True
    if args.local_dataset:
        assistant.config.setdefault("experiment", {}).setdefault("dataset", {})["local_path"] = args.local_dataset
    if args.strict_dataset is not None:
        assistant.config.setdefault("experiment", {})["strict_dataset"] = args.strict_dataset
    if args.strict_baseline is not None:
        assistant.config.setdefault("experiment", {})["strict_baseline"] = args.strict_baseline
    if args.allow_draft_writeup:
        assistant.config.setdefault("writeup", {})["allow_draft_without_valid_experiment"] = True
    if args.offline:
        assistant.config.setdefault("search", {})["enabled"] = False

    assistant.ideation = IdeationPhase(assistant.config)
    assistant.experiment = ExperimentPhaseV2(assistant.config)
    assistant.writeup = WriteupPhase(assistant.config)
    assistant.review = ReviewPhaseV2(assistant.config)

    if args.mock:
        assistant.set_llm_callback(mock_llm_call)

    if args.phase == "full":
        result = assistant.run_full_pipeline(args.topic, args.output, args.idea_id)
    elif args.phase == "ideation":
        result = assistant.ideation.run(Path(args.topic), Path(args.output) / "ideas.json", assistant.llm_call_func)
    elif args.phase == "experiment":
        result = assistant.experiment.run(Path(args.ideas), args.idea_id, Path(args.output), assistant.llm_call_func)
    elif args.phase == "writeup":
        result = assistant.writeup.run(Path(args.ideas), args.idea_id, Path(args.summary), Path(args.output), assistant.llm_call_func)
    else:
        result = assistant.review.run(Path(args.paper), Path(args.output), Path(args.experiment_dir) if args.experiment_dir else None, assistant.llm_call_func)

    if args.mock and isinstance(result, dict):
        result["mock_mode"] = True
        out = Path(args.output)
        out.mkdir(parents=True, exist_ok=True)
        rec = out / "pipeline_record.json"
        if rec.exists():
            data = json.loads(rec.read_text(encoding="utf-8"))
            data["mock_mode"] = True
            rec.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())
