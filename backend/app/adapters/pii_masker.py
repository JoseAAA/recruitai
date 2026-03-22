"""
PII Masker - Anonimización Reversible para Protección de Datos
==============================================================

Implementa anonimización reversible usando Microsoft Presidio para
cumplir con la Ley de Protección de Datos Personales de Perú (LPDP).

Características:
- Detecta PII: nombres, emails, teléfonos, DNI, direcciones
- Reemplaza con tokens únicos reversibles
- Encripta el mapping con Fernet (AES-256)
- Permite restaurar datos después de respuesta LLM

Uso:
    masker = PIIMasker()
    masked_text, mapping = masker.mask("Juan Pérez, DNI 12345678")
    # masked_text = "[PERSON_1], DNI [DNI_1]"
    # mapping = {"PERSON_1": "encrypted(Juan Pérez)", ...}
    
    # Después de LLM response:
    original = masker.unmask(llm_response, mapping)
"""

import re
import hashlib
import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from cryptography.fernet import Fernet
import os
import json
import base64

logger = logging.getLogger(__name__)

# Flag para usar Presidio si está disponible
_PRESIDIO_AVAILABLE = False
try:
    from presidio_analyzer import AnalyzerEngine, RecognizerRegistry, Pattern, PatternRecognizer
    from presidio_anonymizer import AnonymizerEngine
    from presidio_anonymizer.entities import OperatorConfig
    _PRESIDIO_AVAILABLE = True
    logger.info("Presidio disponible - usando detección avanzada de PII")
except ImportError:
    logger.warning("Presidio no instalado - usando detección básica de PII")


@dataclass
class PIIEntity:
    """Representa una entidad PII detectada."""
    type: str
    value: str
    start: int
    end: int
    score: float


