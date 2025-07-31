"""
RAG Milvus Worker for Runpod
- Document processing with Docling
- BGE-M3 embeddings
- Milvus vector database operations
"""

import os
import json
import time
import logging
import tempfile
import uuid
from typing import List, Dict, Optional, Any, Union
from pathlib import Path
import base64

import runpod
import torch
from pymilvus import MilvusClient, DataType
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from FlagEmbedding import BGEM3FlagModel
import numpy as np

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables
milvus_client = None
embedding_model = None
document_converter = None

# Configuration
MILVUS_DB_PATH = os.environ.get("MILVUS_DB_PATH", "./milvus_rag.db")
MODEL_NAME = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-m3")
EMBEDDING_DIM = 1024
DEFAULT_COLLECTION = "rag_documents"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
BATCH_SIZE = 32


def initialize_components():
    """Initialize Milvus, embedding model, and document converter"""
    global milvus_client, embedding_model, document_converter
    
    try:
        # Initialize Milvus client
        logger.info(f"Initializing Milvus client with path: {MILVUS_DB_PATH}")
        milvus_client = MilvusClient(uri=MILVUS_DB_PATH)
        
        # Initialize BGE-M3 embedding model
        logger.info(f"Loading embedding model: {MODEL_NAME}")
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        embedding_model = BGEM3FlagModel(MODEL_NAME, use_fp16=True, device=device)
        
        # Initialize Docling document converter
        logger.info("Initializing Docling document converter")
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = True
        pipeline_options.do_table_structure = True
        
        document_converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )
        
        logger.info("All components initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize components: {e}")
        return False


def create_collection(collection_name: str, dimension: int = EMBEDDING_DIM):
    """Create or recreate a Milvus collection"""
    try:
        # Check if collection exists
        if milvus_client.has_collection(collection_name):
            logger.info(f"Collection {collection_name} already exists")
            return True
            
        # Create collection with optimized schema
        schema = milvus_client.create_schema(
            auto_id=True,
            enable_dynamic_field=True,
        )
        
        # Add fields
        schema.add_field(field_name="id", datatype=DataType.INT64, is_primary=True)
        schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=dimension)
        schema.add_field(field_name="text", datatype=DataType.VARCHAR, max_length=65535)
        schema.add_field(field_name="metadata", datatype=DataType.JSON)
        
        # Create collection
        milvus_client.create_collection(
            collection_name=collection_name,
            schema=schema,
            metric_type="COSINE",
            consistency_level="Strong"
        )
        
        # Create index for better performance
        index_params = {
            "metric_type": "COSINE",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 1024}
        }
        
        milvus_client.create_index(
            collection_name=collection_name,
            field_name="vector",
            index_params=index_params
        )
        
        logger.info(f"Collection {collection_name} created successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to create collection: {e}")
        return False


def process_document_with_docling(file_path: str) -> List[Dict[str, Any]]:
    """Process document using Docling and extract structured content"""
    try:
        logger.info(f"Processing document with Docling: {file_path}")
        
        # Convert document
        result = document_converter.convert(file_path)
        
        # Extract text chunks with metadata
        chunks = []
        chunk_id = 0
        
        # Process document content
        for element in result.document.iterate_items():
            text = str(element)
            
            if not text or len(text.strip()) < 10:
                continue
                
            # Create chunks with sliding window
            words = text.split()
            
            for i in range(0, len(words), CHUNK_SIZE - CHUNK_OVERLAP):
                chunk_text = " ".join(words[i:i + CHUNK_SIZE])
                
                if len(chunk_text.strip()) < 50:  # Skip very short chunks
                    continue
                    
                chunk_metadata = {
                    "chunk_id": chunk_id,
                    "source": os.path.basename(file_path),
                    "page": getattr(element, 'page', 0),
                    "type": element.__class__.__name__,
                    "confidence": getattr(element, 'confidence', 1.0),
                    "timestamp": time.time()
                }
                
                chunks.append({
                    "text": chunk_text,
                    "metadata": chunk_metadata
                })
                
                chunk_id += 1
        
        logger.info(f"Extracted {len(chunks)} chunks from document")
        return chunks
        
    except Exception as e:
        logger.error(f"Failed to process document: {e}")
        return []


