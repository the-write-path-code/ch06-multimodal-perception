# Section 6.1: Tabular Extractor

import os
import hashlib
from typing import List, Dict, Any
import pandas as pd
from ch6.logging import logger, ctx_source_file, ctx_modality, ctx_pipeline_stage
from ch6.models import PerceptionChunk, ModalityType
from ch6.perception.sensitivity import SensitivityScanner

class TableExtractor:
    """Profiles tabular data files (CSV/Excel) and generates descriptive natural language metadata summaries."""

    def __init__(self) -> None:
        self.sensitivity_scanner = SensitivityScanner()

    def _generate_chunk_id(self, filepath: str) -> str:
        """Generates unique chunk ID from file path."""
        return hashlib.md5(filepath.encode()).hexdigest()

    async def extract(self, file_path: str) -> List[PerceptionChunk]:
        """Loads a spreadsheet table, profiles columns/statistics, and yields a grounded chunk."""
        ctx_source_file.set(os.path.basename(file_path))
        ctx_modality.set("table")
        ctx_pipeline_stage.set("extraction")

        logger.info("Starting tabular data profiling", file=file_path)

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Table file not found: {file_path}")

        try:
            # Load file based on extension
            _, ext = os.path.splitext(file_path.lower())
            if ext in [".xls", ".xlsx"]:
                df = pd.read_excel(file_path)
            else:
                df = pd.read_csv(file_path)

            row_count, col_count = df.shape
            columns = list(df.columns)
            dtypes = {col: str(dtype) for col, dtype in df.dtypes.items()}

            # Profile columns (null rates, numeric stats, top categoricals)
            null_rates = df.isnull().mean().to_dict()
            profile_stats: Dict[str, Any] = {}

            for col in df.columns:
                col_profile: Dict[str, Any] = {
                    "dtype": str(df[col].dtype),
                    "null_rate": float(null_rates[col])
                }
                
                # Numeric stats
                if pd.api.types.is_numeric_dtype(df[col]):
                    col_profile["min"] = float(df[col].min()) if not df[col].isnull().all() else None
                    col_profile["max"] = float(df[col].max()) if not df[col].isnull().all() else None
                    col_profile["mean"] = float(df[col].mean()) if not df[col].isnull().all() else None
                else:
                    # Categorical top values
                    top_vals = df[col].value_counts().head(3).to_dict()
                    col_profile["top_values"] = {str(k): int(v) for k, v in top_vals.items()}

                profile_stats[col] = col_profile

            # 2. Programmatically compile natural-language summary anchor
            nl_summary = (
                f"Tabular dataset: {os.path.basename(file_path)}\n"
                f"Dimensions: {row_count} rows by {col_count} columns.\n"
                f"Schema fields: {', '.join(columns)}.\n\n"
                "Profile Details:\n"
            )
            for col, stats in profile_stats.items():
                nl_summary += f"- Column '{col}' ({stats['dtype']}): Null Rate={stats['null_rate']:.1%}"
                if "mean" in stats and stats["mean"] is not None:
                    nl_summary += f", Mean={stats['mean']:.2f}, Range=[{stats['min']:.2f}, {stats['max']:.2f}]"
                elif "top_values" in stats and stats["top_values"]:
                    nl_summary += f", Top values: {stats['top_values']}"
                nl_summary += "\n"

            # 3. Check for PII inside data sample summary
            meta = {
                "layout_type": "tabular_profile",
                "row_count": row_count,
                "col_count": col_count,
                "pii_detected": False
            }
            
            detected_pii = self.sensitivity_scanner.scan_for_pii(nl_summary)
            if detected_pii:
                meta["pii_detected"] = True
                meta["pii_labels"] = detected_pii
                nl_summary = self.sensitivity_scanner.redact_pii(nl_summary)

            # Store first 10 rows in structured data as preview
            preview_rows = df.head(10).to_dict(orient="records")
            structured_data = {
                "row_count": row_count,
                "col_count": col_count,
                "columns": columns,
                "dtypes": dtypes,
                "profile": profile_stats,
                "preview_rows": preview_rows
            }

            chunk = PerceptionChunk(
                chunk_id=self._generate_chunk_id(file_path),
                modality=ModalityType.TABLE,
                source_file=file_path,
                confidence=1.0,
                content_text=nl_summary,
                structured_data=structured_data,
                metadata=meta
            )

            logger.info("Completed tabular profiling", columns=col_count, rows=row_count)
            return [chunk]

        except Exception as e:
            logger.error("Failed tabular profiling on file", error=str(e))
            return []
