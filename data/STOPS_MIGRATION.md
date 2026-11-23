# Inventario P19: normalización reversible

## Archivos y modelo

- `stops.json`: inventario fuente heredado; no se sobrescribe.
- `stops.legacy.json`: copia exacta byte por byte. El generador nunca la crea,
  modifica ni regenera.
- `stops.v2.json`: documento normalizado y versionado.
- `build_stops_v2.py`: generador determinista; exige que origen y respaldo sean
  idénticos y valida el documento antes de reemplazar la salida.
- `stops_v2.py`: validador estricto del documento.

El v2 separa `legacy_records`, `stop_entities`, menciones textuales por versión,
`corridor_trace` y `coverage_contexts`. Por falta de evidencia de identidad
física independiente, `stop_entities` está vacío. Los registros heredados,
incluido S-N-06, no son proyectables. Las menciones textuales de agosto no se
enlazan a IDs físicos por similitud de nombre. Q2 es una sola traza narrativa
sin división direccional inferida. El contexto de cobertura de P1 en mayo está
fuera del recorrido P19. El orden textual no representa distancia ni progresión
espacial.

Las coordenadas heredadas se conservan completas dentro de cada `legacy_record`
y se copian sin cambios a su ubicación de auditoría. Su confianza normalizada
es `null`; `legacy_confidence` conserva el valor histórico. La ubicación tiene
estado `legacy_unverified`, no de abordaje validado.

## Generar y verificar

Desde la raíz del repositorio, usando el intérprete del proyecto:

```powershell
\.venv\Scripts\python.exe data\build_stops_v2.py
\.venv\Scripts\python.exe -m pytest tests\test_stops_v2.py
\.venv\Scripts\python.exe -m pytest
```

El generador compara bytes de `stops.json` y `stops.legacy.json`. Ante una
diferencia, termina antes de abrir la salida v2; el inventario fuente, el
respaldo y cualquier `stops.v2.json` previo permanecen intactos. La salida se
escribe en un temporal dentro de `data/` y se reemplaza atómicamente solo tras
validar el documento generado.

## Comparar copias con PowerShell

```powershell
$sourceHash = (Get-FileHash -Algorithm SHA256 -LiteralPath .\data\stops.json).Hash
$backupHash = (Get-FileHash -Algorithm SHA256 -LiteralPath .\data\stops.legacy.json).Hash
$sourceHash
$backupHash
if ($sourceHash -ne $backupHash) { throw 'El respaldo legacy no coincide con el origen.' }
cmd /c fc /b data\stops.json data\stops.legacy.json
```

`fc /b` debe informar que no hay diferencias y los hashes deben coincidir.
El hash esperado al crear esta copia es:

```text
C67E4B7C5784B33DEC4C232D3056E7940458A1ECB1022607E695D8F7560E3963
```

## Restaurar el inventario original sin depender de Git

Los consumidores actuales siguen usando `stops.json`; para volver al formato
anterior basta con no seleccionar `stops.v2.json`. Si `stops.json` necesita ser
restaurado desde la copia, primero preserve cualquier cambio posterior con una
copia separada y verifique los hashes:

```powershell
Copy-Item -LiteralPath .\data\stops.json -Destination .\data\stops.before-restore.json
$backupHash = (Get-FileHash -Algorithm SHA256 -LiteralPath .\data\stops.legacy.json).Hash
if ($backupHash -ne 'C67E4B7C5784B33DEC4C232D3056E7940458A1ECB1022607E695D8F7560E3963') {
    throw 'La copia legacy no coincide con el hash de referencia; no restaurar.'
}
Copy-Item -LiteralPath .\data\stops.legacy.json -Destination .\data\stops.json -Force
cmd /c fc /b data\stops.json data\stops.legacy.json
```

La restauración copia bytes del respaldo; no los reserializa como JSON. No
ejecute el generador para reparar o regenerar el respaldo. Conserve
`stops.before-restore.json` si había cambios que deben revisarse o recuperarse.
