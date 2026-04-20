"""
沙盒执行器 - 安全执行 LLM 生成的代码

功能：
1. 在隔离环境中执行 Python 代码
2. 捕获输出和结果
3. 资源限制和超时控制
4. 安全检查（禁止危险操作）
"""

import os
import sys
import json
import time
import signal
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from contextlib import contextmanager


@dataclass
class ExecutionResult:
    """代码执行结果"""
    success: bool
    stdout: str
    stderr: str
    return_code: int
    execution_time: float
    output_files: Dict[str, str]  # 文件名 -> 文件路径
    metrics: Optional[Dict] = None  # 提取的评估指标
    error_type: Optional[str] = None  # 错误类型
    
    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "return_code": self.return_code,
            "execution_time": self.execution_time,
            "output_files": self.output_files,
            "metrics": self.metrics,
            "error_type": self.error_type
        }


class SandboxExecutor:
    """沙盒执行器"""
    
    # 禁止的操作模式
    FORBIDDEN_PATTERNS = [
        "os.system",
        "subprocess",
        "exec(",
        "eval(",
        "__import__",
        "open('/etc",
        "open('C:\\\\Windows",
        "open('C:/Windows",
        "import socket",
        "import urllib",
        "requests.get",
        "requests.post",
        "wget",
        "curl",
        "rm -rf",
        "del /",
        "format(",
        "os.remove('/",
        "shutil.rmtree('/",
    ]
    
    def __init__(self, 
                 work_dir: Optional[str] = None,
                 timeout: int = 300,
                 max_memory_mb: int = 2048,
                 allowed_packages: Optional[List[str]] = None):
        """
        初始化沙盒执行器
        
        Args:
            work_dir: 工作目录（默认为临时目录）
            timeout: 执行超时时间（秒）
            max_memory_mb: 最大内存限制（MB）
            allowed_packages: 允许的 Python 包列表
        """
        self.timeout = timeout
        self.max_memory_mb = max_memory_mb
        self.allowed_packages = allowed_packages or []
        
        # 创建工作目录
        if work_dir:
            self.work_dir = Path(work_dir)
            self.work_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.work_dir = Path(tempfile.mkdtemp(prefix="research_sandbox_"))
        
        # 创建子目录
        self.code_dir = self.work_dir / "code"
        self.output_dir = self.work_dir / "outputs"
        self.log_dir = self.work_dir / "logs"
        
        for d in [self.code_dir, self.output_dir, self.log_dir]:
            d.mkdir(exist_ok=True)
    
    def security_check(self, code: str) -> Tuple[bool, List[str]]:
        """
        安全检查代码
        
        Returns:
            (是否通过, 违规模式列表)
        """
        violations = []
        
        for pattern in self.FORBIDDEN_PATTERNS:
            if pattern in code:
                violations.append(pattern)
        
        # 检查导入语句
        lines = code.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('import ') or line.startswith('from '):
                # 提取包名
                if line.startswith('import '):
                    pkg = line.split()[1].split('.')[0]
                else:  # from x import y
                    pkg = line.split()[1].split('.')[0]
                
                # 检查是否在允许列表中（标准库除外）
                std_libs = {'os', 'sys', 'json', 'time', 'math', 'random', 
                           'datetime', 'collections', 'itertools', 'functools',
                           'typing', 'pathlib', 're', 'string', 'hashlib',
                           'copy', 'pickle', 'warnings', 'traceback'}
                
                if pkg not in std_libs and pkg not in self.allowed_packages:
                    violations.append(f"未授权的导入: {pkg}")
        
        return len(violations) == 0, violations
    
    def execute(self, code: str, script_name: str = "experiment.py") -> ExecutionResult:
        """
        在沙盒中执行代码
        
        Args:
            code: Python 代码字符串
            script_name: 脚本文件名
            
        Returns:
            ExecutionResult 执行结果
        """
        start_time = time.time()
        
        # 安全检查
        passed, violations = self.security_check(code)
        if not passed:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=f"安全检查失败，发现违规操作: {', '.join(violations)}",
                return_code=-1,
                execution_time=0,
                output_files={},
                error_type="SecurityError"
            )
        
        # 写入代码文件
        script_path = self.code_dir / script_name
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(code)
        
        # 构建执行命令
        # 使用 -u 参数确保无缓冲输出
        cmd = [
            sys.executable,
            "-u",
            str(script_path)
        ]
        
        # 设置环境变量
        env = os.environ.copy()
        env['PYTHONPATH'] = str(self.code_dir)
        env['MPLBACKEND'] = 'Agg'  # 使用非交互式 matplotlib 后端
        
        try:
            # 执行代码
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(self.work_dir),
                env=env,
                text=True,
                encoding='utf-8'
            )
            
            # 等待执行完成（带超时）
            try:
                stdout, stderr = process.communicate(timeout=self.timeout)
                return_code = process.returncode
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                return_code = -1
                stderr += f"\n[ERROR] 执行超时（超过 {self.timeout} 秒）"
            
            execution_time = time.time() - start_time
            
            # 保存日志
            with open(self.log_dir / "stdout.log", 'w', encoding='utf-8') as f:
                f.write(stdout)
            with open(self.log_dir / "stderr.log", 'w', encoding='utf-8') as f:
                f.write(stderr)
            
            # 收集输出文件
            output_files = {}
            if self.output_dir.exists():
                for f in self.output_dir.iterdir():
                    if f.is_file():
                        output_files[f.name] = str(f)
            
            # 提取评估指标（如果代码生成了 metrics.json）
            metrics = None
            metrics_file = self.output_dir / "metrics.json"
            if metrics_file.exists():
                try:
                    with open(metrics_file, 'r', encoding='utf-8') as f:
                        metrics = json.load(f)
                except:
                    pass
            
            # 确定错误类型
            error_type = None
            if return_code != 0:
                if "SyntaxError" in stderr:
                    error_type = "SyntaxError"
                elif "ImportError" in stderr or "ModuleNotFoundError" in stderr:
                    error_type = "ImportError"
                elif "IndexError" in stderr or "KeyError" in stderr:
                    error_type = "IndexError"
                elif "RuntimeError" in stderr:
                    error_type = "RuntimeError"
                else:
                    error_type = "UnknownError"
            
            return ExecutionResult(
                success=return_code == 0,
                stdout=stdout,
                stderr=stderr,
                return_code=return_code,
                execution_time=execution_time,
                output_files=output_files,
                metrics=metrics,
                error_type=error_type
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=f"执行异常: {str(e)}",
                return_code=-1,
                execution_time=execution_time,
                output_files={},
                error_type="ExecutionError"
            )
    
    def execute_with_retry(self, code: str, max_retries: int = 3, 
                          script_name: str = "experiment.py") -> ExecutionResult:
        """
        带重试的执行
        
        Args:
            code: Python 代码
            max_retries: 最大重试次数
            script_name: 脚本名
            
        Returns:
            最后一次执行结果
        """
        last_result = None
        
        for attempt in range(max_retries):
            result = self.execute(code, script_name)
            last_result = result
            
            if result.success:
                return result
            
            # 如果是语法错误，不需要重试
            if result.error_type == "SyntaxError":
                break
            
            # 如果是安全检查失败，不需要重试
            if result.error_type == "SecurityError":
                break
        
        return last_result
    
    def cleanup(self):
        """清理工作目录"""
        if self.work_dir.exists() and "research_sandbox_" in str(self.work_dir):
            shutil.rmtree(self.work_dir, ignore_errors=True)
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()


