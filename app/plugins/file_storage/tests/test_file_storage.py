"""
Tests for the file storage plugin.

This file contains both unit tests and integration tests for the file storage plugin.
- Unit tests: Test individual components without external dependencies
- Integration tests: Test the full functionality with actual storage providers

To run tests:
    pytest -xvs app/plugins/file_storage/tests/test_file_storage.py
"""

import io
import os
import pytest
import tempfile
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI, UploadFile
from sqlalchemy.orm import Session
from PIL import Image

from app.core.db import get_db
from app.core.security import get_current_user
from app.plugins.file_storage import router
from app.plugins.file_storage.models import StorageProvider, StoredFile, FileThumbnail, FileFolder
from app.plugins.file_storage.schemas import StorageProviderCreate, StorageProviderType
from app.plugins.file_storage.providers import get_provider_instance
from app.plugins.file_storage.utils.image_processor import ImageProcessor


# Sample test user data
TEST_USER = {"id": 1, "username": "test_user", "email": "test@example.com"}

# Sample provider data
TEST_PROVIDER_DATA = {
    "name": "Test MinIO",
    "provider_type": StorageProviderType.MINIO,
    "bucket_name": "test-bucket",
    "endpoint_url": "http://localhost:9000",
    "access_key": "minioadmin",
    "secret_key": "minioadmin",
    "is_default": True
}


# ---- Fixtures ----

@pytest.fixture
def app():
    """Create a test FastAPI app."""
    app = FastAPI()
    app.include_router(router)
    
    # Override authentication dependency
    async def mock_get_current_user():
        return TEST_USER
    
    app.dependency_overrides[get_current_user] = mock_get_current_user
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def db_session():
    """Mock database session."""
    session = MagicMock(spec=Session)
    return session


@pytest.fixture
def mock_db(app, db_session):
    """Override the database dependency."""
    app.dependency_overrides[get_db] = lambda: db_session
    return db_session


@pytest.fixture
def test_image():
    """Create a test image."""
    image = Image.new("RGB", (100, 100), color="red")
    img_io = io.BytesIO()
    image.save(img_io, format="JPEG")
    img_io.seek(0)
    return img_io


@pytest.fixture
def mock_storage_provider():
    """Create a mock storage provider object."""
    provider = MagicMock()
    provider.upload_file.return_value = "https://test-bucket.s3.amazonaws.com/test.jpg"
    provider.download_file.return_value = io.BytesIO(b"test file content")
    provider.get_file_url.return_value = "https://test-bucket.s3.amazonaws.com/test.jpg?signed=true"
    provider.delete_file.return_value = True
    provider.exists.return_value = True
    return provider


# ---- Unit Tests ----

class TestStorageProviders:
    """Tests for storage provider functionality."""
    
    def test_create_provider(self, client, mock_db):
        """Test creating a storage provider."""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        
        provider_obj = StorageProvider(id=1, **TEST_PROVIDER_DATA)
        mock_db.refresh.side_effect = lambda x: setattr(x, 'id', 1)
        
        response = client.post("/file-storage/providers", json=TEST_PROVIDER_DATA)
        
        assert response.status_code == 200
        assert response.json()["name"] == TEST_PROVIDER_DATA["name"]
        assert mock_db.add.called
        assert mock_db.commit.called
    
    def test_get_providers(self, client, mock_db):
        """Test getting all storage providers."""
        provider = StorageProvider(id=1, **TEST_PROVIDER_DATA)
        mock_db.query.return_value.offset.return_value.limit.return_value.all.return_value = [provider]
        
        response = client.get("/file-storage/providers")
        
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["name"] == TEST_PROVIDER_DATA["name"]
    
    def test_get_provider(self, client, mock_db):
        """Test getting a specific storage provider."""
        provider = StorageProvider(id=1, **TEST_PROVIDER_DATA)
        mock_db.query.return_value.filter.return_value.first.return_value = provider
        
        response = client.get("/file-storage/providers/1")
        
        assert response.status_code == 200
        assert response.json()["name"] == TEST_PROVIDER_DATA["name"]
    
    def test_update_provider(self, client, mock_db):
        """Test updating a storage provider."""
        provider = StorageProvider(id=1, **TEST_PROVIDER_DATA)
        mock_db.query.return_value.filter.return_value.first.return_value = provider
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None
        
        update_data = {"name": "Updated Provider Name"}
        response = client.put("/file-storage/providers/1", json=update_data)
        
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Provider Name"
        assert mock_db.commit.called
    
    def test_delete_provider(self, client, mock_db):
        """Test deleting a storage provider."""
        provider = StorageProvider(id=1, **TEST_PROVIDER_DATA)
        mock_db.query.return_value.filter.return_value.first.return_value = provider
        mock_db.query.return_value.filter.return_value.count.return_value = 0
        mock_db.delete.return_value = None
        mock_db.commit.return_value = None
        
        response = client.delete("/file-storage/providers/1")
        
        assert response.status_code == 200
        assert response.json()["message"] == "Storage provider deleted successfully"
        assert mock_db.delete.called
        assert mock_db.commit.called


