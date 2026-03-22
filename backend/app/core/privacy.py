"""
Privacy Module - LPDP Perú Compliance
======================================

Implementa funcionalidades para cumplir con la Ley de Protección de 
Datos Personales de Perú (Ley 29733) y su reglamento (D.S. 016-2024-JUS).

Características:
- Gestión de consentimientos
- Derechos ARCO-P (Acceso, Rectificación, Cancelación, Oposición, Portabilidad)
- Auditoría de accesos
- Políticas de retención de datos
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from enum import Enum
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)


class ConsentPurpose(str, Enum):
    """Propósitos de tratamiento de datos según LPDP."""
    RECRUITMENT = "recruitment"  # Proceso de selección
    TALENT_POOL = "talent_pool"  # Pool de talento para futuras vacantes
    ANALYTICS = "analytics"      # Análisis estadístico anonimizado
    MARKETING = "marketing"      # Comunicaciones de marketing


class DataSubjectRight(str, Enum):
    """Derechos ARCO-P del titular de datos."""
    ACCESS = "access"           # Derecho de acceso
    RECTIFICATION = "rectify"   # Derecho de rectificación
    CANCELLATION = "cancel"     # Derecho de cancelación (olvido)
    OPPOSITION = "oppose"       # Derecho de oposición
    PORTABILITY = "portability" # Derecho de portabilidad


@dataclass
class ConsentRecord:
    """Registro de consentimiento conforme a LPDP."""
    candidate_id: str
    purpose: ConsentPurpose
    granted: bool
    consent_date: datetime
    expiry_date: Optional[datetime]
    consent_text: str
    ip_address: Optional[str]
    user_agent: Optional[str]


@dataclass
class AuditLogEntry:
    """Entrada de log de auditoría para acceso a datos personales."""
    timestamp: datetime
    user_id: str
    action: str
    resource_type: str
    resource_id: str
    ip_address: Optional[str]
    details: Optional[Dict[str, Any]]


class ConsentManager:
    """
    Gestiona los consentimientos de tratamiento de datos.
    
    Conforme a LPDP Perú:
    - Consentimiento debe ser libre, previo, expreso e informado
    - Para datos sensibles, debe ser por escrito
    - Puede ser revocado en cualquier momento
    """
    
    # Texto de consentimiento estándar
    CONSENT_TEXTS = {
        ConsentPurpose.RECRUITMENT: """
        Autorizo el tratamiento de mis datos personales contenidos en mi CV 
        para el proceso de selección de personal en la vacante indicada.
        Este consentimiento es válido por 1 año desde la fecha de postulación.
        """,
        ConsentPurpose.TALENT_POOL: """
        Autorizo que mis datos sean almacenados en el banco de talentos 
        para ser considerado en futuras oportunidades laborales por un 
        período de 2 años.
        """,
        ConsentPurpose.ANALYTICS: """
        Autorizo el uso de mis datos de forma anonimizada para análisis 
        estadísticos del proceso de selección.
        """,
    }
    
    # Períodos de retención por propósito (en días)
    RETENTION_PERIODS = {
        ConsentPurpose.RECRUITMENT: 365,    # 1 año
        ConsentPurpose.TALENT_POOL: 730,    # 2 años
        ConsentPurpose.ANALYTICS: 1825,     # 5 años (anonimizado)
    }
    
    def __init__(self, db_session=None):
        self._db = db_session
        self._consents: Dict[str, List[ConsentRecord]] = {}  # In-memory fallback
    
    async def record_consent(
        self,
        candidate_id: str,
        purpose: ConsentPurpose,
        granted: bool,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> ConsentRecord:
        """
        Registra un consentimiento de tratamiento de datos.
        
        Args:
            candidate_id: ID del candidato
            purpose: Propósito del tratamiento
            granted: Si se otorgó o no el consentimiento
            ip_address: IP desde donde se dio el consentimiento
            user_agent: Navegador/dispositivo
            
        Returns:
            Registro de consentimiento creado
        """
        retention_days = self.RETENTION_PERIODS.get(purpose, 365)
        consent_text = self.CONSENT_TEXTS.get(purpose, "Consentimiento genérico")
        
        record = ConsentRecord(
            candidate_id=candidate_id,
            purpose=purpose,
            granted=granted,
            consent_date=datetime.utcnow(),
            expiry_date=datetime.utcnow() + timedelta(days=retention_days) if granted else None,
            consent_text=consent_text.strip(),
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Store (in-memory or DB)
        if candidate_id not in self._consents:
            self._consents[candidate_id] = []
        self._consents[candidate_id].append(record)
        
        logger.info(f"Consent recorded: {candidate_id} - {purpose.value} - {'granted' if granted else 'denied'}")
        
        return record
    
    async def check_consent(
        self,
        candidate_id: str,
        purpose: ConsentPurpose
    ) -> bool:
        """
        Verifica si existe consentimiento válido para un propósito.
        
        Returns:
            True si hay consentimiento válido y no expirado
        """
        consents = self._consents.get(candidate_id, [])
        
        for consent in reversed(consents):  # Más reciente primero
            if consent.purpose == purpose:
                if not consent.granted:
                    return False
                if consent.expiry_date and consent.expiry_date < datetime.utcnow():
                    return False  # Expirado
                return True
        
        return False  # Sin consentimiento registrado
    
    async def revoke_consent(
        self,
        candidate_id: str,
        purpose: ConsentPurpose
    ) -> bool:
        """
        Revoca un consentimiento existente.
        
        Conforme a LPDP, el titular puede revocar en cualquier momento.
        """
        return await self.record_consent(
            candidate_id=candidate_id,
            purpose=purpose,
            granted=False
        ) is not None


class AuditLogger:
    """
    Registra todos los accesos a datos personales para auditoría.

    Conforme a LPDP, se debe mantener registro de:
    - Quién accedió a los datos
    - Cuándo se accedió
    - Qué datos se accedieron
    - Con qué propósito

    Persiste a PostgreSQL cuando se provee una sesión de DB.
    """

    def __init__(self, db_session=None):
        self._db = db_session

    async def log_access(
        self,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Registra un acceso a datos personales.

        Args:
            user_id: ID del usuario que accede
            action: Tipo de acción (view, edit, delete, export)
            resource_type: Tipo de recurso (candidate, cv, note)
            resource_id: ID del recurso accedido
            ip_address: IP del usuario
            details: Detalles adicionales
        """
        logger.info(f"Audit: {user_id} {action} {resource_type}/{resource_id}")

        if self._db is not None:
            try:
                from app.db.models import AuditLogDB
                entry_db = AuditLogDB(
                    user_id=str(user_id),
                    action=action,
                    resource_type=resource_type,
                    resource_id=str(resource_id),
                    ip_address=ip_address,
                    details=details,
                )
                self._db.add(entry_db)
                await self._db.commit()
            except Exception as e:
                logger.warning(f"Failed to persist audit log: {e}")

    async def get_access_history(
        self,
        resource_id: str,
        limit: int = 100
    ) -> List[AuditLogEntry]:
        """Obtiene historial de accesos a un recurso desde PostgreSQL."""
        if self._db is not None:
            try:
                from sqlalchemy import select
                from app.db.models import AuditLogDB
                result = await self._db.execute(
                    select(AuditLogDB)
                    .where(AuditLogDB.resource_id == str(resource_id))
                    .order_by(AuditLogDB.timestamp.desc())
                    .limit(limit)
                )
                rows = result.scalars().all()
                return [
                    AuditLogEntry(
                        timestamp=r.timestamp,
                        user_id=r.user_id or "",
                        action=r.action,
                        resource_type=r.resource_type,
                        resource_id=r.resource_id,
                        ip_address=r.ip_address,
                        details=r.details,
                    )
                    for r in rows
                ]
            except Exception as e:
                logger.warning(f"Failed to retrieve audit logs: {e}")
        return []