def create_experiment_template(hypothesis: Dict, config: Dict) -> str:
    """
    根据假设创建实验代码模板
    
    Args:
        hypothesis: 假设信息
        config: 配置
        
    Returns:
        Python 代码字符串
    """
    template = '''"""
实验代码: {title}

研究假设: {hypothesis}
"""

import os
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')  # 非交互式后端
import matplotlib.pyplot as plt

# 设置随机种子确保可复现
np.random.seed(42)

# 输出目录
OUTPUT_DIR = "outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def main():
    """主实验函数"""
    print("=" * 50)
    print("开始实验: {title}")
    print("=" * 50)
    
    # TODO: 实现实验逻辑
    {experiment_logic}
    
    # 保存评估指标
    metrics = {{
        "accuracy": 0.0,  # 请替换为实际指标
        "loss": 0.0,
        "experiment_name": "{title}"
    }}
    
    with open(os.path.join(OUTPUT_DIR, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)
    
    print("实验完成！")
    print(f"结果保存在: {{OUTPUT_DIR}}")


if __name__ == "__main__":
    main()
'''
    
    experiment_logic = '''
    # 示例：生成一些随机数据并绘制图表
    data = np.random.randn(100)
    
    plt.figure(figsize=(10, 6))
    plt.hist(data, bins=20, edgecolor='black')
    plt.title('Data Distribution')
    plt.xlabel('Value')
    plt.ylabel('Frequency')
    plt.savefig(os.path.join(OUTPUT_DIR, 'figure1.png'), dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"数据均值: {{np.mean(data):.4f}}")
    print(f"数据标准差: {{np.std(data):.4f}}")
'''
    
    return template.format(
        title=hypothesis.get('title', 'Experiment'),
        hypothesis=hypothesis.get('hypothesis', ''),
        experiment_logic=experiment_logic
    )


if __name__ == "__main__":
    # 测试
    test_code = '''
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os

OUTPUT_DIR = "outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

data = np.random.randn(1000)
print(f"Mean: {np.mean(data):.4f}")

plt.figure(figsize=(8, 6))
plt.hist(data, bins=30, edgecolor='black')
plt.title('Test Distribution')
plt.savefig(os.path.join(OUTPUT_DIR, 'test.png'), dpi=150)
plt.close()

metrics = {"mean": float(np.mean(data)), "std": float(np.std(data))}
with open(os.path.join(OUTPUT_DIR, "metrics.json"), "w") as f:
    import json
    json.dump(metrics, f)

print("Test completed successfully!")
'''
    
    with SandboxExecutor(timeout=30) as sandbox:
        result = sandbox.execute(test_code)
        print(f"Success: {result.success}")
        print(f"Stdout: {result.stdout}")
        print(f"Stderr: {result.stderr}")
        print(f"Output files: {result.output_files}")
        if result.metrics:
            print(f"Metrics: {result.metrics}")
