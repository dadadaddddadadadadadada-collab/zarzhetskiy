from dataclasses import dataclass, field, asdict
from datetime import datetime

from models.block import ScriptBlock


@dataclass
class Scenario:
    title: str
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M"))
    updated_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M"))
    template_name: str = ""
    blocks: list[ScriptBlock] = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["blocks"] = [block.to_dict() for block in self.blocks]
        return data

    @staticmethod
    def from_dict(data: dict) -> "Scenario":
        blocks = [ScriptBlock.from_dict(block_data) for block_data in data.get("blocks", [])]

        return Scenario(
            title=data.get("title", "Новый сценарий"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            template_name=data.get("template_name", ""),
            blocks=blocks,
        )

    def update_time(self):
        self.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M")