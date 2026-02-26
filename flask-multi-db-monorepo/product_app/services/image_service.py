"""
Image Service - DALL-E image generation and Azure Blob Storage upload
Handles both user-uploaded images and AI-generated images for products.
"""
import os
import sys
import requests
from io import BytesIO
from datetime import datetime, timedelta
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


class ImageService:
    """Service for product image management: upload and DALL-E generation."""

    def __init__(self):
        self.dalle_deployment = os.getenv('AZURE_OPENAI_DALLE_DEPLOYMENT', 'dall-e-3')
        self.storage_connection_string = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
        self.container_name = os.getenv('AZURE_STORAGE_CONTAINER', 'product-images')
        self.account_name = os.getenv('AZURE_STORAGE_ACCOUNT')
        self.account_key = os.getenv('AZURE_STORAGE_KEY')

        # Extract account name/key from connection string if available
        if self.storage_connection_string:
            for part in self.storage_connection_string.split(';'):
                if part.startswith('AccountName='):
                    self.account_name = part.split('=', 1)[1]
                elif part.startswith('AccountKey='):
                    self.account_key = part.split('=', 1)[1]

    def _get_blob_service_client(self):
        """Get Azure Blob Storage client."""
        from azure.storage.blob import BlobServiceClient

        if self.storage_connection_string:
            return BlobServiceClient.from_connection_string(self.storage_connection_string)
        elif self.account_name and self.account_key:
            account_url = f"https://{self.account_name}.blob.core.windows.net"
            return BlobServiceClient(account_url, credential=self.account_key)
        else:
            raise ValueError("Azure Storage not configured. Set AZURE_STORAGE_CONNECTION_STRING or AZURE_STORAGE_ACCOUNT + AZURE_STORAGE_KEY.")

    def _get_openai_client(self):
        """Get Azure OpenAI client."""
        from openai import AzureOpenAI

        endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
        api_key = os.getenv('AZURE_OPENAI_API_KEY')

        if not endpoint or not api_key:
            raise ValueError("Azure OpenAI not configured. Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY.")

        return AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version="2024-02-01"
        )

    def upload_to_blob(self, image_bytes: bytes, blob_name: str, content_type: str = 'image/png') -> str:
        """
        Upload image bytes to Azure Blob Storage.
        Returns the public URL (with SAS token) of the uploaded blob.
        """
        from azure.storage.blob import ContentSettings, generate_blob_sas, BlobSasPermissions
        from azure.core.exceptions import ResourceExistsError

        blob_service_client = self._get_blob_service_client()

        # Ensure container exists
        container_client = blob_service_client.get_container_client(self.container_name)
        try:
            container_client.create_container(public_access='blob')
        except ResourceExistsError:
            pass
        except Exception:
            pass  # Container may already exist

        # Upload blob
        blob_client = container_client.get_blob_client(blob_name)
        content_settings = ContentSettings(content_type=content_type)
        blob_client.upload_blob(
            image_bytes,
            overwrite=True,
            content_settings=content_settings
        )

        # Generate SAS URL with long expiry
        sas_token = generate_blob_sas(
            account_name=self.account_name,
            container_name=self.container_name,
            blob_name=blob_name,
            account_key=self.account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(days=3650)  # 10 years
        )

        return f"{blob_client.url}?{sas_token}"

    def upload_product_image(self, sku: str, file_storage) -> str:
        """
        Upload a user-provided image file for a product.
        
        Args:
            sku: Product SKU (used as blob name)
            file_storage: Flask FileStorage object from request.files
            
        Returns:
            URL of the uploaded image
        """
        # Determine content type
        filename = file_storage.filename or ''
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'png'
        content_type_map = {
            'png': 'image/png',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'gif': 'image/gif',
            'webp': 'image/webp'
        }
        content_type = content_type_map.get(ext, 'image/png')

        image_bytes = file_storage.read()
        blob_name = f"products/{sku.lower()}.{ext}"

        return self.upload_to_blob(image_bytes, blob_name, content_type)

    def generate_product_image(self, name: str, description: str, category: str = '', sku: str = '') -> str:
        """
        Generate a product image using DALL-E and upload to Blob Storage.
        
        Args:
            name: Product name
            description: Product description
            category: Product category
            sku: Product SKU (used as blob name)
            
        Returns:
            URL of the generated and uploaded image
        """
        # Build prompt
        prompt = self._build_dalle_prompt(name, description, category)

        # Generate with DALL-E
        client = self._get_openai_client()
        response = client.images.generate(
            model=self.dalle_deployment,
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1
        )

        temp_url = response.data[0].url

        # Download the generated image
        image_response = requests.get(temp_url, timeout=60)
        image_response.raise_for_status()
        image_bytes = image_response.content

        # Upload to Blob Storage
        blob_name = f"products/{sku.lower()}.png"
        return self.upload_to_blob(image_bytes, blob_name, 'image/png')

    def _build_dalle_prompt(self, name: str, description: str, category: str = '') -> str:
        """Create an effective DALL-E prompt for product photography."""
        prompt = f"""Professional product photography of {name}. 
Category: {category}. 
Clean white background, studio lighting, high quality commercial product shot.
Modern minimalist style, centered composition, soft shadows.
{description[:150]}"""
        return prompt[:1000]

    def get_image_proxy(self, sku: str) -> Optional[bytes]:
        """
        Fetch product image bytes from blob storage (for proxying).
        Returns None if image doesn't exist.
        """
        try:
            blob_service_client = self._get_blob_service_client()
            container_client = blob_service_client.get_container_client(self.container_name)
            blob_name = f"products/{sku.lower()}.png"
            blob_client = container_client.get_blob_client(blob_name)
            return blob_client.download_blob().readall()
        except Exception:
            return None
