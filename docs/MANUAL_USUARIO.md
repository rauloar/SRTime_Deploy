# Manual de Usuario Final: Ingesta de Asistencia SRTime

Este manual describe el funcionamiento diario para importar las marcas de asistencia de los empleados.

---

## 1. Importación Desde Archivo (.TXT)
Utilice este método si descarga las marcas de asistencia desde un puerto USB de la terminal o si dispone de un archivo plano provisto externamente.

### Paso a Paso:
1. Abra la aplicación de **SRTime** y diríjase a la pestaña **Importar**.
2. Asegúrese de estar posicionado en la pestaña **Desde Archivo**.
3. Haga clic en **Buscar Archivo** y seleccione el archivo `.txt` con los fichajes.
4. Elija el formato en el selector de formatos si no corresponde al estándar predeterminado de SRTime.
5. Haga clic en **Importar TXT**.
6. En la caja inferior de logs verá el progreso detallado en tiempo real. Al finalizar la carga, el sistema informará la cantidad de registros nuevos procesados y los duplicados omitidos.

El archivo original no se renombra, vacía ni elimina. Puede volver a importarlo: la base de
datos detectará y omitirá las marcas ya existentes.

---

## 2. Descarga Directa Desde Red (Equipos Biométricos)
Utilice este método si las terminales de fichada de la empresa se encuentran conectadas a la red LAN de la empresa o mediante un túnel VPN.

### Paso a Paso:
1. En la pestaña **Importar**, seleccione la sub-pestaña **Desde Red Física** (en la interfaz web) o **Desde Terminal** (en la interfaz de Windows).
2. En el menú desplegable, elija el equipo al cual desea conectarse (ej: *Recepción*).
3. **Prueba de Conectividad (Recomendado)**:
   - Haga clic en **Probar Conexión**.
   - El sistema intentará dialogar con el reloj. Si la comunicación es exitosa, se desplegará una ventana informativa que muestra el *Modelo, Dirección MAC, Número de serie, versión de Firmware y la hora local del dispositivo*.
4. **Descargar Asistencias**:
   - Haga clic en **Descargar Memorias**.
   - El sistema descargará todos los fichajes almacenados en la memoria del hardware de forma autónoma. Comparará contra la base de datos para no duplicar marcas previas e ingresará automáticamente las nuevas filas junto con cualquier empleado nuevo detectado.
5. **Sincronizar Reloj Interno (Opcional)**:
   - Si advierte que el reloj físico de la oficina tiene un desfasaje, haga clic en el botón **Sincronizar Hora**. Esto colocará el hardware en la hora exacta sincronizada del servidor.

---

## 3. Guía de Errores Comunes

* **Error: "No se pudo conectar al dispositivo"**
  - El reloj puede estar apagado, desconectado de la corriente, o no tener acceso a la red local. Póngase en contacto con el administrador de sistemas para verificar la conexión IP.
* **Todos los registros aparecen como "Duplicados"**
  - Esto es correcto y normal. Significa que los datos que está intentando descargar ya fueron ingresados al sistema con anterioridad, evitando duplicidad de información.
* **El archivo cargado es inválido**
  - Verifique que la extensión del archivo sea estrictamente `.txt` y que el formato coincida con el parser que seleccionó.
