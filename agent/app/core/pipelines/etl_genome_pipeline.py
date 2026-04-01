import logging
import os
from datetime import datetime
from celery import Celery
from airflow.sdk import dag, task, get_current_context
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.sdk.bases.sensor import BaseSensorOperator

# 1. Celery Broker Setup
VALKEY_BROKER_URL = os.getenv("VALKEY_BROKER_URL", "redis://airflow-valkey-1:6379/0")
POSTGRES_GENOME_DB = "POSTGRES_GENOME_DB"

bridge_app = Celery('airflow_bridge', broker=VALKEY_BROKER_URL)

# 2. Sensors
class GenomeProcessingSensor(BaseSensorOperator):
    """
    Actively polls the Genome database to check if the Celery worker
    has finished generating all required file paths.
    """
    def __init__(self, postgres_conn_id: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.postgres_conn_id = postgres_conn_id

    def poke(self, context):
        # Safely extract dag_run and conf
        dag_run = context.get('dag_run')
        conf = (dag_run.conf or {}) if dag_run else {}
        
        genome_id = conf.get("genome_id")

        if not genome_id:
            raise ValueError("No genome_id provided in DAG run config.")

        self.log.info(f"Poking database for Genome ID: {genome_id} to check file paths...")

        # Connect to Postgres using parameterized queries (safer and cleaner)
        hook = PostgresHook(postgres_conn_id=self.postgres_conn_id)
        sql = """
            SELECT fasta_path, gff_path, protein_path, cds_path, gene_fasta_path 
            FROM genomes 
            WHERE id = %(genome_id)s;
        """
        record = hook.get_first(sql, parameters={"genome_id": genome_id})

        if not record:
            raise ValueError(f"Genome ID {genome_id} not found in database!")

        # Unpack the 5 columns from the database record
        fasta_path, gff_path, protein_path, cds_path, gene_fasta_path = record

        # In Python, SQL 'NULL' is represented as 'None'. 
        # Check if ANY of these paths are missing.
        paths = [fasta_path, gff_path, protein_path, cds_path, gene_fasta_path]
        
        if any(path is None for path in paths):
            self.log.info(f"Paths are still NULL for genome {genome_id}. Waiting...")
            
            # --- CRITICAL BEHAVIOR CHOICE ---
            # If you want the sensor to wait and try again, leave this as 'return False'.
            # If you want it to instantly fail and stop the DAG, uncomment the ValueError below:
            # raise ValueError(f"One or more required paths are missing for genome {genome_id}!")
            
            return False 

        # If the code reaches this line, none of the paths are NULL. 
        self.log.info("All genome paths are populated! Moving to next step.")
        return True

# 3. DAG Definition
@dag(
    dag_id="genome_etl_pipeline",
    schedule=None, 
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["bioinformatics", "etl"]
)
def genome_etl_pipeline():

    # Pipeline 1: The Tool Backend (BLAST/Bioinformatics)
    @task()
    def dispatch_tools_pipeline(**kwargs):
        """Grabs the config and drops a message into Valkey."""
        log = logging.getLogger(__name__)
        context = get_current_context()
        
        # Safely extract conf
        dag_run = context.get('dag_run')
        conf = (dag_run.conf or {}) if dag_run else {}
        
        genome_id = conf.get("genome_id")
        fasta_s3 = conf.get("fasta_s3")
        
        if not genome_id or not fasta_s3:
            raise ValueError("Missing required config! Must provide genome_id and fasta_s3.")
        
        log.info(f"Instructing worker to build BLAST DB for {conf.get('genome_name')}...")

        bridge_app.send_task(
            name="app.core.tasks.etl_tasks.task_setup_genome_tools",
            args=[genome_id, fasta_s3],
            queue="etl_queue"
        )

    wait_for_tools_task = GenomeProcessingSensor(
        task_id="wait_for_celery_worker",
        postgres_conn_id=POSTGRES_GENOME_DB,
        poke_interval=5,
        timeout=60 * 60 * 4,
        mode="reschedule"
    )

    # Pipeline 2: The Agent 
    @task()
    def dispatch_agent_pipeline(**kwargs):
        """Dispatches the Semantic Extraction task for the LLM."""
        log = logging.getLogger(__name__)
        context = get_current_context()
        
        # Safely extract conf
        dag_run = context.get('dag_run')
        conf = (dag_run.conf or {}) if dag_run else {}
        
        genome_id = conf.get("genome_id")
        genome_name = conf.get("genome_name")
        
        if not genome_id or not genome_name:
            raise ValueError("Missing required config! Must provide genome_id and genome_name.")
            
        log.info(f"Instructing worker to extract semantics for {genome_name}...")  
        
        bridge_app.send_task(
            name="app.core.tasks.etl_tasks.task_setup_genome_agent",
            args=[genome_id, genome_name, conf.get("gff_s3")],
            queue="etl_queue"
        )

    # Define the flow using set_upstream and set_downstream
    tools_dispatch = dispatch_tools_pipeline()
    agent_dispatch = dispatch_agent_pipeline()

    # Chain: tools_dispatch -> wait_for_tools_task -> agent_dispatch
    tools_dispatch.set_upstream(wait_for_tools_task)
    agent_dispatch.set_upstream(wait_for_tools_task)

# Register the DAG
genome_etl_pipeline()