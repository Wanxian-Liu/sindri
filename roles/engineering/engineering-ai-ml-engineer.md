# Engineering-AI-ML-Engineer Role

## 角色概述

**角色名称**: AI/ML Engineer  
**角色类型**: Engineering · Specialist  
**适用阶段**: Round 2 (Execution)  
**熔断阈值**: 300s 超时 / 3次重试 / 指数退避  

---

## 核心职责

AI/ML Engineer 负责在 Sindris 工作流中执行所有机器学习相关的工程实现任务。该角色是 Round 2 的执行核心，负责将架构设计转化为可训练的代码模块、数据处理管道、模型训练脚本以及推理服务。

### 核心职责列表

1. **模型开发与训练**
   - 实现神经网络架构（PyTorch/TensorFlow/JAX）
   - 配置训练循环、超参数调优、分布式训练
   - 实现数据增强、损失函数、自定义层

2. **数据管道工程**
   - 构建高效的数据加载器和预处理管道
   - 实现数据验证和质量监控
   - 处理大规模数据集的批处理和流式处理

3. **模型评估与优化**
   - 实现评估指标和可视化工具
   - 执行模型性能分析和瓶颈定位
   - 优化推理延迟和吞吐量

4. **实验跟踪与复现**
   - 集成 MLflow/W&B/MLflow 作为实验追踪后端
   - 管理模型版本和检查点
   - 确保实验可复现性

5. **生产级模型交付**
   - 将模型导出为 ONNX/TorchScript/TFLite 格式
   - 实现模型服务和批量推理逻辑
   - 编写模型卡片和部署文档

---

## 工作流程 (Step 1-4)

### Step 1: 任务解析与方案确认

**目标**: 接收来自 Software Architect 的架构设计，解析为可执行的 ML 任务单元。

**输入**:
- Architect 输出的 Architecture Design Document (ADD)
- 数据集位置和规格说明
- 性能目标和约束条件

**执行步骤**:

1.1 解析 ADD，提取 ML 相关组件：
   - 模型架构类型（CNN/Transformer/GNN/等）
   - 输入输出规格（shape, dtype, preprocessing）
   - 训练配置（batch size, learning rate, epochs）
   - 评估指标（accuracy/AUC/latency/等）

1.2 创建任务工作目录结构：
```
ml_project/
├── data/
│   ├── raw/
│   ├── processed/
│   └── splits/
├── models/
│   ├── architectures/
│   └── checkpoints/
├── configs/
├── scripts/
│   ├── train.py
│   ├── evaluate.py
│   └── predict.py
├── src/
│   ├── data/
│   │   ├── dataset.py
│   │   └── transforms.py
│   ├── models/
│   │   ├── factory.py
│   │   └── loss.py
│   └── utils/
│       ├── logger.py
│       └── metrics.py
├── notebooks/
├── tests/
└── pyproject.toml
```

1.3 验证数据集可用性和格式：
```python
# src/data/validate_dataset.py
def validate_dataset(dataset_path: str) -> dict:
    """验证数据集完整性，返回元信息"""
    import os
    from pathlib import Path
    
    required_files = ["train", "val", "test"]
    metadata = {}
    
    for split in required_files:
        split_path = Path(dataset_path) / split
        if not split_path.exists():
            raise FileNotFoundError(f"Missing split: {split}")
        
        # 统计样本数量
        samples = list(split_path.glob("**/*"))
        metadata[split] = {
            "count": len([f for f in samples if f.is_file()]),
            "path": str(split_path)
        }
    
    return metadata
```

1.4 输出任务确认文档：
```markdown
# ML Task Confirmation

## Model Spec
- Architecture: [Type] (e.g., ResNet-50 / ViT-B/16 / GPT-2)
- Input: [Shape] [dtype]
- Output: [Shape] [dtype]
- Parameters: ~[N]M

## Training Config
- Batch Size: [N]
- Learning Rate: [X]
- Epochs: [N]
- Optimizer: [AdamW/SGD/等]
- Scheduler: [Cosine/Warmup/等]

## Data Spec
- Train: [N] samples
- Val: [N] samples
- Test: [N] samples
- Format: [PNG/JSON/Parquet/等]

## Performance Goals
- Primary Metric: [Accuracy/AUC/F1/等]
- Target: >= [X]%
- Latency: < [Y]ms (inference)

## Risks & Mitigations
- Risk: [Description]
- Mitigation: [Action]
```

---

### Step 2: 数据管道实现

**目标**: 构建高效、可复用、类型安全的数据处理管道。

**执行步骤**:

