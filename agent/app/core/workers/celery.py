# from app.configs.settings.settings import get_settings
# from celery import Celery
# from kombu import Queue, Exchange


# settings = get_settings()

# CELERY_BACKEND_URL = f"db+{settings.knowledgegraph_postgres_url}"

# celery = Celery(
#     "genome_worker",
#     broker=settings.knowledgegraph_rabbitmq_url,
#     backend=CELERY_BACKEND_URL,      # Storing Task results
#     # Point this to wherever you save the task file below
#     include=["app.core.pipelines.celery.celery_ingest_knowledge"] 
# )

# # 1. Deleted old queues and created a single dedicated queue
# celery.conf.task_queues = (
#     Queue('ingest_knowledge_queue', Exchange('ingest_knowledge_queue'), routing_key='ingest_knowledge_queue'),
# )

# # 2. Route the graph ingestion task exclusively to this new queue
# celery.conf.task_routes = {
#     'llm.tasks.ingest_knowledge': {'queue': 'ingest_knowledge_queue'},
#     'llm.tasks.process_document_ingestion': {'queue': 'ingest_knowledge_queue'}
# }

# # Worker Settings
# celery.conf.update(
#     task_serializer="json",
#     accept_content=["json"],
#     result_serializer="json",
#     timezone="Asia/Ho_Chi_Minh",
#     enable_utc=True,
#     task_acks_late=True,
#     worker_prefetch_multiplier=1,
#     task_track_started=True,
#     worker_send_task_events=True
# )