# Keba Rest-API Integration for Home Assistant

Home Assistant Custom Integration zur Anbindung einer Keba Wallbox ueber die
offizielle REST-API.

## Why?

Diese Integration ermoeglicht es, eine Keba Wallbox direkt in Home Assistant
einzubinden, Statusdaten auszulesen und Steuerfunktionen wie Start/Stop von
Ladevorgaengen zu nutzen.

## What?

### API-Endpunkte der Wallbox

- Basis-URL der Wallbox-API: `https://[URL or IP address of wallbox]:8443`
- API-Dokumentation der Wallbox: `https://[URL or IP address of wallbox]:8443/docs`

### Funktionsumfang der Integration

- Authentifizierung per Username/Passwort mit JWT Login und Token-Refresh.
- Abruf aller Wallboxen sowie detaillierter Wallbox-Daten.
- Steuerung von Ladevorgaengen (Start/Stop), sofern von der Wallbox erlaubt.
- Home-Assistant-konformer Config Flow mit Reauth-Unterstuetzung.

### Projektstruktur (Auszug)

Datei/Ordner | Zweck
-- | --
`custom_components/integration_keba_rest_api/` | Kern der Integration (API-Client, Entities, Coordinator, Services, Config Flow)
`custom_components/integration_keba_rest_api/services.yaml` | Service-Beschreibungen fuer Home Assistant
`custom_components/integration_keba_rest_api/translations/` | Uebersetzungen (u. a. Deutsch/Englisch)
`config/` | Lokale Testkonfiguration fuer Entwicklung
`scripts/` | Hilfsskripte fuer Setup, Entwicklung und Linting

## How?

### Installation (HACS)

1. HACS in Home Assistant oeffnen.
1. Custom Repository hinzufuegen: `https://github.com/k1h0/homeassistant-keba-rest-api`
1. Kategorie `Integration` auswaehlen und Installation starten.
1. Home Assistant neu starten.

### Installation (manuell)

1. Dieses Repository herunterladen oder klonen.
1. Ordner `custom_components/integration_keba_rest_api` nach
	`<config>/custom_components/integration_keba_rest_api` kopieren.
1. Home Assistant neu starten.

### Einrichtung in Home Assistant

1. `Einstellungen -> Geraete & Dienste -> Integration hinzufuegen`.
1. `Keba Rest-API Integration` auswaehlen.
1. Folgende Felder ausfuellen:
	- URL: `https://[URL or IP address of wallbox]:8443`
	- Benutzername
	- Passwort
1. Einrichtung abschliessen.

Hinweis:
Falls ein selbstsigniertes Zertifikat genutzt wird, versucht der Client bei
Zertifikatsfehlern einmalig einen Fallback ohne SSL-Verifikation.

## Next steps

- Optionen in der Integration pruefen (z. B. Polling-Intervall, Confirm-Timeout).
- Entitaeten im Dashboard einbinden und Automationen erstellen.
- Bei Problemen Logs in Home Assistant pruefen und ein Issue erstellen:
  https://github.com/k1h0/homeassistant-keba-rest-api/issues
