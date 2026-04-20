# Database Schema

## ai_content_recommendations

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('ai_content_recommendations_id_seq'::regclass) | Yes |
| user_id | UUID | No | - | No |
| content_type | VARCHAR(50) | No | - | No |
| content_id | INTEGER | No | - | No |
| score | DOUBLE PRECISION | No | - | No |
| reason | VARCHAR(500) | Yes | - | No |
| created_at | TIMESTAMP | Yes | - | No |
| expires_at | TIMESTAMP | Yes | - | No |
| is_dismissed | BOOLEAN | Yes | - | No |
| model_id | INTEGER | No | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| model_id | ai_models.id | NO ACTION | NO ACTION |
| user_id | user.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_ai_content_recommendations_id | id | No |

## ai_embeddings

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('ai_embeddings_id_seq'::regclass) | Yes |
| entity_type | VARCHAR(50) | No | - | No |
| entity_id | INTEGER | No | - | No |
| embedding_vector | TEXT | No | - | No |
| dimensions | INTEGER | No | - | No |
| model_id | INTEGER | No | - | No |
| created_at | TIMESTAMP | Yes | - | No |
| updated_at | TIMESTAMP | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| model_id | ai_models.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_ai_embeddings_id | id | No |

## ai_models

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('ai_models_id_seq'::regclass) | Yes |
| provider_id | INTEGER | No | - | No |
| name | VARCHAR(255) | No | - | No |
| model_type | VARCHAR(10) | No | - | No |
| model_id | VARCHAR(255) | No | - | No |
| version | VARCHAR(50) | Yes | - | No |
| capabilities | JSON | Yes | - | No |
| default_params | JSON | Yes | - | No |
| max_tokens | INTEGER | Yes | - | No |
| is_active | BOOLEAN | Yes | - | No |
| cost_per_1k_tokens | DOUBLE PRECISION | Yes | - | No |
| created_at | TIMESTAMP | Yes | - | No |
| updated_at | TIMESTAMP | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| provider_id | ai_providers.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_ai_models_model_type | model_type | No |
| ix_ai_models_id | id | No |

## ai_providers

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('ai_providers_id_seq'::regclass) | Yes |
| name | VARCHAR(255) | No | - | No |
| provider_type | VARCHAR(13) | No | - | No |
| is_default | BOOLEAN | Yes | - | No |
| is_active | BOOLEAN | Yes | - | No |
| base_url | VARCHAR(255) | Yes | - | No |
| config | JSON | Yes | - | No |
| api_key | VARCHAR(255) | Yes | - | No |
| api_secret | VARCHAR(255) | Yes | - | No |
| created_at | TIMESTAMP | Yes | - | No |
| updated_at | TIMESTAMP | Yes | - | No |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_ai_providers_name | name | No |
| ix_ai_providers_provider_type | provider_type | No |
| ix_ai_providers_id | id | No |

## ai_text_analysis_results

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('ai_text_analysis_results_id_seq'::regclass) | Yes |
| entity_type | VARCHAR(50) | No | - | No |
| entity_id | INTEGER | No | - | No |
| language | VARCHAR(10) | Yes | - | No |
| sentiment_score | DOUBLE PRECISION | Yes | - | No |
| sentiment_magnitude | DOUBLE PRECISION | Yes | - | No |
| sentiment_label | VARCHAR(20) | Yes | - | No |
| categories | JSON | Yes | - | No |
| entities | JSON | Yes | - | No |
| keywords | JSON | Yes | - | No |
| summary | TEXT | Yes | - | No |
| model_id | INTEGER | No | - | No |
| processed_at | TIMESTAMP | Yes | - | No |
| processing_time_ms | INTEGER | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| model_id | ai_models.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_ai_text_analysis_results_id | id | No |

## ai_usage_records

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('ai_usage_records_id_seq'::regclass) | Yes |
| provider_id | INTEGER | No | - | No |
| model_id | INTEGER | No | - | No |
| user_id | UUID | Yes | - | No |
| input_tokens | INTEGER | Yes | - | No |
| output_tokens | INTEGER | Yes | - | No |
| total_tokens | INTEGER | Yes | - | No |
| request_type | VARCHAR(50) | No | - | No |
| request_id | VARCHAR(255) | Yes | - | No |
| prompt_summary | VARCHAR(1000) | Yes | - | No |
| cost | DOUBLE PRECISION | Yes | - | No |
| created_at | TIMESTAMP | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| model_id | ai_models.id | NO ACTION | NO ACTION |
| provider_id | ai_providers.id | NO ACTION | NO ACTION |
| user_id | user.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_ai_usage_records_id | id | No |

## alembic_version

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| version_num | VARCHAR(32) | No | - | Yes |

## alert_rules

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | VARCHAR(36) | No | - | Yes |
| name | VARCHAR(100) | No | - | No |
| description | VARCHAR(500) | Yes | - | No |
| entity_type | VARCHAR(50) | No | - | No |
| alert_type | VARCHAR(50) | No | - | No |
| condition | JSON | No | - | No |
| severity | VARCHAR(20) | No | - | No |
| message_template | VARCHAR(500) | No | - | No |
| is_active | BOOLEAN | Yes | - | No |
| check_frequency | VARCHAR(50) | Yes | - | No |
| created_at | TIMESTAMP | Yes | - | No |
| updated_at | TIMESTAMP | Yes | - | No |
| created_by | VARCHAR(36) | Yes | - | No |
| priority | INTEGER | Yes | - | No |

## api_changes

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('api_changes_id_seq'::regclass) | Yes |
| previous_version_id | INTEGER | Yes | - | No |
| new_version_id | INTEGER | Yes | - | No |
| endpoint_path | VARCHAR | Yes | - | No |
| change_type | VARCHAR | Yes | - | No |
| description | VARCHAR | Yes | - | No |
| details | JSON | Yes | - | No |
| created_at | TIMESTAMP | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| new_version_id | api_versions.id | NO ACTION | NO ACTION |
| previous_version_id | api_versions.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_api_changes_endpoint_path | endpoint_path | No |
| ix_api_changes_id | id | No |

## api_endpoints

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('api_endpoints_id_seq'::regclass) | Yes |
| path | VARCHAR | Yes | - | No |
| method | VARCHAR | Yes | - | No |
| version_id | INTEGER | Yes | - | No |
| description | VARCHAR | Yes | - | No |
| handler_module | VARCHAR | Yes | - | No |
| handler_function | VARCHAR | Yes | - | No |
| parameters | JSON | Yes | - | No |
| response_model | JSON | Yes | - | No |
| created_at | TIMESTAMP | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| version_id | api_versions.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_api_endpoints_path | path | No |
| ix_api_endpoints_method | method | No |
| ix_api_endpoints_id | id | No |

## api_gateway_audit_logs

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | VARCHAR(36) | No | - | Yes |
| api_key_id | VARCHAR(36) | Yes | - | No |
| request_id | VARCHAR(36) | No | - | No |
| path | VARCHAR(255) | No | - | No |
| method | VARCHAR(10) | No | - | No |
| endpoint | VARCHAR(255) | No | - | No |
| ip_address | VARCHAR(50) | Yes | - | No |
| user_agent | VARCHAR(255) | Yes | - | No |
| origin | VARCHAR(255) | Yes | - | No |
| status_code | INTEGER | Yes | - | No |
| response_time_ms | INTEGER | Yes | - | No |
| request_data | JSON | Yes | - | No |
| request_headers | JSON | Yes | - | No |
| is_authorized | BOOLEAN | No | - | No |
| auth_failure_reason | VARCHAR(255) | Yes | - | No |
| is_rate_limited | BOOLEAN | No | - | No |
| created_at | TIMESTAMP | No | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| api_key_id | api_gateway_keys.id | CASCADE | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_api_gateway_audit_logs_id | id | No |
| ix_api_gateway_audit_logs_request_id | request_id | No |

## api_gateway_keys

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | VARCHAR(36) | No | - | Yes |
| name | VARCHAR(100) | No | - | No |
| prefix | VARCHAR(8) | No | - | No |
| hashed_key | VARCHAR(255) | No | - | No |
| owner_id | VARCHAR(36) | No | - | No |
| owner_type | VARCHAR(50) | No | - | No |
| created_at | TIMESTAMP | No | - | No |
| expires_at | TIMESTAMP | Yes | - | No |
| is_active | BOOLEAN | No | - | No |
| rate_limit_per_minute | INTEGER | Yes | - | No |
| rate_limit_per_hour | INTEGER | Yes | - | No |
| rate_limit_per_day | INTEGER | Yes | - | No |
| allowed_ips | JSON | Yes | - | No |
| allowed_origins | JSON | Yes | - | No |
| last_used_at | TIMESTAMP | Yes | - | No |
| use_count | INTEGER | No | - | No |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_api_gateway_keys_owner_id | owner_id | No |
| ix_api_gateway_keys_id | id | No |
| ix_api_gateway_keys_prefix | prefix | Yes |

## api_gateway_permissions

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | VARCHAR(36) | No | - | Yes |
| api_key_id | VARCHAR(36) | No | - | No |
| namespace | VARCHAR(50) | No | - | No |
| resource | VARCHAR(50) | No | - | No |
| action | VARCHAR(50) | No | - | No |
| created_at | TIMESTAMP | No | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| api_key_id | api_gateway_keys.id | CASCADE | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_api_gateway_permissions_id | id | No |

