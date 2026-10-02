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
- Contrato desconocido: audit falla y no confirma el offset. Identificar la versión, desplegar un consumidor compatible y reiniciar; no saltar offsets automáticamente.
- Proyección corrupta: reconstruir desde eventos a una tabla nueva, comparar saldos y versiones y cambiar la lectura después de validar. Conservar una copia verificable.

    docker compose ps
    docker compose logs --tail 80 ledger-csharp ledger-java audit-csharp audit-java
    docker compose stop
    docker compose start

Los volúmenes se conservan al detener el laboratorio. La migración v1 solo se aplica al inicializar un volumen nuevo; modificaciones posteriores requieren migraciones nuevas. No ejecutar limpiezas globales de Docker ni borrar volúmenes de otros proyectos.

Kafka usa explícitamente el directorio persistente /tmp/kraft-combined-logs. La comprobación de persistencia recrea únicamente este broker y verifica que los IDs de sus temas y los offsets de las seis particiones sobreviven. La prueba de backup restaura cada base en una base temporal nueva y elimina únicamente los recursos que ella misma creó.

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

Publish verified images se ejecuta manualmente desde GitHub Actions y exige repetir CI antes de publicar en GHCR. Etiqueta por SHA de commit, SBOM y attestation verificable; no requiere guardar tokens de larga duración. Desplegar cloud requiere seleccionar una plataforma y su configuración de identidad y secretos.

## Límites

PostgreSQL único con cuatro bases y roles separados; Kafka de un broker; Keycloak en modo de desarrollo; HTTP y credenciales locales. Un despliegue real necesita TLS, secretos independientes, IdP externo, Kafka replicado con ACL, HA de PostgreSQL, backups probados y políticas de retención revisadas. Kubernetes sirve como ejercicio verificable, no como certificación de producción.
