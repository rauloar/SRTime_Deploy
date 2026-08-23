# Acceso de SRTime Web desde la LAN (Windows)

Este procedimiento permite que equipos de la misma red local accedan a la
instalación Web de SRTime sin exponer PostgreSQL ni el puerto web a Internet.

## Alcance de red

El navegador de cada cliente se conecta solamente a FastAPI por el puerto
configurado en `API_PORT` (por defecto, `8000`):

```text
Cliente LAN ── HTTP ──> SRTime Web (API_HOST:API_PORT) ──> PostgreSQL
```

Los clientes no deben conectarse directamente a PostgreSQL. Por ello, no se
abre el puerto `5432` para dar acceso a la interfaz web.

## 1. Configurar SRTime

En el archivo local `config\\.env` de la instalación, configurar el servicio
para escuchar en la red. El archivo real es local y no se versiona:

```dotenv
API_HOST=0.0.0.0
API_PORT=8000
SRTIME_SETUP_ALLOWED_IPS=127.0.0.1,::1,private
```

`SRTIME_SETUP_ALLOWED_IPS` regula únicamente el asistente inicial. Después de
terminar la instalación puede reemplazarse `private` por una subred CIDR
concreta, si se requiere una política más estricta.

Reiniciar el único proceso o servicio SRTime después de cambiar el entorno.

## 2. Abrir el firewall solo para la subred corporativa

Abrir PowerShell **como administrador**. Antes de ejecutar el comando, definir
la subred real de la LAN; no copiar una dirección de ejemplo como configuración
permanente.

```powershell
$SRTimeLanSubnet = "<SUBRED_CIDR>" # Ejemplo de formato: 192.168.10.0/24
$SRTimePort = 8000

New-NetFirewallRule `
  -DisplayName "SRTime Web LAN" `
  -Direction Inbound `
  -Action Allow `
  -Protocol TCP `
  -LocalPort $SRTimePort `
  -RemoteAddress $SRTimeLanSubnet `
  -Profile Private,Public
```

Si la regla ya existe, actualizar exclusivamente su filtro de origen:

```powershell
$SRTimeLanSubnet = "<SUBRED_CIDR>"
Get-NetFirewallRule -DisplayName "SRTime Web LAN" |
  Get-NetFirewallAddressFilter |
  Set-NetFirewallAddressFilter -RemoteAddress $SRTimeLanSubnet
```

Verificar el alcance efectivo:

```powershell
Get-NetFirewallRule -DisplayName "SRTime Web LAN" |
  Get-NetFirewallAddressFilter
```

El resultado debe indicar `RemoteAddress` con la subred elegida. La regla debe
seguir siendo de entrada, TCP, puerto 8000 y no debe usar `Any` como origen.

## 3. Identificar la dirección del servidor

En el servidor Windows, ejecutar:

```powershell
ipconfig
```

Usar la IPv4 del adaptador conectado a la LAN, no una IP histórica, de Wi-Fi,
VPN, Docker, VirtualBox o WSL. Desde una PC de la misma subred abrir:

```text
http://<IP_DEL_SERVIDOR>:8000
```

Una IP reservada en DHCP o estática fuera del rango de dispositivos DHCP evita
que la dirección del servidor cambie o colisione con equipos IoT.

## 4. Validación y diagnóstico

En el servidor:

```powershell
netstat -ano -p tcp | Select-String ':8000'
Invoke-WebRequest "http://<IP_DEL_SERVIDOR>:8000/api/health" -UseBasicParsing
```

El listener esperado es `0.0.0.0:8000` y la solicitud debe devolver HTTP 200.
En un cliente LAN, probar la misma URL desde el navegador o:

```bash
curl -I http://<IP_DEL_SERVIDOR>:8000/
```

Si localmente funciona pero un cliente queda esperando, revisar en este orden:

1. Que el cliente y servidor estén en la subred autorizada.
2. Que la regla use el perfil de red activo (`Private` o `Public`).
3. Que `RemoteAddress` sea la subred CIDR real y no una IP anterior.
4. Que no exista otra regla de bloqueo o suite de seguridad administrando el
   firewall.
5. Que el proceso SRTime sea el único dueño del puerto 8000.

## Seguridad

- No abrir PostgreSQL (`5432`) a las estaciones cliente para usar SRTime Web.
- Usar HTTPS mediante un proxy inverso o certificado antes de exponer el
  sistema fuera de la LAN.
- Mantener la regla limitada a la subred corporativa y revisar la reserva DHCP
  o IP estática durante cada cambio de red.
