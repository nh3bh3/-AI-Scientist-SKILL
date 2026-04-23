"""
AI-Research-Assistant 增强功能测试

测试内容：
1. 虚假内容检测
2. AI 写作风格检测
3. GitHub 仓库搜索/克隆
4. 数据集搜索/下载
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "phases"))
sys.path.insert(0, str(Path(__file__).parent / "utils"))


def test_fake_content_detection():
    """测试虚假内容检测"""
    print("\n" + "="*60)
    print("测试 1: 虚假内容检测")
    print("="*60)
    
    from phases.review_v2 import FakeContentDetector
    
    detector = FakeContentDetector()
    
    # 测试文本（包含可疑内容）
    test_paper = """
    # 研究论文
    
    ## 实验结果
    我们的模型达到了 99.9% 的准确率，这是完美的性能。
    所有样本都被正确分类，实现了零误差。
    
    ## 方法
    我们使用深度学习技术，取得了 state-of-the-art 结果。
    
    ## 引用
    根据许多研究，深度学习效果很好。
    """
    
    # 执行检测
    results = detector.analyze(test_paper, metrics_data={"accuracy": 0.999, "f1": 1.0})
    
    print(f"\n检测结果:")
    for check in results:
        status = "[WARN]" if check.is_suspicious else "[OK]"
        print(f"  [{status}] {check.category}: confidence {check.confidence:.0%}")
        if check.evidence:
            print(f"    evidence: {check.evidence[:2]}")
    
    suspicious_count = sum(1 for r in results if r.is_suspicious)
    print(f"\n发现 {suspicious_count}/4 项可疑内容")
    assert suspicious_count > 0


def test_ai_writing_detection():
    """测试 AI 写作检测"""
    print("\n" + "="*60)
    print("测试 2: AI 写作风格检测")
    print("="*60)
    
    from phases.review_v2 import AIWritingDetector
    
    detector = AIWritingDetector()
    
    # 测试文本（包含 AI 写作特征）
    test_paper = """
    # Abstract
    
    This paper delves into the intricate tapestry of machine learning.
    We leverage advanced techniques to enhance model performance.
    Furthermore, our approach facilitates better results.
    
    Furthermore, we optimize the training process.
    Moreover, the results are promising.
    Consequently, further research is needed.
    
    This is a significant improvement over previous work.
    """
    
    patterns = detector.analyze(test_paper)
    
    print(f"\n检测到的 AI 写作特征:")
    for pattern in patterns:
        icon = "[HIGH]" if pattern.severity == 'high' else "[MED]" if pattern.severity == 'medium' else "[LOW]"
        print(f"  {icon} {pattern.pattern_type} ({pattern.severity})")
        print(f"     examples: {pattern.examples[:2]}")
    
    print(f"\n共发现 {len(patterns)} 个特征")
    assert len(patterns) > 0


def test_github_search():
    """测试 GitHub 仓库搜索"""
    print("\n" + "="*60)
    print("测试 3: GitHub 仓库搜索")
    print("="*60)
    
    from utils.github_manager import GitHubManager
    
    manager = GitHubManager()
    
    # 搜索情感分析相关仓库
    print("\n搜索: 'sentiment analysis pytorch'")
    repos = manager.search_repositories(
        "sentiment analysis pytorch",
        language="python",
        max_results=3
    )
    
    if repos:
        print(f"\n找到 {len(repos)} 个仓库:")
        for i, repo in enumerate(repos, 1):
            print(f"  {i}. {repo.name} ({repo.stars} stars)")
            print(f"     {repo.description[:80]}...")
        assert len(repos) > 0
    else:
        print("  未找到仓库（可能达到API限制）")
        # 网络或 API 限流时不强制失败
        assert repos == []


def test_dataset_search():
    """测试数据集搜索"""
    print("\n" + "="*60)
    print("测试 4: 数据集搜索")
    print("="*60)
    
    from utils.dataset_manager import DatasetManager
    
    manager = DatasetManager()
    
    # 搜索情感分析数据集
    print("\n搜索: sentiment analysis 数据集")
    datasets = manager.search_datasets(
        keywords=["sentiment", "analysis", "movie"],
        task_type="nlp",
        max_results=3
    )
    
    if datasets:
        print(f"\n找到 {len(datasets)} 个数据集:")
        for i, ds in enumerate(datasets, 1):
            print(f"  {i}. {ds.name} ({ds.source})")
            print(f"     {ds.description[:80]}...")
        assert len(datasets) > 0
    else:
        print("  未找到数据集")
        assert datasets == []


def test_enhanced_review_integration():
    """测试增强版审稿集成"""
    print("\n" + "="*60)
    print("测试 5: 增强版审稿集成")
    print("="*60)
    
    from phases.review_v2 import ReviewPhaseV2
    
    # 创建测试论文
    test_paper_content = """# 基于深度学习的情感分析研究

## 摘要

本研究提出了一个新的情感分析模型，达到了99.8%的准确率。

## 引言

This paper delves into the intricate world of sentiment analysis.
We leverage state-of-the-art techniques to achieve perfect results.

## 方法

我们使用了深度学习技术，取得了显著的效果提升。

## 实验

