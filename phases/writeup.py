"""
Phase 3: 撰写阶段 (Write-up)

功能：
1. 基于实验结果生成论文
2. 图表处理和描述
3. 引用管理
4. 多章节协同写作
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class PaperSection:
    """论文章节"""
    name: str
    title: str
    content: str
    word_count: int
    required: bool


class WriteupPhase:
    """论文撰写阶段处理器"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.models = config.get('models', {})
        self.output_config = config.get('output', {})
        self.paper_config = config.get('paper_structure', {})
    
    def load_experiment_results(self, summary_file: Path) -> Dict:
        """加载实验结果"""
        with open(summary_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def load_idea(self, ideas_file: Path, idea_id: int) -> Optional[Dict]:
        """加载研究假设"""
        with open(ideas_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for idea in data.get('ideas', []):
            if idea.get('id') == idea_id:
                return idea
        return data.get('ideas', [{}])[0]
    
    def generate_abstract_prompt(self, idea: Dict, results: Dict) -> str:
        """生成摘要 Prompt"""
        metrics = results.get('metrics', {})
        metrics_str = "\n".join([f"- {k}: {v}" for k, v in metrics.items()]) if metrics else "未提供具体指标"
        
        return f"""请基于以下研究信息撰写论文摘要（约300字）。

## 研究信息

**标题**: {idea.get('title', '')}

**研究假设**: {idea.get('hypothesis', '')}

**方法**: {idea.get('method', '')}

**预期贡献**: {idea.get('contribution', '')}

**实验结果**:
{metrics_str}

## 摘要要求

1. 结构：研究背景 → 方法 → 主要结果 → 结论/贡献
2. 突出创新点和主要发现
3. 包含具体数值（如果有）
4. 语言简洁准确

## 输出

直接输出摘要内容，不需要标题。
"""
    
    def generate_introduction_prompt(self, idea: Dict, results: Dict) -> str:
        """生成引言 Prompt"""
        return f"""请撰写论文引言部分（约800字）。

## 研究信息

**标题**: {idea.get('title', '')}

**研究背景**: {idea.get('background', '待补充')}

**研究假设**: {idea.get('hypothesis', '')}

**研究贡献**: {idea.get('contribution', '')}

## 引言结构

1. **研究背景与动机**（第1段）
   - 介绍研究领域的重要性
   - 指出当前存在的问题

2. **相关工作**（第2段，简要）
   - 提及2-3个相关研究方向
   - 指出现有研究的不足

3. **研究问题**（第3段）
   - 明确本文要解决的问题
   - 提出研究假设

4. **主要贡献**（第4段）
   - 列出2-3点具体贡献
   - 简述方法创新

5. **论文结构**（第5段，可选）
   - 简述各章节内容

## 输出

直接输出引言正文，使用 Markdown 格式。
"""
    
    def generate_method_prompt(self, idea: Dict, results: Dict) -> str:
        """生成方法章节 Prompt"""
        return f"""请撰写论文方法章节（约1000字）。

## 研究信息

**研究假设**: {idea.get('hypothesis', '')}

**建议方法**: {idea.get('method', '')}

## 方法章节结构

1. **问题定义**（第1段）
   - 形式化定义研究问题
   - 定义符号和术语

2. **方法概述**（第2段）
   - 简述整体方法框架
   - 可以用文字描述系统架构（如"系统包含三个模块：..."）

3. **详细方法**（第3-5段）
   - 分小节描述各个组件
   - 对于不便绘制的流程图，用文字精确描述流程
   - 例如："数据处理流程如下：首先，输入数据经过预处理模块...
     接着，特征提取模块... 最后，分类器..."

4. **实现细节**（第6段，可选）
   - 提及关键参数和配置
   - 说明使用的工具和库

## 输出要求

- 使用 Markdown 格式
- 数学公式用 LaTeX 格式：$...$ 或 $$...$$
- 对于无法绘制图表的部分，用文字详细描述

## 输出

直接输出方法章节正文。
"""
    
    def generate_experiments_prompt(self, idea: Dict, results: Dict) -> str:
        """生成实验章节 Prompt"""
        metrics = results.get('metrics', {})
        
        return f"""请撰写论文实验章节（约800字）。

## 研究信息

**实验假设**: {idea.get('title', '')}

**预期结果**: {idea.get('expected_result', '')}

**实际结果**:
```json
{json.dumps(metrics, ensure_ascii=False, indent=2)}
```

## 实验章节结构

1. **实验设置**（第1段）
   - 数据集描述
   - 评价指标
   - 实验环境

2. **实现细节**（第2段）
   - 模型配置
   - 训练参数
   - 优化器设置

3. **主要结果**（第3-4段）
   - 呈现具体数值
   - 与 baseline 对比（如有）
   - 分析结果意义

4. **消融实验**（第5段，可选）
   - 分析各组件的贡献

## 输出

直接输出实验章节正文。
"""
    
    def generate_results_prompt(self, idea: Dict, results: Dict, 
                               output_files: List[str]) -> str:
        """生成结果与分析章节 Prompt"""
        has_figures = any(f.endswith(('.png', '.jpg', '.pdf')) for f in output_files)
        
        figure_desc = """## 图表处理

"""
        if has_figures:
            figure_desc += """本文档包含以下图表（在实验执行时生成）：
"""
            for f in output_files:
                if f.endswith(('.png', '.jpg', '.pdf')):
                    figure_desc += f"- `{f}`: 实验生成的图表\n"
        else:
            figure_desc += """由于实验未生成可视化图表，请用文字详细描述：
- 结果的趋势和模式
- 关键数据点
- 对比分析（如有baseline）
"""
        
        return f"""请撰写论文结果与分析章节（约600字）。

## 研究信息

**实验指标**:
```json
{json.dumps(results.get('metrics', {}), ensure_ascii=False, indent=2)}
```

**输出文件**: {', '.join(output_files)}

{figure_desc}

## 结果章节结构

1. **定量结果分析**（第1-2段）
   - 详细分析各指标
   - 解释数值的意义
   - 对比预期目标

2. **定性分析**（第3段，可选）
   - 讨论结果的启示
   - 分析成功/失败原因

3. **局限性**（第4段）
   - 客观分析实验限制
   - 提及可能的改进方向

## 输出

直接输出结果章节正文。
"""
    
    def generate_conclusion_prompt(self, idea: Dict, results: Dict) -> str:
        """生成结论章节 Prompt"""
        return f"""请撰写论文结论章节（约400字）。

## 研究信息

**研究假设**: {idea.get('hypothesis', '')}

**主要发现**: {idea.get('expected_result', '')}

**研究贡献**: {idea.get('contribution', '')}

## 结论章节结构

1. **工作总结**（第1段）
   - 简述研究内容
   - 重申主要发现

2. **主要贡献**（第2段）
   - 总结2-3点贡献
   - 强调创新之处

3. **局限性与未来工作**（第3段）
   - 当前研究的不足
   - 未来改进方向

4. **结束语**（第4段，可选）
   - 强调研究意义
   - 展望应用前景

## 输出

直接输出结论章节正文。
"""
    
    def generate_related_work_prompt(self, idea: Dict) -> str:
        """生成相关工作章节 Prompt"""
        related = idea.get('related_work', [])
        related_str = '\n'.join([f"- {r}" for r in related]) if related else "请基于研究主题自行组织相关文献"
        
        return f"""请撰写论文相关工作章节（约600字）。

## 研究信息

**研究主题**: {idea.get('title', '')}

**关键词**: {', '.join(idea.get('keywords', []))}

**相关研究线索**:
{related_str}

## 相关工作章节结构

1. **研究方向概述**（第1段）
   - 介绍研究领域的发展
   - 划分几个子方向

2. **子方向1**（第2段）
   - 介绍该方向的代表性工作
   - 分析优缺点

3. **子方向2**（第3段）
   - 介绍另一个相关方向
   - 与本文工作的联系

4. **研究空白**（第4段）
   - 总结现有研究的不足
   - 引出本文工作

## 输出

直接输出相关工作章节正文。
"""
    
    def write_section(self, section_name: str, prompt: str, 
                     llm_call_func=None) -> str:
        """
        撰写单个章节
        
        Args:
            section_name: 章节名
            prompt: Prompt
            llm_call_func: LLM 调用函数
            
        Returns:
            章节内容
        """
        if llm_call_func:
            content = llm_call_func(prompt, model=self.models.get('writeup', 'gpt-4o'))
        else:
            content = f"## {section_name}\n\n[待生成内容...]"
        
        return content
    
    def process_figures(self, output_dir: Path, results: Dict) -> List[Dict]:
        """
        处理图表
        
        Args:
            output_dir: 输出目录
            results: 实验结果
            
        Returns:
            图表信息列表
        """
        figures = []
        
        # 查找实验输出目录中的图片
        sandbox_dir = output_dir / "sandbox" / "outputs"
        if sandbox_dir.exists():
            for img_file in sandbox_dir.iterdir():
                if img_file.suffix.lower() in ['.png', '.jpg', '.jpeg', '.pdf']:
                    figures.append({
                        "file": str(img_file),
                        "name": img_file.name,
                        "caption": f"图 {len(figures)+1}: 实验结果可视化"
                    })
        
        return figures
    
    def compile_paper(self, sections: Dict[str, str], figures: List[Dict],
                     idea: Dict, output_file: Path):
        """
        编译完整论文
        
        Args:
            sections: 各章节内容
            figures: 图表信息
            idea: 研究假设
            output_file: 输出文件
        """
        paper_content = f"""# {idea.get('title', '研究论文')}

**作者**: AI-Research-Assistant  
**日期**: {datetime.now().strftime('%Y-%m-%d')}

---

## 摘要

{sections.get('abstract', '')}

**关键词**: {', '.join(idea.get('keywords', []))}

---

## 1. 引言

{sections.get('introduction', '')}

## 2. 相关工作

{sections.get('related_work', '')}

## 3. 方法

{sections.get('method', '')}

## 4. 实验

{sections.get('experiments', '')}

## 5. 结果与分析

{sections.get('results', '')}

## 6. 结论

{sections.get('conclusion', '')}

---

## 参考文献

[1] 相关文献待补充...

---

## 图表清单

"""
        
        if figures:
            for fig in figures:
                paper_content += f"\n### {fig['caption']}\n"
                paper_content += f"\n文件: `{fig['file']}`\n"
                paper_content += f"\n![{fig['name']}]({fig['file']})\n"
        else:
            paper_content += "\n本文档未包含可视化图表，相关分析已在正文中用文字描述。\n"
        
        paper_content += f"""

---

## 附录：实验信息

- **研究假设**: {idea.get('hypothesis', '')}
- **实验名称**: {idea.get('title', '')}
- **关键词**: {', '.join(idea.get('keywords', []))}

---

*本论文由 AI-Research-Assistant 自动生成*
"""
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(paper_content)
    
    def run(self, ideas_file: Path, idea_id: int, 
            summary_file: Path, output_dir: Path,
            llm_call_func=None) -> Dict:
        """
        运行撰写阶段
        
        Args:
            ideas_file: ideas.json 路径
            idea_id: 假设 ID
            summary_file: summary.json 路径
            output_dir: 输出目录
            llm_call_func: LLM 调用函数
            
        Returns:
            执行结果
        """
        print("=" * 60)
        print("Phase 3: 撰写阶段 (Write-up)")
        print("=" * 60)
        
        # 1. 加载数据
        print("\n[1/4] 加载研究数据...")
        idea = self.load_idea(ideas_file, idea_id)
        results = self.load_experiment_results(summary_file)
        print(f"  [OK] 假设: {idea.get('title', '')}")
        print(f"  [OK] 实验状态: {'成功' if results.get('success') else '失败'}")
        
        # 2. 撰写各章节
        print("\n[2/4] 撰写论文各章节...")
        sections = {}
        
        section_prompts = [
            ('abstract', '摘要', self.generate_abstract_prompt(idea, results)),
            ('introduction', '引言', self.generate_introduction_prompt(idea, results)),
            ('related_work', '相关工作', self.generate_related_work_prompt(idea)),
            ('method', '方法', self.generate_method_prompt(idea, results)),
            ('experiments', '实验', self.generate_experiments_prompt(idea, results)),
            ('results', '结果与分析', self.generate_results_prompt(
                idea, results, list(results.get('output_files', []))
            )),
            ('conclusion', '结论', self.generate_conclusion_prompt(idea, results)),
        ]
        
        for section_key, section_name, prompt in section_prompts:
            print(f"  撰写 {section_name}...", end=" ")
            sections[section_key] = self.write_section(section_name, prompt, llm_call_func)
            print("[OK]")
        
        # 3. 处理图表
        print("\n[3/4] 处理图表...")
        figures = self.process_figures(output_dir, results)
        print(f"  [OK] 发现 {len(figures)} 个图表")
        
        # 4. 编译论文
        print("\n[4/4] 编译完整论文...")
        paper_file = output_dir / "paper.md"
        self.compile_paper(sections, figures, idea, paper_file)
        print(f"  [OK] 论文已保存: {paper_file}")
        
        # 同时保存各章节
        sections_dir = output_dir / "sections"
        sections_dir.mkdir(exist_ok=True)
        for key, content in sections.items():
            with open(sections_dir / f"{key}.md", 'w', encoding='utf-8') as f:
                f.write(content)
        
        return {
            "success": True,
            "paper_file": str(paper_file),
            "sections_dir": str(sections_dir),
            "figures_count": len(figures),
            "word_count": sum(len(s) for s in sections.values())
        }


# 便捷函数
def run_writeup(ideas_file: str, idea_id: int, summary_file: str,
                output_dir: str, config: Dict, llm_call_func=None) -> Dict:
    """运行撰写阶段的便捷函数"""
    phase = WriteupPhase(config)
    return phase.run(
        Path(ideas_file), idea_id, 
        Path(summary_file), Path(output_dir),
        llm_call_func
    )


if __name__ == "__main__":
    # 测试
    config = {
        "models": {"writeup": "gpt-4o"},
        "output": {"format": "markdown"}
    }
    
    print("WriteupPhase 加载成功")
