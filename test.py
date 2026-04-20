"""
AI-Research-Assistant Skill 测试脚本

用于测试各模块功能
"""

import sys
from pathlib import Path

# 添加路径
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "phases"))
sys.path.insert(0, str(Path(__file__).parent / "utils"))


def test_sandbox():
    """测试沙盒执行器"""
    print("\n" + "=" * 60)
    print("测试沙盒执行器")
    print("=" * 60)
    
    from utils.sandbox import SandboxExecutor
    
    test_code = '''
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import json
import os

OUTPUT_DIR = "outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

data = np.random.randn(100)
print(f"Mean: {np.mean(data):.4f}")

plt.figure(figsize=(8, 6))
plt.hist(data, bins=20, edgecolor='black')
plt.title('Test Distribution')
plt.savefig(os.path.join(OUTPUT_DIR, 'test.png'), dpi=150)
plt.close()

metrics = {"mean": float(np.mean(data)), "std": float(np.std(data))}
with open(os.path.join(OUTPUT_DIR, "metrics.json"), "w") as f:
    json.dump(metrics, f, indent=2)

print("Test completed!")
'''
    
    with SandboxExecutor(timeout=30) as sandbox:
        result = sandbox.execute(test_code)
        
        print(f"执行成功: {result.success}")
        print(f"返回码: {result.return_code}")
        print(f"执行时间: {result.execution_time:.2f} 秒")
        print(f"输出文件: {list(result.output_files.keys())}")
        if result.metrics:
            print(f"评估指标: {result.metrics}")
    
    return result.success


def test_formatter():
    """测试格式化工具"""
    print("\n" + "=" * 60)
    print("测试格式化工具")
    print("=" * 60)
    
    from utils.formatter import TextFormatter, PaperFormatter
    
    test_text = """# 测试论文

## 摘要
这是一个测试摘要，包含一些文字。

## 引言
这是引言部分。
"""
    
    formatter = PaperFormatter()
    
    # 测试字数统计
    word_count = TextFormatter.count_words(test_text)
    print(f"字数统计: {word_count}")
    
    # 测试完整性检查
    check = formatter.check_completeness(test_text)
    print(f"完整性评分: {check['completeness_score']}/10")
    print(f"包含摘要: {check['has_abstract']}")
    print(f"总字数: {check['total_words']}")
    
    return True


def test_citation():
    """测试引用管理"""
    print("\n" + "=" * 60)
    print("测试引用管理")
    print("=" * 60)
    
    from utils.citation import CitationManager, Reference
    
    manager = CitationManager("GB/T7714")
    
    ref = Reference(
        authors=["张三", "李四"],
        year=2023,
        title="深度学习研究",
        venue="计算机学报",
        volume="45",
        pages="100-110"
    )
    
    citation = manager.cite("Zhang2023", ref)
    print(f"引用标记: {citation}")
    
    bib = manager.generate_bibliography()
    print(f"参考文献:\n{bib}")
    
    return True


def test_ideation():
    """测试构思阶段"""
    print("\n" + "=" * 60)
    print("测试构思阶段")
    print("=" * 60)
    
    from phases.ideation import IdeationPhase
    
    config = {
        "models": {"ideation": "gpt-4o"},
        "search": {"enabled": False}
    }
    
    phase = IdeationPhase(config)
    
    # 测试主题解析
    topic_content = """# 测试主题

## 关键词
关键词1, 关键词2

## 研究背景
这是研究背景。

## 研究目标
这是研究目标。
"""
    
    topic_info = phase.parse_topic(topic_content)
    print(f"标题: {topic_info['title']}")
    print(f"关键词: {topic_info['keywords']}")
    
    return True


def test_full_pipeline_mock():
    """测试完整流程（模拟模式）"""
    print("\n" + "=" * 60)
    print("测试完整流程（模拟模式）")
    print("=" * 60)
    
    from main import AIResearchAssistant, mock_llm_call
    
    # 创建测试主题
    test_topic = """# 基于CNN的图像分类研究

## 关键词
深度学习, 图像分类, CNN

## 研究背景
图像分类是计算机视觉的基础任务。

## 研究目标
构建高效的图像分类模型。
"""
    
    # 保存测试主题
    test_dir = Path("test_output")
    test_dir.mkdir(exist_ok=True)
    
    topic_file = test_dir / "test_topic.md"
    with open(topic_file, 'w', encoding='utf-8') as f:
        f.write(test_topic)
    
    # 初始化并运行
    assistant = AIResearchAssistant()
    assistant.set_llm_callback(mock_llm_call)
    
    print("\n开始测试完整流程...\n")
    result = assistant.run_full_pipeline(
        str(topic_file), 
        str(test_dir / "test_run"),
        idea_id=1
    )
    
    print(f"\n流程结果: {'成功' if result['success'] else '失败'}")
    print(f"输出目录: {result['output_dir']}")
    
    return result['success']


def main():
    """运行所有测试"""
    print("\n" + "=" * 70)
    print("AI-Research-Assistant Skill 测试套件")
    print("=" * 70)
    
    tests = [
        ("沙盒执行器", test_sandbox),
        ("格式化工具", test_formatter),
        ("引用管理", test_citation),
        ("构思阶段", test_ideation),
        ("完整流程（模拟）", test_full_pipeline_mock),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"\n[FAIL] {name} 测试失败: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # 打印总结
    print("\n" + "=" * 70)
    print("测试结果汇总")
    print("=" * 70)
    
    for name, success in results:
        status = "[PASS]" if success else "[FAIL]"
        print(f"{status}: {name}")
    
    passed = sum(1 for _, s in results if s)
    total = len(results)
    print(f"\n总计: {passed}/{total} 通过")
    
    return all(s for _, s in results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
