import json
from pathlib import Path

from phases.ideation import IdeationPhase
from phases.experiment_v2 import ExperimentPhaseV2
from phases.writeup import WriteupPhase
from phases.review_v2 import ReviewPhaseV2
from utils.github_manager import GitHubRepo, FetchResult


def test_no_llm_no_mock_must_fail_ideation(tmp_path):
    topic = tmp_path / "topic.md"
    topic.write_text("# T\n\n关键词：a,b", encoding="utf-8")
    phase = IdeationPhase({"ideation": {"allow_mock": False, "require_keywords": True}, "search": {"mode": "disabled"}})
    out = phase.run(topic, tmp_path / "ideas.json", llm_call_func=None)
    assert out["success"] is False


def test_inline_keywords_parser():
    phase = IdeationPhase({})
    info = phase.parse_topic("# X\n关键词：MSAmba, 多模态, 情感分析")
    assert "MSAmba" in info["keywords"]


def test_example_idea_blocks_experiment(tmp_path):
    ideas = tmp_path / "ideas.json"
    ideas.write_text(json.dumps({"ideas": [{"id": 1, "title": "示例", "hypothesis": "x", "method": "y", "keywords": ["k"]}]}, ensure_ascii=False), encoding="utf-8")
    p = ExperimentPhaseV2({"experiment": {"strict_dataset": False}})
    r = p.run(ideas, 1, tmp_path / "exp")
    assert r["success"] is False
    assert "invalid_mock_content" in r["blocking_errors"]


def test_clone_failure_falls_back_to_zip(tmp_path, monkeypatch):
    p = ExperimentPhaseV2({"experiment": {"github": {"zip_fallback": True}}})
    repo = GitHubRepo("o", "n", "u", "d", 0, "python", [], "", "main")
    monkeypatch.setattr(p.github_manager, "search_repositories", lambda *a, **k: [repo])
    monkeypatch.setattr(p.github_manager, "clone_repository", lambda *a, **k: FetchResult(False, "git_clone", None, 2, 120, "x"))
    monkeypatch.setattr(p.github_manager, "download_repo_zip", lambda *a, **k: FetchResult(True, "zip", str(tmp_path / "r"), 1, 120, ""))
    monkeypatch.setattr(p.github_manager, "analyze_repository", lambda *a, **k: type("A", (), {"repo": repo})())
    repos = p.find_github_repositories({"title": "t", "hypothesis": "h", "method": "m", "keywords": ["k"]})
    assert len(repos) >= 1


def test_strict_dataset_blocks_synthetic(tmp_path):
    ideas = tmp_path / "ideas.json"
    ideas.write_text(json.dumps({"ideas": [{"id": 1, "title": "real", "hypothesis": "x", "method": "y", "keywords": ["k"]}]}), encoding="utf-8")
    p = ExperimentPhaseV2({"experiment": {"strict_dataset": True, "allow_synthetic_fallback": False}})
    p.find_github_repositories = lambda idea: []
    p.find_dataset = lambda idea, warnings: None
    r = p.run(ideas, 1, tmp_path / "exp")
    assert "real_dataset_required" in r["blocking_errors"]


def test_synthetic_fallback_marked_invalid_for_paper(tmp_path):
    ideas = tmp_path / "ideas.json"
    ideas.write_text(json.dumps({"ideas": [{"id": 1, "title": "real", "hypothesis": "x", "method": "y", "keywords": ["k"]}]}), encoding="utf-8")
    p = ExperimentPhaseV2({"experiment": {"strict_dataset": False, "allow_synthetic_fallback": True}})
    p.find_github_repositories = lambda idea: []
    p.find_dataset = lambda idea, warnings: None
    r = p.run(ideas, 1, tmp_path / "exp")
    assert r["valid_for_paper"] is False


def test_transformer_random_metrics_forbidden():
    detector = ReviewPhaseV2({"review": {"block_on_high_authenticity_risk": True}}).detector
    findings = detector.analyze("", {"x": "pseudo_score transformer_fallback"})
    assert "pseudo_score" in findings[0].evidence


def test_writeup_blocks_invalid_experiment(tmp_path):
    ideas = tmp_path / "ideas.json"
    ideas.write_text(json.dumps({"ideas": [{"id": 1, "title": "t"}]}), encoding="utf-8")
    summary = tmp_path / "summary.json"
    summary.write_text(json.dumps({"success": False, "valid_for_writeup": False, "blocking_errors": ["e"]}), encoding="utf-8")
    w = WriteupPhase({})
    r = w.run(ideas, 1, summary, tmp_path)
    assert r["success"] is False
    assert (tmp_path / "experiment_failure_report.md").exists()


def test_review_blocks_pseudo_template_metrics(tmp_path):
    paper = tmp_path / "paper.md"
    paper.write_text("template-generated metrics", encoding="utf-8")
    r = ReviewPhaseV2({"review": {"block_on_high_authenticity_risk": True}}).run(paper, tmp_path / "review", None, None)
    assert r["decision"] == "BLOCKED"


def test_full_pipeline_stops_before_paper_when_data_unavailable(tmp_path):
    topic = tmp_path / "topic.md"
    topic.write_text("# t\n关键词：a,b", encoding="utf-8")
    from main import AIResearchAssistant
    assistant = AIResearchAssistant("config.yaml")
    assistant.set_llm_callback(lambda *a, **k: json.dumps({"ideas": [{"id": 1, "title": "t", "hypothesis": "h", "method": "m", "keywords": ["a"]}]}))
    assistant.config["experiment"]["strict_dataset"] = True
    assistant.config["experiment"]["allow_synthetic_fallback"] = False
    assistant.experiment = ExperimentPhaseV2(assistant.config)
    result = assistant.run_full_pipeline(str(topic), str(tmp_path / "out"), 1)
    assert result["success"] is False
    assert not (tmp_path / "out" / "experiment" / "paper.md").exists()
