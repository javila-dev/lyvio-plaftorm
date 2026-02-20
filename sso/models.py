from django.db import models
from django.utils import timezone


class SSOToken(models.Model):
    """
    Token de autenticación SSO para integración con Chatwoot vía n8n.
    
    Lifecycle:
    1. Token se genera vía API con request_id único
    2. Token tiene validez de 5 minutos
    3. Token se puede usar una sola vez
    4. Token usado se marca con used=True y used_at
    """
    token = models.CharField(
        max_length=64, 
        unique=True, 
        db_index=True,
        help_text="Token SSO único generado con secrets.token_hex(32)"
    )
    email = models.EmailField(
        blank=True,
        default='',
        help_text="Email del usuario que será autenticado (opcional)"
    )
    chatwoot_account_id = models.CharField(
        max_length=50,
        help_text="ID de la cuenta de Chatwoot"
    )
    chatwoot_user_id = models.CharField(
        max_length=50, 
        blank=True,
        help_text="ID del usuario en Chatwoot"
    )
    request_id = models.CharField(
        max_length=100, 
        unique=True,
        db_index=True,
        help_text="ID único de la solicitud para prevenir replay attacks"
    )
    used = models.BooleanField(
        default=False,
        help_text="Indica si el token ya fue utilizado"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp de creación del token"
    )
    expires_at = models.DateTimeField(
        help_text="Timestamp de expiración del token"
    )
    used_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Timestamp cuando el token fue usado"
    )
    
    class Meta:
        db_table = 'sso_tokens'
        verbose_name = 'SSO Token'
        verbose_name_plural = 'SSO Tokens'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['token', 'used'], name='sso_token_used_idx'),
            models.Index(fields=['expires_at'], name='sso_expires_idx'),
            models.Index(fields=['request_id'], name='sso_request_idx'),
        ]
    
    def __str__(self):
        return f"SSO Token for {self.email} (used={self.used})"
    
    def is_valid(self):
        """
        Verifica si el token es válido para autenticación.
        
        Returns:
            bool: True si el token es válido (no usado y no expirado)
        """
        if self.used:
            return False
        if timezone.now() > self.expires_at:
            return False
        return True
    
    def mark_as_used(self):
        """
        Marca el token como usado y registra el timestamp.
        """
        self.used = True
        self.used_at = timezone.now()
        self.save(update_fields=['used', 'used_at'])
