# Seguridad

Se mantiene la rama main. CI falla ante hallazgos altos o críticos del escaneo de imágenes; la restauración de NuGet trata sus avisos de vulnerabilidad como errores. Dependabot propone actualizaciones semanales.

Reportar problemas por el mecanismo de reporte privado de vulnerabilidades del repositorio. Incluir reproducción con datos sintéticos y la versión afectada; no adjuntar tokens, credenciales ni datos de clientes.

El perfil local publica servicios en loopback, utiliza contraseñas aleatorias y almacena configuración sensible en archivos ignorados. Las API validan firma, issuer, audience, rol y propiedad de recursos; los roles SQL de ejecución no pueden modificar ni borrar eventos.

El modo de desarrollo del IdP y los listeners sin TLS son decisiones de laboratorio. Consulte [el runbook](docs/runbook.md) para los requisitos de despliegue real y el procedimiento ante contratos de eventos incompatibles.
