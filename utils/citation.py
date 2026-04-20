"""
引用管理工具

支持格式：
- GB/T 7714（中文常用）
- APA
- MLA
- Chicago
"""

import re
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class Reference:
    """参考文献条目"""
    authors: List[str]
    year: int
    title: str
    venue: str
    volume: Optional[str] = None
    issue: Optional[str] = None
    pages: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    
    def format_gbt7714(self) -> str:
        """格式化为 GB/T 7714"""
        authors_str = ", ".join(self.authors) if self.authors else "佚名"
        if len(self.authors) > 3:
            authors_str = f"{self.authors[0]} 等"
        
        ref = f"[{authors_str}]. {self.title}[J]. {self.venue}, {self.year}"
        if self.volume:
            ref += f", {self.volume}"
        if self.issue:
            ref += f"({self.issue})"
        if self.pages:
            ref += f": {self.pages}"
        ref += "."
        if self.doi:
            ref += f" DOI: {self.doi}."
        return ref
    
    def format_apa(self) -> str:
        """格式化为 APA"""
        if len(self.authors) == 1:
            authors_str = self.authors[0]
        elif len(self.authors) == 2:
            authors_str = f"{self.authors[0]} & {self.authors[1]}"
        elif len(self.authors) > 2:
            authors_str = f"{self.authors[0]} et al."
        else:
            authors_str = "Anonymous"
        
        ref = f"{authors_str} ({self.year}). {self.title}. {self.venue}"
        if self.volume:
            ref += f", {self.volume}"
        if self.pages:
            ref += f", {self.pages}"
        ref += "."
        return ref
    
    def format_mla(self) -> str:
        """格式化为 MLA"""
        authors_str = ", ".join(self.authors) if self.authors else "Anonymous"
        
        ref = f'"{self.title}." {self.venue}, vol. {self.volume or "N/A"}'
        if self.issue:
            ref += f', no. {self.issue}'
        ref += f', {self.year}'
        if self.pages:
            ref += f', pp. {self.pages}'
        ref += "."
        return ref


class CitationManager:
    """引用管理器"""
    
    def __init__(self, style: str = "GB/T7714"):
        self.style = style
        self.references: List[Reference] = []
        self.citations: Dict[str, int] = {}  # 引用标记 -> 序号
    
    def add_reference(self, ref: Reference) -> int:
        """
        添加参考文献
        
        Returns:
            参考文献序号（从1开始）
        """
        self.references.append(ref)
        return len(self.references)
    
    def cite(self, marker: str, ref: Reference) -> str:
        """
        添加引用
        
        Args:
            marker: 引用标记（如"Smith2020"）
            ref: 参考文献
            
        Returns:
            格式化后的引用文本
        """
        if marker not in self.citations:
            num = self.add_reference(ref)
            self.citations[marker] = num
        
        num = self.citations[marker]
        
        # 根据格式返回引用标记
        if self.style == "GB/T7714":
            return f"[{num}]"
        elif self.style == "APA":
            return f"({ref.authors[0].split()[-1]}, {ref.year})"
        elif self.style == "MLA":
            return f"({ref.authors[0].split()[-1]} {ref.year})"
        else:
            return f"[{num}]"
    
    def generate_bibliography(self) -> str:
        """生成参考文献列表"""
        lines = ["## 参考文献", ""]
        
        for i, ref in enumerate(self.references, 1):
            if self.style == "GB/T7714":
                formatted = ref.format_gbt7714()
            elif self.style == "APA":
                formatted = ref.format_apa()
            elif self.style == "MLA":
                formatted = ref.format_mla()
            else:
                formatted = ref.format_gbt7714()
            
            lines.append(f"[{i}] {formatted}")
        
        return "\n".join(lines)
    
    def process_citations_in_text(self, text: str) -> str:
        """
        处理文本中的引用标记
        
        支持格式：
        - [Smith2020] -> 转换为具体引用格式
        - [@Smith2020] -> 同上
        """
        # 查找引用标记
        pattern = r'\[(@?)(\w+\d{4})\]'
        
        def replace_citation(match):
            marker = match.group(2)
            if marker in self.citations:
                num = self.citations[marker]
                if self.style == "GB/T7714":
                    return f"[{num}]"
            return match.group(0)
        
        return re.sub(pattern, replace_citation, text)


def format_citations(text: str, style: str = "GB/T7714") -> str:
    """
    格式化文本中的引用
    
    Args:
        text: 包含引用标记的文本
        style: 引用格式
        
    Returns:
        格式化后的文本
    """
    # 简单的引用格式转换
    if style == "GB/T7714":
        # [1], [2] 格式保持不变
        return text
    elif style == "APA":
        # 将 [1] 转换为 (Author, Year) 需要作者信息
        # 这里简化处理
        return text
    return text


# 测试
if __name__ == "__main__":
    manager = CitationManager("GB/T7714")
    
    ref1 = Reference(
        authors=["张三", "李四", "王五"],
        year=2023,
        title="深度学习在图像识别中的应用",
        venue="计算机学报",
        volume="46",
        issue="5",
        pages="100-110"
    )
    
    ref2 = Reference(
        authors=["LeCun, Y.", "Bengio, Y.", "Hinton, G."],
        year=2015,
        title="Deep learning",
        venue="Nature",
        volume="521",
        pages="436-444",
        doi="10.1038/nature14539"
    )
    
    print("GB/T 7714 格式:")
    print(ref1.format_gbt7714())
    print(ref2.format_gbt7714())
    
    print("\nAPA 格式:")
    print(ref2.format_apa())
