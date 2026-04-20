# File Storage Plugin

A powerful and flexible file storage plugin for Kaapi applications that supports multiple storage backends.

## Features

- **Multiple Storage Providers**: Supports MinIO, AWS S3, and Google Cloud Storage
- **Thumbnails Generation**: Automatically generate thumbnails for images
- **Image Processing**: Comprehensive image manipulation capabilities
  - Resize, crop, rotate, and apply filters
  - Optimize images for web use
  - Add watermarks
- **Organization**: Virtual folder structure for better file organization
- **Flexible API**: Easy-to-use REST API for all operations

## Dependencies

The plugin requires the following dependencies:

```
# Main dependencies
minio>=7.1.15  # MinIO client
boto3>=1.26.0  # AWS S3 client
google-cloud-storage>=2.7.0  # Google Cloud Storage client
Pillow>=9.4.0  # Image processing

# Optional dependencies
python-multipart>=0.0.5  # For file upload handling via FastAPI
webp>=0.1.0  # Optional WebP support
```

## Installation

1. Ensure the plugin directory is in your app's plugins folder
2. Install the required dependencies:

```bash
pip install -r app/plugins/file_storage/requirements.txt
```

3. Add the plugin to your FastAPI app:

```python
from app.plugins.file_storage import router as file_storage_router

app.include_router(file_storage_router)
```

## Configuration

Configure your storage providers through the API or directly in the database:

```python
storage_provider = {
    "name": "MinIO Local",
    "provider_type": "minio",
    "bucket_name": "files",
    "endpoint_url": "http://localhost:9000",
    "access_key": "minioadmin",
    "secret_key": "minioadmin",
    "is_default": True
}
```

## Usage Examples

### Upload a File

```python
import requests

files = {'file': open('image.jpg', 'rb')}
data = {'provider_id': 1, 'is_public': True}
response = requests.post('http://localhost:8000/api/file-storage/files/upload', files=files, data=data)
file_info = response.json()
```

### Generate Thumbnails

```python
response = requests.post(
    'http://localhost:8000/api/file-storage/images/thumbnails/1',
    json={'sizes': ['sm', 'md', 'lg']}
)
thumbnails = response.json()
```

### Download a File

```python
response = requests.get('http://localhost:8000/api/file-storage/files/1/download')
with open('downloaded_file.jpg', 'wb') as f:
    f.write(response.content)
```

## API Endpoints

### Storage Providers
- `POST /file-storage/providers` - Create a new storage provider
- `GET /file-storage/providers` - List all storage providers
- `GET /file-storage/providers/{id}` - Get provider details
- `PUT /file-storage/providers/{id}` - Update a provider
- `DELETE /file-storage/providers/{id}` - Delete a provider

### Files
- `POST /file-storage/files/upload` - Upload a file
- `GET /file-storage/files` - List all files
- `GET /file-storage/files/{id}` - Get file details
- `GET /file-storage/files/{id}/download` - Download a file
- `DELETE /file-storage/files/{id}` - Delete a file

### Folders
- `POST /file-storage/folders` - Create a folder
- `GET /file-storage/folders` - List folders
- `GET /file-storage/folders/{id}` - Get folder details
- `PUT /file-storage/folders/{id}` - Update a folder
- `DELETE /file-storage/folders/{id}` - Delete a folder

### Images
- `POST /file-storage/images/thumbnails/{file_id}` - Generate thumbnails
- `POST /file-storage/images/transform` - Transform an image
- `POST /file-storage/images/optimize` - Optimize an image
- `GET /file-storage/images/{file_id}/info` - Get image info

## License

This plugin is licensed under the same terms as the main Kaapi application.
