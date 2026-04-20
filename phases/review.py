"""
Phase 4: 审核阶段 (Review)

功能：
1. 多维度论文审核
2. 生成改进建议
3. 迭代改进论文
4. 生成审核报告

参考：AI-Scientist-v2 的多轮审阅机制
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class ReviewScore:
    """审核评分"""
    dimension: str
    score: float  # 0-10
    comment: str
    suggestions: List[str]


@dataclass
class ReviewReport:
    """审核报告"""
    round: int
    overall_score: float
    decision: str  # accept / revise / reject
    sections: Dict[str, ReviewScore]
    general_comments: List[str]
    improvement_plan: List[str]


class ReviewPhase:
    """审核阶段处理器"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.models = config.get('models', {})
        self.review_config = config.get('review', {})
        self.dimensions = self.review_config.get('dimensions', [
            'novelty', 'significance', 'methodology', 'experiments', 
            'presentation', 'completeness'
        ])
        self.threshold = self.review_config.get('threshold', 7.0)
    
    def load_paper(self, paper_file: Path) -> str:
        """加载论文内容"""
        with open(paper_file, 'r', encoding='utf-8') as f:
            return f.read()
    
    def generate_review_prompt(self, paper_content: str, 
                              round_num: int) -> str:
        """
        生成审核 Prompt
        
        参考 AI-Scientist-v2 的审阅风格
        """
        dimensions_str = '\n'.join([
            f"  - {d}: 评估该维度（0-10分）"
            for d in self.dimensions
        ])
        
        return f"""你是一位严格的学术论文审稿人。请对以下论文进行第 {round_num} 轮审核。

## 论文内容

```markdown
{paper_content[:8000]}  # 限制长度，避免过长
```

## 审核维度

{dimensions_str}

## 审核要求

1. **创新性 (novelty)**: 研究是否有新见解？与现有工作有何不同？
2. **重要性 (significance)**: 结果对领域是否有价值？
3. **方法论 (methodology)**: 方法是否科学合理？是否可复现？
4. **实验设计 (experiments)**: 实验是否充分？结果是否令人信服？
5. **表达清晰度 (presentation)**: 写作是否清晰？结构是否合理？
6. **完整性 (completeness)**: 是否遗漏重要内容？论证是否充分？

## 输出格式

请以 JSON 格式输出审核结果：

```json
{{
  "overall_score": 7.5,
  "decision": "revise",  // accept / revise / reject
  "sections": {{
    "novelty": {{
      "score": 8.0,
      "comment": "创新点描述...",
      "suggestions": ["建议1", "建议2"]
    }},
    // ... 其他维度
  }},
  "general_comments": [
    "总体评价1",
    "总体评价2"
  ],
  "improvement_plan": [
    "具体改进建议1",
    "具体改进建议2"
  ]
}}
```

评分标准：
- 9-10分: 优秀，几乎无需修改
- 7-8分: 良好，需要小幅修改
- 5-6分: 一般，需要较大修改
- <5分: 较差，需要重大修改或拒稿

注意：只输出 JSON，不要其他内容。
"""
    
    def parse_review_response(self, response: str, round_num: int) -> ReviewReport:
        """解析审核响应"""
        # 提取 JSON
        json_match = re.search(r'```json\s*(\{.+\})\s*```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = response
        
        try:
            data = json.loads(json_str)
            
            # 解析各维度评分
            sections = {}
            for dim in self.dimensions:
                dim_data = data.get('sections', {}).get(dim, {})
                sections[dim] = ReviewScore(
                    dimension=dim,
                    score=float(dim_data.get('score', 5.0)),
                    comment=dim_data.get('comment', ''),
                    suggestions=dim_data.get('suggestions', [])
                )
            
            return ReviewReport(
                round=round_num,
                overall_score=float(data.get('overall_score', 5.0)),
                decision=data.get('decision', 'revise'),
                sections=sections,
                general_comments=data.get('general_comments', []),
                improvement_plan=data.get('improvement_plan', [])
            )
            
        except json.JSONDecodeError as e:
            print(f"审核结果解析错误: {e}")
            # 返回默认报告
            return ReviewReport(
                round=round_num,
                overall_score=5.0,
                decision="revise",
                sections={},
                general_comments=["解析审核结果失败"],
                improvement_plan=[]
            )
    
    def generate_revision_prompt(self, paper_content: str, 
                                review_report: ReviewReport) -> str:
        """生成修改 Prompt"""
        improvements = '\n'.join([
            f"{i+1}. {item}" 
            for i, item in enumerate(review_report.improvement_plan)
        ])
        
        weak_sections = [
            name for name, score in review_report.sections.items() 
            if score.score < self.threshold
        ]
        
        return f"""根据审核意见修改论文。

## 原始论文

```markdown
{paper_content}
```

## 审核意见

**总体评分**: {review_report.overall_score}/10
**决定**: {review_report.decision}

**需要重点改进的章节**: {', '.join(weak_sections) if weak_sections else '无明显薄弱环节'}

**改进建议**:
{improvements}

## 修改要求

1. 针对审核意见逐条修改
2. 重点改进评分较低的章节
3. 保持论文整体结构
4. 提高写作质量和论证充分性

## 输出

输出修改后的完整论文（Markdown 格式）。
"""
    
    def save_review_report(self, report: ReviewReport, output_file: Path):
        """保存审核报告"""
        data = {
            "round": report.round,
            "overall_score": report.overall_score,
            "decision": report.decision,
            "sections": {
                name: {
                    "score": score.score,
                    "comment": score.comment,
                    "suggestions": score.suggestions
                }
                for name, score in report.sections.items()
            },
            "general_comments": report.general_comments,
            "improvement_plan": report.improvement_plan
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def run(self, paper_file: Path, output_dir: Path,
            llm_call_func=None) -> Dict:
        """
        运行审核阶段
        
        Args:
            paper_file: 论文文件路径
            output_dir: 输出目录
            llm_call_func: LLM 调用函数
            
        Returns:
            执行结果
        """
        print("=" * 60)
        print("Phase 4: 审核阶段 (Review)")
        print("=" * 60)
        
        # 加载论文
        paper_content = self.load_paper(paper_file)
        
        rounds = self.review_config.get('rounds', 2)
        reports = []
        
        for round_num in range(1, rounds + 1):
            print(f"\n{'='*40}")
            print(f"第 {round_num}/{rounds} 轮审核")
            print(f"{'='*40}")
            
            # 1. 审核
            print("\n[1/2] 执行审核...")
            prompt = self.generate_review_prompt(paper_content, round_num)
            
            if llm_call_func:
                response = llm_call_func(prompt, model=self.models.get('review', 'gpt-4o'))
                report = self.parse_review_response(response, round_num)
            else:
                # 模拟审核
                report = ReviewReport(
                    round=round_num,
                    overall_score=7.5,
                    decision="revise",
                    sections={},
                    general_comments=["模拟审核意见"],
                    improvement_plan=["建议改进"]
                )
            
            reports.append(report)
            
            print(f"  [OK] 总体评分: {report.overall_score:.1f}/10")
            print(f"  [OK] 审核决定: {report.decision}")
            
            # 显示各维度评分
            if report.sections:
                print(f"  [OK] 维度评分:")
                for name, score in report.sections.items():
                    print(f"    - {name}: {score.score:.1f}")
            
            # 保存审核报告
            output_dir.mkdir(parents=True, exist_ok=True)
            report_file = output_dir / f"review_round_{round_num}.json"
            self.save_review_report(report, report_file)
            print(f"  [OK] 报告已保存: {report_file}")
            
            # 2. 修改（如果不是最后一轮且需要修改）
            if round_num < rounds and report.decision in ['revise', 'reject']:
                print("\n[2/2] 根据审核意见修改论文...")
                
                revision_prompt = self.generate_revision_prompt(paper_content, report)
                
                if llm_call_func:
                    revised_content = llm_call_func(
                        revision_prompt, 
                        model=self.models.get('writeup', 'gpt-4o')
                    )
                else:
                    revised_content = paper_content + "\n\n[已修改]"
                
                # 更新论文内容
                paper_content = revised_content
                
                # 保存修改后的论文
                revised_file = output_dir / f"paper_round_{round_num}.md"
                with open(revised_file, 'w', encoding='utf-8') as f:
                    f.write(paper_content)
                print(f"  [OK] 修改后的论文已保存: {revised_file}")
            else:
                print("\n[2/2] 无需修改，进入下一轮...")
        
        # 保存最终论文
        final_paper_file = output_dir / "paper_final.md"
        with open(final_paper_file, 'w', encoding='utf-8') as f:
            f.write(paper_content)
        print(f"\n[OK] 最终论文已保存: {final_paper_file}")
        
        # 生成审核总结
        summary = {
            "total_rounds": rounds,
            "final_score": reports[-1].overall_score if reports else 0,
            "final_decision": reports[-1].decision if reports else "unknown",
            "rounds": [
                {
                    "round": r.round,
                    "score": r.overall_score,
                    "decision": r.decision
                }
                for r in reports
            ]
        }
        
        summary_file = output_dir / "review_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        return {
            "success": True,
            "final_paper": str(final_paper_file),
            "final_score": summary["final_score"],
            "final_decision": summary["final_decision"],
            "total_rounds": rounds,
            "reports": [str(output_dir / f"review_round_{i+1}.json") for i in range(rounds)]
        }


# 便捷函数
def run_review(paper_file: str, output_dir: str, 
               config: Dict, llm_call_func=None) -> Dict:
    """运行审核阶段的便捷函数"""
    phase = ReviewPhase(config)
    return phase.run(Path(paper_file), Path(output_dir), llm_call_func)


if __name__ == "__main__":
    # 测试
    config = {
        "models": {"review": "gpt-4o"},
        "review": {
            "rounds": 2,
            "threshold": 7.0,
            "dimensions": ['novelty', 'significance', 'methodology', 
                          'experiments', 'presentation', 'completeness']
        }
    }
    
    print("ReviewPhase 加载成功")