class TestFileOperations:
    """Tests for file operations."""
    
    @patch("app.plugins.file_storage.main.get_provider_instance")
    async def test_upload_file(self, mock_get_provider, client, mock_db, test_image, mock_storage_provider):
        """Test uploading a file."""
        mock_get_provider.return_value = mock_storage_provider
        
        provider = StorageProvider(id=1, **TEST_PROVIDER_DATA)
        mock_db.query.return_value.filter.return_value.first.return_value = provider
        
        # Mock the creation of the file record
        stored_file = StoredFile(
            id=1,
            provider_id=1,
            filename="test.jpg",
            original_filename="test.jpg",
            storage_path="uploads/test.jpg",
            file_size=len(test_image.getvalue()),
            content_type="image/jpeg",
            file_url="https://test-bucket.s3.amazonaws.com/test.jpg",
            created_by=1
        )
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.side_effect = lambda x: setattr(x, 'id', 1)
        
        with tempfile.NamedTemporaryFile(suffix=".jpg") as temp_file:
            temp_file.write(test_image.getvalue())
            temp_file.flush()
            
            with open(temp_file.name, "rb") as f:
                response = client.post(
                    "/file-storage/files/upload",
                    files={"file": ("test.jpg", f, "image/jpeg")},
                    data={"provider_id": 1}
                )
        
        assert response.status_code == 200
        assert mock_storage_provider.upload_file.called
        assert mock_db.add.called
        assert mock_db.commit.called
    
    def test_get_files(self, client, mock_db):
        """Test getting all files."""
        stored_file = StoredFile(
            id=1,
            provider_id=1,
            filename="test.jpg",
            original_filename="test.jpg",
            storage_path="uploads/test.jpg",
            file_size=1000,
            content_type="image/jpeg",
            file_url="https://test-bucket.s3.amazonaws.com/test.jpg",
            created_by=1
        )
        mock_db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [stored_file]
        
        response = client.get("/file-storage/files")
        
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["filename"] == "test.jpg"
    
    @patch("app.plugins.file_storage.main.get_provider_instance")
    def test_get_file(self, mock_get_provider, client, mock_db, mock_storage_provider):
        """Test getting a specific file."""
        mock_get_provider.return_value = mock_storage_provider
        
        stored_file = StoredFile(
            id=1,
            provider_id=1,
            filename="test.jpg",
            original_filename="test.jpg",
            storage_path="uploads/test.jpg",
            file_size=1000,
            content_type="image/jpeg",
            file_url="https://test-bucket.s3.amazonaws.com/test.jpg",
            created_by=1
        )
        provider = StorageProvider(id=1, **TEST_PROVIDER_DATA)
        mock_db.query.return_value.filter.return_value.first.side_effect = [stored_file, provider]
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        response = client.get("/file-storage/files/1")
        
        assert response.status_code == 200
        assert response.json()["filename"] == "test.jpg"
        assert "download_url" in response.json()
    
    @patch("app.plugins.file_storage.main.get_provider_instance")
    def test_download_file(self, mock_get_provider, client, mock_db, mock_storage_provider):
        """Test downloading a file."""
        mock_get_provider.return_value = mock_storage_provider
        
        stored_file = StoredFile(
            id=1,
            provider_id=1,
            filename="test.jpg",
            original_filename="test.jpg",
            storage_path="uploads/test.jpg",
            file_size=1000,
            content_type="image/jpeg",
            file_url="https://test-bucket.s3.amazonaws.com/test.jpg",
            created_by=1
        )
        provider = StorageProvider(id=1, **TEST_PROVIDER_DATA)
        mock_db.query.return_value.filter.return_value.first.side_effect = [stored_file, provider]
        
        response = client.get("/file-storage/files/1/download")
        
        assert response.status_code == 200
        assert mock_storage_provider.download_file.called
    
    @patch("app.plugins.file_storage.main.get_provider_instance")
    def test_delete_file(self, mock_get_provider, client, mock_db, mock_storage_provider):
        """Test deleting a file."""
        mock_get_provider.return_value = mock_storage_provider
        
        stored_file = StoredFile(
            id=1,
            provider_id=1,
            filename="test.jpg",
            original_filename="test.jpg",
            storage_path="uploads/test.jpg",
            file_size=1000,
            content_type="image/jpeg",
            file_url="https://test-bucket.s3.amazonaws.com/test.jpg",
            created_by=1
        )
        provider = StorageProvider(id=1, **TEST_PROVIDER_DATA)
        mock_db.query.return_value.filter.return_value.first.side_effect = [stored_file, provider]
        mock_db.query.return_value.filter.return_value.all.return_value = []
        mock_db.delete.return_value = None
        mock_db.commit.return_value = None
        
        response = client.delete("/file-storage/files/1")
        
        assert response.status_code == 200
        assert response.json()["message"] == "File deleted successfully"
        assert mock_storage_provider.delete_file.called
        assert mock_db.delete.called
        assert mock_db.commit.called