## api_gateway_rate_limits

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | VARCHAR(36) | No | - | Yes |
| api_key_id | VARCHAR(36) | No | - | No |
| path_pattern | VARCHAR(255) | No | - | No |
| window_size | VARCHAR(20) | No | - | No |
| window_start | TIMESTAMP | No | - | No |
| window_end | TIMESTAMP | No | - | No |
| request_count | INTEGER | No | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| api_key_id | api_gateway_keys.id | CASCADE | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_api_gateway_rate_limits_path_pattern | path_pattern | No |
| ix_api_gateway_rate_limits_window_start | window_start | No |
| ix_api_gateway_rate_limits_window_size | window_size | No |
| ix_api_gateway_rate_limits_id | id | No |

## api_versions

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('api_versions_id_seq'::regclass) | Yes |
| version | VARCHAR | Yes | - | No |
| description | VARCHAR | Yes | - | No |
| release_date | TIMESTAMP | Yes | - | No |
| is_current | BOOLEAN | Yes | - | No |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_api_versions_id | id | No |
| ix_api_versions_version | version | Yes |

## articles

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('articles_id_seq'::regclass) | Yes |
| url | VARCHAR(1024) | No | - | No |
| title | TEXT | No | - | No |
| source | VARCHAR(100) | No | - | No |
| date | VARCHAR(50) | Yes | - | No |
| content | TEXT | Yes | - | No |
| published | BOOLEAN | No | - | No |
| error | TEXT | Yes | - | No |
| score_pertinence | INTEGER | Yes | - | No |
| analysis | JSON | Yes | - | No |
| analysis_date | TIMESTAMP | No | now() | No |
| sujet_cluster | VARCHAR(255) | Yes | - | No |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_articles_url | url | Yes |
| ix_articles_published | published | No |
| ix_articles_sujet_cluster | sujet_cluster | No |
| ix_articles_id | id | No |
| ix_articles_score_pertinence | score_pertinence | No |

## audit_logs

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('audit_logs_id_seq'::regclass) | Yes |
| user_id | INTEGER | Yes | - | No |
| action | VARCHAR(100) | No | - | No |
| resource | VARCHAR(100) | No | - | No |
| details | TEXT | Yes | - | No |
| created_at | TIMESTAMP | Yes | - | No |

## auth_access_token

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | UUID | No | - | Yes |
| user_id | UUID | No | - | No |
| token | VARCHAR | No | - | No |
| scope | VARCHAR | Yes | - | No |
| client_id | VARCHAR | Yes | - | No |
| expires_at | TIMESTAMP | No | - | No |
| is_active | BOOLEAN | Yes | - | No |
| created_at | TIMESTAMP | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| user_id | user.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_auth_access_token_token | token | Yes |

## auth_group

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | UUID | No | - | Yes |
| name | VARCHAR(100) | No | - | No |
| description | VARCHAR(255) | Yes | - | No |
| is_system_group | BOOLEAN | Yes | - | No |
| created_at | TIMESTAMP | Yes | - | No |
| updated_at | TIMESTAMP | Yes | - | No |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_auth_group_id | id | No |

## auth_mfa_method

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | UUID | No | - | Yes |
| user_id | UUID | No | - | No |
| method_type | VARCHAR(14) | No | - | No |
| name | VARCHAR(100) | Yes | - | No |
| is_primary | BOOLEAN | Yes | - | No |
| is_active | BOOLEAN | Yes | - | No |
| secret | VARCHAR | Yes | - | No |
| data | JSON | Yes | - | No |
| created_at | TIMESTAMP | Yes | - | No |
| updated_at | TIMESTAMP | Yes | - | No |
| last_used_at | TIMESTAMP | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| user_id | user.id | NO ACTION | NO ACTION |

## auth_permission

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | UUID | No | - | Yes |
| name | VARCHAR(100) | No | - | No |
| description | VARCHAR(255) | Yes | - | No |
| code | VARCHAR(100) | No | - | No |
| resource | VARCHAR(100) | No | - | No |
| action | VARCHAR(50) | No | - | No |
| is_system_permission | BOOLEAN | Yes | - | No |
| created_at | TIMESTAMP | Yes | - | No |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_auth_permission_id | id | No |

## auth_role

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | UUID | No | - | Yes |
| name | VARCHAR(50) | No | - | No |
| description | VARCHAR(255) | Yes | - | No |
| is_system_role | BOOLEAN | Yes | - | No |
| created_at | TIMESTAMP | Yes | - | No |
| updated_at | TIMESTAMP | Yes | - | No |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_auth_role_id | id | No |

## auth_role_permission

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| role_id | UUID | No | - | Yes |
| permission_id | UUID | No | - | Yes |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| permission_id | auth_permission.id | NO ACTION | NO ACTION |
| role_id | auth_role.id | NO ACTION | NO ACTION |

## auth_session

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | UUID | No | - | Yes |
| user_id | UUID | No | - | No |
| token | VARCHAR | No | - | No |
| refresh_token | VARCHAR | Yes | - | No |
| expires_at | TIMESTAMP | No | - | No |
| refresh_token_expires_at | TIMESTAMP | Yes | - | No |
| is_active | BOOLEAN | Yes | - | No |
| device_type | VARCHAR(50) | Yes | - | No |
| device_name | VARCHAR(100) | Yes | - | No |
| browser | VARCHAR(100) | Yes | - | No |
| browser_version | VARCHAR(50) | Yes | - | No |
| os | VARCHAR(50) | Yes | - | No |
| os_version | VARCHAR(50) | Yes | - | No |
| ip_address | VARCHAR(50) | Yes | - | No |
| location | VARCHAR(100) | Yes | - | No |
| user_agent | TEXT | Yes | - | No |
| created_at | TIMESTAMP | Yes | - | No |
| updated_at | TIMESTAMP | Yes | - | No |
| last_activity | TIMESTAMP | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| user_id | user.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_auth_session_token | token | Yes |
| ix_auth_session_refresh_token | refresh_token | Yes |

## auth_verification_code

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | UUID | No | - | Yes |
| user_id | UUID | No | - | No |
| code | VARCHAR(64) | No | - | No |
| purpose | VARCHAR(50) | No | - | No |
| expires_at | TIMESTAMP | No | - | No |
| is_used | BOOLEAN | Yes | - | No |
| used_at | TIMESTAMP | Yes | - | No |
| attempt_count | INTEGER | Yes | - | No |
| created_at | TIMESTAMP | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| user_id | user.id | NO ACTION | NO ACTION |

## business_alerts

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | VARCHAR(36) | No | - | Yes |
| entity_type | VARCHAR(50) | No | - | No |
| entity_id | VARCHAR(36) | No | - | No |
| alert_type | VARCHAR(50) | No | - | No |
| severity | VARCHAR(20) | No | - | No |
| message | VARCHAR(500) | No | - | No |
| details | JSON | Yes | - | No |
| status | VARCHAR(20) | No | - | No |
| created_at | TIMESTAMP | No | - | No |
| updated_at | TIMESTAMP | Yes | - | No |
| resolved_at | TIMESTAMP | Yes | - | No |
| acknowledged_at | TIMESTAMP | Yes | - | No |
| acknowledged_by | VARCHAR(36) | Yes | - | No |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_business_alerts_alert_type | alert_type | No |
| ix_business_alerts_entity_id | entity_id | No |
| ix_business_alerts_entity_type | entity_type | No |

## clients

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('clients_id_seq'::regclass) | Yes |
| name | VARCHAR(255) | No | - | No |
| client_type | VARCHAR(100) | No | - | No |
| country | VARCHAR(100) | No | - | No |
| is_active | BOOLEAN | No | - | No |
| created_at | TIMESTAMP | No | now() | No |
| organization_id | INTEGER | No | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| organization_id | organizations.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_clients_id | id | No |
| ix_clients_name | name | No |

## data_exchange_jobs

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('data_exchange_jobs_id_seq'::regclass) | Yes |
| name | VARCHAR(100) | No | - | No |
| description | TEXT | Yes | - | No |
| is_import | BOOLEAN | Yes | - | No |
| format_type | VARCHAR(5) | No | - | No |
| source_path | VARCHAR(255) | No | - | No |
| target_entity | VARCHAR(255) | No | - | No |
| configuration | JSON | Yes | - | No |
| template_id | INTEGER | Yes | - | No |
| schedule_id | INTEGER | Yes | - | No |
| status | VARCHAR(9) | Yes | - | No |
| started_at | TIMESTAMP | Yes | - | No |
| completed_at | TIMESTAMP | Yes | - | No |
| error_message | TEXT | Yes | - | No |
| records_processed | INTEGER | Yes | - | No |
| records_succeeded | INTEGER | Yes | - | No |
| records_failed | INTEGER | Yes | - | No |
| result_log | JSON | Yes | - | No |
| user_id | UUID | No | - | No |
| created_at | TIMESTAMP | Yes | - | No |
| updated_at | TIMESTAMP | Yes | - | No |
| is_active | BOOLEAN | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| schedule_id | data_exchange_schedules.id | NO ACTION | NO ACTION |
| template_id | data_exchange_templates.id | NO ACTION | NO ACTION |
| user_id | user.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_data_exchange_jobs_id | id | No |

## data_exchange_schedules

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('data_exchange_schedules_id_seq'::regclass) | Yes |
| name | VARCHAR(100) | No | - | No |
| description | TEXT | Yes | - | No |
| frequency | VARCHAR(7) | No | - | No |
| start_date | TIMESTAMP | No | - | No |
| end_date | TIMESTAMP | Yes | - | No |
| cron_expression | VARCHAR(100) | Yes | - | No |
| parameters | JSON | Yes | - | No |
| user_id | UUID | No | - | No |
| created_at | TIMESTAMP | Yes | - | No |
| updated_at | TIMESTAMP | Yes | - | No |
| is_active | BOOLEAN | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| user_id | user.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_data_exchange_schedules_id | id | No |

