import json
from pathlib import Path

from models.scenario import Scenario
from models.template import ScenarioTemplate


class FileStorage:
    @staticmethod
    def save_scenario(scenario: Scenario, file_path: str):
        scenario.update_time()

        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w", encoding="utf-8") as file:
            json.dump(scenario.to_dict(), file, ensure_ascii=False, indent=4)

    @staticmethod
    def load_scenario(file_path: str) -> Scenario:
        path = Path(file_path)

        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        return Scenario.from_dict(data)

    @staticmethod
    def save_template(template: ScenarioTemplate, file_path: str):
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w", encoding="utf-8") as file:
            json.dump(template.to_dict(), file, ensure_ascii=False, indent=4)

    @staticmethod
    def load_template(file_path: str) -> ScenarioTemplate:
        path = Path(file_path)

        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        return ScenarioTemplate.from_dict(data)