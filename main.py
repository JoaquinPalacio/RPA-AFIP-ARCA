from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.edge.options import Options
import os
import time
import datetime
import pandas as pd
import mariadb

CONFIG = {
    "AFIP_CREDENTIALS": {"username": "", "password": ""},
    "DOWNLOAD_FOLDER": r"",
    "DATABASES": {
        "": "",
        "": "",
        "": "",
    },
    "DB_CONFIG": {
        "host": "",
        "user": "",
        "password": "",
        "port": 3307,
        "local_infile": 1,
    },
    "CATEGORIAS": [
        "",
        "",
        "",
    ],
    "CUIT_MAPPING": {
        "": "",
        "": "",
        "": "",
    },
    "COLUMNAS": [
        "Cód. Autorización",
        "CUIT Emisor",
        "Imp. Neto No Gravado",
        "Imp. Neto Gravado",
        "Imp. Op. Exentas",
        "Otros Tributos",
        "IVA",
    ],
    "WAIT_TIMEOUT": 30,
}


def setup_driver(download_folder):
    """Configura y retorna la instancia del driver de Edge"""
    edge_options = Options()
    edge_options.add_argument("--headless")
    edge_options.add_experimental_option(
        "prefs",
        {
            "download.default_directory": download_folder,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
        },
    )
    return webdriver.Edge(options=edge_options)


def wait_and_click(driver, locator, timeout=30):
    """Espera y hace clic en un elemento"""
    element = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable(locator))
    driver.execute_script("arguments[0].click();", element)


def login(driver, credentials):
    """Maneja el proceso de autenticación"""
    driver.get("https://auth.afip.gob.ar/contribuyente_/login.xhtml")

    # Ingreso de usuario
    wait_and_click(driver, (By.ID, "F1:username"))
    driver.find_element(By.ID, "F1:username").send_keys(credentials["username"])
    driver.find_element(By.ID, "F1:btnSiguiente").click()

    # Ingreso de contraseña
    wait_and_click(driver, (By.ID, "F1:password"))
    driver.find_element(By.ID, "F1:password").send_keys(credentials["password"])
    driver.find_element(By.ID, "F1:btnIngresar").click()


def switch_to_new_window(driver, original_window):
    """Cambia a la nueva ventana/pestaña"""
    WebDriverWait(driver, CONFIG["WAIT_TIMEOUT"]).until(
        EC.new_window_is_opened(driver.window_handles)
    )
    for window in driver.window_handles:
        if window != original_window:
            driver.switch_to.window(window)
            break


def process_category(driver, category, cuit_empresa):
    """Procesa una categoría y descarga su archivo"""
    try:
        # Navegación a categoría
        wait_and_click(driver, (By.XPATH, f"//a[contains(., '{category}')]"))

        # Configuración de filtros
        wait_and_click(driver, (By.ID, "btnRecibidos"))
        wait_and_click(driver, (By.ID, "btnCalendarioFechaEmision"))
        wait_and_click(driver, (By.XPATH, "//li[@data-range-key='Últimos 15 Días']"))
        wait_and_click(driver, (By.ID, "buscarComprobantes"))

        # Selección de columnas
        wait_and_click(
            driver, (By.XPATH, "//button[@title='Mostrar/ocultar columnas']")
        )
        for columna in CONFIG["COLUMNAS"]:
            wait_and_click(driver, (By.XPATH, f"//a[text()='{columna}']"))

        # Descarga de archivo
        wait_and_click(driver, (By.XPATH, "//button[.//span[text()='Excel']]"))
        return handle_file(cuit_empresa)

    except Exception as e:
        print(f"Error procesando {category}: {str(e)}")
        raise