## data_exchange_templates

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('data_exchange_templates_id_seq'::regclass) | Yes |
| name | VARCHAR(100) | No | - | No |
| description | TEXT | Yes | - | No |
| is_import | BOOLEAN | Yes | - | No |
| format_type | VARCHAR(5) | No | - | No |
| target_entity | VARCHAR(255) | No | - | No |
| configuration | JSON | No | - | No |
| user_id | UUID | No | - | No |
| created_at | TIMESTAMP | Yes | - | No |
| updated_at | TIMESTAMP | Yes | - | No |
| is_active | BOOLEAN | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| user_id | user.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_data_exchange_templates_id | id | No |

## data_exchange_validation_rules

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('data_exchange_validation_rules_id_seq'::regclass) | Yes |
| name | VARCHAR(100) | No | - | No |
| description | TEXT | Yes | - | No |
| rule_type | VARCHAR(50) | No | - | No |
| configuration | JSON | No | - | No |
| field_name | VARCHAR(100) | No | - | No |
| target_entity | VARCHAR(255) | No | - | No |
| user_id | UUID | No | - | No |
| created_at | TIMESTAMP | Yes | - | No |
| updated_at | TIMESTAMP | Yes | - | No |
| is_active | BOOLEAN | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| user_id | user.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_data_exchange_validation_rules_id | id | No |

## digital_signature_evidence

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | VARCHAR | No | - | Yes |
| signature_id | VARCHAR | No | - | No |
| created_at | TIMESTAMP | No | - | No |
| certificate_chain | TEXT | Yes | - | No |
| timestamp_proof | TEXT | Yes | - | No |
| validation_data | TEXT | Yes | - | No |
| evidence_format | VARCHAR | No | - | No |
| is_long_term | BOOLEAN | No | - | No |
| expires_at | TIMESTAMP | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| signature_id | digital_signatures.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_digital_signature_evidence_signature_id | signature_id | No |
| ix_digital_signature_evidence_id | id | No |

## digital_signatures

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | VARCHAR | No | - | Yes |
| document_hash | VARCHAR | No | - | No |
| document_name | VARCHAR | No | - | No |
| signature_data | BYTEA | No | - | No |
| signature_type | VARCHAR | No | - | No |
| created_at | TIMESTAMP | No | - | No |
| user_id | VARCHAR | No | - | No |
| description | TEXT | Yes | - | No |
| signer_info | VARCHAR | Yes | - | No |
| certificate_id | VARCHAR | Yes | - | No |
| is_active | BOOLEAN | No | - | No |
| revoked_at | TIMESTAMP | Yes | - | No |
| revocation_reason | VARCHAR | Yes | - | No |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_digital_signatures_document_hash | document_hash | No |
| ix_digital_signatures_id | id | No |
| ix_digital_signatures_user_id | user_id | No |

## digital_timestamps

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | VARCHAR | No | - | Yes |
| data_hash | VARCHAR | No | - | No |
| data_source | VARCHAR | Yes | - | No |
| timestamp | TIMESTAMP | No | - | No |
| timestamp_token | TEXT | No | - | No |
| user_id | VARCHAR | No | - | No |
| description | TEXT | Yes | - | No |
| created_at | TIMESTAMP | No | - | No |
| is_valid | BOOLEAN | No | - | No |
| verification_count | INTEGER | No | - | No |
| last_verified_at | TIMESTAMP | Yes | - | No |
| certificate_id | VARCHAR | Yes | - | No |
| long_term_verification_data | TEXT | Yes | - | No |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_digital_timestamps_data_hash | data_hash | No |
| ix_digital_timestamps_user_id | user_id | No |
| ix_digital_timestamps_id | id | No |

## file_storage_files

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('file_storage_files_id_seq'::regclass) | Yes |
| provider_id | INTEGER | No | - | No |
| filename | VARCHAR(255) | No | - | No |
| original_filename | VARCHAR(255) | No | - | No |
| storage_path | VARCHAR(512) | No | - | No |
| file_size | INTEGER | No | - | No |
| mime_type | VARCHAR(255) | No | - | No |
| content_hash | VARCHAR(128) | Yes | - | No |
| file_metadata | JSON | Yes | - | No |
| is_public | BOOLEAN | Yes | - | No |
| access_token | VARCHAR(128) | Yes | - | No |
| token_expires_at | TIMESTAMP | Yes | - | No |
| uploaded_at | TIMESTAMP | Yes | - | No |
| updated_at | TIMESTAMP | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| provider_id | file_storage_providers.id | NO ACTION | NO ACTION |

## file_storage_folder_associations

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('file_storage_folder_associations_id_seq'::regclass) | Yes |
| file_id | INTEGER | No | - | No |
| folder_id | INTEGER | No | - | No |
| created_at | TIMESTAMP | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| file_id | file_storage_files.id | NO ACTION | NO ACTION |
| folder_id | file_storage_folders.id | NO ACTION | NO ACTION |

## file_storage_folders

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('file_storage_folders_id_seq'::regclass) | Yes |
| name | VARCHAR(255) | No | - | No |
| parent_id | INTEGER | Yes | - | No |
| file_metadata | JSON | Yes | - | No |
| created_at | TIMESTAMP | Yes | - | No |
| updated_at | TIMESTAMP | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| parent_id | file_storage_folders.id | NO ACTION | NO ACTION |

## file_storage_providers

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('file_storage_providers_id_seq'::regclass) | Yes |
| name | VARCHAR(100) | No | - | No |
| provider_type | VARCHAR(50) | No | - | No |
| is_default | BOOLEAN | Yes | - | No |
| is_active | BOOLEAN | Yes | - | No |
| bucket_name | VARCHAR(100) | No | - | No |
| region | VARCHAR(50) | Yes | - | No |
| endpoint_url | VARCHAR(255) | Yes | - | No |
| access_key | VARCHAR(255) | Yes | - | No |
| secret_key | VARCHAR(255) | Yes | - | No |
| config_options | JSON | Yes | - | No |
| created_at | TIMESTAMP | Yes | - | No |
| updated_at | TIMESTAMP | Yes | - | No |

## file_storage_thumbnails

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('file_storage_thumbnails_id_seq'::regclass) | Yes |
| original_file_id | INTEGER | No | - | No |
| size | VARCHAR(20) | No | - | No |
| width | INTEGER | Yes | - | No |
| height | INTEGER | Yes | - | No |
| storage_path | VARCHAR(512) | No | - | No |
| file_size | INTEGER | No | - | No |
| created_at | TIMESTAMP | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| original_file_id | file_storage_files.id | NO ACTION | NO ACTION |

## i18n_languages

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('i18n_languages_id_seq'::regclass) | Yes |
| code | VARCHAR(10) | Yes | - | No |
| name | VARCHAR(50) | Yes | - | No |
| native_name | VARCHAR(50) | Yes | - | No |
| flag_code | VARCHAR(5) | Yes | - | No |
| is_rtl | BOOLEAN | Yes | - | No |
| is_default | BOOLEAN | Yes | - | No |
| is_enabled | BOOLEAN | Yes | - | No |
| created_at | TIMESTAMP | Yes | now() | No |
| updated_at | TIMESTAMP | Yes | now() | No |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_i18n_languages_code | code | Yes |

## i18n_translation_groups

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('i18n_translation_groups_id_seq'::regclass) | Yes |
| name | VARCHAR(100) | Yes | - | No |
| description | TEXT | Yes | - | No |
| created_at | TIMESTAMP | Yes | now() | No |
| updated_at | TIMESTAMP | Yes | now() | No |

## i18n_translation_history

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('i18n_translation_history_id_seq'::regclass) | Yes |
| translation_id | INTEGER | Yes | - | No |
| language_code | VARCHAR(10) | Yes | - | No |
| key | VARCHAR(255) | Yes | - | No |
| old_value | TEXT | Yes | - | No |
| new_value | TEXT | Yes | - | No |
| user_id | UUID | Yes | - | No |
| created_at | TIMESTAMP | Yes | now() | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| translation_id | i18n_translations.id | NO ACTION | NO ACTION |
| user_id | user.id | NO ACTION | NO ACTION |

## i18n_translations

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('i18n_translations_id_seq'::regclass) | Yes |
| language_id | INTEGER | Yes | - | No |
| group_id | INTEGER | Yes | - | No |
| key | VARCHAR(255) | Yes | - | No |
| value | TEXT | Yes | - | No |
| context | VARCHAR(100) | Yes | - | No |
| plural_forms | JSON | Yes | - | No |
| is_machine_translated | BOOLEAN | Yes | - | No |
| needs_review | BOOLEAN | Yes | - | No |
| created_at | TIMESTAMP | Yes | now() | No |
| updated_at | TIMESTAMP | Yes | now() | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| group_id | i18n_translation_groups.id | NO ACTION | NO ACTION |
| language_id | i18n_languages.id | NO ACTION | NO ACTION |

