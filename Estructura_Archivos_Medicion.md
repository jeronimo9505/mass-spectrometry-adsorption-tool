# Documentación de Estructura de Archivos de Medición (.asc)

Este documento describe la especificación técnica, organización interna y métodos de lectura/graficación para los archivos de mediciones de espectrometría de masas (MID / Residual Gas Analyzer) con extensión `.asc`.

---

## 1. Especificación Técnica y Formato Físico

- **Extensión de archivo**: `.asc` (originalmente exportados desde archivos `.mdc`).
- **Formato de datos**: Texto plano delimitado por tabuladores (**TSV** - *Tab-Separated Values*).
- **Codificación de caracteres**: ASCII / UTF-8.
- **Caracter de salto de línea**: Retorno de carro estilo Mac clásico (`\r` / ASCII 13).
  > **Nota Importante para Carga**: No utiliza `\n` o `\r\n` estándar. Al procesar en Python, R, MATLAB o Excel, se debe especificar `\r` como separador de línea o reemplazar `\r` por `\n` antes de parsear.

---

## 2. Organización Interna del Documento

El archivo consta de 3 bloques principales:

```
+-------------------------------------------------------------------+
| BLOQUE 1: Metadatos Generales del Ensayo (Líneas 1 - 9)           |
+-------------------------------------------------------------------+
| BLOQUE 2: Metadatos de Canales / Masas m/z (Líneas 10 - 18)       |
+-------------------------------------------------------------------+
| BLOQUE 3: Tabla Matriz de Mediciones (Línea 19 en adelante)       |
+-------------------------------------------------------------------+
```

### Bloque 1: Metadatos Generales (Líneas 1 a 9)
Define las propiedades globales del experimento:
- `ASCII SAMPLE CYCLES :`: Nombre del proyecto fuente en formato `.mdc`.
- `DATE :`: Fecha de inicio de la medición (`DD/MM/YYYY`).
- `TIME :`: Hora de inicio (`HH:MM:SS`).
- `CONVERTED CYCLES :` / `Number of stored cycles`: Cantidad total de ciclos medidos.
- `Printed start cycle` / `Printed end cycle`: Rango de ciclos exportados en el archivo.
- `Number of stored datablocks`: Cantidad de bloques de datos almacenados (habitualmente `1`).

---

### Bloque 2: Definición de Canales de Masas (Líneas 10 a 18)
Identifica la magnitud física medida (`Ion Current` en Amperios `[A]`), los identificadores de canal (`'0/0'` a `'0/6'`), las masas relativas ($m/z$), las especies químicas asociadas y sus rangos de valor:

| Identificador | Masa ($m/z$) | Gas / Especie Química Asociada | Notación en Tabla |
| :--- | :--- | :--- | :--- |
| `'0/0'` | **14.13** | Nitrógeno atómico ($N^+$) / $N_2^{++}$ | `'0/0'` |
| `'0/1'` | **16.13** | Oxígeno atómico ($O^+$) / fragmento metano ($CH_4$) | `'0/1'` |
| `'0/2'` | **18.16** | Vapor de Agua ($H_2O^+$) | `'0/2'` |
| `'0/3'` | **28.19** | Nitrógeno molecular ($N_2^+$) / Monóxido de Carbono ($CO^+$) | `'0/3'` |
| `'0/4'` | **32.22** | Oxígeno molecular ($O_2^+$) | `'0/4'` |
| `'0/5'` | **40.22** | Argón ($Ar^+$) | `'0/5'` |
| `'0/6'` | **44.28** | Dióxido de Carbono ($CO_2^+$) | `'0/6'` |

---

### Bloque 3: Tabla Matriz de Datos (Línea 19 en adelante)

- **Línea de Encabezados (Línea 19)**:
  `Cycle \t Date \t Time \t RelTime[s] \t '0/0' \t '0/1' \t '0/2' \t '0/3' \t '0/4' \t '0/5' \t '0/6'`

- **Descripción de las Columnas**:
  1. `Cycle` *(Entero)*: Número de ciclo correlativo ($1, 2, 3 \dots$).
  2. `Date` *(Texto)*: Fecha de lectura (`DD/MM/YYYY`).
  3. `Time` *(Texto)*: Hora exacta del ciclo con precisión de centésimas de segundo (`HH:MM:SS:cc`).
  4. `RelTime[s]` *(Decimal)*: Tiempo relativo transcurrido en segundos desde el inicio de la prueba ($0.0, 0.81, 1.61 \dots$).
  5. `'0/0'` al `'0/6'` *(Decimales Científicos)*: Lecturas de corriente iónica en Amperios ($A$), ej. `2.32584E-010`.

---

## 3. Guía de Carga y Graficación en Python

Para cargar el archivo correctamente y convertir los canales a los nombres de los gases para graficar:

```python
import pandas as pd
import matplotlib.pyplot as plt
from io import StringIO

def cargar_archivo_asc(filepath):
    # 1. Leer manejando el fin de línea \r
    with open(filepath, 'rb') as f:
        text = f.read().decode('utf-8', errors='ignore')
    
    content = text.replace('\r\n', '\n').replace('\r', '\n')
    
    # 2. Cargar tabla ignorando las primeras 18 líneas de encabezado
    df = pd.read_csv(StringIO(content), skiprows=18, sep='\t')
    
    # Limpiar columnas vacías resultantes de tabuladores finales
    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
    
    # 3. Mapeo de canales a etiquetas legibles de gases
    mapeo_gases = {
        "'0/0'": "N+ (m/z 14.13)",
        "'0/1'": "O+ (m/z 16.13)",
        "'0/2'": "H2O (m/z 18.16)",
        "'0/3'": "N2 / CO (m/z 28.19)",
        "'0/4'": "O2 (m/z 32.22)",
        "'0/5'": "Ar (m/z 40.22)",
        "'0/6'": "CO2 (m/z 44.28)"
    }
    
    return df, mapeo_gases

# Ejemplo de uso y graficación:
# df, mapeo = cargar_archivo_asc("01092026 zz10 monolith final full 3 cycles.asc")
# plt.plot(df['RelTime[s]'], df["'0/3'"], label=mapeo["'0/3'"])
# plt.xlabel('Tiempo Relativo [s]')
# plt.ylabel('Corriente Iónica [A]')
# plt.legend()
# plt.show()
```
