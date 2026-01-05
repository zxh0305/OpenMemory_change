import os
import json
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Config as ConfigModel
from app.utils.memory import reset_memory_client

"""
配置管理API路由

提供系统配置管理功能：
- 获取和更新LLM配置
- 获取和更新Embedder配置
- 获取和更新OpenMemory自定义配置
- 重置配置为默认值
"""
router = APIRouter(prefix="/api/v1/config", tags=["config"])

class LLMConfig(BaseModel):
    model: str = Field(..., description="LLM model name")
    temperature: float = Field(..., description="Temperature setting for the model")
    max_tokens: int = Field(..., description="Maximum tokens to generate")
    api_key: Optional[str] = Field(None, description="API key or 'env:API_KEY' to use environment variable")
    ollama_base_url: Optional[str] = Field(None, description="Base URL for Ollama server (e.g., http://host.docker.internal:11434)")

class LLMProvider(BaseModel):
    provider: str = Field(..., description="LLM provider name")
    config: LLMConfig

class EmbedderConfig(BaseModel):
    model: str = Field(..., description="Embedder model name")
    api_key: Optional[str] = Field(None, description="API key or 'env:API_KEY' to use environment variable")
    ollama_base_url: Optional[str] = Field(None, description="Base URL for Ollama server (e.g., http://host.docker.internal:11434)")

class EmbedderProvider(BaseModel):
    provider: str = Field(..., description="Embedder provider name")
    config: EmbedderConfig

class OpenMemoryConfig(BaseModel):
    custom_instructions: Optional[str] = Field(None, description="Custom instructions for memory management and fact extraction")

class Mem0Config(BaseModel):
    llm: Optional[LLMProvider] = None
    embedder: Optional[EmbedderProvider] = None

class ConfigSchema(BaseModel):
    openmemory: Optional[OpenMemoryConfig] = None
    mem0: Mem0Config

def get_default_configuration():
    """Get the default configuration structure with 'env:VAR_NAME' placeholders."""
    return {
        "openmemory": {
            "custom_instructions": "env:OPENMEMORY_CUSTOM_INSTRUCTIONS"
        },
        "mem0": {
            "llm": {
                "provider": "env:OPENAI_PROVIDER",
                "config": {
                    "model": "env:OPENAI_MODEL",
                    "temperature": 0.1,
                    "max_tokens": 2000,
                    "api_key": "env:OPENAI_API_KEY",
                    "openai_base_url": "env:OPENAI_BASE_URL"
                }
            },
            "embedder": {
                "provider": "openai",
                "config": {
                    "model": "env:OPENAI_EMBEDDING_MODEL",
                    "api_key": "env:OPENAI_EMBEDDING_MODEL_API_KEY",
                    "openai_base_url": "env:OPENAI_EMBEDDING_MODEL_BASE_URL"
                }
            }
        }
    }

def get_config_from_db(db: Session, key: str = "main"):
    """Get configuration from database."""
    config = db.query(ConfigModel).filter(ConfigModel.key == key).first()
    
    if not config:
        # Create default config with proper provider configurations
        default_config = get_default_configuration()
        db_config = ConfigModel(key=key, value=default_config)
        db.add(db_config)
        db.commit()
        db.refresh(db_config)
        return default_config
    
    # Ensure the config has all required sections with defaults
    config_value = config.value
    default_config = get_default_configuration()
    
    # Merge with defaults to ensure all required fields exist
    if "openmemory" not in config_value:
        config_value["openmemory"] = default_config["openmemory"]
    
    if "mem0" not in config_value:
        config_value["mem0"] = default_config["mem0"]
    else:
        # Ensure LLM config exists with defaults
        if "llm" not in config_value["mem0"] or config_value["mem0"]["llm"] is None:
            config_value["mem0"]["llm"] = default_config["mem0"]["llm"]
        
        # Ensure embedder config exists with defaults
        if "embedder" not in config_value["mem0"] or config_value["mem0"]["embedder"] is None:
            config_value["mem0"]["embedder"] = default_config["mem0"]["embedder"]
    
    # Save the updated config back to database if it was modified
    if config_value != config.value:
        config.value = config_value
        db.commit()
        db.refresh(config)
    
    return config_value

