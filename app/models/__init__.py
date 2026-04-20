# app/models/__init__.py

from app.core.db import Base  # <-- Import from db.py

# Advanced Audit models
from app.plugins.advanced_audit.models import AuditLog

# Authentication models
from app.plugins.advanced_auth.models import User, Role, Permission, Group, user_group, role_permission, Session, AccessToken, MFAMethod, MFAMethodType, VerificationCode

# I18n models
from app.plugins.advanced_i18n.models import Translation, Language, TranslationGroup, TranslationHistory

# Advanced scheduler models
from app.plugins.advanced_scheduler.models import ScheduledJob


# AI integration models
from app.plugins.ai_integration.models import AIProvider, AIModel, AIUsageRecord, TextAnalysisResult, ContentRecommendation, AIEmbedding

# API Gateway models
from app.plugins.api_gateway.models import ApiKeyDB, ApiPermissionDB, RateLimitDB, ApiAuditLogDB


# API Versionning models
from app.plugins.api_versioning.models import APIVersion, APIEndpoint, APIChange

# Business alerts models
from app.plugins.business_alerts.models import BusinessAlertDB, AlertRuleDB


# Data exchange models
from app.plugins.data_exchange.models import ImportExportJob, ImportExportTemplate, ImportExportSchedule, ValidationRule

# Digital signature models
from app.plugins.digital_signature.models import SignatureDB, TimestampDB, EvidenceDB

# File storage models
from app.plugins.file_storage.models import StorageProvider, StoredFile, FileThumbnail, FileFolder, FileFolderAssociation

# KYC models
from app.plugins.kyc.models import KycVerificationDB, VerificationStatus, VerificationType, IdentityDocument, RiskLevel, KycRegionDB, InfrastructureLevel, KycUserProfileDB, ProfileStatus

# Messaging Service models
from app.plugins.messaging_service.models import ConversationDB, GroupChatDB, UserBlockDB, MessageDB, MessageReactionDB, MessageReceiptDB, UserConversationSettingsDB, MessageAttachmentDB, MessageDeliveryStatusDB, ConversationType, conversation_participants

# Offline sync models
from app.plugins.offline_sync.models import SyncOperationDB, SyncBatchDB, SyncConfigDB, SyncStatus, SyncPriority

# Payment models
from app.plugins.payment.models import ProviderResponse, PaymentDB, PaymentRefundDB, PaymentTransactionDB, PaymentApprovalStepDB, payment_approver

# Privacy compliance models
from app.plugins.privacy_compliance.models import CookieCategory, Cookie, CookieSettings, UserConsent, DataRequest, ExportedData, DataProcessingRecord, PrivacyPolicy, AnonymizationLog, cookie_category_settings

# Push notification models
from app.plugins.push_notifications.models import Device, Notification, NotificationDevice, NotificationSegment

# PWA Support models
from app.plugins.pwa_support.models import PWASettings, NotificationSegment, NotificationHistory, NotificationReceipt

# Recommendation models
from app.plugins.recommendation.models import InteractionDB, RecommendationDB, UserPreferenceDB, ItemFeatureDB, SimilarityMatrixDB, ItemSimilarityDB

# Security models
from app.plugins.security.models import UserSession

# Social subscriptions models
from app.plugins.social_subscriptions.models import Subscription, ActivityEvent, FeedItem, NotificationRecord, UserPreference

# Webhooks models
from app.plugins.webhooks.models import WebhookSubscription

# Workflow models
from app.plugins.workflow.models import Workflow, WorkflowStep, WorkflowState, WorkflowTransition, WorkflowInstance, StepApproval, WorkflowHistory

# User analytics models
from app.plugins.matomo_integration.models import MatomoSettings, MatomoUserMapping, MatomoEmbedConfig

## Specif Models
from .test import Test
from .veille import Article
from .petro import Product, Client, Purchase, PurchaseTax, Storage, Sale, StockMovement