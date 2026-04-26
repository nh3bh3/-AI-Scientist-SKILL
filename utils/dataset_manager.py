"""
数据集管理器

功能：
1. 根据研究主题自动搜索相关数据集
2. 从多个数据源下载数据集（Kaggle、Hugging Face、UCI等）
3. 自动配置数据集路径和格式
4. 数据预处理和转换
5. 数据集元数据管理
"""

import os
import json
import datetime
import shutil
import zipfile
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from urllib.parse import urlparse


@dataclass
class DatasetInfo:
    """数据集信息"""
    name: str
    source: str  # kaggle, huggingface, uci, github, etc.
    url: str
    description: str
    size_mb: Optional[float]
    format: str  # csv, json, zip, etc.
    task_type: str  # classification, regression, nlp, cv, etc.
    features: List[str]
    target_column: Optional[str]
    download_path: Optional[str] = None
    local_path: Optional[str] = None
    retrieved_at: Optional[str] = None


class DatasetManager:
    """数据集管理器"""
    
    # 常见的数据集仓库
    DATASET_SOURCES = {
        'kaggle': 'https://www.kaggle.com/datasets',
        'huggingface': 'https://huggingface.co/datasets',
        'uci': 'https://archive.ics.uci.edu/ml/datasets.php',
        'github': 'https://github.com',
        'google': 'https://datasetsearch.research.google.com',
        'paperswithcode': 'https://paperswithcode.com/datasets'
    }
    
    def __init__(self, work_dir: Optional[str] = None,
                 kaggle_token: Optional[str] = None,
                 hf_token: Optional[str] = None):
        """
        初始化
        
        Args:
            work_dir: 数据存储目录
            kaggle_token: Kaggle API Token
            hf_token: Hugging Face Token
        """
        self.work_dir = Path(work_dir) if work_dir else Path.cwd() / "datasets"
        self.work_dir.mkdir(parents=True, exist_ok=True)
        
        self.kaggle_token = kaggle_token
        self.hf_token = hf_token
        
        # 已下载的数据集
        self.downloaded_datasets: Dict[str, DatasetInfo] = {}
    
    def search_datasets(self, keywords: List[str], 
                       task_type: Optional[str] = None,
                       max_results: int = 10) -> List[DatasetInfo]:
        """
        搜索数据集
        
        Args:
            keywords: 关键词列表
            task_type: 任务类型（classification/regression/nlp/cv）
            max_results: 最大结果数
            
        Returns:
            数据集列表
        """
        query = self.build_search_query(keywords, task_type)
        print(f"搜索数据集: {query}")
        
        datasets = []
        
        # 搜索 Hugging Face
        hf_datasets = self._search_huggingface(keywords, task_type, max_results // 2)
        datasets.extend(hf_datasets)
        
        # 搜索 Kaggle（如果有 token）
        if self.kaggle_token:
            kaggle_datasets = self._search_kaggle(keywords, max_results // 3)
            datasets.extend(kaggle_datasets)
        
        # 搜索 UCI ML Repository
        uci_datasets = self._search_uci(keywords, max_results // 3)
        datasets.extend(uci_datasets)
        
        print(f"  找到 {len(datasets)} 个数据集")
        return datasets[:max_results]

    @staticmethod
    def build_search_query(keywords: List[str], task_type: Optional[str] = None) -> str:
        tokens = [k.strip() for k in keywords if k and k.strip()]
        if task_type:
            tokens.append(task_type)
        return " ".join(tokens[:8]) if tokens else "machine learning dataset"
    
    def _search_huggingface(self, keywords: List[str], 
                           task_type: Optional[str],
                           max_results: int) -> List[DatasetInfo]:
        """搜索 Hugging Face Datasets"""
        datasets = []
        
        try:
            import urllib.request
            import urllib.parse
            
            query = " ".join(keywords)
            url = f"https://huggingface.co/api/datasets?search={urllib.parse.quote(query)}&limit={max_results}"
            
            req = urllib.request.Request(url)
            if self.hf_token:
                req.add_header('Authorization', f'Bearer {self.hf_token}')
            
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode())
                
                for item in data:
                    id_parts = item['id'].split('/')
                    if len(id_parts) >= 2:
                        name = id_parts[-1]
                    else:
                        name = item['id']
                    
                    # 推断任务类型
                    tags = item.get('tags', [])
                    inferred_task = self._infer_task_type(tags, item.get('description', ''))
                    
                    # 如果指定了任务类型，进行过滤
                    if task_type and inferred_task != task_type:
                        continue
                    
                    dataset = DatasetInfo(
                        name=name,
                        source='huggingface',
                        url=f"https://huggingface.co/datasets/{item['id']}",
                        description=item.get('description', '')[:200],
                        size_mb=None,  # HF API 不直接提供大小
                        format=self._infer_format(item),
                        task_type=inferred_task,
                        features=[],  # 需要下载后才能知道
                        target_column=None,
                        retrieved_at=datetime.datetime.utcnow().isoformat()
                    )
                    datasets.append(dataset)
                    
        except Exception as e:
            print(f"  Hugging Face 搜索失败: {e}")
        
        return datasets
    
    def _search_kaggle(self, keywords: List[str], max_results: int) -> List[DatasetInfo]:
        """搜索 Kaggle 数据集"""
        datasets = []
        
        try:
            # 使用 kaggle API
            query = " ".join(keywords)
            result = subprocess.run(
                ['kaggle', 'datasets', 'list', '-s', query, '--csv'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                # 解析 CSV 输出
                for line in lines[1:max_results+1]:  # 跳过表头
                    parts = line.split(',')
                    if len(parts) >= 4:
                        ref = parts[0].strip('"')
                        name = ref.split('/')[-1] if '/' in ref else ref
                        
                        dataset = DatasetInfo(
                            name=name,
                            source='kaggle',
                            url=f"https://www.kaggle.com/datasets/{ref}",
                            description=parts[1].strip('"') if len(parts) > 1 else '',
                            size_mb=None,
                            format='csv',  # Kaggle 大多是 CSV
                            task_type='unknown',
                            features=[],
                            target_column=None,
                            retrieved_at=datetime.datetime.utcnow().isoformat()
                        )
                        datasets.append(dataset)
                        
        except FileNotFoundError:
            print("  Kaggle CLI 未安装")
        except Exception as e:
            print(f"  Kaggle 搜索失败: {e}")
        
        return datasets
    
    def _search_uci(self, keywords: List[str], max_results: int) -> List[DatasetInfo]:
        """搜索 UCI ML Repository"""
        datasets = []
        
        try:
            import urllib.request
            from html.parser import HTMLParser
            
            class UCIParser(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.datasets = []
                    self.in_table = False
                    self.current_data = {}
                    self.in_link = False
                    self.current_url = ''
                
                def handle_starttag(self, tag, attrs):
                    attrs_dict = dict(attrs)
                    if tag == 'table':
                        self.in_table = True
                    elif tag == 'a' and self.in_table and 'href' in attrs_dict:
                        self.in_link = True
                        self.current_url = attrs_dict['href']
                
                def handle_endtag(self, tag):
                    if tag == 'table':
                        self.in_table = False
                    elif tag == 'a':
                        self.in_link = False
                
                def handle_data(self, data):
                    if self.in_link and data.strip():
                        # 检查是否匹配关键词
                        if any(kw.lower() in data.lower() for kw in keywords):
                            self.datasets.append({
                                'name': data.strip(),
                                'url': f"https://archive.ics.uci.edu/ml/{self.current_url}"
                            })
            
            url = "https://archive.ics.uci.edu/ml/datasets.php"
            req = urllib.request.Request(url)
            
            with urllib.request.urlopen(req, timeout=30) as response:
                html = response.read().decode('utf-8', errors='ignore')
                parser = UCIParser()
                parser.feed(html)
                
                for item in parser.datasets[:max_results]:
                    dataset = DatasetInfo(
                        name=item['name'],
                        source='uci',
                        url=item['url'],
                        description='UCI ML Repository dataset',
                        size_mb=None,
                        format='csv',
                        task_type='unknown',
                        features=[],
                        target_column=None,
                        retrieved_at=datetime.datetime.utcnow().isoformat()
                    )
                    datasets.append(dataset)
                    
        except Exception as e:
            print(f"  UCI 搜索失败: {e}")
        
        return datasets
    
    def _infer_task_type(self, tags: List[str], description: str) -> str:
        """推断任务类型"""
        text = ' '.join(tags + [description]).lower()
        
        if any(kw in text for kw in ['classification', 'classify', 'category']):
            return 'classification'
        elif any(kw in text for kw in ['regression', 'predict', 'forecast']):
            return 'regression'
        elif any(kw in text for kw in ['nlp', 'text', 'sentiment', 'language']):
            return 'nlp'
        elif any(kw in text for kw in ['image', 'vision', 'cnn', 'object detection']):
            return 'cv'
        elif any(kw in text for kw in ['translation', 'seq2seq']):
            return 'translation'
        else:
            return 'unknown'
    
    def _infer_format(self, item: Dict) -> str:
        """推断数据格式"""
        tags = item.get('tags', [])
        
        if 'csv' in tags:
            return 'csv'
        elif 'json' in tags:
            return 'json'
        elif 'text' in tags or 'text-classification' in tags:
            return 'text'
        elif 'image' in tags:
            return 'image'
        else:
            return 'unknown'
    
    def download_dataset(self, dataset: DatasetInfo, 
                        target_dir: Optional[Path] = None) -> bool:
        """
        下载数据集
        
        Args:
            dataset: 数据集信息
            target_dir: 目标目录
            
        Returns:
            是否成功
        """
        if target_dir is None:
            target_dir = self.work_dir / dataset.name.replace(' ', '_')
        
        target_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"下载数据集: {dataset.name} ({dataset.source})")
        
        if dataset.source == 'huggingface':
            return self._download_huggingface(dataset, target_dir)
        elif dataset.source == 'kaggle':
            return self._download_kaggle(dataset, target_dir)
        elif dataset.source == 'uci':
            return self._download_uci(dataset, target_dir)
        else:
            print(f"  [FAIL] 不支持的数据源: {dataset.source}")
            return False
    
    def _download_huggingface(self, dataset: DatasetInfo, target_dir: Path) -> bool:
        """从 Hugging Face 下载"""
        try:
            # 使用 datasets 库
            from datasets import load_dataset
            
            dataset_id = dataset.url.replace('https://huggingface.co/datasets/', '')
            
            print(f"  使用 datasets 库加载: {dataset_id}")
            hf_dataset = load_dataset(dataset_id)
            
            # 保存为 CSV
            for split in ['train', 'test', 'validation']:
                if split in hf_dataset:
                    output_file = target_dir / f"{split}.csv"
                    hf_dataset[split].to_csv(output_file, index=False)
                    print(f"  [OK] 保存 {split} 到 {output_file}")
            
            # 保存数据集信息
            dataset.local_path = str(target_dir)
            self.downloaded_datasets[dataset.name] = dataset
            self.save_source_metadata(dataset, target_dir)
            
            return True
            
        except ImportError:
            print("  [WARN] datasets 库未安装，尝试使用 wget")
            return self._download_with_wget(dataset.url, target_dir)
        except Exception as e:
            print(f"  [FAIL] 下载失败: {e}")
            return False
    
    def _download_kaggle(self, dataset: DatasetInfo, target_dir: Path) -> bool:
        """从 Kaggle 下载"""
        try:
            # 提取 dataset ref
            ref = dataset.url.replace('https://www.kaggle.com/datasets/', '')
            
            print(f"  使用 kaggle API 下载: {ref}")
            
            # 下载到临时目录
            temp_dir = target_dir / "temp"
            temp_dir.mkdir(exist_ok=True)
            
            result = subprocess.run(
                ['kaggle', 'datasets', 'download', '-d', ref, '-p', str(temp_dir), '--unzip'],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                # 移动文件到目标目录
                for f in temp_dir.iterdir():
                    if f.is_file():
                        shutil.move(str(f), str(target_dir))
                    elif f.is_dir():
                        for sub_f in f.iterdir():
                            shutil.move(str(sub_f), str(target_dir))
                
                # 删除临时目录
                shutil.rmtree(temp_dir)
                
                dataset.local_path = str(target_dir)
                self.downloaded_datasets[dataset.name] = dataset
                self.save_source_metadata(dataset, target_dir)
                
                print(f"  [OK] 下载完成")
                return True
            else:
                print(f"  [FAIL] {result.stderr}")
                return False
                
        except Exception as e:
            print(f"  [FAIL] 下载失败: {e}")
            return False
    
    def _download_uci(self, dataset: DatasetInfo, target_dir: Path) -> bool:
        """从 UCI 下载"""
        try:
            import urllib.request
            from html.parser import HTMLParser
            
            # 获取数据集页面
            req = urllib.request.Request(dataset.url)
            
            with urllib.request.urlopen(req, timeout=30) as response:
                html = response.read().decode('utf-8', errors='ignore')
                
                # 查找数据文件链接
                data_url = None
                if 'href="https://archive.ics.uci.edu/ml/machine-learning-databases/' in html:
                    start = html.find('href="https://archive.ics.uci.edu/ml/machine-learning-databases/')
                    end = html.find('"', start + 6)
                    data_url = html[start+6:end]
                
                if data_url:
                    print(f"  下载数据文件: {data_url}")
                    
                    # 下载数据
                    file_name = data_url.split('/')[-1]
                    file_path = target_dir / file_name
                    
                    urllib.request.urlretrieve(data_url, file_path)
                    
                    # 解压如果是 zip
                    if file_name.endswith('.zip'):
                        with zipfile.ZipFile(file_path, 'r') as zip_ref:
                            zip_ref.extractall(target_dir)
                        file_path.unlink()
                    
                    dataset.local_path = str(target_dir)
                    self.downloaded_datasets[dataset.name] = dataset
                    self.save_source_metadata(dataset, target_dir)
                    
                    print(f"  [OK] 下载完成")
                    return True
                else:
                    print(f"  [FAIL] 未找到数据文件链接")
                    return False
                    
        except Exception as e:
            print(f"  [FAIL] 下载失败: {e}")
            return False
    
    def _download_with_wget(self, url: str, target_dir: Path) -> bool:
        """使用 wget 下载"""
        try:
            file_name = url.split('/')[-1] or 'data'
            file_path = target_dir / file_name
            
            subprocess.run(
                ['wget', '-O', str(file_path), url],
                capture_output=True,
                timeout=120
            )
            
            if file_path.exists():
                print(f"  [OK] 下载完成: {file_path}")
                return True
            else:
                return False
                
        except FileNotFoundError:
            print("  [FAIL] wget 未安装")
            return False
        except Exception as e:
            print(f"  [FAIL] 下载失败: {e}")
            return False
    
    def analyze_dataset(self, dataset_name: str) -> Optional[Dict]:
        """
        分析已下载的数据集
        
        Args:
            dataset_name: 数据集名称
            
        Returns:
            分析结果
        """
        if dataset_name not in self.downloaded_datasets:
            print(f"数据集未下载: {dataset_name}")
            return None
        
        dataset = self.downloaded_datasets[dataset_name]
        local_path = Path(dataset.local_path)
        
        print(f"分析数据集: {dataset_name}")
        
        analysis = {
            'name': dataset_name,
            'path': dataset.local_path,
            'files': [],
            'statistics': {}
        }
        
        # 查找数据文件
        data_files = []
        for ext in ['.csv', '.json', '.jsonl', '.txt', '.tsv', '.parquet']:
            data_files.extend(list(local_path.rglob(f"*{ext}")))
        
        analysis['files'] = [str(f.relative_to(local_path)) for f in data_files]
        
        # 分析 CSV 文件
        if data_files:
            import pandas as pd
            
            for df_file in data_files[:3]:  # 限制分析前3个文件
                if df_file.suffix == '.csv':
                    try:
                        df = pd.read_csv(df_file)
                        
                        file_stats = {
                            'rows': len(df),
                            'columns': len(df.columns),
                            'column_names': list(df.columns),
                            'dtypes': {col: str(dtype) for col, dtype in df.dtypes.items()},
                            'missing_values': df.isnull().sum().to_dict()
                        }
                        
                        analysis['statistics'][df_file.name] = file_stats
                        
                    except Exception as e:
                        print(f"  分析 {df_file} 失败: {e}")
        
        print(f"  [OK] 分析完成: {len(data_files)} 个数据文件")
        
        return analysis

    def save_source_metadata(self, dataset: DatasetInfo, target_dir: Path) -> Path:
        target_dir.mkdir(parents=True, exist_ok=True)
        metadata = {
            "title": dataset.name,
            "source": dataset.source,
            "url": dataset.url,
            "download_time": datetime.datetime.utcnow().isoformat() + "Z",
            "task_type": dataset.task_type,
            "description": dataset.description,
        }
        out = target_dir / "source_metadata.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        return out

    def preprocess_dataframe(self, df, task_type: str = "classification"):
        """通用清洗：缺失值、标准化、编码。"""
        import pandas as pd
        from sklearn.impute import SimpleImputer
        from sklearn.preprocessing import StandardScaler

        cleaned = df.copy()
        num_cols = cleaned.select_dtypes(include=["number"]).columns.tolist()
        cat_cols = [c for c in cleaned.columns if c not in num_cols]
        if num_cols:
            imp = SimpleImputer(strategy="median")
            cleaned[num_cols] = imp.fit_transform(cleaned[num_cols])
            scaler = StandardScaler()
            cleaned[num_cols] = scaler.fit_transform(cleaned[num_cols])
        if cat_cols:
            for c in cat_cols:
                cleaned[c] = cleaned[c].astype(str).fillna("unknown")
            cleaned = pd.get_dummies(cleaned, columns=cat_cols, dummy_na=True)
        return cleaned
    
    def generate_data_loading_code(self, dataset_name: str) -> str:
        """
        生成数据加载代码
        
        Args:
            dataset_name: 数据集名称
            
        Returns:
            Python 代码字符串
        """
        if dataset_name not in self.downloaded_datasets:
            return f"# 数据集未下载: {dataset_name}"
        
        dataset = self.downloaded_datasets[dataset_name]
        local_path = Path(dataset.local_path)
        
        # 查找 CSV 文件
        csv_files = list(local_path.rglob("*.csv"))
        
        code = f'''"""
数据加载代码 - {dataset_name}
数据集路径: {dataset.local_path}
"""

import pandas as pd
import os

DATASET_PATH = "{dataset.local_path}"

def load_data():
    """加载数据集"""
    data_path = DATASET_PATH
    
'''
        
        if csv_files:
            # 为每个 CSV 文件生成加载代码
            for i, csv_file in enumerate(csv_files[:3]):
                rel_path = csv_file.relative_to(local_path)
                var_name = f"data_{i+1}" if len(csv_files) > 1 else "data"
                
                code += f'''    # 加载 {rel_path}
    {var_name} = pd.read_csv(os.path.join(data_path, "{rel_path}"))
    print(f"Loaded {rel_path}: {{{var_name}.shape}}")
    
'''
            
            if len(csv_files) > 1:
                code += '''    return data_1, data_2, data_3
'''
            else:
                code += '''    return data
'''
        else:
            code += '''    # 请根据实际数据格式修改
    raise NotImplementedError("请实现数据加载逻辑")
'''
        
        code += '''
if __name__ == "__main__":
    data = load_data()
'''
        
        return code
    
    def get_dataset_for_task(self, task_description: str, 
                            task_type: str) -> Optional[DatasetInfo]:
        """
        根据任务描述自动获取合适的数据集
        
        Args:
            task_description: 任务描述
            task_type: 任务类型
            
        Returns:
            数据集信息
        """
        # 提取关键词
        keywords = task_description.lower().split()
        
        # 搜索数据集
        datasets = self.search_datasets(keywords, task_type, max_results=5)
        
        if not datasets:
            return None
        
        # 选择最合适的数据集（根据描述匹配度）
        best_match = datasets[0]
        
        # 尝试下载
        if self.download_dataset(best_match):
            return best_match
        
        # 如果失败，尝试下一个
        for dataset in datasets[1:]:
            if self.download_dataset(dataset):
                return dataset
        
        return None
    
    def cleanup(self, dataset_name: Optional[str] = None):
        """清理下载的数据集"""
        if dataset_name and dataset_name in self.downloaded_datasets:
            dataset = self.downloaded_datasets[dataset_name]
            if dataset.local_path and Path(dataset.local_path).exists():
                shutil.rmtree(dataset.local_path)
                del self.downloaded_datasets[dataset_name]
        elif dataset_name is None:
            # 清理所有
            for dataset in self.downloaded_datasets.values():
                if dataset.local_path and Path(dataset.local_path).exists():
                    shutil.rmtree(dataset.local_path)
            self.downloaded_datasets.clear()


if __name__ == "__main__":
    # 测试
    manager = DatasetManager()
    
    # 搜索情感分析数据集
    datasets = manager.search_datasets(
        ["sentiment", "analysis", "movie", "review"],
        task_type="nlp",
        max_results=5
    )
    
    if datasets:
        # 下载第一个
        dataset = datasets[0]
        print(f"\n下载: {dataset.name}")
        
        if manager.download_dataset(dataset):
            # 分析
            analysis = manager.analyze_dataset(dataset.name)
            print(f"\n分析结果: {json.dumps(analysis, indent=2, default=str)[:500]}")
            
            # 生成加载代码
            code = manager.generate_data_loading_code(dataset.name)
            print(f"\n数据加载代码:\n{code[:500]}")
        
        # 清理
        manager.cleanup(dataset.name)
