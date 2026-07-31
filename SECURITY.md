# Seguridad y alcance clínico

Este MVP no debe usarse en atención clínica sin una evaluación formal de riesgo, privacidad, respaldo, interoperabilidad y cumplimiento local. Antes de producción: TLS real en el proxy, secretos externos, cifrado de volúmenes y respaldos, antivirus de cargas, MFA, política RBAC/ABAC, retención, consentimiento, pruebas de restauración y revisión de Ley 19.628/Ley 21.719, normativa sanitaria chilena y contratos con encargados de tratamiento.

`SECURE_COOKIE=false` se conserva porque fue solicitado, pero es inseguro con autenticación real. En producción debe ser `true` bajo HTTPS. Los archivos deben validarse por firma binaria, tamaño y contenido; nunca solo por extensión.