## kyc_regions

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | VARCHAR | No | - | Yes |
| name | VARCHAR | No | - | No |
| country_code | VARCHAR(2) | No | - | No |
| infrastructure_level | VARCHAR(8) | No | - | No |
| created_at | TIMESTAMP | No | - | No |
| updated_at | TIMESTAMP | No | - | No |
| required_documents | JSON | No | - | No |
| alternative_documents | JSON | Yes | - | No |
| simplified_kyc_threshold | INTEGER | Yes | - | No |
| regulatory_requirements | TEXT | Yes | - | No |
| risk_assessment_rules | JSON | Yes | - | No |
| verification_expiry_days | INTEGER | No | - | No |
| simplified_kyc_enabled | BOOLEAN | No | - | No |
| simplified_requirements | JSON | Yes | - | No |
| trusted_referee_types | JSON | Yes | - | No |
| description | TEXT | Yes | - | No |
| notes | TEXT | Yes | - | No |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_kyc_regions_name | name | Yes |
| ix_kyc_regions_country_code | country_code | No |

## kyc_user_profiles

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | VARCHAR | No | - | Yes |
| user_id | VARCHAR | No | - | No |
| status | VARCHAR(11) | No | - | No |
| created_at | TIMESTAMP | No | - | No |
| updated_at | TIMESTAMP | No | - | No |
| full_name | VARCHAR | Yes | - | No |
| date_of_birth | VARCHAR | Yes | - | No |
| nationality | VARCHAR | Yes | - | No |
| address | JSON | Yes | - | No |
| phone_number | VARCHAR | Yes | - | No |
| email | VARCHAR | Yes | - | No |
| tax_id | VARCHAR | Yes | - | No |
| occupation | VARCHAR | Yes | - | No |
| employer | VARCHAR | Yes | - | No |
| source_of_funds | VARCHAR | Yes | - | No |
| politically_exposed | BOOLEAN | Yes | - | No |
| is_encrypted | BOOLEAN | No | - | No |
| encryption_metadata | JSON | Yes | - | No |
| last_verified_at | TIMESTAMP | Yes | - | No |
| region_id | VARCHAR | Yes | - | No |
| audit_log | JSON | Yes | - | No |
| references | JSON | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| region_id | kyc_regions.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_kyc_user_profiles_user_id | user_id | Yes |

## kyc_verifications

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | VARCHAR | No | - | Yes |
| user_id | VARCHAR | No | - | No |
| verification_type | VARCHAR(10) | No | - | No |
| status | VARCHAR(22) | No | - | No |
| created_at | TIMESTAMP | No | - | No |
| updated_at | TIMESTAMP | No | - | No |
| expires_at | TIMESTAMP | Yes | - | No |
| submitted_data | JSON | Yes | - | No |
| verification_result | JSON | Yes | - | No |
| rejection_reason | TEXT | Yes | - | No |
| review_notes | TEXT | Yes | - | No |
| risk_level | VARCHAR(8) | No | - | No |
| risk_factors | JSON | Yes | - | No |
| documents_provided | JSON | Yes | - | No |
| verification_method | VARCHAR | Yes | - | No |
| verification_provider | VARCHAR | Yes | - | No |
| is_encrypted | BOOLEAN | No | - | No |
| encryption_metadata | JSON | Yes | - | No |
| profile_id | VARCHAR | Yes | - | No |
| region_id | VARCHAR | Yes | - | No |
| reviewed_by | VARCHAR | Yes | - | No |
| review_date | TIMESTAMP | Yes | - | No |
| audit_log | JSON | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| profile_id | kyc_user_profiles.id | NO ACTION | NO ACTION |
| region_id | kyc_regions.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_kyc_verifications_user_id | user_id | No |

## matomo_embed_configs

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | UUID | No | - | Yes |
| name | VARCHAR | No | - | No |
| embed_type | VARCHAR | No | - | No |
| embed_id | VARCHAR | Yes | - | No |
| date_range | VARCHAR | Yes | - | No |
| filters | JSON | Yes | - | No |
| position | INTEGER | Yes | - | No |
| visible | BOOLEAN | Yes | - | No |
| created_at | TIMESTAMP | Yes | now() | No |
| updated_at | TIMESTAMP | Yes | - | No |

## matomo_settings

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | UUID | No | - | Yes |
| matomo_url | VARCHAR | No | - | No |
| site_id | INTEGER | No | - | No |
| auth_token | VARCHAR | Yes | - | No |
| enabled | BOOLEAN | Yes | - | No |
| track_admin_users | BOOLEAN | Yes | - | No |
| heartbeat_timer | INTEGER | Yes | - | No |
| additional_settings | JSON | Yes | - | No |
| created_at | TIMESTAMP | Yes | now() | No |
| updated_at | TIMESTAMP | Yes | - | No |

## matomo_user_mappings

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | UUID | No | - | Yes |
| kaapi_user_id | UUID | No | - | No |
| matomo_user_id | VARCHAR | No | - | No |
| matomo_login | VARCHAR | Yes | - | No |
| access_level | VARCHAR | No | - | No |
| last_sync | TIMESTAMP | Yes | - | No |
| created_at | TIMESTAMP | Yes | now() | No |
| updated_at | TIMESTAMP | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| kaapi_user_id | user.id | NO ACTION | NO ACTION |

## messaging_attachments

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | VARCHAR(36) | No | - | Yes |
| message_id | VARCHAR(36) | No | - | No |
| file_name | VARCHAR(255) | No | - | No |
| file_type | VARCHAR(100) | No | - | No |
| file_size | INTEGER | No | - | No |
| file_path | VARCHAR(512) | No | - | No |
| is_image | BOOLEAN | Yes | - | No |
| thumbnail_path | VARCHAR(512) | Yes | - | No |
| created_at | TIMESTAMP | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| message_id | messaging_messages.id | CASCADE | NO ACTION |

## messaging_conversation_participants

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| conversation_id | VARCHAR(36) | No | - | Yes |
| user_id | VARCHAR(36) | No | - | Yes |
| role | VARCHAR(20) | Yes | - | No |
| joined_at | TIMESTAMP | Yes | - | No |
| is_active | BOOLEAN | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| conversation_id | messaging_conversations.id | CASCADE | NO ACTION |

## messaging_conversations

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | VARCHAR(36) | No | - | Yes |
| conversation_type | VARCHAR(20) | No | - | No |
| title | VARCHAR(255) | Yes | - | No |
| avatar_url | VARCHAR(512) | Yes | - | No |
| created_by | VARCHAR(36) | No | - | No |
| is_encrypted | BOOLEAN | Yes | - | No |
| conversation_metadata | JSON | Yes | - | No |
| created_at | TIMESTAMP | Yes | - | No |
| updated_at | TIMESTAMP | Yes | - | No |
| last_message_at | TIMESTAMP | Yes | - | No |

## messaging_group_settings

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | VARCHAR(36) | No | - | Yes |
| conversation_id | VARCHAR(36) | No | - | No |
| description | TEXT | Yes | - | No |
| max_participants | INTEGER | Yes | - | No |
| is_public | BOOLEAN | Yes | - | No |
| join_mode | VARCHAR(20) | Yes | - | No |
| message_permission | VARCHAR(20) | Yes | - | No |
| who_can_invite | VARCHAR(20) | Yes | - | No |
| who_can_remove | VARCHAR(20) | Yes | - | No |
| created_at | TIMESTAMP | Yes | - | No |
| updated_at | TIMESTAMP | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| conversation_id | messaging_conversations.id | CASCADE | NO ACTION |

## messaging_message_delivery_status

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | VARCHAR(36) | No | - | Yes |
| message_id | VARCHAR(36) | No | - | No |
| user_id | UUID | No | - | No |
| is_delivered | BOOLEAN | Yes | - | No |
| is_read | BOOLEAN | Yes | - | No |
| delivered_at | TIMESTAMP | Yes | - | No |
| read_at | TIMESTAMP | Yes | - | No |
| created_at | TIMESTAMP | Yes | - | No |
| updated_at | TIMESTAMP | Yes | - | No |
| delivery_metadata | TEXT | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| message_id | messaging_messages.id | CASCADE | NO ACTION |
| user_id | user.id | CASCADE | NO ACTION |

## messaging_messages

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | VARCHAR(36) | No | - | Yes |
| conversation_id | VARCHAR(36) | No | - | No |
| sender_id | VARCHAR(36) | No | - | No |
| message_type | VARCHAR(20) | No | - | No |
| content | TEXT | Yes | - | No |
| message_metadata | JSON | Yes | - | No |
| is_encrypted | BOOLEAN | Yes | - | No |
| is_edited | BOOLEAN | Yes | - | No |
| is_deleted | BOOLEAN | Yes | - | No |
| is_forwarded | BOOLEAN | Yes | - | No |
| original_message_id | VARCHAR(36) | Yes | - | No |
| reply_to_message_id | VARCHAR(36) | Yes | - | No |
| created_at | TIMESTAMP | Yes | - | No |
| updated_at | TIMESTAMP | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| conversation_id | messaging_conversations.id | CASCADE | NO ACTION |
| reply_to_message_id | messaging_messages.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_messaging_messages_sender_id | sender_id | No |

## messaging_reactions

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | VARCHAR(36) | No | - | Yes |
| message_id | VARCHAR(36) | No | - | No |
| user_id | UUID | No | - | No |
| reaction | VARCHAR(20) | No | - | No |
| created_at | TIMESTAMP | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| message_id | messaging_messages.id | CASCADE | NO ACTION |
| user_id | user.id | NO ACTION | NO ACTION |