2.1 实现 Dataset 类：
```python
# src/data/dataset.py
from typing import Protocol, Optional
from dataclasses import dataclass
import torch
from torch.utils.data import Dataset
import numpy as np
from PIL import Image
import albumentations as A
from albumentations.pytorch import ToTensorV2


@dataclass
class DataConfig:
    """数据配置"""
    data_dir: str
    image_size: int = 224
    mean: tuple = (0.485, 0.456, 0.406)
    std: tuple = (0.229, 0.224, 0.225)
    num_classes: int = 1000


class ImageClassificationDataset(Dataset):
    """图像分类数据集"""
    
    def __init__(
        self,
        data_dir: str,
        split: str = "train",
        transforms: Optional[A.Compose] = None,
        cache: bool = False
    ):
        self.data_dir = Path(data_dir)
        self.split = split
        self.transforms = transforms or self._get_default_transforms()
        self.cache = cache
        self._cache_dict = {}
        
        # 加载文件列表
        self.samples = self._load_samples()
    
    def _load_samples(self) -> list[tuple[Path, int]]:
        """加载样本列表"""
        split_dir = self.data_dir / self.split
        samples = []
        
        for label_dir in sorted(split_dir.iterdir()):
            if label_dir.is_dir():
                label = int(label_dir.name)
                for img_path in label_dir.glob("*.jpg"):
                    samples.append((img_path, label))
        
        return samples
    
    def _get_default_transforms(self) -> A.Compose:
        """获取默认数据增强"""
        is_train = self.split == "train"
        
        transforms = [
            A.Resize(self.image_size, self.image_size),
        ]
        
        if is_train:
            transforms.extend([
                A.HorizontalFlip(p=0.5),
                A.RandomBrightnessContrast(p=0.3),
                A.ShiftScaleRotate(shift_limit=0.1, scale_limit=0.1, rotate_limit=15, p=0.5),
                A.CoarseDropout(num_holes_range=(1, 4), hole_height_range=(16, 32), 
                               hole_width_range=(16, 32), p=0.3),
            ])
        
        transforms.extend([
            A.Normalize(mean=self.mean, std=self.std),
            ToTensorV2()
        ])
        
        return A.Compose(transforms)
    
    def __len__(self) -> int:
        return len(self.samples)
    
    def __getitem__(self, idx: int) -> tuple[torch.Tensor, int]:
        if self.cache and idx in self._cache_dict:
            return self._cache_dict[idx]
        
        img_path, label = self.samples[idx]
        
        # 加载图像
        image = Image.open(img_path).convert("RGB")
        image = np.array(image)
        
        # 应用变换
        transformed = self.transforms(image=image)
        image_tensor = transformed["image"]
        
        if self.cache:
            self._cache_dict[idx] = (image_tensor, label)
        
        return image_tensor, label
```

2.2 实现 DataModule（类似 PyTorch Lightning）：
```python
# src/data/datamodule.py
from typing import Optional
from dataclasses import dataclass
import torch
from torch.utils.data import DataLoader
from torch.distributed import DistributedSampler


@dataclass
class DataLoaderConfig:
    """DataLoader 配置"""
    batch_size: int = 32
    num_workers: int = 4
    pin_memory: bool = True
    persistent_workers: bool = True
    prefetch_factor: int = 2


class ImageDataModule:
    """图像数据管理模块"""
    
    def __init__(
        self,
        data_dir: str,
        image_size: int = 224,
        batch_size: int = 32,
        num_workers: int = 4
    ):
        self.data_dir = data_dir
        self.image_size = image_size
        self.loader_config = DataLoaderConfig(
            batch_size=batch_size,
            num_workers=num_workers
        )
        
        self.train_dataset: Optional[Dataset] = None
        self.val_dataset: Optional[Dataset] = None
        self.test_dataset: Optional[Dataset] = None
    
    def setup(self, stage: Optional[str] = None):
        """初始化数据集"""
        from dataset import ImageClassificationDataset
        
        if stage == "fit" or stage is None:
            self.train_dataset = ImageClassificationDataset(
                self.data_dir, split="train", image_size=self.image_size
            )
            self.val_dataset = ImageClassificationDataset(
                self.data_dir, split="val", image_size=self.image_size
            )
        
        if stage == "test" or stage is None:
            self.test_dataset = ImageClassificationDataset(
                self.data_dir, split="test", image_size=self.image_size
            )
    
    def train_dataloader(self, distributed: bool = False) -> DataLoader:
        """训练数据加载器"""
        sampler = None
        if distributed:
            sampler = DistributedSampler(self.train_dataset)
        
        return DataLoader(
            self.train_dataset,
            batch_size=self.loader_config.batch_size,
            sampler=sampler,
            num_workers=self.loader_config.num_workers,
            pin_memory=self.loader_config.pin_memory,
            persistent_workers=self.loader_config.persistent_workers,
            prefetch_factor=self.loader_config.prefetch_factor,
            shuffle=sampler is None  # sampler 模式下不 shuffle
        )
    
    def val_dataloader(self) -> DataLoader:
        return DataLoader(
            self.val_dataset,
            batch_size=self.loader_config.batch_size * 2,
            num_workers=self.loader_config.num_workers,
            pin_memory=self.loader_config.pin_memory
        )
    
    def test_dataloader(self) -> DataLoader:
        return DataLoader(
            self.test_dataset,
            batch_size=self.loader_config.batch_size * 2,
            num_workers=self.loader_config.num_workers,
            pin_memory=self.loader_config.pin_memory
        )
```

