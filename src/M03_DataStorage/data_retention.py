"""
data_retention.py
Подмодуль 2.3.4 Data Retention / Purge Policy (боевой).

Отвечает за:
- очистку старых данных по политикам retention;
- соблюдение лимитов по размеру;
- работу в связке с конфигом ITA (config.yaml);
- формирование отчёта по очистке.

НЕ:
- не трогает бизнес-логику стратегий;
- не изменяет правила и снапшоты напрямую;
- не запускает оркестрацию (только сервис, который вызывают другие модули).

Основано на:
- ITA_TZ_03_DataStorage_2.3.4_DataRetention_PurgePolicy_v1.0
- ITA Development Guidelines
- ITA_modules_v1.1 (M03_DataStorage)
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml  # type: ignore

logger = logging.getLogger("ita.M03_DataStorage.data_retention")
logger.addHandler(logging.NullHandler())


# ===========================
# Вспомогательные структуры
# ===========================


@dataclass
class RetentionPolicy:
    ttl_days: int
    max_gb: Optional[float] = None


@dataclass
class RetentionItemReport:
    data_type: str
    dir: str
    total_files_scanned: int
    candidates: int
    protected_skipped: int
    deleted: int
    freed_bytes: int


# ===========================
# Работа с конфигом
# ===========================


def _get_project_root() -> Path:
    """
    Корень проекта ITA_01.
    Ожидаем:
      <root>/
        configs/config.yaml
        src/M03_DataStorage/data_retention.py
    """
    return Path(__file__).resolve().parents[2]


def _load_config() -> Dict[str, Any]:
    root = _get_project_root()
    cfg_path = root / "configs" / "config.yaml"

    if not cfg_path.exists():
        logger.warning("config.yaml not found for DataRetention, using safe defaults")
        # Без конфига модуль работает в режиме "ничего не удалять"
        return {
            "paths": {
                "data_root": "data/",
                "cache_root": "data/cache/",
                "archive_root": "data/archive/",
                "results_root": "data/results/",
                "logs_root": "logs/",
                "temp_root": "data/temp/",
            },
            "results": {
                "backtests_path": "data/results/backtests",
                "analytics_path": "data/results/analytics",
                "provenance_path": "data/results/provenance",
                "rules_path": "data/rules",
                "retention_reports_path": "data/results/retention",
            },
            "retention": {
                "enabled": False,
                "policies": {},
                "disk_limits": {},
            },
        }

    with cfg_path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    # Минимальные значения по умолчанию
    paths = cfg.setdefault("paths", {})
    paths.setdefault("data_root", "data/")
    paths.setdefault("cache_root", "data/cache/")
    paths.setdefault("archive_root", "data/archive/")
    paths.setdefault("results_root", "data/results/")
    paths.setdefault("logs_root", "logs/")
    paths.setdefault("temp_root", "data/temp/")
    paths.setdefault("analytics_root", "data/results/analytics/")
    paths.setdefault("backtests_root", "data/results/backtests/")

    results = cfg.setdefault("results", {})
    results.setdefault("backtests_path", "data/results/backtests")
    results.setdefault("analytics_path", "data/results/analytics")
    results.setdefault("provenance_path", "data/results/provenance")
    results.setdefault("rules_path", "data/rules")
    results.setdefault("retention_reports_path", "data/results/retention")

    retention = cfg.setdefault("retention", {})
    retention.setdefault("enabled", True)
    retention.setdefault("policies", {})
    retention.setdefault("disk_limits", {})

    return cfg


def _resolve_path(root: Path, path_str: str) -> Path:
    """
    Преобразует путь из конфига в абсолютный Path.
    Если путь относительный — считаем его относительно корня проекта.
    """
    p = Path(path_str)
    if p.is_absolute():
        return p
    return root / p


# ===========================
# Основной сервис
# ===========================


class DataRetentionService:
    """
    Боевой сервис управления хранением данных (2.3.4 Data Retention / Purge Policy).

    Публичные методы:
    - purge(data_type, dry_run=None) -> dict
    - purge_all(dry_run=None) -> dict
    - enforce_disk_limits(dry_run=None) -> dict
    - get_protected_files() -> set[str]
    """

    def __init__(self, dry_run_default: bool = True) -> None:
        self._project_root = _get_project_root()
        self._config = _load_config()
        self._dry_run_default = dry_run_default

        retention_cfg = self._config.get("retention", {})
        self._enabled: bool = bool(retention_cfg.get("enabled", True))

        self._policies_raw: Dict[str, Dict[str, Any]] = retention_cfg.get("policies", {})
        self._disk_limits_raw: Dict[str, Dict[str, Any]] = retention_cfg.get(
            "disk_limits", {}
        )

        self._paths_cfg = self._config.get("paths", {})
        self._results_cfg = self._config.get("results", {})

        # Кеш путей по типам данных
        self._type_to_dir: Dict[str, Path] = self._build_type_mapping()

    # -----------------------
    # Внутренние маппинги
    # -----------------------

    def _build_type_mapping(self) -> Dict[str, Path]:
        """
        Формирует отображение логического типа данных (cache, archive, backtests, analytics, temp)
        в директорию на диске.
        """
        root = self._project_root

        mapping: Dict[str, Path] = {}

        # cache → paths.cache_root
        cache_root = self._paths_cfg.get("cache_root", "data/cache/")
        mapping["cache"] = _resolve_path(root, cache_root)

        # archive → paths.archive_root
        archive_root = self._paths_cfg.get("archive_root", "data/archive/")
        mapping["archive"] = _resolve_path(root, archive_root)

        # backtests → results.backtests_path или paths.backtests_root
        backtests_path = self._results_cfg.get(
            "backtests_path", self._paths_cfg.get("backtests_root", "data/results/backtests/")
        )
        mapping["backtests"] = _resolve_path(root, backtests_path)

        # analytics → results.analytics_path или paths.analytics_root
        analytics_path = self._results_cfg.get(
            "analytics_path",
            self._paths_cfg.get("analytics_root", "data/results/analytics/"),
        )
        mapping["analytics"] = _resolve_path(root, analytics_path)

        # temp → paths.temp_root
        temp_root = self._paths_cfg.get("temp_root", "data/temp/")
        mapping["temp"] = _resolve_path(root, temp_root)

        return mapping

    def _get_policy(self, data_type: str) -> RetentionPolicy:
        raw = self._policies_raw.get(data_type)
        if not raw:
            raise ValueError(
                f"Retention policy for data_type='{data_type}' not found in config.retention.policies"
            )

        ttl = raw.get("ttl_days")
        if ttl is None:
            raise ValueError(
                f"Retention policy for data_type='{data_type}' must define ttl_days"
            )

        max_gb_raw = raw.get("max_gb")
        max_gb = float(max_gb_raw) if max_gb_raw is not None else None
        return RetentionPolicy(ttl_days=int(ttl), max_gb=max_gb)

    def _get_disk_limit_gb(self, data_type: str) -> Optional[float]:
        cfg = self._disk_limits_raw.get(data_type)
        if not cfg:
            return None
        val = cfg.get("max_gb")
        if val is None:
            return None
        return float(val)

    # -----------------------
    # Protected files
    # -----------------------

    def get_protected_files(self) -> Set[str]:
        """
        Возвращает множество файлов, которые не должны удаляться.

        На этом этапе реализация консервативная:
        - ВСЕ файлы из:
          - results.provenance_path (RunSnapshot)
          - results.rules_path (RuleVersionRegistry)
        """
        protected: Set[str] = set()
        root = self._project_root

        provenance_dir_str = self._results_cfg.get(
            "provenance_path", "data/results/provenance"
        )
        rules_dir_str = self._results_cfg.get("rules_path", "data/rules")

        for dir_str in (provenance_dir_str, rules_dir_str):
            base = _resolve_path(root, dir_str)
            if not base.exists():
                continue

            for dirpath, _, filenames in os.walk(base):
                for name in filenames:
                    full_path = Path(dirpath) / name
                    protected.add(str(full_path.resolve()))

        return protected

    # -----------------------
    # Вспомогательные методы
    # -----------------------

    @staticmethod
    def _file_age_days(path: Path) -> float:
        """
        Возраст файла в днях (по mtime).
        """
        stat = path.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = now - mtime
        return delta.total_seconds() / 86400.0

    @staticmethod
    def _file_size_bytes(path: Path) -> int:
        try:
            return path.stat().st_size
        except OSError:
            return 0

    def _scan_files(self, base_dir: Path) -> List[Path]:
        """
        Возвращает список всех файлов (рекурсивно) в директории.
        """
        results: List[Path] = []
        if not base_dir.exists():
            return results

        for dirpath, _, filenames in os.walk(base_dir):
            for name in filenames:
                p = Path(dirpath) / name
                results.append(p)
        return results

    # -----------------------
    # Основной метод purge
    # -----------------------

    def purge(
        self,
        data_type: str,
        dry_run: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Очистка файлов для одного логического типа данных (cache, archive, backtests, analytics, temp).

        Использует:
        - config.retention.enabled
        - config.retention.policies[data_type].ttl_days

        Возвращает отчёт формата:
        {
          "dry_run": bool,
          "mode": "purge",
          "data_type": "...",
          "items": [RetentionItemReport as dict],
          "total_freed_bytes": int
        }
        """
        if dry_run is None:
            dry_run = self._dry_run_default

        if not self._enabled:
            logger.info(
                "DataRetention is disabled in config.retention.enabled; skipping purge for '%s'",
                data_type,
            )
            return {
                "dry_run": dry_run,
                "mode": "purge",
                "data_type": data_type,
                "items": [],
                "total_freed_bytes": 0,
                "note": "retention disabled",
            }

        base_dir = self._type_to_dir.get(data_type)
        if base_dir is None:
            raise ValueError(f"Unknown data_type for purge: '{data_type}'")

        policy = self._get_policy(data_type)
        logger.info(
            "Running purge for data_type=%s, dir=%s, ttl_days=%s, dry_run=%s",
            data_type,
            base_dir,
            policy.ttl_days,
            dry_run,
        )

        files = self._scan_files(base_dir)
        total_files = len(files)

        protected = self.get_protected_files()
        candidates: List[Path] = []
        protected_skipped = 0

        for p in files:
            age = self._file_age_days(p)
            if age <= policy.ttl_days:
                continue

            p_resolved = str(p.resolve())
            if p_resolved in protected:
                protected_skipped += 1
                continue

            candidates.append(p)

        deleted = 0
        freed_bytes = 0

        if not dry_run:
            for p in candidates:
                size = self._file_size_bytes(p)
                try:
                    p.unlink()
                    deleted += 1
                    freed_bytes += size
                    logger.info("Deleted (TTL): %s (%d bytes)", p, size)
                except OSError as exc:  # не падаем на одном файле
                    logger.warning("Failed to delete %s: %s", p, exc)

        item_report = RetentionItemReport(
            data_type=data_type,
            dir=str(base_dir),
            total_files_scanned=total_files,
            candidates=len(candidates),
            protected_skipped=protected_skipped,
            deleted=deleted if not dry_run else 0,
            freed_bytes=freed_bytes if not dry_run else 0,
        )

        report = {
            "dry_run": dry_run,
            "mode": "purge",
            "data_type": data_type,
            "items": [item_report.__dict__],
            "total_freed_bytes": item_report.freed_bytes,
        }

        self._save_report(report, mode="purge", data_type=data_type)
        return report

    # -----------------------
    # purge_all
    # -----------------------

    def purge_all(self, dry_run: Optional[bool] = None) -> Dict[str, Any]:
        """
        Запускает purge для всех типов данных, у которых есть политики в config.retention.policies.
        """
        if dry_run is None:
            dry_run = self._dry_run_default

        if not self._enabled:
            logger.info(
                "DataRetention is disabled; skipping purge_all"
            )
            return {
                "dry_run": dry_run,
                "mode": "purge_all",
                "items": [],
                "total_freed_bytes": 0,
                "note": "retention disabled",
            }

        items: List[Dict[str, Any]] = []
        total_freed = 0

        for data_type in self._policies_raw.keys():
            sub_report = self.purge(data_type, dry_run=dry_run)
            items.extend(sub_report.get("items", []))
            total_freed += int(sub_report.get("total_freed_bytes", 0))

        report = {
            "dry_run": dry_run,
            "mode": "purge_all",
            "items": items,
            "total_freed_bytes": total_freed,
        }

        self._save_report(report, mode="purge_all")
        return report

    # -----------------------
    # enforce_disk_limits
    # -----------------------

    def enforce_disk_limits(self, dry_run: Optional[bool] = None) -> Dict[str, Any]:
        """
        Приводит размер директорий к max_gb, если указано в retention.disk_limits.
        Работает по принципу: удаляем самые старые файлы, пока не уложимся в лимит.
        """
        if dry_run is None:
            dry_run = self._dry_run_default

        if not self._enabled:
            logger.info("DataRetention is disabled; skipping enforce_disk_limits")
            return {
                "dry_run": dry_run,
                "mode": "enforce_limits",
                "items": [],
                "total_freed_bytes": 0,
                "note": "retention disabled",
            }

        protected = self.get_protected_files()
        items: List[RetentionItemReport] = []
        total_freed = 0

        for data_type, limit_cfg in self._disk_limits_raw.items():
            max_gb_raw = limit_cfg.get("max_gb")
            if max_gb_raw is None:
                continue

            max_bytes = int(float(max_gb_raw) * (1024**3))
            base_dir = self._type_to_dir.get(data_type)
            if base_dir is None:
                continue

            files = self._scan_files(base_dir)
            total_files = len(files)

            # сортируем по времени изменения (старые → новые)
            files_sorted = sorted(
                files,
                key=lambda p: p.stat().st_mtime,
            )

            # вычисляем текущий размер
            current_size = sum(self._file_size_bytes(p) for p in files_sorted)

            if current_size <= max_bytes:
                items.append(
                    RetentionItemReport(
                        data_type=data_type,
                        dir=str(base_dir),
                        total_files_scanned=total_files,
                        candidates=0,
                        protected_skipped=0,
                        deleted=0,
                        freed_bytes=0,
                    )
                )
                continue

            candidates: List[Path] = []
            protected_skipped = 0
            freed_here = 0
            deleted_here = 0

            for p in files_sorted:
                if current_size <= max_bytes:
                    break

                p_resolved = str(p.resolve())
                if p_resolved in protected:
                    protected_skipped += 1
                    continue

                size = self._file_size_bytes(p)
                candidates.append(p)

                if not dry_run:
                    try:
                        p.unlink()
                        deleted_here += 1
                        freed_here += size
                        current_size -= size
                        logger.info(
                            "Deleted (limit): %s (%d bytes), data_type=%s",
                            p,
                            size,
                            data_type,
                        )
                    except OSError as exc:
                        logger.warning("Failed to delete %s: %s", p, exc)
                else:
                    # в dry_run мы только моделируем
                    freed_here += size
                    current_size -= size

            item_report = RetentionItemReport(
                data_type=data_type,
                dir=str(base_dir),
                total_files_scanned=total_files,
                candidates=len(candidates),
                protected_skipped=protected_skipped,
                deleted=deleted_here if not dry_run else 0,
                freed_bytes=freed_here if not dry_run else 0,
            )
            items.append(item_report)
            total_freed += item_report.freed_bytes

        report = {
            "dry_run": dry_run,
            "mode": "enforce_limits",
            "items": [it.__dict__ for it in items],
            "total_freed_bytes": total_freed,
        }

        self._save_report(report, mode="enforce_limits")
        return report

    # -----------------------
    # Сохранение отчётов
    # -----------------------

    def _get_reports_dir(self) -> Path:
        reports_dir_str = self._results_cfg.get(
            "retention_reports_path", "data/results/retention"
        )
        reports_dir = _resolve_path(self._project_root, reports_dir_str)
        reports_dir.mkdir(parents=True, exist_ok=True)
        return reports_dir

    def _save_report(
        self,
        report: Dict[str, Any],
        mode: str,
        data_type: Optional[str] = None,
    ) -> None:
        """
        Сохраняет отчёт об очистке в JSON:
        data/results/retention/retention_<mode>_<data_type?>_<timestamp>.json
        """
        try:
            reports_dir = self._get_reports_dir()
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

            suffix = f"_{data_type}" if data_type else ""
            filename = f"retention_{mode}{suffix}_{ts}.json"

            path = reports_dir / filename
            with path.open("w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)

            logger.info("Retention report saved: %s", path)
        except Exception as exc:  # noqa: BLE001
            # отчёт не критичен для основной логики
            logger.warning("Failed to save retention report: %s", exc)
