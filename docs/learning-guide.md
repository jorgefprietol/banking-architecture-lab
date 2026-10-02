# Guía de práctica y trazabilidad

Leer el requisito, ejecutar el escenario, alterar deliberadamente una invariante y comprobar qué prueba lo detecta. Repetir en C# y Java antes de comparar diseños.

| Tema del temario | Evidencia ejecutable | Coste / límite |
| --- | --- | --- |
| Arquitectura convencional | ReconciliationBatch y CsvSettlementSource: entrada, negocio y adaptación de datos | Suficiente para batches pequeños; no ofrece garantías distribuidas |
| DDD, lenguaje ubicuo | Money, Account, Transfer e Inventory | Agregados pequeños; evitar modelos anémicos y agregados gigantes |
| Contextos y mapeo | Ledger, Onboarding, Risk, Reconciliation, Inventory y Audit | La frontera organizativa se explica en architecture.md |
| Entidades y value objects | Cuenta identificable; dinero validado e inmutable | USD/EUR de dos decimales; no hay FX implícito |
| Modelo de dominio vs persistencia | AccountEvent/Account frente a tablas SQL y adaptadores | SQL explícito mantiene visibles transacciones y bloqueos |
| Servicios de dominio | Transfer y RiskEngine | Las reglas no conocen HTTP, JDBC, Kafka ni ASP.NET |
| CQRS | Payments/TransferCommand frente a AccountView y History | Código y modelo separados; misma base para coherencia local |
| CQRS avanzado | Audit tiene su propia proyección y base, alimentadas por Kafka | Lectura eventualmente consistente; retraso observable |
| Event sourcing | account_events, Replay y check_ledger_invariants.py | Sin snapshots todavía; replay O(n), versiones de esquema necesarias |
| Programación por eventos | EventDispatcher y pruebas de suscriptores | En memoria, síncrona; no garantiza entrega tras una caída |
| Arquitectura por eventos | OutboxRelay -> Kafka -> AuditWorker/inbox | Al menos una vez, deduplicación; sin exactamente una vez global |
| Microservicios | Ledger y Audit, imágenes y almacenes independientes | Solo se extrae el contexto con necesidades distintas |
| Despliegue distribuido | Compose y Kubernetes local | Un broker y un servidor PostgreSQL; no simula HA regional |
| Seguridad y monitorización | Keycloak, JWT, roles, propietario, Jaeger y logs | HTTP y usuarios sintéticos de laboratorio |
| Hexagonal | Puertos en Application y adaptadores en Infrastructure | Las dependencias apuntan hacia dentro |
| Microkernel | IRiskRule / RiskEngine.Rule: cantidad, velocidad y sanciones | Plugins conocidos al construir; sin carga arbitraria de binarios |
| Arquitectura testable | Unitarias, aceptación común, fallos reales y check_architecture.py | Cobertura medida por suite; no representa dominio de producción |
| Arquitectura evolutiva | Migraciones numeradas, contratos v1 y ADR | Migrar datos y consumidores antes de romper contratos |
| Arquitectura sacrificable | CSV de proveedor e identidad sintética reemplazables por puertos | Reemplazar adaptadores sin cambiar reglas monetarias |

## Recorrido

1. Ejecutar las suites y leer los resultados.
2. Rastrear una transferencia desde el controlador hasta PostgreSQL. Identificar el momento exacto del commit.
3. Seguir su contrato en outbox, Kafka e inbox. Repetir la entrega y comprobar que no hay otro efecto.
4. Detener Kafka durante una transferencia. Explicar por qué hay dinero confirmado antes de aparecer en Audit.
5. Abrir una cuenta con referencia sintética verificada y repetir la misma solicitud. Contrastar con el ejemplo compensatorio de Onboarding del dominio.
6. Reservar stock con una versión obsoleta y cancelar dos veces. Explicar por qué el reintento exacto se acepta antes de revisar la versión.
7. Añadir un plugin de riesgo y una prueba de sus razones. Ninguna regla existente debe editarse.
8. Cambiar la proyección de lectura en una copia y reconstruir desde eventos. Mantener intacto el historial.

## Separar conocimiento de afirmaciones de experiencia

El repositorio acredita resultados reproducibles, diseño y capacidad de explicar alternativas. No representa experiencia laboral con bancos, un sistema certificado ni resultados de carga en producción. Las decisiones y pruebas se pueden defender mostrando el código, sus fallos y sus límites.
