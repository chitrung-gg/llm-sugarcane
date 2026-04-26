import functools
from typing import Any, Callable, Literal, Optional, ParamSpec, TypeVar, cast
from langfuse import observe
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

from app.common.constants import ObservationType

P = ParamSpec("P")
R = TypeVar("R")

_LANGFUSE_AS_TYPE = Literal[
    "span",
    "generation",
    "embedding",
    "agent",
    "tool",
    "chain",
    "retriever",
    "evaluator",
    "guardrail",
]

def tracing(
    _func: Optional[Callable[P, R]] = None,
    *,
    span_name: Optional[str] = None,
    observation_type: ObservationType = ObservationType.SPAN
) -> Any:
    """
    Unified decorator that wraps Langfuse's @observe.
    This prevents duplication by using the native Langfuse engine while 
    allowing custom span naming and observation types (span, tool, retriever, etc.)
    """
    def decorator(func):
        # We use langfuse.observe to handle the heavy lifting.
        # as_type maps to Langfuse UI categories (retriever, tool, generation, etc.)

        node_name = span_name or func.__name__
        # @observe(
        #     name=span_name or func.__name__, 
        #     as_type=cast(_LANGFUSE_AS_TYPE, observation_type.value)
        # )
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            with tracer.start_as_current_span(f"node.{node_name}.observation_type.{observation_type.value}"):
                return await func(*args, **kwargs)
        return wrapper

    if _func is not None and callable(_func):
        return decorator(_func)

    return decorator