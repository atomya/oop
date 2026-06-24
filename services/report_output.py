import csv
import json
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path

from shared.exceptions import InvalidOperationError
from utils.validation import require_non_empty_string


class ReportValueSerializer:
    @staticmethod
    def serialize(value):
        if isinstance(value, Decimal):
            return format(value, "f")
        if isinstance(value, datetime):
            return value.isoformat(timespec="seconds")
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, dict):
            return {
                str(key): ReportValueSerializer.serialize(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [ReportValueSerializer.serialize(item) for item in value]
        return value

    @staticmethod
    def format_scalar(value) -> str:
        serialized_value = ReportValueSerializer.serialize(value)
        if isinstance(serialized_value, (dict, list)):
            return json.dumps(serialized_value, ensure_ascii=True)
        return str(serialized_value)

    @staticmethod
    def flatten_for_csv(value, path: str = "") -> list[tuple[str, str]]:
        if isinstance(value, dict):
            if not value:
                return [(path, "{}")]
            rows = []
            for key, item in value.items():
                next_path = f"{path}.{key}" if path else str(key)
                rows.extend(ReportValueSerializer.flatten_for_csv(item, next_path))
            return rows

        if isinstance(value, list):
            if not value:
                return [(path, "[]")]
            rows = []
            for index, item in enumerate(value):
                next_path = f"{path}[{index}]"
                rows.extend(ReportValueSerializer.flatten_for_csv(item, next_path))
            return rows

        return [(path, ReportValueSerializer.format_scalar(value))]

    @staticmethod
    def normalize_path_input(path_value, label: str) -> Path:
        if isinstance(path_value, Path):
            return path_value
        return Path(require_non_empty_string(path_value, label))


class TextReportFormatter:
    def format(self, report: dict) -> str:
        if not isinstance(report, dict) or "report_type" not in report:
            raise InvalidOperationError("Report must be a dictionary produced by ReportBuilder")

        lines = [
            report["report_title"],
            f"type: {report['report_type']}",
            f"generated_at: {ReportValueSerializer.format_scalar(report['generated_at'])}",
        ]
        if "scope" in report:
            lines.append(f"scope: {report['scope']}")

        for section_name, section_value in report.items():
            if section_name in {"report_title", "report_type", "generated_at", "scope"}:
                continue
            lines.extend(self._format_section(section_name, section_value, indent=0))

        return "\n".join(lines)

    def _format_section(self, name: str, value, *, indent: int) -> list[str]:
        prefix = " " * indent
        title = f"{prefix}{name}:"

        if isinstance(value, dict):
            lines = [title]
            for key, item in value.items():
                if isinstance(item, (dict, list)):
                    lines.extend(self._format_section(str(key), item, indent=indent + 2))
                else:
                    lines.append(f"{' ' * (indent + 2)}{key}: {ReportValueSerializer.format_scalar(item)}")
            return lines

        if isinstance(value, list):
            lines = [f"{title} count={len(value)}"]
            for index, item in enumerate(value[:10], start=1):
                if isinstance(item, dict):
                    lines.append(f"{' ' * (indent + 2)}[{index}]")
                    for key, nested_value in item.items():
                        lines.append(f"{' ' * (indent + 4)}{key}: {ReportValueSerializer.format_scalar(nested_value)}")
                else:
                    lines.append(f"{' ' * (indent + 2)}[{index}] {ReportValueSerializer.format_scalar(item)}")
            if len(value) > 10:
                lines.append(f"{' ' * (indent + 2)}... truncated ...")
            return lines

        return [f"{title} {ReportValueSerializer.format_scalar(value)}"]


class JsonReportExporter:
    def export(self, report: dict, file_path) -> Path:
        if not isinstance(report, dict):
            raise InvalidOperationError("Report must be a dictionary")

        target_path = ReportValueSerializer.normalize_path_input(file_path, "JSON file path")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with target_path.open("w", encoding="utf-8") as file:
            json.dump(ReportValueSerializer.serialize(report), file, ensure_ascii=True, indent=2)
        return target_path


class CsvReportExporter:
    def export(self, report: dict, file_path) -> Path:
        if not isinstance(report, dict):
            raise InvalidOperationError("Report must be a dictionary")

        target_path = ReportValueSerializer.normalize_path_input(file_path, "CSV file path")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        rows = ReportValueSerializer.flatten_for_csv(ReportValueSerializer.serialize(report))
        with target_path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["path", "value"])
            writer.writerows(rows)
        return target_path
