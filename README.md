# Banking Architecture Lab

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
| Auditoría | Procesar eventos repetidos y reinicios de consumidores | Outbox/inbox, Kafka, microservicio independiente |

El núcleo no depende de frameworks. ASP.NET Core y Spring Boot son adaptadores de entrada; PostgreSQL y Kafka son adaptadores de salida. El servicio de auditoría mantiene su propia base de datos. Las versiones son alternativas del mismo servicio, no dos escritores de una base compartida.

## Tecnologías

.NET 10 LTS, Java 21 LTS, Spring Boot 4.1, PostgreSQL, Apache Kafka, Docker Compose, Kubernetes, GitHub Actions y OpenTelemetry. La justificación, las fuentes de contratación y los límites del muestreo están en [docs/technology-selection.md](docs/technology-selection.md).

## Ejecución

Las instrucciones verificadas, requisitos y resultados se incorporan junto a cada implementación. Consulte [docs/exercises.md](docs/exercises.md), [docs/architecture.md](docs/architecture.md) y [docs/verification.md](docs/verification.md).

Este repositorio es un portafolio ejecutable. Las reglas de identidad y riesgo son ejemplos educativos y no certifican cumplimiento regulatorio ni sustituyen controles de una institución financiera.
