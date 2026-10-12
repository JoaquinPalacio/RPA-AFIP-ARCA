# RPA Bot: Automatización de Extracción y Carga de Datos Fiscales (AFIP)

Este repositorio es una demostración (showcase) de un bot de Automatización Robótica de Procesos (RPA) desarrollado en Python. El sistema automatiza la extracción de comprobantes fiscales desde el portal gubernamental AFIP/ARCA, su posterior transformación y la carga masiva en bases de datos relacionales.

*Nota: Por motivos de confidencialidad y seguridad de datos, este repositorio contiene una versión sanitizada del código. Las credenciales, endpoints internos y datos sensibles de las empresas han sido removidos u ofuscados.*

## El Problema que Resuelve

Anteriormente, la descarga de comprobantes para múltiples entidades (CUITs) requería que un operario ingresara manualmente al portal, navegara por diferentes menús, aplicara filtros de fechas, seleccionara columnas específicas, descargara archivos Excel, los convirtiera y finalmente los cargara a mano en el sistema de gestión. 

Este bot reduce un proceso tedioso y propenso a errores humanos de varias horas a **unos pocos minutos de ejecución autónoma**, garantizando la disponibilidad diaria de los datos operativos.

## Stack Tecnológico

- **Lenguaje:** Python 3.x
- **RPA & Web Scraping:** Selenium WebDriver (Edge en modo headless)
- **Procesamiento de Datos:** Pandas
- **Base de Datos:** MariaDB / MySQL (mediante conector nativo `mariadb`)
- **Arquitectura:** Patrón ETL (Extract, Transform, Load)

## Arquitectura y Flujo de Trabajo (Pipeline ETL)

El script sigue un flujo de trabajo estructurado en 4 fases principales:

### 1. Autenticación Segura
- Instanciación de un navegador en modo silencioso (`headless`).
- Navegación al portal de autenticación e inyección segura de credenciales.
- Manejo de ventanas emergentes y redirecciones del portal.

### 2. Extracción de Datos (Extract)
- Iteración dinámica sobre un diccionario de categorías y CUITs empresariales.
- Interacción con el DOM dinámico (esperas explícitas con `WebDriverWait`) para seleccionar fechas ("Últimos 15 días") y habilitar columnas específicas de reportes.
- Descarga automatizada de archivos `.xlsx` a un directorio temporal.

### 3. Transformación (Transform)
- Monitoreo del sistema de archivos para detectar la finalización de la descarga.
- Lectura en memoria usando **Pandas** (`pd.read_excel`).
- Limpieza básica y conversión del archivo a un formato `.csv` estandarizado, renombrándolo dinámicamente según el CUIT y la fecha de ejecución para mantener un registro histórico ordenado.

### 4. Carga Masiva (Load)
- Conexión a la base de datos MariaDB correspondiente a cada entidad.
- Registro de la operación en una tabla de auditoría (`log_mis_comprobantes`) para trazabilidad.
- Inserción ultra-rápida de miles de registros utilizando `LOAD DATA LOCAL INFILE`, mapeando variables y formateando fechas sobre la marcha mediante SQL nativo.
- Manejo transaccional (Commit/Rollback) para asegurar la integridad de los datos.

## Destacados del Código

El diseño del software se enfoca en la robustez y mantenibilidad:
- **Configuración Centralizada:** Uso de un diccionario `CONFIG` global para gestionar rutas, mapeos de CUITs y configuraciones de bases de datos de forma limpia.
- **Manejo de Excepciones:** Bloques `try/except/finally` estructurados para garantizar que las conexiones a la base de datos y los procesos del navegador se cierren correctamente incluso si ocurre un error inesperado (evitando procesos "zombie" en el servidor).
- **Esperas Inteligentes:** Reemplazo de los estáticos `time.sleep()` por `WebDriverWait` y `expected_conditions` (EC) de Selenium, haciendo que el bot sea resistente a la latencia de la red o tiempos de carga lentos del servidor gubernamental.
