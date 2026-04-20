"""
实验代码模板

基于研究假设自动生成实验代码
"""

import os
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')  # 非交互式后端
import matplotlib.pyplot as plt
from typing import Dict, Any

# 设置随机种子确保可复现
SEED = 42
np.random.seed(SEED)

# 输出目录
OUTPUT_DIR = "outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def save_metrics(metrics: Dict[str, Any]):
    """保存评估指标"""
    with open(os.path.join(OUTPUT_DIR, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"Metrics saved: {metrics}")


def save_figure(fig, name: str):
    """保存图表"""
    path = os.path.join(OUTPUT_DIR, name)
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Figure saved: {path}")


def main():
    """
    主实验函数
    
    请在此处实现实验逻辑
    """
    print("=" * 50)
    print("Experiment Started")
    print("=" * 50)
    
    # ==================== 实验实现区域 ====================
    
    # TODO: 实现数据加载
    # data = load_data()
    
    # TODO: 实现模型定义
    # model = build_model()
    
    # TODO: 实现训练循环
    # train(model, data)
    
    # TODO: 实现评估
    # metrics = evaluate(model, data)
    
    # ==================== 示例代码 ====================
    
    # 生成示例数据
    data = np.random.randn(1000)
    
    # 示例：计算统计指标
    metrics = {
        "mean": float(np.mean(data)),
        "std": float(np.std(data)),
        "min": float(np.min(data)),
        "max": float(np.max(data)),
        "experiment_name": "base_template"
    }
    
    # 示例：绘制图表
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    
    # 直方图
    axes[0].hist(data, bins=30, edgecolor='black', alpha=0.7)
    axes[0].set_title('Data Distribution')
    axes[0].set_xlabel('Value')
    axes[0].set_ylabel('Frequency')
    axes[0].axvline(metrics["mean"], color='red', linestyle='--', label=f'Mean={metrics["mean"]:.2f}')
    axes[0].legend()
    
    # 箱线图
    axes[1].boxplot(data, vert=True)
    axes[1].set_title('Box Plot')
    axes[1].set_ylabel('Value')
    
    plt.tight_layout()
    save_figure(fig, "analysis.png")
    
    # 保存指标
    save_metrics(metrics)
    
    print("\n" + "=" * 50)
    print("Experiment Completed")
    print("=" * 50)


if __name__ == "__main__":
    main()