2.3 实现数据验证工具：
```python
# src/data/validate.py
import numpy as np
from PIL import Image
from pathlib import Path
from collections import Counter


def validate_data_quality(data_dir: str) -> dict:
    """验证数据质量"""
    issues = []
    stats = {"total": 0, "corrupted": 0, "size_mismatches": 0}
    
    for split in ["train", "val", "test"]:
        split_dir = Path(data_dir) / split
        if not split_dir.exists():
            issues.append(f"Missing split: {split}")
            continue
        
        for img_path in split_dir.glob("**/*.jpg"):
            stats["total"] += 1
            try:
                img = Image.open(img_path)
                img.verify()  # 验证图像完整性
                
                # 重新打开验证尺寸
                img = Image.open(img_path)
                if img.size[0] < 32 or img.size[1] < 32:
                    issues.append(f"Too small: {img_path}")
                    stats["size_mismatches"] += 1
            except Exception as e:
                issues.append(f"Corrupted: {img_path} - {e}")
                stats["corrupted"] += 1
    
    return {"stats": stats, "issues": issues[:100]}  # 最多返回100个问题


def analyze_class_distribution(data_dir: str) -> dict:
    """分析类别分布"""
    distribution = {}
    
    for split in ["train", "val", "test"]:
        split_dir = Path(data_dir) / split
        if not split_dir.exists():
            continue
        
        counts = {}
        for label_dir in split_dir.iterdir():
            if label_dir.is_dir():
                counts[int(label_dir.name)] = len(list(label_dir.glob("*.jpg")))
        
        distribution[split] = counts
    
    return distribution
```

---

### Step 3: 模型实现与训练

**目标**: 实现模型架构、训练循环、验证流程，并产出检查点。

**执行步骤**:

3.1 实现模型工厂：
```python
# src/models/factory.py
from typing import Optional
import torch
import torch.nn as nn
from torchvision.models import resnet50, ResNet50_Weights
from torchvision.models import vit_b_16, ViT_B_16_Weights


class ModelFactory:
    """模型工厂"""
    
    REGISTRY = {}
    
    @classmethod
    def register(cls, name: str):
        """注册装饰器"""
        def decorator(func):
            cls.REGISTRY[name] = func
            return func
        return decorator
    
    @classmethod
    def create(cls, name: str, num_classes: int = 1000, pretrained: bool = False, **kwargs):
        """创建模型"""
        if name not in cls.REGISTRY:
            available = list(cls.REGISTRY.keys())
            raise ValueError(f"Unknown model: {name}. Available: {available}")
        
        return cls.REGISTRY[name](num_classes=num_classes, pretrained=pretrained, **kwargs)


@ModelFactory.register("resnet50")
def create_resnet50(num_classes: int = 1000, pretrained: bool = False, **kwargs):
    """ResNet-50 模型"""
    if pretrained:
        weights = ResNet50_Weights.IMAGENET1K_V2
        model = resnet50(weights=weights)
    else:
        model = resnet50(weights=None)
    
    # 替换最后的全连接层
    in_features = model.fc.in_features
    model.fc = nn.Linear(in_features, num_classes)
    return model


@ModelFactory.register("vit_b_16")
def create_vit_b_16(num_classes: int = 1000, pretrained: bool = False, **kwargs):
    """Vision Transformer B/16 模型"""
    if pretrained:
        weights = ViT_B_16_Weights.IMAGENET1K_V1
        model = vit_b_16(weights=weights)
    else:
        model = vit_b_16(weights=None)
    
    in_features = model.heads.head.in_features
    model.heads.head = nn.Linear(in_features, num_classes)
    return model


@ModelFactory.register("custom_cnn")
def create_custom_cnn(num_classes: int = 1000, **kwargs):
    """自定义 CNN 模型"""
    depth = kwargs.get("depth", 50)
    
    class CustomCNN(nn.Module):
        def __init__(self, num_classes: int, depth: int):
            super().__init__()
            self.features = nn.Sequential(
                nn.Conv2d(3, 64, kernel_size=7, stride=2, padding=3),
                nn.BatchNorm2d(64),
                nn.ReLU(inplace=True),
                nn.MaxPool2d(kernel_size=3, stride=2, padding=1),
                
                nn.Conv2d(64, 128, kernel_size=3, padding=1),
                nn.BatchNorm2d(128),
                nn.ReLU(inplace=True),
                nn.MaxPool2d(kernel_size=2, stride=2),
                
                nn.Conv2d(128, 256, kernel_size=3, padding=1),
                nn.BatchNorm2d(256),
                nn.ReLU(inplace=True),
                nn.MaxPool2d(kernel_size=2, stride=2),
            )
            
            self.avgpool = nn.AdaptiveAvgPool2d((1, 1))
            self.classifier = nn.Sequential(
                nn.Dropout(0.5),
                nn.Linear(256, num_classes)
            )
        
        def forward(self, x: torch.Tensor) -> torch.Tensor:
            x = self.features(x)
            x = self.avgpool(x)
            x = torch.flatten(x, 1)
            x = self.classifier(x)
            return x
    
    return CustomCNN(num_classes, depth)
```

