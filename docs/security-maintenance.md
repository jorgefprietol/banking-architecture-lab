# Mantenimiento de dependencias

La revisión inicial de imágenes detectó CVEs en el Tomcat y Jackson administrados por Spring Boot y en OpenSSL de la imagen base .NET. El código fija temporalmente Tomcat 11.0.26 y Jackson 3.1.7; la imagen .NET instala las correcciones disponibles de Ubuntu. El escaneo no excluye hallazgos ni usa ignore-unfixed.

Fuentes: [avisos oficiales de Tomcat 11](https://tomcat.apache.org/security-11.html), [versiones oficiales de Jackson](https://github.com/FasterXML/jackson/wiki/Jackson-Releases) y [avisos de Ubuntu](https://ubuntu.com/security/notices). Revisar los overrides al actualizar Spring Boot: retirarlos cuando su BOM incluya versiones corregidas y las suites y el escaneo pasen.

El resultado de Trivy depende de la base de vulnerabilidades y de la fecha. Un resultado sin HIGH/CRITICAL es evidencia del escaneo ejecutado, no una garantía de ausencia de defectos. Los informes completos se guardan en artifacts/security; las credenciales y dumps permanecen fuera del repositorio.

Las propuestas de actualización también requieren comprobar la línea del JDK. La actualización de Maven sugirió JDK 24; se conservó Maven 3 con JDK 25 para compilación y runtime. check_architecture.py comprueba esta política antes de la integración. [Adoptium](https://adoptium.net/support/) mantiene Java 25 como LTS y marca Java 24 como una línea que terminó soporte. Una migración futura a otra línea exige actualizar la política y repetir las pruebas.