def save_config_to_db(db: Session, config: Dict[str, Any], key: str = "main"):
    """Save configuration to database."""
    db_config = db.query(ConfigModel).filter(ConfigModel.key == key).first()
    
    if db_config:
        db_config.value = config
        db_config.updated_at = None  # Will trigger the onupdate to set current time
    else:
        db_config = ConfigModel(key=key, value=config)
        db.add(db_config)
        
    db.commit()
    db.refresh(db_config)
    return db_config.value

@router.get("/", response_model=ConfigSchema)
async def get_configuration(db: Session = Depends(get_db)):
    """
    获取系统的完整配置信息。
    
    返回内容：
    - OpenMemory自定义配置（自定义指令等）
    - Mem0配置（LLM和Embedder配置）
    
    配置结构：
    - openmemory: OpenMemory特定配置
    - mem0.llm: 大语言模型配置
    - mem0.embedder: 嵌入模型配置
    """
    config = get_config_from_db(db)
    return config

@router.put("/", response_model=ConfigSchema)
async def update_configuration(config: ConfigSchema, db: Session = Depends(get_db)):
    """
    更新系统的完整配置。
    
    功能说明：
    - 可以同时更新OpenMemory和Mem0配置
    - 更新后会自动重新初始化内存客户端
    - 配置会持久化到数据库
    
    参数:
    - openmemory: OpenMemory配置（可选）
    - mem0: Mem0配置（必填，包含llm和embedder）
    
    注意事项：
    - 更新配置后需要重新初始化内存客户端
    - 某些配置更改可能需要重启服务才能生效
    """
    current_config = get_config_from_db(db)
    
    # Convert to dict for processing
    updated_config = current_config.copy()
    
    # Update openmemory settings if provided
    if config.openmemory is not None:
        if "openmemory" not in updated_config:
            updated_config["openmemory"] = {}
        updated_config["openmemory"].update(config.openmemory.dict(exclude_none=True))
    
    # Update mem0 settings
    updated_config["mem0"] = config.mem0.dict(exclude_none=True)
    
    # Save the configuration to database
    save_config_to_db(db, updated_config)
    reset_memory_client()
    return updated_config

@router.post("/reset", response_model=ConfigSchema)
async def reset_configuration(db: Session = Depends(get_db)):
    """
    将配置重置为默认值。
    
    功能说明：
    - 恢复所有配置为默认值
    - 使用环境变量中的默认配置
    - 重置后会自动重新初始化内存客户端
    
    注意事项：
    - 此操作会覆盖所有自定义配置
    - 请谨慎使用
    """
    try:
        # Get the default configuration with proper provider setups
        default_config = get_default_configuration()
        
        # Save it as the current configuration in the database
        save_config_to_db(db, default_config)
        reset_memory_client()
        return default_config
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to reset configuration: {str(e)}"
        )

@router.get("/mem0/llm", response_model=LLMProvider)
async def get_llm_configuration(db: Session = Depends(get_db)):
    """
    获取大语言模型（LLM）的配置信息。
    
    返回内容：
    - LLM提供商（openai, ollama等）
    - 模型配置（模型名称、温度、最大token数等）
    - API密钥和基础URL
    """
    config = get_config_from_db(db)
    llm_config = config.get("mem0", {}).get("llm", {})
    return llm_config

