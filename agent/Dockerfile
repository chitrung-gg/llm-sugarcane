FROM continuumio/miniconda3:latest

WORKDIR /app

COPY environment.yml .

RUN conda env update --file environment.yml --prune

ENV PATH /opt/conda/envs/llm-sugarcane/bin:$PATH

COPY . .

CMD ["celery", "-A", "app.core.workers.celery", "worker", "-Q", "ingest_knowledge_queue", "--loglevel=debug", "--concurrency=2"]
