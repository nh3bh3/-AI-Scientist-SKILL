# AI-Scientist-SKILL（OpenClaw / Codex Agent）

该仓库实现一个分阶段科研流程：构思、实验、写作、审稿。

## 功能概览

- Ideation：根据主题生成研究假设。
- Experiment v2：检索代码基线与数据集，执行候选实验。
- Writeup：根据实验摘要生成论文草稿。
- Review v2：多轮审稿、真实性检查与可复现性检查。

## 快速开始

```bash
python main.py --phase full --topic examples/topic_example.md --output ./research_output --mock
```

常用分阶段命令：

```bash
python main.py --phase ideation --topic examples/topic_example.md --output ./research_output
python main.py --phase experiment --ideas ./research_output/ideas.json --idea-id 1 --output ./research_output/experiment
python main.py --phase writeup --ideas ./research_output/ideas.json --idea-id 1 --summary ./research_output/experiment/summary.json --output ./research_output/experiment
python main.py --phase review --paper ./research_output/experiment/paper.md --output ./research_output/review --experiment-dir ./research_output/experiment
```

## 实验阶段配置（重点）

`ExperimentPhaseV2` 支持候选池、并行执行和 BFTS 搜索：

```yaml
experiment:
  candidate_manager:
    enabled: true
    max_candidates: 4
    top_k: 2
    model_types: [LogisticRegression, RandomForest, MLPClassifier, Transformer]
    enable_gpu: true
    max_parallel: 2
  search:
    strategy: bfts
  bfts:
    max_depth: 2
    max_nodes: 8
    branching_factor: 2
  resume_from: null
```

说明：
- `search.strategy: bfts` 时启用 Best-First Tree Search。
- 每个候选在独立沙箱目录运行，可并行执行。
- 运行过程会写入 `pipeline_record.json`，并可通过 `resume_from` 恢复。

## 审稿阶段配置（重点）

```yaml
review:
  threshold: 7.0
  automated_reviewer:
    enabled: true
  vlm_feedback:
    enabled: true
```

说明：
- 审稿包含结构性评分与真实性检查。
- 当 `vlm_feedback` 启用且存在图像文件时，会附加图表检查反馈。

## 目录结构

```text
.
├── main.py
├── config.yaml
├── SKILL.md
├── phases/
├── templates/
├── utils/
└── examples/
```

## 注意事项

- 仓库会执行自动生成代码，建议在隔离环境运行。
- 正式投稿前建议人工复核实验结果、引用和伦理合规内容。