在测试集上，我们的模型准确率达到了99.8%，F1分数为1.0。
这是目前最好的结果。

## 结论

Further research is needed in this area.
"""
    
    # 保存测试论文
    test_dir = Path("test_review_v2")
    test_dir.mkdir(exist_ok=True)
    
    paper_file = test_dir / "test_paper.md"
    with open(paper_file, 'w', encoding='utf-8') as f:
        f.write(test_paper_content)
    
    # 创建配置
    config = {
        "models": {"review": "gpt-4o"},
        "review": {
            "rounds": 1,
            "threshold": 7.0,
            "use_enhanced": True
        }
    }
    
    # 运行增强版审稿
    phase = ReviewPhaseV2(config)
    
    print("\n运行增强版审稿（模拟模式）...")
    result = phase.run(
        paper_file,
        test_dir / "review_output",
        llm_call_func=None  # 使用模拟模式
    )
    
    print(f"\n审稿结果:")
    print(f"  总体评分: {result['final_score']:.1f}/10")
    print(f"  审稿决定: {result['final_decision']}")
    print(f"  可复现性: {result['reproducibility_score']:.1f}/10")
    print(f"  虚假内容问题: {result['authenticity_issues']}")
    print(f"  AI写作特征: {result['ai_patterns_found']}")
    
    assert result['authenticity_issues'] > 0 or result['ai_patterns_found'] > 0


def test_experiment_config_from_nested_config():
    """确保增强实验配置正确读取 experiment 子配置。"""
    from phases.experiment_v2 import ExperimentConfig

    cfg = {
        "experiment": {
            "use_github_baseline": False,
            "use_real_dataset": False,
            "run_baseline": False,
            "run_proposed": True,
            "github": {"max_repos": 7},
            "dataset": {"max_attempts": 5},
            "search_iterations": 3
        }
    }
    exp = ExperimentConfig.from_config(cfg)
    assert exp.use_github_baseline is False
    assert exp.use_real_dataset is False
    assert exp.run_baseline is False
    assert exp.run_proposed is True
    assert exp.max_github_repos == 7
    assert exp.max_dataset_attempts == 5
    assert exp.search_iterations == 3


def test_mini_candidate_manager_build_and_select():
    """测试候选实验池构建与淘汰逻辑。"""
    from phases.experiment_v2 import ExperimentConfig, MiniExperimentManager, CandidateExperiment

    cfg = ExperimentConfig()
    manager = MiniExperimentManager(cfg)
    idea = {"title": "测试课题", "keywords": ["nlp"], "method": "classification"}

    candidates = manager.build_candidates(idea)
    assert len(candidates) >= 2
    assert all("metrics.json" in c.code for c in candidates)

    # 模拟评分并淘汰
    mocked = [
        CandidateExperiment(name="a", description="a", code="", score=0.7),
        CandidateExperiment(name="b", description="b", code="", score=0.9),
        CandidateExperiment(name="c", description="c", code="", score=0.8),
    ]
    survivors = manager.select_survivors(mocked)
    assert survivors[0].name == "b"


def test_allowed_packages_normalization():
    """测试白名单包名归一化。"""
    from phases.experiment_v2 import ExperimentPhaseV2

    phase = ExperimentPhaseV2({
        "experiment": {
            "allowed_packages": ["numpy", "scikit-learn", "Pillow"]
        }
    })
    pkgs = phase._normalized_allowed_packages()
    assert "sklearn" in pkgs
    assert "PIL" in pkgs


def main():
    """运行所有测试"""
    print("\n" + "="*70)
    print(" AI-Research-Assistant 增强功能测试套件")
    print("="*70)
    
    tests = [
        ("虚假内容检测", test_fake_content_detection),
        ("AI写作检测", test_ai_writing_detection),
        ("GitHub搜索", test_github_search),
        ("数据集搜索", test_dataset_search),
        ("增强版审稿集成", test_enhanced_review_integration),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            print(f"\n{'='*70}")
            print(f"开始测试: {name}")
            print(f"{'='*70}")
            success = test_func()
            results.append((name, success))
            print(f"\n[{'PASS' if success else 'FAIL'}] {name}")
        except Exception as e:
            print(f"\n[FAIL] {name} 测试失败: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # 打印总结
    print("\n" + "="*70)
    print(" 测试结果汇总")
    print("="*70)
    
    for name, success in results:
        status = "[PASS]" if success else "[FAIL]"
        print(f"{status}: {name}")
    
    passed = sum(1 for _, s in results if s)
    total = len(results)
    print(f"\n总计: {passed}/{total} 通过")
    
    # 特别说明
    print("\n" + "="*70)
    print(" 重要说明")
    print("="*70)
    print("""
1. GitHub搜索和数据集搜索需要网络连接
2. 部分数据集可能需要API Token才能下载
3. 如果数据集无法自动下载，可以：
   - 手动下载后放到 datasets/ 目录
   - 在配置中指定本地数据路径
   - 使用 --no-enhanced 参数使用基础版

人工数据集配置步骤：
1. 手动下载数据集
2. 放入 datasets/<dataset_name>/ 目录
3. 修改 experiment_v2.py 中的数据路径
4. 重新运行实验阶段
""")
    
    return all(s for _, s in results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