def generate_embeddings(texts: List[str]) -> List[List[float]]:
    """Generate embeddings using BGE-M3"""
    try:
        # Batch processing for efficiency
        embeddings = []
        
        for i in range(0, len(texts), BATCH_SIZE):
            batch_texts = texts[i:i + BATCH_SIZE]
            
            # Generate embeddings
            batch_embeddings = embedding_model.encode(
                batch_texts,
                batch_size=BATCH_SIZE,
                max_length=512,
                return_dense=True,
                return_sparse=False,
                return_colbert_vecs=False
            )
            
            # Extract dense embeddings
            if isinstance(batch_embeddings, dict):
                dense_embeddings = batch_embeddings['dense_vecs']
            else:
                dense_embeddings = batch_embeddings
                
            embeddings.extend(dense_embeddings.tolist())
        
        return embeddings
        
    except Exception as e:
        logger.error(f"Failed to generate embeddings: {e}")
        return []


def create_vector_db(request: Dict[str, Any]) -> Dict[str, Any]:
    """Create or update vector database with documents"""
    try:
        collection_name = request.get("collection_name", DEFAULT_COLLECTION)
        documents = request.get("documents", [])
        merge_existing = request.get("merge_existing", True)
        
        # Handle base64 encoded documents
        processed_docs = []
        temp_files = []
        
        for doc in documents:
            if "content_base64" in doc:
                # Decode base64 content and save to temp file
                content = base64.b64decode(doc["content_base64"])
                temp_file = tempfile.NamedTemporaryFile(
                    suffix=f".{doc.get('format', 'pdf')}", 
                    delete=False
                )
                temp_file.write(content)
                temp_file.close()
                temp_files.append(temp_file.name)
                
                # Process document with Docling
                chunks = process_document_with_docling(temp_file.name)
                processed_docs.extend(chunks)
                
            elif "file_path" in doc:
                # Process local file
                chunks = process_document_with_docling(doc["file_path"])
                processed_docs.extend(chunks)
        
        if not processed_docs:
            return {
                "success": False,
                "message": "No documents to process",
                "error": "Empty document list"
            }
        
        # Create collection if needed
        if not merge_existing or not milvus_client.has_collection(collection_name):
            # Drop existing if not merging
            if milvus_client.has_collection(collection_name) and not merge_existing:
                milvus_client.drop_collection(collection_name)
                
            create_collection(collection_name)
        
        # Generate embeddings
        texts = [doc["text"] for doc in processed_docs]
        embeddings = generate_embeddings(texts)
        
        if not embeddings:
            return {
                "success": False,
                "message": "Failed to generate embeddings",
                "error": "Embedding generation failed"
            }
        
        # Prepare data for insertion
        data = []
        for i, (doc, embedding) in enumerate(zip(processed_docs, embeddings)):
            data.append({
                "vector": embedding,
                "text": doc["text"],
                "metadata": doc["metadata"]
            })
        
        # Insert into Milvus
        milvus_client.insert(
            collection_name=collection_name,
            data=data
        )
        
        # Load collection for searching
        milvus_client.load_collection(collection_name)
        
        # Get collection stats
        stats = milvus_client.get_collection_stats(collection_name)
        
        # Cleanup temp files
        for temp_file in temp_files:
            try:
                os.unlink(temp_file)
            except:
                pass
        
        return {
            "success": True,
            "message": f"Successfully processed {len(processed_docs)} chunks",
            "collection_name": collection_name,
            "chunks_processed": len(processed_docs),
            "total_entities": stats.get("row_count", 0),
            "merge_mode": merge_existing
        }
        
    except Exception as e:
        logger.error(f"Error creating vector database: {e}")
        return {
            "success": False,
            "message": "Failed to create vector database",
            "error": str(e)
        }


