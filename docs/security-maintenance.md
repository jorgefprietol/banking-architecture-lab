# Mantenimiento de dependencias

La revisión inicial de imágenes detectó CVEs en el Tomcat y Jackson administrados por Spring Boot y en OpenSSL de la imagen base .NET. El código fija temporalmente Tomcat 11.0.26 y Jackson 3.1.7; la imagen .NET instala las correcciones disponibles de Ubuntu. El escaneo no excluye hallazgos ni usa ignore-unfixed.

Fuentes: [avisos oficiales de Tomcat 11](https://tomcat.apache.org/security-11.html), [versiones oficiales de Jackson](https://github.com/FasterXML/jackson/wiki/Jackson-Releases) y [avisos de Ubuntu](https://ubuntu.com/security/notices). Revisar los overrides al actualizar Spring Boot: retirarlos cuando su BOM incluya versiones corregidas y las suites y el escaneo pasen.

El resultado de Trivy depende de la base de vulnerabilidades y de la fecha. Un resultado sin HIGH/CRITICAL es evidencia del escaneo ejecutado, no una garantía de ausencia de defectos. Los informes completos se guardan en artifacts/security; las credenciales y dumps permanecen fuera del repositorio.
