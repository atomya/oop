from decimal import Decimal
from pathlib import Path
from typing import Any

from shared.exceptions import InvalidOperationError
from utils.validation import require_non_empty_string


class MatplotlibChartRenderer:
    def __init__(self, pyplot_loader=None):
        self._pyplot_loader = pyplot_loader or self._import_pyplot

    @staticmethod
    def _import_pyplot():
        try:
            import matplotlib

            matplotlib.use("Agg")
            from matplotlib import pyplot as plt
        except ModuleNotFoundError as error:
            raise InvalidOperationError("matplotlib is required to save charts") from error
        return plt

    @staticmethod
    def _normalize_output_dir(path_value) -> Path:
        if isinstance(path_value, Path):
            return path_value
        return Path(require_non_empty_string(path_value, "Charts output directory"))

    @staticmethod
    def _normalize_chart_values(values: list[Any]) -> list[float]:
        normalized_values = []
        for value in values:
            if isinstance(value, Decimal):
                normalized_values.append(float(value))
            else:
                normalized_values.append(float(value))
        return normalized_values

    def save(self, charts: list[dict], output_dir) -> list[Path]:
        if not isinstance(charts, list):
            raise InvalidOperationError("Charts must be a list")

        target_dir = self._normalize_output_dir(output_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        plt = self._pyplot_loader()
        saved_paths: list[Path] = []

        for chart in charts:
            chart_type = chart["chart_type"]
            figure, axis = plt.subplots(figsize=(8, 5))

            if chart_type == "pie":
                values = self._normalize_chart_values(chart["values"])
                if not any(values):
                    values = [1.0]
                axis.pie(values, labels=chart["labels"], autopct="%1.1f%%")
            elif chart_type == "bar":
                values = self._normalize_chart_values(chart["values"])
                axis.bar(chart["labels"], values, color="#4C78A8")
                axis.set_ylabel(chart.get("y_label", "Value"))
                axis.tick_params(axis="x", rotation=30)
            elif chart_type == "line":
                values = self._normalize_chart_values(chart["values"])
                axis.plot(chart["x_labels"], values, marker="o", color="#F58518")
                axis.set_ylabel(chart.get("y_label", "Value"))
                axis.tick_params(axis="x", rotation=30)
            else:
                plt.close(figure)
                raise InvalidOperationError(f"Unsupported chart type: {chart_type}")

            axis.set_title(chart["title"])
            figure.tight_layout()
            output_path = target_dir / chart["filename"]
            figure.savefig(output_path)
            plt.close(figure)
            saved_paths.append(output_path)

        return saved_paths
