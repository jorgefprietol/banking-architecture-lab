# Verificación

Este documento registra exclusivamente comandos ejecutados y resultados observados. Los manifiestos de despliegue no implican que exista un entorno cloud desplegado.

Fecha: 2026-10-02. Entorno local: Windows, Docker Desktop con contenedores Linux y clúster kind independiente banking-architecture. Se conservaron los otros proyectos y clústeres del equipo.

| Comprobación ejecutada | Resultado |
| --- | --- |
| C# / .NET 10, dotnet test | 33 pruebas, cero fallos |
| Java, mvn verify con compilación release 21 y runtime JDK 25 | 32 pruebas, cero fallos |
| Aceptación contra las dos APIs de Compose | 20 escenarios, cero fallos y errores; 188.042 segundos |
| Misma aceptación contra ambas APIs en Kubernetes | 20 escenarios, cero fallos y errores; 114.905 segundos |
| Proyección de saldos y versiones vs historial | projection_drift=0 en ambas bases |
| Apuntes de transferencias | unbalanced_postings=0 en ambas bases |
| Recreación de Kafka | IDs de temas y offsets conservados en las seis particiones de aplicación |
| Restauración de backups | Cuatro bases restauradas en bases temporales nuevas; registros y saldos comprobados coinciden |
| Trazas con traceparent nuevo | Ambas APIs exportaron a Jaeger los IDs propagados, también desde Kubernetes |
| Trivy 0.75.0, tres imágenes de aplicación | Cero hallazgos HIGH/CRITICAL; sin exclusiones ni ignore-unfixed |
| Fronteras de arquitectura y contrato versionado | Comprobación satisfactoria |
| Manifiestos Kubernetes | Validación del servidor y cuatro pods Ready, cero reinicios al finalizar la aceptación |

Los escenarios cubren JWT y roles, propiedad de cuentas, doble partida, replay, reintentos, conflictos de idempotencia, 24 reintentos concurrentes, conservación de dinero, sobregiros, JSON estricto, rollback ante fallo de outbox, plugins, conciliación, duplicados, caída de Kafka, eventos inmutables, reservas concurrentes, apertura idempotente y restricciones contables diferidas. La base también rechazó un tercer apunte añadido a una transferencia ya confirmada.

## Reproducir

    dotnet restore Banking.sln --locked-mode
    dotnet test Banking.sln -c Release --collect:"XPlat Code Coverage"
    mvn -B -ntp -f java/pom.xml verify
    python scripts/check_architecture.py
    python scripts/setup.py
    docker compose up --build -d
    python scripts/migrate.py
    python scripts/integration_test.py
    python scripts/broker_persistence_test.py
    python scripts/check_ledger_invariants.py
    python scripts/backup_restore_test.py
    python scripts/verify_telemetry.py
    python scripts/security_scan.py

La configuración y los comandos de Kubernetes están en [runbook.md](runbook.md). Los informes completos permanecen en artifacts; [verification-summary.json](verification-summary.json) conserva los resultados resumidos y los identificadores de las imágenes escaneadas.

## Interpretar la evidencia

Cada uno de los 20 escenarios recorre ambas implementaciones. Las 40 solicitudes de la muestra de latencia compiten por una misma pareja de cuentas, con 12 clientes concurrentes: en Compose se observaron p95 de 1079 ms para C# y 859 ms para Java. El equipo ejecutaba otros servicios; estos números describen contención local y no estiman capacidad de producción ni comparan rendimiento entre lenguajes.

Las pruebas unitarias producen cobertura con Coverlet y JaCoCo; la aceptación valida infraestructura real por separado. El escaneo cubre las imágenes ledger-csharp, audit-csharp y java y la base de vulnerabilidades disponible durante la ejecución. La apertura HTTP es una transacción local con identidad sintética; la compensación de saga se verifica en pruebas del dominio.

CI publica resultados unitarios, cobertura, aceptación, recuperación, carga e informes de vulnerabilidades en los artefactos de GitHub Actions. Las acciones están fijadas por SHA. La publicación manual promueve las imágenes probadas de la misma ejecución, conserva sus identidades y añade attestations de procedencia y SBOM. Los enlaces de ejecución permiten consultar el estado actual.

## Verificación después de actualizar dependencias

Se incorporaron las actualizaciones integradas de xunit.runner.visualstudio 4.0.0 y coverlet.collector 10.1.0. La suite local con cobertura volvió a pasar sus 33 pruebas. Maven 3 con JDK 25 pasó las 32 pruebas de Java; la aceptación de las imágenes reconstruidas pasó los 20 escenarios en 97.314 segundos. Las dos comprobaciones de invariantes y las trazas nuevas volvieron a pasar; el nuevo escaneo de las tres imágenes registró cero HIGH/CRITICAL. La política de compilación preserva JDK 25 LTS ante propuestas de imágenes con otras líneas.

## Recuperación y entrega de imágenes

La ampliación añade cuarentena durable y DLQ, alerta por antigüedad del outbox, carga con semilla y promoción del paquete probado. Se verificó primero con binarios nativos en Windows (.NET 10 y Java 21) contra PostgreSQL, Kafka y Keycloak locales. C# pasó 58 pruebas y Java 41; seis comprobaciones de herramientas verificaron alteraciones del paquete, commit/ejecución incorrectos, rutas inválidas, imágenes incompletas, reproducibilidad y percentiles.

Los 20 escenarios de aceptación pasaron en 84.570 segundos. Los dos escenarios nuevos pasaron en 139.682 segundos y recorrieron ambas versiones: ocho rechazos por lenguaje, preservación del mensaje, continuidad de la partición, conflicto de identidad, evidencia inmutable, repetición de entrega con el mismo failureId y alerta/recuperación del outbox. Las cuatro restauraciones incluyeron la cuarentena y volvieron a coincidir; las proyecciones y apuntes no registraron diferencias.

La carga usó semilla 42, cuatro parejas y ocho clientes: 80 transferencias únicas y ocho reintentos por versión, con saldos y recibos verificados. La huella del trabajo y los resultados quedan en verification-summary.json. Son muestras sintéticas cortas en un host compartido; no estiman capacidad de producción ni comparan los lenguajes.

La primera inicialización sufrió una interrupción de infraestructura y otra ejecución agotó el tiempo de arranque de Keycloak. La verificación final usa control del contenedor exacto de Kafka y reintentos limitados del cliente de identidad; mantiene el rechazo de credenciales inválidas y tokens cortos. Los procesos nativos se cerraron al terminar; las bases y sus volúmenes se conservaron.

Las imágenes reconstruidas de Docker (.NET 10 y Java 25) también pasaron los 20 escenarios en 92.753 segundos y los dos nuevos en 112.744 segundos. La misma carga registró p95 de 55.493 ms y 77.088 ms, respectivamente, usando reloj de alta resolución. Las doce particiones, incluidas las DLQ, conservaron IDs y offsets después de recrear el broker. Las invariantes volvieron a pasar y las dos trazas nuevas llegaron a Jaeger. Trivy registró cero HIGH/CRITICAL en las tres imágenes nuevas, sin exclusiones.
