from dataclasses import dataclass, field, asdict
from models.note import Note


@dataclass
class ScriptBlock:
    id: int
    title: str
    order_index: int
    text: str = ""
    color: str = "#FFFFFF"
    hint: str = ""
    notes: list[Note] = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["notes"] = [note.to_dict() for note in self.notes]
        return data

    @staticmethod
    def from_dict(data: dict) -> "ScriptBlock":
        notes = [Note.from_dict(note_data) for note_data in data.get("notes", [])]

        return ScriptBlock(
            id=data.get("id", 0),
            title=data.get("title", "Без названия"),
            order_index=data.get("order_index", 0),
            text=data.get("text", ""),
            color=data.get("color", "#FFFFFF"),
            hint=data.get("hint", ""),
            notes=notes,
        )