# Contribuir

Implementar cada capacidad en C# y Java con el contrato común como referencia. El dominio permanece libre de frameworks; las decisiones sobre persistencia y comunicación se documentan junto a sus consecuencias.

1. Usar ramas cortas desde main y cambios pequeños con un propósito concreto.
2. Mantener reglas monetarias, autorización por propietario e idempotencia.
3. Añadir una prueba cuando se introduce una regla o se corrige un fallo observable.
4. Ejecutar las suites unitarias, la aceptación común y las comprobaciones de arquitectura.
5. Si cambia infraestructura o una dependencia, repetir las comprobaciones afectadas y el escaneo de seguridad.
6. Mantener migraciones existentes inmutables después de publicar; agregar un archivo numerado nuevo.
7. Explicar problema, comportamiento resultante y validación en cada PR.

Los commits describen cambios realmente realizados. Usar feat, fix, test, docs o ci según su contenido. No agrupar arreglos independientes, incorporar credenciales, modificar retrospectivamente evidencias ni declarar validaciones que no se ejecutaron.
