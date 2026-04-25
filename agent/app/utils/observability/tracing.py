import functools
from typing import Callable, Optional
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

def tracing(_func: Optional[Callable] = None, *, trace_name: Optional[str] = None, span_name: Optional[str] = None):
    """Decorator to automatically wrap a LangGraph node in an OTel span."""
    def decorator(func):
        graph_name = trace_name or "sugarcane_agent_execution"
        node_name = span_name or func.__name__

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            with tracer.start_as_current_span(f"graph.{graph_name}.node.{node_name}"):
                return await func(*args, **kwargs)
        return wrapper
    
    if _func is not None and callable(_func):
        return decorator(_func)
    
    return decorator