class TestFolderOperations:
    """Tests for folder operations."""
    
    def test_create_folder(self, client, mock_db):
        """Test creating a folder."""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        
        folder_data = {
            "name": "Test Folder",
            "path": "/test-folder"
        }
        folder = FileFolder(id=1, **folder_data)
        mock_db.refresh.side_effect = lambda x: setattr(x, 'id', 1)
        
        response = client.post("/file-storage/folders", json=folder_data)
        
        assert response.status_code == 200
        assert response.json()["name"] == folder_data["name"]
        assert mock_db.add.called
        assert mock_db.commit.called
    
    def test_get_folders(self, client, mock_db):
        """Test getting all folders."""
        folder = FileFolder(
            id=1,
            name="Test Folder",
            path="/test-folder"
        )
        mock_db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [folder]
        
        response = client.get("/file-storage/folders")
        
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["name"] == "Test Folder"
    
    def test_get_folder(self, client, mock_db):
        """Test getting a specific folder."""
        folder = FileFolder(
            id=1,
            name="Test Folder",
            path="/test-folder"
        )
        mock_db.query.return_value.filter.return_value.first.return_value = folder
        mock_db.query.return_value.filter.return_value.scalar.return_value = 0
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        response = client.get("/file-storage/folders/1")
        
        assert response.status_code == 200
        assert response.json()["name"] == "Test Folder"


class TestImageProcessing:
    """Tests for image processing functionality."""
    
    def test_generate_thumbnail(self, test_image):
        """Test generating a thumbnail."""
        thumbnail_data, metadata = ImageProcessor.generate_thumbnail(
            test_image,
            size="sm",
            format="jpeg",
            quality=85
        )
        
        # Verify the result
        assert isinstance(thumbnail_data, io.BytesIO)
        assert metadata["width"] == 100  # Our test image is 100x100
        assert metadata["height"] == 100
        assert metadata["format"] == "jpeg"
    
    def test_optimize_image(self, test_image):
        """Test optimizing an image."""
        optimized_data, metadata = ImageProcessor.optimize_image(
            test_image,
            output_format="jpeg",
            quality=85
        )
        
        # Verify the result
        assert isinstance(optimized_data, io.BytesIO)
        assert metadata["width"] == 100  # Our test image is 100x100
        assert metadata["height"] == 100
        assert metadata["format"] == "jpeg"
    
    def test_get_image_info(self, test_image):
        """Test getting image information."""
        info = ImageProcessor.get_image_info(test_image)
        
        # Verify the result
        assert info["width"] == 100  # Our test image is 100x100
        assert info["height"] == 100
        assert info["format"] == "JPEG"


