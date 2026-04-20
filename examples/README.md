# AI-Research-Assistant 示例

本目录包含使用 AI-Research-Assistant Skill 的示例。

## 快速开始

### 1. 准备主题描述

创建 `topic.md` 文件：

```markdown
# 你的研究主题

## 关键词
关键词1, 关键词2, 关键词3

## 研究背景
介绍研究背景...

## 研究目标
描述研究目标...
```

参考：[topic_example.md](topic_example.md)

### 2. 运行完整流程（增强版）

增强版自动从 GitHub 下载基线代码和获取真实数据集：

```bash
cd ~/.workbuddy/skills/ai-research-assistant
python main.py --topic topic.md --output ./output --enhanced
```

### 3. 查看结果（增强版）

```
output/
├── ideas.json                    # 生成的研究假设
├── experiment/
│   ├── github_repos/             # 下载的 GitHub 仓库
│   │   └── owner_repo/
│   ├── datasets/                 # 下载的数据集
│   │   └── dataset_name/
│   │       ├── train.csv
│   │       └── test.csv
│   ├── baseline.py               # 基线实验代码
│   ├── proposed.py               # 改进实验代码
│   ├── sandbox/
│   │   └── outputs/
│   │       ├── baseline_metrics.json
│   │       ├── proposed_metrics.json
│   │       └── comparison.json   # 对比分析
│   ├── experiment_results.json   # 完整实验结果
│   ├── paper.md                  # 生成的论文
│   └── sections/                 # 论文章节
├── review/
│   ├── review_round_1.json       # 审核报告
│   ├── review_round_2.json
│   └── paper_final.md            # 最终论文
└── pipeline_record.json          # 执行记录
```

## 增强版功能

### GitHub 集成

自动搜索和下载相关代码仓库作为基线：

```bash
# 启用增强版（默认）
python main.py --topic topic.md --output ./output --enhanced

# 禁用增强版（仅使用基础实验）
python main.py --topic topic.md --output ./output --no-enhanced
```

功能：
- 根据研究关键词搜索 GitHub 仓库
- 自动克隆仓库到本地
- 分析仓库结构和入口点
- 提取可运行的基线代码

### 数据集自动获取

自动从多个数据源获取真实数据集：

支持的数据源：
- **Hugging Face Datasets**：`datasets` 库
- **Kaggle**：Kaggle API（需要配置 token）
- **UCI ML Repository**：网页爬取

配置 Kaggle Token：
```bash
# 在 config.yaml 中设置
# 或将 ~/.kaggle/kaggle.json 放在正确位置
```

### 基线对比实验

自动运行基线和改进方法进行对比：

1. **基线实验**：从 GitHub 仓库提取代码运行
2. **改进实验**：基于研究假设生成代码运行
3. **对比分析**：自动生成性能对比表格

## 分阶段执行

### 仅生成假设

```bash
python main.py --phase ideation --topic topic.md --output ./output
```

### 仅执行实验（增强版）

```bash
python main.py --phase experiment \
    --ideas ./output/ideas.json \
    --idea-id 1 \
    --output ./output/experiment \
    --enhanced
```

### 仅撰写论文

```bash
python main.py --phase writeup \
    --ideas ./output/ideas.json \
    --summary ./output/experiment/experiment_results.json \
    --output ./output/experiment
```

### 仅审核论文

```bash
python main.py --phase review \
    --paper ./output/experiment/paper.md \
    --output ./output/review
```

## 配置

编辑 `config.yaml` 自定义：

- 使用的 LLM 模型
- 实验执行参数
- 论文章节结构
- 审核标准

## 安全说明

⚠️ 实验代码在沙盒中执行，采取以下安全措施：

1. 代码执行前安全检查
2. 超时控制
3. 资源限制（内存、CPU）
4. 禁止危险操作（网络访问、系统命令等）

## 自定义模板

可以修改 `templates/` 目录下的模板文件：

- `paper/` - 论文章节模板
- `experiment/` - 实验代码模板

## 提示

1. **主题描述越详细，生成的假设质量越高**
2. **实验阶段可能需要根据具体领域调整代码**
3. **论文生成后可以手动编辑优化**
4. **建议先使用 `--mock` 测试流程**
