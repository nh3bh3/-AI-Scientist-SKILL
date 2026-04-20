"""
Phase 2 (Enhanced): 实验阶段增强版

新增功能：
1. 从 GitHub 搜索并下载相关仓库
2. 自动获取真实数据集
3. 在沙盒中运行基线和改进实验
4. 支持对比实验
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from sandbox import SandboxExecutor
from github_manager import GitHubManager, GitHubRepo, RepoAnalysis
from dataset_manager import DatasetManager, DatasetInfo


@dataclass
class ExperimentConfig:
    """实验配置"""
    use_github_baseline: bool = True
    use_real_dataset: bool = True
    run_baseline: bool = True
    run_proposed: bool = True
    max_github_repos: int = 3
    max_dataset_attempts: int = 3


class ExperimentPhaseV2:
    """增强版实验阶段处理器"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.models = config.get('models', {})
        self.exp_config = config.get('experiment', {})
        
        # 初始化管理器
        self.github_manager = GitHubManager()
        self.dataset_manager = DatasetManager()
        
        # 实验配置
        self.experiment_config = ExperimentConfig(
            use_github_baseline=config.get('use_github_baseline', True),
            use_real_dataset=config.get('use_real_dataset', True),
            run_baseline=config.get('run_baseline', True),
            run_proposed=config.get('run_proposed', True)
        )
        
        # 存储状态
        self.selected_repos: List[RepoAnalysis] = []
        self.selected_dataset: Optional[DatasetInfo] = None
        self.baseline_results: Optional[Dict] = None
        self.proposed_results: Optional[Dict] = None
    
    def load_idea(self, ideas_file: Path, idea_id: int = 1) -> Optional[Dict]:
        """加载研究假设"""
        with open(ideas_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        ideas = data.get('ideas', [])
        for idea in ideas:
            if idea.get('id') == idea_id:
                return idea
        
        return ideas[0] if ideas else None
    
    def find_github_repositories(self, idea: Dict) -> List[RepoAnalysis]:
        """
        搜索并分析 GitHub 仓库
        
        Args:
            idea: 研究假设
            
        Returns:
            仓库分析列表
        """
        print("\n[Phase 2.1] 搜索 GitHub 仓库...")
        
        # 构建搜索查询
        keywords = idea.get('keywords', [])
        method = idea.get('method', '')
        
        # 从方法描述中提取关键技术
        tech_keywords = self._extract_tech_keywords(method)
        search_query = ' '.join(keywords + tech_keywords)
        
        print(f"  搜索关键词: {search_query}")
        
        # 搜索仓库
        repos = self.github_manager.search_repositories(
            query=search_query,
            language="python",
            max_results=self.experiment_config.max_github_repos
        )
        
        if not repos:
            print("  [WARN] 未找到相关仓库")
            return []
        
        # 克隆并分析仓库
        repo_analyses = []
        for repo in repos:
            print(f"\n  分析仓库: {repo.name}")
            
            # 克隆仓库
            local_path = self.github_manager.clone_repository(repo)
            if not local_path:
                continue
            
            # 分析仓库
            analysis = self.github_manager.analyze_repository(local_path, repo)
            repo_analyses.append(analysis)
            
            # 设置环境（可选，取决于配置）
            # self.github_manager.setup_environment(local_path)
            
            if len(repo_analyses) >= self.experiment_config.max_github_repos:
                break
        
        print(f"\n[OK] 成功分析 {len(repo_analyses)} 个仓库")
        self.selected_repos = repo_analyses
        
        return repo_analyses
    
    def _extract_tech_keywords(self, text: str) -> List[str]:
        """从技术描述中提取关键词"""
        # 常见的深度学习/ML 关键词
        tech_terms = [
            'transformer', 'bert', 'gpt', 'cnn', 'lstm', 'rnn',
            'pytorch', 'tensorflow', 'keras', 'sklearn',
            'classification', 'regression', 'nlp', 'vision',
            'yolo', 'resnet', 'vgg', 'efficientnet'
        ]
        
        found = []
        text_lower = text.lower()
        for term in tech_terms:
            if term in text_lower:
                found.append(term)
        
        return found
    
    def find_dataset(self, idea: Dict) -> Optional[DatasetInfo]:
        """
        搜索并下载数据集
        
        Args:
            idea: 研究假设
            
        Returns:
            数据集信息
        """
        print("\n[Phase 2.2] 搜索真实数据集...")
        
        # 推断任务类型
        task_type = self._infer_task_type(idea)
        keywords = idea.get('keywords', [])
        
        print(f"  任务类型: {task_type}")
        print(f"  关键词: {', '.join(keywords)}")
        
        # 搜索数据集
        datasets = self.dataset_manager.search_datasets(
            keywords=keywords,
            task_type=task_type,
            max_results=5
        )
        
        if not datasets:
            print("  [WARN] 未找到相关数据集")
            return None
        
        # 尝试下载数据集
        for dataset in datasets[:self.experiment_config.max_dataset_attempts]:
            print(f"\n  尝试下载: {dataset.name} ({dataset.source})")
            
            if self.dataset_manager.download_dataset(dataset):
                print(f"  [OK] 下载成功: {dataset.name}")
                self.selected_dataset = dataset
                
                # 分析数据集
                analysis = self.dataset_manager.analyze_dataset(dataset.name)
                
                return dataset
            else:
                print(f"  [FAIL] 下载失败，尝试下一个...")
        
        print("  [FAIL] 所有数据集下载失败")
        return None
    
    def _infer_task_type(self, idea: Dict) -> str:
        """推断任务类型"""
        text = ' '.join(idea.get('keywords', []) + [idea.get('method', '')]).lower()
        
        if any(kw in text for kw in ['classification', '分类']):
            return 'classification'
        elif any(kw in text for kw in ['regression', '回归']):
            return 'regression'
        elif any(kw in text for kw in ['nlp', 'text', 'sentiment', 'language', '文本', '语言']):
            return 'nlp'
        elif any(kw in text for kw in ['image', 'vision', 'cnn', '图像', '视觉']):
            return 'cv'
        else:
            return 'unknown'
    
    def generate_baseline_code(self, idea: Dict, repo_analysis: RepoAnalysis) -> str:
        """
        生成基线实验代码
        
        Args:
            idea: 研究假设
            repo_analysis: 仓库分析
            
        Returns:
            Python 代码
        """
        print(f"\n[Phase 2.3] 生成基线代码...")
        
        # 提取可运行代码
        runnable_code = self.github_manager.extract_runnable_code(repo_analysis)
        
        # 生成数据加载代码
        data_loading_code = ""
        if self.selected_dataset:
            data_loading_code = self.dataset_manager.generate_data_loading_code(
                self.selected_dataset.name
            )
        
        # 构建基线代码
        baseline_code = f'''"""
基线实验代码
基于仓库: {repo_analysis.repo.name}
数据集: {self.selected_dataset.name if self.selected_dataset else 'None'}
"""

import os
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUTPUT_DIR = "outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

{data_loading_code}

# 从 GitHub 仓库提取的基线方法
# 原始文件: {runnable_code[0]['file'] if runnable_code else 'N/A'}

class BaselineModel:
    """基线模型"""
    
    def __init__(self):
        self.name = "{repo_analysis.repo.name}"
    
    def fit(self, X, y):
        """训练模型"""
        # 这里应该包含从仓库提取的训练逻辑
        pass
    
    def predict(self, X):
        """预测"""
        # 这里应该包含从仓库提取的预测逻辑
        return np.zeros(len(X))
    
    def evaluate(self, X, y):
        """评估"""
        from sklearn.metrics import accuracy_score, f1_score
        
        predictions = self.predict(X)
        
        metrics = {{
            'accuracy': accuracy_score(y, predictions),
            'f1_score': f1_score(y, predictions, average='weighted')
        }}
        
        return metrics

def run_baseline_experiment():
    """运行基线实验"""
    print("=" * 50)
    print("运行基线实验")
    print("=" * 50)
    
    # 加载数据
    data = load_data()
    
    # 如果是 DataFrame，分离特征和标签
    if hasattr(data, 'columns'):
        # 假设最后一列是标签
        X = data.iloc[:, :-1]
        y = data.iloc[:, -1]
    else:
        X, y = data, None
    
    # 划分训练集和测试集
    from sklearn.model_selection import train_test_split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # 训练基线模型
    model = BaselineModel()
    model.fit(X_train, y_train)
    
    # 评估
    metrics = model.evaluate(X_test, y_test)
    
    print(f"基线模型评估结果: {{metrics}}")
    
    # 保存结果
    with open(os.path.join(OUTPUT_DIR, "baseline_metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)
    
    return metrics

if __name__ == "__main__":
    run_baseline_experiment()
'''
        
        return baseline_code
    
    def generate_proposed_code(self, idea: Dict) -> str:
        """
        生成改进方法代码
        
        Args:
            idea: 研究假设
            
        Returns:
            Python 代码
        """
        print(f"\n[Phase 2.4] 生成改进方法代码...")
        
        # 生成数据加载代码
        data_loading_code = ""
        if self.selected_dataset:
            data_loading_code = self.dataset_manager.generate_data_loading_code(
                self.selected_dataset.name
            )
        
        proposed_code = f'''"""
改进方法实验代码
研究假设: {idea.get('title', '')}
数据集: {self.selected_dataset.name if self.selected_dataset else 'None'}
"""

import os
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUTPUT_DIR = "outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

{data_loading_code}

class ProposedModel:
    """提出的改进模型"""
    
    def __init__(self):
        self.name = "Proposed"
        # TODO: 根据研究假设初始化模型参数
    
    def fit(self, X, y):
        """训练模型"""
        # TODO: 实现训练逻辑
        pass
    
    def predict(self, X):
        """预测"""
        # TODO: 实现预测逻辑
        return np.zeros(len(X))
    
    def evaluate(self, X, y):
        """评估"""
        from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
        
        predictions = self.predict(X)
        
        metrics = {{
            'accuracy': accuracy_score(y, predictions),
            'precision': precision_score(y, predictions, average='weighted', zero_division=0),
            'recall': recall_score(y, predictions, average='weighted', zero_division=0),
            'f1_score': f1_score(y, predictions, average='weighted', zero_division=0)
        }}
        
        return metrics

def run_proposed_experiment():
    """运行改进方法实验"""
    print("=" * 50)
    print("运行改进方法实验")
    print("=" * 50)
    
    # 加载数据
    data = load_data()
    
    # 如果是 DataFrame，分离特征和标签
    if hasattr(data, 'columns'):
        X = data.iloc[:, :-1]
        y = data.iloc[:, -1]
    else:
        X, y = data, None
    
    # 划分训练集和测试集
    from sklearn.model_selection import train_test_split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # 训练改进模型
    model = ProposedModel()
    model.fit(X_train, y_train)
    
    # 评估
    metrics = model.evaluate(X_test, y_test)
    
    print(f"改进方法评估结果: {{metrics}}")
    
    # 保存结果
    with open(os.path.join(OUTPUT_DIR, "proposed_metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)
    
    return metrics

if __name__ == "__main__":
    run_proposed_experiment()
'''
        
        return proposed_code
    
    def run_experiments(self, output_dir: Path) -> Dict:
        """
        运行基线和改进实验
        
        Args:
            output_dir: 输出目录
            
        Returns:
            实验结果
        """
        results = {
            'baseline': None,
            'proposed': None,
            'comparison': None
        }
        
        sandbox = SandboxExecutor(
            work_dir=str(output_dir / "sandbox"),
            timeout=self.exp_config.get('timeout', 600)
        )
        
        # 运行基线实验
        if self.experiment_config.run_baseline and self.selected_repos:
            print("\n[Phase 2.5] 运行基线实验...")
            
            baseline_code = self.generate_baseline_code(
                self.current_idea, 
                self.selected_repos[0]
            )
            
            baseline_result = sandbox.execute(baseline_code, "baseline.py")
            self.baseline_results = baseline_result
            
            if baseline_result.success:
                print("  [OK] 基线实验成功")
                results['baseline'] = baseline_result.metrics
            else:
                print(f"  [FAIL] 基线实验失败: {baseline_result.error_type}")
        
        # 运行改进实验
        if self.experiment_config.run_proposed:
            print("\n[Phase 2.6] 运行改进实验...")
            
            proposed_code = self.generate_proposed_code(self.current_idea)
            
            proposed_result = sandbox.execute(proposed_code, "proposed.py")
            self.proposed_results = proposed_result
            
            if proposed_result.success:
                print("  [OK] 改进实验成功")
                results['proposed'] = proposed_result.metrics
            else:
                print(f"  [FAIL] 改进实验失败: {proposed_result.error_type}")
        
        # 对比分析
        if results['baseline'] and results['proposed']:
            print("\n[Phase 2.7] 生成对比结果...")
            
            comparison = self._compare_results(
                results['baseline'], 
                results['proposed']
            )
            results['comparison'] = comparison
            
            # 保存对比结果
            with open(output_dir / "comparison.json", 'w', encoding='utf-8') as f:
                json.dump(comparison, f, ensure_ascii=False, indent=2)
        
        return results
    
    def _compare_results(self, baseline: Dict, proposed: Dict) -> Dict:
        """对比基线和改进结果"""
        comparison = {
            'baseline_metrics': baseline,
            'proposed_metrics': proposed,
            'improvements': {}
        }
        
        for metric in baseline.keys():
            if metric in proposed and isinstance(baseline[metric], (int, float)):
                improvement = proposed[metric] - baseline[metric]
                improvement_pct = (improvement / baseline[metric] * 100) if baseline[metric] != 0 else 0
                
                comparison['improvements'][metric] = {
                    'absolute': improvement,
                    'percentage': improvement_pct
                }
        
        return comparison
    
    def run(self, ideas_file: Path, idea_id: int, output_dir: Path,
            llm_call_func=None) -> Dict:
        """
        运行增强版实验阶段
        
        Args:
            ideas_file: ideas.json 文件
            idea_id: 假设 ID
            output_dir: 输出目录
            llm_call_func: LLM 调用函数
            
        Returns:
            执行结果
        """
        print("=" * 70)
        print("Phase 2 (Enhanced): 实验阶段 - 基线对比与真实数据")
        print("=" * 70)
        
        # 加载假设
        self.current_idea = self.load_idea(ideas_file, idea_id)
        if not self.current_idea:
            print("[FAIL] 未找到研究假设")
            return {"success": False, "error": "Hypothesis not found"}
        
        print(f"\n研究假设: {self.current_idea['title']}")
        
        # 1. 搜索 GitHub 仓库
        if self.experiment_config.use_github_baseline:
            repos = self.find_github_repositories(self.current_idea)
        
        # 2. 获取数据集
        if self.experiment_config.use_real_dataset:
            dataset = self.find_dataset(self.current_idea)
        
        # 3. 运行实验
        output_dir.mkdir(parents=True, exist_ok=True)
        results = self.run_experiments(output_dir)
        
        # 4. 保存完整结果
        final_results = {
            "success": True,
            "hypothesis": self.current_idea['title'],
            "github_repos": [
                {
                    "name": r.repo.name,
                    "url": r.repo.url,
                    "stars": r.repo.stars
                }
                for r in self.selected_repos
            ] if self.selected_repos else [],
            "dataset": {
                "name": self.selected_dataset.name if self.selected_dataset else None,
                "source": self.selected_dataset.source if self.selected_dataset else None,
                "local_path": self.selected_dataset.local_path if self.selected_dataset else None
            },
            "experiments": results
        }
        
        with open(output_dir / "experiment_results.json", 'w', encoding='utf-8') as f:
            json.dump(final_results, f, ensure_ascii=False, indent=2)
        
        print("\n" + "=" * 70)
        print("实验阶段完成")
        print("=" * 70)
        print(f"GitHub 仓库: {len(self.selected_repos)}")
        print(f"数据集: {self.selected_dataset.name if self.selected_dataset else 'None'}")
        print(f"基线实验: {'成功' if results.get('baseline') else '失败'}")
        print(f"改进实验: {'成功' if results.get('proposed') else '失败'}")
        
        return final_results


if __name__ == "__main__":
    # 测试
    config = {
        "models": {"experiment": "claude-3-5-sonnet"},
        "experiment": {"timeout": 300}
    }
    
    test_ideas = {
        "ideas": [{
            "id": 1,
            "title": "基于Transformer的情感分析改进",
            "hypothesis": "使用改进的注意力机制提升情感分析准确率",
            "method": "使用PyTorch实现改进的Transformer模型",
            "keywords": ["sentiment", "analysis", "transformer", "nlp"]
        }]
    }
    
    test_file = Path("test_ideas_v2.json")
    with open(test_file, 'w', encoding='utf-8') as f:
        json.dump(test_ideas, f)
    
    phase = ExperimentPhaseV2(config)
    result = phase.run(test_file, 1, Path("test_experiment_v2"))
    
    print(f"\n结果:\n{json.dumps(result, indent=2, default=str)}")
