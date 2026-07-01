# Section 6.1: Structured Perception Auditing & Logging

import logging
import sys
from contextvars import ContextVar
from typing import Any, Dict
import structlog
from structlog.types import EventDict, WrappedLogger

# ContextVars to carry correlation context across async task boundaries
ctx_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="sys-init")
ctx_modality: ContextVar[str] = ContextVar("modality", default="general")
ctx_source_file: ContextVar[str] = ContextVar("source_file", default="unknown")
ctx_pipeline_stage: ContextVar[str] = ContextVar("pipeline_stage", default="startup")

def inject_context_vars(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Processor to inject ContextVar tracing identifiers to every structlog record."""
    event_dict["correlation_id"] = ctx_correlation_id.get()
    event_dict["modality"] = ctx_modality.get()
    event_dict["source_file"] = ctx_source_file.get()
    event_dict["pipeline_stage"] = ctx_pipeline_stage.get()
    return event_dict

def configure_logger(level: int = logging.INFO) -> None:
    """Configures structured JSON logging with thread/task-local tracing variables."""
    # Standard library handler configuration
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(level)

    # Configure structlog processors pipeline
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            inject_context_vars,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

# Run initial config on load
configure_logger()
logger = structlog.get_logger("ch6")
