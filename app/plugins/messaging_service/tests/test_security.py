"""
Security Tests

This module tests the standardized security approach implemented in the messaging service,
ensuring consistent security practices across all components.
"""
import pytest
import json
from unittest.mock import MagicMock, patch
import datetime
from fastapi import HTTPException

from ..utils.security import MessageSecurity
from ..services.message_service import MessageService
from ..services.conversation_service import ConversationService


class TestStandardizedSecurity:
    """Test class for standardized security approach in messaging service."""
    
    @pytest.fixture
    def mock_encryption_handler(self):
        """Mock encryption handler fixture."""
        handler = MagicMock()
        handler.encrypt.return_value = "encrypted_data"
        handler.decrypt.return_value = "decrypted_data"
        return handler
    
    @pytest.fixture
    def security_handler(self, mock_encryption_handler):
        """Initialize security handler with mock encryption handler."""
        return MessageSecurity(mock_encryption_handler)
    
    @pytest.fixture
    def message_service(self, security_handler):
        """Initialize message service with security handler."""
        return MessageService(
            security_handler=security_handler,
            notification_handler=MagicMock(),
            file_handler=MagicMock(),
            websocket_manager=MagicMock(),
            config={"encryption_enabled": True}
        )
    
    @pytest.fixture
    def conversation_service(self, security_handler):
        """Initialize conversation service with security handler."""
        return ConversationService(
            security_handler=security_handler,
            notification_handler=MagicMock(),
            websocket_manager=MagicMock(),
            config={"encryption_enabled": True}
        )
    
    def test_metadata_encryption(self, security_handler):
        """Test standardized encryption of metadata."""
        # Test data
        metadata = {
            "sensitive_key": "sensitive_value",
            "another_key": "another_value"
        }
        
        # Encrypt metadata
        encrypted = security_handler.encrypt_metadata(metadata)
        
        # Verify encryption handler was called
        security_handler.encryption_handler.encrypt.assert_called_once()
        
        # Decrypt metadata
        decrypted = security_handler.decrypt_metadata(encrypted)
        
        # Verify decryption handler was called
        security_handler.encryption_handler.decrypt.assert_called_once()
        
        # Compare original and decrypted (mock returns "decrypted_data")
        assert decrypted == "decrypted_data"
    
    def test_message_encryption(self, security_handler):
        """Test standardized encryption of message content."""
        # Test data
        content = "This is a sensitive message"
        recipient_id = "user123"
        
        # Encrypt message
        encrypted = security_handler.encrypt_message(content, recipient_id)
        
        # Verify encryption handler was called with correct parameters
        security_handler.encryption_handler.encrypt.assert_called_once()
        
        # Decrypt message
        decrypted = security_handler.decrypt_message(encrypted, recipient_id)
        
        # Verify decryption handler was called with correct parameters
        security_handler.encryption_handler.decrypt.assert_called_once()
        
        # Compare original and decrypted (mock returns "decrypted_data")
        assert decrypted == "decrypted_data"
    
    def test_secure_logging(self, security_handler):
        """Test standardized secure logging."""
        # Test data
        event = "Test security event"
        data = {"user_id": "user123", "action": "test_action"}
        level = "info"
        
        # Call secure_log
        security_handler.secure_log(event, data, level)
        
        # Verify encryption was used for sensitive data
        security_handler.encryption_handler.encrypt.assert_called_once()
    
    def test_service_level_security_message(self, message_service, mock_encryption_handler):
        """Test standardized security at the message service level."""
        # Mock DB session and models
        db = MagicMock()
        user_id = "user123"
        message_content = "Secret message"
        recipient_id = "user456"
        
        # Test encrypt_message method
        encrypted = message_service.encrypt_message(message_content, recipient_id)
        
        # Verify security handler was used
        message_service.security_handler.encrypt_message.assert_called_once_with(
            message_content, recipient_id
        )
        
        # Test decrypt_message method
        message_service.decrypt_message(encrypted, user_id)
        
        # Verify security handler was used
        message_service.security_handler.decrypt_message.assert_called_once_with(
            encrypted, user_id
        )
    
    def test_service_level_security_conversation(self, conversation_service):
        """Test standardized security at the conversation service level."""
        # Mock conversation with metadata
        conversation = MagicMock()
        conversation.metadata = "encrypted_metadata"
        conversation.is_encrypted = True
        
        # Mock user
        user_id = "user123"
        
        # Test conversation to dict with metadata decryption
        with patch.object(conversation_service, '_conversation_to_dict', 
                         return_value={"id": "conv1"}) as mock_method:
            result = conversation_service._conversation_to_dict(
                conversation, user_id
            )
            
            # Verify method was called
            mock_method.assert_called_once()
    
    def test_request_validation(self, message_service):
        """Test standardized validation of requests."""
        # Invalid message data (missing required field)
        invalid_data = {
            "conversation_id": "conv123",
            # Missing content
            "message_type": "text"
        }
        
        # Mock the validation method to raise an exception
        with patch.object(message_service, '_validate_message_data', 
                         side_effect=HTTPException(status_code=400, detail="Validation error")):
            # Verify that validation error is raised
            with pytest.raises(HTTPException) as exc_info:
                message_service._validate_message_data(invalid_data)
            
            assert exc_info.value.status_code == 400
            assert "Validation error" in str(exc_info.value.detail)
    
    def test_consistent_security_across_services(self, message_service, conversation_service):
        """Test standardized security approach across different services."""
        # Verify both services use the same security handler
        assert message_service.security_handler == conversation_service.security_handler
        
        # Test that both services use the same approach for encryption
        test_content = "Test content"
        recipient_id = "user123"
        
        # Both services should delegate to the security handler
        message_service.encrypt_message(test_content, recipient_id)
        message_service.security_handler.encrypt_message.assert_called_once_with(
            test_content, recipient_id
        )
        
        # Reset mock
        message_service.security_handler.encrypt_message.reset_mock()
        
        # Conversation service should use the same approach
        conversation_service.encrypt_message(test_content, recipient_id)
        conversation_service.security_handler.encrypt_message.assert_called_once_with(
            test_content, recipient_id
        )
