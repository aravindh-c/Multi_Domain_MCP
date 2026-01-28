"""CloudWatch observability integration for structured logs and metrics."""
import json
import logging
from typing import Any, Dict, List, Optional

try:
    import boto3
    from botocore.exceptions import ClientError
    CLOUDWATCH_AVAILABLE = True
except ImportError:
    CLOUDWATCH_AVAILABLE = False

from src.app.multi_tenant_schemas import TenantMetrics

logger = logging.getLogger(__name__)

# CloudWatch client (initialized lazily)
_cloudwatch_client = None
_cloudwatch_logs_client = None
_log_group_name = "multi-tenant-chatbot"
_metric_namespace = "MultiTenantChatbot"


def _get_cloudwatch_client():
    """Get or create CloudWatch client."""
    global _cloudwatch_client
    if _cloudwatch_client is None and CLOUDWATCH_AVAILABLE:
        _cloudwatch_client = boto3.client("cloudwatch")
    return _cloudwatch_client


def _get_cloudwatch_logs_client():
    """Get or create CloudWatch Logs client."""
    global _cloudwatch_logs_client
    if _cloudwatch_logs_client is None and CLOUDWATCH_AVAILABLE:
        _cloudwatch_logs_client = boto3.client("logs")
    return _cloudwatch_logs_client


def emit_metrics(metrics: TenantMetrics):
    """Emit structured metrics to CloudWatch."""
    if not CLOUDWATCH_AVAILABLE:
        logger.warning("CloudWatch not available, skipping metrics")
        return
    
    client = _get_cloudwatch_client()
    if not client:
        return
    
    try:
        # Emit custom metrics
        metric_data = [
            {
                "MetricName": "RequestLatency",
                "Dimensions": [
                    {"Name": "TenantId", "Value": metrics.tenant_id},
                    {"Name": "Route", "Value": metrics.route},
                ],
                "Value": float(metrics.latency_ms),
                "Unit": "Milliseconds",
            },
            {
                "MetricName": "RequestCount",
                "Dimensions": [
                    {"Name": "TenantId", "Value": metrics.tenant_id},
                    {"Name": "Route", "Value": metrics.route},
                ],
                "Value": 1.0,
                "Unit": "Count",
            },
            {
                "MetricName": "TokenUsage",
                "Dimensions": [
                    {"Name": "TenantId", "Value": metrics.tenant_id},
                    {"Name": "Route", "Value": metrics.route},
                ],
                "Value": float(metrics.token_usage.get("total", 0)),
                "Unit": "Count",
            },
            {
                "MetricName": "CostEstimate",
                "Dimensions": [
                    {"Name": "TenantId", "Value": metrics.tenant_id},
                    {"Name": "Route", "Value": metrics.route},
                ],
                "Value": float(metrics.cost_usd_estimate),
                "Unit": "None",
            },
        ]
        
        if metrics.refusal_reason:
            metric_data.append({
                "MetricName": "RefusalCount",
                "Dimensions": [
                    {"Name": "TenantId", "Value": metrics.tenant_id},
                    {"Name": "Route", "Value": metrics.route},
                    {"Name": "Reason", "Value": metrics.refusal_reason[:50]},  # Truncate long reasons
                ],
                "Value": 1.0,
                "Unit": "Count",
            })
        
        client.put_metric_data(
            Namespace=_metric_namespace,
            MetricData=metric_data,
        )
    except ClientError as e:
        logger.error(f"Failed to emit CloudWatch metrics: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error emitting metrics: {e}")


def log_request(
    tenant_id: str,
    query: str,
    route: str,
    latency_ms: int,
    chunk_ids: Optional[List[str]] = None,
    citations: Optional[List[Dict[str, Any]]] = None,
    refusal_reason: Optional[str] = None,
    token_usage: Optional[Dict[str, int]] = None,
    cost_usd_estimate: float = 0.0,
):
    """Log structured request data to CloudWatch Logs."""
    if not CLOUDWATCH_AVAILABLE:
        # Fallback to standard logging
        logger.info(
            f"tenant_id={tenant_id} route={route} latency_ms={latency_ms} "
            f"chunk_ids={chunk_ids} citations={len(citations or [])} "
            f"refusal_reason={refusal_reason} tokens={token_usage} cost={cost_usd_estimate}"
        )
        return
    
    client = _get_cloudwatch_logs_client()
    if not client:
        return
    
    log_data = {
        "tenant_id": tenant_id,
        "route": route,
        "latency_ms": latency_ms,
        "chunk_ids": chunk_ids or [],
        "citations": citations or [],
        "refusal_reason": refusal_reason,
        "token_usage": token_usage or {},
        "cost_usd_estimate": cost_usd_estimate,
        "query_preview": query[:100],  # Truncate for privacy
    }
    
    try:
        # In production, use log streams per tenant or time-based
        log_stream_name = f"tenant-{tenant_id}"
        
        client.put_log_events(
            logGroupName=_log_group_name,
            logStreamName=log_stream_name,
            logEvents=[
                {
                    "timestamp": int(__import__("time").time() * 1000),
                    "message": json.dumps(log_data),
                }
            ],
        )
    except ClientError as e:
        # If log stream doesn't exist, create it
        if e.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
            try:
                client.create_log_stream(
                    logGroupName=_log_group_name,
                    logStreamName=log_stream_name,
                )
                # Retry
                client.put_log_events(
                    logGroupName=_log_group_name,
                    logStreamName=log_stream_name,
                    logEvents=[
                        {
                            "timestamp": int(__import__("time").time() * 1000),
                            "message": json.dumps(log_data),
                        }
                    ],
                )
            except Exception as create_error:
                logger.error(f"Failed to create log stream: {create_error}")
        else:
            logger.error(f"Failed to write CloudWatch log: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error logging to CloudWatch: {e}")


def ensure_log_group():
    """Ensure CloudWatch log group exists."""
    if not CLOUDWATCH_AVAILABLE:
        return
    
    client = _get_cloudwatch_logs_client()
    if not client:
        return
    
    try:
        client.create_log_group(logGroupName=_log_group_name)
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") != "ResourceAlreadyExistsException":
            logger.error(f"Failed to create log group: {e}")
