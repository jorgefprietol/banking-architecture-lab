# Operación local

## Arranque reproducible

Requisitos: Docker con contenedores Linux, Compose v2, Python 3.10+. Para compilar fuera de contenedores: SDK .NET 10.0.401, Maven 3.9+ y JDK 21+.

    python scripts/setup.py
    docker compose up --build -d
    python scripts/migrate.py
    python scripts/integration_test.py
    python scripts/check_ledger_invariants.py
    python scripts/broker_persistence_test.py
    python scripts/backup_restore_test.py
    python scripts/verify_telemetry.py
    python scripts/security_scan.py

En Windows con launcher de Python usar py en lugar de python. El primer arranque descarga imágenes; las compilaciones de Docker ejecutan las pruebas unitarias antes de publicar. Java compila para 21 y se prueba además sobre JDK 25 en la imagen.

| Servicio | Dirección |
| --- | --- |
| Ledger C# | http://localhost:19081/health/ready |
| Ledger Java | http://localhost:19082/health/ready |
| Keycloak | http://localhost:18180 |
| Jaeger | http://localhost:19686 |

setup.py guarda contraseñas aleatorias en .env y genera un realm sintético en artifacts/keycloak. No subir estos archivos. Los usuarios alice, bob y guest tienen permisos distintos. El grant de contraseña se habilita únicamente para pruebas locales automatizadas; una aplicación interactiva debe usar authorization code con PKCE. La cuenta admin de Keycloak usa la contraseña KC_ADMIN_PASSWORD.

## Fallos y recuperación

- Broker caído: ledger sigue confirmando transacciones y acumula outbox; revisar SELECT count(*) FROM outbox WHERE published_at IS NULL. Al volver Kafka, el relay entrega pendientes.
- Caída después de publicar: puede repetirse el evento; la clave primaria del inbox evita repetir el efecto. Confirmar offsets después de persistir.
- Error de base de datos: rollback revierte saldos, recibo, eventos y outbox. Revisar logs con trace ID; ningún token ni contraseña debe registrarse.
- Evento inválido o contrato desconocido: audit guarda el mensaje original y su posición en dead_letters antes de confirmar el offset. Un relay independiente entrega el rechazo a transfers.csharp.dlq.v1 o transfers.java.dlq.v1. Revisar error_code y la versión antes de reprocesar un mensaje corregido. La cuarentena preserva datos sintéticos; un entorno real debe definir acceso y retención para mensajes sensibles.
- Proyección corrupta: reconstruir desde eventos a una tabla nueva, comparar saldos y versiones y cambiar la lectura después de validar. Conservar una copia verificable.

    docker compose ps
    docker compose logs --tail 80 ledger-csharp ledger-java audit-csharp audit-java
    docker compose stop
    docker compose start

Los volúmenes se conservan al detener el laboratorio. La migración v1 solo se aplica al inicializar un volumen nuevo; modificaciones posteriores requieren migraciones nuevas. No ejecutar limpiezas globales de Docker ni borrar volúmenes de otros proyectos.

Kafka usa explícitamente el directorio persistente /tmp/kraft-combined-logs. La comprobación de persistencia recrea únicamente este broker y verifica los IDs y offsets de las doce particiones de aplicación, incluidas las DLQ. La prueba de backup restaura cada base en una base temporal nueva y elimina únicamente los recursos que ella misma creó.

## Kubernetes local

Instalar kind y kubectl. Los manifiestos conectan con la infraestructura de Compose por host.docker.internal; no necesitan credenciales cloud. Se utiliza un kubeconfig explícito para evitar cambiar el contexto de otros clústeres.

    python scripts/generate_k8s.py
    kind create cluster --name banking-architecture --config k8s/kind.yaml --kubeconfig artifacts/k8s/kubeconfig
    kind load docker-image banking-ledger-csharp:local banking-audit-csharp:local banking-java:local --name banking-architecture
    kubectl --kubeconfig artifacts/k8s/kubeconfig apply -f k8s/local.json
    kubectl --kubeconfig artifacts/k8s/kubeconfig apply -f artifacts/k8s/secret.json
    kubectl --kubeconfig artifacts/k8s/kubeconfig -n banking-lab rollout status deployment/ledger-csharp --timeout=600s
    kubectl --kubeconfig artifacts/k8s/kubeconfig -n banking-lab rollout status deployment/ledger-java --timeout=600s

Abrir dos terminales para los port-forward:

    kubectl --kubeconfig artifacts/k8s/kubeconfig -n banking-lab port-forward service/ledger-csharp 19981:8080
    kubectl --kubeconfig artifacts/k8s/kubeconfig -n banking-lab port-forward service/ledger-java 19982:8080

Ejecutar la misma aceptación indicando BASE_CSHARP=http://127.0.0.1:19981 y BASE_JAVA=http://127.0.0.1:19982 como variables de entorno. Detener previamente las cuatro aplicaciones de Compose, conservando la infraestructura, facilita observar consumidores sin otras réplicas.

