"""
格式化处理工具

功能：
1. 文本格式清理
2. 论文章节格式化
3. 字数统计
4. 内容验证
"""

import re
from typing import Dict, List, Tuple
from pathlib import Path


class TextFormatter:
    """文本格式化器"""
    
    @staticmethod
    def clean_markdown(text: str) -> str:
        """清理 Markdown 格式"""
        # 移除多余的空行
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # 统一标题格式
        text = re.sub(r'^#{1,6}\s*', lambda m: m.group().strip() + ' ', text, flags=re.MULTILINE)
        
        # 移除行尾空格
        text = re.sub(r' +\n', '\n', text)
        
        return text.strip()
    
    @staticmethod
    def count_words(text: str) -> int:
        """统计字数（中文按字符，英文按单词）"""
        # 移除 Markdown 标记
        clean_text = re.sub(r'[#*`\[\]()]', '', text)
        
        # 中文字符数
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', clean_text))
        
        # 英文单词数
        english_words = len(re.findall(r'[a-zA-Z]+', clean_text))
        
        return chinese_chars + english_words
    
    @staticmethod
    def extract_sections(text: str) -> Dict[str, str]:
        """提取 Markdown 章节"""
        sections = {}
        
        # 匹配标题
        pattern = r'^(#{1,6})\s+(.+)$'
        
        current_section = None
        current_content = []
        
        for line in text.split('\n'):
            match = re.match(pattern, line)
            if match:
                # 保存上一章节
                if current_section:
                    sections[current_section] = '\n'.join(current_content).strip()
                
                # 开始新章节
                current_section = match.group(2).strip()
                current_content = []
            else:
                if current_section:
                    current_content.append(line)
        
        # 保存最后一个章节
        if current_section:
            sections[current_section] = '\n'.join(current_content).strip()
        
        return sections
    
    @staticmethod
    def validate_paper_structure(text: str, required_sections: List[str]) -> Tuple[bool, List[str]]:
        """
        验证论文结构完整性
        
        Returns:
            (是否完整, 缺失章节列表)
        """
        sections = TextFormatter.extract_sections(text)
        section_titles = [s.lower() for s in sections.keys()]
        
        missing = []
        for required in required_sections:
            # 检查是否存在（支持模糊匹配）
            if not any(required.lower() in title or title in required.lower() 
                      for title in section_titles):
                missing.append(required)
        
        return len(missing) == 0, missing
    
    @staticmethod
    def format_equations(text: str) -> str:
        """格式化数学公式"""
        # 将 $...$ 中的中文标点替换为英文标点
        def replace_in_equation(match):
            eq = match.group(1)
            # 替换常见中文标点
            eq = eq.replace('，', ',').replace('。', '.').replace('（', '(').replace('）', ')')
            return f'${eq}$'
        
        return re.sub(r'\$(.+?)\$', replace_in_equation, text)
    
    @staticmethod
    def format_citations(text: str, style: str = "GB/T7714") -> str:
        """格式化引用"""
        # 确保引用标记格式一致
        text = re.sub(r'\[\s*(\d+)\s*\]', r'[\1]', text)
        return text


class PaperFormatter:
    """论文格式化器"""
    
    SECTION_ORDER = [
        "摘要", "Abstract",
        "引言", "Introduction",
        "相关工作", "Related Work",
        "方法", "Methodology", "Method",
        "实验", "Experiments", "Experiment",
        "结果", "Results",
        "讨论", "Discussion",
        "结论", "Conclusion",
        "参考文献", "References"
    ]
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.formatter = TextFormatter()
    
    def format_paper(self, text: str) -> str:
        """格式化整篇论文"""
        # 1. 基础清理
        text = self.formatter.clean_markdown(text)
        
        # 2. 格式化公式
        text = self.formatter.format_equations(text)
        
        # 3. 格式化引用
        text = self.formatter.format_citations(text)
        
        return text
    
    def check_completeness(self, text: str) -> Dict:
        """检查论文完整性"""
        sections = self.formatter.extract_sections(text)
        
        # 检查必要章节
        essential_sections = ["摘要", "引言", "方法", "实验", "结论"]
        has_essential = all(
            any(req in title for title in sections.keys())
            for req in essential_sections
        )
        
        # 统计字数
        total_words = self.formatter.count_words(text)
        
        # 检查图表
        has_figures = "![" in text or "图" in text
        
        # 检查引用
        has_citations = bool(re.search(r'\[\d+\]', text))
        
        return {
            "has_abstract": "摘要" in text or "Abstract" in text,
            "has_introduction": any(s in text for s in ["引言", "Introduction"]),
            "has_method": any(s in text for s in ["方法", "Methodology", "Method"]),
            "has_experiments": any(s in text for s in ["实验", "Experiments"]),
            "has_conclusion": any(s in text for s in ["结论", "Conclusion"]),
            "has_references": any(s in text for s in ["参考文献", "References"]),
            "has_essential_sections": has_essential,
            "total_words": total_words,
            "has_figures": has_figures,
            "has_citations": has_citations,
            "completeness_score": self._calculate_completeness(
                has_essential, total_words, has_figures, has_citations
            )
        }
    
    def _calculate_completeness(self, has_essential: bool, 
                                word_count: int,
                                has_figures: bool,
                                has_citations: bool) -> float:
        """计算完整性得分"""
        score = 0.0
        
        if has_essential:
            score += 0.4
        
        # 字数评分（3000-8000字为满分）
        if 3000 <= word_count <= 8000:
            score += 0.3
        elif word_count > 0:
            score += 0.3 * min(word_count / 3000, 1.0)
        
        if has_figures:
            score += 0.15
        
        if has_citations:
            score += 0.15
        
        return round(score * 10, 1)  # 转换为 0-10 分
    
    def generate_summary(self, text: str) -> str:
        """生成论文摘要"""
        check = self.check_completeness(text)
        sections = self.formatter.extract_sections(text)
        
        summary = f"""## 论文检查报告

### 结构完整性
- 摘要: {'✓' if check['has_abstract'] else '✗'}
- 引言: {'✓' if check['has_introduction'] else '✗'}
- 方法: {'✓' if check['has_method'] else '✗'}
- 实验: {'✓' if check['has_experiments'] else '✗'}
- 结论: {'✓' if check['has_conclusion'] else '✗'}
- 参考文献: {'✓' if check['has_references'] else '✗'}

### 内容统计
- 总字数: {check['total_words']} 字
- 章节数: {len(sections)}
- 包含图表: {'是' if check['has_figures'] else '否'}
- 包含引用: {'是' if check['has_citations'] else '否'}

### 完整性评分
**{check['completeness_score']}/10**

"""
        
        if check['completeness_score'] < 7:
            summary += "\n### 改进建议\n\n"
            if not check['has_essential_sections']:
                summary += "- 补充缺失的必要章节\n"
            if check['total_words'] < 2000:
                summary += "- 论文字数较少，建议扩充内容\n"
            if not check['has_figures']:
                summary += "- 建议添加图表辅助说明\n"
            if not check['has_citations']:
                summary += "- 建议添加参考文献引用\n"
        
        return summary


if __name__ == "__main__":
    # 测试
    formatter = PaperFormatter()
    
    test_text = """# 测试论文

## 摘要
这是一个测试摘要。

## 引言
这是引言部分。

## 方法
这是方法部分。

## 实验
这是实验部分。

## 结论
这是结论部分。
"""
    
    print(formatter.generate_summary(test_text))
    print(f"\n字数统计: {TextFormatter.count_words(test_text)}")
