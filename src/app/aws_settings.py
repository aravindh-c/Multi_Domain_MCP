"""AWS-specific settings with IRSA and Secrets Manager integration."""
import json
import logging
from typing import Optional

import boto3
from botocore.exceptions import ClientError
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class AWSSettings(BaseSettings):
    """AWS-specific settings with Secrets Manager integration."""
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    
    # AWS Configuration
    aws_region: str = "us-east-1"
    aws_role_arn: Optional[str] = None  # IRSA role ARN
    
    # Secrets Manager
    secrets_manager_secret_name: Optional[str] = None
    
    # CloudWatch
    cloudwatch_log_group: str = "multi-tenant-chatbot"
    cloudwatch_metric_namespace: str = "MultiTenantChatbot"
    
    # Service URLs (from service discovery or env)
    orchestrator_service_url: str = "http://orchestrator-service:8000"
    rag_service_url: str = "http://rag-service:8000"
    vllm_service_url: str = "http://vllm-service:8000"
    
    # Model Configuration
    model_name: str = "mistralai/Mistral-7B-Instruct-v0.2"
    embedding_model: str = "text-embedding-3-small"
    
    # RAG Configuration
    faiss_path: str = "/data/faiss/user_vault.index"
    diet_top_k: int = 4
    use_mmr: bool = True
    mmr_fetch_k: int = 20
    mmr_lambda_param: float = 0.5
    use_reranking: bool = False
    rerank_top_n: int = 4
    min_retrieval_confidence: float = 0.0
    
    # Request Configuration
    request_timeout: float = 30.0
    response_max_tokens: int = 512
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Load secrets from Secrets Manager if configured
        if self.secrets_manager_secret_name:
            self._load_secrets()
    
    def _load_secrets(self):
        """Load secrets from AWS Secrets Manager."""
        try:
            session = boto3.Session(region_name=self.aws_region)
            client = session.client("secretsmanager")
            
            response = client.get_secret_value(SecretId=self.secrets_manager_secret_name)
            secret_string = response.get("SecretString", "{}")
            secrets = json.loads(secret_string)
            
            # Update settings from secrets
            for key, value in secrets.items():
                if hasattr(self, key):
                    setattr(self, key, value)
                    logger.info(f"Loaded secret: {key} (from Secrets Manager)")
        except ClientError as e:
            logger.error(f"Failed to load secrets from Secrets Manager: {e}")
            # Continue with defaults
        except Exception as e:
            logger.exception(f"Unexpected error loading secrets: {e}")
            # Continue with defaults
    
    def get_openai_api_key(self) -> Optional[str]:
        """Get OpenAI API key from Secrets Manager or env."""
        # First try env var
        import os
        key = os.getenv("OPENAI_API_KEY")
        if key:
            return key
        
        # Then try Secrets Manager
        if self.secrets_manager_secret_name:
            try:
                session = boto3.Session(region_name=self.aws_region)
                client = session.client("secretsmanager")
                response = client.get_secret_value(SecretId=self.secrets_manager_secret_name)
                secrets = json.loads(response.get("SecretString", "{}"))
                return secrets.get("OPENAI_API_KEY")
            except Exception as e:
                logger.error(f"Failed to get OpenAI API key from Secrets Manager: {e}")
        
        return None
    
    def get_langsmith_api_key(self) -> Optional[str]:
        """Get LangSmith API key from Secrets Manager or env."""
        import os
        key = os.getenv("LANGSMITH_API_KEY")
        if key:
            return key
        
        if self.secrets_manager_secret_name:
            try:
                session = boto3.Session(region_name=self.aws_region)
                client = session.client("secretsmanager")
                response = client.get_secret_value(SecretId=self.secrets_manager_secret_name)
                secrets = json.loads(response.get("SecretString", "{}"))
                return secrets.get("LANGSMITH_API_KEY")
            except Exception as e:
                logger.error(f"Failed to get LangSmith API key from Secrets Manager: {e}")
        
        return None


# Global settings instance
aws_settings = AWSSettings()