## messaging_receipts

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | VARCHAR(36) | No | - | Yes |
| message_id | VARCHAR(36) | No | - | No |
| user_id | UUID | No | - | No |
| status | VARCHAR(20) | No | - | No |
| created_at | TIMESTAMP | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| message_id | messaging_messages.id | CASCADE | NO ACTION |
| user_id | user.id | NO ACTION | NO ACTION |

## messaging_user_blocks

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | VARCHAR(36) | No | - | Yes |
| blocker_id | UUID | No | - | No |
| blocked_id | UUID | No | - | No |
| reason | VARCHAR(255) | Yes | - | No |
| created_at | TIMESTAMP | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| blocked_id | user.id | NO ACTION | NO ACTION |
| blocker_id | user.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_messaging_user_blocks_blocker_id | blocker_id | No |
| ix_messaging_user_blocks_blocked_id | blocked_id | No |

## messaging_user_conversation_settings

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | VARCHAR(36) | No | - | Yes |
| user_id | UUID | No | - | No |
| conversation_id | VARCHAR(36) | No | - | No |
| is_muted | BOOLEAN | Yes | - | No |
| is_pinned | BOOLEAN | Yes | - | No |
| is_archived | BOOLEAN | Yes | - | No |
| is_deleted | BOOLEAN | Yes | - | No |
| custom_name | VARCHAR(255) | Yes | - | No |
| theme_color | VARCHAR(20) | Yes | - | No |
| notification_level | VARCHAR(20) | Yes | - | No |
| last_read_message_id | VARCHAR(36) | Yes | - | No |
| unread_count | INTEGER | Yes | - | No |
| role | VARCHAR(20) | Yes | - | No |
| created_at | TIMESTAMP | Yes | - | No |
| updated_at | TIMESTAMP | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| conversation_id | messaging_conversations.id | CASCADE | NO ACTION |
| user_id | user.id | NO ACTION | NO ACTION |

## notification_history

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('notification_history_id_seq'::regclass) | Yes |
| title | VARCHAR(200) | No | - | No |
| message | TEXT | No | - | No |
| icon | VARCHAR(255) | Yes | - | No |
| url | VARCHAR(255) | Yes | - | No |
| additional_data | TEXT | Yes | - | No |
| segment_id | INTEGER | Yes | - | No |
| sent_at | TIMESTAMP | Yes | - | No |
| sent_count | INTEGER | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| segment_id | notification_segments.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_notification_history_id | id | No |

## notification_receipts

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('notification_receipts_id_seq'::regclass) | Yes |
| notification_id | INTEGER | No | - | No |
| subscription_id | INTEGER | No | - | No |
| delivered | BOOLEAN | Yes | - | No |
| clicked | BOOLEAN | Yes | - | No |
| delivered_at | TIMESTAMP | Yes | - | No |
| clicked_at | TIMESTAMP | Yes | - | No |
| error_message | TEXT | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| notification_id | notification_history.id | NO ACTION | NO ACTION |
| subscription_id | push_subscriptions.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_notification_receipts_id | id | No |

## notification_segments

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('notification_segments_id_seq'::regclass) | Yes |
| name | VARCHAR(100) | No | - | No |
| description | TEXT | Yes | - | No |
| criteria | TEXT | Yes | - | No |
| is_dynamic | BOOLEAN | Yes | - | No |
| created_at | TIMESTAMP | Yes | - | No |
| updated_at | TIMESTAMP | Yes | - | No |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_notification_segments_id | id | No |

## offline_sync_batches

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | VARCHAR(36) | No | - | Yes |
| user_id | VARCHAR(36) | No | - | No |
| created_at | TIMESTAMP | No | - | No |
| updated_at | TIMESTAMP | No | - | No |
| name | VARCHAR(255) | Yes | - | No |
| description | TEXT | Yes | - | No |
| status | VARCHAR(20) | No | - | No |
| priority | VARCHAR(20) | No | - | No |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_sync_batches_status_priority | status, priority | No |
| ix_sync_batches_user_id_status | user_id, status | No |
| ix_offline_sync_batches_user_id | user_id | No |
| ix_offline_sync_batches_id | id | No |

## offline_sync_configs

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | VARCHAR(36) | No | - | Yes |
| user_id | VARCHAR(36) | No | - | No |
| created_at | TIMESTAMP | No | - | No |
| updated_at | TIMESTAMP | No | - | No |
| auto_sync_enabled | BOOLEAN | No | - | No |
| sync_on_connectivity | BOOLEAN | No | - | No |
| sync_interval_minutes | INTEGER | No | - | No |
| max_offline_storage_mb | INTEGER | No | - | No |
| conflict_resolution_strategy | VARCHAR(50) | No | - | No |
| prioritize_by_endpoint | JSON | Yes | - | No |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_offline_sync_configs_id | id | No |
| ix_offline_sync_configs_user_id | user_id | Yes |

## offline_sync_operations

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | VARCHAR(36) | No | - | Yes |
| user_id | VARCHAR(36) | No | - | No |
| created_at | TIMESTAMP | No | - | No |
| updated_at | TIMESTAMP | No | - | No |
| endpoint | VARCHAR(255) | No | - | No |
| method | VARCHAR(10) | No | - | No |
| payload | JSON | Yes | - | No |
| headers | JSON | Yes | - | No |
| query_params | JSON | Yes | - | No |
| status | VARCHAR(20) | No | - | No |
| priority | VARCHAR(20) | No | - | No |
| retry_count | INTEGER | No | - | No |
| max_retries | INTEGER | No | - | No |
| last_error | TEXT | Yes | - | No |
| is_encrypted | BOOLEAN | No | - | No |
| encryption_metadata | JSON | Yes | - | No |
| response_data | JSON | Yes | - | No |
| response_status | INTEGER | Yes | - | No |
| batch_id | VARCHAR(36) | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| batch_id | offline_sync_batches.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_sync_operations_user_id_status | user_id, status | No |
| ix_offline_sync_operations_user_id | user_id | No |
| ix_sync_operations_status_priority | status, priority | No |
| ix_offline_sync_operations_id | id | No |

## organizations

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('organizations_id_seq'::regclass) | Yes |
| name | VARCHAR(255) | No | - | No |
| org_type | VARCHAR(50) | No | - | No |
| is_active | BOOLEAN | No | - | No |
| created_at | TIMESTAMP | No | now() | No |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_organizations_id | id | No |

## payment_approval_steps

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('payment_approval_steps_id_seq'::regclass) | Yes |
| payment_id | INTEGER | Yes | - | No |
| approver_id | UUID | Yes | - | No |
| status | VARCHAR | No | - | No |
| comments | VARCHAR | Yes | - | No |
| step_order | INTEGER | No | - | No |
| created_at | TIMESTAMP | Yes | - | No |
| updated_at | TIMESTAMP | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| approver_id | user.id | NO ACTION | NO ACTION |
| payment_id | payments.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_payment_approval_steps_id | id | No |

## payment_approver

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| payment_id | INTEGER | Yes | - | No |
| user_id | UUID | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| payment_id | payments.id | NO ACTION | NO ACTION |
| user_id | user.id | NO ACTION | NO ACTION |

## payment_refunds

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('payment_refunds_id_seq'::regclass) | Yes |
| payment_id | INTEGER | Yes | - | No |
| reference | VARCHAR | Yes | - | No |
| amount | DOUBLE PRECISION | No | - | No |
| currency | VARCHAR | No | - | No |
| reason | VARCHAR | Yes | - | No |
| status | VARCHAR | No | - | No |
| provider | VARCHAR | Yes | - | No |
| provider_reference | VARCHAR | Yes | - | No |
| refund_metadata | JSON | Yes | - | No |
| refunded_by_id | UUID | Yes | - | No |
| created_at | TIMESTAMP | Yes | - | No |
| updated_at | TIMESTAMP | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| payment_id | payments.id | NO ACTION | NO ACTION |
| refunded_by_id | user.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_payment_refunds_id | id | No |
| ix_payment_refunds_reference | reference | Yes |

## payment_subscription_history

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('payment_subscription_history_id_seq'::regclass) | Yes |
| subscription_id | INTEGER | No | - | No |
| action | VARCHAR | No | - | No |
| status_before | VARCHAR | Yes | - | No |
| status_after | VARCHAR | Yes | - | No |
| user_id | UUID | Yes | - | No |
| timestamp | TIMESTAMP | No | - | No |
| data | JSON | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| subscription_id | payment_subscriptions.id | NO ACTION | NO ACTION |
| user_id | user.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_payment_subscription_history_id | id | No |

## payment_subscription_items

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('payment_subscription_items_id_seq'::regclass) | Yes |
| subscription_id | INTEGER | No | - | No |
| name | VARCHAR | No | - | No |
| description | TEXT | Yes | - | No |
| price | DOUBLE PRECISION | No | - | No |
| currency | VARCHAR | No | - | No |
| quantity | INTEGER | No | - | No |
| product_id | VARCHAR | Yes | - | No |
| provider_item_id | VARCHAR | Yes | - | No |
| item_metadata | JSON | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| subscription_id | payment_subscriptions.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_payment_subscription_items_id | id | No |

