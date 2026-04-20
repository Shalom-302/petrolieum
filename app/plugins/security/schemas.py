from pydantic import BaseModel, Field

class EncryptionRequest(BaseModel):
    data: str = Field(..., max_length=4096, 
                    description="Données à chiffrer (max 4KB)")

class DecryptionRequest(BaseModel):
    encrypted: str = Field(..., pattern=r'^[0-9a-fA-F:]+$',
                         description="Payload chiffré valid")