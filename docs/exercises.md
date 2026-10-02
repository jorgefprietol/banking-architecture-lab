# Ejercicios y defensa en entrevista

Cada caso debe ejecutarse en ambas versiones y pasar los mismos escenarios. El código contiene la solución base; estas extensiones permiten demostrar criterio propio.

| Caso | Criterios de aceptación | Extensión |
| --- | --- | --- |
| Transferencia | Conserva suma; rechaza sobregiro, autocuenta y moneda distinta; reintento no duplica; concurrencia no pierde actualizaciones | Añadir reserva/liberación de fondos antes de liquidar |
| Event sourcing / CQRS | Replay produce saldo correcto; versión incremental; rollback no deja eventos huérfanos | Reconstruir una proyección en otra tabla y comparar antes de sustituir |
| Onboarding | KYC rechazado impide apertura; aprovisionamiento fallido compensa reserva; éxito es terminal | Persistir saga y simular caída entre pasos |
| Microkernel | Plugins independientes; todos devuelven razones; decisión determinista; no permitir regla con identificador repetido | Añadir regla de velocidad con ventana temporal |
| Conciliación | Clasifica faltantes, discrepancias y duplicados sin silenciarlos; importa CSV controlado por un puerto | Añadir totales de control y cierre de archivo del proveedor |
| Inventory | Rechaza sobreventa; versión protege escritor concurrente; cancelación devuelve stock una sola vez | Añadir expiración con reloj inyectado |
| Auditoría | Outbox se recupera tras caída; duplicado no duplica efecto; offset se confirma después del commit | Simular caída entre publicación y marca de entrega |

## Preguntas de arquitectura

- ¿Qué transacciones deben ser fuertes y qué lecturas toleran consistencia eventual?
- ¿Por qué una saga no sustituye la atomicidad del ledger?
- ¿Cómo distingue el modelo un evento de dominio de un contrato de integración?
- ¿Qué información se puede borrar y qué retención necesita una revisión legal?
- ¿Qué coste tiene añadir Kafka, y cuándo bastaría un worker con una cola de base de datos?
- ¿Cómo migraría desde tres capas sin reescribir todo el sistema?
- ¿Cómo demostraría que una prueba falla al introducir una transferencia no atómica?

Los escenarios usan clientes y dinero ficticios. Ningún ejercicio reproduce material propietario del curso adjunto.
