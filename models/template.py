from dataclasses import dataclass, field, asdict


@dataclass
class TemplateBlock:
    title: str
    order_index: int
    color: str = "#FFFFFF"
    hint: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "TemplateBlock":
        return TemplateBlock(
            title=data.get("title", "Без названия"),
            order_index=data.get("order_index", 0),
            color=data.get("color", "#FFFFFF"),
            hint=data.get("hint", ""),
        )


@dataclass
class ScenarioTemplate:
    title: str
    blocks: list[TemplateBlock] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "blocks": [block.to_dict() for block in self.blocks],
        }

    @staticmethod
    def from_dict(data: dict) -> "ScenarioTemplate":
        blocks = [
            TemplateBlock.from_dict(block_data)
            for block_data in data.get("blocks", [])
        ]

        return ScenarioTemplate(
            title=data.get("title", "Новый шаблон"),
            blocks=blocks,
        )