El namespace aplica Pod Security restricted; los contenedores no usan root, eliminan capacidades, no montan tokens de Kubernetes y tienen límites de recursos y probes de API. La compatibilidad failCgroupV1:false de kind se limita a Docker Desktop local cuando usa cgroup v1. Un entorno nuevo debe usar cgroup v2 según las [recomendaciones de Kubernetes](https://v1-35.docs.kubernetes.io/docs/concepts/architecture/cgroups/).

Después de verificar Kubernetes se pueden escalar estas cuatro aplicaciones a cero y volver a iniciar las de Compose para usar los puertos 19081 y 19082. El kubeconfig, el namespace y los manifiestos permiten reactivar el despliegue local sin recrear la infraestructura.

## CI y publicación

CI corre con cada push y PR. Las acciones se fijan por SHA; Dependabot propone actualizaciones. Las pruebas generan cobertura y artefactos de resultados. security_scan.py falla si Trivy encuentra vulnerabilidades HIGH o CRITICAL en las tres imágenes de aplicación.

Publish verified images se ejecuta manualmente desde GitHub Actions y exige repetir CI antes de publicar en GHCR. Antes de exportar, CI compara los IDs con los cuatro contenedores probados y con los escaneos Trivy. Exporta tested-images: un archivo Docker save, manifest.json con IDs y checksums, y tres SBOM CycloneDX. Release descarga el artefacto de esa misma ejecución, valida commit y runId, carga las imágenes, etiqueta por commit y publica sin rebuild. Después las descarga por digest y compara nuevamente sus IDs. promotion-evidence conserva los resultados y las attestations de procedencia y SBOM pueden verificarse con gh attestation verify. No requiere tokens de larga duración. Véase la documentación de [actions/attest](https://github.com/actions/attest).

## Cuarentena y entrega a DLQ

dead_letters tiene una clave única por tema, partición y offset. Los roles de auditoría solo pueden insertar, consultar y marcar published_at; no pueden modificar la evidencia ni borrarla. Un fallo de PostgreSQL impide confirmar el offset de origen. Si Kafka falla después de guardar el rechazo, este sigue pendiente y se entrega al recuperarse el broker.

La entrega a DLQ puede repetirse si hay una caída entre publicar y marcar published_at. failureId se mantiene estable y permite deduplicar el rechazo. Los reintentos idénticos de eventos válidos no duplican inbox; reutilizar eventId o transferId con otro contenido produce event_identity_conflict. No se reemplaza la evidencia original.

    python scripts/migrate.py
    python scripts/recovery_test.py

Para observar pendientes, consultar SELECT id,error_code,source_topic,source_partition,source_offset FROM dead_letters WHERE published_at IS NULL en la base audit correspondiente. La recuperación de un evento de otra versión requiere un consumidor compatible y revisión de su identidad y efecto; no se saltan offsets manualmente.

## Alertas y carga

GET /api/operations/outbox exige el rol admin y devuelve pending, oldestAgeSeconds, thresholdSeconds y alert. OUTBOX_MAX_AGE_SECONDS vale 60 por defecto y admite 1..86400. Con pendientes cuya antigüedad alcanza el umbral, el monitor emite outbox_stale; al salir de esa condición emite outbox_recovered. La consulta y el monitor funcionan independientemente del relay cuando Kafka está caído.

    python scripts/load_test.py --seed 42 --iterations 200 --pairs 4 --concurrency 8

Cada décima operación se reintenta con la misma clave. La semilla fija la distribución de cuentas, montos y orden; un UUID de ejecución nuevo evita colisiones con pruebas previas. workloadSha256 identifica la carga, mientras que los datos de negocio cambian de identidad en cada ejecución. La prueba falla ante respuestas incorrectas, recibos cambiados o saldos distintos a los calculados. artifacts/load conserva p50/p95/p99 y solicitudes por segundo. --max-p95-ms permite imponer un presupuesto explícito en un equipo controlado; las mediciones locales de un host compartido no describen capacidad de producción.

## Verificación con procesos nativos

Si compilar contenedores y ejecutar otros proyectos a la vez supera los recursos del equipo, se pueden probar las aplicaciones compiladas contra la misma infraestructura local. Requiere .NET 10, Java 21+ y Maven. Detener primero las cuatro aplicaciones de Compose para liberar los puertos y no duplicar consumidores; conservar sus volúmenes.

    dotnet build Banking.sln -c Release -m:1
    mvn -B -ntp -f java/pom.xml verify
    docker compose stop ledger-csharp audit-csharp ledger-java audit-java
    python scripts/native_verify.py --dotnet /ruta/dotnet --java /ruta/java

El script arranca la infraestructura, aplica migraciones, inicia cuatro procesos propios y ejecuta aceptación, recuperación, carga, invariantes y restauración de backups. Guarda logs en artifacts/native y detiene únicamente sus procesos al terminar. Esta modalidad prueba binarios nativos; CI prueba los contenedores y el agente de instrumentación. Después se puede volver a docker compose up -d.

## Límites

PostgreSQL único con cuatro bases y roles separados; Kafka de un broker; Keycloak en modo de desarrollo; HTTP y credenciales locales. Un despliegue real necesita TLS, secretos independientes, IdP externo, Kafka replicado con ACL, HA de PostgreSQL, backups probados y políticas de retención revisadas. Kubernetes sirve como ejercicio verificable, no como certificación de producción.
