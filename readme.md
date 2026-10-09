# Entorno Virtual Python

Proyecto con configuración básica de entorno virtual en Python y control de versiones con Git listo para GitHub.

## Estructura del Proyecto

```text
├── .gitattributes      # Normalización de saltos de línea (LF/CRLF)
├── .gitignore          # Exclusión de archivos temporales y entorno virtual (.venv)
├── .env.example        # Plantilla de variables de entorno
├── requirements.txt    # Dependencias del proyecto
├── main.py             # Punto de entrada / script de prueba
└── readme.md           # Documentación del proyecto
```

## Configuración del Entorno Virtual

### 1. Activar el Entorno Virtual

- **PowerShell (Windows):**
  ```powershell
  .\.venv\Scripts\Activate.ps1
  ```
- **CMD (Windows):**
  ```cmd
  .venv\Scripts\activate.bat
  ```

### 2. Instalar Dependencias
Una vez activado el entorno:
```bash
pip install -r requirements.txt
```

### 3. Ejecutar el Proyecto
```bash
python main.py
```

### 4. Desactivar el Entorno
```bash
deactivate
```