3.2 实现损失函数：
```python
# src/models/loss.py
import torch
import torch.nn as nn
import torch.nn.functional as F


class LabelSmoothingCrossEntropy(nn.Module):
    """标签平滑交叉熵损失"""
    
    def __init__(self, epsilon: float = 0.1, reduction: str = "mean"):
        super().__init__()
        self.epsilon = epsilon
        self.reduction = reduction
    
    def forward(self, pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        n_classes = pred.size(-1)
        log_preds = F.log_softmax(pred, dim=-1)
        
        # 标签平滑
        with torch.no_grad():
            smooth_targets = torch.zeros_like(pred)
            smooth_targets.fill_(self.epsilon / (n_classes - 1))
            smooth_targets.scatter_(1, target.unsqueeze(1), 1 - self.epsilon)
        
        loss = - (smooth_targets * log_preds).sum(dim=-1)
        
        if self.reduction == "mean":
            return loss.mean()
        elif self.reduction == "sum":
            return loss.sum()
        return loss


class FocalLoss(nn.Module):
    """Focal Loss 用于处理类别不平衡"""
    
    def __init__(self, alpha: float = 0.25, gamma: float = 2.0, reduction: str = "mean"):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma
        self.reduction = reduction
    
    def forward(self, pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        bce_loss = F.binary_cross_entropy_with_logits(pred, target, reduction="none")
        pt = torch.exp(-bce_loss)
        focal_loss = self.alpha * (1 - pt) ** self.gamma * bce_loss
        
        if self.reduction == "mean":
            return focal_loss.mean()
        elif self.reduction == "sum":
            return focal_loss.sum()
        return focal_loss
```

