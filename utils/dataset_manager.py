import json
import datetime
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional

import csv


@dataclass
class DatasetInfo:
    name: str
    source: str
    url: str
    description: str
    size_mb: Optional[float]
    format: str
    task_type: str
    features: List[str]
    target_column: Optional[str]
    download_path: Optional[str] = None
    local_path: Optional[str] = None
    retrieved_at: Optional[str] = None
    relevance_score: float = 0.0


class DatasetManager:
    def __init__(self, work_dir: Optional[str] = None, kaggle_token: Optional[str] = None, hf_token: Optional[str] = None):
        self.work_dir = Path(work_dir) if work_dir else Path.cwd() / "datasets"
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.kaggle_token = kaggle_token
        self.hf_token = hf_token
        self.downloaded_datasets: Dict[str, DatasetInfo] = {}

    def register_local_dataset(self, path: str, name: Optional[str] = None, task_type: str = "classification") -> Optional[DatasetInfo]:
        p = Path(path)
        if not p.exists():
            return None
        ds = DatasetInfo(name=name or p.stem, source="local", url=str(p), description="local dataset", size_mb=None,
                         format=p.suffix.lstrip(".") or "unknown", task_type=task_type, features=[], target_column=None,
                         local_path=str(p), retrieved_at=datetime.datetime.utcnow().isoformat(), relevance_score=1.0)
        self.downloaded_datasets[ds.name] = ds
        self._save_metadata(ds)
        self.profile_dataset(ds.name)
        return ds

    def search_datasets(self, keywords: List[str], task_type: Optional[str] = None, max_results: int = 10) -> List[DatasetInfo]:
        hf = self._search_huggingface(keywords, task_type, max_results)
        kg = self._search_kaggle(keywords, task_type, max_results)
        uci = self._search_uci(keywords, max_results)  # warning only on failure inside
        all_ds = hf + kg + uci
        return sorted(all_ds, key=lambda d: d.relevance_score, reverse=True)[:max_results]

    def _score_relevance(self, text: str, keywords: List[str], task_type: Optional[str]) -> float:
        t = text.lower()
        score = sum(1 for k in keywords if k.lower() in t)
        if task_type and task_type.lower() in t:
            score += 2
        return float(score)

    def _search_huggingface(self, keywords: List[str], task_type: Optional[str], max_results: int) -> List[DatasetInfo]:
        q = " ".join(keywords) or "dataset"
        return [DatasetInfo(name="hf_mock", source="huggingface", url=f"https://huggingface.co/datasets?search={q}", description=q,
                            size_mb=None, format="csv", task_type=task_type or "nlp", features=[], target_column=None,
                            retrieved_at=datetime.datetime.utcnow().isoformat(), relevance_score=self._score_relevance(q, keywords, task_type))]

    def _search_kaggle(self, keywords: List[str], task_type: Optional[str], max_results: int) -> List[DatasetInfo]:
        q = " ".join(keywords) or "dataset"
        return [DatasetInfo(name="kaggle_mock", source="kaggle", url=f"https://www.kaggle.com/datasets?search={q}", description=q,
                            size_mb=None, format="csv", task_type=task_type or "classification", features=[], target_column=None,
                            retrieved_at=datetime.datetime.utcnow().isoformat(), relevance_score=self._score_relevance(q, keywords, task_type)-0.1)]

    def _search_uci(self, keywords: List[str], max_results: int) -> List[DatasetInfo]:
        try:
            return []
        except Exception:
            print("[WARN] UCI 搜索失败，仅作为 warning")
            return []

    def download_dataset(self, dataset: DatasetInfo, target_dir: Optional[Path] = None) -> bool:
        if dataset.source == "local" and dataset.local_path:
            return True
        return False

    def analyze_dataset(self, dataset_name: str) -> Dict:
        return self.profile_dataset(dataset_name)

    def _save_metadata(self, dataset: DatasetInfo):
        ddir = self.work_dir / dataset.name
        ddir.mkdir(parents=True, exist_ok=True)
        (ddir / "source_metadata.json").write_text(json.dumps(asdict(dataset), ensure_ascii=False, indent=2), encoding="utf-8")

    def profile_dataset(self, dataset_name: str) -> Dict:
        ds = self.downloaded_datasets.get(dataset_name)
        if not ds or not ds.local_path:
            return {}
        p = Path(ds.local_path)
        if not p.exists():
            return {}
        ext = p.suffix.lower()
        if ext in {".csv", ".tsv"}:
            sep = "\t" if ext == ".tsv" else ","
            with open(p, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f, delimiter=sep)
                rows = list(reader)
            columns = reader.fieldnames or []
            dtypes = {c: "str" for c in columns}
            profile = {"rows": len(rows), "columns": columns, "dtypes": dtypes}
        elif ext == ".jsonl":
            rows = [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
            columns = sorted(set().union(*[set(r.keys()) for r in rows])) if rows else []
            profile = {"rows": len(rows), "columns": columns, "dtypes": {c: "unknown" for c in columns}}
        elif ext == ".parquet":
            return {}
        else:
            return {}
        ddir = self.work_dir / dataset_name
        ddir.mkdir(parents=True, exist_ok=True)
        (ddir / "dataset_profile.json").write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
        (ddir / "schema.json").write_text(json.dumps(profile["dtypes"], ensure_ascii=False, indent=2), encoding="utf-8")
        if not (ddir / "source_metadata.json").exists():
            self._save_metadata(ds)
        return profile

    def generate_data_loading_code(self, dataset_name: str) -> str:
        ds = self.downloaded_datasets.get(dataset_name)
        if not ds or not ds.local_path:
            return "def load_data():\n    raise RuntimeError('No local dataset configured')\n"
        return f"""import pandas as pd\n\ndef load_data():\n    return pd.read_csv(r'{ds.local_path}')\n"""
