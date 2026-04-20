---
name: ai-research-assistant
description: >-
  Orchestrates ideation, sandboxed experiments (optional GitHub baselines and
  public datasets), paper write-up, and multi-round review with authenticity
  checks. Use when the user mentions automated research, AI Scientist,
  hypothesis generation, experiment automation, paper drafting, 科研助手,
  自动科研, 假设生成, 实验自动化, or end-to-end research workflows inspired by
  Sakana AI-Scientist-v2.
---

# AI-Research-Assistant（科研助手 Skill）

本仓库是面向 **Cursor Agent** 的操作说明：在对话中按阶段调用本项目的 `main.py` 与各 `phases/`，完成「构思 → 实验 → 撰写 → 审稿」闭环。设计参考 [SakanaAI/AI-Scientist-v2](https://github.com/SakanaAI/AI-Scientist-v2)，但 **不是** 该仓库的 Python 复刻（上游依赖 Linux/CUDA、BFTS 树搜索与独立脚本链）。

---

## 与 AI-Scientist-v2 的对应关系

| AI-Scientist-v2（上游） | 本 Skill / 仓库 |
|------------------------|-----------------|
| `perform_ideation_temp_free.py` + workshop Markdown → JSON | `phases/ideation.py`：主题 Markdown → `ideas.json`（由 Agent 调 LLM + 可选检索完成） |
| `launch_scientist_bfts.py` + `bfts_config.yaml`（BFTS 树搜索、多 worker） | `phases/experiment.py` / `experiment_v2.py`：顺序实验 + 重试调试，**无**完整 BFTS 实现 |
| 多模型：`model_writeup` / `model_citation` / `model_review` 等 | `config.yaml` 中 `models.ideation|experiment|writeup|review`（由集成方映射到实际 API） |
| Semantic Scholar、`S2_API_KEY` | `config.yaml` 的 `search.sources` 可含 `semantic_scholar`；有 key 时降低限流风险 |
| 沙箱警告：执行 LLM 生成代码 | **必须** 限定工作目录、超时、白名单包；执行前向用户展示代码并得到确认（若环境策略要求） |

**何时仍应直接使用上游仓库**：需要论文级完整管线、GPU 上真实训练、以及官方 BFTS 行为时，请在隔离环境克隆上游并按其 README 运行，而不是仅依赖本 Skill。

---

## Agent 工作方式（必读）

1. **先读** 用户仓库根目录的 `config.yaml`，尊重 `experiment`、`review`、`output`、`search` 等开关。
2. **构思**：读取用户提供的主题 Markdown，解析标题与「关键词」等章节；调用项目内逻辑或自行用 LLM 生成结构化 `ideas.json`，字段需与 `phases/ideation.py` 中 `ResearchIdea` 一致（含 `id`, `title`, `hypothesis`, `method`, `expected_result`, `contribution`, `feasibility`, `novelty`, `significance`, `related_work`, `keywords`）。
3. **实验**：优先使用增强版 `ExperimentPhaseV2`（`main.py` 默认）。在沙盒目录运行生成代码，收集 `summary.json`、`experiment_results.json`、图表与日志；失败则按 `experiment.max_retries` 分析日志并迭代。
4. **撰写**：用 **真实指标与文件路径** 写 `paper.md`，禁止编造表格数值；图不可用则按 `output.figure_fallback` 做文字化描述。
5. **审稿**：增强审稿 `ReviewPhaseV2` 需要实验目录做交叉核对时，单独跑 `review` 阶段应传入 `--experiment-dir`（指向含 `experiment_results.json` 等的实验输出目录）。

实现 LLM 调用时：对 `AIResearchAssistant` 使用 `set_llm_callback`，签名 `(prompt: str, model: str) -> str`。

---

## 主题 Markdown（对齐 workshop 思路）

建议包含下列信息（可与中文小节标题混用）：

- **Title / 标题**：一行点明研究主题  
- **Keywords / 关键词**：逗号或顿号分隔  
- **TL;DR**（可选）：非正式一句话概括  
- **Abstract / 摘要式说明**：问题、缺口、拟做方向  
- **研究背景 / 目标**：与 `phases/ideation.py` 中 `parse_topic` 的正则一致更易解析  

上游示例结构见 [AI-Scientist-v2 `ai_scientist/ideas/`](https://github.com/SakanaAI/AI-Scientist-v2/tree/main/ai_scientist/ideas)；本仓库不强制英文标题，但字段越完整，构思与检索越稳。

---

## 命令行（本仓库真实入口）

在项目根目录执行（将路径换成用户实际路径）：

```bash
# 完整流程：主题 → ideas → 实验 → 论文 → 审稿
python main.py --phase full --topic path/to/topic.md --output ./research_output --idea-id 1

# 仅构思
python main.py --phase ideation --topic path/to/topic.md --output ./research_output

# 仅实验（需已有 ideas.json）
python main.py --phase experiment --ideas path/to/ideas.json --idea-id 1 --output ./experiment_out

# 仅撰写
python main.py --phase writeup --ideas path/to/ideas.json --idea-id 1 --summary path/to/summary.json --output ./writeup_out

# 仅审稿（增强版建议提供实验目录以便核对指标）
python main.py --phase review --paper path/to/paper.md --output ./review_out --experiment-dir path/to/experiment_out
```

测试无 API 时：`--mock` 可走通管线，但结果仅供调试。

---

## 各阶段产物（约定）

```
research_output/
├── ideas.json
├── experiment/           # 或你指定的 --output 子目录
│   ├── summary.json
│   ├── paper.md
│   └── sandbox/...
├── review/
└── pipeline_record.json
```

增强实验阶段可能包含 `github_repos/`、`datasets/`、`comparison.json` 等，以 `phases/experiment_v2.py` 实际输出为准。

---

## 论文与审稿要点

- **结构**：见 `config.yaml` 的 `paper_structure.sections`；模板在 `templates/paper/`。  
- **审稿**：`review.dimensions` 含创新性、可复现性、伦理等；`authenticity_check` 与 `ai_detection` 在 `review_v2` 中使用。  
- **多轮**：`review.rounds` 与 `review.threshold` 控制轮次与是否达标。

---

## 安全与合规

- **风险**：执行 LLM 生成的代码可能导致危险依赖、非预期进程或外联；默认应在隔离环境（容器/专用机）运行。  
- **披露**：若成果用于正式稿件，须在方法或致谢中 **明确披露** 使用自动化或 LLM 辅助（上游许可证亦要求显著披露；发表前请核对上游 [LICENSE](https://github.com/SakanaAI/AI-Scientist-v2/blob/main/LICENSE) 与你方单位政策）。  
- **本仓库 `config.yaml`**：`experiment.forbidden_operations`、`allowed_packages`、`resource_limits` 用于收紧执行面；Agent 不应擅自关闭这些约束。

---

## 依赖与技能协作

- **系统**：`git`、Python 3.9+；具体 ML/GPU 依赖由实验代码决定，勿在 Skill 中写死为「已安装」。  
- **Python**：按需安装 `pyyaml` 及实验/撰写所用库（本仓库未捆绑单一 `requirements.txt` 时，以实际 `import` 为准）。  
- **可选协作**：文献检索可用 WebSearch / 浏览器类工具；`config.yaml` 中 `search.sources` 列出期望来源时，Agent 应尽量满足。

---

## 项目结构（精简）

```
├── SKILL.md
├── config.yaml
├── main.py
├── phases/          # ideation, experiment(_v2), writeup, review(_v2)
├── utils/           # sandbox, github_manager, dataset_manager, ...
├── templates/
└── examples/
```

---

## 致谢

方法与流程灵感来自 [The AI Scientist-v2](https://github.com/SakanaAI/AI-Scientist-v2)（Sakana AI）。本 Skill 文本与仓库实现为其启发下的 **独立** 自动化助手，行为以本仓库代码为准。