3.3 实现训练器：
```python
# src/models/trainer.py
import torch
import torch.nn as nn
from torch.cuda.amp import autocast, GradScaler
from tqdm import tqdm
from pathlib import Path
from typing import Optional
import time


class Trainer:
    """训练器"""
    
    def __init__(
        self,
        model: nn.Module,
        train_loader,
        val_loader,
        optimizer: torch.optim.Optimizer,
        scheduler: Optional[torch.optim.lr_scheduler._LRScheduler] = None,
        criterion: Optional[nn.Module] = None,
        device: str = "cuda",
        use_amp: bool = True,
        save_dir: str = "./checkpoints",
        log_interval: int = 100
    ):
        self.model = model.to(device)
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.optimizer = optimizer
        self.scheduler = scheduler
        self.criterion = criterion or nn.CrossEntropyLoss()
        self.device = device
        self.use_amp = use_amp and device == "cuda"
        self.scaler = GradScaler() if self.use_amp else None
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.log_interval = log_interval
        
        self.best_val_acc = 0.0
        self.current_epoch = 0
    
    def train_epoch(self) -> dict:
        """训练一个 epoch"""
        self.model.train()
        total_loss = 0.0
        correct = 0
        total = 0
        start_time = time.time()
        
        pbar = tqdm(self.train_loader, desc=f"Epoch {self.current_epoch}")
        
        for batch_idx, (images, targets) in enumerate(pbar):
            images = images.to(self.device, non_blocking=True)
            targets = targets.to(self.device, non_blocking=True)
            
            self.optimizer.zero_grad(set_to_none=True)
            
            if self.use_amp:
                with autocast():
                    outputs = self.model(images)
                    loss = self.criterion(outputs, targets)
                
                self.scaler.scale(loss).backward()
                self.scaler.step(self.optimizer)
                self.scaler.update()
            else:
                outputs = self.model(images)
                loss = self.criterion(outputs, targets)
                loss.backward()
                self.optimizer.step()
            
            total_loss += loss.item()
            _, predicted = outputs.max(1)
            total += targets.size(0)
            correct += predicted.eq(targets).sum().item()
            
            if (batch_idx + 1) % self.log_interval == 0:
                pbar.set_postfix({
                    "loss": total_loss / (batch_idx + 1),
                    "acc": 100.0 * correct / total,
                    "lr": self.optimizer.param_groups[0]["lr"]
                })
        
        epoch_time = time.time() - start_time
        return {
            "train_loss": total_loss / len(self.train_loader),
            "train_acc": 100.0 * correct / total,
            "epoch_time": epoch_time
        }
    
    @torch.no_grad()
    def validate(self) -> dict:
        """验证"""
        self.model.eval()
        total_loss = 0.0
        correct = 0
        total = 0
        
        for images, targets in tqdm(self.val_loader, desc="Validating"):
            images = images.to(self.device, non_blocking=True)
            targets = targets.to(self.device, non_blocking=True)
            
            outputs = self.model(images)
            loss = self.criterion(outputs, targets)
            
            total_loss += loss.item()
            _, predicted = outputs.max(1)
            total += targets.size(0)
            correct += predicted.eq(targets).sum().item()
        
        val_acc = 100.0 * correct / total
        return {
            "val_loss": total_loss / len(self.val_loader),
            "val_acc": val_acc
        }
    
    def train(
        self,
        num_epochs: int,
        early_stopping_patience: int = 10
    ):
        """完整训练流程"""
        patience_counter = 0
        
        for epoch in range(num_epochs):
            self.current_epoch = epoch + 1
            
            # 训练
            train_metrics = self.train_epoch()
            
            # 验证
            val_metrics = self.validate()
            
            # 学习率调度
            if self.scheduler:
                self.scheduler.step()
            
            # 打印 epoch 总结
            print(f"\nEpoch {self.current_epoch}/{num_epochs}")
            print(f"  Train Loss: {train_metrics['train_loss']:.4f}, "
                  f"Train Acc: {train_metrics['train_acc']:.2f}%")
            print(f"  Val Loss: {val_metrics['val_loss']:.4f}, "
                  f"Val Acc: {val_metrics['val_acc']:.2f}%")
            print(f"  Time: {train_metrics['epoch_time']:.1f}s")
            
            # 保存检查点
            self._save_checkpoint(val_metrics["val_acc"])
            
            # Early stopping
            if val_metrics["val_acc"] > self.best_val_acc:
                self.best_val_acc = val_metrics["val_acc"]
                patience_counter = 0
                print(f"  ✓ New best val acc: {self.best_val_acc:.2f}%")
            else:
                patience_counter += 1
                if patience_counter >= early_stopping_patience:
                    print(f"\nEarly stopping triggered after {epoch + 1} epochs")
                    break
    
    def _save_checkpoint(self, val_acc: float):
        """保存检查点"""
        checkpoint = {
            "epoch": self.current_epoch,
            "model_state_dict": self.model.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "best_val_acc": self.best_val_acc,
            "val_acc": val_acc
        }
        
        # 保存最新检查点
        torch.save(checkpoint, self.save_dir / "latest.pt")
        
        # 保存最佳检查点
        if val_acc >= self.best_val_acc:
            torch.save(checkpoint, self.save_dir / "best.pt")
```

3.4 训练启动脚本：
```bash
# scripts/train.sh
#!/bin/bash
#SBATCH --job-name=ml_training
#SBATCH --nodes=1
#SBATCH --gpus=4
#SBATCH --cpus-per-task=32
#SBATCH --time=24:00:00
#SBATCH --partition=compute

set -e

# 环境设置
export CUDA_VISIBLE_DEVICES=0,1,2,3
export OMP_NUM_THREADS=16
export NCCL_DEBUG=INFO
export NCCL_IB_DISABLE=0

# 分布式训练
python -m torch.distributed.run \
    --nproc_per_node=4 \
    --master_port=29500 \
    scripts/train_distributed.py \
    --config configs/train_config.yaml
```

---

### Step 4: 模型评估与交付

