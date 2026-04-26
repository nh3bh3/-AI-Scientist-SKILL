import json
import shutil
import subprocess
import urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class GitHubRepo:
    owner: str
    name: str
    url: str
    description: str
    stars: int
    language: str
    topics: List[str]
    last_updated: str
    default_branch: str = "main"

    @property
    def clone_url(self) -> str:
        return f"https://github.com/{self.owner}/{self.name}.git"


@dataclass
class FetchResult:
    success: bool
    method: str
    local_path: Optional[str]
    retries: int
    timeout: int
    stderr: str = ""


@dataclass
class RepoAnalysis:
    repo: GitHubRepo
    local_path: Path
    structure: Dict
    has_requirements: bool
    has_setup_py: bool
    has_pyproject: bool
    main_entry_points: List[str]
    data_directories: List[str]
    notebooks: List[str]
    python_files: List[str]
    relevance_score: float
    runnable_entry_valid: bool


class GitHubManager:
    def __init__(self, work_dir: Optional[str] = None, github_token: Optional[str] = None, clone_retries: int = 2, clone_timeout: int = 120):
        self.work_dir = Path(work_dir) if work_dir else Path.cwd() / "github_repos"
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.github_token = github_token
        self.clone_retries = clone_retries
        self.clone_timeout = clone_timeout

    def search_repositories(self, query: str, language: str = "python", sort: str = "stars", max_results: int = 10) -> List[GitHubRepo]:
        # offline-friendly fallback: return empty when API unavailable
        url = f"https://api.github.com/search/repositories?q={query}+language:{language}&sort={sort}&order=desc&per_page={min(max_results,30)}"
        headers = {"Accept": "application/vnd.github+json"}
        if self.github_token:
            headers["Authorization"] = f"Bearer {self.github_token}"
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read().decode("utf-8"))
            repos = []
            for item in data.get("items", [])[:max_results]:
                repos.append(GitHubRepo(
                    owner=item["owner"]["login"], name=item["name"], url=item["html_url"],
                    description=item.get("description") or "", stars=item.get("stargazers_count", 0), language=item.get("language") or "",
                    topics=item.get("topics", []), last_updated=item.get("updated_at", ""), default_branch=item.get("default_branch", "main")
                ))
            return repos
        except Exception:
            return []

    def clone_repository(self, repo: GitHubRepo, target_dir: Optional[Path] = None) -> FetchResult:
        target = target_dir or (self.work_dir / f"{repo.owner}_{repo.name}")
        if target.exists():
            shutil.rmtree(target)
        last_err = ""
        for i in range(1, self.clone_retries + 1):
            try:
                p = subprocess.run(["git", "clone", "--depth", "1", repo.clone_url, str(target)], capture_output=True, text=True, timeout=self.clone_timeout)
                if p.returncode == 0:
                    res = FetchResult(True, "git_clone", str(target), i, self.clone_timeout, p.stderr or "")
                    self._save_fetch_status(repo, res)
                    return res
                last_err = p.stderr or p.stdout
            except Exception as e:
                last_err = str(e)
        res = FetchResult(False, "git_clone", None, self.clone_retries, self.clone_timeout, last_err)
        self._save_fetch_status(repo, res)
        return res

    def download_repo_zip(self, repo: GitHubRepo, target_dir: Optional[Path] = None) -> FetchResult:
        target = target_dir or (self.work_dir / f"{repo.owner}_{repo.name}")
        if target.exists():
            shutil.rmtree(target)
        branches = [repo.default_branch, "main", "master"]
        last_err = ""
        for branch in branches:
            if not branch:
                continue
            zip_url = f"https://github.com/{repo.owner}/{repo.name}/archive/refs/heads/{branch}.zip"
            zip_path = self.work_dir / f"{repo.name}-{branch}.zip"
            try:
                urllib.request.urlretrieve(zip_url, zip_path)
                shutil.unpack_archive(zip_path, self.work_dir)
                extracted = self.work_dir / f"{repo.name}-{branch}"
                if extracted.exists():
                    extracted.rename(target)
                zip_path.unlink(missing_ok=True)
                res = FetchResult(True, "zip", str(target), 1, self.clone_timeout, "")
                self._save_fetch_status(repo, res)
                return res
            except Exception as e:
                last_err = str(e)
        res = FetchResult(False, "zip", None, 1, self.clone_timeout, last_err)
        self._save_fetch_status(repo, res)
        return res

    def _save_fetch_status(self, repo: GitHubRepo, status: FetchResult):
        path = self.work_dir / "repo_fetch_status.json"
        data = []
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                data = []
        data.append({"repo": repo.url, **asdict(status)})
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def analyze_repository(self, repo_path: Path, repo: GitHubRepo, context: Optional[Dict] = None) -> RepoAnalysis:
        py_files = [str(p.relative_to(repo_path)) for p in repo_path.rglob("*.py")]
        entries = [f for f in py_files if Path(f).name in {"main.py", "train.py", "run.py", "app.py"}]
        keywords = [k.lower() for k in (context or {}).get("keywords", [])]
        text = f"{repo.name} {repo.description}".lower()
        relevance = min(1.0, sum(1 for k in keywords if k in text) / max(1, len(keywords))) if keywords else 0.5
        return RepoAnalysis(
            repo=repo, local_path=repo_path, structure={}, has_requirements=(repo_path / "requirements.txt").exists(),
            has_setup_py=(repo_path / "setup.py").exists(), has_pyproject=(repo_path / "pyproject.toml").exists(),
            main_entry_points=entries, data_directories=[], notebooks=[str(p.relative_to(repo_path)) for p in repo_path.rglob("*.ipynb")],
            python_files=py_files, relevance_score=relevance, runnable_entry_valid=bool(entries)
        )

    def extract_runnable_code(self, repo_analysis: RepoAnalysis):
        return [{"file": p} for p in repo_analysis.main_entry_points[:1]]
