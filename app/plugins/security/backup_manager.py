# /backend/app/plugins/security/backup_manager.py
def backup_keys():
    """Sauvegarde chiffrée des clés dans stockage sécurisé"""
    encrypted_backup = encrypt_with_kms(keys)
    upload_to_secure_storage(encrypted_backup)