class PIIMasker:
    """
    Anonimizador reversible de PII para proteger datos antes de enviar a LLM.
    
    Cumple con:
    - LPDP Perú (Ley 29733)
    - GDPR (para referencias internacionales)
    - OWASP LLM Security Guidelines
    """
    
    # Tipos de PII a detectar
    ENTITY_TYPES = [
        "PERSON",           # Nombres completos
        "EMAIL_ADDRESS",    # Correos electrónicos
        "PHONE_NUMBER",     # Teléfonos
        "DNI_PERU",         # DNI peruano (8 dígitos)
        "RUC_PERU",         # RUC (11 dígitos)
        "LOCATION",         # Direcciones
        "DATE_TIME",        # Fechas de nacimiento
        "CREDIT_CARD",      # Tarjetas de crédito
        "IBAN_CODE",        # Cuentas bancarias
        "IP_ADDRESS",       # IPs
    ]
    
    # Patrones básicos para fallback sin Presidio
    BASIC_PATTERNS = {
        "EMAIL": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        "PHONE_PE": r'\b(?:\+51|51)?[\s.-]?9\d{2}[\s.-]?\d{3}[\s.-]?\d{3}\b',
        "PHONE_GENERIC": r'\b\d{3}[\s.-]?\d{3}[\s.-]?\d{3,4}\b',
        "DNI_PERU": r'\b\d{8}\b',  # 8 dígitos
        "RUC_PERU": r'\b(?:10|20)\d{9}\b',  # 11 dígitos, empieza con 10 o 20
        "CREDIT_CARD": r'\b\d{4}[\s.-]?\d{4}[\s.-]?\d{4}[\s.-]?\d{4}\b',
    }
    
    def __init__(self, encryption_key: Optional[str] = None):
        """
        Inicializa el masker con encriptación.
        
        Args:
            encryption_key: Clave Fernet base64. Si no se proporciona,
                           se usa ENCRYPTION_KEY del entorno o se genera una.
        """
        # Configurar encriptación
        if encryption_key:
            self._fernet = Fernet(encryption_key.encode())
        else:
            key = os.getenv("ENCRYPTION_KEY")
            if key:
                self._fernet = Fernet(key.encode())
            else:
                # Generar clave temporal (solo para desarrollo)
                logger.warning("ENCRYPTION_KEY no configurada - usando clave temporal")
                self._fernet = Fernet(Fernet.generate_key())
        
        # Inicializar Presidio si está disponible
        self._analyzer = None
        self._anonymizer = None
        if _PRESIDIO_AVAILABLE:
            self._setup_presidio()
    
    def _setup_presidio(self):
        """Configura Presidio con reconocedores personalizados para Perú."""
        try:
            registry = RecognizerRegistry()
            registry.load_predefined_recognizers(languages=["es", "en"])
            
            # Agregar reconocedor de DNI peruano
            dni_pattern = Pattern(
                name="dni_peru_pattern",
                regex=r"\b\d{8}\b",
                score=0.7
            )
            dni_recognizer = PatternRecognizer(
                supported_entity="DNI_PERU",
                patterns=[dni_pattern],
                supported_language="es"
            )
            registry.add_recognizer(dni_recognizer)
            
            # Agregar reconocedor de RUC peruano
            ruc_pattern = Pattern(
                name="ruc_peru_pattern",
                regex=r"\b(?:10|20)\d{9}\b",
                score=0.85
            )
            ruc_recognizer = PatternRecognizer(
                supported_entity="RUC_PERU",
                patterns=[ruc_pattern],
                supported_language="es"
            )
            registry.add_recognizer(ruc_recognizer)
            
            # Agregar reconocedor de teléfonos peruanos
            phone_pattern = Pattern(
                name="phone_peru_pattern",
                regex=r"(?:\+51|51)?[\s.-]?9\d{2}[\s.-]?\d{3}[\s.-]?\d{3}",
                score=0.75
            )
            phone_recognizer = PatternRecognizer(
                supported_entity="PHONE_NUMBER",
                patterns=[phone_pattern],
                supported_language="es"
            )
            registry.add_recognizer(phone_recognizer)
            
            self._analyzer = AnalyzerEngine(registry=registry)
            self._anonymizer = AnonymizerEngine()
            
            logger.info("Presidio configurado con reconocedores para Perú")
            
        except Exception as e:
            logger.error(f"Error configurando Presidio: {e}")
            self._analyzer = None
            self._anonymizer = None
    
    def _encrypt(self, value: str) -> str:
        """Encripta un valor con Fernet (AES-256)."""
        encrypted = self._fernet.encrypt(value.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    
    def _decrypt(self, encrypted_value: str) -> str:
        """Desencripta un valor."""
        try:
            data = base64.urlsafe_b64decode(encrypted_value.encode())
            return self._fernet.decrypt(data).decode()
        except Exception as e:
            logger.error(f"Error desencriptando: {e}")
            return "[DECRYPT_ERROR]"
    
    def _detect_pii_basic(self, text: str) -> List[PIIEntity]:
        """Detección básica de PII usando regex (fallback)."""
        entities = []
        
        for entity_type, pattern in self.BASIC_PATTERNS.items():
            for match in re.finditer(pattern, text, re.IGNORECASE):
                entities.append(PIIEntity(
                    type=entity_type,
                    value=match.group(),
                    start=match.start(),
                    end=match.end(),
                    score=0.7
                ))
        
        return entities
    
    def _detect_pii_presidio(self, text: str) -> List[PIIEntity]:
        """Detección avanzada usando Presidio."""
        entities = []
        
        try:
            results = self._analyzer.analyze(
                text=text,
                language="es",
                entities=self.ENTITY_TYPES
            )
            
            for result in results:
                entities.append(PIIEntity(
                    type=result.entity_type,
                    value=text[result.start:result.end],
                    start=result.start,
                    end=result.end,
                    score=result.score
                ))
                
        except Exception as e:
            logger.error(f"Error en análisis Presidio: {e}")
            # Fallback a detección básica
            entities = self._detect_pii_basic(text)
        
        return entities
    
    def detect(self, text: str, min_score: float = 0.5) -> List[PIIEntity]:
        """
        Detecta todas las entidades PII en el texto.
        
        Args:
            text: Texto a analizar
            min_score: Puntuación mínima de confianza (0-1)
            
        Returns:
            Lista de entidades PII detectadas
        """
        if not text:
            return []
        
        if self._analyzer:
            entities = self._detect_pii_presidio(text)
        else:
            entities = self._detect_pii_basic(text)
        
        # Filtrar por puntuación mínima
        entities = [e for e in entities if e.score >= min_score]
        
        # Ordenar por posición (de mayor a menor para reemplazo seguro)
        entities.sort(key=lambda x: x.start, reverse=True)
        
        return entities
    
    def mask(self, text: str, min_score: float = 0.5) -> Tuple[str, Dict[str, str]]:
        """
        Anonimiza PII en el texto con tokens reversibles.
        
        Args:
            text: Texto original con PII
            min_score: Puntuación mínima para detectar PII
            
        Returns:
            Tuple de (texto_anonimizado, mapping_encriptado)
            
        Ejemplo:
            >>> masker.mask("Contactar a Juan Pérez, email: juan@email.com")
            ("[PERSON_1], email: [EMAIL_1]", {"PERSON_1": "enc(...)", "EMAIL_1": "enc(...)"})
        """
        if not text:
            return text, {}
        
        entities = self.detect(text, min_score)
        
        if not entities:
            return text, {}
        
        masked_text = text
        mapping = {}
        counters = {}
        
        # Procesar de atrás hacia adelante para mantener posiciones
        for entity in entities:
            # Generar token único
            entity_type = entity.type.replace("_", "")
            counters[entity_type] = counters.get(entity_type, 0) + 1
            token = f"[{entity_type}_{counters[entity_type]}]"
            
            # Reemplazar en texto
            masked_text = (
                masked_text[:entity.start] + 
                token + 
                masked_text[entity.end:]
            )
            
            # Guardar mapping encriptado
            mapping[token] = self._encrypt(entity.value)
        
        logger.info(f"Masked {len(entities)} PII entities")
        return masked_text, mapping
    
    def unmask(self, text: str, mapping: Dict[str, str]) -> str:
        """
        Restaura los valores originales de PII.
        
        Args:
            text: Texto con tokens de anonimización
            mapping: Mapping encriptado de tokens a valores
            
        Returns:
            Texto con valores originales restaurados
        """
        if not text or not mapping:
            return text
        
        result = text
        
        for token, encrypted_value in mapping.items():
            original_value = self._decrypt(encrypted_value)
            result = result.replace(token, original_value)
        
        return result
    
    def get_pii_summary(self, text: str) -> Dict[str, int]:
        """
        Retorna un resumen de tipos de PII encontrados.
        Útil para auditoría y compliance.
        """
        entities = self.detect(text)
        summary = {}
        
        for entity in entities:
            summary[entity.type] = summary.get(entity.type, 0) + 1
        
        return summary
    
    @staticmethod
    def generate_encryption_key() -> str:
        """Genera una nueva clave de encriptación Fernet."""
        return Fernet.generate_key().decode()


# Instancia singleton para uso global
_masker_instance: Optional[PIIMasker] = None


def get_pii_masker() -> PIIMasker:
    """Obtiene la instancia singleton del PIIMasker."""
    global _masker_instance
    if _masker_instance is None:
        _masker_instance = PIIMasker()
    return _masker_instance


# Funciones de conveniencia
def mask_pii(text: str) -> Tuple[str, Dict[str, str]]:
    """Función de conveniencia para anonimizar texto."""
    return get_pii_masker().mask(text)


def unmask_pii(text: str, mapping: Dict[str, str]) -> str:
    """Función de conveniencia para restaurar texto."""
    return get_pii_masker().unmask(text, mapping)