@router.put("/mem0/llm", response_model=LLMProvider)
async def update_llm_configuration(llm_config: LLMProvider, db: Session = Depends(get_db)):
    """
    更新大语言模型（LLM）的配置。
    
    功能说明：
    - 只更新LLM相关配置
    - 更新后会自动重新初始化内存客户端
    - 支持多种LLM提供商（OpenAI、Ollama等）
    
    参数:
    - provider: LLM提供商（必填）
    - config: 配置信息（必填）
      - model: 模型名称
      - temperature: 温度参数（0-2）
      - max_tokens: 最大token数
      - api_key: API密钥（可选，可使用env:变量名）
      - ollama_base_url: Ollama基础URL（可选）
    """
    current_config = get_config_from_db(db)
    
    # Ensure mem0 key exists
    if "mem0" not in current_config:
        current_config["mem0"] = {}
    
    # Update the LLM configuration
    current_config["mem0"]["llm"] = llm_config.dict(exclude_none=True)
    
    # Save the configuration to database
    save_config_to_db(db, current_config)
    reset_memory_client()
    return current_config["mem0"]["llm"]

@router.get("/mem0/embedder", response_model=EmbedderProvider)
async def get_embedder_configuration(db: Session = Depends(get_db)):
    """
    获取嵌入模型（Embedder）的配置信息。
    
    返回内容：
    - Embedder提供商
    - 模型配置（模型名称、API密钥、基础URL等）
    """
    config = get_config_from_db(db)
    embedder_config = config.get("mem0", {}).get("embedder", {})
    return embedder_config

@router.put("/mem0/embedder", response_model=EmbedderProvider)
async def update_embedder_configuration(embedder_config: EmbedderProvider, db: Session = Depends(get_db)):
    """
    更新嵌入模型（Embedder）的配置。
    
    功能说明：
    - 只更新Embedder相关配置
    - 更新后会自动重新初始化内存客户端
    - 支持多种Embedder提供商
    
    参数:
    - provider: Embedder提供商（必填）
    - config: 配置信息（必填）
      - model: 模型名称
      - api_key: API密钥（可选，可使用env:变量名）
      - ollama_base_url: Ollama基础URL（可选）
    """
    current_config = get_config_from_db(db)
    
    # Ensure mem0 key exists
    if "mem0" not in current_config:
        current_config["mem0"] = {}
    
    # Update the Embedder configuration
    current_config["mem0"]["embedder"] = embedder_config.dict(exclude_none=True)
    
    # Save the configuration to database
    save_config_to_db(db, current_config)
    reset_memory_client()
    return current_config["mem0"]["embedder"]

@router.get("/openmemory", response_model=OpenMemoryConfig)
async def get_openmemory_configuration(db: Session = Depends(get_db)):
    """
    获取OpenMemory的自定义配置。
    
    返回内容：
    - custom_instructions: 自定义指令（用于记忆提取和事实提取）
    
    自定义指令说明：
    - 用于指导大模型如何提取和存储记忆
    - 可以自定义记忆提取的规则和格式
    - 支持中文和英文
    """
    config = get_config_from_db(db)
    openmemory_config = config.get("openmemory", {})
    return openmemory_config

@router.put("/openmemory", response_model=OpenMemoryConfig)
async def update_openmemory_configuration(openmemory_config: OpenMemoryConfig, db: Session = Depends(get_db)):
    """
    更新OpenMemory的自定义配置。
    
    功能说明：
    - 更新自定义指令
    - 更新后会自动重新初始化内存客户端
    - 新配置会立即生效
    
    参数:
    - custom_instructions: 自定义指令（可选）
      - 用于指导大模型如何提取事实信息
      - 可以定义提取规则、格式要求等
      - 如果不提供，将使用默认的中文事实提取提示词
    """
    current_config = get_config_from_db(db)
    
    # Ensure openmemory key exists
    if "openmemory" not in current_config:
        current_config["openmemory"] = {}
    
    # Update the OpenMemory configuration
    current_config["openmemory"].update(openmemory_config.dict(exclude_none=True))
    
    # Save the configuration to database
    save_config_to_db(db, current_config)
    reset_memory_client()
    return current_config["openmemory"] 