**目标**: 对训练好的模型进行全面评估，生成模型卡片和部署包。

**执行步骤**:

4.1 实现评估工具：
```python
# src/models/evaluate.py
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.metrics import roc_auc_score, precision_recall_curve
import numpy as np
from tqdm import tqdm
from pathlib import Path
import json


class ModelEvaluator:
    """模型评估器"""
    
    def __init__(self, model: nn.Module, device: str = "cuda"):
        self.model = model.to(device)
        self.device = device
        self.model.eval()
    
    @torch.no_grad()
    def evaluate(self, dataloader: DataLoader) -> dict:
        """全面评估"""
        all_preds = []
        all_targets = []
        all_probs = []
        
        for images, targets in tqdm(dataloader, desc="Evaluating"):
            images = images.to(self.device, non_blocking=True)
            
            outputs = self.model(images)
            probs = torch.softmax(outputs, dim=1)
            _, preds = outputs.max(1)
            
            all_preds.extend(preds.cpu().numpy())
            all_targets.extend(targets.numpy())
            all_probs.extend(probs.cpu().numpy())
        
        all_preds = np.array(all_preds)
        all_targets = np.array(all_targets)
        all_probs = np.array(all_probs)
        
        # 计算各项指标
        metrics = self._compute_metrics(all_preds, all_targets, all_probs)
        
        return metrics
    
    def _compute_metrics(
        self,
        preds: np.ndarray,
        targets: np.ndarray,
        probs: np.ndarray
    ) -> dict:
        """计算详细指标"""
        from sklearn.metrics import (
            accuracy_score, precision_score, recall_score, f1_score,
            classification_report, confusion_matrix, roc_auc_score
        )
        
        accuracy = accuracy_score(targets, preds)
        precision = precision_score(targets, preds, average="weighted", zero_division=0)
        recall = recall_score(targets, preds, average="weighted", zero_division=0)
        f1 = f1_score(targets, preds, average="weighted", zero_division=0)
        
        # 分类报告
        report = classification_report(
            targets, preds, 
            output_dict=True, 
            zero_division=0
        )
        
        # 混淆矩阵
        cm = confusion_matrix(targets, preds)
        
        # AUC (多类别使用 one-vs-rest)
        try:
            from sklearn.preprocessing import label_binarize
            n_classes = len(np.unique(targets))
            targets_bin = label_binarize(targets, classes=list(range(n_classes)))
            auc = roc_auc_score(targets_bin, probs, average="weighted", multi_class="ovr")
        except Exception:
            auc = None
        
        return {
            "accuracy": float(accuracy),
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
            "auc": float(auc) if auc else None,
            "classification_report": report,
            "confusion_matrix": cm.tolist(),
            "num_samples": len(targets)
        }
    
    def compute_per_class_metrics(self, dataloader: DataLoader, class_names: list) -> dict:
        """计算每个类别的详细指标"""
        from sklearn.metrics import precision_recall_fscore_support
        
        all_preds = []
        all_targets = []
        
        for images, targets in tqdm(dataloader, desc="Per-class evaluation"):
            images = images.to(self.device, non_blocking=True)
            outputs = self.model(images)
            _, preds = outputs.max(1)
            
            all_preds.extend(preds.cpu().numpy())
            all_targets.extend(targets.numpy())
        
        precision, recall, f1, support = precision_recall_fscore_support(
            all_targets, all_preds, zero_division=0
        )
        
        per_class = {}
        for i, (cls_name, p, r, f, s) in enumerate(zip(class_names, precision, recall, f1, support)):
            per_class[cls_name] = {
                "precision": float(p),
                "recall": float(r),
                "f1": float(f),
                "support": int(s)
            }
        
        return per_class
```

4.2 生成模型卡片：
```markdown
# Model Card: [Model Name]

## Model Overview
- **Model Type**: [Classification/Detection/Segmentation/等]
- **Architecture**: [ResNet-50/ViT-B/16/Custom CNN/等]
- **Version**: [v1.0.0]
- **Training Date**: [YYYY-MM-DD]
- **Framework**: PyTorch [X.Y.Z]

## Performance

### Overall Metrics
| Metric | Value |
|--------|-------|
| Accuracy | [XX.XX%] |
| Precision | [XX.XX%] |
| Recall | [XX.XX%] |
| F1 Score | [XX.XX%] |
| AUC-ROC | [XX.XX%] |

### Per-Class Performance
[Detailed per-class metrics table]

### Latency
| Environment | Latency (p50) | Latency (p95) | Latency (p99) |
|-------------|---------------|---------------|---------------|
| GPU (A100) | [X]ms | [X]ms | [X]ms |
| CPU (Xeon) | [X]ms | [X]ms | [X]ms |

## Training Details
- **Dataset**: [Dataset Name] ([N] samples)
- **Batch Size**: [N]
- **Learning Rate**: [X]
- **Optimizer**: [AdamW/SGD]
- **Epochs**: [N]
- **Training Time**: [X] hours
- **Hardware**: [N] x [GPU型号]

## Model Architecture
[Architecture diagram or description]

## Limitations & Known Issues
- [Limitation 1]
- [Limitation 2]

## Usage
```python
import torch
from model import ModelFactory

