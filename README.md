# Qlik-MCP-server

Een Model Context Protocol (MCP) server die als interface dient tussen MCP clients en Qlik Cloud. De server maakt gebruik van de qlik-cli tool om Qlik Cloud functionaliteiten toegankelijk te maken via het MCP protocol.

## Overzicht

Deze MCP server biedt een gestandaardiseerde interface voor Qlik Cloud operaties, waardoor ontwikkelaars en data analisten eenvoudig Qlik functionaliteiten kunnen integreren in hun MCP-gebaseerde workflows.

### Hoofdfunctionaliteiten

- **MCP Protocol Ondersteuning**: Volledige implementatie van het Model Context Protocol
- **Qlik CLI Integratie**: Naadloze integratie met qlik-cli voor Qlik Cloud operaties
- **App Management**: Ondersteuning voor qlik app build en unbuild operaties
- **Configureerbaar**: Flexibele configuratie via environment variables of config files

## Vereisten

### Systeem Vereisten

- Python 3.8 of hoger
- qlik-cli geïnstalleerd en geconfigureerd
- Toegang tot Qlik Cloud tenant

### Qlik CLI Setup

1. **Installeer qlik-cli**:
   ```bash
   # Via npm (aanbevolen)
   npm install -g @qlik/cli
   
   # Of download van GitHub releases
   # https://github.com/qlik-oss/qlik-cli/releases
   ```

2. **Configureer qlik-cli**:
   ```bash
   # Stel je Qlik Cloud context in
   qlik context create --server https://your-tenant.qlikcloud.com --server-type cloud
   
   # Authenticeer met API key
   qlik auth add --type api-key --api-key your-api-key
   ```

3. **Test de configuratie**:
   ```bash
   qlik app ls
   ```

## Installatie

### 1. Clone de Repository

```bash
git clone https://github.com/AliceLynxx/Qlik-MCP-server.git
cd Qlik-MCP-server
```

### 2. Installeer Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configuratie

Maak een `.env` bestand aan in de root directory (optioneel):

```env
# Qlik CLI configuratie
QLIK_CLI_PATH=qlik
QLIK_TENANT_URL=https://your-tenant.qlikcloud.com
QLIK_API_KEY=your-api-key-here
QLIK_COMMAND_TIMEOUT=300

# MCP Server configuratie
MCP_SERVER_NAME=qlik-mcp-server
MCP_SERVER_VERSION=1.0.0
LOG_LEVEL=INFO
DEBUG=false
```

## Gebruik

### Server Starten

```bash
python main.py
```

De server start en luistert naar MCP client verbindingen.

### MCP Client Configuratie

Configureer je MCP client om verbinding te maken met de Qlik-MCP-server. De exacte configuratie hangt af van je MCP client, maar over het algemeen heb je nodig:

- **Server naam**: `qlik-mcp-server`
- **Protocol**: MCP
- **Verbinding**: Lokale socket of HTTP endpoint (afhankelijk van implementatie)

### Beschikbare Tools

De server biedt de volgende MCP tools:

1. **qlik_app_build**: Bouw een Qlik app vanuit source bestanden
2. **qlik_app_unbuild**: Pak een Qlik app uit naar source bestanden

## Configuratie Opties

### Environment Variables

| Variable | Beschrijving | Default |
|----------|-------------|---------|
| `QLIK_CLI_PATH` | Pad naar qlik-cli executable | `qlik` |
| `QLIK_TENANT_URL` | Qlik Cloud tenant URL | None |
| `QLIK_API_KEY` | API key voor authenticatie | None |
| `QLIK_COMMAND_TIMEOUT` | Timeout voor commando's (seconden) | `300` |
| `MCP_SERVER_NAME` | Server naam voor MCP | `qlik-mcp-server` |
| `LOG_LEVEL` | Log niveau (DEBUG/INFO/WARNING/ERROR) | `INFO` |
| `DEBUG` | Debug modus inschakelen | `false` |

### Configuratie Validatie

De server valideert automatisch of qlik-cli correct is geconfigureerd bij het opstarten. Als er problemen zijn, worden deze gerapporteerd in de logs.

## Ontwikkeling

### Project Structuur

```
Qlik-MCP-server/
├── main.py              # Hoofdbestand met FastMCP server
├── qlik_tools.py        # Qlik CLI integratie module
├── config.py            # Configuratie en instellingen
├── requirements.txt     # Python dependencies
├── README.md           # Deze documentatie
├── project_info.txt    # Project informatie
└── project_stappen.txt # Ontwikkel roadmap
```

### Bijdragen

1. Fork de repository
2. Maak een feature branch (`git checkout -b feature/nieuwe-functie`)
3. Commit je wijzigingen (`git commit -am 'Voeg nieuwe functie toe'`)
4. Push naar de branch (`git push origin feature/nieuwe-functie`)
5. Maak een Pull Request

## Troubleshooting

### Veelvoorkomende Problemen

1. **"qlik command not found"**
   - Zorg ervoor dat qlik-cli is geïnstalleerd en in je PATH staat
   - Controleer de `QLIK_CLI_PATH` environment variable

2. **"Authentication failed"**
   - Controleer je API key en tenant URL
   - Zorg ervoor dat qlik-cli correct is geconfigureerd

3. **"Connection timeout"**
   - Verhoog de `QLIK_COMMAND_TIMEOUT` waarde
   - Controleer je netwerkverbinding

### Logs

De server gebruikt structured logging. Stel `LOG_LEVEL=DEBUG` in voor gedetailleerde informatie.

## Licentie

Dit project is gelicenseerd onder de MIT License - zie het LICENSE bestand voor details.

## Support

Voor vragen, problemen of feature requests, maak een issue aan in de GitHub repository.