import logging
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Vector and embedding libraries
import chromadb
import docx2txt
import easyocr
import mammoth  # For DOCX conversion
import markdown

# Document processing libraries
import pandas as pd
import psycopg2
import PyPDF2
import pytesseract
from colpali import (
    Colpali,  # Note: Colpali is hypothetical, might need to be replaced with actual implementation
)
from langchain.embeddings import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import Chroma
from PIL import Image
from psycopg2.extras import Json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DocumentProcessor:
    """
    A class to process documents of various formats, convert them to markdown,
    create embeddings, and store them in a vector database with hierarchical context.
    """
    
    def __init__(self, 
                    db_type: str = "chroma",
                    chroma_persist_directory: str = "./chroma_db",
                    postgres_connection_string: str = None,
                    embedding_model: str = "text-embedding-ada-002",
                    api_key: str = None,
                    chunk_size: int = 1000,
                    chunk_overlap: int = 200):
        """
        Initialize the DocumentProcessor with configuration for database and embedding model.
        
        Args:
            db_type: Type of vector database to use ("chroma" or "postgres")
            chroma_persist_directory: Directory to persist Chroma DB
            postgres_connection_string: Connection string for PostgreSQL 
            embedding_model: Name of the embedding model to use
            api_key: API key for embedding model (if needed)
            chunk_size: Size of text chunks for embedding
            chunk_overlap: Overlap between chunks
        """
        self.db_type = db_type.lower()
        self.chroma_persist_directory = chroma_persist_directory
        self.postgres_connection_string = postgres_connection_string
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # Initialize embedding model
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key
        self.embeddings = OpenAIEmbeddings(model=embedding_model)
        
        # Initialize OCR readers
        self.easyocr_reader = easyocr.Reader(['en'])
        self.colpali = Colpali()  # Initialize Colpali
        
        # Initialize database connection
        if self.db_type == "chroma":
            self._init_chroma()
        elif self.db_type == "postgres":
            self._init_postgres()
        else:
            raise ValueError(f"Unsupported database type: {db_type}")
            
        # Initialize text splitter for chunking
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len
        )
    
    def _init_chroma(self):
        """Initialize Chroma database connection."""
        os.makedirs(self.chroma_persist_directory, exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(path=self.chroma_persist_directory)
        logger.info(f"Initialized Chroma DB at {self.chroma_persist_directory}")
    
    def _init_postgres(self):
        """Initialize PostgreSQL database connection."""
        if not self.postgres_connection_string:
            raise ValueError("Postgres connection string is required for PostgreSQL database")
        
        self.pg_conn = psycopg2.connect(self.postgres_connection_string)
        self.pg_cursor = self.pg_conn.cursor()
        
        # Create tables if they don't exist
        self.pg_cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) UNIQUE NOT NULL
            )
        """)
        
        self.pg_cursor.execute("""
            CREATE TABLE IF NOT EXISTS datasources (
                id SERIAL PRIMARY KEY,
                account_id INTEGER REFERENCES accounts(id),
                name VARCHAR(255) NOT NULL,
                UNIQUE(account_id, name)
            )
        """)
        
        self.pg_cursor.execute("""
            CREATE TABLE IF NOT EXISTS document_chunks (
                id SERIAL PRIMARY KEY,
                datasource_id INTEGER REFERENCES datasources(id),
                document_id VARCHAR(255) NOT NULL,
                chunk_id VARCHAR(255) NOT NULL,
                parent_chunk_id VARCHAR(255),
                content TEXT NOT NULL,
                metadata JSONB,
                embedding VECTOR(1536),
                UNIQUE(datasource_id, chunk_id)
            )
        """)
        
        self.pg_conn.commit()
        logger.info("Initialized PostgreSQL connection and tables")
    
    def process_document(self, 
                            file_path: str, 
                            account_name: str, 
                            datasource_name: str,
                            metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Process a document file, convert to markdown, create embeddings and store in database.
        
        Args:
            file_path: Path to the document file
            account_name: Account name for hierarchical storage
            datasource_name: Datasource name for hierarchical storage
            metadata: Additional metadata for the document
            
        Returns:
            Document ID of the processed document
        """
        # Generate a unique document ID
        document_id = str(uuid.uuid4())
        
        # Extract text from document based on file type
        file_extension = os.path.splitext(file_path)[1].lower()
        markdown_text = self._convert_to_markdown(file_path, file_extension)
        
        # Create hierarchical chunks
        chunks = self._create_hierarchical_chunks(markdown_text)
        
        # Store embeddings
        self._store_embeddings(chunks, document_id, account_name, datasource_name, metadata)
        
        return document_id
    
    def _convert_to_markdown(self, file_path: str, file_extension: str) -> str:
        """
        Convert document to markdown format based on file extension.
        
        Args:
            file_path: Path to the document file
            file_extension: File extension to determine conversion method
            
        Returns:
            Markdown formatted text
        """
        logger.info(f"Converting {file_path} to markdown")
        
        try:
            if file_extension in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']:
                return self._process_image(file_path)
            
            elif file_extension == '.pdf':
                return self._process_pdf(file_path)
            
            elif file_extension == '.docx':
                return self._process_docx(file_path)
            
            elif file_extension == '.csv':
                return self._process_csv(file_path)
            
            elif file_extension == '.txt':
                with open(file_path, 'r', encoding='utf-8') as file:
                    text = file.read()
                return text
            
            elif file_extension == '.md':
                with open(file_path, 'r', encoding='utf-8') as file:
                    text = file.read()
                return text
            
            else:
                raise ValueError(f"Unsupported file extension: {file_extension}")
                
        except Exception as e:
            logger.error(f"Error converting document: {str(e)}")
            raise
    
    def _process_image(self, file_path: str) -> str:
        """Process image file using OCR."""
        logger.info(f"Processing image with OCR: {file_path}")
        
        # Try Colpali first
        try:
            result = self.colpali.extract_text(file_path)
            if result and len(result.strip()) > 0:
                return result
        except Exception as e:
            logger.warning(f"Colpali OCR failed: {str(e)}")
        
        # Try EasyOCR
        try:
            result = self.easyocr_reader.readtext(file_path)
            if result:
                return "\n\n".join([text for _, text, _ in result])
        except Exception as e:
            logger.warning(f"EasyOCR failed: {str(e)}")
        
        # Fall back to Tesseract
        try:
            img = Image.open(file_path)
            text = pytesseract.image_to_string(img)
            return text
        except Exception as e:
            logger.warning(f"Tesseract OCR failed: {str(e)}")
            raise ValueError("All OCR methods failed for this image")
    
    def _process_pdf(self, file_path: str) -> str:
        """Process PDF file and convert to markdown."""
        logger.info(f"Processing PDF: {file_path}")
        
        # Check if the PDF has text content or is scanned
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                page_text = page.extract_text()
                
                # If page has no text, it might be scanned - use OCR
                if not page_text or len(page_text.strip()) < 50:
                    # Convert PDF page to image and use OCR
                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                        temp_image_path = temp_file.name
                    
                    # This is a simplified approach - would need to use a library like pdf2image in practice
                    img = Image.open(file_path)
                    img.save(temp_image_path)
                    
                    page_text = self._process_image(temp_image_path)
                    os.unlink(temp_image_path)
                
                text += f"\n\n--- Page {page_num + 1} ---\n\n{page_text}"
                
        return text
    
    def _process_docx(self, file_path: str) -> str:
        """Process DOCX file and convert to markdown."""
        logger.info(f"Processing DOCX: {file_path}")
        
        # Try using mammoth for better markdown conversion
        try:
            with open(file_path, "rb") as docx_file:
                result = mammoth.convert_to_markdown(docx_file)
                return result.value
        except Exception as e:
            logger.warning(f"Mammoth conversion failed: {str(e)}")
            
            # Fallback to docx2txt
            try:
                text = docx2txt.process(file_path)
                return text
            except Exception as e2:
                logger.error(f"docx2txt conversion failed: {str(e2)}")
                raise
    
    def _process_csv(self, file_path: str) -> str:
        """Process CSV file and convert to markdown."""
        logger.info(f"Processing CSV: {file_path}")
        
        try:
            df = pd.read_csv(file_path)
            markdown_table = df.to_markdown(index=False)
            return markdown_table
        except Exception as e:
            logger.error(f"CSV conversion failed: {str(e)}")
            raise
    
    def _create_hierarchical_chunks(self, text: str) -> List[Dict[str, Any]]:
        """
        Create hierarchical chunks from the text.
        
        Args:
            text: The text to split into chunks
            
        Returns:
            List of chunk dictionaries with parent-child relationships
        """
        logger.info("Creating hierarchical chunks")
        
        # First level: Split by major sections (e.g., headers)
        # This is a simplified approach - would need more sophisticated parsing for real docs
        sections = []
        current_section = ""
        
        for line in text.split('\n'):
            if line.startswith('# '):  # Major section header
                if current_section:
                    sections.append(current_section)
                current_section = line + '\n'
            else:
                current_section += line + '\n'
                
        if current_section:
            sections.append(current_section)
            
        # Create hierarchical chunks
        chunks = []
        
        # Create a parent chunk for the entire document
        parent_chunk_id = str(uuid.uuid4())
        chunks.append({
            'content': text[:1000] + '...' if len(text) > 1000 else text,  # Truncated overview
            'chunk_id': parent_chunk_id,
            'parent_chunk_id': None
        })
        
        # Create child chunks for each section
        for section in sections:
            # Create a section parent
            section_id = str(uuid.uuid4())
            chunks.append({
                'content': section[:1000] + '...' if len(section) > 1000 else section,
                'chunk_id': section_id,
                'parent_chunk_id': parent_chunk_id
            })
            
            # Further split the section into smaller chunks
            section_chunks = self.text_splitter.split_text(section)
            for chunk in section_chunks:
                chunks.append({
                    'content': chunk,
                    'chunk_id': str(uuid.uuid4()),
                    'parent_chunk_id': section_id
                })
                
        return chunks
    
    def _store_embeddings(self, 
                            chunks: List[Dict[str, Any]], 
                            document_id: str,
                            account_name: str, 
                            datasource_name: str,
                            metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Store embeddings in the database with hierarchical context.
        
        Args:
            chunks: List of text chunks with parent-child relationships
            document_id: Unique ID for the document
            account_name: Account name for hierarchical storage
            datasource_name: Datasource name for hierarchical storage
            metadata: Additional metadata for the document
        """
        if metadata is None:
            metadata = {}
            
        # Add document_id to metadata
        metadata['document_id'] = document_id
        
        if self.db_type == "chroma":
            self._store_in_chroma(chunks, document_id, account_name, datasource_name, metadata)
        else:
            self._store_in_postgres(chunks, document_id, account_name, datasource_name, metadata)
    
    def _store_in_chroma(self, 
                            chunks: List[Dict[str, Any]], 
                            document_id: str,
                            account_name: str, 
                            datasource_name: str,
                            metadata: Dict[str, Any]) -> None:
        """Store embeddings in Chroma DB."""
        logger.info(f"Storing embeddings in Chroma DB for document {document_id}")
        
        # Create a collection for the account/datasource if it doesn't exist
        collection_name = f"{account_name}_{datasource_name}"
        collection = self.chroma_client.get_or_create_collection(collection_name)
        
        # Process chunks and store them
        for chunk in chunks:
            chunk_metadata = {
                **metadata,
                'chunk_id': chunk['chunk_id'],
                'parent_chunk_id': chunk['parent_chunk_id'],
                'account': account_name,
                'datasource': datasource_name
            }
            
            # Generate embedding
            embedding = self.embeddings.embed_query(chunk['content'])
            
            # Add document to collection
            collection.add(
                ids=[chunk['chunk_id']],
                embeddings=[embedding],
                metadatas=[chunk_metadata],
                documents=[chunk['content']]
            )
            
        logger.info(f"Stored {len(chunks)} chunks in Chroma DB")
    
    def _store_in_postgres(self, 
                            chunks: List[Dict[str, Any]], 
                            document_id: str,
                            account_name: str, 
                            datasource_name: str,
                            metadata: Dict[str, Any]) -> None:
        """Store embeddings in PostgreSQL database."""
        logger.info(f"Storing embeddings in PostgreSQL for document {document_id}")
        
        # Get or create account
        self.pg_cursor.execute(
            "INSERT INTO accounts (name) VALUES (%s) ON CONFLICT (name) DO NOTHING RETURNING id",
            (account_name,)
        )
        result = self.pg_cursor.fetchone()
        if result:
            account_id = result[0]
        else:
            self.pg_cursor.execute("SELECT id FROM accounts WHERE name = %s", (account_name,))
            account_id = self.pg_cursor.fetchone()[0]
        
        # Get or create datasource
        self.pg_cursor.execute(
            """
            INSERT INTO datasources (account_id, name) 
            VALUES (%s, %s) ON CONFLICT (account_id, name) DO NOTHING RETURNING id
            """,
            (account_id, datasource_name)
        )
        result = self.pg_cursor.fetchone()
        if result:
            datasource_id = result[0]
        else:
            self.pg_cursor.execute(
                "SELECT id FROM datasources WHERE account_id = %s AND name = %s",
                (account_id, datasource_name)
            )
            datasource_id = self.pg_cursor.fetchone()[0]
        
        # Process chunks and store them
        for chunk in chunks:
            chunk_metadata = {
                **metadata,
                'account': account_name,
                'datasource': datasource_name
            }
            
            # Generate embedding
            embedding = self.embeddings.embed_query(chunk['content'])
            
            # Add document to database
            self.pg_cursor.execute(
                """
                INSERT INTO document_chunks 
                (datasource_id, document_id, chunk_id, parent_chunk_id, content, metadata, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (datasource_id, chunk_id) 
                DO UPDATE SET 
                    document_id = EXCLUDED.document_id,
                    parent_chunk_id = EXCLUDED.parent_chunk_id,
                    content = EXCLUDED.content,
                    metadata = EXCLUDED.metadata,
                    embedding = EXCLUDED.embedding
                """,
                (
                    datasource_id,
                    document_id,
                    chunk['chunk_id'],
                    chunk['parent_chunk_id'],
                    chunk['content'],
                    Json(chunk_metadata),
                    embedding
                )
            )
        
        self.pg_conn.commit()
        logger.info(f"Stored {len(chunks)} chunks in PostgreSQL")
    
    def search(self, 
                query: str, 
                account_name: str, 
                datasource_name: str = None,
                limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search for similar documents based on a query.
        
        Args:
            query: Search query text
            account_name: Account name to search in
            datasource_name: Optional datasource name to filter by
            limit: Number of results to return
            
        Returns:
            List of matching document chunks with metadata
        """
        logger.info(f"Searching for '{query}' in account '{account_name}'")
        
        # Generate embedding for the query
        query_embedding = self.embeddings.embed_query(query)
        
        if self.db_type == "chroma":
            return self._search_in_chroma(query_embedding, account_name, datasource_name, limit)
        else:
            return self._search_in_postgres(query_embedding, account_name, datasource_name, limit)
    
    def _search_in_chroma(self, 
                            query_embedding: List[float], 
                            account_name: str, 
                            datasource_name: str = None,
                            limit: int = 5) -> List[Dict[str, Any]]:
        """Search for similar documents in Chroma DB."""
        if datasource_name:
            collection_name = f"{account_name}_{datasource_name}"
            collection = self.chroma_client.get_or_create_collection(collection_name)
            
            # Query the collection
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=limit,
                include=["metadatas", "documents", "distances"]
            )
        else:
            # Search across all datasources for the account
            all_results = []
            
            for collection in self.chroma_client.list_collections():
                if collection.name.startswith(f"{account_name}_"):
                    result = collection.query(
                        query_embeddings=[query_embedding],
                        n_results=limit,
                        include=["metadatas", "documents", "distances"]
                    )
                    
                    for i in range(len(result["ids"][0])):
                        all_results.append({
                            "id": result["ids"][0][i],
                            "metadata": result["metadatas"][0][i],
                            "content": result["documents"][0][i],
                            "distance": result["distances"][0][i]
                        })
            
            # Sort by distance and limit results
            all_results.sort(key=lambda x: x["distance"])
            return all_results[:limit]
        
        # Format results
        formatted_results = []
        for i in range(len(results["ids"][0])):
            formatted_results.append({
                "id": results["ids"][0][i],
                "metadata": results["metadatas"][0][i],
                "content": results["documents"][0][i],
                "distance": results["distances"][0][i]
            })
            
        return formatted_results
    
    def _search_in_postgres(self, 
                            query_embedding: List[float], 
                            account_name: str, 
                            datasource_name: str = None,
                            limit: int = 5) -> List[Dict[str, Any]]:
        """Search for similar documents in PostgreSQL database."""
        # Get account ID
        self.pg_cursor.execute("SELECT id FROM accounts WHERE name = %s", (account_name,))
        result = self.pg_cursor.fetchone()
        if not result:
            logger.warning(f"Account '{account_name}' not found")
            return []
        
        account_id = result[0]
        
        # Build the query
        if datasource_name:
            self.pg_cursor.execute(
                """
                SELECT id FROM datasources WHERE account_id = %s AND name = %s
                """,
                (account_id, datasource_name)
            )
            result = self.pg_cursor.fetchone()
            if not result:
                logger.warning(f"Datasource '{datasource_name}' not found for account '{account_name}'")
                return []
                
            datasource_id = result[0]
            
            # Query for specific datasource
            self.pg_cursor.execute(
                """
                SELECT 
                    chunk_id, document_id, parent_chunk_id, content, metadata,
                    embedding <=> %s AS distance
                FROM document_chunks
                WHERE datasource_id = %s
                ORDER BY distance ASC
                LIMIT %s
                """,
                (query_embedding, datasource_id, limit)
            )
        else:
            # Query across all datasources for the account
            self.pg_cursor.execute(
                """
                SELECT 
                    dc.chunk_id, dc.document_id, dc.parent_chunk_id, dc.content, dc.metadata,
                    dc.embedding <=> %s AS distance
                FROM document_chunks dc
                JOIN datasources ds ON dc.datasource_id = ds.id
                WHERE ds.account_id = %s
                ORDER BY distance ASC
                LIMIT %s
                """,
                (query_embedding, account_id, limit)
            )
        
        results = self.pg_cursor.fetchall()
        
        # Format results
        formatted_results = []
        for result in results:
            formatted_results.append({
                "id": result[0],  # chunk_id
                "metadata": {
                    "document_id": result[1],
                    "parent_chunk_id": result[2],
                    **result[4]  # metadata JSONB
                },
                "content": result[3],  # content
                "distance": result[5]  # distance
            })
            
        return formatted_results
    
    def get_related_chunks(self, 
                            chunk_id: str, 
                            account_name: str, 
                            datasource_name: str) -> List[Dict[str, Any]]:
        """
        Get related chunks based on parent-child relationships.
        
        Args:
            chunk_id: ID of the chunk to find related chunks for
            account_name: Account name
            datasource_name: Datasource name
            
        Returns:
            List of related chunks including parents and children
        """
        logger.info(f"Getting related chunks for chunk {chunk_id}")
        
        if self.db_type == "chroma":
            return self._get_related_chunks_chroma(chunk_id, account_name, datasource_name)
        else:
            return self._get_related_chunks_postgres(chunk_id, account_name, datasource_name)
    
    def _get_related_chunks_chroma(self, 
                                    chunk_id: str, 
                                    account_name: str, 
                                    datasource_name: str) -> List[Dict[str, Any]]:
        """Get related chunks from Chroma DB."""
        collection_name = f"{account_name}_{datasource_name}"
        collection = self.chroma_client.get_or_create_collection(collection_name)
        
        # Get the chunk
        result = collection.get(ids=[chunk_id])
        if not result or len(result["ids"]) == 0:
            logger.warning(f"Chunk {chunk_id} not found")
            return []
        
        parent_chunk_id = result["metadatas"][0].get("parent_chunk_id")
        
        related_chunks = []
        
        # Get parent chunk
        if parent_chunk_id:
            parent_result = collection.get(ids=[parent_chunk_id])
            if parent_result and len(parent_result["ids"]) > 0:
                related_chunks.append({
                    "id": parent_result["ids"][0],
                    "metadata": parent_result["metadatas"][0],
                    "content": parent_result["documents"][0],
                    "relation": "parent"
                })
        
        # Get child chunks
        child_results = collection.get(
            where={"parent_chunk_id": chunk_id}
        )
        
        for i in range(len(child_results["ids"])):
            related_chunks.append({
                "id": child_results["ids"][i],
                "metadata": child_results["metadatas"][i],
                "content": child_results["documents"][i],
                "relation": "child"
            })
            
        return related_chunks
    
    def _get_related_chunks_postgres(self, 
                                    chunk_id: str, 
                                    account_name: str, 
                                    datasource_name: str) -> List[Dict[str, Any]]:
        """Get related chunks from PostgreSQL database."""
        # Get account and datasource IDs
        self.pg_cursor.execute(
            """
            SELECT ds.id FROM datasources ds
            JOIN accounts acc ON ds.account_id = acc.id
            WHERE acc.name = %s AND ds.name = %s
            """,
            (account_name, datasource_name)
        )
        result = self.pg_cursor.fetchone()
        if not result:
            logger.warning(f"Datasource '{datasource_name}' not found for account '{account_name}'")
            return []
            
        datasource_id = result[0]
        
        # Get the chunk
        self.pg_cursor.execute(
            """
            SELECT parent_chunk_id FROM document_chunks
            WHERE datasource_id = %s AND chunk_id = %s
            """,
            (datasource_id, chunk_id)
        )
        result = self.pg_cursor.fetchone()
        if not result:
            logger.warning(f"Chunk {chunk_id} not found")
            return []
            
        parent_chunk_id = result[0]
        
        related_chunks = []
        
        # Get parent chunk
        if parent_chunk_id:
            self.pg_cursor.execute(
                """
                SELECT chunk_id, document_id, parent_chunk_id, content, metadata
                FROM document_chunks
                WHERE datasource_id = %s AND chunk_id = %s
                """,
                (datasource_id, parent_chunk_id)
            )
            result = self.pg_cursor.fetchone()
            if result:
                related_chunks.append({
                    "id": result[0],
                    "metadata": {
                        "document_id": result[1],
                        "parent_chunk_id": result[2],
                        **result[4]
                    },
                    "content": result[3],
                    "relation": "parent"
                })
        
        # Get child chunks
        self.pg_cursor.execute(
            """
            SELECT chunk_id, document_id, parent_chunk_id, content, metadata
            FROM document_chunks
            WHERE datasource_id = %s AND parent_chunk_id = %s
            """,
            (datasource_id, chunk_id)
        )
        results = self.pg_cursor.fetchall()
        
        for result in results:
            related_chunks.append({
                "id": result[0],
                "metadata": {
                    "document_id": result[1],
                    "parent_chunk_id": result[2],
                    **result[4]
                },
                "content": result[3],
                "relation": "child"
            })
            
        return related_chunks
    
    def delete_document(self, document_id: str, account_name: str, datasource_name: str) -> int:
        """
        Delete a document and all its chunks from the database.
        
        Args:
            document_id: ID of the document to delete
            account_name: Account name
            datasource_name: Datasource name
            
        Returns:
            Number of chunks deleted
        """
        logger.info(f"Deleting document {document_id}")
        
        if self.db_type == "chroma":
            return self._delete_document_chroma(document_id, account_name, datasource_name)
        else:
            return self._delete_document_postgres(document_id, account_name, datasource_name)
    
    def _delete_document_chroma(self, document_id: str, account_name: str, datasource_name: str) -> int:
        """Delete a document from Chroma DB."""
        collection_name = f"{account_name}_{datasource_name}"
        collection = self.chroma_client.get_or_create_collection(collection_name)
        
        # Get all chunks for the document
        results = collection.get(
            where={"document_id": document_id}
        )
        
        if not results or len(results["ids"]) == 0:
            logger.warning(f"Document {document_id} not found")
            return 0
        
        # Delete all

def main():
    """
    Test and validate the DocumentProcessor class with various file types and operations.
    This function provides examples of how to use the DocumentProcessor for different scenarios.
    """
    import argparse
    import os
    import tempfile
    
    # Setup argument parser
    parser = argparse.ArgumentParser(description='Test DocumentProcessor with different options.')
    parser.add_argument('--db_type', choices=['chroma', 'postgres'], default='chroma', 
                        help='Type of vector database to use')
    parser.add_argument('--api_key', type=str, help='API key for embedding model')
    parser.add_argument('--postgres_conn', type=str, 
                        help='PostgreSQL connection string (required if using postgres)')
    parser.add_argument('--test_dir', type=str, default=None, 
                        help='Directory containing test documents')
    parser.add_argument('--operation', choices=['process', 'search', 'delete', 'all'], 
                        default='all', help='Operation to test')
    parser.add_argument('--account', type=str, default='test_account', 
                        help='Account name for testing')
    parser.add_argument('--datasource', type=str, default='test_datasource', 
                        help='Datasource name for testing')
    
    args = parser.parse_args()
    
    # Validate required arguments
    if args.db_type == 'postgres' and not args.postgres_conn:
        parser.error("--postgres_conn is required when db_type is postgres")
    
    # Initialize DocumentProcessor
    processor = DocumentProcessor(
        db_type=args.db_type,
        chroma_persist_directory="./test_chroma_db",
        postgres_connection_string=args.postgres_conn,
        api_key=args.api_key
    )
    
    # Create temp test files if no test directory provided
    if not args.test_dir:
        test_files = create_test_files()
    else:
        # Gather files from provided directory
        test_files = []
        for root, _, files in os.walk(args.test_dir):
            for file in files:
                if not file.startswith('.'):  # Skip hidden files
                    test_files.append(os.path.join(root, file))
    
    # Track processed document IDs for testing search and delete
    document_ids = []
    
    # Test document processing
    if args.operation in ['process', 'all']:
        print("\n=== Testing Document Processing ===")
        for file_path in test_files:
            try:
                print(f"Processing {file_path}...")
                doc_id = processor.process_document(
                    file_path=file_path,
                    account_name=args.account,
                    datasource_name=args.datasource,
                    metadata={"test_file": os.path.basename(file_path)}
                )
                document_ids.append(doc_id)
                print(f"Successfully processed document with ID: {doc_id}")
            except Exception as e:
                print(f"Error processing {file_path}: {str(e)}")
    
    # Test search functionality
    if args.operation in ['search', 'all'] and document_ids:
        print("\n=== Testing Search Functionality ===")
        
        # Search queries to test
        test_queries = [
            "import pandas",  # Technical query
            "process document",  # General query
            "database connection",  # Database-related
            "This is a test file"  # Generic document content
        ]
        
        for query in test_queries:
            print(f"\nSearching for: '{query}'")
            results = processor.search(
                query=query,
                account_name=args.account,
                datasource_name=args.datasource,
                limit=3
            )
            
            if results:
                print(f"Found {len(results)} results:")
                for i, result in enumerate(results):
                    print(f"\nResult {i+1} (distance: {result['distance']:.4f}):")
                    print(f"Chunk ID: {result['id']}")
                    print(f"Document ID: {result['metadata'].get('document_id', 'N/A')}")
                    print(f"Content (first 100 chars): {result['content'][:100]}...")
            else:
                print("No results found.")
                
        # Test related chunks functionality for the first search result
        if results:
            chunk_id = results[0]['id']
            print(f"\nGetting related chunks for chunk {chunk_id}")
            related = processor.get_related_chunks(
                chunk_id=chunk_id,
                account_name=args.account,
                datasource_name=args.datasource
            )
            
            if related:
                print(f"Found {len(related)} related chunks:")
                for i, chunk in enumerate(related):
                    print(f"\nRelated Chunk {i+1} ({chunk['relation']}):")
                    print(f"Chunk ID: {chunk['id']}")
                    print(f"Content (first 100 chars): {chunk['content'][:100]}...")
            else:
                print("No related chunks found.")
    
    # Test delete functionality
    if args.operation in ['delete', 'all'] and document_ids:
        print("\n=== Testing Delete Functionality ===")
        
        # Delete the first document
        if document_ids:
            doc_id = document_ids[0]
            print(f"Deleting document {doc_id}...")
            count = processor.delete_document(
                document_id=doc_id,
                account_name=args.account,
                datasource_name=args.datasource
            )
            print(f"Deleted {count} chunks from document {doc_id}")
            
            # Verify deletion by searching
            print(f"Verifying deletion by searching for document {doc_id}...")
            results = processor.search(
                query="test document",
                account_name=args.account,
                datasource_name=args.datasource,
                limit=5
            )
            
            document_still_exists = any(r['metadata'].get('document_id') == doc_id for r in results)
            if document_still_exists:
                print(f"WARNING: Document {doc_id} still found in search results")
            else:
                print(f"Success: Document {doc_id} no longer found in search results")
    
    print("\n=== Testing Complete ===")


def create_test_files():
    """Create temporary test files of different formats."""
    print("Creating temporary test files...")
    test_files = []
    
    # Create a temporary directory
    temp_dir = tempfile.mkdtemp()
    print(f"Created temporary directory: {temp_dir}")
    
    # Create a text file
    txt_path = os.path.join(temp_dir, "test.txt")
    with open(txt_path, 'w') as f:
        f.write("This is a test file.\n" * 10)
        f.write("It contains some sample text for processing.\n")
        f.write("The DocumentProcessor should handle this text file correctly.\n")
    test_files.append(txt_path)
    print(f"Created test.txt at {txt_path}")
    
    # Create a markdown file
    md_path = os.path.join(temp_dir, "test.md")
    with open(md_path, 'w') as f:
        f.write("# Test Markdown File\n\n")
        f.write("This is a **markdown** file with some formatting.\n\n")
        f.write("## Section 1\n\n")
        f.write("- Item 1\n- Item 2\n- Item 3\n\n")
        f.write("## Section 2\n\n")
        f.write("This is another section with `code` and [links](https://example.com).\n")
    test_files.append(md_path)
    print(f"Created test.md at {md_path}")
    
    # Create a CSV file
    csv_path = os.path.join(temp_dir, "test.csv")
    with open(csv_path, 'w') as f:
        f.write("id,name,value\n")
        f.write("1,Item A,10.5\n")
        f.write("2,Item B,20.3\n")
        f.write("3,Item C,15.7\n")
    test_files.append(csv_path)
    print(f"Created test.csv at {csv_path}")
    
    # Attempt to create a simple PDF using reportlab if available
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        
        pdf_path = os.path.join(temp_dir, "test.pdf")
        c = canvas.Canvas(pdf_path, pagesize=letter)
        c.drawString(100, 750, "Test PDF Document")
        c.drawString(100, 700, "This is a PDF file created for testing.")
        c.drawString(100, 650, "The DocumentProcessor should handle this PDF file.")
        c.save()
        test_files.append(pdf_path)
        print(f"Created test.pdf at {pdf_path}")
    except ImportError:
        print("reportlab not installed, skipping PDF creation")
    
    # Return the list of test files
    return test_files


if __name__ == "__main__":
    main()