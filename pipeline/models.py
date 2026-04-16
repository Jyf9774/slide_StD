"""
数据模型定义
Data Models for Slide Pipeline

包含所有数据结构：ElementType, BoundingBox, SlideElement, SlideMetadata
"""

from dataclasses import dataclass, field
from typing import List, Dict
from enum import Enum
from datetime import datetime


class ElementType(Enum):
    """元素类型枚举"""
    TEXT = "text"
    IMAGE = "image"
    CHART = "chart"
    TABLE = "table"
    DIAGRAM = "diagram"
    LOGO = "logo"
    DECORATION = "decoration"
    MIXED = "mixed"
    UNKNOWN = "unknown"


@dataclass
class BoundingBox:
    """边界框数据结构"""
    x: int
    y: int
    width: int
    height: int

    @property
    def x2(self) -> int:
        return self.x + self.width

    @property
    def y2(self) -> int:
        return self.y + self.height

    @property
    def area(self) -> int:
        return self.width * self.height

    def to_dict(self) -> Dict:
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}


@dataclass
class SlideElement:
    """幻灯片元素数据结构"""
    id: str
    name: str
    type: ElementType
    bbox: BoundingBox
    image_path: str
    text_content: str = ""
    confidence: float = 0.0
    is_title: bool = False
    description: str = ""
    z_order: int = 0

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "bbox": self.bbox.to_dict(),
            "image_path": self.image_path,
            "text_content": self.text_content,
            "confidence": self.confidence,
            "is_title": self.is_title,
            "description": self.description,
            "z_order": self.z_order
        }


@dataclass
class SlideMetadata:
    """幻灯片元数据结构"""
    slide_id: str
    source_image: str
    width: int
    height: int
    background_color: str
    element_count: int
    elements: List[SlideElement]
    title: str = ""
    description: str = ""
    key_points: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    version: str = "4.0"

    def to_dict(self) -> Dict:
        return {
            "slide_id": self.slide_id,
            "source_image": self.source_image,
            "width": self.width,
            "height": self.height,
            "background_color": self.background_color,
            "element_count": self.element_count,
            "elements": [e.to_dict() for e in self.elements],
            "title": self.title,
            "description": self.description,
            "key_points": self.key_points,
            "created_at": self.created_at,
            "version": self.version
        }
