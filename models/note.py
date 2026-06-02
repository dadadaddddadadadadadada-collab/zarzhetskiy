from dataclasses import dataclass, asdict


@dataclass
class Note:
    id: int
    text: str
    color: str = "#FFD966"
    line_index: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "Note":
        return Note(
            id=data.get("id", 0),
            text=data.get("text", ""),
            color=data.get("color", "#FFD966"),
            line_index=data.get("line_index", 0),
        )