def handle_file(cuit_empresa):
    """Maneja la descarga y conversión del archivo"""
    start_time = time.time()
    file_path = None
    download_folder = CONFIG["DOWNLOAD_FOLDER"]

    # Espera por la descarga
    while time.time() - start_time < 120:
        for file in os.listdir(download_folder):
            if file.lower().endswith((".xlsx", ".xls")) and cuit_empresa in file:
                file_path = os.path.join(download_folder, file)
                break
        if file_path:
            break
        time.sleep(1)

    if not file_path:
        raise FileNotFoundError("Archivo no encontrado")

    # Conversión y movimiento
    df = pd.read_excel(file_path)
    csv_path = os.path.join(
        download_folder,
        cuit_empresa,
        f"{cuit_empresa}_{datetime.date.today().strftime('%Y%m%d')}.csv",
    )
    df.to_csv(csv_path, index=False, sep=",")
    os.remove(file_path)

    return csv_path


def load_to_database(csv_path, cuit):
    """Carga los datos a la base de datos correspondiente"""
    db_name = CONFIG["DATABASES"].get(cuit)
    if not db_name:
        print(f"Base de datos no encontrada para CUIT {cuit}")
        return

    try:
        clean_csv_path = csv_path.replace("\\", "/")

        conn = mariadb.connect(**CONFIG["DB_CONFIG"], database=db_name)
        cursor = conn.cursor()

        cursor.execute("SELECT MAX(nro_recep) FROM log_mis_comprobantes")
        last_nro_recep = cursor.fetchone()[0]
        nro_recep = 1 if last_nro_recep is None else last_nro_recep + 1
        log_query = """
            INSERT INTO log_mis_comprobantes (archivo, fecha, nro_recep, obs)
            VALUES (?, NOW(), ?, NULL)
        """
        cursor.execute(log_query, (clean_csv_path, nro_recep))

        query = f"""
            LOAD DATA LOCAL INFILE '{clean_csv_path}'
            INTO TABLE mis_comprobantes
            FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
            LINES TERMINATED BY '\\r\\n'
            IGNORE 2 ROWS
            (@fecha, tipo, @pto_vta, @numero_desde, numero_hasta, @cad, tipo_doc, @nro_doc, 
            denominacion, tipo_cambio, moneda, imp_neto_nogravado, imp_neto_gravado, 
            imp_op_exentas, otros_tributos, iva, @imp_total, @nro_recep)
            SET
                fecha = STR_TO_DATE(@fecha, '%d/%m/%Y'),
                pto_vta = TRIM(@pto_vta),
                numero_desde = TRIM(@numero_desde),
                cad = TRIM(@cad),
                nro_doc = TRIM(@nro_doc),
                imp_total = @imp_total,
                nro_recep = {nro_recep}
        """
        cursor.execute(query)
        conn.commit()
        print(f"Datos cargados en {db_name} exitosamente! Log ID: {nro_recep}")

    except mariadb.Error as e:
        print(f"Error de base de datos: {str(e)}")
        if "conn" in locals():
            conn.rollback()
    except Exception as e:
        print(f"Error general: {str(e)}")
        if "conn" in locals():
            conn.rollback()
    finally:
        if "conn" in locals():
            conn.close()


def main():
    """Flujo principal de ejecución"""
    driver = setup_driver(CONFIG["DOWNLOAD_FOLDER"])
    original_window = driver.current_window_handle

    try:
        login(driver, CONFIG["AFIP_CREDENTIALS"])
        wait_and_click(
            driver, (By.XPATH, "//a[.//h3[contains(text(), 'Mis Comprobantes')]]")
        )
        switch_to_new_window(driver, original_window)

        for categoria in CONFIG["CATEGORIAS"]:
            cuit = CONFIG["CUIT_MAPPING"].get(categoria)
            if not cuit:
                print(f"CUIT no encontrado para {categoria}")
                continue

            try:
                csv_path = process_category(driver, categoria, cuit)
                load_to_database(csv_path, cuit)
            except Exception as e:
                print(f"Error en categoría {categoria}: {str(e)}")

            driver.get("https://fes.afip.gob.ar/mcmp/jsp/index.do")

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
