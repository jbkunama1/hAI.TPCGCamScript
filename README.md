# hAI.TPCGCamScript 📸

[![Docker Image](https://img.shields.io/github/v/release/jbkunama1/hAI.TPCGCamScript?label=version&color=blue)](https://github.com/jbkunama1/hAI.TPCGCamScript/releases)
[![License](https://img.shields.io/github/license/jbkunama1/hAI.TPCGCamScript?color=green)](LICENSE)
[![Build Status](https://img.shields.io/github/actions/workflow/status/jbkunama1/hAI.TPCGCamScript/docker-publish.yml?label=build&color=brightgreen)](https://github.com/jbkunama1/hAI.TPCGCamScript/actions)

---

### 🚀 Projekt-Übersicht
Containerisierte Bildverarbeitung für TPCG-Live-Kameras. Alles in einem Container: **Python-Worker**, **Web-Admin**, **FTP/FTPS** und **SFTP**.

### 🛠️ Features
- ✂️ **Bildverarbeitung:** Ein- oder Zwei-Kamera-Zuschnitt.
- 🔒 **Sicherheit:** FTPS (Port 21) & SFTP (Port 22) integriert.
- 🌐 **Web-Admin:** Live-Vorschau, Logs, Statistiken & Script-Editor.
- ⚡ **Performance:** Alles in einem schlanken Debian-Container.

---

### 📦 Installation

1. **Voraussetzungen:**
   - Docker & Docker Compose installiert.
   - Netzwerk `highfishNetwork` muss existieren:
     ```bash
     docker network create highfishNetwork
     ```

2. **Starten:**
   ```bash
   # Repository klonen
   git clone https://github.com/jbkunama1/hAI.TPCGCamScript.git
   cd hAI.TPCGCamScript

   # Container bauen und starten
   docker compose up -d --build
   ```

3. **Konfiguration:**
   - Passe die `.env` Datei an (siehe `.env.example`).
   - Daten liegen unter `/opt/hai-tpcg-cam-script/data/`.

---

### 🔌 Ports
| Port | Dienst |
| :--- | :--- |
| `8067` | Web-Admin (HTTP) |
| `21` | FTP / FTPS |
| `22` | SFTP |
| `30000-30010` | FTP Passive Ports |

---

### 🛡️ Sicherheit
- **Kein unverschlüsseltes FTP.**
- **Passwort-Schutz** für Admin-UI & API.
- **TruffleHog** Action zur Secret-Prüfung aktiv.

---
*Entwickelt mit ❤️ für TPCG-Kameras.*
