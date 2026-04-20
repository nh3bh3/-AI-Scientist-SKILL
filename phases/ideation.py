"""
Phase 1: 构思阶段 (Ideation)

功能：
1. 分析研究主题
2. 检索相关文献
3. 生成研究假设
4. 评估可行性
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict


@dataclass
class ResearchIdea:
    """研究假设数据结构"""
    id: int
    title: str
    hypothesis: str
    method: str
    expected_result: str
    contribution: str
    feasibility: float  # 0-1
    novelty: float  # 0-1
    significance: float  # 0-1
    related_work: List[str]
    keywords: List[str]
    
    def to_dict(self) -> Dict:
        return asdict(self)


class IdeationPhase:
    """构思阶段处理器"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.models = config.get('models', {})
        self.search_config = config.get('search', {})
    
    def parse_topic(self, topic_content: str) -> Dict:
        """
        解析主题描述文件
        
        Args:
            topic_content: Markdown 格式的主题描述
            
        Returns:
            解析后的主题信息
        """
        # 提取标题
        title_match = re.search(r'^#\s+(.+)$', topic_content, re.MULTILINE)
        title = title_match.group(1) if title_match else "未命名研究"
        
        # 提取关键词
        keywords = []
        keywords_match = re.search(r'##?\s*关键词\s*\n+([^#]+)', topic_content, re.IGNORECASE)
        if keywords_match:
            keywords_text = keywords_match.group(1)
            # 支持逗号、顿号分隔
            keywords = [k.strip() for k in re.split(r'[,，、]', keywords_text) if k.strip()]
        
        # 提取研究背景
        background = ""
        bg_match = re.search(r'##?\s*(研究背景|背景|Background)\s*\n+([^#]+)', topic_content, re.IGNORECASE)
        if bg_match:
            background = bg_match.group(2).strip()
        
        # 提取研究目标
        objectives = ""
        obj_match = re.search(r'##?\s*(研究目标|目标|预期目标|Objectives)\s*\n+([^#]+)', topic_content, re.IGNORECASE)
        if obj_match:
            objectives = obj_match.group(2).strip()
        
        return {
            "title": title,
            "keywords": keywords,
            "background": background,
            "objectives": objectives,
            "raw_content": topic_content
        }
    
    def search_literature(self, topic_info: Dict) -> List[Dict]:
        """
        检索相关文献
        
        Args:
            topic_info: 主题信息
            
        Returns:
            文献列表
        """
        if not self.search_config.get('enabled', True):
            return []
        
        # 构建检索查询
        keywords = topic_info.get('keywords', [])
        query = " ".join(keywords[:3]) if keywords else topic_info.get('title', '')
        
        # 这里应该调用 WebSearch 或专门的知识库
        # 返回模拟数据作为示例
        literature = [
            {
                "title": f"相关研究 {i}: {topic_info['title']} 的相关工作",
                "authors": ["Author A", "Author B"],
                "year": 2023 + i,
                "venue": "Conference/Journal Name",
                "abstract": f"This paper explores aspects related to {query}...",
                "url": f"https://example.com/paper{i}"
            }
            for i in range(1, 6)
        ]
        
        return literature
    
    def generate_ideas_prompt(self, topic_info: Dict, literature: List[Dict]) -> str:
        """
        生成假设生成的 Prompt
        
        Args:
            topic_info: 主题信息
            literature: 文献列表
            
        Returns:
            LLM Prompt
        """
        lit_summary = "\n".join([
            f"{i+1}. {lit['title']} ({lit['year']})\n   {lit['abstract'][:100]}..."
            for i, lit in enumerate(literature[:5])
        ])
        
        prompt = f"""你是一个专业的学术研究助手。请基于以下研究主题和相关文献，生成 3-5 个创新的研究假设。

## 研究主题
{topic_info['title']}

## 关键词
{', '.join(topic_info['keywords'])}

## 研究背景
{topic_info['background']}

## 研究目标
{topic_info['objectives']}

## 相关文献
{lit_summary}

## 任务要求

请生成 3-5 个研究假设，每个假设应包含：

1. **标题**：简洁明了的假设标题（不超过20字）
2. **研究假设**：具体的假设描述（1-2句话）
3. **建议方法**：实现该假设的技术方法
4. **预期结果**：预期的研究成果
5. **研究贡献**：该假设的创新点和学术价值
6. **可行性评分**：0-1 之间的小数
7. **创新性评分**：0-1 之间的小数
8. **重要性评分**：0-1 之间的小数
9. **相关关键词**：3-5个相关关键词

## 输出格式

请以 JSON 格式输出，示例如下：

```json
{{
  "ideas": [
    {{
      "id": 1,
      "title": "假设标题",
      "hypothesis": "具体的假设描述...",
      "method": "建议采用的方法...",
      "expected_result": "预期得到的结果...",
      "contribution": "该研究的创新点和价值...",
      "feasibility": 0.85,
      "novelty": 0.80,
      "significance": 0.75,
      "keywords": ["关键词1", "关键词2"],
      "related_work": ["相关文献1", "相关文献2"]
    }}
  ]
}}
```

注意：
- 假设应该具体、可验证
- 方法应该可行，考虑到资源和时间限制
- 评分应该客观，基于当前技术水平
- 只输出 JSON，不要其他内容
"""
        return prompt
    
    def parse_ideas_response(self, response: str) -> List[ResearchIdea]:
        """
        解析 LLM 返回的假设
        
        Args:
            response: LLM 响应文本
            
        Returns:
            ResearchIdea 列表
        """
        # 提取 JSON
        json_match = re.search(r'```json\s*(\{.+\})\s*```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = response
        
        try:
            data = json.loads(json_str)
            ideas_data = data.get('ideas', [])
            
            ideas = []
            for idea_data in ideas_data:
                idea = ResearchIdea(
                    id=idea_data.get('id', len(ideas) + 1),
                    title=idea_data.get('title', ''),
                    hypothesis=idea_data.get('hypothesis', ''),
                    method=idea_data.get('method', ''),
                    expected_result=idea_data.get('expected_result', ''),
                    contribution=idea_data.get('contribution', ''),
                    feasibility=idea_data.get('feasibility', 0.5),
                    novelty=idea_data.get('novelty', 0.5),
                    significance=idea_data.get('significance', 0.5),
                    related_work=idea_data.get('related_work', []),
                    keywords=idea_data.get('keywords', [])
                )
                ideas.append(idea)
            
            return ideas
            
        except json.JSONDecodeError as e:
            print(f"JSON 解析错误: {e}")
            print(f"响应内容: {response[:500]}...")
            return []
    
    def rank_ideas(self, ideas: List[ResearchIdea]) -> List[ResearchIdea]:
        """
        对假设进行综合排序
        
        评分公式：综合得分 = 可行性×0.3 + 创新性×0.4 + 重要性×0.3
        """
        for idea in ideas:
            idea.feasibility = float(idea.feasibility)
            idea.novelty = float(idea.novelty)
            idea.significance = float(idea.significance)
        
        # 按综合得分排序
        return sorted(ideas, 
                     key=lambda x: x.feasibility * 0.3 + x.novelty * 0.4 + x.significance * 0.3,
                     reverse=True)
    
    def save_ideas(self, ideas: List[ResearchIdea], output_path: Path):
        """保存假设到文件"""
        data = {
            "topic": "研究主题",
            "total_ideas": len(ideas),
            "ideas": [idea.to_dict() for idea in ideas]
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def run(self, topic_file: Path, output_file: Path, 
            llm_call_func=None) -> Dict:
        """
        运行构思阶段
        
        Args:
            topic_file: 主题描述文件路径
            output_file: 输出文件路径
            llm_call_func: LLM 调用函数（外部传入）
            
        Returns:
            执行结果统计
        """
        print("=" * 60)
        print("Phase 1: 构思阶段 (Ideation)")
        print("=" * 60)
        
        # 1. 读取主题文件
        print("\n[1/4] 读取研究主题...")
        with open(topic_file, 'r', encoding='utf-8') as f:
            topic_content = f.read()
        
        topic_info = self.parse_topic(topic_content)
        print(f"  [OK] 主题: {topic_info['title']}")
        print(f"  [OK] 关键词: {', '.join(topic_info['keywords'])}")
        
        # 2. 检索文献
        print("\n[2/4] 检索相关文献...")
        literature = self.search_literature(topic_info)
        print(f"  [OK] 找到 {len(literature)} 篇相关文献")
        
        # 3. 生成假设
        print("\n[3/4] 生成研究假设...")
        prompt = self.generate_ideas_prompt(topic_info, literature)
        
        # 调用 LLM（外部传入函数）
        if llm_call_func:
            response = llm_call_func(prompt, model=self.models.get('ideation', 'gpt-4o'))
            ideas = self.parse_ideas_response(response)
        else:
            # 模拟返回
            ideas = [
                ResearchIdea(
                    id=1,
                    title="示例假设1",
                    hypothesis="这是一个示例研究假设",
                    method="建议方法",
                    expected_result="预期结果",
                    contribution="研究贡献",
                    feasibility=0.8,
                    novelty=0.7,
                    significance=0.75,
                    related_work=[],
                    keywords=["示例"]
                )
            ]
        
        print(f"  [OK] 生成 {len(ideas)} 个研究假设")
        
        # 4. 排序并保存
        print("\n[4/4] 评估与排序...")
        ideas = self.rank_ideas(ideas)
        
        for i, idea in enumerate(ideas[:3], 1):
            score = idea.feasibility * 0.3 + idea.novelty * 0.4 + idea.significance * 0.3
            print(f"  {i}. {idea.title} (综合得分: {score:.2f})")
        
        self.save_ideas(ideas, output_file)
        print(f"\n[OK] 结果已保存: {output_file}")
        
        return {
            "success": True,
            "topic": topic_info['title'],
            "total_ideas": len(ideas),
            "top_idea": ideas[0].title if ideas else None,
            "output_file": str(output_file)
        }


# 便捷函数
def run_ideation(topic_file: str, output_file: str, config: Dict, llm_call_func=None) -> Dict:
    """运行构思阶段的便捷函数"""
    phase = IdeationPhase(config)
    return phase.run(Path(topic_file), Path(output_file), llm_call_func)


if __name__ == "__main__":
    # 测试
    config = {
        "models": {"ideation": "gpt-4o"},
        "search": {"enabled": True}
    }
    
    # 创建测试主题文件
    test_topic = """# 基于深度学习的施工场地人群行为分析

## 关键词
人群检测、行为识别、深度学习、施工安全、3D视觉

## 研究背景
施工场地人员众多，传统监控方式难以实时识别危险行为，需要智能化的监测手段。

## 研究目标
构建一个能够实时检测人群异常行为的智能系统，提高施工安全性。
"""
    
    test_topic_file = Path("test_topic.md")
    test_output_file = Path("test_ideas.json")
    
    with open(test_topic_file, 'w', encoding='utf-8') as f:
        f.write(test_topic)
    
    result = run_ideation(str(test_topic_file), str(test_output_file), config)
    print(f"\n结果: {result}")
