import json
import re
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict


@dataclass
class ResearchIdea:
    id: int
    title: str
    hypothesis: str
    method: str
    expected_result: str
    contribution: str
    feasibility: float
    novelty: float
    significance: float
    related_work: List[str]
    keywords: List[str]

    def to_dict(self) -> Dict:
        return asdict(self)


class IdeationPhase:
    def __init__(self, config: Dict):
        self.config = config
        self.models = config.get("models", {})
        self.search_config = config.get("search", {})
        self.ideation_config = config.get("ideation", {})

    def parse_topic(self, topic_content: str) -> Dict:
        title_match = re.search(r"^#\s+(.+)$", topic_content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else "未命名研究"

        keywords = []
        inline_patterns = [r"(?:关键词|关键字|Keywords|Tags)\s*[：:]\s*([^\n]+)"]
        for p in inline_patterns:
            m = re.search(p, topic_content, re.IGNORECASE)
            if m:
                keywords.extend([k.strip() for k in re.split(r"[,，、]", m.group(1)) if k.strip()])

        sec_match = re.search(r"##?\s*(关键词|关键字|Keywords|Tags)\s*\n+([^#]+)", topic_content, re.IGNORECASE)
        if sec_match:
            keywords.extend([k.strip() for k in re.split(r"[,，、]", sec_match.group(2)) if k.strip()])

        background = ""
        bg_match = re.search(r"##?\s*(研究背景|背景|Background)\s*\n+([^#]+)", topic_content, re.IGNORECASE)
        if bg_match:
            background = bg_match.group(2).strip()

        objectives = ""
        obj_match = re.search(r"##?\s*(研究目标|目标|预期目标|Objectives)\s*\n+([^#]+)", topic_content, re.IGNORECASE)
        if obj_match:
            objectives = obj_match.group(2).strip()

        tech_terms = ["MSAmba", "Mamba", "多模态", "情感分析", "multimodal", "sentiment", "transformer"]
        joined = f"{title} {background}"
        for t in tech_terms:
            if re.search(re.escape(t), joined, re.IGNORECASE):
                keywords.append(t)

        dedup = []
        seen = set()
        for k in keywords:
            kl = k.lower()
            if kl not in seen:
                seen.add(kl)
                dedup.append(k)

        return {"title": title, "keywords": dedup, "background": background, "objectives": objectives, "raw_content": topic_content}

    def search_literature(self, topic_info: Dict) -> List[Dict]:
        mode = self.search_config.get("mode", "real")
        if mode == "disabled" or not self.search_config.get("enabled", True):
            return []
        if mode == "mock":
            return [{"title": "mock literature", "url": "mock://literature", "authors": [], "year": 2024, "venue": "mock", "abstract": "mock"}]
        return []

    def generate_ideas_prompt(self, topic_info: Dict, literature: List[Dict]) -> str:
        return f"topic={topic_info.get('title')} keywords={','.join(topic_info.get('keywords', []))}"

    def _contains_mock_text(self, text: str) -> bool:
        return bool(re.search(r"示例|mock|placeholder", text, re.IGNORECASE))

    def parse_ideas_response(self, response: str) -> Dict:
        json_match = re.search(r"```json\s*(\{.+\})\s*```", response, re.DOTALL)
        json_str = json_match.group(1) if json_match else response
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return {"success": False, "ideas": [], "invalid_mock_content": False, "error": "invalid_json"}

        ideas: List[ResearchIdea] = []
        invalid_mock_content = False
        for idea_data in data.get("ideas", []):
            required = ["title", "hypothesis", "method", "keywords"]
            if any(not idea_data.get(k) for k in required):
                return {"success": False, "ideas": [], "invalid_mock_content": False, "error": "missing_required_fields"}
            serialized = json.dumps(idea_data, ensure_ascii=False)
            if self._contains_mock_text(serialized):
                invalid_mock_content = True
            ideas.append(ResearchIdea(
                id=idea_data.get("id", len(ideas)+1), title=idea_data["title"], hypothesis=idea_data["hypothesis"],
                method=idea_data["method"], expected_result=idea_data.get("expected_result", ""), contribution=idea_data.get("contribution", ""),
                feasibility=float(idea_data.get("feasibility", 0.0)), novelty=float(idea_data.get("novelty", 0.0)), significance=float(idea_data.get("significance", 0.0)),
                related_work=idea_data.get("related_work", []), keywords=idea_data.get("keywords", [])
            ))
        return {"success": len(ideas) > 0, "ideas": ideas, "invalid_mock_content": invalid_mock_content}

    def rank_ideas(self, ideas: List[ResearchIdea]) -> List[ResearchIdea]:
        return sorted(ideas, key=lambda x: x.feasibility * 0.3 + x.novelty * 0.4 + x.significance * 0.3, reverse=True)

    def save_ideas(self, ideas: List[ResearchIdea], output_path: Path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({"total_ideas": len(ideas), "ideas": [i.to_dict() for i in ideas]}, f, ensure_ascii=False, indent=2)

    def run(self, topic_file: Path, output_file: Path, llm_call_func=None) -> Dict:
        topic_info = self.parse_topic(topic_file.read_text(encoding="utf-8"))
        if self.ideation_config.get("require_keywords", False) and not topic_info.get("keywords"):
            return {"success": False, "error": "keywords_required"}
        literature = self.search_literature(topic_info)
        allow_mock = bool(self.ideation_config.get("allow_mock", False))
        if llm_call_func is None and not allow_mock:
            return {"success": False, "error": "llm_call_func_required", "invalid_mock_content": False}

        if llm_call_func is None and allow_mock:
            response = json.dumps({"ideas": [{"id": 1, "title": "mock idea", "hypothesis": "mock hypothesis", "method": "mock", "keywords": ["mock"]}]}, ensure_ascii=False)
        else:
            response = llm_call_func(self.generate_ideas_prompt(topic_info, literature), model=self.models.get("ideation", "gpt-4o"))

        parsed = self.parse_ideas_response(response)
        if not parsed["success"]:
            return parsed
        ranked = self.rank_ideas(parsed["ideas"])
        self.save_ideas(ranked, output_file)
        return {"success": True, "total_ideas": len(ranked), "invalid_mock_content": parsed["invalid_mock_content"], "output_file": str(output_file)}
