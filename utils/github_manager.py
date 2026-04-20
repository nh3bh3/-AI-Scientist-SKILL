"""
GitHub 仓库管理器

功能：
1. 从 GitHub 搜索相关仓库
2. 下载/克隆仓库到沙盒
3. 分析仓库结构
4. 提取可运行的代码
5. 配置依赖环境
"""

import os
import re
import json
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class GitHubRepo:
    """GitHub 仓库信息"""
    owner: str
    name: str
    url: str
    description: str
    stars: int
    language: str
    topics: List[str]
    last_updated: str
    
    @property
    def clone_url(self) -> str:
        return f"https://github.com/{self.owner}/{self.name}.git"
    
    @property
    def api_url(self) -> str:
        return f"https://api.github.com/repos/{self.owner}/{self.name}"


@dataclass
class RepoAnalysis:
    """仓库分析结果"""
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


class GitHubManager:
    """GitHub 仓库管理器"""
    
    def __init__(self, work_dir: Optional[str] = None, 
                 github_token: Optional[str] = None):
        """
        初始化
        
        Args:
            work_dir: 工作目录
            github_token: GitHub API Token（可选，用于提高速率限制）
        """
        self.work_dir = Path(work_dir) if work_dir else Path.cwd() / "github_repos"
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.github_token = github_token
        self.cloned_repos: Dict[str, Path] = {}
    
    def search_repositories(self, query: str, language: str = "python",
                           sort: str = "stars", max_results: int = 10) -> List[GitHubRepo]:
        """
        搜索 GitHub 仓库
        
        Args:
            query: 搜索关键词
            language: 编程语言
            sort: 排序方式（stars/forks/updated）
            max_results: 最大结果数
            
        Returns:
            仓库列表
        """
        print(f"搜索 GitHub: {query} (language:{language})")
        
        # 构建 GitHub API 请求
        search_query = f"{query} language:{language}"
        url = f"https://api.github.com/search/repositories"
        
        import urllib.request
        import urllib.parse
        
        params = {
            'q': search_query,
            'sort': sort,
            'order': 'desc',
            'per_page': min(max_results, 30)
        }
        
        headers = {'Accept': 'application/vnd.github.v3+json'}
        if self.github_token:
            headers['Authorization'] = f'token {self.github_token}'
        
        try:
            req = urllib.request.Request(
                f"{url}?{urllib.parse.urlencode(params)}",
                headers=headers
            )
            
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode())
                
                repos = []
                for item in data.get('items', []):
                    repo = GitHubRepo(
                        owner=item['owner']['login'],
                        name=item['name'],
                        url=item['html_url'],
                        description=item.get('description', ''),
                        stars=item['stargazers_count'],
                        language=item.get('language', ''),
                        topics=item.get('topics', []),
                        last_updated=item['updated_at']
                    )
                    repos.append(repo)
                
                print(f"  找到 {len(repos)} 个仓库")
                return repos
                
        except Exception as e:
            print(f"  搜索失败: {e}")
            return []
    
    def clone_repository(self, repo: GitHubRepo, 
                        target_dir: Optional[Path] = None) -> Optional[Path]:
        """
        克隆仓库到本地
        
        Args:
            repo: 仓库信息
            target_dir: 目标目录（可选）
            
        Returns:
            本地路径
        """
        if target_dir is None:
            target_dir = self.work_dir / f"{repo.owner}_{repo.name}"
        
        # 如果已存在，先删除
        if target_dir.exists():
            shutil.rmtree(target_dir)
        
        print(f"克隆仓库: {repo.clone_url}")
        print(f"  目标: {target_dir}")
        
        try:
            result = subprocess.run(
                ['git', 'clone', '--depth', '1', repo.clone_url, str(target_dir)],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                print(f"  [OK] 克隆成功")
                self.cloned_repos[repo.name] = target_dir
                return target_dir
            else:
                print(f"  [FAIL] 克隆失败: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            print(f"  [FAIL] 克隆超时")
            return None
        except Exception as e:
            print(f"  [FAIL] 克隆错误: {e}")
            return None
    
    def download_repo_zip(self, repo: GitHubRepo, 
                         target_dir: Optional[Path] = None) -> Optional[Path]:
        """
        下载仓库 ZIP 文件（备用方案）
        
        Args:
            repo: 仓库信息
            target_dir: 目标目录
            
        Returns:
            本地路径
        """
        if target_dir is None:
            target_dir = self.work_dir / f"{repo.owner}_{repo.name}"
        
        zip_url = f"https://github.com/{repo.owner}/{repo.name}/archive/refs/heads/main.zip"
        zip_path = self.work_dir / f"{repo.name}.zip"
        
        print(f"下载 ZIP: {zip_url}")
        
        try:
            import urllib.request
            urllib.request.urlretrieve(zip_url, zip_path)
            
            # 解压
            shutil.unpack_archive(zip_path, target_dir.parent)
            
            # 重命名
            extracted_dir = target_dir.parent / f"{repo.name}-main"
            if extracted_dir.exists():
                extracted_dir.rename(target_dir)
            
            zip_path.unlink()  # 删除 ZIP
            
            print(f"  [OK] 下载并解压成功")
            self.cloned_repos[repo.name] = target_dir
            return target_dir
            
        except Exception as e:
            print(f"  [FAIL] 下载失败: {e}")
            return None
    
    def analyze_repository(self, repo_path: Path, repo: GitHubRepo) -> RepoAnalysis:
        """
        分析仓库结构
        
        Args:
            repo_path: 本地仓库路径
            repo: 仓库信息
            
        Returns:
            分析结果
        """
        print(f"分析仓库结构: {repo.name}")
        
        structure = self._get_directory_structure(repo_path)
        
        # 检查依赖文件
        has_requirements = (repo_path / "requirements.txt").exists()
        has_setup_py = (repo_path / "setup.py").exists()
        has_pyproject = (repo_path / "pyproject.toml").exists()
        
        # 查找入口点
        main_entry_points = []
        for py_file in repo_path.rglob("*.py"):
            if py_file.name in ["main.py", "train.py", "run.py", "demo.py", "example.py"]:
                main_entry_points.append(str(py_file.relative_to(repo_path)))
        
        # 查找数据目录
        data_dirs = []
        for pattern in ["data", "dataset", "datasets", "input", "inputs", "assets"]:
            for d in repo_path.iterdir():
                if d.is_dir() and pattern in d.name.lower():
                    data_dirs.append(str(d.relative_to(repo_path)))
        
        # 查找 notebooks
        notebooks = [str(f.relative_to(repo_path)) for f in repo_path.rglob("*.ipynb")]
        
        # 查找 Python 文件
        python_files = [str(f.relative_to(repo_path)) for f in repo_path.rglob("*.py")]
        
        print(f"  [OK] 分析完成:")
        print(f"    - Python 文件: {len(python_files)}")
        print(f"    - Notebooks: {len(notebooks)}")
        print(f"    - 依赖文件: requirements.txt={has_requirements}, setup.py={has_setup_py}")
        print(f"    - 入口点: {main_entry_points[:3]}")
        
        return RepoAnalysis(
            repo=repo,
            local_path=repo_path,
            structure=structure,
            has_requirements=has_requirements,
            has_setup_py=has_setup_py,
            has_pyproject=has_pyproject,
            main_entry_points=main_entry_points,
            data_directories=data_dirs,
            notebooks=notebooks,
            python_files=python_files
        )
    
    def _get_directory_structure(self, path: Path, max_depth: int = 3) -> Dict:
        """获取目录结构"""
        if max_depth == 0:
            return {}
        
        structure = {}
        try:
            for item in path.iterdir():
                if item.name.startswith('.') and item.name != '.gitignore':
                    continue
                
                if item.is_dir():
                    structure[item.name] = self._get_directory_structure(item, max_depth - 1)
                else:
                    structure[item.name] = None
        except PermissionError:
            pass
        
        return structure
    
    def setup_environment(self, repo_path: Path, 
                         python_version: str = "3.10") -> bool:
        """
        设置 Python 环境并安装依赖
        
        Args:
            repo_path: 仓库路径
            python_version: Python 版本
            
        Returns:
            是否成功
        """
        print(f"设置环境: {repo_path.name}")
        
        # 创建虚拟环境
        venv_path = repo_path / "venv"
        try:
            subprocess.run(
                ['python', '-m', 'venv', str(venv_path)],
                cwd=repo_path,
                capture_output=True,
                check=True
            )
            print(f"  [OK] 虚拟环境创建成功")
        except Exception as e:
            print(f"  [WARN] 虚拟环境创建失败: {e}")
            venv_path = None
        
        # 确定 pip 路径
        if venv_path:
            pip_cmd = str(venv_path / "Scripts" / "pip") if os.name == 'nt' else str(venv_path / "bin" / "pip")
            python_cmd = str(venv_path / "Scripts" / "python") if os.name == 'nt' else str(venv_path / "bin" / "python")
        else:
            pip_cmd = "pip"
            python_cmd = "python"
        
        # 安装依赖
        requirements_file = repo_path / "requirements.txt"
        if requirements_file.exists():
            print(f"  安装 requirements.txt...")
            try:
                subprocess.run(
                    [pip_cmd, 'install', '-r', str(requirements_file)],
                    cwd=repo_path,
                    capture_output=True,
                    timeout=300
                )
                print(f"  [OK] 依赖安装完成")
            except Exception as e:
                print(f"  [WARN] 依赖安装失败: {e}")
        
        # 安装本地包
        setup_py = repo_path / "setup.py"
        pyproject = repo_path / "pyproject.toml"
        
        if setup_py.exists() or pyproject.exists():
            print(f"  安装本地包...")
            try:
                subprocess.run(
                    [pip_cmd, 'install', '-e', '.'],
                    cwd=repo_path,
                    capture_output=True,
                    timeout=120
                )
                print(f"  [OK] 本地包安装完成")
            except Exception as e:
                print(f"  [WARN] 本地包安装失败: {e}")
        
        return True
    
    def extract_runnable_code(self, repo_analysis: RepoAnalysis) -> List[Dict]:
        """
        提取可运行的代码片段
        
        Args:
            repo_analysis: 仓库分析结果
            
        Returns:
            可运行代码列表
        """
        runnable_code = []
        
        # 分析入口点文件
        for entry in repo_analysis.main_entry_points:
            file_path = repo_analysis.local_path / entry
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # 检查是否是可运行的脚本
                if '__main__' in content or 'def main' in content:
                    runnable_code.append({
                        'file': entry,
                        'type': 'script',
                        'content': content,
                        'purpose': self._infer_purpose(content)
                    })
        
        # 分析 notebooks
        for nb in repo_analysis.notebooks[:3]:  # 限制数量
            nb_path = repo_analysis.local_path / nb
            try:
                with open(nb_path, 'r', encoding='utf-8') as f:
                    nb_content = json.load(f)
                
                # 提取代码单元格
                code_cells = []
                for cell in nb_content.get('cells', []):
                    if cell.get('cell_type') == 'code':
                        code_cells.append(''.join(cell.get('source', [])))
                
                if code_cells:
                    runnable_code.append({
                        'file': nb,
                        'type': 'notebook',
                        'content': '\n\n'.join(code_cells),
                        'purpose': self._infer_purpose('\n'.join(code_cells))
                    })
            except:
                pass
        
        return runnable_code
    
    def _infer_purpose(self, code: str) -> str:
        """推断代码用途"""
        if 'train' in code.lower():
            return 'training'
        elif 'test' in code.lower() or 'eval' in code.lower():
            return 'evaluation'
        elif 'demo' in code.lower() or 'example' in code.lower():
            return 'demonstration'
        elif 'data' in code.lower() or 'load' in code.lower():
            return 'data_loading'
        else:
            return 'general'
    
    def find_baseline_implementations(self, repo_analysis: RepoAnalysis) -> List[Dict]:
        """
        查找基线实现
        
        Args:
            repo_analysis: 仓库分析
            
        Returns:
            基线实现列表
        """
        baselines = []
        
        # 常见的基线关键词
        baseline_keywords = ['baseline', 'comparison', 'compare', 'vanilla', 
                           'standard', 'traditional', 'classic']
        
        for py_file in repo_analysis.python_files:
            file_path = repo_analysis.local_path / py_file
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # 检查是否包含基线关键词
                if any(keyword in content.lower() for keyword in baseline_keywords):
                    baselines.append({
                        'file': py_file,
                        'content': content[:1000]  # 前1000字符
                    })
            except:
                pass
        
        return baselines
    
    def cleanup(self, repo_name: Optional[str] = None):
        """清理克隆的仓库"""
        if repo_name and repo_name in self.cloned_repos:
            path = self.cloned_repos[repo_name]
            if path.exists():
                shutil.rmtree(path)
                del self.cloned_repos[repo_name]
        elif repo_name is None:
            # 清理所有
            for path in self.cloned_repos.values():
                if path.exists():
                    shutil.rmtree(path)
            self.cloned_repos.clear()


if __name__ == "__main__":
    # 测试
    manager = GitHubManager()
    
    # 搜索仓库
    repos = manager.search_repositories("sentiment analysis pytorch", max_results=5)
    
    if repos:
        # 克隆第一个仓库
        repo = repos[0]
        print(f"\n测试克隆: {repo.name}")
        local_path = manager.clone_repository(repo)
        
        if local_path:
            # 分析仓库
            analysis = manager.analyze_repository(local_path, repo)
            
            # 提取可运行代码
            code_snippets = manager.extract_runnable_code(analysis)
            print(f"\n找到 {len(code_snippets)} 个可运行代码片段")
            
            # 清理
            manager.cleanup(repo.name)