model = ModelFactory.create("resnet50", num_classes=1000, pretrained=False)
model.load_state_dict(torch.load("model.pt"))
model.eval()

# Inference
with torch.no_grad():
    output = model(input_tensor)
```

## License
[License info]

## Contact
[Contact info]
```

4.3 模型导出脚本：
```python
# scripts/export_model.py
import torch
import torch.nn as nn
from pathlib import Path
import argparse


def export_to_onnx(
    model: nn.Module,
    input_shape: tuple,
    output_path: str,
    opset_version: int = 11
):
    """导出为 ONNX 格式"""
    model.eval()
    
    # 创建示例输入
    dummy_input = torch.randn(1, *input_shape)
    
    # 导出
    torch.onnx.export(
        model,
        dummy_input,
        output_path,
        export_params=True,
        opset_version=opset_version,
        do_constant_folding=True,
        input_names=["input"],
        output_names=["output"],
        dynamic_axes={
            "input": {0: "batch_size"},
            "output": {0: "batch_size"}
        }
    )
    print(f"Exported ONNX model to: {output_path}")


def export_to_torchscript(
    model: nn.Module,
    output_path: str,
    example_input: torch.Tensor = None
):
    """导出为 TorchScript 格式"""
    model.eval()
    
    if example_input is None:
        example_input = torch.randn(1, 3, 224, 224)
    
    # TorchScript 跟踪
    traced_model = torch.jit.trace(model, example_input)
    traced_model.save(output_path)
    print(f"Exported TorchScript model to: {output_path}")


def export_to_tflite(
    model: nn.Module,
    input_shape: tuple,
    output_path: str
):
    """导出为 TensorFlow Lite 格式（需要 ONNX 作为中间格式）"""
    import subprocess
    
    # 先导出 ONNX
    onnx_path = output_path.replace(".tflite", ".onnx")
    export_to_onnx(model, input_shape, onnx_path)
    
    # 使用 onnx-tflite 转换
    subprocess.run([
        "onnx-tflite",
        "--input", onnx_path,
        "--output", output_path
    ], check=True)
    print(f"Exported TFLite model to: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", type=str, required=True)
    parser.add_argument("--output-path", type=str, required=True)
    parser.add_argument("--format", choices=["onnx", "torchscript", "tflite"], default="onnx")
    parser.add_argument("--input-shape", type=int, nargs="+", default=[3, 224, 224])
    args = parser.parse_args()
    
    # 加载模型
    model = torch.load(args.model_path, map_location="cpu")
    if isinstance(model, dict):
        model = model["model_state_dict"]
    
    # 导出
    if args.format == "onnx":
        export_to_onnx(model, tuple(args.input_shape), args.output_path)
    elif args.format == "torchscript":
        export_to_torchscript(model, args.output_path)
    elif args.format == "tflite":
        export_to_tflite(model, tuple(args.input_shape), args.output_path)
```

---

## 技术栈与工具

### 框架与库

| 类别 | 工具 | 版本 | 用途 |
|------|------|------|------|
| 深度学习框架 | PyTorch | >=2.0 | 核心训练框架 |
| 深度学习框架 | TensorFlow | >=2.13 | 备选框架 |
| 分布式训练 | DeepSpeed | >=0.9 | 大规模训练加速 |
| 分布式训练 | Megatron-LM | latest | 超大规模模型训练 |
| 图像处理 | torchvision | >=0.15 | 预训练模型、数据集 |
| 图像增强 | albumentations | >=1.3 | 数据增强 |
| NLP | transformers | >=4.30 | Transformer 模型 |
| 图神经网络 | PyG | >=2.3 | GNN 模型 |
| 强化学习 | RLlib | >=2.0 | RL 训练 |
| AutoML | Optuna | >=3.0 | 超参数搜索 |
| 实验追踪 | MLflow | >=2.5 | 实验日志 |
| 实验追踪 | Weights & Biases | latest | 在线实验追踪 |
| 版本控制 | DVC | >=2.0 | 数据版本控制 |