## payment_subscriptions

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('payment_subscriptions_id_seq'::regclass) | Yes |
| name | VARCHAR | No | - | No |
| description | TEXT | Yes | - | No |
| status | VARCHAR | No | - | No |
| customer_id | UUID | Yes | - | No |
| customer_email | VARCHAR | Yes | - | No |
| created_by_id | UUID | Yes | - | No |
| created_at | TIMESTAMP | No | - | No |
| updated_at | TIMESTAMP | No | - | No |
| start_date | TIMESTAMP | Yes | - | No |
| end_date | TIMESTAMP | Yes | - | No |
| next_billing_date | TIMESTAMP | Yes | - | No |
| amount | DOUBLE PRECISION | No | - | No |
| currency | VARCHAR | No | - | No |
| billing_period | VARCHAR | No | - | No |
| billing_interval | INTEGER | No | - | No |
| trial_enabled | BOOLEAN | Yes | - | No |
| trial_start_date | TIMESTAMP | Yes | - | No |
| trial_end_date | TIMESTAMP | Yes | - | No |
| payment_method_id | VARCHAR | Yes | - | No |
| payment_provider | VARCHAR | Yes | - | No |
| provider_subscription_id | VARCHAR | Yes | - | No |
| auto_renew | BOOLEAN | Yes | - | No |
| subscription_metadata | JSON | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| created_by_id | user.id | NO ACTION | NO ACTION |
| customer_id | user.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_payment_subscriptions_id | id | No |

## payment_transactions

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('payment_transactions_id_seq'::regclass) | Yes |
| payment_id | INTEGER | Yes | - | No |
| reference | VARCHAR | Yes | - | No |
| amount | DOUBLE PRECISION | No | - | No |
| status | VARCHAR | No | - | No |
| provider | VARCHAR | No | - | No |
| provider_reference | VARCHAR | Yes | - | No |
| transaction_type | VARCHAR | No | - | No |
| transaction_metadata | JSON | Yes | - | No |
| created_at | TIMESTAMP | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| payment_id | payments.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_payment_transactions_reference | reference | Yes |
| ix_payment_transactions_id | id | No |

## payments

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('payments_id_seq'::regclass) | Yes |
| reference | VARCHAR | Yes | - | No |
| amount | DOUBLE PRECISION | No | - | No |
| currency | VARCHAR | No | - | No |
| description | VARCHAR | Yes | - | No |
| status | VARCHAR | No | - | No |
| payment_method | VARCHAR | No | - | No |
| provider | VARCHAR | Yes | - | No |
| provider_reference | VARCHAR | Yes | - | No |
| payment_metadata | JSON | Yes | - | No |
| created_at | TIMESTAMP | Yes | - | No |
| updated_at | TIMESTAMP | Yes | - | No |
| created_by_id | UUID | Yes | - | No |
| customer_id | UUID | Yes | - | No |
| subscription_id | INTEGER | Yes | - | No |
| refunded_amount | DOUBLE PRECISION | Yes | - | No |
| is_fully_refunded | BOOLEAN | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| created_by_id | user.id | NO ACTION | NO ACTION |
| customer_id | user.id | NO ACTION | NO ACTION |
| subscription_id | payment_subscriptions.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_payments_reference | reference | Yes |
| ix_payments_id | id | No |

## privacy_anonymization_logs

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('privacy_anonymization_logs_id_seq'::regclass) | Yes |
| entity_type | VARCHAR(50) | No | - | No |
| entity_id | INTEGER | No | - | No |
| fields_anonymized | TEXT | No | - | No |
| anonymization_method | VARCHAR(50) | No | - | No |
| reason | VARCHAR(255) | Yes | - | No |
| performed_by | UUID | Yes | - | No |
| performed_at | TIMESTAMP | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| performed_by | user.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_privacy_anonymization_logs_id | id | No |

## privacy_cookie_categories

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('privacy_cookie_categories_id_seq'::regclass) | Yes |
| name | VARCHAR(50) | No | - | No |
| description | TEXT | No | - | No |
| is_necessary | BOOLEAN | Yes | - | No |
| created_at | TIMESTAMP | Yes | - | No |
| updated_at | TIMESTAMP | Yes | - | No |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_privacy_cookie_categories_id | id | No |

## privacy_cookie_category_settings

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| settings_id | INTEGER | Yes | - | No |
| category_id | INTEGER | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| category_id | privacy_cookie_categories.id | NO ACTION | NO ACTION |
| settings_id | privacy_cookie_settings.id | NO ACTION | NO ACTION |

## privacy_cookie_settings

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('privacy_cookie_settings_id_seq'::regclass) | Yes |
| consent_expiry_days | INTEGER | Yes | - | No |
| block_until_consent | BOOLEAN | Yes | - | No |
| created_at | TIMESTAMP | Yes | - | No |
| updated_at | TIMESTAMP | Yes | - | No |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_privacy_cookie_settings_id | id | No |

## privacy_cookies

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('privacy_cookies_id_seq'::regclass) | Yes |
| name | VARCHAR(255) | No | - | No |
| domain | VARCHAR(255) | No | - | No |
| purpose | TEXT | No | - | No |
| duration | VARCHAR(50) | No | - | No |
| provider | VARCHAR(255) | Yes | - | No |
| category_id | INTEGER | Yes | - | No |
| created_at | TIMESTAMP | Yes | - | No |
| updated_at | TIMESTAMP | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| category_id | privacy_cookie_categories.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_privacy_cookies_id | id | No |

## privacy_data_processing_records

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('privacy_data_processing_records_id_seq'::regclass) | Yes |
| activity_name | VARCHAR(255) | No | - | No |
| purpose | TEXT | No | - | No |
| data_categories | TEXT | No | - | No |
| data_subjects | TEXT | No | - | No |
| recipients | TEXT | Yes | - | No |
| transfers | TEXT | Yes | - | No |
| retention_period | VARCHAR(255) | No | - | No |
| security_measures | TEXT | No | - | No |
| legal_basis | VARCHAR(255) | No | - | No |
| created_at | TIMESTAMP | Yes | - | No |
| updated_at | TIMESTAMP | Yes | - | No |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_privacy_data_processing_records_id | id | No |

## privacy_data_requests

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('privacy_data_requests_id_seq'::regclass) | Yes |
| user_id | UUID | Yes | - | No |
| email | VARCHAR(255) | No | - | No |
| request_type | VARCHAR(20) | No | - | No |
| request_details | TEXT | Yes | - | No |
| verification_token | VARCHAR(255) | Yes | - | No |
| verification_expires | TIMESTAMP | Yes | - | No |
| verified_at | TIMESTAMP | Yes | - | No |
| status | VARCHAR(20) | No | - | No |
| request_ip | VARCHAR(50) | No | - | No |
| created_at | TIMESTAMP | Yes | - | No |
| updated_at | TIMESTAMP | Yes | - | No |
| completed_at | TIMESTAMP | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| user_id | user.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_privacy_data_requests_id | id | No |

## privacy_exported_data

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('privacy_exported_data_id_seq'::regclass) | Yes |
| data_request_id | INTEGER | No | - | No |
| data_content | TEXT | Yes | - | No |
| file_path | VARCHAR(255) | Yes | - | No |
| encryption_key | VARCHAR(255) | Yes | - | No |
| created_at | TIMESTAMP | Yes | - | No |
| expires_at | TIMESTAMP | No | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| data_request_id | privacy_data_requests.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_privacy_exported_data_id | id | No |

## privacy_policies

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('privacy_policies_id_seq'::regclass) | Yes |
| version | VARCHAR(20) | No | - | No |
| content | TEXT | No | - | No |
| is_active | BOOLEAN | Yes | - | No |
| created_at | TIMESTAMP | Yes | - | No |
| activated_at | TIMESTAMP | Yes | - | No |
| created_by | UUID | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| created_by | user.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_privacy_policies_id | id | No |

## privacy_user_consents

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('privacy_user_consents_id_seq'::regclass) | Yes |
| user_id | UUID | Yes | - | No |
| consent_type | VARCHAR(50) | No | - | No |
| consent_details | TEXT | Yes | - | No |
| ip_address | VARCHAR(50) | No | - | No |
| user_agent | VARCHAR(255) | No | - | No |
| consented_at | TIMESTAMP | Yes | - | No |
| updated_at | TIMESTAMP | Yes | - | No |
| expires_at | TIMESTAMP | Yes | - | No |
| revoked_at | TIMESTAMP | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| user_id | user.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_privacy_user_consents_id | id | No |

## product_price_configs

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('product_price_configs_id_seq'::regclass) | Yes |
| product_id | INTEGER | No | - | No |
| purchase_sir_unit | DOUBLE PRECISION | No | - | No |
| taxes_unit | DOUBLE PRECISION | No | - | No |
| margin_boss_unit | DOUBLE PRECISION | No | - | No |
| selling_price_unit | DOUBLE PRECISION | No | - | No |
| is_active | BOOLEAN | No | - | No |
| updated_at | TIMESTAMP | No | now() | No |
| organization_id | INTEGER | No | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| organization_id | organizations.id | NO ACTION | NO ACTION |
| product_id | products.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_product_price_configs_id | id | No |

## products

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('products_id_seq'::regclass) | Yes |
| name | VARCHAR(255) | No | - | No |
| unit | VARCHAR(50) | No | - | No |
| created_at | TIMESTAMP | No | now() | No |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_products_name | name | Yes |
| ix_products_id | id | No |

## pumps

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('pumps_id_seq'::regclass) | Yes |
| tank_id | INTEGER | No | - | No |
| name | VARCHAR(100) | No | - | No |
| last_index_value | DOUBLE PRECISION | No | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| tank_id | tanks.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_pumps_id | id | No |

## purchase_taxes

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('purchase_taxes_id_seq'::regclass) | Yes |
| purchase_id | INTEGER | No | - | No |
| name | VARCHAR(255) | No | - | No |
| amount | DOUBLE PRECISION | No | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| purchase_id | purchases.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_purchase_taxes_id | id | No |

