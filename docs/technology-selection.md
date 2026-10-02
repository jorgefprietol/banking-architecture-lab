# Selección tecnológica

Revisión: 2026-10-02. Mercado objetivo: Latinoamérica y puestos remotos internacionales.

La muestra de ofertas describe señales de contratación; no mide cuota de mercado ni salarios. No existe un stack universalmente superior para todos los bancos.

| Fuente primaria | Señal observada | Decisión |
| --- | --- | --- |
| [Citi, Java Microservices Developer, 26990555, 18 septiembre 2026](https://jobs.citi.com/job/jersey-city/java-microservices-developer-vice-president/287/100801454416) | Spring Boot, Kafka, concurrencia y servicios cloud | API Java, outbox y consumidor independiente |
| [Citi, .NET Full Stack, 26995360, 30 septiembre 2026](https://jobs.citi.com/job/chennai/net-full-stack-developer-assistant-vice-president/287/101350212608) | C#, .NET, Java, bases relacionales y CI/CD | Dos implementaciones, SQL explícito y pipeline reproducible |
| [Citi, Java Developer, 26995779, 29 septiembre 2026](https://jobs.citi.com/job/pune/java-developer/287/101320614928) | Spring, Kafka, SQL, contenedores, observabilidad, pruebas | Pruebas de concurrencia, Docker, Kubernetes y telemetría |
| [CodeRoad, Senior .NET Engineer, LATAM remoto](https://job-boards.greenhouse.io/coderoad/jobs/4377865009) | C#, APIs, microservicios; Docker, AKS y CI/CD como complementos | Núcleo C# probado, API y entrega automatizada |
| [Endava, Senior Backend Engineer](https://jobs.smartrecruiters.com/Endava/744000131964923-senior-backend-engineer-java-kafka-cloud-) | Java, Spring Boot, Kafka, Docker, pruebas y equipos internacionales | Contratos compartidos y ejecución de escenarios transaccionales |

Las ofertas internacionales incluyen roles presenciales o híbridos; no se presentan como oportunidades remotas abiertas desde Ecuador. La selección prioriza capacidades transferibles. Azure/AWS, Oracle/SQL Server y Jenkins/Tekton son frecuentes en entornos bancarios; no se instalan sistemas redundantes solo para acumular nombres.

## Versiones y soporte

- [.NET support policy](https://dotnet.microsoft.com/en-us/platform/support/policy): .NET 10 es LTS. Se evita iniciar con .NET 8/9, cuyo soporte termina en noviembre de 2026.
- [Spring Boot requirements](https://docs.spring.io/spring-boot/system-requirements.html): línea estable 4.1; JDK 21 compatible. Java 21 permite demostrar virtual threads sin requerir preview features.
- [Adoptium support](https://adoptium.net/support/): usar un JDK LTS actualizado. El JDK instalado se registra en el informe local.
- [Event sourcing](https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing): útil cuando se necesita reconstrucción y auditoría; aumenta la complejidad de versiones y proyecciones.
- [Outbox](https://microservices.io/patterns/data/transactional-outbox.html): publicación al menos una vez; consumidores idempotentes. No se promete exactamente una vez extremo a extremo.

Dependencias con versiones explícitas, actualizaciones por Dependabot y pruebas antes de adoptar cambios. Las imágenes deben fijarse por digest para una promoción real; los tags del laboratorio facilitan reproducir ejercicios y se registran al verificar.
