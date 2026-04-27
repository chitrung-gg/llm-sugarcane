import functools
from typing import Any, Callable, Literal, Optional, ParamSpec, TypeVar, cast
from langfuse import observe, get_client
from opentelemetry import trace

from app.common.constants import ObservationType

tracer = trace.get_tracer(__name__)

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

import inspect
from functools import wraps
from typing import Any, Callable, Optional
from langchain_core.runnables import RunnableConfig
from opentelemetry import trace
from langfuse import get_client

from app.common.constants import ObservationType

tracer = trace.get_tracer(__name__)

def tracing(
    _func: Optional[Callable[P, R]] = None,
    *,
    span_name: Optional[str] = None, 
    observation_type: ObservationType = ObservationType.SPAN
):
    """
    A Langfuse v3 / OpenTelemetry compliant decorator for LangGraph nodes.
    Automatically nests under the graph's active trace and spreads context safely.
    """
    def decorator(func: Callable):
        node_name = span_name or func.__name__

        @wraps(func)
        async def async_wrapper(state: Any, *args, **kwargs):
            # Because config["callbacks"] contains the Langfuse handler,
            # OpenTelemetry context is already active here. We just nest a new span!
            with tracer.start_as_current_span(node_name) as span:
                
                # Customize the Langfuse rendering type
                span.set_attribute("langfuse.object.type", observation_type.value)
                
                # (Optional) Tie the OTel ID to Langfuse metadata for easy searching
                span_context = span.get_span_context()
                if span_context.is_valid:
                    langfuse = get_client()
                    langfuse.update_current_span(
                        metadata={"otel_span_id": format(span_context.span_id, "016x")}
                    )

                # Execute the node
                result = func(state, *args, **kwargs)
                if inspect.isawaitable(result):
                    return await result
                return result

        @wraps(func)
        def sync_wrapper(state: Any, *args, **kwargs):
            with tracer.start_as_current_span(node_name) as span:
                span.set_attribute("langfuse.object.type", observation_type.value)
                
                span_context = span.get_span_context()
                if span_context.is_valid:
                    langfuse = get_client()
                    langfuse.update_current_span(
                        metadata={"otel_span_id": format(span_context.span_id, "016x")}
                    )

                return func(state, *args, **kwargs)

        return async_wrapper if inspect.iscoroutinefunction(func) else sync_wrapper
    if _func is not None and callable(_func):
        return decorator(_func)

    return decorator

# def tracing(
#     _func: Optional[Callable[P, R]] = None,
#     *,
#     span_name: Optional[str] = None,
#     observation_type: ObservationType = ObservationType.SPAN
# ) -> Any:
#     """
#     Unified decorator that wraps Langfuse's @observe and OpenTelemetry.
#     Automatically injects the OTel Span ID into Langfuse metadata for cross-referencing.
#     """
#     def decorator(func):
#         node_name = span_name or func.__name__

#         # @observe(
#         #     name=node_name, 
#         #     as_type=cast(_LANGFUSE_AS_TYPE, observation_type.value)
#         # )
#         @functools.wraps(func)
#         async def wrapper(*args, **kwargs):
            
#             # 1. Create the single OpenTelemetry span
#             with tracer.start_as_current_span(node_name) as current_otel_span:
                
#                 # 2. Tell Langfuse what kind of observation this is via OTel attributes!
#                 # This replaces the need for `@observe(as_type=...)`
#                 current_otel_span.set_attribute("langfuse.object.type", observation_type.value)

#                 # Extract the OTel Span ID
#                 span_context = current_otel_span.get_span_context()
#                 if span_context.is_valid:
#                     otel_span_id = format(span_context.span_id, "016x")
                    
#                     # 3. You can still use the Langfuse client to easily push metadata
#                     # Because there is only one active OTel span, Langfuse attaches this perfectly.
#                     langfuse = get_client()
#                     langfuse.update_current_span(
#                         metadata={"otel_span_id": otel_span_id}
#                     )
                
#                 # Execute the actual function
#                 return await func(*args, **kwargs)
                
#         return wrapper

#     if _func is not None and callable(_func):
#         return decorator(_func)

#     return decorator