# ---- Integration Tests ----
# Note: These tests require actual storage providers to be available
# They are marked with 'integration' so they can be skipped with pytest -k "not integration"

@pytest.mark.integration
class TestMinioIntegration:
    """Integration tests for MinIO provider."""
    
    @pytest.fixture
    def minio_provider(self):
        """Create a real MinIO provider instance for testing."""
        from app.plugins.file_storage.providers.minio_provider import MinioStorageProvider
        
        provider = MinioStorageProvider()
        provider.initialize({
            "endpoint_url": "http://localhost:9000",
            "access_key": "minioadmin",
            "secret_key": "minioadmin",
            "bucket_name": "test-bucket",
            "secure": False
        })
        return provider
    
    def test_minio_upload_download(self, minio_provider, test_image):
        """Test uploading and downloading a file with MinIO."""
        # Upload a file
        file_url = minio_provider.upload_file(
            test_image,
            "test/integration_test.jpg",
            content_type="image/jpeg"
        )
        
        # Verify the URL
        assert "test/integration_test.jpg" in file_url
        
        # Download the file
        downloaded = minio_provider.download_file("test/integration_test.jpg")
        
        # Verify the content
        assert downloaded.getvalue() == test_image.getvalue()
        
        # Clean up
        minio_provider.delete_file("test/integration_test.jpg")
        
        # Verify it's deleted
        assert not minio_provider.exists("test/integration_test.jpg")


@pytest.mark.integration
class TestS3Integration:
    """Integration tests for S3 provider."""
    
    @pytest.fixture
    def s3_provider(self):
        """Create a real S3 provider instance for testing."""
        # This requires actual AWS credentials
        # You should use environment variables or AWS credentials file
        from app.plugins.file_storage.providers.s3_provider import S3StorageProvider
        
        provider = S3StorageProvider()
        provider.initialize({
            "access_key": os.environ.get("AWS_ACCESS_KEY"),
            "secret_key": os.environ.get("AWS_SECRET_KEY"),
            "bucket_name": "test-bucket",
            "region": "us-east-1"
        })
        return provider
    
    def test_s3_upload_download(self, s3_provider, test_image):
        """Test uploading and downloading a file with S3."""
        # Skip if no AWS credentials
        if not os.environ.get("AWS_ACCESS_KEY") or not os.environ.get("AWS_SECRET_KEY"):
            pytest.skip("AWS credentials not available")
        
        # Upload a file
        file_url = s3_provider.upload_file(
            test_image,
            "test/integration_test.jpg",
            content_type="image/jpeg"
        )
        
        # Verify the URL
        assert "test/integration_test.jpg" in file_url
        
        # Download the file
        downloaded = s3_provider.download_file("test/integration_test.jpg")
        
        # Verify the content
        assert downloaded.getvalue() == test_image.getvalue()
        
        # Clean up
        s3_provider.delete_file("test/integration_test.jpg")
        
        # Verify it's deleted
        assert not s3_provider.exists("test/integration_test.jpg")


# ---- Test main functionality ----

def test_module_import():
    """Test that the module can be imported without errors."""
    from app.plugins.file_storage import router
    assert router is not None

def test_router_endpoints():
    """Test that the router has the expected endpoints."""
    from app.plugins.file_storage import router
    routes = [route.path for route in router.routes]
    
    # Check if essential endpoints are present
    essential_paths = [
        "/file-storage/providers",
        "/file-storage/files/upload",
        "/file-storage/folders",
        "/file-storage/images/thumbnails/{file_id}"
    ]
    
    for path in essential_paths:
        assert any(path in route for route in routes), f"Missing endpoint: {path}"
