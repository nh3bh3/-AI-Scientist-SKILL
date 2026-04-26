import json
from pathlib import Path
from typing import Dict, Optional


class WriteupPhase:
    def __init__(self, config: Dict):
        self.config = config
        self.writeup_config = config.get("writeup", {})

    def load_experiment_results(self, summary_file: Path) -> Dict:
        return json.loads(summary_file.read_text(encoding="utf-8"))

    def load_idea(self, ideas_file: Path, idea_id: int) -> Optional[Dict]:
        data = json.loads(ideas_file.read_text(encoding="utf-8"))
        for i in data.get("ideas", []):
            if i.get("id") == idea_id:
                return i
        return data.get("ideas", [None])[0]

    def validate_writeup_inputs(self, idea: Dict, results: Dict) -> Dict:
        valid_for_writeup = bool(results.get("valid_for_writeup", results.get("success")))
        valid_for_paper = bool(results.get("valid_for_paper", False))
        return {
            "ok": bool(idea) and valid_for_writeup,
            "valid_for_writeup": valid_for_writeup,
            "valid_for_paper": valid_for_paper,
            "blocking_errors": results.get("blocking_errors", []),
        }

    def run(self, ideas_file: Path, idea_id: int, summary_file: Path, output_dir: Path, llm_call_func=None) -> Dict:
        output_dir.mkdir(parents=True, exist_ok=True)
        idea = self.load_idea(ideas_file, idea_id)
        results = self.load_experiment_results(summary_file)
        check = self.validate_writeup_inputs(idea, results)

        if not check["ok"]:
            fail = output_dir / "experiment_failure_report.md"
            fail.write_text(f"# Experiment Failure Report\n\nblocking_errors: {check['blocking_errors']}\n", encoding="utf-8")
            return {"success": False, "valid_for_writeup": False, "valid_for_paper": False, "report": str(fail)}

        if not check["valid_for_paper"]:
            draft = output_dir / "draft_paper_unvalidated.md"
            draft.write_text("# Draft Paper (Unvalidated)\n\n参考文献未生成\n", encoding="utf-8")
            return {"success": True, "valid_for_writeup": True, "valid_for_paper": False, "paper_file": str(draft)}

        paper = output_dir / "paper.md"
        citations = idea.get("related_work", []) if isinstance(idea.get("related_work", []), list) else []
        refs = "\n".join([f"- {c}" for c in citations]) if citations else "参考文献未生成"
        paper.write_text(f"# {idea.get('title','Research')}\n\n## References\n{refs}\n", encoding="utf-8")
        return {"success": True, "valid_for_writeup": True, "valid_for_paper": True, "paper_file": str(paper)}