class DataRetentionPolicy:
    """
    Gestiona políticas de retención de datos según LPDP.
    
    Los datos no deben conservarse más tiempo del necesario
    para la finalidad para la que fueron recopilados.
    """
    
    DEFAULT_RETENTION_DAYS = 730  # 2 años por defecto
    
    @staticmethod
    def get_expiry_date(purpose: ConsentPurpose) -> datetime:
        """Calcula fecha de expiración según propósito."""
        days = ConsentManager.RETENTION_PERIODS.get(purpose, 730)
        return datetime.utcnow() + timedelta(days=days)
    
    @staticmethod
    def is_expired(expiry_date: Optional[datetime]) -> bool:
        """Verifica si los datos han expirado."""
        if expiry_date is None:
            return False
        return datetime.utcnow() > expiry_date
    
    @staticmethod
    async def get_candidates_for_deletion(db_session) -> List[str]:
        """
        Obtiene lista de candidatos cuyos datos deben ser eliminados.
        
        Debería ejecutarse periódicamente (ej: cron job semanal).
        """
        # TODO: Implementar query a BD
        logger.info("Checking for candidates with expired data retention")
        return []


class ARCOPHandler:
    """
    Maneja las solicitudes de derechos ARCO-P del titular de datos.
    
    Plazos según LPDP:
    - Respuesta inicial: 20 días hábiles
    - Prórroga máxima: 20 días hábiles adicionales
    """
    
    RESPONSE_DEADLINE_DAYS = 20
    
    def __init__(self, db_session=None, audit_logger: Optional[AuditLogger] = None):
        self._db = db_session
        self._audit = audit_logger or AuditLogger()
    
    async def handle_access_request(
        self,
        candidate_id: str,
        requester_email: str
    ) -> Dict[str, Any]:
        """
        Maneja solicitud de acceso a datos personales.
        
        El titular tiene derecho a conocer qué datos tenemos sobre él.
        """
        await self._audit.log_access(
            user_id=requester_email,
            action="arco_access_request",
            resource_type="candidate",
            resource_id=candidate_id
        )
        
        # TODO: Obtener datos del candidato de la BD
        return {
            "request_type": "access",
            "candidate_id": candidate_id,
            "status": "pending",
            "deadline": (datetime.utcnow() + timedelta(days=self.RESPONSE_DEADLINE_DAYS)).isoformat(),
            "message": "Su solicitud ha sido recibida. Recibirá respuesta en un plazo máximo de 20 días hábiles."
        }
    
    async def handle_deletion_request(
        self,
        candidate_id: str,
        requester_email: str,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Maneja solicitud de cancelación (derecho al olvido).
        
        El titular puede solicitar la eliminación de sus datos.
        """
        await self._audit.log_access(
            user_id=requester_email,
            action="arco_deletion_request",
            resource_type="candidate",
            resource_id=candidate_id,
            details={"reason": reason}
        )
        
        # TODO: Marcar candidato para eliminación
        return {
            "request_type": "deletion",
            "candidate_id": candidate_id,
            "status": "pending",
            "deadline": (datetime.utcnow() + timedelta(days=self.RESPONSE_DEADLINE_DAYS)).isoformat(),
            "message": "Su solicitud de eliminación ha sido recibida. Será procesada en un plazo máximo de 20 días hábiles."
        }
    
    async def handle_portability_request(
        self,
        candidate_id: str,
        requester_email: str,
        format: str = "json"
    ) -> Dict[str, Any]:
        """
        Maneja solicitud de portabilidad de datos.
        
        El titular puede solicitar sus datos en formato estructurado
        para transferirlos a otro servicio.
        """
        await self._audit.log_access(
            user_id=requester_email,
            action="arco_portability_request",
            resource_type="candidate",
            resource_id=candidate_id,
            details={"format": format}
        )
        
        # TODO: Generar exportación
        return {
            "request_type": "portability",
            "candidate_id": candidate_id,
            "status": "pending",
            "format": format,
            "deadline": (datetime.utcnow() + timedelta(days=self.RESPONSE_DEADLINE_DAYS)).isoformat(),
            "message": f"Su solicitud de portabilidad en formato {format} ha sido recibida."
        }


# Singleton instances
_consent_manager: Optional[ConsentManager] = None
_audit_logger: Optional[AuditLogger] = None
_arcop_handler: Optional[ARCOPHandler] = None


def get_consent_manager() -> ConsentManager:
    """Obtiene instancia singleton del gestor de consentimientos."""
    global _consent_manager
    if _consent_manager is None:
        _consent_manager = ConsentManager()
    return _consent_manager


def get_audit_logger() -> AuditLogger:
    """Obtiene instancia singleton del logger de auditoría."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


def get_arcop_handler() -> ARCOPHandler:
    """Obtiene instancia singleton del manejador ARCO-P."""
    global _arcop_handler
    if _arcop_handler is None:
        _arcop_handler = ARCOPHandler()
    return _arcop_handler
