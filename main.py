"""
AI-Research-Assistant Skill 主入口

使用方法：
    python main.py --topic topic.md --output ./output
    python main.py --phase ideation --topic topic.md
    python main.py --phase experiment --ideas ideas.json --idea-id 1
    python main.py --phase writeup --summary summary.json
    python main.py --phase review --paper paper.md
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Optional, Callable

# 添加路径
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "phases"))
sys.path.insert(0, str(Path(__file__).parent / "utils"))

from phases.ideation import IdeationPhase
from phases.experiment import ExperimentPhase
from phases.experiment_v2 import ExperimentPhaseV2
from phases.writeup import WriteupPhase
from phases.review import ReviewPhase
from phases.review_v2 import ReviewPhaseV2
from utils.formatter import PaperFormatter


class AIResearchAssistant:
    """AI 科研助手主类"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化
        
        Args:
            config_path: 配置文件路径，默认使用内置配置
        """
        self.config = self._load_config(config_path)
        self.llm_call_func: Optional[Callable] = None
        
        # 初始化各阶段
        self.ideation = IdeationPhase(self.config)
        
        # 选择实验阶段版本
        self.use_enhanced_experiment = self.config.get('use_enhanced_experiment', True)
        if self.use_enhanced_experiment:
            self.experiment = ExperimentPhaseV2(self.config)
        else:
            self.experiment = ExperimentPhase(self.config)
        
        self.writeup = WriteupPhase(self.config)
        
        # 选择审稿阶段版本
        self.use_enhanced_review = self.config.get('review', {}).get('use_enhanced', True)
        if self.use_enhanced_review:
            self.review = ReviewPhaseV2(self.config)
        else:
            self.review = ReviewPhase(self.config)
    
    @staticmethod
    def _load_config_static(config_path: Optional[str]) -> Dict:
        """静态方法：加载配置"""
        if config_path and Path(config_path).exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                try:
                    import yaml
                    return yaml.safe_load(f)
                except ImportError:
                    # 如果没有 yaml，尝试 json
                    return json.load(f)
        
        # 默认配置
        return {
            "models": {
                "ideation": "gpt-4o",
                "experiment": "claude-3-5-sonnet",
                "writeup": "gpt-4o",
                "review": "gpt-4o"
            },
            "experiment": {
                "timeout": 600,
                "max_retries": 3,
                "use_github_baseline": True,
                "use_real_dataset": True,
                "run_baseline": True,
                "run_proposed": True
            },
            "review": {
                "rounds": 2,
                "threshold": 7.0
            },
            "output": {
                "format": "markdown",
                "language": "zh-CN"
            },
            "use_enhanced_experiment": True
        }
    
    def _load_config(self, config_path: Optional[str]) -> Dict:
        """加载配置（实例方法）"""
        return self._load_config_static(config_path)
    
    def set_llm_callback(self, callback: Callable):
        """
        设置 LLM 调用回调函数
        
        Args:
            callback: 函数签名 (prompt: str, model: str) -> str
        """
        self.llm_call_func = callback
    
    def run_full_pipeline(self, topic_file: str, output_dir: str,
                         idea_id: int = 1) -> Dict:
        """
        运行完整流程
        
        Args:
            topic_file: 主题描述文件
            output_dir: 输出目录
            idea_id: 要执行的假设 ID
            
        Returns:
            执行结果
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        print("\n" + "=" * 70)
        print("  AI-Research-Assistant: 完整科研流程")
        print("=" * 70)
        
        results = {
            "phases": {},
            "output_dir": str(output_path),
            "success": True
        }
        
        try:
            # Phase 1: 构思
            print("\n" + "=" * 70)
            ideas_file = output_path / "ideas.json"
            result1 = self.ideation.run(
                Path(topic_file), ideas_file, self.llm_call_func
            )
            results["phases"]["ideation"] = result1
            
            if not result1.get("success"):
                print("\n[FAIL] 构思阶段失败")
                results["success"] = False
                return results
            
            # Phase 2: 实验
            print("\n" + "=" * 70)
            exp_dir = output_path / "experiment"
            result2 = self.experiment.run(
                ideas_file, idea_id, exp_dir, self.llm_call_func
            )
            results["phases"]["experiment"] = result2
            
            if not result2.get("success"):
                print("\n[WARN] 实验阶段失败，但仍继续撰写...")
            
            # Phase 3: 撰写
            print("\n" + "=" * 70)
            summary_file = exp_dir / "summary.json"
            result3 = self.writeup.run(
                ideas_file, idea_id, summary_file, exp_dir, self.llm_call_func
            )
            results["phases"]["writeup"] = result3
            
            if not result3.get("success"):
                print("\n[FAIL] 撰写阶段失败")
                results["success"] = False
                return results
            
            # Phase 4: 审核
            print("\n" + "=" * 70)
            paper_file = exp_dir / "paper.md"
            review_dir = output_path / "review"
            
            # 根据配置选择审稿版本
            if self.use_enhanced_review:
                print("使用增强版审稿（包含虚假内容检测和AI写作审查）")
                result4 = self.review.run(
                    paper_file, review_dir, exp_dir, self.llm_call_func
                )
            else:
                result4 = self.review.run(
                    paper_file, review_dir, self.llm_call_func
                )
            results["phases"]["review"] = result4
            
            # 最终总结
            print("\n" + "=" * 70)
            print("  流程完成总结")
            print("=" * 70)
            print(f"\n[OK] 构思阶段: 生成 {result1.get('total_ideas', 0)} 个假设")
            print(f"[OK] 实验阶段: {'成功' if result2.get('success') else '失败'}")
            print(f"[OK] 撰写阶段: {result3.get('word_count', 0)} 字")
            print(f"[OK] 审核阶段: 最终评分 {result4.get('final_score', 0):.1f}/10")
            
            print(f"\n输出目录: {output_dir}")
            print(f"最终论文: {result4.get('final_paper', paper_file)}")
            
        except Exception as e:
            print(f"\n[FAIL] 流程执行出错: {e}")
            import traceback
            traceback.print_exc()
            results["success"] = False
            results["error"] = str(e)
        
        # 保存执行记录
        record_file = output_path / "pipeline_record.json"
        with open(record_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        return results
    
    def run_ideation(self, topic_file: str, output_file: str) -> Dict:
        """仅运行构思阶段"""
        return self.ideation.run(
            Path(topic_file), Path(output_file), self.llm_call_func
        )
    
    def run_experiment(self, ideas_file: str, idea_id: int, 
                       output_dir: str) -> Dict:
        """仅运行实验阶段"""
        return self.experiment.run(
            Path(ideas_file), idea_id, Path(output_dir), self.llm_call_func
        )
    
    def run_writeup(self, ideas_file: str, idea_id: int,
                   summary_file: str, output_dir: str) -> Dict:
        """仅运行撰写阶段"""
        return self.writeup.run(
            Path(ideas_file), idea_id, 
            Path(summary_file), Path(output_dir),
            self.llm_call_func
        )
    
    def run_review(
        self,
        paper_file: str,
        output_dir: str,
        experiment_dir: Optional[str] = None,
    ) -> Dict:
        """仅运行审核阶段"""
        if self.use_enhanced_review:
            return self.review.run(
                Path(paper_file),
                Path(output_dir),
                Path(experiment_dir) if experiment_dir else None,
                self.llm_call_func,
            )
        return self.review.run(
            Path(paper_file), Path(output_dir), self.llm_call_func
        )


def mock_llm_call(prompt: str, model: str = "gpt-4o") -> str:
    """模拟 LLM 调用（用于测试）"""
    print(f"  [Mock LLM Call] Model: {model}, Prompt length: {len(prompt)}")
    
    # 根据 prompt 内容返回模拟响应
    if "假设" in prompt and "JSON" in prompt:
        return '''```json
{
  "ideas": [
    {
      "id": 1,
      "title": "基于CNN的人群密度估计方法",
      "hypothesis": "卷积神经网络可以有效估计施工场地的人群密度",
      "method": "使用ResNet作为骨干网络，结合密度图回归",
      "expected_result": "在测试集上达到MAE < 10的性能",
      "contribution": "提出适用于施工场景的轻量级密度估计模型",
      "feasibility": 0.85,
      "novelty": 0.75,
      "significance": 0.80,
      "keywords": ["人群密度", "CNN", "施工安全"],
      "related_work": ["文献1", "文献2"]
    }
  ]
}
```'''
    
    elif "```python" in prompt:
        return '''```python
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import json
import os

OUTPUT_DIR = "outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def main():
    print("开始实验...")
    
    # 生成模拟数据
    np.random.seed(42)
    data = np.random.randn(100)
    
    # 计算指标
    mean = np.mean(data)
    std = np.std(data)
    
    print(f"Mean: {mean:.4f}")
    print(f"Std: {std:.4f}")
    
    # 绘图
    plt.figure(figsize=(8, 6))
    plt.hist(data, bins=20, edgecolor='black')
    plt.title('Data Distribution')
    plt.savefig(os.path.join(OUTPUT_DIR, 'distribution.png'))
    plt.close()
    
    # 保存指标
    metrics = {
        "accuracy": 0.85,
        "precision": 0.82,
        "recall": 0.88,
        "f1": 0.85
    }
    
    with open(os.path.join(OUTPUT_DIR, 'metrics.json'), 'w') as f:
        json.dump(metrics, f, indent=2)
    
    print("实验完成!")

if __name__ == "__main__":
    main()
```'''
    
    elif "审核" in prompt:
        return '''```json
{
  "overall_score": 7.5,
  "decision": "revise",
  "sections": {
    "novelty": {
      "score": 8.0,
      "comment": "具有一定的创新性",
      "suggestions": ["进一步突出创新点"]
    },
    "methodology": {
      "score": 7.5,
      "comment": "方法描述较清晰",
      "suggestions": ["补充更多实现细节"]
    }
  },
  "general_comments": ["整体质量良好"],
  "improvement_plan": ["补充实验细节", "完善图表说明"]
}
```'''
    
    else:
        return f"[Generated content for: {prompt[:50]}...]"


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description="AI-Research-Assistant: 自动化科研助手"
    )
    
    parser.add_argument(
        "--phase",
        choices=["full", "ideation", "experiment", "writeup", "review"],
        default="full",
        help="执行阶段 (默认: full)"
    )
    
    parser.add_argument(
        "--topic",
        help="主题描述文件路径 (用于 ideation 阶段)"
    )
    
    parser.add_argument(
        "--ideas",
        help="ideas.json 文件路径 (用于 experiment/writeup 阶段)"
    )
    
    parser.add_argument(
        "--idea-id",
        type=int,
        default=1,
        help="要执行的假设 ID (默认: 1)"
    )
    
    parser.add_argument(
        "--summary",
        help="summary.json 文件路径 (用于 writeup 阶段)"
    )
    
    parser.add_argument(
        "--paper",
        help="论文文件路径 (用于 review 阶段)"
    )

    parser.add_argument(
        "--experiment-dir",
        help="实验输出目录 (用于增强审稿时交叉核对 metrics 等，可选)"
    )
    
    parser.add_argument(
        "--output",
        "-o",
        default="./research_output",
        help="输出目录 (默认: ./research_output)"
    )
    
    parser.add_argument(
        "--config",
        "-c",
        help="配置文件路径"
    )
    
    parser.add_argument(
        "--mock",
        action="store_true",
        help="使用模拟 LLM（用于测试）"
    )
    
    parser.add_argument(
        "--enhanced",
        action="store_true",
        default=True,
        help="使用增强版实验阶段（支持GitHub和数据集）"
    )
    
    parser.add_argument(
        "--no-enhanced",
        action="store_false",
        dest="enhanced",
        help="使用基础版实验阶段"
    )
    
    parser.add_argument(
        "--enhanced-review",
        action="store_true",
        default=True,
        help="使用增强版审稿（虚假内容检测+AI写作审查）"
    )
    
    parser.add_argument(
        "--no-enhanced-review",
        action="store_false",
        dest="enhanced_review",
        help="使用基础版审稿"
    )
    
    args = parser.parse_args()
    
    # 加载配置
    config = AIResearchAssistant._load_config_static(args.config)
    config['use_enhanced_experiment'] = args.enhanced
    config['review'] = config.get('review', {})
    config['review']['use_enhanced'] = args.enhanced_review
    
    # 初始化
    assistant = AIResearchAssistant(args.config)
    assistant.config = config  # 更新配置
    
    # 重新初始化实验阶段
    if args.enhanced:
        assistant.experiment = ExperimentPhaseV2(config)
        assistant.use_enhanced_experiment = True
        print("[INFO] 使用增强版实验阶段（支持GitHub和数据集）")
    else:
        assistant.experiment = ExperimentPhase(config)
        assistant.use_enhanced_experiment = False
        print("[INFO] 使用基础版实验阶段")
    
    # 重新初始化审稿阶段
    if args.enhanced_review:
        assistant.review = ReviewPhaseV2(config)
        assistant.use_enhanced_review = True
        print("[INFO] 使用增强版审稿（虚假内容检测+AI写作审查）")
    else:
        assistant.review = ReviewPhase(config)
        assistant.use_enhanced_review = False
        print("[INFO] 使用基础版审稿")
    
    if args.mock:
        assistant.set_llm_callback(mock_llm_call)
        print("[!] 使用模拟 LLM 模式（测试用）\n")
    
    # 执行
    if args.phase == "full":
        if not args.topic:
            print("错误: --topic 参数是必需的（完整流程模式）")
            return 1
        
        result = assistant.run_full_pipeline(args.topic, args.output, args.idea_id)
        
    elif args.phase == "ideation":
        if not args.topic:
            print("错误: --topic 参数是必需的")
            return 1
        
        output_file = Path(args.output) / "ideas.json"
        result = assistant.run_ideation(args.topic, str(output_file))
        
    elif args.phase == "experiment":
        if not args.ideas:
            print("错误: --ideas 参数是必需的")
            return 1
        
        result = assistant.run_experiment(
            args.ideas, args.idea_id, args.output
        )
        
    elif args.phase == "writeup":
        if not args.ideas or not args.summary:
            print("错误: --ideas 和 --summary 参数是必需的")
            return 1
        
        result = assistant.run_writeup(
            args.ideas, args.idea_id, args.summary, args.output
        )
        
    elif args.phase == "review":
        if not args.paper:
            print("错误: --paper 参数是必需的")
            return 1
        
        result = assistant.run_review(
            args.paper, args.output, args.experiment_dir
        )
    
    # 结果
    if result.get("success"):
        print("\n[OK] 执行成功!")
        return 0
    else:
        print("\n[FAIL] 执行失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