def remove_vector_db(request: Dict[str, Any]) -> Dict[str, Any]:
    """Remove vector database collection"""
    try:
        collection_name = request.get("collection_name", DEFAULT_COLLECTION)
        
        if not milvus_client.has_collection(collection_name):
            return {
                "success": False,
                "message": f"Collection {collection_name} does not exist",
                "error": "Collection not found"
            }
        
        # Drop collection
        milvus_client.drop_collection(collection_name)
        
        return {
            "success": True,
            "message": f"Successfully removed collection {collection_name}",
            "collection_name": collection_name
        }
        
    except Exception as e:
        logger.error(f"Error removing vector database: {e}")
        return {
            "success": False,
            "message": "Failed to remove vector database",
            "error": str(e)
        }


def search_vectors(request: Dict[str, Any]) -> Dict[str, Any]:
    """Search vectors in the database"""
    try:
        collection_name = request.get("collection_name", DEFAULT_COLLECTION)
        query = request.get("query", "")
        top_k = request.get("top_k", 5)
        score_threshold = request.get("score_threshold", 0.7)
        filters = request.get("filters", {})
        
        if not query:
            return {
                "success": False,
                "message": "Query text is required",
                "error": "Empty query"
            }
        
        if not milvus_client.has_collection(collection_name):
            return {
                "success": False,
                "message": f"Collection {collection_name} does not exist",
                "error": "Collection not found"
            }
        
        # Generate query embedding
        query_embedding = generate_embeddings([query])[0]
        
        # Prepare search parameters
        search_params = {
            "metric_type": "COSINE",
            "params": {"nprobe": 16}
        }
        
        # Build filter expression if provided
        filter_expr = None
        if filters:
            filter_parts = []
            for key, value in filters.items():
                if isinstance(value, str):
                    filter_parts.append(f'metadata["{key}"] == "{value}"')
                else:
                    filter_parts.append(f'metadata["{key}"] == {value}')
            filter_expr = " && ".join(filter_parts)
        
        # Perform search
        results = milvus_client.search(
            collection_name=collection_name,
            data=[query_embedding],
            anns_field="vector",
            search_params=search_params,
            limit=top_k,
            output_fields=["text", "metadata"],
            expr=filter_expr
        )
        
        # Process results
        search_results = []
        for hits in results:
            for hit in hits:
                score = 1 - hit.distance  # Convert distance to similarity
                
                if score >= score_threshold:
                    result = {
                        "id": str(hit.id),
                        "score": float(score),
                        "text": hit.entity.get("text", ""),
                        "metadata": hit.entity.get("metadata", {})
                    }
                    search_results.append(result)
        
        return {
            "success": True,
            "message": f"Found {len(search_results)} results",
            "query": query,
            "results": search_results,
            "total_results": len(search_results),
            "collection_name": collection_name
        }
        
    except Exception as e:
        logger.error(f"Error searching vectors: {e}")
        return {
            "success": False,
            "message": "Failed to search vectors",
            "error": str(e)
        }


def handler(event: Dict[str, Any]) -> Dict[str, Any]:
    """Main handler for Runpod requests"""
    try:
        action = event.get("input", {}).get("action", "")
        
        if action == "create_vector_db":
            return create_vector_db(event.get("input", {}))
            
        elif action == "remove_vector_db":
            return remove_vector_db(event.get("input", {}))
            
        elif action == "search_vectors":
            return search_vectors(event.get("input", {}))
            
        else:
            return {
                "success": False,
                "message": f"Unknown action: {action}",
                "error": "Invalid action",
                "available_actions": ["create_vector_db", "remove_vector_db", "search_vectors"]
            }
            
    except Exception as e:
        logger.error(f"Handler error: {e}")
        return {
            "success": False,
            "message": "Internal server error",
            "error": str(e)
        }


if __name__ == "__main__":
    # Initialize components on startup
    if initialize_components():
        logger.info("Starting RAG Milvus Worker...")
        runpod.serverless.start({"handler": handler})
    else:
        logger.error("Failed to initialize components, exiting...")
        exit(1)