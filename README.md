# Sistema de Gestión Documental para la ORMD Arequipa

## 💡Resumen 

El archivo de la Oficina de Registro Militar Departamental (ORMD) de Arequipa tiene gran cantidad de documentos históricos (libros, folios, hojas de registro y constancias). La gestión actual es principalmente manual, lo que resulta en tiempos de respuesta prolongados e imprecisión al atender las consultas ciudadanas o solicitudes de entidades como la RENIEC.

## ❗Problema

La dificultad para realizar búsquedas rápidas y precisas en el archivo físico limita la eficiencia operativa y la calidad del servicio al ciudadano. La ausencia de un sistema centralizado impide la trazabilidad de la información y la generación de reportes formales ágiles.

## ✔️Objetivos del Proyecto
## ⚫Objetivo General
Digitalizar e indexar el archivo histórico de la ORMD Arequipa para responder a las consultas ciudadanas con rapidez y precisión, mejorando la eficiencia y la calidad del servicio.
## ⚫Objetivos Específicos
- Implementar un motor OCR local para la extracción automática de campos clave, complementado con una edición manual validada.
- Desarrollar una interfaz que permita búsquedas multi-criterio y la generación de reportes oficiales.
- Establecer un sistema robusto con roles de usuario, auditoría completa y mecanismos de backup.
- Entregar una solución autónoma y offline mediante un instalador ejecutable para Windows.

## 🔵Propuesta de Solución: Sistema Local ORMD
Se propone la implementación de una aplicación de escritorio local para Windows, ligera y autónoma, que combina tecnologías de Reconocimiento Óptico de Caracteres (OCR) con una base de datos relacional para la indexación y consulta.
### Beneficios Clave
| Beneficio |  Descripción                |
| :-------- |:------------------------- |
| Búsqueda Rápida | Consultas por DNI, Libreta Militar, Clase, Libro, Folio, Nombres/Apellidos y Fecha de Nacimiento. |
| Reportes Formales | Generación inmediata de reportes en PDF para el ciudadano o la RENIEC, con sello/firma parametrizable del Comandante. |
| Auditoría Completa | Trazabilidad total de cada cambio (quién, cuándo, qué modificó). |
| Operación Autónoma | Instalación offline con ejecutable Windows y BD SQLite, sin dependencia de la red o Internet. |
| Carga Masiva Ágil | Uso de OCR local para acelerar la digitalización y carga de lotes de documentos. |

## 🔳Tecnologías y Arquitectura
### Stack
| Componente | Tecnología     | Propósito               |
| :-------- | :------- | :------------------------- |
| Lenguaje | `Python 3.11` | Core del sistema y lógica de negocio. |
| Interfaz Gráfica (GUI) | `PySide6 (Qt)` | Desarrollo de la aplicación de escritorio nativa y multiplataforma. |
| Base de Datos | `SQLite` | BD ligera y autónoma, ideal para despliegues locales (offline) |
| OCR | `Tesseract OCR, Poppler (pdf2image), OpenCV` | Módulo local para la conversión de PDF a imagen, pre-procesamiento y extracción de texto. |
| Empaquetado | `PyInstaller` | Creación del ejecutable único (EXE) para la instalación offline. |

## 🔳Arquitectura Lógica (Local / Offline)
La aplicación es monolítica y está diseñada para operar sin conexión a la red.

- La GUI Qt interactúa con el módulo de negocio.
- El Módulo OCR procesa los archivos PDF/IMG.
- Los datos extraídos son almacenados en la base de datos SQLite.
- La BD SQLite indexa los datos clave de los documentos, los cuales se almacenan en un Repositorio de Archivos local.
- Se incluyen mecanismos para Backups programados.
## 🔳Requisitos y Funcionalidades Importantes
Alcance del Proyecto (Incluye)
- Carga de documentos (PDF/imagen) con extracción OCR.
- Gestión Manual (CRUD) de ciudadanos y documentos con auditoría.
- Buscador Multi-Criterio robusto (DNI, Libreta, Clase, Libro, Folio, Nombres/Apellidos, F. Nac.).
- Gestión de Usuarios/Roles y utilidades de Backups/Exportación (CSV/Excel).
Módulos del Sistema

| Módulo |  Funcionalidades             |
| :-------- |:------------------------- |
| OCR y Carga Masiva | Procesamiento de formatos Registro Militar y Constancia de Unidad mediante el Pipeline PDF → Imagen → Preprocesado → Tesseract → Heurísticas. |
|Catálogo | Edición y Consulta (CRUD) de Ciudadanos y Documentos con registro de auditoría. |
| Buscador | Interfaz principal para la búsqueda rápida con múltiples filtros. |
| Reportes | Generación de documentos oficiales en PDF con datos parametrizados y firma. |
| Administración | Usuarios/Roles (ADMIN, OPERADOR, CONSULTA) y Backups/Exportaciones. |

## 🔳Modelo de Datos
El modelo de datos se enfoca en centralizar la información de la persona (ciudadanos) y vincularla a los documentos originales (documentos).

![App Screenshot](https://github.com/YonyVilca/ORMD-Arequipa/blob/main/ORMD_DOC/Modelo%20de%20datos.png)

## 🔳PIPELINE Extracción de Datos de PDF basado en OCR
### Fase de OCR y Preprocesamiento
Esta fase se encarga de convertir el PDF en texto legible por máquina.
Ingesta y Preprocesamiento de Imágenes: Carga el PDF y convierte cada página en una imagen.
- Mejora de Imagen: Aplica corrección de sesgo (deskew) para enderezar el texto y, en modo calidad, mejora el contraste (CLAHE) y selecciona la mejor binarización (blanco y negro), incluso aplicando un filtro para eliminar líneas de formularios.
- Generación de Texto: Ejecuta Tesseract OCR sobre la imagen optimizada y guarda el resultado en un archivo de texto plano

### Fase de Análisis y Estructuración
Esta fase procesa el texto plano para identificar y extraer la información clave.
- Normalización de Texto: Limpia el texto de errores comunes de OCR y normaliza espacios.
- Extracción de Campos: Utiliza expresiones regulares (regex) robustas para buscar y aislar valores específicos (Nombres, DNI, Fechas, Unidades, etc.).
- Normalización de Datos: Convierte los meses a formato numérico, corrige errores de lectura en el DNI (ej., 'O' por '0') y estandariza las fechas a AAAA-MM-DD.
- Salida Estructurada: Genera la información extraída en un formato de datos estructurado.

![App Screenshot](https://github.com/YonyVilca/ORMD-Arequipa/blob/main/ORMD_DOC/PIPELINE.png)

## 🔳Autores
- [@YonyVilca](https://github.com/YonyVilca)
- [@JosePeraltilla](https://www.github.com/)

## 🔳Historial de Versiones
| Versión | Fecha    | Cambios Principales              |
| :-------- | :------- | :------------------------- |
| v0.1.0 | `03-10-2025` | inicio del proyecto |
| v0.2.0 | `10-10-2025` | Primer entregable |

## 🔳Probar Codigo
- git clone https://github.com/YonyVilca/ORMD-Arequipa.git
- pip install -r requirements.txt
- configurar .env credenciales postgresql
