# Banking Architecture Lab

[![CI](https://github.com/jorgefprietol/banking-architecture-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/jorgefprietol/banking-architecture-lab/actions/workflows/ci.yml)

Casos de ingeniería de software para banca digital y sistemas de reservas, con implementaciones equivalentes en C# y Java. Datos sintéticos; reglas de negocio explícitas; pruebas que verifican invariantes y fallos.

## Casos

| Caso | Problema | Diseño |
| --- | --- | --- |
| Transferencias | Evitar sobregiros, duplicados y dinero creado por concurrencia | DDD, hexagonal, doble partida, transacciones |
| Historial de cuentas | Reconstruir saldos y consultar sin mutar el agregado | Event sourcing, CQRS, proyecciones |
| Apertura de cuentas | Validar identidad, aprobar o compensar una solicitud | Máquina de estados, saga, puertos externos |
| Riesgo | Incorporar reglas independientes con resultados explicables | Microkernel, plugins de dominio |
| Conciliación | Detectar diferencias y referencias duplicadas | Arquitectura de tres capas, anticorrupción |
| Reservas | Evitar sobreventa y liberar stock al cancelar | Agregados, concurrencia optimista |
| Auditoría | Procesar repeticiones y aislar eventos inválidos sin bloquear particiones | Outbox/inbox, cuarentena durable, Kafka DLQ |
| Operación | Detectar entregas atrasadas y medir cargas repetibles | Alertas de antigüedad, carga con semilla, promoción de imágenes probadas |

El núcleo no depende de frameworks. ASP.NET Core y Spring Boot son adaptadores de entrada; PostgreSQL y Kafka son adaptadores de salida. El servicio de auditoría mantiene su propia base de datos. Las versiones son alternativas del mismo servicio, no dos escritores de una base compartida.

## Tecnologías

.NET 10 LTS, Java 21 LTS, Spring Boot 4.1, PostgreSQL, Apache Kafka, Docker Compose, Kubernetes, GitHub Actions y OpenTelemetry. La justificación, las fuentes de contratación y los límites del muestreo están en [docs/technology-selection.md](docs/technology-selection.md).

## Ejecución

Requisitos: Docker con contenedores Linux, Compose v2 y Python 3.10+. En Windows puede usarse py en lugar de python.

    python scripts/setup.py
    docker compose up --build -d
    python scripts/migrate.py
    python scripts/integration_test.py
    python scripts/recovery_test.py
    python scripts/load_test.py --seed 42 --iterations 80 --pairs 4 --concurrency 8

Las compilaciones de contenedores ejecutan las suites unitarias. La aceptación usa PostgreSQL, Kafka y Keycloak reales y valida ambas APIs contra el mismo contrato OpenAPI. Las credenciales se generan localmente y permanecen fuera de Git.

- APIs: http://localhost:19081/health/ready y http://localhost:19082/health/ready.
- Trazas: http://localhost:19686.
- [Ejercicios y defensa en entrevista](docs/exercises.md), [mapa completo del temario](docs/learning-guide.md) y [decisiones de arquitectura](docs/architecture.md).
- [Operación, recuperación y Kubernetes](docs/runbook.md), [resultados observados](docs/verification.md) y [política de seguridad](SECURITY.md).

El pipeline verifica pruebas, contratos, invariantes, recuperación, carga, backups y vulnerabilidades. Exporta las tres imágenes probadas con sus IDs, checksum y SBOM. La publicación manual carga ese mismo paquete, comprueba las identidades antes y después de enviarlas a GHCR y añade attestations; no reconstruye imágenes. Consulte [.github/workflows](.github/workflows).

Este repositorio es un portafolio ejecutable. Las reglas de identidad y riesgo son ejemplos educativos y no certifican cumplimiento regulatorio ni sustituyen controles de una institución financiera.
