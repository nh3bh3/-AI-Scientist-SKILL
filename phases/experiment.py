"""
Phase 2: 实验阶段 (Experimentation)

功能：
1. 基于假设生成实验代码
2. 在沙盒中安全执行
3. 收集结果和指标
4. 错误处理和重试
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

# 导入沙盒执行器
sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from sandbox import SandboxExecutor, create_experiment_template


@dataclass
class ExperimentResult:
    """实验结果"""
    success: bool
    hypothesis_id: int
    hypothesis_title: str
    code: str
    execution_result: Dict
    output_files: Dict[str, str]
    metrics: Optional[Dict]
    logs: Dict[str, str]
    retry_count: int


class ExperimentPhase:
    """实验阶段处理器"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.models = config.get('models', {})
        self.exp_config = config.get('experiment', {})
    
    def load_idea(self, ideas_file: Path, idea_id: int = 1) -> Optional[Dict]:
        """
        加载指定的研究假设
        
        Args:
            ideas_file: ideas.json 文件路径
            idea_id: 假设 ID
            
        Returns:
            假设信息
        """
        with open(ideas_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        ideas = data.get('ideas', [])
        for idea in ideas:
            if idea.get('id') == idea_id:
                return idea
        
        # 如果没有找到指定 ID，返回第一个
        return ideas[0] if ideas else None
    
    def generate_code_prompt(self, hypothesis: Dict, template: str = "") -> str:
        """
        生成代码生成的 Prompt
        
        Args:
            hypothesis: 假设信息
            template: 可选的代码模板
            
        Returns:
            LLM Prompt
        """
        allowed_packages = self.exp_config.get('allowed_packages', [])
        packages_str = ", ".join(allowed_packages[:10]) if allowed_packages else "numpy, pandas, matplotlib, scikit-learn"
        
        prompt = f"""你是一个专业的机器学习工程师。请基于以下研究假设，编写完整的 Python 实验代码。

## 研究假设

**标题**: {hypothesis.get('title', '')}

**假设描述**: {hypothesis.get('hypothesis', '')}

**建议方法**: {hypothesis.get('method', '')}

**预期结果**: {hypothesis.get('expected_result', '')}

## 代码要求

1. **完整性**: 代码应该可以直接运行，包含所有必要的导入和实现
2. **输出要求**:
   - 所有输出文件必须保存到 `outputs/` 目录
   - 必须生成 `outputs/metrics.json` 文件，包含评估指标
   - 生成的图表保存到 `outputs/` 目录（支持 PNG 格式）

3. **允许使用的包**: {packages_str}
   - 使用 matplotlib 时，必须设置: `matplotlib.use('Agg')`
   - 不要执行网络请求或文件系统危险操作

4. **代码结构**:
   - 使用函数组织代码
   - 包含主函数 `main()`
   - 添加适当的注释

5. **评估指标**:
   - metrics.json 应包含具体的数值指标
   - 例如: accuracy, precision, recall, f1, loss, mse 等

## 输出格式

请只输出 Python 代码，不要输出任何解释文字。代码应该可以直接保存为 .py 文件并运行。

```python
# 你的代码
```
"""
        return prompt
    
    def parse_code_response(self, response: str) -> str:
        """
        解析 LLM 返回的代码
        
        Args:
            response: LLM 响应
            
        Returns:
            Python 代码字符串
        """
        import re
        
        # 提取代码块
        code_match = re.search(r'```python\s*(.+?)\s*```', response, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()
        
        # 如果没有 python 标记，尝试普通代码块
        code_match = re.search(r'```\s*(.+?)\s*```', response, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()
        
        # 直接返回（假设响应就是代码）
        return response.strip()
    
    def debug_code_prompt(self, code: str, error: str, hypothesis: Dict) -> str:
        """
        生成代码调试的 Prompt
        
        Args:
            code: 原始代码
            error: 错误信息
            hypothesis: 假设信息
            
        Returns:
            LLM Prompt
        """
        prompt = f"""代码执行出现错误，请修复。

## 原始代码

```python
{code}
```

## 错误信息

```
{error}
```

## 修复要求

1. 分析错误原因
2. 修复代码中的问题
3. 确保代码可以正常运行
4. 保持原有功能不变

## 输出格式

只输出修复后的完整代码，不要输出解释：

```python
# 修复后的代码
```
"""
        return prompt
    
    def execute_experiment(self, code: str, hypothesis: Dict, 
                          work_dir: Path) -> ExperimentResult:
        """
        执行实验
        
        Args:
            code: Python 代码
            hypothesis: 假设信息
            work_dir: 工作目录
            
        Returns:
            ExperimentResult
        """
        # 创建沙盒执行器
        sandbox = SandboxExecutor(
            work_dir=str(work_dir),
            timeout=self.exp_config.get('timeout', 300),
            max_memory_mb=self.exp_config.get('resource_limits', {}).get('max_memory_mb', 2048),
            allowed_packages=self.exp_config.get('allowed_packages', [])
        )
        
        max_retries = self.exp_config.get('max_retries', 3)
        
        # 执行代码（带重试）
        result = sandbox.execute_with_retry(code, max_retries=max_retries)
        
        # 读取日志文件
        logs = {}
        log_dir = work_dir / "logs"
        if log_dir.exists():
            for log_file in log_dir.iterdir():
                if log_file.is_file():
                    try:
                        with open(log_file, 'r', encoding='utf-8') as f:
                            logs[log_file.name] = f.read()
                    except:
                        pass
        
        return ExperimentResult(
            success=result.success,
            hypothesis_id=hypothesis.get('id', 1),
            hypothesis_title=hypothesis.get('title', ''),
            code=code,
            execution_result=result.to_dict(),
            output_files=result.output_files,
            metrics=result.metrics,
            logs=logs,
            retry_count=0  # 实际重试次数需要追踪
        )
    
    def generate_summary(self, result: ExperimentResult) -> Dict:
        """
        生成实验摘要
        
        Args:
            result: 实验结果
            
        Returns:
            摘要字典
        """
        summary = {
            "hypothesis_id": result.hypothesis_id,
            "hypothesis_title": result.hypothesis_title,
            "success": result.success,
            "execution_time": result.execution_result.get('execution_time', 0),
            "metrics": result.metrics,
            "output_files": list(result.output_files.keys()),
            "error": None if result.success else result.execution_result.get('stderr', '')[:500]
        }
        
        return summary
    
    def run(self, ideas_file: Path, idea_id: int, output_dir: Path,
            llm_call_func=None) -> Dict:
        """
        运行实验阶段
        
        Args:
            ideas_file: ideas.json 文件路径
            idea_id: 要执行的假设 ID
            output_dir: 输出目录
            llm_call_func: LLM 调用函数
            
        Returns:
            执行结果
        """
        print("=" * 60)
        print("Phase 2: 实验阶段 (Experimentation)")
        print("=" * 60)
        
        # 1. 加载假设
        print(f"\n[1/5] 加载研究假设 (ID: {idea_id})...")
        hypothesis = self.load_idea(ideas_file, idea_id)
        if not hypothesis:
            print("  ✗ 未找到指定的研究假设")
            return {"success": False, "error": "Hypothesis not found"}
        
        print(f"  [OK] 假设: {hypothesis['title']}")
        print(f"  [OK] 方法: {hypothesis.get('method', 'N/A')[:50]}...")
        
        # 2. 生成代码
        print("\n[2/5] 生成实验代码...")
        prompt = self.generate_code_prompt(hypothesis)
        
        if llm_call_func:
            response = llm_call_func(prompt, model=self.models.get('experiment', 'claude-3-5-sonnet'))
            code = self.parse_code_response(response)
        else:
            # 使用模板代码
            code = create_experiment_template(hypothesis, self.config)
        
        print(f"  [OK] 代码生成完成 ({len(code)} 字符)")
        
        # 保存代码
        code_file = output_dir / "experiment.py"
        code_file.parent.mkdir(parents=True, exist_ok=True)
        with open(code_file, 'w', encoding='utf-8') as f:
            f.write(code)
        print(f"  [OK] 代码已保存: {code_file}")
        
        # 3. 执行实验
        print("\n[3/5] 执行实验...")
        print("  [!] 安全检查中...")
        
        work_dir = output_dir / "sandbox"
        result = self.execute_experiment(code, hypothesis, work_dir)
        
        if result.success:
            print(f"  [OK] 实验执行成功")
            print(f"  [OK] 执行时间: {result.execution_result.get('execution_time', 0):.2f} 秒")
        else:
            print(f"  [FAIL] 实验执行失败")
            error_preview = result.execution_result.get('stderr', '')[:200]
            print(f"  [ERROR] 错误: {error_preview}...")
        
        # 4. 收集结果
        print("\n[4/5] 收集实验结果...")
        
        if result.metrics:
            print(f"  [OK] 评估指标:")
            for key, value in result.metrics.items():
                if isinstance(value, (int, float)):
                    print(f"    - {key}: {value:.4f}")
                else:
                    print(f"    - {key}: {value}")
        
        if result.output_files:
            print(f"  [OK] 输出文件: {len(result.output_files)} 个")
            for name in list(result.output_files.keys())[:5]:
                print(f"    - {name}")
        
        # 5. 保存摘要
        print("\n[5/5] 保存实验摘要...")
        summary = self.generate_summary(result)
        summary_file = output_dir / "summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"  [OK] 摘要已保存: {summary_file}")
        
        return {
            "success": result.success,
            "hypothesis": hypothesis['title'],
            "execution_time": result.execution_result.get('execution_time', 0),
            "metrics": result.metrics,
            "output_dir": str(output_dir),
            "summary_file": str(summary_file)
        }


# 便捷函数
def run_experiment(ideas_file: str, idea_id: int, output_dir: str, 
                   config: Dict, llm_call_func=None) -> Dict:
    """运行实验阶段的便捷函数"""
    phase = ExperimentPhase(config)
    return phase.run(Path(ideas_file), idea_id, Path(output_dir), llm_call_func)


if __name__ == "__main__":
    # 测试
    config = {
        "models": {"experiment": "claude-3-5-sonnet"},
        "experiment": {
            "timeout": 60,
            "max_retries": 1,
            "allowed_packages": ["numpy", "pandas", "matplotlib", "scikit-learn"]
        }
    }
    
    # 创建测试假设
    test_ideas = {
        "ideas": [{
            "id": 1,
            "title": "测试假设",
            "hypothesis": "测试假设描述",
            "method": "使用随机数据生成和简单统计",
            "expected_result": "得到数据的统计指标"
        }]
    }
    
    test_ideas_file = Path("test_ideas.json")
    with open(test_ideas_file, 'w', encoding='utf-8') as f:
        json.dump(test_ideas, f)
    
    result = run_experiment(str(test_ideas_file), 1, "test_experiment", config)
    print(f"\n结果: {result}")