### 开发工具

| 类别 | 工具 | 用途 |
|------|------|------|
| 环境管理 | conda/pipenv/poetry | 依赖管理 |
| 容器化 | Docker | 环境一致性 |
| 容器化 | NVIDIA Container Toolkit | GPU 支持 |
| 编排 | Kubernetes | 集群训练 |
| GPU 调度 | SLURM/PBS | HPC 调度 |
| 代码质量 | Black | 代码格式化 |
| 代码质量 | Ruff | Linting |
| 类型检查 | mypy | 静态类型检查 |
| 测试 | pytest | 单元测试 |
| 测试 | pytest-cov | 覆盖率 |

### 示例配置

```yaml
# configs/train_config.yaml
model:
  name: resnet50
  num_classes: 1000
  pretrained: true

data:
  data_dir: /data/imagenet
  image_size: 224
  batch_size: 256
  num_workers: 8

training:
  epochs: 90
  learning_rate: 0.001
  weight_decay: 0.0001
  optimizer: adamw
  scheduler: cosine
  warmup_epochs: 5
  use_amp: true
  gradient_clip: 1.0

distributed:
  backend: nccl
  world_size: 4

logging:
  experiment_name: resnet50_imagenet
  log_dir: ./logs
  save_interval: 1
  metrics:
    - accuracy
    - loss
    - learning_rate
```

---

## 输出格式

### 标准输出格式

每个任务完成后，AI/ML Engineer 必须输出以下内容：

```markdown
# ML Engineer Output

## 1. 任务总结

**模型类型**: [类型]  
**数据集**: [数据集名] ([N] samples)  
**训练配置**: [核心超参]

## 2. 性能指标

### 验证集结果
| Metric | Value |
|--------|-------|
| Accuracy | XX.XX% |
| Precision | XX.XX% |
| Recall | XX.XX% |
| F1 Score | XX.XX% |

### 训练曲线
[训练损失曲线图]  
[验证准确率曲线图]

## 3. 模型文件

| File | Description | Size |
|------|-------------|------|
| best.pt | 最佳检查点 | XX MB |
| latest.pt | 最新检查点 | XX MB |
| model.onnx | ONNX 导出 | XX MB |

## 4. 代码交付

```
ml_project/
├── src/
│   ├── data/
│   ├── models/
│   └── utils/
├── scripts/
│   ├── train.py
│   ├── evaluate.py
│   └── export.py
├── configs/
│   └── train_config.yaml
└── tests/
    └── test_model.py
```

## 5. 使用示例

```python
from src.models.factory import ModelFactory
import torch

# 加载模型
model = ModelFactory.create("resnet50", num_classes=1000)
checkpoint = torch.load("checkpoints/best.pt")
model.load_state_dict(checkpoint["model_state_dict"])
model.eval()

# 推理
with torch.no_grad():
    output = model(input_tensor)
```

## 6. 已知问题与限制

- [Issue 1]
- [Issue 2]
```

---

## 验证条件

### 代码质量验证

1. **语法检查**: 所有 Python 文件通过 `python -m py_compile`
2. **类型检查**: 通过 mypy 类型检查（无严重错误）
3. **Linting**: 通过 Ruff 检查（无 Error 级别问题）
4. **单元测试**: 所有核心模块通过 pytest 测试

### 模型验证

1. **训练可复现**: 相同 seed 的训练产生相似结果（<1% 差异）
2. **验证集达标**: 达到 Architect 指定的性能目标
3. **模型文件完整**: 所有检查点可正常加载
4. **导出格式正确**: ONNX/TorchScript 模型可正常推理

### 文档验证

1. **模型卡片完整**: 包含所有必填字段
2. **代码注释**: 关键函数有 docstring
3. **README 存在**: 项目根目录有使用说明

### 集成验证

1. **导入测试**: 所有模块可正常导入
2. **数据管道测试**: Dataset 和 DataLoader 正常工作
3. **训练脚本测试**: 训练脚本可在单 GPU 上运行一个 epoch
4. **评估脚本测试**: 评估脚本可在测试集上运行

---

## 熔断规则

| 条件 | 动作 | 恢复策略 |
|------|------|----------|
| 单个任务超时 >300s | 熔断当前任务 | 重试1次，降低batch size |
| 连续2次OOM | 熔断训练 | 减小模型规模，清理缓存 |
| 3次实验失败 | 熔断实验 | 重新评估任务可行性 |
| 梯度爆炸/消失 | 自动检测停止 | 降低学习率，检查初始化 |

---

_Last updated: 2026-04-18_