## purchases

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('purchases_id_seq'::regclass) | Yes |
| product_id | INTEGER | No | - | No |
| volume | DOUBLE PRECISION | No | - | No |
| total_amount | DOUBLE PRECISION | No | - | No |
| supplier | VARCHAR(100) | No | - | No |
| purchase_date | TIMESTAMP | No | now() | No |
| unit_purchase_price | DOUBLE PRECISION | No | - | No |
| unit_taxes | DOUBLE PRECISION | No | - | No |
| organization_id | INTEGER | No | - | No |
| tank_id | INTEGER | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| organization_id | organizations.id | NO ACTION | NO ACTION |
| product_id | products.id | NO ACTION | NO ACTION |
| tank_id | tanks.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_purchases_id | id | No |

## push_subscriptions

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('push_subscriptions_id_seq'::regclass) | Yes |
| endpoint | VARCHAR(500) | No | - | No |
| p256dh | VARCHAR(255) | No | - | No |
| auth | VARCHAR(255) | No | - | No |
| user_id | UUID | Yes | - | No |
| user_agent | VARCHAR(500) | Yes | - | No |
| created_at | TIMESTAMP | Yes | - | No |
| last_used | TIMESTAMP | Yes | - | No |
| device_type | VARCHAR(50) | Yes | - | No |
| language | VARCHAR(10) | Yes | - | No |
| location | VARCHAR(100) | Yes | - | No |
| tags | TEXT | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| user_id | user.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_push_subscriptions_id | id | No |

## pwa_settings

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('pwa_settings_id_seq'::regclass) | Yes |
| manifest | TEXT | Yes | - | No |
| service_worker_config | TEXT | Yes | - | No |
| vapid_public_key | VARCHAR(255) | Yes | - | No |
| vapid_private_key | VARCHAR(255) | Yes | - | No |
| updated_at | TIMESTAMP | Yes | - | No |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_pwa_settings_id | id | No |

## recommendation_interactions

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('recommendation_interactions_id_seq'::regclass) | Yes |
| user_id | INTEGER | No | - | No |
| item_id | INTEGER | No | - | No |
| interaction_type | VARCHAR(50) | No | - | No |
| value | DOUBLE PRECISION | No | - | No |
| context | VARCHAR(255) | Yes | - | No |
| interaction_metadata | VARCHAR(1024) | Yes | - | No |
| created_at | TIMESTAMP | No | - | No |
| updated_at | TIMESTAMP | No | - | No |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| idx_interaction_type | interaction_type | No |
| ix_recommendation_interactions_item_id | item_id | No |
| ix_recommendation_interactions_user_id | user_id | No |
| ix_recommendation_interactions_id | id | No |
| idx_user_item | user_id, item_id | No |

## recommendation_item_features

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('recommendation_item_features_id_seq'::regclass) | Yes |
| item_id | INTEGER | No | - | No |
| item_type | VARCHAR(50) | No | - | No |
| title | VARCHAR(255) | Yes | - | No |
| description | TEXT | Yes | - | No |
| categories | VARCHAR(512) | Yes | - | No |
| text_features | TEXT | Yes | - | No |
| feature_vector | VARCHAR(4096) | Yes | - | No |
| popularity_score | DOUBLE PRECISION | No | - | No |
| average_rating | DOUBLE PRECISION | No | - | No |
| rating_count | INTEGER | No | - | No |
| view_count | INTEGER | No | - | No |
| created_at | TIMESTAMP | No | - | No |
| updated_at | TIMESTAMP | No | - | No |
| last_feature_update | TIMESTAMP | Yes | - | No |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_recommendation_item_features_item_type | item_type | No |
| ix_recommendation_item_features_id | id | No |
| idx_item_type_rating | item_type, average_rating | No |
| idx_item_type_popularity | item_type, popularity_score | No |
| ix_recommendation_item_features_item_id | item_id | Yes |

## recommendation_item_similarities

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('recommendation_item_similarities_id_seq'::regclass) | Yes |
| item_id | INTEGER | No | - | No |
| similar_item_id | INTEGER | No | - | No |
| algorithm | VARCHAR(50) | No | - | No |
| similarity_score | DOUBLE PRECISION | No | - | No |
| similarity_context | VARCHAR(512) | Yes | - | No |
| created_at | TIMESTAMP | No | - | No |
| updated_at | TIMESTAMP | No | - | No |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_recommendation_item_similarities_id | id | No |
| idx_item_algorithm_score | item_id, algorithm, similarity_score | No |
| ix_recommendation_item_similarities_item_id | item_id | No |
| idx_item_similar | item_id, similar_item_id | No |
| ix_recommendation_item_similarities_similar_item_id | similar_item_id | No |
| ix_recommendation_item_similarities_algorithm | algorithm | No |

## recommendation_results

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('recommendation_results_id_seq'::regclass) | Yes |
| user_id | INTEGER | No | - | No |
| item_id | INTEGER | No | - | No |
| algorithm | VARCHAR(50) | No | - | No |
| score | DOUBLE PRECISION | No | - | No |
| rank | INTEGER | No | - | No |
| context | VARCHAR(255) | Yes | - | No |
| was_clicked | INTEGER | No | - | No |
| click_time | TIMESTAMP | Yes | - | No |
| created_at | TIMESTAMP | No | - | No |
| expires_at | TIMESTAMP | Yes | - | No |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| idx_algorithm_score | algorithm, score | No |
| ix_recommendation_results_user_id | user_id | No |
| idx_user_context | user_id, context | No |
| ix_recommendation_results_algorithm | algorithm | No |
| ix_recommendation_results_id | id | No |
| idx_created_expires | created_at, expires_at | No |
| ix_recommendation_results_item_id | item_id | No |

## recommendation_similarity_matrices

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('recommendation_similarity_matrices_id_seq'::regclass) | Yes |
| matrix_type | VARCHAR(50) | No | - | No |
| algorithm | VARCHAR(50) | No | - | No |
| matrix_data | BYTEA | No | - | No |
| rows | INTEGER | No | - | No |
| columns | INTEGER | No | - | No |
| matrix_metadata | VARCHAR(1024) | Yes | - | No |
| training_duration | DOUBLE PRECISION | Yes | - | No |
| created_at | TIMESTAMP | No | - | No |
| updated_at | TIMESTAMP | No | - | No |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_recommendation_similarity_matrices_id | id | No |
| ix_recommendation_similarity_matrices_matrix_type | matrix_type | No |
| ix_recommendation_similarity_matrices_algorithm | algorithm | No |

## recommendation_user_preferences

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('recommendation_user_preferences_id_seq'::regclass) | Yes |
| user_id | INTEGER | No | - | No |
| preferred_categories | VARCHAR(1024) | Yes | - | No |
| preferred_tags | VARCHAR(1024) | Yes | - | No |
| disliked_items | VARCHAR(1024) | Yes | - | No |
| interest_vector | TEXT | Yes | - | No |
| latent_factors | TEXT | Yes | - | No |
| diversity_preference | DOUBLE PRECISION | No | - | No |
| novelty_preference | DOUBLE PRECISION | No | - | No |
| created_at | TIMESTAMP | No | - | No |
| updated_at | TIMESTAMP | No | - | No |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_recommendation_user_preferences_id | id | No |
| ix_recommendation_user_preferences_user_id | user_id | Yes |

## sales

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('sales_id_seq'::regclass) | Yes |
| client_id | INTEGER | No | - | No |
| product_id | INTEGER | No | - | No |
| volume | DOUBLE PRECISION | No | - | No |
| unit_price | DOUBLE PRECISION | No | - | No |
| total_amount | DOUBLE PRECISION | No | - | No |
| status | VARCHAR(50) | No | - | No |
| created_at | TIMESTAMP | No | now() | No |
| margin_boss_total | DOUBLE PRECISION | No | - | No |
| organization_id | INTEGER | No | - | No |
| pump_id | INTEGER | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| client_id | clients.id | NO ACTION | NO ACTION |
| organization_id | organizations.id | NO ACTION | NO ACTION |
| product_id | products.id | NO ACTION | NO ACTION |
| pump_id | pumps.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_sales_id | id | No |

## scheduled_jobs

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('scheduled_jobs_id_seq'::regclass) | Yes |
| name | VARCHAR(100) | No | - | No |
| description | VARCHAR(255) | Yes | - | No |
| cron_expr | VARCHAR(50) | No | - | No |
| task_name | VARCHAR(200) | No | - | No |
| args | JSON | No | - | No |
| enabled | BOOLEAN | No | - | No |
| created_at | TIMESTAMP | Yes | CURRENT_TIMESTAMP | No |
| updated_at | TIMESTAMP | Yes | - | No |

## step_approvals

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('step_approvals_id_seq'::regclass) | Yes |
| instance_id | INTEGER | No | - | No |
| step_id | INTEGER | No | - | No |
| user_id | UUID | Yes | - | No |
| status | VARCHAR(50) | Yes | - | No |
| decision_at | TIMESTAMP | Yes | - | No |
| comments | TEXT | Yes | - | No |
| created_at | TIMESTAMP | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| instance_id | workflow_instances.id | CASCADE | NO ACTION |
| step_id | workflow_steps.id | NO ACTION | NO ACTION |
| user_id | user.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_step_approvals_id | id | No |
| ix_step_approvals_status | status | No |

