# devsecops-demo

App web mínima (Flask + MySQL) para practicar CI/CD con GitHub Actions y DevSecOps,
con despliegue automático a Oracle Cloud cuando todo el pipeline pasa.

## Pipeline

```
push/PR ─┬─ Gitleaks (secretos) ───────┐
         ├─ Bandit + pip-audit (SAST/SCA) ─┤
         └─ pytest + MySQL real ───────┴─► Hadolint → Build → Trivy → Push a GHCR
                                                            │ (solo main)
                                                            ▼
                                        Deploy por SSH a Oracle → Smoke test → ZAP (DAST)
```

Aparte: `codeql.yml` (SAST con CodeQL) y `dependabot.yml` (actualiza pip, Docker y Actions).

## Probar en local

```bash
cp .env.example .env      # edita las contraseñas
docker compose up --build
# abre http://localhost:8080
```

## Configuración paso a paso

### 1. Repo en GitHub
```bash
cd devsecops-demo
git init -b main
git add .
git commit -m "Proyecto inicial DevSecOps"
git remote add origin https://github.com/AngelGabri3l/pruebapc2.git
git push -u origin main
```
Antes del primer push configura la VM y los Secrets (pasos 2 a 4); si no, el job `deploy` fallará.
(Repo **público** = CodeQL y GHCR sin complicaciones.)

### 2. VM en Oracle Cloud
- Crea una instancia Ubuntu (Always Free). Ojo con la arquitectura:
  - `VM.Standard.E2.1.Micro` = AMD/x86 (1 GB RAM: agrega swap) → deja `PLATFORM: linux/amd64`.
  - `VM.Standard.A1.Flex` = ARM → cambia `PLATFORM` a `linux/arm64` en `ci-cd.yml` y agrega el paso `docker/setup-qemu-action@v3` antes de buildx.
- Instala Docker en la VM:
  ```bash
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker $USER   # cierra sesión y vuelve a entrar
  ```
- Crea la carpeta de despliegue (una sola vez; `/opt` es de root):
  ```bash
  sudo mkdir -p /opt/app
  sudo chown $USER:$USER /opt/app
  ```
  El workflow clona ahí el repo (la primera vez) y luego hace `git fetch` + `git reset --hard <commit>` en cada deploy, y escribe el `.env` desde tus Secrets. La carpeta debe estar **vacía** antes del primer deploy y la VM necesita `git` (`sudo apt install -y git`). El repo es público, por eso se clona por HTTPS sin credenciales; si lo haces privado, agrega una *deploy key* de solo lectura. Para usar otra ruta, cambia `APP_DIR` en el job `deploy` de `ci-cd.yml`.
- Abre el puerto 80:
  1. En OCI: VCN → Security List → Ingress Rule: `0.0.0.0/0`, TCP, puerto `80`.
  2. En la VM Ubuntu:
     ```bash
     sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
     sudo netfilter-persistent save
     ```

### 3. Llave SSH exclusiva para el deploy (en tu PC)
```bash
ssh-keygen -t ed25519 -f gha_deploy -N "" -C "github-actions"
# Instala la pública en la VM:
ssh-copy-id -i gha_deploy.pub ubuntu@IP_DE_LA_VM
# Obtén la huella del servidor (para known_hosts):
ssh-keyscan -t ed25519 IP_DE_LA_VM
```
Nunca subas `gha_deploy` al repo (ya está en `.gitignore`).

### 4. Secrets (Settings → Environments → New environment `production` → Secrets)

| Secret | Qué poner |
|---|---|
| `OCI_HOST` | IP pública de la VM |
| `OCI_USER` | Usuario SSH (`ubuntu` u `opc`) |
| `OCI_SSH_KEY` | Contenido completo de `gha_deploy` (privada) |
| `OCI_KNOWN_HOSTS` | Salida de `ssh-keyscan -t ed25519 IP` |
| `MYSQL_ROOT_PASSWORD` | Contraseña root de MySQL |
| `DB_NAME` | Nombre de la BD (ej. `appdb`) |
| `DB_USER` | Usuario de la app (ej. `appuser`) |
| `DB_PASSWORD` | Contraseña del usuario de la app |

Evita `$`, comillas y espacios en las contraseñas (se escriben en un `.env`).
`GITHUB_TOKEN` lo da GitHub automáticamente, no lo crees.

En ese mismo Environment activa **Required reviewers** si quieres aprobación manual antes de desplegar.

### 5. Proteger `main`
Settings → Branches → regla para `main`: exigir pull request y que pasen los checks
`Gitleaks`, `Bandit + pip-audit`, `Pruebas con MySQL` y `Build, Hadolint, Trivy, Push`.

## Cosas para practicar
- Rompe algo a propósito: sube una dependencia vieja con CVE, un Dockerfile con `USER root`, o un secreto falso, y mira cómo falla el pipeline.
- Si Trivy bloquea por una vulnerabilidad del sistema base, actualiza la imagen base o documenta la excepción en un `.trivyignore`.
- Siguiente nivel: fijar las Actions por SHA, firmar la imagen con cosign y generar SBOM.

## Aviso
Revisa la configuración con alguien con experiencia antes de usarla en producción.
Si la usas en un trabajo o entrega, indica que se apoyó en IA generativa.