## stock_movements

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('stock_movements_id_seq'::regclass) | Yes |
| product_id | INTEGER | No | - | No |
| type | VARCHAR(10) | No | - | No |
| volume | DOUBLE PRECISION | No | - | No |
| source | VARCHAR(50) | No | - | No |
| source_id | INTEGER | No | - | No |
| created_at | TIMESTAMP | No | now() | No |
| organization_id | INTEGER | No | - | No |
| tank_id | INTEGER | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| organization_id | organizations.id | NO ACTION | NO ACTION |
| product_id | products.id | NO ACTION | NO ACTION |
| tank_id | tanks.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_stock_movements_id | id | No |

## storages

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('storages_id_seq'::regclass) | Yes |
| purchase_id | INTEGER | No | - | No |
| entry_date | TIMESTAMP | No | now() | No |
| storage_cost | DOUBLE PRECISION | No | - | No |
| location | VARCHAR(100) | No | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| purchase_id | purchases.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_storages_id | id | No |

## subscription_segment_association

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| subscription_id | INTEGER | Yes | - | No |
| segment_id | INTEGER | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| segment_id | notification_segments.id | NO ACTION | NO ACTION |
| subscription_id | push_subscriptions.id | NO ACTION | NO ACTION |

## tanks

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('tanks_id_seq'::regclass) | Yes |
| organization_id | INTEGER | No | - | No |
| product_id | INTEGER | No | - | No |
| name | VARCHAR(100) | No | - | No |
| capacity | DOUBLE PRECISION | No | - | No |
| current_volume | DOUBLE PRECISION | No | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| organization_id | organizations.id | NO ACTION | NO ACTION |
| product_id | products.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_tanks_id | id | No |

## test

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | UUID | No | - | Yes |
| name | VARCHAR(50) | No | - | No |
| description | VARCHAR(255) | Yes | - | No |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_test_id | id | No |

## user

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | UUID | No | - | Yes |
| username | VARCHAR(50) | No | - | No |
| email | VARCHAR(255) | No | - | No |
| hashed_password | VARCHAR | Yes | - | No |
| first_name | VARCHAR(100) | Yes | - | No |
| last_name | VARCHAR(100) | Yes | - | No |
| is_active | BOOLEAN | Yes | - | No |
| is_verified | BOOLEAN | Yes | - | No |
| is_superuser | BOOLEAN | Yes | - | No |
| created_at | TIMESTAMP | Yes | - | No |
| updated_at | TIMESTAMP | Yes | - | No |
| last_login | TIMESTAMP | Yes | - | No |
| password_changed_at | TIMESTAMP | Yes | - | No |
| failed_login_attempts | INTEGER | Yes | - | No |
| locked_until | TIMESTAMP | Yes | - | No |
| profile_picture | VARCHAR | Yes | - | No |
| locale | VARCHAR(10) | Yes | - | No |
| timezone | VARCHAR(50) | Yes | - | No |
| primary_auth_provider | VARCHAR(50) | Yes | - | No |
| auth_provider_data | JSON | Yes | - | No |
| phone_number | VARCHAR | Yes | - | No |
| ssn | VARCHAR | Yes | - | No |
| date_of_birth | TIMESTAMP | Yes | - | No |
| refresh_token | VARCHAR | Yes | - | No |
| refresh_token_expires_at | TIMESTAMP | Yes | - | No |
| role_id | UUID | No | - | No |
| organization_id | INTEGER | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| organization_id | organizations.id | NO ACTION | NO ACTION |
| role_id | auth_role.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_user_id | id | No |

## user_group

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| user_id | UUID | No | - | Yes |
| group_id | UUID | No | - | Yes |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| group_id | auth_group.id | NO ACTION | NO ACTION |
| user_id | user.id | NO ACTION | NO ACTION |

## user_sessions

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('user_sessions_id_seq'::regclass) | Yes |
| created_at | TIMESTAMP | Yes | - | No |
| refresh_count | INTEGER | Yes | - | No |
| user_id | VARCHAR | No | - | No |
| ip_address | VARCHAR(45) | No | - | No |
| user_agent | VARCHAR(255) | Yes | - | No |
| expires_at | TIMESTAMP | No | - | No |
| mfa_authenticated | BOOLEAN | Yes | - | No |
| revoked | BOOLEAN | Yes | - | No |
| last_activity | TIMESTAMP | Yes | - | No |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_user_sessions_id | id | No |

## webhooks

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('webhooks_id_seq'::regclass) | Yes |
| name | VARCHAR(100) | No | - | No |
| event | VARCHAR(100) | No | - | No |
| url | VARCHAR(500) | No | - | No |
| secret | VARCHAR(200) | Yes | - | No |
| is_enabled | BOOLEAN | No | - | No |
| config | JSON | Yes | '{}'::json | No |
| created_at | TIMESTAMP | Yes | CURRENT_TIMESTAMP | No |
| updated_at | TIMESTAMP | Yes | - | No |

## workflow_history

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('workflow_history_id_seq'::regclass) | Yes |
| instance_id | INTEGER | No | - | No |
| action_type | VARCHAR(50) | No | - | No |
| from_state_id | INTEGER | Yes | - | No |
| to_state_id | INTEGER | Yes | - | No |
| step_id | INTEGER | Yes | - | No |
| user_id | UUID | Yes | - | No |
| details | JSON | Yes | - | No |
| created_at | TIMESTAMP | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| from_state_id | workflow_states.id | NO ACTION | NO ACTION |
| instance_id | workflow_instances.id | CASCADE | NO ACTION |
| step_id | workflow_steps.id | NO ACTION | NO ACTION |
| to_state_id | workflow_states.id | NO ACTION | NO ACTION |
| user_id | user.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_workflow_history_id | id | No |

## workflow_instances

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('workflow_instances_id_seq'::regclass) | Yes |
| workflow_id | INTEGER | No | - | No |
| target_type | VARCHAR(8) | No | - | No |
| target_id | INTEGER | No | - | No |
| current_state_id | INTEGER | Yes | - | No |
| started_at | TIMESTAMP | Yes | - | No |
| completed_at | TIMESTAMP | Yes | - | No |
| is_active | BOOLEAN | Yes | - | No |
| instance_metadata | JSON | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| current_state_id | workflow_states.id | NO ACTION | NO ACTION |
| workflow_id | workflows.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_workflow_instances_id | id | No |

## workflow_states

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('workflow_states_id_seq'::regclass) | Yes |
| workflow_id | INTEGER | No | - | No |
| name | VARCHAR(100) | No | - | No |
| description | TEXT | Yes | - | No |
| is_initial | BOOLEAN | Yes | - | No |
| is_final | BOOLEAN | Yes | - | No |
| color | VARCHAR(50) | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| workflow_id | workflows.id | CASCADE | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_workflow_states_id | id | No |

## workflow_step_roles

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| workflow_step_id | INTEGER | No | - | Yes |
| role_id | UUID | No | - | Yes |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| role_id | auth_role.id | NO ACTION | NO ACTION |
| workflow_step_id | workflow_steps.id | NO ACTION | NO ACTION |

## workflow_steps

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('workflow_steps_id_seq'::regclass) | Yes |
| workflow_id | INTEGER | No | - | No |
| name | VARCHAR(100) | No | - | No |
| description | TEXT | Yes | - | No |
| step_type | VARCHAR(12) | No | - | No |
| step_order | INTEGER | No | - | No |
| is_required | BOOLEAN | Yes | - | No |
| config | JSON | Yes | - | No |
| next_step_on_approve | INTEGER | Yes | - | No |
| next_step_on_reject | INTEGER | Yes | - | No |
| created_at | TIMESTAMP | Yes | - | No |
| updated_at | TIMESTAMP | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| next_step_on_approve | workflow_steps.id | NO ACTION | NO ACTION |
| next_step_on_reject | workflow_steps.id | NO ACTION | NO ACTION |
| workflow_id | workflows.id | CASCADE | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_workflow_steps_id | id | No |

## workflow_transitions

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('workflow_transitions_id_seq'::regclass) | Yes |
| workflow_id | INTEGER | No | - | No |
| from_state_id | INTEGER | No | - | No |
| to_state_id | INTEGER | No | - | No |
| name | VARCHAR(100) | No | - | No |
| description | TEXT | Yes | - | No |
| triggers | JSON | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| from_state_id | workflow_states.id | CASCADE | NO ACTION |
| to_state_id | workflow_states.id | CASCADE | NO ACTION |
| workflow_id | workflows.id | CASCADE | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_workflow_transitions_id | id | No |

## workflows

### Columns

| Name | Type | Nullable | Default | Primary Key |
|------|------|----------|---------|-------------|
| id | INTEGER | No | nextval('workflows_id_seq'::regclass) | Yes |
| name | VARCHAR(100) | No | - | No |
| description | TEXT | Yes | - | No |
| target_type | VARCHAR(8) | No | - | No |
| target_filter | JSON | Yes | - | No |
| is_active | BOOLEAN | Yes | - | No |
| is_default | BOOLEAN | Yes | - | No |
| created_at | TIMESTAMP | Yes | - | No |
| updated_at | TIMESTAMP | Yes | - | No |
| created_by | UUID | Yes | - | No |
| updated_by | UUID | Yes | - | No |

### Foreign Keys

| Column | References | On Delete | On Update |
|--------|------------|-----------|----------|
| created_by | user.id | NO ACTION | NO ACTION |
| updated_by | user.id | NO ACTION | NO ACTION |

### Indexes

| Name | Columns | Unique |
|------|---------|--------|
| ix_workflows_target_type | target_type | No |
| ix_workflows_id | id | No |
| ix_workflows_name | name | No |

